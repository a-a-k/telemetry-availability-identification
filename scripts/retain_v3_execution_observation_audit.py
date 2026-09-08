"""Retain exact compact evidence only; original ordinary/native inputs stay remote."""
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import zipfile

RUN = 34241300741
HEAD = 'dc9256875b943df509469ffc50cb0fc8caf09b67'
ROOT = Path(f'docs/evidence/v3-execution-observation-audit-{RUN}')
PROFILES = ('deathstarbench_social_network', 'opentelemetry_demo', 'spring_petclinic_microservices')
FILES = {'source-audit.json', 'consumer-read-audit.json', 'execution-observation-audit.json',
         'completion.json', 'preparation-resource-usage.txt', 'audit-resource-usage.txt'}


def api(path):
    return subprocess.check_output(['gh', 'api', 'repos/a-a-k/telemetry-availability-identification/' + path])


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2) + '\n').encode())


def main():
    run = json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha'] == HEAD and run['conclusion'] == 'success'
    save(ROOT/'run-api.json', {k: run[k] for k in ('id', 'head_sha', 'status', 'conclusion', 'html_url', 'created_at', 'updated_at')})
    items = json.loads(api(f'actions/runs/{RUN}/artifacts?per_page=100'))['artifacts']
    wanted = {f'v3-execution-audit-compact-{p}-{RUN}': p for p in PROFILES}
    assert {r['name'] for r in items} == set(wanted)
    records = []
    for item in items:
        assert not item['expired'] and item['size_in_bytes'] < 2000000
        data = api(f"actions/artifacts/{item['id']}/zip")
        assert len(data) == item['size_in_bytes'] and 'sha256:' + sha256(data).hexdigest() == item['digest']
        profile = wanted[item['name']]; dest = ROOT/profile
        dest.mkdir(parents=True, exist_ok=True); (dest/'compact.zip').write_bytes(data)
        save(dest/'artifact-api.json', item); members = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert len(archive.namelist()) == len(FILES) and set(archive.namelist()) == FILES
            assert archive.testzip() is None
            for name in sorted(FILES):
                assert archive.getinfo(name).file_size < 5000000
                value = archive.read(name)
                members.append(dict(name=name, bytes=len(value), sha256=sha256(value).hexdigest()))
                target = dest/'files'/name; target.parent.mkdir(exist_ok=True); target.write_bytes(value)
        save(dest/'member-hashes.json', members)
        records.append(dict(profile=profile, artifact_id=item['id'], bytes=len(data), sha256=sha256(data).hexdigest()))
    save(ROOT/'verified-archives.json', records)
    (ROOT/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps(records))


if __name__ == '__main__':
    main()
