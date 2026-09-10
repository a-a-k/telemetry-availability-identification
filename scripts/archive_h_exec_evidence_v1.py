"""Preserve the exact completed H-EXEC artifacts remotely in an unpublished release.

This copies and verifies bytes. It neither interprets outcomes nor runs a model.
Full source payloads are allowed only on the GitHub Actions worker.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

REPO = 'a-a-k/telemetry-availability-identification'
CONFIG = Path('configs/h_exec_durable_archive_v1.json')
CONFIG_SHA = '01fe9f26cd4d1620823674cda20954f81a961bc21f53e4627f842ecf33273198'
OUT = Path('.smoke/h-exec-durable-archive-v1')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n').encode()


def digest(path):
    value = sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def api(path, body=None):
    command = ['gh', 'api', 'repos/'+REPO+'/'+path]
    if body is not None:
        command += ['--method', 'POST', '--input', '-']
    raw = subprocess.check_output(command, input=None if body is None else encoded(body), timeout=120)
    return json.loads(raw)


def verify_zip(path, expected):
    require(path.stat().st_size == expected['size_in_bytes'], 'source ZIP size differs')
    require('sha256:'+digest(path) == expected['digest'], 'source ZIP digest differs')
    with zipfile.ZipFile(path) as archive:
        names = set()
        for member in archive.infolist():
            name = member.filename
            parts = name.rstrip('/').split('/')
            require(name and not name.startswith('/') and '\\' not in name and ':' not in name
                    and all(part not in ('', '.', '..') for part in parts), 'unsafe ZIP member')
            require(name.casefold() not in names, 'duplicate ZIP member')
            names.add(name.casefold())
            require((member.external_attr >> 16) & 0o170000 != 0o120000, 'ZIP symlink')
        require(archive.testzip() is None, 'source ZIP CRC differs')
        return dict(members=len(names), uncompressed_bytes=sum(m.file_size for m in archive.infolist()),
                    provider_digest_verified=True, zip_crc_verified=True)


def checked_draft(release, tag, head):
    require(release.get('draft') is True and release.get('published_at') is None,
            'release must remain unpublished')
    require(release.get('tag_name') == tag and release.get('target_commitish') == head,
            'archive release identity differs')
    return release


def fixed_member(archive, name, data):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def main():
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPO,
            'full evidence archival is remote only')
    require(os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'archive attempts are not silently replaced')
    head = os.environ['GITHUB_SHA']
    require(re.fullmatch(r'[0-9a-f]{40}', head) is not None, 'invalid archive source head')
    require(digest(CONFIG) == CONFIG_SHA, 'archive source allowlist changed')
    config = json.loads(CONFIG.read_bytes())
    require(config['publish_release'] is False and config['scientific_reanalysis'] is False,
            'archive scope changed')
    OUT.mkdir(parents=True, exist_ok=True)
    copies = []
    for source in config['source_runs']:
        run = api('actions/runs/'+str(source['id']))
        require(all(run.get(k) == source[k] for k in ('id', 'head_sha', 'path', 'run_attempt', 'status', 'conclusion')),
                'source execution identity changed')
        for expected in source['artifacts']:
            item = api('actions/artifacts/'+str(expected['id']))
            require(all(item.get(k) == expected[k] for k in ('id', 'name', 'size_in_bytes', 'digest', 'expired'))
                    and item['expired'] is False, 'source artifact identity changed')
            require(item['workflow_run']['id'] == source['id']
                    and item['workflow_run']['head_sha'] == source['head_sha'], 'artifact belongs to another execution')
            require(re.fullmatch(r'[A-Za-z0-9._-]+', item['name']) is not None, 'unsafe artifact name')
            relative = f"source/{source['id']}/{item['id']}-{item['name']}.zip"
            path = OUT/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as target:
                subprocess.run(['gh', 'api', f"repos/{REPO}/actions/artifacts/{item['id']}/zip"],
                               stdout=target, check=True, timeout=180)
            check = verify_zip(path, expected)
            copies.append(dict(run_id=source['id'], artifact_id=item['id'], name=item['name'],
                               archive_member=relative, bytes=item['size_in_bytes'], sha256=item['digest'][7:], **check))
            print(json.dumps(dict(verified_artifacts=len(copies), expected_artifacts=config['expected_artifacts'])), flush=True)
    require(len(copies) == config['expected_artifacts']
            and sum(c['bytes'] for c in copies) == config['expected_source_bytes'], 'archive source census differs')
    manifest = dict(version=config['version'], repository=REPO, archive_workflow_run=int(os.environ['GITHUB_RUN_ID']),
                    archive_source_head=head, source_allowlist_sha256=CONFIG_SHA,
                    source_runs=config['source_runs'], source_artifacts=copies,
                    new_independent_campaigns=0, scientific_reanalysis=False, release_published=False)
    manifest_path = OUT/'manifest.json'
    manifest_path.write_bytes(encoded(manifest))
    bundle = OUT/config['archive_name']
    with zipfile.ZipFile(bundle, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        fixed_member(archive, 'manifest.json', manifest_path.read_bytes())
        fixed_member(archive, 'source-allowlist.json', CONFIG.read_bytes())
        for item in copies:
            fixed_member(archive, item['archive_member'], (OUT/item['archive_member']).read_bytes())
    with zipfile.ZipFile(bundle) as archive:
        require(archive.testzip() is None, 'outer archive CRC differs')
        for item in copies:
            require(sha256(archive.read(item['archive_member'])).hexdigest() == item['sha256'],
                    'source ZIP changed during packaging')
    tag = config['release_tag']
    releases = api('releases?per_page=100')
    matches = [r for r in releases if r['tag_name'] == tag]
    require(len(matches) <= 1, 'duplicate archive release')
    if matches:
        release = checked_draft(matches[0], tag, head)
    else:
        release = api('releases', dict(tag_name=tag, target_commitish=head, name=config['release_title'],
            draft=True, prerelease=False, make_latest='false', generate_release_notes=False,
            body='Unpublished byte-preserving archive of all 66 original H-EXEC artifacts and both immutable-audit artifacts. '
                 'Source runs 34230603338 and 34238008817. The original failure and its corrected interpretation remain distinct. '
                 'No model execution, changed outcome or new independent campaign. Full data stay in this repository; '
                 'the manifest binds each source ZIP to its provider digest. This release is not published automatically.'))
        checked_draft(release, tag, head)
    assets = []
    for path in (bundle, manifest_path):
        current = checked_draft(api('releases/'+str(release['id'])), tag, head)
        wanted = dict(name=path.name, size=path.stat().st_size, digest='sha256:'+digest(path), state='uploaded')
        existing = [a for a in current['assets'] if a['name'] == path.name]
        if not existing:
            subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo', REPO], check=True, timeout=300)
        current = checked_draft(api('releases/'+str(release['id'])), tag, head)
        found = [a for a in current['assets'] if a['name'] == path.name]
        require(len(found) == 1 and all(found[0].get(k) == v for k, v in wanted.items()),
                'uploaded archive asset differs; no overwrite is permitted')
        assets.append({k:found[0][k] for k in ('id','name','size','digest','state','url','browser_download_url')})
    result = dict(version=config['version'], qualified=True, archive_workflow_run=int(os.environ['GITHUB_RUN_ID']),
                  archive_source_head=head, source_allowlist_sha256=CONFIG_SHA,
                  source_artifacts=len(copies), source_bytes=sum(c['bytes'] for c in copies),
                  source_zip_bytes_preserved=True, all_zip_crc_checks_passed=True,
                  release_id=release['id'], release_tag=tag, release_url=release['html_url'], draft=True,
                  published_at=None, assets=assets, manifest_sha256=digest(manifest_path),
                  model_execution=False, outcome_reanalysis=False, new_independent_campaigns=0)
    (OUT/'compact.json').write_bytes(encoded(result))
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
