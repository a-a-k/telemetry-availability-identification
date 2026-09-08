"""Download exactly one sealed learner artifact; no evaluator/archive access."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

from telemetry_availability.isolated_stochastic_fit import verify_learner_bundle, write

SOURCES={34202539028:'06e83aad5f65f17365c7715ca3b312938b94f1a9',
         34204098497:'68bf0b86acab9072d0d8abfabb7c2d64d4a69546'}


def api(path):
    return subprocess.check_output(['gh','api','repos/a-a-k/telemetry-availability-identification/'+path])


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--placement',choices=['colocated','split'],required=True)
    parser.add_argument('--law',choices=['N','NC','ND','NCD'],required=True)
    args=parser.parse_args()
    run=34204098497 if (args.placement,args.law)==('colocated','NCD') else 34202539028
    run_info=json.loads(api(f'actions/runs/{run}'))
    assert run_info['head_sha']==SOURCES[run]
    name=f'petclinic-technical-learner-{args.placement}-{args.law}-{run}'
    artifacts=json.loads(api(f'actions/runs/{run}/artifacts?per_page=100'))['artifacts']
    matches=[a for a in artifacts if a['name']==name]
    if len(matches)!=1:
        raise ValueError('required retained learner artifact unavailable: '+name)
    meta=matches[0]
    assert meta['workflow_run']['id']==run and meta['workflow_run']['head_sha']==SOURCES[run]
    raw=api(f'actions/artifacts/{meta["id"]}/zip')
    sha=hashlib.sha256(raw).hexdigest()
    assert len(raw)==meta['size_in_bytes'] and meta['digest']=='sha256:'+sha
    root=Path('workflow-input/learner');root.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        names=archive.namelist()
        assert len(names)==len(set(names))
        for name in names:
            p=PurePosixPath(name)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
        archive.extractall(root)
    seal=verify_learner_bundle(root)
    assert seal['metadata']['source_run']==str(run) and seal['metadata']['study_head']==SOURCES[run]
    assert seal['metadata']['placement']==args.placement and seal['metadata']['failure_law']==args.law
    write(Path('workflow-results/source-artifact-audit.json'),dict(artifact=meta,actual_sha256=sha,
        actual_bytes=len(raw),crc_verified=True,all_sealed_files_verified=True,
        downloaded_roles=['learner'],evaluator_downloads=0,source_seal=seal))
    with open(os.environ['GITHUB_OUTPUT'],'a') as stream:
        stream.write('usable='+str(seal['metadata']['usable']).lower()+'\n')
    if not seal['metadata']['usable']:
        write(Path('workflow-results/fit/acquisition-absence.json'),dict(status='acquisition_qualification_failed',
            source=seal['metadata'],boundary=json.loads((root/'audit/boundary.json').read_text()),model_fits=0))


if __name__=='__main__':
    main()
