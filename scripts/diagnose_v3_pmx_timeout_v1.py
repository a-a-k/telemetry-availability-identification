"""Remote diagnostic of one retained PMX timeout; never admits main or reads test."""
from collections import Counter
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import zipfile

from telemetry_availability.pmx_application_comparison import run_application_pmx
from telemetry_availability.pmx_adapter_conformance import JAR_SHA

REPO='a-a-k/telemetry-availability-identification'
RUN=34447262633
HEAD='e89e7ca91dd474d8cf2b8c4ed7c1ffc052d98569'
ARTIFACT=10142302472
ARTIFACT_NAME='v3-comparison-pmx-extraction-deathstarbench_social_network--split--NCD--r0-34447262633'
ARTIFACT_BYTES=5865357
ARTIFACT_SHA='9923484e5becacd136f83f651bd2fbbbaa362e8b1d76d2a167bf5c520dc72f87'
CASE='campaign-4d578f947be720d0e912--read_user_timeline'
OUT=Path('workflow-results/pmx-timeout-diagnostic')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode())


def api(path):
    return subprocess.check_output(['gh','api',f'repos/{REPO}/'+path])


def log_summary(raw):
    text=raw.decode('utf-8',errors='replace');lines=text.splitlines()
    selected=[]
    for line in lines:
        if re.search(r'ERROR|Exception|Caused by:|Command not found|[Pp]ress|[Cc]onsole|osgi>|^g!|^\s+at\s',line):
            # Exclude native data and preserve only bounded diagnostic text.
            if any(token in line for token in ('"traceID"','"spanID"','"tags"','{"','[{')):continue
            clean=re.sub(r'\b[0-9a-fA-F]{12,}\b','<hex-id>',line)
            selected.append(clean[:700])
    return dict(bytes=len(raw),sha256=sha256(raw).hexdigest(),lines=len(lines),
        diagnostic_lines=selected[-50:],diagnostic_lines_total=len(selected),
        marker_counts={marker:text.count(marker) for marker in ('ERROR','Exception','StackOverflowError','OutOfMemoryError','main:main','Command not found','g!','Reconstruct','extracted.repository')})


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    run=json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha']==HEAD and run['run_attempt']==1 and run['status']=='completed'
    meta=json.loads(api(f'actions/artifacts/{ARTIFACT}'))
    assert meta['name']==ARTIFACT_NAME and meta['size_in_bytes']==ARTIFACT_BYTES and meta['digest']=='sha256:'+ARTIFACT_SHA and not meta['expired']
    data=api(f'actions/artifacts/{ARTIFACT}/zip')
    assert len(data)==ARTIFACT_BYTES and sha256(data).hexdigest()==ARTIFACT_SHA
    old_files={};source=OUT/'source';source.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names=archive.namelist();assert len(names)==len(set(names))
        assert all(not p.startswith('/') and '..' not in Path(p).parts for p in names)
        # Read only saved projection input, exact execution metadata and logs of the failed case.
        projection='projection/cases/'+CASE+'/'
        for info in archive.infolist():
            name=info.filename
            if name.startswith(projection) and not info.is_dir():
                assert info.file_size<80_000_000
                raw=archive.read(name);relative=name[len(projection):]
                path=source/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                old_files[relative]=dict(bytes=len(raw),sha256=sha256(raw).hexdigest())
        original_log=archive.read('raw/'+CASE+'/stdout.log')
        original_execution=json.loads(archive.read('raw/'+CASE+'/execution.json'))
        resources=archive.read('raw/'+CASE+'/resource-usage.txt').decode(errors='replace')
        record=json.loads(archive.read('extraction-campaign-4d578f947be720d0e912.json'))
    assert original_execution['exit_code']==124 and original_execution['internal_watchdog_seconds']==1800
    assert set(old_files)>={'Options.txt','traces/observed.json','expected.json','operation_oracle.json'}
    jar=Path('workflow-input/main.jar');assert sha256(jar.read_bytes()).hexdigest()==JAR_SHA
    result=dict(version='v3-pmx-timeout-diagnostic-v1',source_run=RUN,source_head=HEAD,
        diagnostic_head=os.environ['GITHUB_SHA'],diagnostic_run=os.environ['GITHUB_RUN_ID'],
        source_artifact=dict(id=ARTIFACT,name=ARTIFACT_NAME,bytes=ARTIFACT_BYTES,sha256=ARTIFACT_SHA),
        operation='read_user_timeline',application='deathstarbench_social_network',placement='split',
        original_execution=original_execution,original_log=log_summary(original_log),
        original_resource_usage=resources,projection_inputs=old_files,
        original_case=next({k:r.get(k) for k in ('case_id','qualified','error','execution','variants')} for r in record['cases'] if r['case_id']==CASE),
        diagnostic_watchdog_seconds=120,diagnostic_is_not_qualification=True,
        native_calibration_projection_unchanged=True,evaluator_inputs_read=0,new_independent_campaigns=0)
    write(OUT/'compact.json',result)
    stop=threading.Event();snapshots=[]
    def watch():
        if stop.wait(55):return
        listing=subprocess.run(['jcmd','-l'],capture_output=True,text=True,timeout=15)
        for line in listing.stdout.splitlines():
            if str(jar.resolve()) not in line:continue
            pid=line.split()[0]
            dump=subprocess.run(['jcmd',pid,'Thread.print'],capture_output=True,text=True,timeout=15)
            (OUT/'thread-dump.txt').write_bytes(dump.stdout.encode())
            snapshots.append(dict(thread_state_counts=dict(Counter(re.findall(r'java.lang.Thread.State: ([A-Z_]+)',dump.stdout))),
                frame_counts=dict(Counter(re.findall(r'^\s+at ([A-Za-z0-9_.$/]+)\(',dump.stdout,re.M))),
                sha256=sha256(dump.stdout.encode()).hexdigest()))
    watcher=threading.Thread(target=watch,daemon=True);watcher.start()
    try:
        result['exact_input_replay']=run_application_pmx(jar,source,OUT/'replay',limit=120)
    except Exception as error:
        result['exact_input_replay']=dict(status='exception',error=type(error).__name__+': '+str(error))
    finally:
        stop.set();watcher.join(timeout=35)
    result['thread_snapshots']=snapshots
    replay_log=OUT/'replay/stdout.log'
    if replay_log.exists():result['replay_log']=log_summary(replay_log.read_bytes())
    result['replay_result_files']=[dict(name=p.name,bytes=p.stat().st_size,sha256=sha256(p.read_bytes()).hexdigest()) for p in sorted((OUT/'replay/results').glob('*')) if p.is_file()]
    result['input_hashes_unchanged']=all(sha256((source/name).read_bytes()).hexdigest()==row['sha256'] for name,row in old_files.items())
    assert result['input_hashes_unchanged']
    write(OUT/'compact.json',result)
    print(json.dumps({k:result[k] for k in ('source_run','source_head','diagnostic_run','exact_input_replay','input_hashes_unchanged','new_independent_campaigns')}))


if __name__=='__main__':main()
