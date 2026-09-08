"""Retain compact prediction/diagnostic archives, never learner/raw archives."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

RUN=34218526868
HEAD='e6f2c11afe9d4b51b466b4d2ba9f66573d8fbfe9'
root=Path(f'docs/evidence/health-prefix-refit-{RUN}')


def api(path):
    return subprocess.check_output(['gh','api','repos/a-a-k/telemetry-availability-identification/'+path])


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


run=json.loads(api(f'actions/runs/{RUN}'))
assert run['status']=='completed' and run['head_sha']==HEAD
save(root/'run-api.json',{k:run[k] for k in ('id','head_sha','status','conclusion','html_url','created_at','updated_at')})
items=json.loads(api(f'actions/runs/{RUN}/artifacts'))['artifacts']
save(root/'all-artifact-metadata.json',items)
records=[]
for item in items:
    if not item['name'].startswith(('prefix-comparison-','prefix-candidates-','prefix-preparation-')):continue
    assert item['size_in_bytes']<1000000 and not item['expired']
    data=api(f'actions/artifacts/{item["id"]}/zip')
    assert len(data)==item['size_in_bytes'] and 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
    role=item['name'].removesuffix('-'+str(RUN))
    dest=root/role;dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        allowed={'qualification.json','paired-predictions.json','parity-mismatches.json','seal.json',
                 'preparation.json','source-artifacts.json','resource-usage.txt'}
        names=archive.namelist()
        assert len(names)==len(set(names))
        assert all(n in allowed or re.fullmatch(r'(colocated|split)-(N|NC|ND|NCD)-r[0-9]\.json',n) for n in names),names
        assert archive.testzip() is None
        members={}
        for name in names:
            raw=archive.read(name)
            members[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            # All members are preserved exactly in compact.zip. Expand only short summaries.
            if name in allowed-{'paired-predictions.json','seal.json'}:
                (dest/name).write_bytes(raw)
        (dest/'compact.zip').write_bytes(data)
        save(dest/'artifact-api.json',item)
        records.append(dict(id=item['id'],name=item['name'],bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                       members=members,crc_verified=True,all_members_preserved_exactly_in_zip=True))
assert len(records)==5
save(root/'verified-archives.json',records)
(root/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
print(json.dumps({k:v for k,v in json.loads((root/'prefix-comparison/qualification.json').read_text()).items()
                  if k not in ('source_seals','historical_m7_artifact')},indent=2))
