"""Retain compact rescore reports and compressed aggregate tables, never raw inputs."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

RUN=34220234444
HEAD='38f5e01c7f5003a3cde84afc647fe4d2f3ae1180'
ROOT=Path(f'docs/evidence/health-prefix-rescore-{RUN}')


def api(path):
    return subprocess.check_output(['gh','api','repos/a-a-k/telemetry-availability-identification/'+path])


def save(path,value):
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


run=json.loads(api(f'actions/runs/{RUN}'))
assert run['head_sha']==HEAD and run['conclusion']=='success'
items=json.loads(api(f'actions/runs/{RUN}/artifacts'))['artifacts']
assert len(items)==2
ROOT.mkdir(parents=True,exist_ok=True)
save(ROOT/'run-api.json',{k:run[k] for k in ('id','head_sha','status','conclusion','html_url','created_at','updated_at')})
save(ROOT/'all-artifact-metadata.json',items)
records=[]
for role in ('compact','tables'):
    item=next(a for a in items if a['name']==f'health-prefix-rescore-{role}-{RUN}')
    assert not item['expired'] and item['size_in_bytes']<(50000 if role=='compact' else 8000000)
    data=api(f'actions/artifacts/{item["id"]}/zip')
    assert len(data)==item['size_in_bytes'] and 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist();assert len(names)==len(set(names))
        if role=='compact':
            expected={'dependency-qualification.json','rescore.json','resource-usage.txt'}
        else:
            report=json.loads((ROOT/'rescore.json').read_text())
            expected=set(report['files'])
            assert all(n in ('accepted-predictions.json','dependency-decisions.json') or
                       n.endswith(('/operation-summary.csv','/condition-summary.csv','/common-cells.csv',
                                   '/paired-summary.csv','/census.csv','/scores.csv',
                                   '/historical-contrasts.csv','/historical-summary.csv')) for n in expected)
        assert set(names)==expected
        assert archive.testzip() is None
        members={}
        for name in names:
            raw=archive.read(name)
            members[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            if role=='compact':(ROOT/name).write_bytes(raw)
            else:assert members[name]==report['files'][name],name
        (ROOT/(role+'.zip')).write_bytes(data)
        records.append(dict(id=item['id'],role=role,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                            members=members,crc_verified=True,all_members_preserved_exactly_in_zip=True))
save(ROOT/'verified-archives.json',records)
(ROOT/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
report=json.loads((ROOT/'rescore.json').read_text())
print(json.dumps(dict(qualified=report['qualified'],historical_score_max_error=report['historical_score_max_error'],
      dependency_counts=report['dependency_qualification']['counts'],records=[
          {k:r[k] for k in ('prediction_version','window_version','census_slots','scored_rows',
                           'current_all_sequence_requests','current_stable_requests')} for r in report['records']]),indent=2))
