"""Verify the exact-backend archive from compact documents and remote metadata."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import archive_v3_exact_backends_v1 as source
import retain_v3_comparison_compact_v4 as transport
from archive_h_exec_evidence_v1 import require, checked_draft


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    args = parser.parse_args()
    run = transport.read_api(f'actions/runs/{args.run}')
    require(run['path'] == '.github/workflows/v3-exact-backends-durable-archive-v1.yml'
            and run['run_attempt'] == 1 and run['status'] == 'completed'
            and run['conclusion'] == 'success'
            and run['head_repository']['full_name'] == transport.REPO, 'wrong or incomplete archive run')
    items = transport.collect_pages(f'actions/runs/{args.run}/artifacts', 'artifacts')
    require(len(items) == 1 and items[0]['name'] == f'v3-exact-backends-archive-compact-{args.run}'
            and items[0]['workflow_run']['head_sha'] == run['head_sha']
            and items[0]['size_in_bytes'] <= 2_000_000, 'compact identity/size differs')
    item = items[0]
    raw = transport.api(f'actions/artifacts/{item["id"]}/zip')
    names = {'compact.json', 'manifest.json', 'source-artifacts.json'}
    members = transport.check_archive(raw, item, names)
    require(set(members) == names, 'compact member census differs')
    receipt = json.loads(members['compact.json'])
    manifest = json.loads(members['manifest.json'])
    artifacts = json.loads(members['source-artifacts.json'])
    require(all(receipt[k] == v for k, v in manifest.items()), 'receipt and manifest differ')
    expected = [dict(run_id=r, head=v[0], conclusion=v[2]) for r, v in source.SOURCES.items()]
    require(manifest['version'] == 'v3-exact-backends-durable-archive-v1'
            and manifest['sources'] == expected and manifest['source_artifacts'] == 16
            and manifest['archive_run'] == args.run and manifest['archive_head'] == run['head_sha']
            and receipt['published'] is False and receipt['draft'] is True
            and receipt['all_source_zip_bytes_preserved'] is True
            and receipt['new_campaigns'] == 0 and receipt['scientific_reanalysis'] is False,
            'archive identity/scope differs')
    for name in ('scripts/archive_v3_exact_backends_v1.py', 'scripts/archive_v3_main_evidence_v1.py',
                 'scripts/archive_h_exec_evidence_v1.py', 'scripts/retain_v3_comparison_compact_v4.py',
                 '.github/workflows/v3-exact-backends-durable-archive-v1.yml'):
        require(subprocess.check_output(['git', 'show', run['head_sha'] + ':' + name]) == Path(name).read_bytes(),
                'archive execution source differs: ' + name)
    for run_id in source.SOURCES:
        original = transport.read_api(f'actions/runs/{run_id}')
        group = [a for a in artifacts if a['workflow_run']['id'] == run_id]
        source.checked_source(original, group)
        current = transport.collect_pages(f'actions/runs/{run_id}/artifacts', 'artifacts')
        fields = ('id', 'name', 'size_in_bytes', 'digest', 'expired')
        require({a['id']: tuple(a[k] for k in fields) for a in current} ==
                {a['id']: tuple(a[k] for k in fields) for a in group}, 'source artifact census changed')
    by_id = {a['id']: a for a in artifacts}
    entries = manifest['entries']
    require(len(entries) == 16 and {e['artifact_id'] for e in entries} == set(by_id), 'entry census differs')
    require(manifest['source_bytes'] == sum(a['size_in_bytes'] for a in artifacts), 'source byte count differs')
    for entry in entries:
        actual = by_id[entry['artifact_id']]
        require(entry['member'] == str(actual['id']) + '.zip' and entry['artifact_name'] == actual['name']
                and entry['source_run'] == actual['workflow_run']['id']
                and entry['bytes'] == actual['size_in_bytes']
                and 'sha256:' + entry['sha256'] == actual['digest'], 'source ZIP identity differs')
    release = checked_draft(transport.read_api(f'releases/{receipt["release_id"]}'), source.TAG, manifest['archive_head'])
    fields = ('id', 'name', 'size', 'digest', 'state')
    require({a['id']: tuple(a[k] for k in fields) for a in release['assets']} ==
            {a['id']: tuple(a[k] for k in fields) for a in receipt['assets']}, 'archive assets differ')
    assets = {a['name']: a for a in receipt['assets']}
    require(set(assets) == {manifest['full_asset_name'], 'manifest.json'}, 'asset census differs')
    require(assets['manifest.json']['digest'] == 'sha256:' + sha256(members['manifest.json']).hexdigest()
            and assets[manifest['full_asset_name']]['digest'] == 'sha256:' + manifest['full_asset_sha256']
            and assets[manifest['full_asset_name']]['size'] == manifest['full_asset_bytes'], 'asset digest/size differs')
    out = Path(f'docs/evidence/v3-exact-backends-durable-archive-{args.run}')
    transport.persist(out / '.gitattributes', b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    transport.persist(out / 'compact.zip', raw)
    for name, data in members.items():
        transport.persist(out / name, data)
    record = dict(version='v3-exact-backends-archive-compact-retention-v1', archive_run=args.run,
                  sources=expected, archive_head=run['head_sha'], artifact_id=item['id'],
                  compact_bytes=len(raw), compact_sha256=sha256(raw).hexdigest(),
                  release_id=receipt['release_id'], draft=True, source_artifacts=16,
                  source_bytes=manifest['source_bytes'], full_payloads_downloaded_locally=False,
                  provider_zip_and_release_asset_digests_verified=True)
    transport.persist(out / 'retention.json', transport.encoded(record))
    print(json.dumps(record))


if __name__ == '__main__':
    main()
