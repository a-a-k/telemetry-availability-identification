"""Retain compact primary-verdict/transition audit results with exact provenance."""
import argparse
from collections import Counter
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from audit_v3_attempts_v1 import ROOT, PROTOCOL, read
from retain_v3_attempt_audit_v1 import table_bytes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=int,required=True);parser.add_argument('--head',required=True)
    args=parser.parse_args();run=transport.read_api(f'actions/runs/{args.run}')
    if (run['head_sha']!=args.head or run['path']!='.github/workflows/v3-primary-mechanisms-v1.yml'
        or run['run_attempt']!=1 or run['status']!='completed'): raise ValueError('mechanism audit provenance differs')
    artifacts=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    by_name={a['name']:a for a in artifacts};protocol=read(PROTOCOL)
    root=ROOT/f'docs/evidence/v3-primary-mechanisms-v1-{args.run}';selected=[];profiles={};rows=[]
    for app in sorted({c['identity']['application'] for c in protocol['cases']}):
        cases=[c for c in protocol['cases'] if c['identity']['application']==app][:4]
        allowed={c['artifact_key']+'.json' for c in cases}|{'receipt.json'}
        name=f'v3-primary-mechanisms-v1-compact-{app}-{args.run}';artifact=by_name[name]
        blob=transport.api(f"actions/artifacts/{artifact['id']}/zip")
        members=transport.check_archive(blob,artifact,allowed)
        if set(members)!=allowed: raise ValueError('incomplete mechanism census')
        counts=Counter()
        for member,content in members.items():
            data=json.loads(content)
            if data['run']!=str(args.run) or data['head']!=args.head: raise ValueError('inner mechanism provenance differs')
            transport.persist(root/app/member,content)
            if member=='receipt.json': continue
            counts['campaigns']+=1
            for op in data['operations']:
                counts['operations']+=1;counts.update(op['counts'])
                for key,value in op['counts'].items():
                    rows.append(dict(application=app,placement=data['identity']['placement'],law=data['identity']['law'],
                        repetition=data['identity']['repetition'],operation=op['operation'],measure=key,count=value))
        profiles[app]=dict(counts)
        selected.append({k:artifact[k] for k in ('id','name','digest','size_in_bytes')})
    receipt=dict(run=args.run,head=args.head,artifacts=selected,full_primary_artifacts_downloaded=False)
    transport.persist(root/'retention.json',transport.encoded(receipt))
    tables=ROOT/f'docs/tables/v3-primary-mechanisms-v1-{args.run}'
    transport.persist(tables/'counts.csv',table_bytes(rows))
    summary=dict(run=args.run,head=args.head,applications=profiles)
    transport.persist(tables/'summary.json',transport.encoded(summary))
    print(json.dumps(summary))


if __name__=='__main__':main()
