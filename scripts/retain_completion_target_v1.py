"""Retain compact evidence and byte-check its complete remote scalar tables."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import retain_v3_comparison_compact_v4 as t


def main():
    p=argparse.ArgumentParser(); p.add_argument('--run', type=int, required=True); args=p.parse_args()
    run=t.read_api(f'actions/runs/{args.run}')
    versions={'.github/workflows/v5-completion-target-v1.yml':1,'.github/workflows/v5-completion-target-v2.yml':2}
    if run['path'] not in versions or run['status']!='completed' or run['run_attempt']!=1:
        raise ValueError('wrong or unfinished source')
    cfg_raw=subprocess.check_output(['git','show',run['head_sha']+f':configs/v5_completion_target_v{versions[run["path"]]}.json'])
    config=json.loads(cfg_raw)
    artifacts=t.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts'); by={a['name']:a for a in artifacts}
    out=Path(f'docs/evidence/v5-completion-target-{args.run}'); tables=Path(f'docs/tables/v5-completion-target-{args.run}')
    attr=b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n'
    t.persist(out/'.gitattributes',attr); t.persist(out/'run-api.json',t.encoded(run));t.persist(out/'artifacts-api.json',t.encoded(artifacts))
    receipts=[]
    required={'protocol.json','environment.json','timings.json','semantics.json','receipt.json'}
    for profile in config['operation_cases']:
        name=f'v5-completion-compact-{profile}-{args.run}'
        if name not in by:
            if run['conclusion']=='success': raise ValueError('missing successful profile')
            continue
        a=by[name]
        if a['workflow_run']['head_sha']!=run['head_sha'] or a['workflow_run']['id']!=args.run or a['size_in_bytes']>25_000_000:
            raise ValueError('compact provider identity or size differs')
        raw=t.api(f"actions/artifacts/{a['id']}/zip")
        members=t.check_archive(raw,a,required|{'failure.json'})
        if run['conclusion']=='success' and set(members)!=required: raise ValueError('complete successful compact census differs')
        if 'protocol.json' in members and json.loads(members['protocol.json'])!=config: raise ValueError('executed configuration differs')
        if 'receipt.json' in members:
            r=json.loads(members['receipt.json'])
            if (r['run']!=str(args.run) or r['head']!=run['head_sha'] or r['profile']!=profile
                or r['config_sha256']!=sha256(cfg_raw).hexdigest() or r['source_run']!=config['source_run']
                or r['source_head']!=config['source_head']): raise ValueError('source/producer/configuration binding differs')
        for name, data in members.items():t.persist(out/profile/name,data)
        receipts.append({k:a[k] for k in ('id','name','size_in_bytes','digest')})
    record=dict(run=args.run,head=run['head_sha'],conclusion=run['conclusion'],compact_artifacts=receipts,
                full_model_or_observation_artifacts_downloaded=False,local_model_execution=False)
    if run['conclusion']=='success':
        subprocess.run([sys.executable,'scripts/summarize_completion_target_v1.py','--source',str(out),'--out',str(tables)],check=True)
        a=by[f'v5-completion-tables-{args.run}']
        if a['size_in_bytes']>25_000_000 or a['workflow_run']['head_sha']!=run['head_sha']: raise ValueError('table provider differs')
        allowed={p.name for p in tables.iterdir() if p.is_file() and p.name!='.gitattributes'}
        members=t.check_archive(t.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
        if set(members)!=allowed or len(members)!=9: raise ValueError('complete table census differs')
        for name,data in members.items():
            if (tables/name).read_bytes()!=data: raise ValueError('remote/local table bytes differ: '+name)
        record.update(all_remote_table_bytes_match_local=True,table_files=len(members),
                      table_artifact={k:a[k]for k in ('id','name','size_in_bytes','digest')},
                      tables={name:sha256(data).hexdigest() for name,data in members.items()})
        t.persist(tables/'.gitattributes',attr)
    t.persist(out/'retention.json',t.encoded(record))
    print(json.dumps({k:v for k,v in record.items() if k not in ('tables','compact_artifacts')}))


if __name__=='__main__': main()
