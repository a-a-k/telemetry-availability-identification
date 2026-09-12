"""Verify durable confirmation archive receipts without downloading full evidence."""
import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as t


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path)
    args=p.parse_args();config=json.loads(args.config.read_bytes());run=t.read_api(f'actions/runs/{args.run}')
    if (run['path']!='.github/workflows/v4-confirmation-archive-v1.yml' or run['status']!='completed'
        or run['conclusion']!='success' or run['run_attempt']!=1):raise ValueError('archive producer differs')
    config_meta=t.read_api('contents/'+args.config.as_posix()+'?ref='+run['head_sha'])
    committed_config=base64.b64decode(config_meta['content'])
    if json.loads(committed_config)!=config:raise ValueError('declared archive configuration differs from producer')
    artifacts=t.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    if len(artifacts)!=1 or artifacts[0]['name']!=f'v4-confirmation-archive-compact-{args.run}':raise ValueError('archive receipt census differs')
    a=artifacts[0]
    if a['workflow_run']['head_sha']!=run['head_sha'] or a['workflow_run']['id']!=args.run:raise ValueError('archive provider differs')
    allowed={'compact.json','manifest.json','source-artifacts.json','resource-records.json'}
    files=t.check_archive(t.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
    if set(files)!=allowed:raise ValueError('archive member census differs')
    compact=json.loads(files['compact.json']);manifest=json.loads(files['manifest.json']);sources=json.loads(files['source-artifacts.json'])
    expected=[{k:s[k]for k in ('run','head','workflow','conclusion')}for s in config['sources']]
    fields=('id','name','size_in_bytes','digest')
    if ({s['id']:tuple(s[k]for k in fields)for s in sources}!=
        {s['id']:tuple(s[k]for k in fields)for source in config['sources']for s in source['artifacts']}):raise ValueError('original ZIP census differs')
    if (compact['archive_run']!=args.run or compact['archive_head']!=run['head_sha'] or compact['sources']!=expected
        or compact['config_sha256']!=sha256(committed_config).hexdigest() or compact['tag_name']!=config['tag']
        or compact['source_artifacts']!=len(sources) or compact['source_bytes']!=sum(s['size_in_bytes']for s in sources)
        or compact['published'] is not False or compact['all_source_zip_bytes_preserved'] is not True
        or any(compact[k]!=v for k,v in manifest.items())):raise ValueError('archive provenance differs')
    release=t.read_api(f"releases/{compact['release_id']}")
    if not release['draft'] or release['published_at'] is not None or release['tag_name']!=config['tag']:raise ValueError('unpublished archive identity differs')
    assets=[{k:a[k]for k in ('id','name','size','digest','state')}for a in release['assets']]
    if assets!=compact['assets']:raise ValueError('durable provider asset metadata differs')
    out=args.out or Path(f'docs/evidence/v4-confirmation-complete-archive-{args.run}')
    for name,raw in files.items():t.persist(out/name,raw)
    receipt=dict(run=args.run,head=run['head_sha'],artifact={k:a[k]for k in fields},release_id=release['id'],
        full_primary_payloads_downloaded=False,provider_assets_verified=True)
    t.persist(out/'retention.json',t.encoded(receipt));t.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({k:compact[k]for k in ('release_id','source_artifacts','source_bytes','published')}))


if __name__=='__main__':main()
