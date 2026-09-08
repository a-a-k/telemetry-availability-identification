"""Retain compact B0 audits only; full model artifact endpoints are never called."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import zipfile


def api(path):return subprocess.check_output(['gh','api','repos/a-a-k/telemetry-availability-identification/'+path])


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=int,required=True);parser.add_argument('--head',required=True);args=parser.parse_args()
    root=Path(f'docs/evidence/b0-v3-technical-{args.run}')
    run=json.loads(api(f'actions/runs/{args.run}'));assert run['status']=='completed' and run['head_sha']==args.head
    save(root/'run-api.json',{k:run[k] for k in ('id','head_sha','status','conclusion','html_url','created_at','updated_at','path')})
    artifacts=json.loads(api(f'actions/runs/{args.run}/artifacts?per_page=100'))['artifacts']
    save(root/'all-artifact-metadata.json',artifacts)
    allowed={'source-audit.json','outcome-encoding-census.json','consumer-read-audit.json','qualification.json',
             'preparation-resource-usage.txt','fit-resource-usage.txt'}
    records=[]
    for profile in ('deathstarbench_social_network','opentelemetry_demo','spring_petclinic_microservices'):
        selected=[a for a in artifacts if a['name']==f'b0-v3-compact-{profile}-{args.run}'];assert len(selected)==1
        item=selected[0];assert not item['expired'] and item['size_in_bytes']<100000
        data=api(f"actions/artifacts/{item['id']}/zip")
        assert len(data)==item['size_in_bytes'] and 'sha256:'+sha256(data).hexdigest()==item['digest']
        dest=root/profile;dest.mkdir(parents=True,exist_ok=True)
        (dest/'compact.zip').write_bytes(data);save(dest/'artifact-api.json',item)
        hashes=[]
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members=[m for m in archive.infolist() if not m.is_dir()]
            assert len(members)==len({m.filename for m in members}) and archive.testzip() is None
            for member in members:
                assert member.filename in allowed and member.file_size<100000
                value=archive.read(member);target=dest/'files'/member.filename;target.parent.mkdir(exist_ok=True);target.write_bytes(value)
                hashes.append({'name':member.filename,'bytes':len(value),'sha256':sha256(value).hexdigest()})
        records.append({'profile':profile,'artifact_id':item['id'],'bytes':len(data),'sha256':sha256(data).hexdigest(),'members':hashes})
    save(root/'verified-archives.json',records)
    (root/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({'run':args.run,'conclusion':run['conclusion'],'compact_archives':len(records),'bytes':sum(r['bytes'] for r in records)}))


if __name__=='__main__':main()
