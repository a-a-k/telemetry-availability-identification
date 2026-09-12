"""Inspect actual saved PCM representations and their calibration wrapper counts."""
from collections import Counter
from fractions import Fraction
import os
from pathlib import Path
import tempfile
from xml.etree import ElementTree as ET

from audit_v3_attempts_v1 import ARCHIVE,MAIN_RUN,MAIN_HEAD,fetch,read,write,digest
from telemetry_availability.v4_pcm_recurrence_audit_v1 import audit as recurrence

XSI='{http://www.w3.org/2001/XMLSchema-instance}type'


def shape(node,depth=0):
    return dict(tag=node.tag,attributes=node.attrib,
        children=[shape(c,depth+1) for c in node] if depth<6 else [],truncated=depth>=6 and len(node)>0)


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('saved application PCM inspection is remote only')
    config=read(Path('configs/v4_pmx_b0_explanation_v1.json'))
    sources={s['name']:s for part in read(ARCHIVE)['parts'] for s in part['sources']}
    results=[];explanations=[]
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
                calculation=recurrence((path/'extracted.repository').read_text(),(path/'extracted.usagemodel').read_text())
                method='PMX' if model['variant']=='conditional_local' else 'PMX_inclusive'
                forecast=case['forecasts'][model['operation']][method]
                if forecast['status']!='ok' or abs(calculation['probability']-forecast['probability'])>1e-10:
                    raise ValueError('independent saved-PCM recurrence does not reproduce Palladio')
                b0=case['forecasts'][model['operation']]['B0'];n=wrapper_oracle['invocations']
                if n!=b0['attempts'] or n-wrapper_oracle['inclusive_errors']!=b0['successes']:
                    raise ValueError('saved wrapper does not reproduce B0 calibration ledger')
                n0=wrapper_oracle['no_child_error_invocations'];e0=wrapper_oracle['local_errors_without_child_error']
                identity_holds=wrapper_oracle['child_error_parent_success']==0 and n0>0
                q=Fraction(e0,n0) if identity_holds else None
                if identity_holds and Fraction(n0-e0,n)!=Fraction(b0['exact_fraction']):
                    raise ValueError('empirical conditional wrapper identity failed')
                decomposition=(1-float(q))*(calculation['modeled_subcalls_survival']-n0/n) if q is not None else None
                if model['variant']=='conditional_local' and (decomposition is None or
                    abs(decomposition-(calculation['probability']-b0['probability']))>1e-10):
                    raise ValueError('PMX-B0 discrepancy does not reproduce the wrapper decomposition')
                labels={operation:sorted({r['service']+'.'+r['operation'] for r in mapping if r['pmx_operation']==operation})
                    for operation in calculation['operations']}
                resources=ET.parse(path/'extracted.resourceenvironment').getroot()
                explanations.append(dict(case=key,operation=model['operation'],variant=model['variant'],
                    source_artifact_id=provenance['artifact_id'],source_artifact_sha256=provenance['sha256'],
                    model_id=model['model_id'],model_files_sha256=model['files'],
                    calibration_attempts=n,calibration_successes=b0['successes'],b0_exact=b0['exact_fraction'],
                    recorded_pmx_probability=forecast['probability'],recalculated_probability=calculation['probability'],
                    recurrence_absolute_error=abs(calculation['probability']-forecast['probability']),
                    pmx_minus_b0=calculation['probability']-b0['probability'],
                    external_wrapper_uses_calibration_success_labels=True,
                    wrapper_conditional_error_exact=str(q) if q is not None else None,
                    empirical_subcalls_survival_exact=str(Fraction(n0,n)),
                    modeled_subcalls_survival=calculation['modeled_subcalls_survival'],
                    conditional_wrapper_identity_holds=identity_holds,
                    conditional_difference_decomposition=decomposition,operation_labels=labels,recurrence=calculation,
                    physical_reliability_attributes=[dict(tag=node.tag,attributes={k:v for k,v in node.attrib.items()
                        if 'MTT' in k or 'failure' in k.lower()}) for node in resources.iter()
                        if any('MTT' in k or 'failure' in k.lower() for k in node.attrib)]))
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
    write(Path('workflow-results/pmx-explanation/explanation.json'),dict(
        version='v4-pmx-b0-explanation-v1',run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
        source_main_run=MAIN_RUN,source_main_head=MAIN_HEAD,
        all_saved_Palladio_answers_reproduced=True,tolerance=1e-10,rows=explanations,
        external_test_outcomes_used=False,new_forecasts_fitted=False,new_benchmark_algorithm_claimed=False))


if __name__=='__main__':main()
