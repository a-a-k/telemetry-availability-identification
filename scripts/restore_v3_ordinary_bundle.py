"""Restore only a pinned ordinary-calibration artifact on GitHub Actions."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from telemetry_availability.v3_primary_projection import verify_bundle,write

SOURCES={
    'colocated':(10050553358,2403906,'2961e5d2f9c34cc68fe458ec3dda07730e7888eae2056859dc2dda476c3e25de'),
    'split':(10050553448,2430058,'3583d1f0a2d8d6a74e7c9dd033e34c3182550804da18851c7fee9a0ca129859c')}


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','ordinary native archives stay remote'
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--placement',choices=list(SOURCES),required=True)
    placement=parser.parse_args().placement;identifier,size,digest=SOURCES[placement]
    base='repos/a-a-k/telemetry-availability-identification/actions/artifacts/'+str(identifier)
    api=json.loads(subprocess.check_output(['gh','api',base]))
    assert api['workflow_run']['id']==34212928736 and api['workflow_run']['head_sha']=='b0ddadb83868e4a80b6a4391b9c65e2269012014'
    assert api['name']==f'v3-ordinary-{placement}-NCD-34212928736' and not api['expired']
    data=subprocess.check_output(['gh','api',base+'/zip'])
    assert len(data)==size==api['size_in_bytes'] and hashlib.sha256(data).hexdigest()==digest
    assert api['digest']=='sha256:'+digest
    root=Path('workflow-input/ordinary');root.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        for member in archive.infolist():
            if member.is_dir():continue
            assert '/' not in member.filename and '\\' not in member.filename
            (root/member.filename).write_bytes(archive.read(member))
    seal=verify_bundle(root)
    write(Path('workflow-results/source/source-audit.json'),dict(artifact=api,actual_zip_sha256=digest,
        actual_zip_bytes=size,zip_crc_verified=True,ordinary_seal=seal,downloaded_roles=['ordinary_calibration'],
        legacy_or_evaluator_downloads=0))


if __name__=='__main__':main()
