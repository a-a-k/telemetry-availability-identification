"""Keep repaired aggregate bytes under their actual producer, separate from source."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from v4_confirmed_source_v3 import SOURCE_RUN,SOURCE_HEAD


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);args=p.parse_args()
    run=transport.read_api(f'actions/runs/{args.run}')
    if run['path']!='.github/workflows/v4-confirmation-summary-v3.yml' or run['status']!='completed' or run['conclusion']!='success' or run['run_attempt']!=1:
        raise ValueError('aggregate repair source differs')
    items=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    if len(items)!=1:raise ValueError('aggregate artifact census differs')
    a=items[0]
    if a['workflow_run']['id']!=args.run or a['workflow_run']['head_sha']!=run['head_sha']:raise ValueError('aggregate provider identity differs')
    allowed={'comparison.json','comparison-seal.json','confirmation.json','confirmation-seal.json','aggregation-provenance.json'}
    files=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
    if set(files)!=allowed:raise ValueError('aggregate output member census differs')
    for name,key in [('comparison','run_id'),('confirmation','run')]:
        value=json.loads(files[name+'.json']);seal=json.loads(files[name+'-seal.json'])
        if (int(value[key])!=SOURCE_RUN or value['head']!=SOURCE_HEAD or int(value['analysis_run'])!=args.run
            or value['analysis_head']!=run['head_sha'] or seal['files']!={name+'.json':sha256(files[name+'.json']).hexdigest()}):
            raise ValueError('measurement and actual aggregation identities differ')
    out=Path(f'docs/evidence/v4-confirmation-summary-v3-{args.run}')
    for name,raw in files.items():transport.persist(out/name,raw)
    transport.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    transport.persist(out/'retention.json',transport.encoded(dict(run=args.run,head=run['head_sha'],source_run=SOURCE_RUN,
        source_head=SOURCE_HEAD,artifact={k:a[k]for k in ('id','name','size_in_bytes','digest')},local_model_execution=False)))
    result=json.loads(files['confirmation.json'])
    print(json.dumps(dict(run=args.run,qualified_within_declared_conditions=result['qualified_within_declared_conditions'],checks=result['checks'])))


if __name__=='__main__':main()
