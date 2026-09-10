"""Preserve all original recovery artifacts remotely in an unpublished archive."""
import json
import os
from pathlib import Path
import subprocess
import zipfile

import retain_v3_comparison_compact_v4 as transport
from archive_h_exec_evidence_v1 import require,encoded,digest,verify_zip,checked_draft
from archive_v3_main_evidence_v1 import add_source,verify_part

RUN=34517752889
HEAD='3412fa5e4b58e950b976835b9f354e9da28f27dd'
TAG=f'evidence-v3-main-recovery-{RUN}-v1'
OUT=Path('workflow-results/recovery-archive')
PROFILES=('deathstarbench_social_network','opentelemetry_demo','spring_petclinic_microservices')


def expected_names():
    names={f'v3-main-recovery-{role}-{profile}-{RUN}' for profile in PROFILES
           for role in ('pmx-solver','pmx-candidates','pmx-solver-contract','frozen','evaluation')}
    return names|{f'v3-main-recovery-analysis-{RUN}'}


def checked_source(run,artifacts):
    require(run['id']==RUN and run['head_sha']==HEAD and run['run_attempt']==1
        and run['path']=='.github/workflows/v3-main-transport-recovery-v1.yml'
        and run['status']=='completed' and run['conclusion']=='success'
        and run['head_repository']['full_name']==transport.REPO,'wrong or incomplete recovery source')
    require(len(artifacts)==16 and len({a['id'] for a in artifacts})==16
        and {a['name'] for a in artifacts}==expected_names(),'recovery archive source census differs')
    require(sum(a['size_in_bytes'] for a in artifacts)<900_000_000,'recovery archive exceeds bounded package')
    for item in artifacts:
        require(item['expired'] is False and 0<item['size_in_bytes']<=100_000_000
            and item['workflow_run']['id']==RUN and item['workflow_run']['head_sha']==HEAD,
            'recovery artifact source/size differs')


def main():
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_REPOSITORY')==transport.REPO
        and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','original remote archival attempt required')
    run=transport.read_api(f'actions/runs/{RUN}')
    artifacts=transport.collect_pages(f'actions/runs/{RUN}/artifacts','artifacts')
    checked_source(run,artifacts)
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    releases=transport.read_api('releases?per_page=100')
    require(len(releases)<100,'release census needs pagination before creating archive')
    matches=[r for r in releases if r['tag_name']==TAG]
    require(not matches,'recovery archive already exists; do not overwrite or create a replacement')
    body=dict(tag_name=TAG,target_commitish=head,draft=True,prerelease=False,make_latest='false',
        name=f'Unpublished recovered main computation evidence {RUN}',
        body='Exact original recovery ZIPs. No new observations, refitting, scientific reanalysis or automatic publication.')
    release=json.loads(subprocess.check_output(['gh','api',f'repos/{transport.REPO}/releases','--method','POST','--input','-'],input=encoded(body)))
    checked_draft(release,TAG,head)
    OUT.mkdir(parents=True);full=OUT/f'v3-main-recovery-{RUN}-original-artifacts.zip';entries=[]
    with zipfile.ZipFile(full,'w',allowZip64=True) as archive:
        for item in sorted(artifacts,key=lambda a:a['name']):
            temporary=OUT/f'source-{item["id"]}.zip'
            temporary.write_bytes(transport.api(f'actions/artifacts/{item["id"]}/zip'))
            verify_zip(temporary,item)
            member=f'{item["id"]}.zip'
            add_source(archive,temporary,member)
            entries.append(dict(member=member,artifact_id=item['id'],artifact_name=item['name'],
                bytes=item['size_in_bytes'],sha256=digest(temporary)))
            require(temporary.resolve().parent==OUT.resolve(),'temporary source outside archive directory')
            temporary.unlink()
    verify_part(full,entries)
    manifest=dict(version='v3-main-recovery-durable-archive-v1',source_run=RUN,source_head=HEAD,
        archive_run=int(os.environ['GITHUB_RUN_ID']),archive_head=head,release_id=release['id'],draft=True,
        source_artifacts=16,source_bytes=sum(a['size_in_bytes'] for a in artifacts),entries=entries,
        full_asset_name=full.name,full_asset_bytes=full.stat().st_size,full_asset_sha256=digest(full),
        new_campaigns=0,scientific_reanalysis=False)
    (OUT/'manifest.json').write_bytes(encoded(manifest))
    (OUT/'source-artifacts.json').write_bytes(encoded(artifacts))
    subprocess.run(['gh','release','upload',TAG,str(full),str(OUT/'manifest.json'),'--repo',transport.REPO],check=True)
    current=checked_draft(transport.read_api(f'releases/{release["id"]}'),TAG,head)
    assets={a['name']:a for a in current['assets']}
    require(set(assets)=={full.name,'manifest.json'},'archive asset census differs')
    for path in (full,OUT/'manifest.json'):
        item=assets[path.name]
        require(item['state']=='uploaded' and item['size']==path.stat().st_size
            and item['digest']=='sha256:'+digest(path),'uploaded recovery archive digest differs')
    receipt=dict(manifest,assets=[{k:a[k] for k in ('id','name','size','digest','state')} for a in current['assets']],
        published=False,full_payloads_downloaded_locally=False,all_source_zip_bytes_preserved=True)
    (OUT/'compact.json').write_bytes(encoded(receipt))
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('entries','assets')}))


if __name__=='__main__':main()
