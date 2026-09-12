"""Preserve all three primary-refinement runs as exact original ZIPs in an unpublished draft."""
import json
import os
from pathlib import Path
import subprocess
import zipfile

import retain_v3_comparison_compact_v4 as transport
from archive_h_exec_evidence_v1 import require, encoded, digest, verify_zip, checked_draft
from archive_v3_main_evidence_v1 import add_source, verify_part



PROFILES = ('deathstarbench_social_network', 'opentelemetry_demo', 'spring_petclinic_microservices')
SOURCES = {
    34694957306: ('02f31dc45efb05006117793fcd0fe770f49e9d1e', 'v3-attempt-audit-v1.yml', 'success'),
    34695678140: ('29f7fbd14cca526d4cc93da60180a644014769b5', 'v3-primary-mechanisms-v1.yml', 'success'),
    34696809884: ('1e1a443d73dcfa2a529aa952359153f93101f34d', 'v4-binding-diagnostic-v1.yml', 'success'),
}

OUT = Path('workflow-results/exact-backends-archive')


def expected_names(run_id):
    prefix = SOURCES[run_id][1].removesuffix('.yml')
    roles = ('first', 'compact', 'full') if run_id == 34694957306 else ('compact', 'full')
    return {f'{prefix}-{role}-{profile}-{run_id}' for role in roles for profile in PROFILES}


def checked_source(run, artifacts):
    head, workflow, conclusion = SOURCES[run['id']]
    require(run['id'] > 0 and len(head) == 40, 'invalid source identity')
    require(run['head_sha'] == head and run['run_attempt'] == 1
            and run['path'] == '.github/workflows/' + workflow
            and run['status'] == 'completed' and run['conclusion'] == conclusion
            and run['head_repository']['full_name'] == transport.REPO,
            'wrong, incomplete or reclassified exact-backend cohort')
    names = expected_names(run['id'])
    require(len(artifacts) == len(names) and len({a['id'] for a in artifacts}) == len(names)
            and {a['name'] for a in artifacts} == names, 'exact-backend artifact census differs')
    require(sum(a['size_in_bytes'] for a in artifacts) < 900_000_000, 'archive exceeds bounded size')
    for item in artifacts:
        require(item['expired'] is False and 0 < item['size_in_bytes'] <= 200_000_000
                and item['workflow_run']['id'] == run['id']
                and item['workflow_run']['head_sha'] == head, 'artifact source/size differs')


def main():
    require(os.environ.get('GITHUB_ACTIONS') == 'true'
            and os.environ.get('GITHUB_REPOSITORY') == transport.REPO
            and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'original remote archival attempt required')
    TAG = 'evidence-v4-primary-refinement-20260912-v1'
    artifacts = []
    for run_id in SOURCES:
        run = transport.read_api(f'actions/runs/{run_id}')
        items = transport.collect_pages(f'actions/runs/{run_id}/artifacts', 'artifacts')
        checked_source(run, items)
        artifacts.extend(items)
    require(len(artifacts) == 21, 'combined original artifact census differs')
    require(sum(a['size_in_bytes'] for a in artifacts) < 900_000_000, 'combined archive exceeds bounded size')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    releases = transport.read_api('releases?per_page=100')
    require(len(releases) < 100 and not any(r['tag_name'] == TAG for r in releases),
            'archive already exists or release list needs pagination; never overwrite')
    body = dict(tag_name=TAG, target_commitish=head, draft=True, prerelease=False, make_latest='false',
                name='Unpublished primary audit and diagnosed binding evidence',
                body='All original ZIPs of the complete 240-campaign attempt audit, independent primary-verdict audit, and fixed 29-campaign semantic-binding diagnostic. '
                     'No new observations, reanalysis or automatic publication.')
    release = json.loads(subprocess.check_output(
        ['gh', 'api', f'repos/{transport.REPO}/releases', '--method', 'POST', '--input', '-'], input=encoded(body)))
    checked_draft(release, TAG, head)
    OUT.mkdir(parents=True)
    full = OUT / 'v4-primary-refinement-original-artifacts.zip'
    entries = []
    with zipfile.ZipFile(full, 'w', allowZip64=True) as archive:
        for item in sorted(artifacts, key=lambda a: a['id']):
            temporary = OUT / f'source-{item["id"]}.zip'
            temporary.write_bytes(transport.api(f'actions/artifacts/{item["id"]}/zip'))
            verify_zip(temporary, item)
            member = f'{item["id"]}.zip'
            add_source(archive, temporary, member)
            entries.append(dict(member=member, artifact_id=item['id'], artifact_name=item['name'],
                                source_run=item['workflow_run']['id'], bytes=item['size_in_bytes'],
                                sha256=digest(temporary)))
            require(temporary.resolve().parent == OUT.resolve(), 'temporary source outside archive directory')
            temporary.unlink()
    verify_part(full, entries)
    manifest = dict(version='v4-primary-refinement-durable-archive-v1',
                    sources=[dict(run_id=r, head=v[0], conclusion=v[2]) for r, v in SOURCES.items()],
                    archive_run=int(os.environ['GITHUB_RUN_ID']), archive_head=head, tag_name=TAG,
                    release_id=release['id'], draft=True, source_artifacts=len(artifacts),
                    source_bytes=sum(a['size_in_bytes'] for a in artifacts), entries=entries,
                    full_asset_name=full.name, full_asset_bytes=full.stat().st_size,
                    full_asset_sha256=digest(full), new_campaigns=0, scientific_reanalysis=False)
    (OUT / 'manifest.json').write_bytes(encoded(manifest))
    (OUT / 'source-artifacts.json').write_bytes(encoded(artifacts))
    subprocess.run(['gh', 'release', 'upload', TAG, str(full), str(OUT / 'manifest.json'),
                    '--repo', transport.REPO], check=True)
    current = checked_draft(transport.read_api(f'releases/{release["id"]}'), TAG, head)
    assets = {a['name']: a for a in current['assets']}
    require(set(assets) == {full.name, 'manifest.json'}, 'archive asset census differs')
    for path in (full, OUT / 'manifest.json'):
        item = assets[path.name]
        require(item['state'] == 'uploaded' and item['size'] == path.stat().st_size
                and item['digest'] == 'sha256:' + digest(path), 'uploaded archive digest differs')
    receipt = dict(manifest, assets=[{k: a[k] for k in ('id', 'name', 'size', 'digest', 'state')}
                                    for a in current['assets']], published=False,
                   full_payloads_downloaded_locally=False, all_source_zip_bytes_preserved=True)
    (OUT / 'compact.json').write_bytes(encoded(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('entries', 'assets')}))


if __name__ == '__main__':
    main()
