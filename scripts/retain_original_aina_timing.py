"""Retain only the named compact historical audit, never original payload archives."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile


def api(path):
    return subprocess.check_output(['gh', 'api', 'repos/a-a-k/telemetry-availability-identification/'+path])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2)+'\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--head', required=True)
    args = parser.parse_args()
    root = Path(f'docs/evidence/original-aina-timing-{args.run}')
    run = json.loads(api(f'actions/runs/{args.run}'))
    assert run['head_sha'] == args.head and run['status'] == 'completed'
    save(root/'run-api.json', {k: run[k] for k in ('id','head_sha','status','conclusion','html_url','created_at','updated_at','path')})
    artifacts = json.loads(api(f'actions/runs/{args.run}/artifacts'))['artifacts']
    selected = [a for a in artifacts if a['name'] == f'original-aina-timing-compact-{args.run}']
    assert len(selected) == 1
    item = selected[0]
    assert not item['expired'] and item['size_in_bytes'] <= 5_000_000
    data = api(f"actions/artifacts/{item['id']}/zip")
    assert len(data) == item['size_in_bytes']
    assert 'sha256:'+hashlib.sha256(data).hexdigest() == item['digest']
    allowed = {'summary.json','window-timing-census.json','error-type-census.json','failure.json','resource-usage.txt'}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        assert len(members) == len({m.filename for m in members})
        assert all(m.filename in allowed and m.file_size <= 15_000_000 for m in members)
        assert archive.testzip() is None
        hashes = []
        for member in members:
            value = archive.read(member)
            hashes.append({'name':member.filename,'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()})
            if member.filename in {'summary.json','input-provenance.json','progress.json','failure.json','resource-usage.txt'}:
                target = root/'files'/member.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(value)
        save(root/'member-hashes.json', hashes)
    (root/'compact.zip').write_bytes(data)
    save(root/'artifact-api.json', item)
    (root/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({'run':args.run,'conclusion':run['conclusion'],'artifact_id':item['id'],'bytes':len(data)}))


if __name__ == '__main__':
    main()
