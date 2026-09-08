"""Retain only predeclared compact reports; never fetch model/native artifacts."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

RUN = 34223543390
HEAD = 'e41468f845c8172fcb9a410ea71dd8b7792312c8'
ROOT = Path(f'docs/evidence/existing-ordinary-{RUN}')


def api(path):
    return subprocess.check_output(['gh', 'api', 'repos/a-a-k/telemetry-availability-identification/' + path])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    run = json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha'] == HEAD and run['conclusion'] == 'success'
    save(ROOT/'run-api.json', {k: run[k] for k in ('id', 'head_sha', 'status', 'conclusion', 'html_url', 'created_at', 'updated_at')})
    artifacts = json.loads(api(f'actions/runs/{RUN}/artifacts'))['artifacts']
    selected = {f'existing-{role}-{profile}-{RUN}': f'{role}-{profile}'
                for role in ('preparation', 'inventory') for profile in
                ('deathstarbench_social_network', 'opentelemetry_demo')}
    allowed = {'projection-audit.json', 'inventory.json', 'read-audit.json', 'resource-usage.txt'}
    records = []
    # Metadata for ordinary bundles is retained, but their download endpoints are never called.
    save(ROOT/'all-artifact-metadata.json', artifacts)
    for item in artifacts:
        if item['name'] not in selected:
            continue
        assert not item['expired'] and item['size_in_bytes'] < 200000
        data = api(f"actions/artifacts/{item['id']}/zip")
        assert len(data) == item['size_in_bytes']
        assert 'sha256:' + hashlib.sha256(data).hexdigest() == item['digest']
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            assert members and len(members) == len({m.filename for m in members})
            assert all(m.filename in allowed and m.file_size < 2000000 for m in members), [m.filename for m in members]
            assert archive.testzip() is None
            dest = ROOT/selected[item['name']]
            dest.mkdir(parents=True, exist_ok=True)
            (dest/'compact.zip').write_bytes(data)
            save(dest/'artifact-api.json', item)
            hashes = {}
            for member in members:
                value = archive.read(member)
                target = dest/'files'/member.filename
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(value)
                assert target.read_bytes() == value
                hashes[member.filename] = hashlib.sha256(value).hexdigest()
            records.append(dict(id=item['id'], name=item['name'], bytes=len(data),
                                sha256=hashlib.sha256(data).hexdigest(), member_sha256=hashes))
    assert len(records) == 4
    save(ROOT/'verified-archives.json', records)
    (ROOT/'.gitattributes').write_text('* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps([dict(id=r["id"],name=r["name"],bytes=r["bytes"]) for r in records]))


if __name__ == '__main__':
    main()
