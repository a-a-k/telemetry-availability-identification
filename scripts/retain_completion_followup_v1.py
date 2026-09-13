"""Retain compact four-route/accuracy evidence and verify every remote table byte."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import retain_v3_comparison_compact_v4 as t


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);args=p.parse_args()
    run=t.read_api(f'actions/runs/{args.run}')
    if run['path']!='.github/workflows/v5-completion-followup-v1.yml' or run['status']!='completed' or run['run_attempt']!=1:
        raise ValueError('wrong or unfinished producer')
    raw_config=subprocess.check_output(['git','show',run['head_sha']+':configs/v5_completion_followup_v1.json'])
    config=json.loads(raw_config);artifacts=t.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    by={a['name']:a for a in artifacts};out=Path(f'docs/evidence/v5-completion-followup-{args.run}')
    tables=Path(f'docs/tables/v5-completion-followup-{args.run}')
    attr=b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n'
    t.persist(out/'.gitattributes',attr);t.persist(out/'run-api.json',t.encoded(run));t.persist(out/'artifacts-api.json',t.encoded(artifacts))
    receipts=[];required={'protocol.json','environment.json','timings.json','receipt.json'}
    def download(name,allowed):
        a=by[name]
        if a['workflow_run']['head_sha']!=run['head_sha'] or a['workflow_run']['id']!=args.run or a['size_in_bytes']>25_000_000:
            raise ValueError('compact provider identity/size differs')
        members=t.check_archive(t.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
        receipts.append({k:a[k]for k in ('id','name','size_in_bytes','digest')})
        return members
    for profile in config['applications']:
        name=f'v5-followup-compact-{profile}-{args.run}'
        if name not in by:
            if run['conclusion']=='success':raise ValueError('missing successful profile')
            continue
        members=download(name,required|{'failure.json'})
        if run['conclusion']=='success' and set(members)!=required:raise ValueError('incomplete successful compact')
        if 'protocol.json' in members and json.loads(members['protocol.json'])!=config:raise ValueError('configuration differs')
        if 'receipt.json' in members:
            r=json.loads(members['receipt.json'])
            if (r['run'],r['head'],r['profile'],r['config_sha256'])!=(str(args.run),run['head_sha'],profile,sha256(raw_config).hexdigest()):
                raise ValueError('receipt binding differs')
        for name,data in members.items():t.persist(out/profile/name,data)
    name=f'v5-followup-accuracy-{args.run}'
    if name in by:
        members=download(name,{'results.json'});r=json.loads(members['results.json'])
        if (r['run'],r['head'],r['config_sha256'])!=(str(args.run),run['head_sha'],sha256(raw_config).hexdigest()):
            raise ValueError('accuracy binding differs')
        t.persist(out/'accuracy/results.json',members['results.json'])
    elif run['conclusion']=='success':raise ValueError('missing accuracy')
    record=dict(run=args.run,head=run['head_sha'],conclusion=run['conclusion'],compact_artifacts=receipts,
                full_model_or_observation_artifacts_downloaded=False,local_model_execution=False)
    if run['conclusion']=='success':
        subprocess.run([sys.executable,'scripts/summarize_completion_followup_v1.py','--source',str(out),'--out',str(tables)],check=True)
        allowed={p.name for p in tables.iterdir()if p.is_file() and p.name!='.gitattributes'}
        members=download(f'v5-followup-tables-{args.run}',allowed)
        if len(members)!=11 or set(members)!=allowed:raise ValueError('complete table census differs')
        for name,data in members.items():
            if (tables/name).read_bytes()!=data:raise ValueError('remote/local table bytes differ: '+name)
        record.update(all_remote_table_bytes_match_local=True,table_files=len(members),
                      tables={name:sha256(data).hexdigest()for name,data in members.items()})
        t.persist(tables/'.gitattributes',attr)
    t.persist(out/'retention.json',t.encoded(record));print({k:v for k,v in record.items()if k not in ('tables','compact_artifacts')})


if __name__=='__main__':main()
