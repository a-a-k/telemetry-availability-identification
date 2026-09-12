"""Retain only verified archive receipts; full evidence stays remote."""
import argparse
import json
from pathlib import Path
import retain_v3_comparison_compact_v4 as transport


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--head',required=True)
    args=p.parse_args();run=transport.read_api(f'actions/runs/{args.run}')
    if (run['head_sha']!=args.head or run['path']!='.github/workflows/v4-primary-refinement-archive-v1.yml'
        or run['run_attempt']!=1 or run['conclusion']!='success'):raise ValueError('archive source identity differs')
    artifacts=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    if len(artifacts)!=1 or artifacts[0]['name']!=f'v4-primary-refinement-archive-compact-{args.run}':raise ValueError('archive compact census differs')
    names={'compact.json','manifest.json','source-artifacts.json'};artifact=artifacts[0]
    files=transport.check_archive(transport.api(f"actions/artifacts/{artifact['id']}/zip"),artifact,names)
    if set(files)!=names:raise ValueError('archive receipt files differ')
    receipt=json.loads(files['compact.json']);manifest=json.loads(files['manifest.json'])
    if (receipt['archive_head']!=args.head or receipt['archive_run']!=args.run or receipt['source_artifacts']!=21
        or receipt['draft'] is not True or receipt['published'] is not False
        or any(receipt[k]!=v for k,v in manifest.items())):raise ValueError('archive receipt does not reproduce manifest')
    release=transport.read_api(f"releases/{receipt['release_id']}")
    if not release['draft'] or release['published_at'] is not None:raise ValueError('evidence draft was published')
    assets=[{k:a[k] for k in ('id','name','size','digest','state')} for a in release['assets']]
    if assets!=receipt['assets']:raise ValueError('remote durable asset metadata changed')
    root=Path(f'docs/evidence/v4-primary-refinement-archive-{args.run}')
    for name,blob in files.items():transport.persist(root/name,blob)
    transport.persist(root/'retention.json',transport.encoded(dict(run=args.run,head=args.head,artifact=artifact,
        full_payloads_downloaded_locally=False,unpublished_draft_verified=True)))
    transport.persist(root/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({k:receipt[k] for k in ('release_id','source_artifacts','source_bytes','full_asset_bytes','draft','published')}))


if __name__=='__main__':main()
