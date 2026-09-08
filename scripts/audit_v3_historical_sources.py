"""Remote-only byte comparison of published source archives with retained tag files."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Historical archives stay remote'
    root=Path('docs/evidence/v3-historical-sources')
    out=Path('workflow-results/v3-historical-source-audit')
    out.mkdir(parents=True,exist_ok=True)
    records=[]
    for record_id,prefix,manifest in [
        ('18271837','icse-v1.2.0-release','icse-source-manifest.json'),
        ('17703953','aina-v1.0.0','aina-source-manifest.json')]:
        metadata_bytes=urllib.request.urlopen('https://zenodo.org/api/records/'+record_id,timeout=90).read()
        (out/(record_id+'-record.json')).write_bytes(metadata_bytes)
        metadata=json.loads(metadata_bytes)
        assert len(metadata['files'])==1
        item=metadata['files'][0]
        assert item['size']<5_000_000
        data=urllib.request.urlopen(item['links']['self'],timeout=90).read()
        assert len(data)==item['size']
        algorithm,checksum=item['checksum'].split(':',1)
        assert algorithm in ('md5','sha256') and hashlib.new(algorithm,data).hexdigest()==checksum
        comparisons=[]
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert archive.testzip() is None
            for source in json.loads((root/manifest).read_text()):
                candidates=[x for x in archive.namelist() if x.endswith('/'+source['path']) or x==source['path']]
                assert len(candidates)==1,(source['path'],candidates)
                content=archive.read(candidates[0])
                tag_content=(root/prefix/source['path']).read_bytes()
                assert hashlib.sha256(tag_content).hexdigest()==source['sha256']
                comparisons.append(dict(path=source['path'],archive_member=candidates[0],
                    archive_sha256=hashlib.sha256(content).hexdigest(),tag_sha256=source['sha256'],
                    equal=content==tag_content))
        records.append(dict(record_id=record_id,record_url='https://zenodo.org/records/'+record_id,
            archive_size=len(data),archive_sha256=hashlib.sha256(data).hexdigest(),
            published_checksum_verified=True,zip_crc_verified=True,comparisons=comparisons))
    # The PMX solver-contract contains complete PCM models, so audit it remotely.
    pmx_root=Path('docs/evidence/petclinic-pmx-34206870187/solver-contract')
    pmx_api=json.loads(subprocess.check_output(['gh','api',
        'repos/a-a-k/telemetry-availability-identification/actions/artifacts/10048446080']))
    assert pmx_api['workflow_run']['head_sha']=='3a916932bbce78fcb270b5710e90dead8cd00723'
    pmx_data=subprocess.check_output(['gh','api',
        'repos/a-a-k/telemetry-availability-identification/actions/artifacts/10048446080/zip'])
    assert len(pmx_data)==441236 and hashlib.sha256(pmx_data).hexdigest()=='70da55072eed2eca50473bb33f31900b88274243e3492d51f8d6ce9205ac9400'
    with zipfile.ZipFile(io.BytesIO(pmx_data)) as archive:
        assert archive.testzip() is None
        assert archive.read('solver-contract.json')==(pmx_root/'files/solver-contract.json').read_bytes()
        pmx_members={x.filename:hashlib.sha256(archive.read(x)).hexdigest() for x in archive.infolist() if not x.is_dir()}
    (out/'pmx-contract-audit.json').write_text(json.dumps(dict(artifact=pmx_api,all_member_sha256=pmx_members,
        exact_metadata_equal=True,actual_archive_sha256=hashlib.sha256(pmx_data).hexdigest()),indent=2)+'\n')
    report=dict(head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
        scope='selected original source files; no historical runtime/data replication',records=records)
    (out/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    assert all(c['equal'] for r in records for c in r['comparisons']), 'Archive and tag differ: preserve both versions before selecting G0'
    print(json.dumps(dict(records=len(records),selected_files=sum(len(r['comparisons']) for r in records),all_equal=True)))


if __name__=='__main__': main()
