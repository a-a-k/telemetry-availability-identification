"""Verify every M9X ZIP remotely and export only compact metadata/cost evidence."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

RUN = 34196680992
HEAD = '4dac3acf0115ca7b532dcce02ebc325eceee9c10'
OUT = Path('workflow-results/m9x-archive-audit')


def gh(path):
    return subprocess.check_output(['gh', 'api', 'repos/a-a-k/telemetry-availability-identification/'+path])


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Full application ZIPs stay remote'
    run = json.loads(gh(f'actions/runs/{RUN}'))
    assert run['head_sha'] == HEAD and run['conclusion'] == 'success'
    api = json.loads(gh(f'actions/runs/{RUN}/artifacts'))
    assert api['total_count'] == 11
    save(OUT/'artifact-api.json', api)
    records = []
    for item in api['artifacts']:
        assert item['workflow_run']['head_sha'] == HEAD and not item['expired']
        data = gh(f"actions/artifacts/{item['id']}/zip")
        assert len(data) == item['size_in_bytes']
        assert 'sha256:'+hashlib.sha256(data).hexdigest() == item['digest']
        checks, metadata = [], {}
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.testzip() is None
            names = set(archive.namelist())
            assert len(names) == len(archive.namelist())
            for name in sorted(names):
                base = Path(name).name
                if base in ('application-input-contract.json', 'solver-contract.json') or (
                        base.startswith('extraction-') and base.endswith('.json')):
                    value = json.loads(archive.read(name))
                    assert value['head_sha'] == HEAD and str(value['run_id']) == str(RUN)
                    prefix = name[:-len(base)]
                    for relative, digest in value.get('files', {}).items():
                        assert hashlib.sha256(archive.read(prefix+relative)).hexdigest() == digest
                        checks.append(prefix+relative)
                    for model in value.get('models', []):
                        for relative, digest in model['files'].items():
                            member = prefix+'models/'+model['model_id']+'/'+relative
                            assert hashlib.sha256(archive.read(member)).hexdigest() == digest
                            checks.append(member)
                    metadata[name] = value
                elif base.endswith('resource-usage.txt'):
                    metadata[name] = archive.read(name).decode()
            # JSON contracts contain identities, hashes, counts and measured times; no raw spans or PCM files.
            save(OUT/'metadata'/(item['name']+'.json'), metadata)
            records.append(dict(id=item['id'], name=item['name'], size=len(data), digest=item['digest'],
                actual_zip_hash_verified=True, zip_crc_verified=True, member_count=len(names),
                manifest_hash_checks=len(checks), exported_metadata_files=sorted(metadata)))
    save(OUT/'archive-integrity.json', dict(source_run=RUN, source_head=HEAD,
        audit_run=os.environ['GITHUB_RUN_ID'], audit_head=os.environ['GITHUB_SHA'], archives=records,
        raw_native_parses=0, model_fits=0, evaluator_rows_read=0))
    print(json.dumps({'verified_archives': len(records), 'verified_bytes': sum(r['size'] for r in records),
                      'manifest_hash_checks': sum(r['manifest_hash_checks'] for r in records)}))


if __name__ == '__main__':
    main()
