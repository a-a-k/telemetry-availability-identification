"""Inspect actual saved PCM representations and their calibration wrapper counts."""
from collections import Counter
import os
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET

from audit_v3_attempts_v1 import ARCHIVE,MAIN_RUN,MAIN_HEAD,fetch,read,write,digest

XSI='{http://www.w3.org/2001/XMLSchema-instance}type'


def shape(node,depth=0):
    return dict(tag=node.tag,attributes=node.attrib,
        children=[shape(c,depth+1) for c in node] if depth<6 else [],truncated=depth>=6 and len(node)>0)


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('saved application PCM inspection is remote only')
    config=read(Path('configs/v4_pmx_b0_explanation_v1.json'))
    sources={s['name']:s for part in read(ARCHIVE)['parts'] for s in part['sources']}
    results=[]
    for case in config['cases']:
        key=case['artifact_key']
        with tempfile.TemporaryDirectory(prefix='pmx-explanation-') as directory:
            root=Path(directory);provenance=fetch(sources[f'v3-comparison-pmx-extraction-{key}-{MAIN_RUN}'],root/'extraction')
            records=list((root/'extraction').glob('extraction-*.json'))
            if len(records)!=1:raise ValueError('ambiguous PCM extraction record')
            record=read(records[0])
            if record['head_sha']!=MAIN_HEAD or str(record['run_id'])!=str(MAIN_RUN):raise ValueError('PCM extraction source differs')
            models=[]
            for model in record['models']:
                path=root/'extraction/models'/model['model_id']
                for name,expected in model['files'].items():
                    if digest(path/name)!=expected:raise ValueError('serialized PCM bytes differ')
                projection=root/'extraction/projection/cases'/model['case_id']
                oracle=read(projection/'operation_oracle.json');mapping=read(projection/'mapping.json')
                request_audit=read(projection/'request_audit.json')
                wrappers={r['pmx_operation'] for r in mapping if r['synthetic']}
                if len(wrappers)!=1:raise ValueError('external operation wrapper is not unique')
                wrapper=next(iter(wrappers));wrapper_oracle=next(r for r in oracle if r['operation']==wrapper)
                if (wrapper_oracle['invocations']!=len(request_audit)
                    or wrapper_oracle['inclusive_errors']!=sum(not r['semantic_success'] for r in request_audit)):
                    raise ValueError('external wrapper counts do not reproduce the calibration request ledger')
                repository=ET.parse(path/'extracted.repository').getroot()
                names={n.attrib['id']:n.attrib['entityName'] for n in repository.iter() if 'id' in n.attrib and 'entityName' in n.attrib}
                seffs={names[n.attrib['describedService__SEFF']]:n for n in repository.iter() if n.tag=='serviceEffectSpecifications__BasicComponent'}
                types=Counter(n.get(XSI,'') for n in repository.iter() if n.get(XSI))
                models.append(dict(operation=model['operation'],variant=model['variant'],model_id=model['model_id'],
                    repository_sha256=digest(path/'extracted.repository'),wrapper=wrapper,wrapper_oracle=wrapper_oracle,
                    calibration_attempts=len(request_audit),calibration_successes=sum(r['semantic_success'] for r in request_audit),
                    all_wrapper_outcomes_from_calibration=all(r['external_outcome_used_for_wrapper'] for r in request_audit),
                    forecasts=case['forecasts'][model['operation']],operation_oracle=oracle,
                    pcm_action_types=dict(types),wrapper_SEFF_shape=shape(seffs[wrapper]),
                    other_SEFF_shapes=[dict(operation=k,shape=shape(v)) for k,v in list(seffs.items()) if k!=wrapper][:2],
                    usage_shape=shape(ET.parse(path/'extracted.usagemodel').getroot()),
                    parameter_and_loop_changes=model['changes']))
            results.append(dict(case=key,source=provenance,models=models))
            print(key,'saved models:',len(models),flush=True)
    write(Path('workflow-results/pmx-explanation/inspection.json'),dict(
        run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],cases=results,
        external_test_outcomes_used=False,new_forecasts_fitted=False))


if __name__=='__main__':main()
