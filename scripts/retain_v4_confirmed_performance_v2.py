"""Retain complete new compact timings with the unchanged exact v2 validator."""
import argparse
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from retain_v3_exact_comparison_v2 import validate_compact,require
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
from telemetry_availability.v3_comparison_roles_v1 import campaign_id


def validate(result,config):
    _,design,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    expected={campaign_id(c['identity'])+'/'+op:dict(c['identity'],operation=op)
        for c in cases if c['profile']==result['profile'] for op in design['applications'][c['profile']]}
    actual={c['case_id']:c['parameters'] for c in result['cases']}
    require(len(actual)==len(result['cases']),'duplicate measured model')
    for absent in result['absent']:
        require(absent['case_id'] not in actual and absent['reason'],'invalid/overlapping structural absence')
        actual[absent['case_id']]=absent['identity']
    require(actual==expected and len(actual)==config['planned_operation_cases'][result['profile']],
        'complete planned case identities differ')
    require(result['source']['run_id']==config['source_run'] and result['source']['head']==config['source_head']
        and result['source']['all_supported_models_included'] is True and result['source']['selection_uses_performance'] is False,
        'new calibration source or selection differs')
    checked=deepcopy(config);index=config['profiles'].index(result['profile'])
    checked['expected_models'][index]=len(result['cases']);checked['expected_original_absences'][index]=len(result['absent'])
    validate_compact(result,checked)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);args=p.parse_args()
    run=transport.read_api(f'actions/runs/{args.run}')
    require(run['status']=='completed' and run['run_attempt']==1 and run['path']=='.github/workflows/v4-confirmed-performance-v2.yml','wrong performance run')
    meta=transport.read_api('contents/configs/v4_confirmed_performance_v2.json?ref='+run['head_sha'])
    protocol=base64.b64decode(meta['content']);config=json.loads(protocol)
    artifacts=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts');out=Path(f'docs/evidence/v4-confirmed-performance-v2-{args.run}')
    transport.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n');rows=[]
    for profile in config['profiles']:
        matches=[a for a in artifacts if a['name']==f'v4-confirmed-performance-compact-{profile}-{args.run}'];require(len(matches)==1,'missing compact profile')
        a=matches[0];require(a['workflow_run']['head_sha']==run['head_sha'] and a['workflow_run']['id']==args.run,'wrong provider source')
        names={'protocol.json','environment.json','results.json'};members=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,names)
        require(set(members)==names and members['protocol.json']==protocol,'protocol/member bytes differ')
        result=json.loads(members['results.json']);environment=json.loads(members['environment.json'])
        for value in (result,environment):
            require(value['run_id']==args.run and value['head']==run['head_sha'] and value['profile']==profile
                and value['config_sha256']==sha256(protocol).hexdigest(),'result provenance differs')
        validate(result,config)
        for name,data in members.items():transport.persist(out/profile/name,data)
        transport.persist(out/profile/'artifact-api.json',transport.encoded(a))
        rows.append(dict(profile=profile,artifact_id=a['id'],sha256=a['digest'],bytes=a['size_in_bytes'],
            models=len(result['cases']),absent=len(result['absent']),records=len(result['records']),failed=sum(r['status']!='qualified'for r in result['records'])))
    receipt=dict(run_id=args.run,head=run['head_sha'],conclusion=run['conclusion'],artifacts=rows,
        source_run=config['source_run'],source_head=config['source_head'],local_model_execution=False,full_models_downloaded=False)
    transport.persist(out/'retention.json',transport.encoded(receipt));transport.persist(out/'run-api.json',transport.encoded(run))
    print(json.dumps(receipt))


if __name__=='__main__':main()
