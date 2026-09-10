"""Retain exact compact matched-qualification evidence; never fetch models/JARs."""
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v2 as retention

RUN=34458641994
HEAD='f3d4061dd6468de68d61060c1d22a8066cb6d586'
WORKFLOW='.github/workflows/pmx-clock-progress-qualification-v1.yml'


def main():
    run=retention.read_api(f'actions/runs/{RUN}')
    assert run['head_sha']==HEAD and run['run_attempt']==1 and run['status']=='completed'
    assert run['path']==WORKFLOW and run['head_repository']['full_name']==retention.REPO
    artifacts=retention.collect_pages(f'actions/runs/{RUN}/artifacts','artifacts')
    jobs=retention.collect_pages(f'actions/runs/{RUN}/jobs','jobs')
    choices={}
    config=json.loads(Path('configs/pmx_clock_progress_qualification_v1.json').read_bytes())
    for i,record in enumerate(config['artifacts'],1):
        choices[f"pmx-clock-compact-{record['key']}-{RUN}"]=dict(directory=f'extract-{i:02d}',allowed={'compact.json'})
    old,_=retention.selections(34447262633,'preflight')
    for name,choice in old.items():
        if name.startswith('v3-comparison-pmx-candidates-'):
            new=name.replace('v3-comparison-pmx-candidates-','pmx-clock-candidates-').replace('34447262633',str(RUN))
            choices[new]=choice
    choices[f'pmx-clock-qualification-audit-{RUN}']=dict(directory='audit',allowed={'compact.json'})
    assert len(choices)==11
    out=Path(f'docs/evidence/pmx-clock-progress-qualification-{RUN}')
    retention.persist(out/'run-api.json',retention.encoded(run))
    retention.persist(out/'jobs-api.json',retention.encoded(jobs))
    retention.persist(out/'artifacts-api.json',retention.encoded(artifacts))
    records=[];missing=[]
    for name,choice in choices.items():
        matches=[a for a in artifacts if a['name']==name]
        assert len(matches)<=1
        if not matches:missing.append(name);continue
        artifact=matches[0];data=retention.api(f"actions/artifacts/{artifact['id']}/zip")
        files=retention.check_archive(data,artifact,choice['allowed'])
        assert set(files)==choice['allowed']
        target=out/choice['directory']
        retention.persist(target/'compact.zip',data)
        retention.persist(target/'artifact-api.json',retention.encoded(artifact))
        for member,raw in files.items():retention.persist(target/'files'/member,raw)
        records.append(dict(name=name,directory=choice['directory'],bytes=len(data),
            sha256=sha256(data).hexdigest(),members={n:sha256(raw).hexdigest() for n,raw in files.items()}))
    manifest=dict(run_id=RUN,head=HEAD,records=records,absent_artifacts=missing,
        archives=len(records),compressed_bytes=sum(r['bytes'] for r in records),
        member_count=sum(len(r['members']) for r in records),no_model_or_jar_artifacts_downloaded=True)
    retention.persist(out/'verified-archives.json',retention.encoded(manifest))
    retention.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    if not missing:
        proof=json.loads((out/'audit/files/compact.json').read_bytes())
        assert proof['run_id']==str(RUN) and proof['head']==HEAD
        for name,expected in proof['evidence_sha256'].items():
            parts=Path(name).parts
            artifact_name=parts[1]
            relative=Path(*parts[2:])
            assert artifact_name in choices
            actual=out/choices[artifact_name]['directory']/'files'/relative
            assert sha256(actual.read_bytes()).hexdigest()==expected
        manifest['qualification_result']=proof['qualified']
    print(json.dumps({k:v for k,v in manifest.items() if k!='records'}))


if __name__=='__main__':main()
