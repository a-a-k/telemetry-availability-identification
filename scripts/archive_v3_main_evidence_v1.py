"""Preserve terminal main-run evidence remotely, without analysis or publication.

Uses the collector's exact source-artifact census. Original ZIP bytes are packed
in bounded release assets so disk use does not grow with the full study size.
Only the compact manifest and archive receipt are repository results.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

import retain_v3_comparison_compact_v4 as transport
from archive_h_exec_evidence_v1 import checked_draft, digest, encoded, require, verify_zip

RUN = 34465226083
HEAD = 'd857ea65ca9da7fa9ae4ee1198317487475246a7'
REPO = transport.REPO
TAG = f'evidence-v3-main-{RUN}-v1'
SOURCE = Path(f'docs/evidence/v3-comparison-main-{RUN}')
DISPATCH = Path('docs/evidence/v3-main-dispatch-v3.json')
OUT = Path('.smoke/v3-main-durable-archive-v1')
MAX_PART_BYTES = 1_000_000_000
IDENTITY_FIELDS = ('id', 'name', 'size_in_bytes', 'digest', 'expired')


def expected_artifacts():
    _, cases = transport.selections(RUN, 'main')
    roles = ('raw', 'ordinary', 'pmx-input', 'closed-evaluator', 'receipt',
             'graph', 'graph-compact', 'pmx-extraction', 'pmx-build', 'frozen', 'evaluation')
    names = {f'v3-comparison-{role}-{case["artifact_key"]}-{RUN}'
             for case in cases for role in roles}
    profiles = {case['identity']['application'] for case in cases}
    names.update(f'v3-comparison-{role}-{profile}-{RUN}' for profile in profiles
                 for role in ('pmx-solver', 'pmx-candidates', 'pmx-solver-contract'))
    names.update(f'v3-comparison-{role}-{RUN}' for role in
                 ('pmx-extraction-controls', 'pmx-build-controls', 'compact'))
    require(len(cases) == 240 and len(names) == 2652, 'unexpected frozen main census')
    return names


def checked_census(retained, current, expected):
    def index(rows):
        ids = [row['id'] for row in rows]
        names = [row['name'] for row in rows]
        require(len(ids) == len(set(ids)) and len(names) == len(set(names)),
                'duplicate artifact identity')
        require(set(names) <= expected, 'unlisted main artifact')
        for row in rows:
            require(row['expired'] is False and 0 < row['size_in_bytes'] < MAX_PART_BYTES,
                    'expired, empty or oversized source artifact')
            require(re.fullmatch(r'sha256:[0-9a-f]{64}', row['digest']) is not None,
                    'source digest unavailable')
            require(row['workflow_run']['id'] == RUN and row['workflow_run']['head_sha'] == HEAD,
                    'artifact source run differs')
        return {row['id']: tuple(row[key] for key in IDENTITY_FIELDS) for row in rows}
    require(index(retained) == index(current), 'collector and current source census differ')
    return sorted(expected - {row['name'] for row in current})


def add_source(archive, path, member):
    info = zipfile.ZipInfo(member, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as target:
        shutil.copyfileobj(source, target, 1024 * 1024)


def compact_extraction_resource(path, item):
    """Retain only the existing GNU-time text, never interpret native/model data."""
    if not item['name'].startswith('v3-comparison-pmx-extraction-'):
        return None
    member = 'process-resource-usage.txt'
    record = dict(artifact_id=item['id'], artifact_name=item['name'], member=member)
    with zipfile.ZipFile(path) as archive:
        if member not in archive.namelist():
            return dict(record, present=False, reason='resource_record_not_in_source_artifact')
        info = archive.getinfo(member)
        require(info.file_size <= 65536 and not info.is_dir()
                and (info.external_attr >> 16) & 0o170000 != 0o120000,
                'invalid compact resource member')
        raw = archive.read(member)
    return dict(record, present=True, bytes=len(raw), sha256=sha256(raw).hexdigest(),
                text=raw.decode('utf-8'),
                scope='complete timed PMX extraction command and accounted children')


def verify_part(path, entries):
    with zipfile.ZipFile(path) as archive:
        require(archive.namelist() == [row['member'] for row in entries], 'part member census differs')
        for row in entries:
            value = sha256()
            with archive.open(row['member']) as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    value.update(block)
            require(value.hexdigest() == row['sha256'], 'source bytes changed during packaging')


def create_draft(head):
    releases = []
    page = 1
    while True:
        batch = transport.read_api(f'releases?per_page=100&page={page}')
        releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    matches = [item for item in releases if item['tag_name'] == TAG]
    require(len(matches) <= 1, 'duplicate archive release')
    if matches:
        return checked_draft(matches[0], TAG, head)
    body = dict(tag_name=TAG, target_commitish=head, draft=True, prerelease=False,
                make_latest='false', generate_release_notes=False,
                name=f'Unpublished original evidence: independent main {RUN}',
                body='Byte-preserving archive of the terminal independent main run. '
                     'Original source ZIPs, failed cases and absent artifacts retain their identities. '
                     'This archive neither reruns models nor adds observations. It is not published automatically.')
    raw = subprocess.check_output(['gh', 'api', f'repos/{REPO}/releases', '--method', 'POST', '--input', '-'],
                                  input=encoded(body), timeout=120)
    return checked_draft(json.loads(raw), TAG, head)


def upload(path, release, head):
    current = checked_draft(transport.read_api(f'releases/{release["id"]}'), TAG, head)
    wanted = dict(name=path.name, size=path.stat().st_size, digest='sha256:' + digest(path), state='uploaded')
    existing = [item for item in current['assets'] if item['name'] == path.name]
    if not existing:
        subprocess.run(['gh', 'release', 'upload', TAG, str(path), '--repo', REPO], check=True, timeout=900)
    current = checked_draft(transport.read_api(f'releases/{release["id"]}'), TAG, head)
    found = [item for item in current['assets'] if item['name'] == path.name]
    require(len(found) == 1 and all(found[0].get(key) == value for key, value in wanted.items()),
            'uploaded asset differs; existing bytes are never overwritten')
    return {key: found[0][key] for key in ('id', 'name', 'size', 'digest', 'state')}


def main():
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPO,
            'full main archival is remote only')
    require(os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'archive retries need a separate explicit record')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    require(re.fullmatch(r'[0-9a-f]{40}', head) is not None, 'invalid archive source head')
    dispatch = json.loads(DISPATCH.read_bytes())
    require(dispatch['run_id'] == RUN and dispatch['head'] == HEAD
            and dispatch['protocol_sha256'] == transport.DESIGN_SHA, 'main dispatch differs')
    run = transport.read_api(f'actions/runs/{RUN}')
    require(run['id'] == RUN and run['head_sha'] == HEAD and run['path'] == transport.WORKFLOW
            and run['head_repository']['full_name'] == REPO and run['event'] == 'workflow_dispatch'
            and run['run_attempt'] == 1 and run['status'] == 'completed', 'main is not the exact terminal original run')
    # Collection is a prerequisite: no early opening of closed evaluation inputs.
    summary = json.loads((SOURCE / 'collection-summary.json').read_bytes())
    require(summary['run_id'] == RUN and summary['head'] == HEAD, 'terminal collection identity differs')
    retained = json.loads((SOURCE / 'all-artifact-metadata.json').read_bytes())
    current = transport.collect_pages(f'actions/runs/{RUN}/artifacts', 'artifacts')
    missing = checked_census(retained, current, expected_artifacts())
    OUT.mkdir(parents=True, exist_ok=True)
    require(not (OUT / 'compact.json').exists(), 'archive receipt already exists')
    release = create_draft(head)
    manifest = dict(version='v3-main-durable-archive-v1', repository=REPO, main_run=RUN,
                    main_head=HEAD, main_conclusion=run['conclusion'], archive_source_head=head,
                    archive_run=int(os.environ['GITHUB_RUN_ID']), expected_artifacts=2652,
                    source_artifacts=len(current), source_bytes=sum(item['size_in_bytes'] for item in current),
                    source_metadata_sha256=digest(SOURCE / 'all-artifact-metadata.json'),
                    missing_artifacts=missing, release_id=release['id'], draft=True,
                    new_independent_campaigns=0, scientific_reanalysis=False,
                    compact_resource_records=[], parts=[])
    part = None
    archive = None
    entries = []
    size = 0

    def finish_part():
        archive.close()
        verify_part(part, entries)
        asset = upload(part, release, head)
        manifest['parts'].append(dict(asset=asset, sources=list(entries)))
        (OUT / 'progress.json').write_bytes(encoded(manifest))
        # Only the already verified and uploaded temporary part is removed.
        require(part.resolve().parent == OUT.resolve(), 'temporary part escaped archive directory')
        part.unlink()
        print(json.dumps(dict(stage='main_archive_part_preserved', part=asset['name'],
                              preserved_artifacts=sum(len(p['sources']) for p in manifest['parts']))), flush=True)

    for item in sorted(current, key=lambda row: row['name']):
        if archive is not None and size + item['size_in_bytes'] > MAX_PART_BYTES:
            finish_part()
            archive = None
        if archive is None:
            part = OUT / f'v3-main-{RUN}-part-{len(manifest["parts"]) + 1:03d}.zip'
            archive = zipfile.ZipFile(part, 'x', compression=zipfile.ZIP_STORED, allowZip64=True)
            entries = []
            size = 0
        raw = OUT / 'source.zip'
        with raw.open('xb') as target:
            target.write(transport.api(f'actions/artifacts/{item["id"]}/zip'))
        check = verify_zip(raw, item)
        resource = compact_extraction_resource(raw, item)
        if resource is not None:
            manifest['compact_resource_records'].append(resource)
        member = f'source/{item["id"]}-{item["name"]}.zip'
        add_source(archive, raw, member)
        entries.append(dict(artifact_id=item['id'], name=item['name'], member=member,
                            bytes=item['size_in_bytes'], sha256=item['digest'][7:], **check))
        size += item['size_in_bytes']
        raw.unlink()
    if archive is not None:
        finish_part()
    require(sum(len(part['sources']) for part in manifest['parts']) == len(current), 'incomplete archive')
    path = OUT / 'manifest.json'
    path.write_bytes(encoded(manifest))
    manifest_asset = upload(path, release, head)
    receipt = dict(version=manifest['version'], qualified=True, main_run=RUN, main_head=HEAD,
                   archive_run=manifest['archive_run'], archive_source_head=head,
                   archived_artifacts=len(current), expected_artifacts=2652,
                   complete_artifact_census=not missing, missing_artifacts=missing,
                   source_bytes=manifest['source_bytes'], release_id=release['id'], release_tag=TAG,
                   draft=True, published_at=None, manifest_asset=manifest_asset,
                   parts=[part['asset'] for part in manifest['parts']],
                   compact_resource_records=len(manifest['compact_resource_records']),
                   available_resource_records=sum(row['present'] for row in manifest['compact_resource_records']),
                   source_zip_bytes_preserved=True, new_independent_campaigns=0,
                   model_execution=False, outcome_reanalysis=False)
    (OUT / 'compact.json').write_bytes(encoded(receipt))
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
