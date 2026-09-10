"""Retain only the two compact provenance members of completed H-EXEC archival."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import zipfile

from archive_h_exec_evidence_v1 import api, checked_draft, encoded, require

REPO = 'a-a-k/telemetry-availability-identification'
RUN = 34481208537
HEAD = '65547b0ddd5180a6fe01b647690bbf96f128dcfb'
ARTIFACT = 10153683518
SHA = 'cd7db9a564259b376964c400fabdae000e160fa230ac574109c4fe569490d46c'
SIZE = 7700
OUT = Path('docs/evidence/h-exec-durable-archive-34481208537')


def preserve(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == data, 'existing retained evidence differs')
    else:
        path.write_bytes(data)


def main():
    run = api(f'actions/runs/{RUN}')
    require(run['head_sha'] == HEAD and run['run_attempt'] == 1
            and run['status'] == 'completed' and run['conclusion'] == 'success'
            and run['path'] == '.github/workflows/h-exec-durable-archive-v1.yml', 'archive run differs')
    item = api(f'actions/artifacts/{ARTIFACT}')
    require(item['name'] == f'h-exec-durable-archive-compact-{RUN}' and item['size_in_bytes'] == SIZE
            and item['digest'] == 'sha256:'+SHA and item['expired'] is False
            and item['workflow_run']['id'] == RUN and item['workflow_run']['head_sha'] == HEAD,
            'compact artifact identity differs')
    data = subprocess.check_output(['gh', 'api', f'repos/{REPO}/actions/artifacts/{ARTIFACT}/zip'], timeout=120)
    require(len(data) == SIZE and sha256(data).hexdigest() == SHA, 'compact ZIP bytes differ')
    with zipfile.ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        require(len(members) == 2 and set(archive.namelist()) == {'compact.json', 'manifest.json'},
                'compact member allowlist differs')
        require(all((m.external_attr >> 16) & 0o170000 != 0o120000 for m in members), 'compact symlink')
        require(sum(m.file_size for m in members) < 100000 and archive.testzip() is None, 'compact size/CRC differs')
        payloads = {name: archive.read(name) for name in archive.namelist()}
    compact = json.loads(payloads['compact.json'])
    manifest = json.loads(payloads['manifest.json'])
    require(compact['qualified'] is True and compact['archive_workflow_run'] == RUN
            and compact['archive_source_head'] == HEAD and compact['source_artifacts'] == 68
            and compact['source_bytes'] == 58302662 and compact['source_zip_bytes_preserved'] is True
            and compact['all_zip_crc_checks_passed'] is True and compact['model_execution'] is False
            and compact['outcome_reanalysis'] is False and compact['new_independent_campaigns'] == 0,
            'archive completion scope differs')
    require(sha256(payloads['manifest.json']).hexdigest() == compact['manifest_sha256'], 'manifest hash differs')
    config_bytes = Path('configs/h_exec_durable_archive_v1.json').read_bytes()
    require(sha256(config_bytes).hexdigest() == compact['source_allowlist_sha256'], 'source allowlist differs')
    config = json.loads(config_bytes)
    require(manifest['source_runs'] == config['source_runs'] and len(manifest['source_artifacts']) == 68,
            'source census differs')
    release = checked_draft(api(f"releases/{compact['release_id']}"), compact['release_tag'], HEAD)
    require(len(release['assets']) == len(compact['assets']) == 2, 'release asset census differs')
    for expected in compact['assets']:
        found = [a for a in release['assets'] if a['id'] == expected['id']]
        require(len(found) == 1 and all(found[0][k] == expected[k] for k in ('id','name','size','digest','state')),
                'release asset metadata differs')
    record = dict(version='h-exec-durable-archive-compact-retention-v1', run_id=RUN, head_sha=HEAD,
        artifact_id=ARTIFACT, artifact_name=item['name'], bytes=SIZE, sha256=SHA,
        exact_member_allowlist=sorted(payloads), zip_crc_verified=True, release_id=release['id'],
        release_draft=True, release_published_at=None, full_archive_downloaded_locally=False,
        files=[dict(path=n, bytes=len(b), sha256=sha256(b).hexdigest()) for n,b in sorted(payloads.items())])
    preserve(OUT/'.gitattributes', b'* -text\n')
    preserve(OUT/'compact-source.zip', data)
    for name, content in payloads.items():
        preserve(OUT/name, content)
    preserve(OUT/'verified-archives.json', encoded(record))
    print(json.dumps(record))


if __name__ == '__main__':
    main()
