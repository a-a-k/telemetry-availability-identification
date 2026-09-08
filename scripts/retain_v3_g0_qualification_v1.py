"""Retain exact compact execution reports; ordinary/full-model artifacts stay remote."""
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import zipfile

RUN = 34252702244
HEAD = '497b582f65adfb9a84b0442eb025981266f20fb7'
ROOT = Path(f'docs/evidence/v3-g0-qualification-{RUN}')
PROFILES = ('deathstarbench_social_network', 'opentelemetry_demo', 'spring_petclinic_microservices')
FILES = {'preparation': {'source-audit.json', 'resource-usage.txt'},
         'fit': {'results.json', 'read-audit.json', 'resource-usage.txt'},
         'replay': {'results.json', 'read-audit.json', 'resource-usage.txt'}}


def api(path):
    return subprocess.check_output(['gh', 'api', 'repos/a-a-k/telemetry-availability-identification/' + path])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2) + '\n').encode())


def main():
    # Use exact run identity from canonical metadata; no broad artifact downloads.
    recent = json.loads(api('actions/runs?per_page=100'))['workflow_runs']
    matches = [r for r in recent if r['id'] == RUN]
    run = matches[0] if len(matches) == 1 else json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha'] == HEAD and run['conclusion'] == 'success'
    save(ROOT/'run-api.json', {k: run[k] for k in ('id', 'head_sha', 'status', 'conclusion', 'html_url', 'created_at', 'updated_at')})
    artifacts = json.loads(api(f'actions/runs/{RUN}/artifacts?per_page=100'))['artifacts']
    save(ROOT/'all-artifact-metadata.json', artifacts)
    selected = {f'v3-g0-{kind}-compact-{profile}-{RUN}': (kind, profile)
                for kind in FILES for profile in PROFILES}
    expected = set(selected) | {f'v3-g0-{kind}-{p}-{RUN}' for kind in ('source-model', 'model') for p in PROFILES}
    assert {a['name'] for a in artifacts} == expected
    records = []
    for artifact in artifacts:
        if artifact['name'] not in selected:
            continue
        assert not artifact['expired'] and artifact['size_in_bytes'] < 2000000
        data = api(f"actions/artifacts/{artifact['id']}/zip")
        assert len(data) == artifact['size_in_bytes'] and 'sha256:' + sha256(data).hexdigest() == artifact['digest']
        kind, profile = selected[artifact['name']]; dest = ROOT/f'{kind}-{profile}'
        dest.mkdir(parents=True, exist_ok=True); (dest/'compact.zip').write_bytes(data)
        save(dest/'artifact-api.json', artifact); members = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert len(archive.namelist()) == len(FILES[kind]) and set(archive.namelist()) == FILES[kind]
            assert archive.testzip() is None
            for name in sorted(FILES[kind]):
                assert archive.getinfo(name).file_size < 5000000
                value = archive.read(name)
                target = dest/'files'/name; target.parent.mkdir(exist_ok=True); target.write_bytes(value)
                members.append(dict(name=name, bytes=len(value), sha256=sha256(value).hexdigest()))
        save(dest/'member-hashes.json', members)
        records.append(dict(stage=kind, profile=profile, artifact_id=artifact['id'], bytes=len(data), sha256=sha256(data).hexdigest()))
    save(ROOT/'verified-archives.json', records)
    (ROOT/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps(records))


if __name__ == '__main__':
    main()
