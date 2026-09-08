"""Keep exact compact census evidence; never download historical input archives."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

RUN=34217614608
HEAD='92f0cdb49ef31c1efe6aebb28b350e100f7e4391'
root=Path(f'docs/evidence/health-prefix-audit-{RUN}')


def api(path):
    return subprocess.check_output(['gh','api','repos/a-a-k/telemetry-availability-identification/'+path])


def save(path,value):
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


run=json.loads(api(f'actions/runs/{RUN}'))
assert run['conclusion']=='success' and run['head_sha']==HEAD
items=json.loads(api(f'actions/runs/{RUN}/artifacts'))['artifacts']
assert len(items)==1
item=items[0]
assert item['name']==f'health-prefix-audit-v3-{RUN}' and item['size_in_bytes']<500000 and not item['expired']
data=api(f'actions/artifacts/{item["id"]}/zip')
assert len(data)==item['size_in_bytes'] and 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    allowed={'audit.json','source-artifacts.json','source-members.json','resource-usage.txt'}
    assert set(archive.namelist())==allowed and len(archive.namelist())==len(allowed)
    assert archive.testzip() is None
    root.mkdir(parents=True,exist_ok=True)
    files={}
    for name in sorted(allowed):
        raw=archive.read(name)
        (root/name).write_bytes(raw)
        assert (root/name).read_bytes()==raw
        files[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    (root/'compact.zip').write_bytes(data)
    save(root/'artifact-api.json',item)
    save(root/'run-api.json',{k:run[k] for k in ('id','head_sha','status','conclusion','html_url','created_at','updated_at')})
    save(root/'verified-archive.json',dict(id=item['id'],bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),files=files,crc_verified=True))
    (root/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
report=json.loads((root/'audit.json').read_text())
print(json.dumps(report['totals'],indent=2))
