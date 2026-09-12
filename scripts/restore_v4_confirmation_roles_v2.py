"""Trusted byte-only transport of twelve fixed unopened confirmation cohorts."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.v4_confirmation_orchestration_v2 import SOURCE_RUN,SOURCE_HEAD
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
from telemetry_availability.v3_primary_projection import write


def main():
    p=argparse.ArgumentParser();p.add_argument('--key',required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('role transport is remote only')
    run=transport.read_api(f'actions/runs/{SOURCE_RUN}')
    if (run['head_sha']!=SOURCE_HEAD or run['path']!='.github/workflows/v4-confirmation-v1.yml'
        or run['run_attempt']!=1 or run['status']!='completed' or run['conclusion']!='failure'):
        raise ValueError('fixed technically incomplete source run differs')
    jobs=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/jobs','jobs')
    if any(j['name'].startswith(('evaluate','primary','bounds','freeze')) and j['conclusion']!='skipped' for j in jobs):
        raise ValueError('the fixed source reached a post-freeze job; cannot assert unopened outcomes')
    _,_,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    case=next(c for c in cases if c['key']==args.key)
    if case['profile']=='spring_petclinic_microservices':raise ValueError('lost cohorts cannot be substituted')
    artifacts=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/artifacts','artifacts')
    if any(a['name'].startswith(('v4-confirmation-evaluation-','v4-confirmation-primary-compact-','v4-confirmation-primary-full-')) for a in artifacts):
        raise ValueError('source has outcome-derived artifacts')
    roles={
        'ordinary':('roles/ordinary',{'declarations.json','requests.json','native.json','probes.json','manifest.json','seal.json'},'graph_input_seal_sha256'),
        'pmx-input':('roles/pmx',{'requests.json','native.json','manifest.json','seal.json'},'pmx_input_seal_sha256'),
        'closed-evaluator':('roles/evaluator',{'requests.json','probes.json','manifest.json','seal.json'},'evaluator_seal_sha256'),
        'test-binding':('roles/test-binding',{'requests.json','native.json','probes.json','declarations.json','manifest.json','seal.json'},'test_binding_seal_sha256'),
        'primary-closed':('roles/primary-closed',{'requests.json','health.json','events.json','manifest.json','seal.json'},'primary_closed_seal_sha256'),
        'receipt':('public',{'receipt.json','costs.json'},None)}
    received={};provenance=[]
    for role,(relative,allowed,key) in roles.items():
        name=f'v4-confirmation-{role}-{args.key}-{SOURCE_RUN}'
        matches=[a for a in artifacts if a['name']==name]
        if len(matches)!=1:raise ValueError('incomplete fixed cohort: '+name)
        a=matches[0]
        if a['workflow_run']['id']!=SOURCE_RUN or a['workflow_run']['head_sha']!=SOURCE_HEAD:raise ValueError('provider role identity differs')
        files=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
        if set(files)!=allowed:raise ValueError('role byte census differs')
        for member,content in files.items():transport.persist(args.out/relative/member,content)
        # No estimator or outcome parser is invoked. Only the public seal is parsed.
        if key:
            seal=json.loads(files['seal.json'])
            if set(seal['files'])!=allowed-{'seal.json'} or any(sha256(files[n]).hexdigest()!=h for n,h in seal['files'].items()):raise ValueError('source role seal differs')
            if 'identity' in seal and seal['identity']!=case['identity']:raise ValueError('sealed identity differs')
            received[key]=sha256(files['seal.json']).hexdigest()
        else:receipt=json.loads(files['receipt.json'])
        provenance.append({k:a[k] for k in ('id','name','digest','size_in_bytes')})
    if (receipt['identity']!=case['identity'] or str(receipt['acquisition_run'])!=str(SOURCE_RUN)
        or receipt['acquisition_head']!=SOURCE_HEAD or any(receipt[k]!=v for k,v in received.items())):
        raise ValueError('public receipt does not bind the original role bytes')
    write(args.out/'transport.json',dict(source_run=SOURCE_RUN,source_head=SOURCE_HEAD,identity=case['identity'],
        artifacts=provenance,only_bytes_and_public_seals_interpreted=True,outcomes_opened=False,new_acquisition=False))
    print('Preserved one fixed cohort with exact original sealed bytes; no outcome interpretation.')


if __name__=='__main__':main()
