"""Remote workflow experiment: symmetric preparation, exact BN and exact Storm."""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path,PurePosixPath
import platform
import signal
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from telemetry_availability.exact_backend_common_v1 import updates,semantic_key
from telemetry_availability.graph_execution_model_v1 import solve
from telemetry_availability.prepared_exact_v1 import PreparedSpecialized,PreparedCUDD
import retain_v3_comparison_compact_v4 as transport

CONFIG=ROOT/'configs/v3_exact_backends_v1.json'
def encoded(value):return (json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode()
def digest(value):return sha256(encoded(value)).hexdigest()
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(encoded(value))
def require(value,message):
    if not value:raise ValueError(message)


def backend(name,model):
    if name=='prepared_specialized':return PreparedSpecialized(model)
    if name.startswith('cudd_'):return PreparedCUDD(model,name.removeprefix('cudd_'))
    if name=='agrum_lazy':
        from telemetry_availability.agrum_exact_v1 import AgrumExact
        return AgrumExact(model)
    if name=='storm_exact':
        from telemetry_availability.storm_exact_v1 import StormExact
        return StormExact(model)
    raise ValueError('unknown method')


def native_controls():
    import traceback
    from test_graph_execution_bdd_v1 import tiny_model
    config=json.loads(CONFIG.read_text());original=tiny_model()
    failures=[]
    for method in config['methods']:
        try:
            obj=None;key=None
            for phase,model in updates(original):
                new_key=semantic_key(model)
                if new_key!=key:obj=backend(method,model);key=new_key
                actual=obj.query(model)
                require(actual==solve(model)['estimates'],f'native semantic control failed: {method}/{phase}')
            print('native control passed: '+method,flush=True)
        except Exception as exc:
            traceback.print_exc();failures.append(method+': '+str(exc))
    require(not failures,'native controls failed: '+str(failures))


def worker(args,config):
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(config['address_space_limit_bytes'],config['address_space_limit_bytes']))
    case=json.loads(args.input.read_text());obj=None;key=None
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'records.jsonl').open('w') as stream:
        for phase,model in updates(case['model']):
            record=dict(case_id=case['case_id'],method=args.method,round=args.round,phase=phase,status='failed')
            try:
                cpu=time.process_time_ns();started=time.perf_counter_ns()
                tick=time.perf_counter_ns();new_key=semantic_key(model);rebuild=new_key!=key;check_ns=time.perf_counter_ns()-tick
                tick=time.perf_counter_ns()
                if rebuild:obj=backend(args.method,model);key=new_key
                build_ns=time.perf_counter_ns()-tick if rebuild else 0
                tick=time.perf_counter_ns();actual=obj.query(model);query_ns=time.perf_counter_ns()-tick
                total_ns=time.perf_counter_ns()-started;cpu_ns=time.process_time_ns()-cpu
                require(actual==case['expected'][phase], 'exact endpoint/status mismatch')
                record.update(status='qualified',total_ns=total_ns,cpu_ns=cpu_ns,key_check_ns=check_ns,
                    construction_ns=build_ns,update_ns=round(getattr(obj,'last_update_seconds',0.0)*1e9),
                    query_including_update_ns=query_ns,reconstructed=rebuild,estimates=actual,
                    semantic_key_sha256=sha256(new_key).hexdigest(),stats=obj.stats)
                if args.method.startswith('cudd_'):
                    record['stats']=dict(obj.stats,native=obj.compiled.statistics())
            except Exception as exc:
                record['error']=type(exc).__name__+': '+str(exc)
                obj=None;key=None
            stream.write(json.dumps(record,allow_nan=False)+'\n');stream.flush()


def prepare(profile,config):
    item=config['source_artifacts'][profile];metadata=transport.read_api(f'actions/artifacts/{item["id"]}')
    require(metadata['workflow_run']['id']==config['source_run'] and metadata['workflow_run']['head_sha']==config['source_head']
            and metadata['name']==f'v3-bdd-full-{profile}-{config["source_run"]}' and not metadata['expired'],'wrong source artifact')
    raw=transport.api(f'actions/artifacts/{item["id"]}/zip')
    require(len(raw)==item['bytes']==metadata['size_in_bytes'] and sha256(raw).hexdigest()==item['sha256']
            and metadata['digest']=='sha256:'+item['sha256'],'source artifact size/hash differs')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names=archive.namelist()
        require(len(names)==len(set(names)) and archive.testzip() is None
                and all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names),'invalid ZIP')
        rows=json.loads(archive.read('full-inputs.json'))
        compact=json.loads(archive.read('compact/results.json'))
    selected=[r for r in rows if profile=='synthetic' or r['identity']['repetition']==0]
    absent=[r for r in compact['absent'] if r['identity']['repetition']==0]
    index=config['profiles'].index(profile)
    require(len(selected)==config['expected_models'][index] and len(absent)==config['expected_original_absences'][index],'panel census differs')
    selected.sort(key=lambda r:r['case_id'])
    for case in selected:
        case['expected']={phase:solve(model)['estimates'] for phase,model in updates(case['model'])}
        require(case['expected']['initial']==case['reference']['estimates'],'saved original predictions differ')
    return selected,absent,metadata


