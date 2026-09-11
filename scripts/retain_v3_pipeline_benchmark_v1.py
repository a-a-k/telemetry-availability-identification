"""Retain only the three allowlisted compact benchmark documents per application."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from archive_h_exec_evidence_v1 import require
import retain_v3_comparison_compact_v4 as transport


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=int,required=True)
    args=parser.parse_args()
    run=transport.read_api(f'actions/runs/{args.run}')
    require(run['path'] in ('.github/workflows/v3-pipeline-benchmark-v1.yml','.github/workflows/v3-pipeline-benchmark-v2.yml')
            and run['run_attempt']==1 and run['status']=='completed', 'wrong or unfinished benchmark')
    protocol_raw=subprocess.check_output(['git','show',run['head_sha']+':configs/v3_pipeline_benchmark_v1.json'])
    protocol=json.loads(protocol_raw)
    items=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    by_name={a['name']:a for a in items}
    names={'protocol.json','environment.json','results.json'}
    root=Path(f'docs/evidence/v3-pipeline-benchmark-{args.run}')
    transport.persist(root/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    receipts=[]
    for profile in protocol['applications']:
        key=f'v3-pipeline-benchmark-compact-{profile}-{args.run}'
        require(key in by_name,'missing compact application: '+profile)
        item=by_name[key]
        require(item['workflow_run']['head_sha']==run['head_sha'] and item['size_in_bytes']<=10_000_000,
                'compact identity/size differs')
        data=transport.api(f'actions/artifacts/{item["id"]}/zip')
        members=transport.check_archive(data,item,names)
        require(set(members)==names,'compact member census differs')
        require(json.loads(members['protocol.json'])==protocol,'executed protocol differs')
        result=json.loads(members['results.json']);environment=json.loads(members['environment.json'])
        require(result['profile']==profile and result['run_id']==args.run
                and result['workflow_head']==run['head_sha'] and result['config_sha256']==sha256(protocol_raw).hexdigest()
                and environment['workflow_head']==run['head_sha'] and environment['profile']==profile,
                'result identity/source differs')
        expected=[(r,m) for r,order in enumerate(protocol['scale_orders']) for m in order]
        require([(r['repetition'],r['multiplier']) for r in result['records']]==expected,
                'planned timing census differs')
        for row in result['records']:
            require(row['workload']['attempts']==3600*row['multiplier']
                    and row['workload']['independent_new_observations']==0, 'workload count/scope differs')
            if row['status']=='qualified':
                require(row['original_forecasts_preserved'] and row['pmx']['controls_qualified'],
                        'unqualified forecast verification')
                require(all(s['exit_code']==0 and not s['timed_out'] for method in ('graph','pmx')
                            for s in row[method]['stages'].values()),'failed timed command promoted')
                require(abs(row['speedup_pmx_over_graph']-row['pmx']['wall_seconds']/row['graph']['wall_seconds'])<1e-12,
                        'recorded speed ratio differs')
        out=root/profile
        transport.persist(out/'compact.zip',data)
        for name,raw in members.items():transport.persist(out/name,raw)
        transport.persist(out/'artifact-api.json',transport.encoded(item))
        receipts.append(dict(profile=profile,artifact_id=item['id'],bytes=len(data),sha256=sha256(data).hexdigest(),
                             records=len(result['records']),qualified=sum(r['status']=='qualified' for r in result['records'])))
    transport.persist(root/'run-api.json',transport.encoded(run))
    record=dict(version='v3-pipeline-benchmark-compact-retention-v1',run_id=args.run,head=run['head_sha'],
                workflow_conclusion=run['conclusion'],artifacts=receipts,full_native_or_model_payloads_downloaded=False,
                local_model_execution=False,provider_digests_and_member_census_verified=True)
    transport.persist(root/'retention.json',transport.encoded(record))
    print(json.dumps(record))


if __name__=='__main__':main()
