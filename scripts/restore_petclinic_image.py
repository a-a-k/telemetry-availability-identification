"""Restore the exact previously built Petclinic image remotely; never rebuild it."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Application image stays remote'
config = json.loads(Path('configs/petclinic_runtime_v2.json').read_text())
lock = config['build_artifact']
out = Path('workflow-input/petclinic-build')
out.mkdir(parents=True, exist_ok=True)
prefix = 'repos/a-a-k/telemetry-availability-identification/actions/artifacts/'
actual = json.loads(subprocess.check_output(['gh','api',prefix+str(lock['id'])]))
assert all(actual[k] == lock[k] for k in ('id','name','size_in_bytes'))
assert actual['digest'] == 'sha256:'+lock['sha256'] and not actual['expired']
assert actual['workflow_run']['id']==lock['run_id'] and actual['workflow_run']['head_sha']==lock['head_sha']
archive_path = out.parent/'petclinic-build.zip'
with archive_path.open('wb') as stream:
    subprocess.run(['gh','api',prefix+str(lock['id'])+'/zip'],stdout=stream,check=True)
assert archive_path.stat().st_size == lock['size_in_bytes']
def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
assert sha(archive_path) == lock['sha256']
with zipfile.ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    assert all((out/name).resolve().is_relative_to(out.resolve()) for name in archive.namelist())
    archive.extractall(out)
assert sha(out/'build-manifest.json') == lock['manifest_sha256']
manifest=json.loads((out/'build-manifest.json').read_text())
for name,digest in manifest['files'].items():
    assert sha(out/name)==digest,name
subprocess.run(['docker','load','-i',str(out/'petclinic-image.tar')],check=True)
image=json.loads(subprocess.check_output(['docker','image','inspect',manifest['image_tag']]))[0]
assert image['Id']==manifest['image']['Id']==lock['image_id']
target=Path('workflow-results/petclinic-v2-compact')
target.mkdir(parents=True,exist_ok=True)
(target/'image-restore-audit.json').write_text(json.dumps(dict(lock=lock,actual=actual,
    actual_zip_sha_verified=True,manifest_hash_checks=len(manifest['files']),image_id=image['Id'],
    build_count=0,study_head=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID']),indent=2)+'\n')
