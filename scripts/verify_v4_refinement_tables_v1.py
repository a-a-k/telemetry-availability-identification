"""Check all remotely exported table bytes against compact-only local exports."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as t


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);args=p.parse_args()
    run=t.read_api(f'actions/runs/{args.run}')
    if (run['path']!='.github/workflows/v4-refinement-tables-v1.yml' or run['status']!='completed'
        or run['conclusion']!='success' or run['run_attempt']!=1):raise ValueError('table producer differs')
    artifacts=t.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    if len(artifacts)!=1 or artifacts[0]['name']!=f'v4-complete-refinement-tables-{args.run}':raise ValueError('table artifact census differs')
    a=artifacts[0]
    if a['workflow_run']['id']!=args.run or a['workflow_run']['head_sha']!=run['head_sha'] or a['size_in_bytes']>20_000_000:raise ValueError('table provider differs')
    roots=['evidence/v4-confirmation-v2-34703686592','evidence/v4-confirmation-summary-v3-34707482231',
        'evidence/v4-missingness-v2-34707544832','evidence/v4-confirmed-performance-v2-34707544825',
        'tables/v4-confirmation-v2-34703686592','tables/v4-missingness-v2-34707544832','tables/v4-confirmed-performance-v2-34707544825']
    # This later audit of already frozen scalars was added after the first table
    # producer. It cannot be attributed to that earlier producer.
    later='tables/v4-confirmation-v2-34703686592/gstar-b0-common-points.csv'
    allowed={p.relative_to('docs').as_posix()for root in roots for p in (Path('docs')/root).rglob('*')
        if p.is_file() and p.name!='.gitattributes' and p.relative_to('docs').as_posix()!=later}
    files=t.check_archive(t.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
    if set(files)!=allowed:raise ValueError('complete remote compact/table census differs')
    table_names=sorted(n for n in files if n.startswith('tables/'))
    for name in table_names:
        if files[name]!=(Path('docs')/name).read_bytes():raise ValueError('remote/local table bytes differ: '+name)
    out=Path(f'docs/evidence/v4-refinement-tables-{args.run}')
    receipt=dict(run=args.run,head=run['head_sha'],artifact={k:a[k]for k in ('id','name','size_in_bytes','digest')},
        all_remote_table_bytes_match_local=True,table_files=len(table_names),compact_files=len(files)-len(table_names),
        independently_added_after_producer=[later],local_model_execution=False,
        tables={n:sha256(files[n]).hexdigest()for n in table_names})
    t.persist(out/'retention.json',t.encoded(receipt));t.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({k:v for k,v in receipt.items()if k!='tables'}))


if __name__=='__main__':main()
