"""Retain exact compact replay outputs; no raw/native artifact download."""
from hashlib import sha256
import io
import json
from pathlib import Path,PurePosixPath
import re
import subprocess
import zipfile

RUN=34238008817
HEAD='88b9d0065f064a2fa130d185435e3d34cef2cca8'
ROOT=Path(f'docs/evidence/h-exec-sealed-audit-{RUN}')


def api(path):return subprocess.check_output(['gh','api','repos/a-a-k/telemetry-availability-identification/'+path])


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


def main():
    run=json.loads(api(f'actions/runs/{RUN}'));assert run['head_sha']==HEAD and run['conclusion']=='success'
    save(ROOT/'run-api.json',{k:run[k] for k in ('id','head_sha','status','conclusion','html_url','created_at','updated_at','path')})
    artifacts=json.loads(api(f'actions/runs/{RUN}/artifacts?per_page=100'))['artifacts']
    selected={f'h-exec-sealed-audit-compact-{RUN}':'audit',f'h-exec-sealed-recomputed-compact-{RUN}':'recomputed'}
    assert {a['name'] for a in artifacts}==set(selected)
    records=[]
    for item in artifacts:
        kind=selected[item['name']];assert not item['expired'] and item['size_in_bytes']<5000000
        data=api(f"actions/artifacts/{item['id']}/zip")
        assert len(data)==item['size_in_bytes'] and 'sha256:'+sha256(data).hexdigest()==item['digest']
        dest=ROOT/kind;dest.mkdir(parents=True,exist_ok=True);(dest/'compact.zip').write_bytes(data)
        save(dest/'artifact-api.json',item);hashes=[]
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members=[m for m in archive.infolist() if not m.is_dir()]
            assert len(members)==len({m.filename for m in members}) and archive.testzip() is None
            for member in members:
                path=PurePosixPath(member.filename)
                if kind=='audit':
                    assert member.filename in {'cell-audits.json','study-analysis.json','replay-audit-summary.json','resource-usage.txt'}
                else:
                    assert len(path.parts)==2 and re.fullmatch(r'h-exec-compact-study-b[0-7]-s[0-3]-34230603338',path.parts[0])
                    assert path.name in {'census.json','static-controls.json','summary.json','identity.json','boundaries.json','interventions.json','periods.json','instrumentation-audit.json','acquisition-summary.json'}
                assert member.file_size<10000000
                value=archive.read(member)
                hashes.append({'name':member.filename,'bytes':len(value),'sha256':sha256(value).hexdigest()})
                if kind=='audit':
                    target=dest/'files'/member.filename;target.parent.mkdir(exist_ok=True);target.write_bytes(value)
        save(dest/'member-hashes.json',hashes)
        records.append({'kind':kind,'artifact_id':item['id'],'bytes':len(data),'sha256':sha256(data).hexdigest(),'files':len(hashes)})
    save(ROOT/'verified-archives.json',records)
    (ROOT/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps(records))


if __name__=='__main__':main()
