"""Strict compact-only retention, callable locally or by the report workflow."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import retain_v3_comparison_compact_v4 as transport


def require(value,message):
    if not value:raise ValueError(message)


def validate_compact(result,config):
    index=config['profiles'].index(result['profile']);cases=result['cases'];ids={c['case_id'] for c in cases}
    require(len(cases)==len(ids)==config['expected_models'][index] and len(result['absent'])==config['expected_original_absences'][index],'case census differs')
    expected={(i,m,r,p) for i in ids for m in config['methods'] for r in range(config['technical_rounds']) for p in config['phases']}
    actual=[(r['case_id'],r['method'],r['round'],r['phase']) for r in result['records']]
    require(len(actual)==len(expected) and set(actual)==expected and result['complete_census'],'planned record census differs')
    by_id={c['case_id']:c for c in cases}
    for row in result['records']:
        if row['status']=='qualified':
            require(row['estimates']==by_id[row['case_id']]['expected'][row['phase']],'record differs from exact reference')
            require(row['total_ns']>0 and row['query_including_update_ns']>0 and row['key_check_ns']>=0,'invalid timing')
            require(set(row['estimates'])==set(by_id[row['case_id']]['expected']['initial']) and len(row['estimates'])==11,'functional census differs')
        else:require(row['status']=='failed' and row.get('error'),'undocumented failed case')
    require(result['qualified']==all(r['status']=='qualified' for r in result['records']),'qualification flag differs')
    resource_keys=[(r['case_id'],r['method'],r['round']) for r in result['resources']]
    require(len(resource_keys)==len(ids)*len(config['methods'])*config['technical_rounds'] and len(set(resource_keys))==len(resource_keys),'resource census differs')
    forbidden={'model','models','observation_categories','replicas','signal_ids','category_certificates','lower_witness','upper_witness','native_spans'}
    def walk(obj):
        if isinstance(obj,dict):
            require(not set(obj)&forbidden,'full model/native payload in compact artifact')
            for value in obj.values():walk(value)
        elif isinstance(obj,list):
            for value in obj:walk(value)
    walk(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=int,required=True);parser.add_argument('--out',type=Path)
    args=parser.parse_args();run=transport.read_api(f'actions/runs/{args.run}')
    require(run['status']=='completed' and run['run_attempt']==1 and run['path']=='.github/workflows/v3-exact-backends-v1.yml','wrong/incomplete source run')
    source=transport.read_api(f'contents/configs/v3_exact_backends_v1.json?ref={run["head_sha"]}')
    protocol=base64.b64decode(source['content']);config=json.loads(protocol)
    items=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts');by_name={i['name']:i for i in items}
    out=args.out or Path(f'docs/evidence/v3-exact-backends-{args.run}')
    transport.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    receipts=[]
    for profile in config['profiles']:
        item=by_name[f'v3-exact-backends-compact-{profile}-{args.run}']
        require(item['workflow_run']['head_sha']==run['head_sha'] and item['size_in_bytes']<=20_000_000,'wrong/oversized compact artifact')
        raw=transport.api(f'actions/artifacts/{item["id"]}/zip');names={'protocol.json','environment.json','results.json'}
        members=transport.check_archive(raw,item,names)
        require(set(members)==names and members['protocol.json']==protocol,'compact protocol/member census differs')
        result=json.loads(members['results.json']);environment=json.loads(members['environment.json'])
        for value in (result,environment):
            require(value['profile']==profile and value['run_id']==args.run and value['head']==run['head_sha']
                    and value['config_sha256']==sha256(protocol).hexdigest(),'compact source identity differs')
        validate_compact(result,config)
        root=out/profile;transport.persist(root/'compact.zip',raw)
        for name,value in members.items():transport.persist(root/name,value)
        transport.persist(root/'artifact-api.json',transport.encoded(item))
        receipts.append(dict(profile=profile,artifact_id=item['id'],bytes=len(raw),sha256=sha256(raw).hexdigest(),
                             records=len(result['records']),failed=sum(r['status']=='failed' for r in result['records']),qualified=result['qualified']))
    transport.persist(out/'run-api.json',transport.encoded(run))
    receipt=dict(version='v3-exact-backends-compact-retention-v1',run_id=args.run,head=run['head_sha'],conclusion=run['conclusion'],
                 artifacts=receipts,full_models_downloaded_locally=False,local_model_execution=False)
    transport.persist(out/'retention.json',transport.encoded(receipt));print(json.dumps(receipt))


if __name__=='__main__':main()