def run(args,config):
    args.out.mkdir(parents=True,exist_ok=False);compact=args.out/'compact';compact.mkdir()
    (compact/'protocol.json').write_bytes(CONFIG.read_bytes())
    import dd,dd.cudd,pyagrum,stormpy,stormpy.info
    environment=dict(run_id=int(os.environ['GITHUB_RUN_ID']),head=os.environ['GITHUB_SHA'],profile=args.profile,
        config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),python=sys.version,platform=platform.platform(),
        cpu_info=Path('/proc/cpuinfo').read_text(),memory_info=Path('/proc/meminfo').read_text(),cpu_count=os.cpu_count(),
        versions=dict(dd=dd.__version__,cudd=dd.cudd.__version__,pyagrum=pyagrum.__version__,stormpy=stormpy.__version__),
        packages=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    write(compact/'environment.json',environment)
    rows,absent,source=prepare(args.profile,config)
    result=dict(version=config['version'],run_id=environment['run_id'],head=environment['head'],profile=args.profile,
                config_sha256=environment['config_sha256'],source=source,cases=[],absent=absent,records=[],resources=[],qualified=False,
                new_campaigns=0,full_telemetry_reconstruction_measured=False)
    for case in rows:
        m=case['model'];result['cases'].append(dict(case_id=case['case_id'],model_sha256=digest(m),
            nodes=len(m['graph']['services']),edges=len(m['graph']['edges']),coordinates=len(m['signal_ids']),
            categories=len(m['observation_categories']),axis=case['axis'],parameters=case['parameters'],expected=case['expected']))
        write(args.out/'inputs'/(sha256(case['case_id'].encode()).hexdigest()[:20]+'.json'),case)
    write(compact/'results.json',result)
    for repetition in range(config['technical_rounds']):
        for ordinal,case in enumerate(rows):
            case_key=sha256(case['case_id'].encode()).hexdigest()[:20]
            offset=(ordinal+repetition)%len(config['methods']);methods=config['methods'][offset:]+config['methods'][:offset]
            for method in methods:
                dest=args.out/'workers'/f'r{repetition}'/case_key/method;dest.mkdir(parents=True)
                command=['/usr/bin/time','-f','%e %U %S %M %x','-o',str(dest/'resource.txt'),sys.executable,
                    str(Path(__file__).resolve()),'worker','--input',str(args.out/'inputs'/(case_key+'.json')),
                    '--method',method,'--round',str(repetition),'--out',str(dest)]
                with (dest/'console.txt').open('w') as log:
                    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:code=process.wait(timeout=config['stream_timeout_seconds']);timed_out=False
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);code=process.wait();timed_out=True
                resource=dict(case_id=case['case_id'],method=method,round=repetition,returncode=code,timed_out=timed_out)
                text=(dest/'resource.txt').read_text().strip() if (dest/'resource.txt').exists() else ''
                fields=text.splitlines()[-1].split() if text else []
                if len(fields)==5:
                    resource.update(wall_seconds=float(fields[0]),user_seconds=float(fields[1]),system_seconds=float(fields[2]),
                                    peak_rss_kib=int(fields[3]),exit_code=int(fields[4]))
                result['resources'].append(resource)
                records=[json.loads(line) for line in (dest/'records.jsonl').read_text().splitlines()] if (dest/'records.jsonl').exists() else []
                by_phase={r['phase']:r for r in records};require(len(by_phase)==len(records),'duplicate stream phase')
                for phase in config['phases']:
                    result['records'].append(by_phase.get(phase,dict(case_id=case['case_id'],method=method,round=repetition,
                        phase=phase,status='failed',error='stream_timeout' if timed_out else 'worker_exit_'+str(code))))
            if ordinal%5==0:
                write(compact/'results.json',result)
                print(json.dumps(dict(profile=args.profile,round=repetition,case=ordinal+1,total=len(rows),
                    failures=sum(r['status']!='qualified' for r in result['records']))),flush=True)
    result['qualified']=all(r['status']=='qualified' for r in result['records'])
    result['complete_census']=len(result['records'])==len(rows)*len(config['methods'])*len(config['phases'])*config['technical_rounds']
    write(compact/'results.json',result)
    require(result['complete_census'],'incomplete experiment census')
    print(json.dumps(dict(profile=args.profile,qualified=result['qualified'],records=len(result['records']),
                         failed=sum(r['status']=='failed' for r in result['records']))),flush=True)


def main():
    require(os.environ.get('GITHUB_ACTIONS')=='true','native backends and application execution are remote only')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['controls','run','worker'])
    parser.add_argument('--profile');parser.add_argument('--out',type=Path);parser.add_argument('--input',type=Path)
    parser.add_argument('--method');parser.add_argument('--round',type=int)
    args=parser.parse_args();config=json.loads(CONFIG.read_text())
    if args.mode=='controls':native_controls()
    elif args.mode=='worker':worker(args,config)
    else:run(args,config)


if __name__=='__main__':main()
