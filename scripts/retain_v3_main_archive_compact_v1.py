"""Retain terminal main archival provenance and exact compact resource records.

Never downloads a release asset or full application/model source ZIP locally.
"""
import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import zipfile

import archive_v3_main_evidence_v1 as archival
from archive_h_exec_evidence_v1 import checked_draft, encoded, require
from render_v3_comparison_tables_v1 import csv_bytes
import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.v3_resource_summary_v1 import summarize

WORKFLOW = '.github/workflows/v3-main-durable-archive-v1.yml'
MEMBERS = {'compact.json', 'manifest.json', 'progress.json'}


def unpack(data, item):
    require(item['expired'] is False and 0 < item['size_in_bytes'] <= 20_000_000,
            'compact artifact expired or oversized')
    require(len(data) == item['size_in_bytes'] and 'sha256:' + sha256(data).hexdigest() == item['digest'],
            'compact ZIP bytes differ')
    with zipfile.ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        require(len(members) == len(MEMBERS) and set(archive.namelist()) == MEMBERS,
                'compact member allowlist differs')
        require(all(not m.is_dir() and (m.external_attr >> 16) & 0o170000 != 0o120000 for m in members),
                'compact directory or symlink')
        require(sum(m.file_size for m in members) <= 25_000_000 and archive.testzip() is None,
                'compact expansion or CRC differs')
        return {name: archive.read(name) for name in sorted(MEMBERS)}


def resource_bytes(record):
    common = {'artifact_id', 'artifact_name', 'member', 'present'}
    require(record['member'] == 'process-resource-usage.txt', 'resource member differs')
    if record['present'] is False:
        require(set(record) == common | {'reason'} and record['reason'] == 'resource_record_not_in_source_artifact',
                'resource absence differs')
        return None
    require(record['present'] is True and set(record) == common | {'bytes', 'sha256', 'text', 'scope'},
            'unlisted compact resource field')
    raw = record['text'].encode('utf-8')
    require(len(raw) == record['bytes'] <= 65536 and sha256(raw).hexdigest() == record['sha256'],
            'resource bytes differ')
    require(record['scope'] == 'complete timed PMX extraction command and accounted children',
            'resource measurement scope differs')
    return raw


