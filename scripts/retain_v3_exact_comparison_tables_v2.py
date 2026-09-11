"""Verify remotely generated tables against local compact-only aggregation."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import retain_v3_comparison_compact_v4 as t


def require(ok,message):
    if not ok:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=int,required=True)
    args=parser.parse_args();run=t.read_api(f'actions/runs/{args.run}')
    require(run['status']=='completed' and run['conclusion']=='success' and run['run_attempt']==1
            and run['path']=='.github/workflows/v3-exact-comparison-report-v2.yml','wrong report workflow')
    items=t.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    expected={f'v3-exact-comparison-v2-tables-{args.run}',f'v3-exact-comparison-v2-retention-{args.run}'}
    require(len(items)==2 and {a['name'] for a in items}==expected,'report artifact census differs')
    item=next(a for a in items if a['name'].startswith('v3-exact-comparison-v2-tables-'))
    require(item['size_in_bytes']<20_000_000 and item['workflow_run']['head_sha']==run['head_sha'],'report source/size differs')
    raw=t.api(f'actions/artifacts/{item["id"]}/zip')
    allowed={n+'.csv' for n in ('measurements','process_resources','stage_summary','paired_ratios','exact_bounds','failures','census','synthetic_grid','representations','projection_ratios')}|{'REPORT.md','provenance.json'}
    members=t.check_archive(raw,item,allowed);provenance=json.loads(members['provenance.json'])
    tables=Path(f'docs/tables/v3-exact-comparison-v2-{provenance["run_id"]}')
    require(set(members)=={p.name for p in tables.iterdir() if p.name!='.gitattributes'},'table member census differs')
    for name,value in members.items():require(value==(tables/name).read_bytes(),'remote/local table bytes differ: '+name)
    out=Path(f'docs/evidence/v3-exact-comparison-v2-tables-{args.run}')
    t.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    t.persist(out/'tables.zip',raw);t.persist(out/'run-api.json',t.encoded(run));t.persist(out/'artifact-api.json',t.encoded(item))
    record=dict(version='v3-exact-comparison-v2-remote-tables-retention-v1',report_run=args.run,report_head=run['head_sha'],
                comparison_run=provenance['run_id'],comparison_head=provenance['head'],artifact_id=item['id'],
                bytes=len(raw),sha256=sha256(raw).hexdigest(),all_remote_table_bytes_match_local=True,
                rows={n:v['rows'] for n,v in provenance['tables'].items()},local_model_execution=False)
    t.persist(out/'retention.json',t.encoded(record));print(json.dumps(record))


if __name__=='__main__':main()
