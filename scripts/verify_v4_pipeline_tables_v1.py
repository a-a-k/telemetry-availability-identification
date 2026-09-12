"""Verify every primary/verification/scaling table from its actual remote producer."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as t


SOURCE=34708991534


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);args=p.parse_args()
    run=t.read_api(f'actions/runs/{args.run}')
    if (run['path']!='.github/workflows/v4-pipeline-report-v1.yml' or run['status']!='completed'
        or run['conclusion']!='success' or run['run_attempt']!=1):raise ValueError('report producer differs')
    items=t.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    if len(items)!=1 or items[0]['name']!=f'v4-pipeline-complete-tables-{args.run}':raise ValueError('report artifact census differs')
    a=items[0]
    if a['workflow_run']['id']!=args.run or a['workflow_run']['head_sha']!=run['head_sha'] or a['size_in_bytes']>10_000_000:raise ValueError('provider/size differs')
    roots=[f'evidence/v4-pipeline-benchmark-{SOURCE}',f'tables/v4-pipeline-benchmark-{SOURCE}']
    allowed={p.relative_to('docs').as_posix()for root in roots for p in (Path('docs')/root).rglob('*')if p.is_file()and p.name!='.gitattributes'}
    files=t.check_archive(t.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
    if set(files)!=allowed:raise ValueError('complete report member census differs')
    tables={n:v for n,v in files.items()if n.startswith('tables/')}
    expected={'paired-pipelines.csv','pipeline-summary.csv','stage-processes.csv','telemetry-scaling.csv','verification-processes.csv','README.md','provenance.json'}
    if {Path(n).name for n in tables}!=expected:raise ValueError('complete seven-table export differs')
    for name,raw in tables.items():
        if raw!=(Path('docs')/name).read_bytes():raise ValueError('remote/local table bytes differ: '+name)
    out=Path(f'docs/evidence/v4-pipeline-tables-{args.run}')
    receipt=dict(run=args.run,head=run['head_sha'],measurement_run=SOURCE,artifact={k:a[k]for k in ('id','name','size_in_bytes','digest')},
        all_remote_table_bytes_match_local=True,table_files=len(tables),local_model_execution=False,
        tables={n:sha256(raw).hexdigest()for n,raw in tables.items()})
    t.persist(out/'retention.json',t.encoded(receipt));t.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({k:v for k,v in receipt.items()if k!='tables'}))


if __name__=='__main__':main()
