"""Retain only predeclared compact reports; never fetch model/native artifacts."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

RUN = 34224526327
HEAD = '62023d2f18e04a28db3c99d4a4f7cd5eccdf0f3b'
ROOT = Path(f'docs/evidence/existing-graph-observation-{RUN}')


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
    selected = {f'existing-graph-{role}-{profile}-{RUN}': f'{role}-{profile}'
                for role in ('fit', 'source', 'replay') for profile in ('deathstarbench_social_network', 'opentelemetry_demo')}
    selected[f'existing-graph-qualification-{RUN}'] = 'qualification'
    allowed = {'fit.json', 'read-audit.json', 'resource-usage.txt', 'replay.json',
               'qualification.json', 'source-audit.json'}
    records = []
    # Metadata for models is retained, but their download endpoints are never called.
    save(ROOT/'all-artifact-metadata.json', artifacts)
    for item in artifacts:
        if item['name'] not in selected:
            continue
        assert not item['expired'] and item['size_in_bytes'] < 20000
        data = api(f"actions/artifacts/{item['id']}/zip")
        assert len(data) == item['size_in_bytes']
        assert 'sha256:' + hashlib.sha256(data).hexdigest() == item['digest']
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            assert members and len(members) == len({m.filename for m in members})
            assert all(m.filename in allowed and m.file_size < 100000 for m in members), [m.filename for m in members]
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
    assert len(records) == 7
    save(ROOT/'verified-archives.json', records)
    (ROOT/'.gitattributes').write_text('* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps([dict(id=r["id"],name=r["name"],bytes=r["bytes"]) for r in records]))


if __name__ == '__main__':
    main()
