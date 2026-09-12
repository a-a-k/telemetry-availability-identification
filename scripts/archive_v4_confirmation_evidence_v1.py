"""Archive an exact declared terminal census; never interpret primary outcomes."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import zipfile

import retain_v3_comparison_compact_v4 as transport
import archive_v3_main_evidence_v1 as archive_support
from archive_h_exec_evidence_v1 import require,digest,encoded,verify_zip,checked_draft

OUT=Path('workflow-results/confirmation-archive')
PART_LIMIT=750_000_000


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);args=p.parse_args()
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','original remote archive attempt required')
    config=json.loads(args.config.read_bytes());tag=config['tag'];head=os.environ['GITHUB_SHA']
    artifacts=[];runs=[]
    for source in config['sources']:
        run=transport.read_api(f"actions/runs/{source['run']}")
        require(run['head_sha']==source['head'] and run['path']=='.github/workflows/'+source['workflow']
            and run['status']=='completed' and run['run_attempt']==1 and run['conclusion']==source['conclusion'],'source identity or terminal conclusion differs')
        items=transport.collect_pages(f"actions/runs/{source['run']}/artifacts",'artifacts')
        fields=('id','name','size_in_bytes','digest')
        require({a['id']:tuple(a[k]for k in fields)for a in items}=={a['id']:tuple(a[k]for k in fields)for a in source['artifacts']},'declared complete artifact census differs')
        for a in items:
            require(not a['expired'] and 0<a['size_in_bytes']<PART_LIMIT and a['workflow_run']['id']==source['run']
                and a['workflow_run']['head_sha']==source['head'],'source artifact bounds differ')
        artifacts.extend(items);runs.append({k:source[k]for k in ('run','head','workflow','conclusion')})
    require(len(artifacts)==len({a['id']for a in artifacts}) and sum(a['size_in_bytes']for a in artifacts)<4_000_000_000,'combined archive exceeds its declared bounds')
    releases=transport.read_api('releases?per_page=100')
    require(len(releases)<100 and not any(r['tag_name']==tag for r in releases),'archive already exists; never overwrite')
    body=dict(tag_name=tag,target_commitish=head,draft=True,prerelease=False,make_latest='false',
        name=config['name'],body='Exact original ZIP bytes, including technical failures. No primary-outcome interpretation, new observations, reanalysis or automatic publication.')
    release=json.loads(subprocess.check_output(['gh','api','repos/'+transport.REPO+'/releases','--method','POST','--input','-'],input=encoded(body)))
    checked_draft(release,tag,head);archive_support.TAG=tag
    OUT.mkdir(parents=True,exist_ok=False);parts=[];entries=[];resources=[];part=None;current=[];size=0
    def close_part():
        nonlocal part,current,size
        if part is None:return
        path=Path(part.filename);part.close();archive_support.verify_part(path,current)
        asset=archive_support.upload(path,release,head)
        parts.append(dict(name=path.name,bytes=path.stat().st_size,sha256=digest(path),asset=asset,sources=current))
        require(path.resolve().parent==OUT.resolve(),'part deletion outside archive output');path.unlink()
        part=None;current=[];size=0
    for item in sorted(artifacts,key=lambda a:a['id']):
        if part is not None and size+item['size_in_bytes']>PART_LIMIT:close_part()
        if part is None:part=zipfile.ZipFile(OUT/f'original-part-{len(parts)+1:02d}.zip','w',allowZip64=True)
        path=OUT/f"source-{item['id']}.zip";path.write_bytes(transport.api(f"actions/artifacts/{item['id']}/zip"));verify_zip(path,item)
        with zipfile.ZipFile(path) as source_zip:
            for info in source_zip.infolist():
                if info.filename.endswith('resource-usage.txt') and not info.is_dir():
                    require(info.file_size<=65536,'oversized timing metadata')
                    raw=source_zip.read(info.filename)
                    resources.append(dict(source_run=item['workflow_run']['id'],artifact_id=item['id'],artifact_name=item['name'],
                        member=info.filename,sha256=sha256(raw).hexdigest(),text=raw.decode('utf-8')))
        member=f"{item['id']}.zip";archive_support.add_source(part,path,member)
        record=dict(member=member,artifact_id=item['id'],artifact_name=item['name'],source_run=item['workflow_run']['id'],
            bytes=item['size_in_bytes'],sha256=digest(path))
        current.append(record);entries.append(record);size+=item['size_in_bytes']
        require(path.resolve().parent==OUT.resolve(),'temporary deletion outside archive output');path.unlink()
    close_part()
    manifest=dict(version='v4-confirmation-durable-archive-v1',sources=runs,archive_run=int(os.environ['GITHUB_RUN_ID']),
        archive_head=head,config_sha256=sha256(args.config.read_bytes()).hexdigest(),tag_name=tag,release_id=release['id'],
        source_artifacts=len(artifacts),source_bytes=sum(a['size_in_bytes']for a in artifacts),parts=parts,
        all_source_zip_bytes_preserved=True,outcomes_interpreted=False,scientific_reanalysis=False,published=False)
    for name,value in [('manifest.json',manifest),('resource-records.json',resources),('source-artifacts.json',artifacts)]:
        path=OUT/name;path.write_bytes(encoded(value));archive_support.upload(path,release,head)
    current_release=checked_draft(transport.read_api(f"releases/{release['id']}"),tag,head)
    require({a['name']for a in current_release['assets']}=={p['name']for p in parts}|{'manifest.json','resource-records.json','source-artifacts.json'},'final release asset census differs')
    compact=dict(manifest,assets=[{k:a[k]for k in ('id','name','size','digest','state')}for a in current_release['assets']])
    (OUT/'compact.json').write_bytes(encoded(compact))
    print(json.dumps(dict(source_artifacts=len(artifacts),source_bytes=manifest['source_bytes'],parts=len(parts),release_id=release['id'],published=False)))


if __name__=='__main__':main()
