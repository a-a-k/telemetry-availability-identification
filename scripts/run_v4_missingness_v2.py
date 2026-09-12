"""Remote missingness experiment on the unchanged independent primary census."""
import argparse
import json
import os
from pathlib import Path
import tempfile

import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.v3_primary_projection import read,write,sha
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
from telemetry_availability.v4_primary_capture_v1 import load
from telemetry_availability.v4_missingness_v1 import experiment

SOURCE_RUN=34703686592
SOURCE_HEAD='12ddb09369ee6e0b60ca4c7db6fe1e749530b7df'


def fetch(artifacts,name,allowed,destination):
    matches=[a for a in artifacts if a['name']==name]
    if len(matches)!=1:raise ValueError('missing/duplicate independent evidence: '+name)
    a=matches[0]
    if a['workflow_run']['id']!=SOURCE_RUN or a['workflow_run']['head_sha']!=SOURCE_HEAD or a['expired']:
        raise ValueError('missingness source artifact identity differs')
    files=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
    if set(files)!=allowed:raise ValueError('incomplete evidence role')
    for member,blob in files.items():
        path=destination/member;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)
    return {k:a[k] for k in ('id','name','digest','size_in_bytes')}


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('real missingness experiment is remote only')
    config=read(Path('configs/v4_missingness_execution_v2.json'))
    for path,expected in config['source_locks'].items():
        if sha(Path(path))!=expected:raise ValueError('fixed missingness code changed')
    run=transport.read_api(f'actions/runs/{SOURCE_RUN}')
    if (run['head_sha']!=SOURCE_HEAD or run['path']!='.github/workflows/v4-confirmation-v2.yml'
        or run['run_attempt']!=1 or run['status']!='completed' or run['conclusion']!='success'):
        raise ValueError('independent primary series has not completed successfully')
    settings,_,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    cases=[c for c in cases if c['profile']==args.profile]
    artifacts=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/artifacts','artifacts')
    results=[]
    for case in cases:
        key=case['key'];identity=case['identity']
        with tempfile.TemporaryDirectory(prefix='independent-missingness-') as directory:
            root=Path(directory);source={}
            source['bounds']=fetch(artifacts,f'v4-confirmation-bounds-{key}-{SOURCE_RUN}',
                {'compact.json','sealed/bounds.json','sealed/receipt.json','sealed/read-audit.json','sealed/seal.json'},root/'bounds')
            source['primary_compact']=fetch(artifacts,f'v4-confirmation-primary-compact-{key}-{SOURCE_RUN}',{'compact.json'},root/'primary-compact')
            names={'test.json','controls.json'} if args.profile=='spring_petclinic_microservices' else {'test.json'}
            source['primary_full']=fetch(artifacts,f'v4-confirmation-primary-full-{key}-{SOURCE_RUN}',names,root/'primary')
            bounded,_=load(root/'bounds/sealed','realized_bounds',identity)
            compact=read(root/'primary-compact/compact.json');primary=read(root/'primary/test.json')
            if (compact['identity']!=identity or compact['run']!=str(SOURCE_RUN) or compact['head']!=SOURCE_HEAD
                or compact['bound_seal_sha256']!=sha(root/'bounds/sealed/seal.json')
                or primary['independently_verified_attempts']!=primary['primary_attempts']
                or primary['primary_attempts']!=3600 or len(primary['primary_verdicts'])!=3600
                or primary['selected_by_E_equals_Y'] is not False):raise ValueError('primary verification population differs')
            operations=[]
            for row in bounded['bounds.json']['operations']:
                op=row['operation']
                if row['status']=='unsupported':
                    operations.append(dict(operation=op,status='unsupported',reason=row['reason'],attempts=row['attempts']));continue
                records=[r for r in primary['attempts'] if r['operation']==op]
                for record in records:
                    if record['outcome']!=primary['primary_verdicts'][record['request_id']]['outcome']:
                        raise ValueError('missingness outcome does not match primary verdict')
                model=bounded['bounds.json']['models'][op]
                result=experiment(model,records,config['levels'],config['mechanisms'],config['seed'])
                operations.append(dict(operation=op,status='experimented',attempts=len(records),**result))
            output=dict(version=config['version'],identity=identity,source_run=SOURCE_RUN,source_head=SOURCE_HEAD,
                run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],sources=source,
                config_sha256=sha(Path('configs/v4_missingness_execution_v2.json')),operations=operations,
                selected_by_E_equals_Y=False,additional_native_masks_not_topology_deletion=True,
                source_primary_label_mismatches=primary['primary_label_mismatches'])
            write(args.out/(key+'.json'),output);results.append(dict(case=key,operations=len(operations)))
            print(json.dumps(results[-1]),flush=True)
    write(args.out/'receipt.json',dict(profile=args.profile,cases=results,run=os.environ['GITHUB_RUN_ID'],
        head=os.environ['GITHUB_SHA'],source_run=SOURCE_RUN,source_head=SOURCE_HEAD))


if __name__=='__main__':main()