def retain(run_id):
    require(type(run_id) is int and run_id > 0, 'exact positive archive run required')
    run = transport.read_api(f'actions/runs/{run_id}')
    require(run['id'] == run_id and run['path'] == WORKFLOW and run['run_attempt'] == 1
            and run['status'] == 'completed' and run['conclusion'] == 'success'
            and run['head_repository']['full_name'] == transport.REPO
            and run['event'] in ('workflow_run', 'workflow_dispatch'), 'archive run identity or terminal state differs')
    items = transport.collect_pages(f'actions/runs/{run_id}/artifacts', 'artifacts')
    found = [item for item in items if item['name'] == f'v3-main-durable-archive-compact-{run_id}']
    require(len(found) == 1, 'exact compact archive artifact missing or duplicated')
    item = found[0]
    require(item['workflow_run']['id'] == run_id and item['workflow_run']['head_sha'] == run['head_sha']
            and item['expired'] is False and 0 < item['size_in_bytes'] <= 20_000_000,
            'compact artifact source or size differs')
    # Only this exact, small, provenance artifact is downloaded.
    data = transport.api(f'actions/artifacts/{item["id"]}/zip')
    payloads = unpack(data, item)
    compact, manifest = (json.loads(payloads[name]) for name in ('compact.json', 'manifest.json'))
    require(payloads['progress.json'] == payloads['manifest.json'], 'final archive progress differs')
    require(compact['version'] == manifest['version'] == 'v3-main-durable-archive-v1'
            and compact['archive_run'] == manifest['archive_run'] == run_id
            and compact['main_run'] == manifest['main_run'] == archival.RUN
            and compact['main_head'] == manifest['main_head'] == archival.HEAD
            and compact['archive_source_head'] == manifest['archive_source_head'], 'archive receipt identity differs')
    require(compact['qualified'] is True and compact['source_zip_bytes_preserved'] is True
            and compact['model_execution'] is False and compact['outcome_reanalysis'] is False
            and compact['new_independent_campaigns'] == manifest['new_independent_campaigns'] == 0
            and manifest['scientific_reanalysis'] is False
            and compact['draft'] is manifest['draft'] is True and compact['published_at'] is None,
            'archive scientific or publication scope differs')
    head = compact['archive_source_head']
    require(re.fullmatch(r'[0-9a-f]{40}', head) is not None, 'invalid archive checkout hash')
    for name in (WORKFLOW, 'scripts/archive_v3_main_evidence_v1.py', 'scripts/archive_h_exec_evidence_v1.py',
                 'scripts/retain_v3_comparison_compact_v4.py', 'configs/v3_comparison_design_v3.json'):
        actual = subprocess.check_output(['git', 'show', head + ':' + name])
        require(actual == Path(name).read_bytes(), 'archiver checkout source differs: ' + name)
    source_raw = (archival.SOURCE / 'all-artifact-metadata.json').read_bytes()
    source_run = json.loads((archival.SOURCE / 'run-api.json').read_bytes())
    require(source_run['id'] == archival.RUN and source_run['head_sha'] == archival.HEAD
            and source_run['status'] == 'completed' and source_run['run_attempt'] == 1
            and manifest['main_conclusion'] == source_run['conclusion'], 'main execution outcome differs')
    require(sha256(source_raw).hexdigest() == manifest['source_metadata_sha256'], 'collector metadata hash differs')
    sources = json.loads(source_raw)
    missing = archival.checked_census(sources, sources, archival.expected_artifacts())
    entries = [row for part in manifest['parts'] for row in part['sources']]
    require(len(entries) == len({row['artifact_id'] for row in entries}) == len(sources)
            == compact['archived_artifacts'] == manifest['source_artifacts'], 'archived source census differs')
    by_id = {row['id']: row for row in sources}
    for row in entries:
        source = by_id[row['artifact_id']]
        require(row['name'] == source['name'] and row['bytes'] == source['size_in_bytes']
                and 'sha256:' + row['sha256'] == source['digest']
                and row['member'] == f'source/{source["id"]}-{source["name"]}.zip'
                and row['provider_digest_verified'] is True and row['zip_crc_verified'] is True,
                'preserved original ZIP identity differs')
    require(compact['expected_artifacts'] == manifest['expected_artifacts'] == 2652
            and missing == compact['missing_artifacts'] == manifest['missing_artifacts']
            and compact['complete_artifact_census'] == (not missing)
            and compact['source_bytes'] == manifest['source_bytes'] == sum(row['bytes'] for row in entries),
            'archive size or missing-source accounting differs')
    require(compact['manifest_asset']['digest'] == 'sha256:' + sha256(payloads['manifest.json']).hexdigest()
            and compact['manifest_asset']['size'] == len(payloads['manifest.json'])
            and compact['parts'] == [part['asset'] for part in manifest['parts']]
            and compact['release_tag'] == archival.TAG and compact['release_id'] == manifest['release_id'],
            'manifest asset binding differs')
    release = checked_draft(transport.read_api(f'releases/{compact["release_id"]}'), archival.TAG, head)
    assets = compact['parts'] + [compact['manifest_asset']]
    require(len(release['assets']) == len(assets), 'release asset census differs')
    for expected in assets:
        matches = [asset for asset in release['assets'] if asset['id'] == expected['id']]
        require(len(matches) == 1 and all(matches[0][key] == expected[key]
                for key in ('id', 'name', 'size', 'digest', 'state')) and expected['state'] == 'uploaded',
                'release asset provider metadata differs')
    resources = manifest['compact_resource_records']
    expected_ids = {row['id'] for row in sources if row['name'].startswith('v3-comparison-pmx-extraction-')}
    require(len(resources) == len(expected_ids) and {row['artifact_id'] for row in resources} == expected_ids
            and compact['compact_resource_records'] == len(resources)
            and compact['available_resource_records'] == sum(row['present'] for row in resources),
            'resource census differs')
    resource_files = {}
    for row in resources:
        require(row['artifact_name'] == by_id[row['artifact_id']]['name'], 'resource source artifact differs')
        content = resource_bytes(row)
        if content is not None:
            resource_files[f'{row["artifact_id"]}-resource-usage.txt'] = content
    out = Path(f'docs/evidence/v3-main-durable-archive-{run_id}')
    transport.persist(out / '.gitattributes', b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n*.zip binary\n')
    transport.persist(out / 'compact.zip', data)
    for name, content in payloads.items():
        transport.persist(out / name, content)
    for name, content in resource_files.items():
        transport.persist(out / 'resources' / name, content)
    parsed = {row['path']: row for row in summarize(out / 'resources')['records']}
    table = []
    for row in resources:
        values = parsed.get(f'{row["artifact_id"]}-resource-usage.txt', {})
        table.append(dict(artifact_id=row['artifact_id'], artifact_name=row['artifact_name'],
                          scope='timed extraction command/children; not total deployment resources',
                          measurement_present=row['present'],
                          **{key: values.get(key) for key in ('wall_seconds', 'user_seconds', 'system_seconds', 'maximum_rss_bytes')}))
    transport.persist(out / 'pmx-process-resources.csv', csv_bytes(table))
    receipt = dict(version='v3-main-archive-compact-retention-v1', archive_run=run_id,
                   main_workflow_conclusion=source_run['conclusion'],
                   archive_workflow_head=run['head_sha'], archive_checkout_head=head,
                   artifact_id=item['id'], compact_zip_bytes=len(data), compact_zip_sha256=sha256(data).hexdigest(),
                   exact_member_allowlist=sorted(MEMBERS), original_zip_sources=len(entries),
                   release_id=release['id'], draft=True, release_asset_metadata_verified=True,
                   full_archive_or_application_payload_downloaded_locally=False,
                   compact_resource_records=len(resources), available_resource_records=len(resource_files),
                   files={path.relative_to(out).as_posix(): dict(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest())
                          for path in sorted(out.rglob('*')) if path.is_file() and path.name != 'retention.json'})
    transport.persist(out / 'retention.json', encoded(receipt))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    result = retain(parser.parse_args().run)
    print(json.dumps({key:value for key,value in result.items() if key != 'files'}))
