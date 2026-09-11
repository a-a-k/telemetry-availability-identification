"""Remote-only fixed comparative experiment; oracle qualification follows timing."""
import argparse
from hashlib import sha256
from itertools import product
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from telemetry_availability.exact_comparison_v2 import METHODS,REPRESENTATIONS,PHASES,Direct,Prepared,project,snapshots,semantic_key
from telemetry_availability.graph_execution_model_v1 import solve,validate
import benchmark_v3_exact_backends_v1 as source_v1

CONFIG=ROOT/'configs/v3_exact_comparison_v2.json'
encoded=source_v1.encoded
digest=source_v1.digest
write=source_v1.write
require=source_v1.require


def backend(name):
    if name=='ours_direct':return Direct()
    if name=='ours_prepared':return Prepared()
    if name.startswith('cudd_'):
        from telemetry_availability.cudd_comparison_v2 import Cudd
        return Cudd(sift=name=='cudd_sift')
    if name.startswith('agrum_'):
        from telemetry_availability.agrum_comparison_v2 import Agrum
        return Agrum(joint=name=='agrum_joint')
    if name.startswith('storm_'):
        from telemetry_availability.storm_comparison_v2 import Storm
        return Storm(compact=name=='storm_compact')
    raise ValueError('unknown backend')


def controls():
    from test_graph_execution_bdd_v1 import tiny_model
    for name,representation in product(METHODS,REPRESENTATIONS):
        obj=backend(name);key=None
        for phase,raw in snapshots(tiny_model()):
            model=project(raw,representation);validate(model);new=semantic_key(model)
            if new!=key:obj.rebuild(model);key=new
            actual=obj.query(model)
            require(actual==solve(raw)['estimates'],f'control mismatch {name}/{representation}/{phase}')
        require(obj.builds==3,'wrong semantic rebuild count')
        print('native control passed: '+name+'/'+representation,flush=True)


def worker(args,config):
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(config['address_space_limit_bytes'],config['address_space_limit_bytes']))
    if args.method.startswith('cudd_'):
        import dd.cudd
        import telemetry_availability.cudd_comparison_v2
    elif args.method.startswith('agrum_'):
        import pyagrum
        import telemetry_availability.agrum_comparison_v2
    elif args.method.startswith('storm_'):
        import stormpy
        import telemetry_availability.storm_comparison_v2
    case=json.loads(args.input.read_text());obj=None;key=None;broken=False
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'records.jsonl').open('w') as stream:
        for phase,raw in snapshots(case['model']):
            record=dict(case_id=case['case_id'],method=args.method,representation=args.representation,round=args.round,phase=phase,status='failed')
            try:
                if broken:raise RuntimeError('upstream_failure: stream infrastructure cannot safely be reused')
                cpu=time.process_time_ns();started=time.perf_counter_ns()
                tick=time.perf_counter_ns();model=project(raw,args.representation);conversion_ns=time.perf_counter_ns()-tick
                tick=time.perf_counter_ns();new_key=semantic_key(model);rebuild=new_key!=key;check_ns=time.perf_counter_ns()-tick
                tick=time.perf_counter_ns()
                if rebuild:
                    if obj is None:obj=backend(args.method)
                    obj.rebuild(model);key=new_key
                build_ns=time.perf_counter_ns()-tick if rebuild else 0
                tick=time.perf_counter_ns();actual=obj.query(model);query_ns=time.perf_counter_ns()-tick
                total_ns=time.perf_counter_ns()-started;cpu_ns=time.process_time_ns()-cpu
                # Only read cached answers/diagnostics below. No oracle or native inference.
                stats=dict(obj.stats)
                if hasattr(obj,'diagnostics'):stats.update(obj.diagnostics())
                record.update(status='measured',total_ns=total_ns,kernel_ns=total_ns-conversion_ns,cpu_ns=cpu_ns,
                    conversion_ns=conversion_ns,key_check_ns=check_ns,construction_ns=build_ns,
                    update_ns=getattr(obj,'last_update_ns',0),query_including_update_ns=query_ns,
                    reconstructed=rebuild,estimates=actual,semantic_key_sha256=sha256(new_key).hexdigest(),stats=stats,
                    input_coordinates=len(model['signal_ids']),input_categories=len(model['observation_categories']))
                if hasattr(obj,'cells'):record['verification_cells']=list(obj.cells)
            except Exception as exc:
                broken=True;record['error']=type(exc).__name__+': '+str(exc)
            stream.write(json.dumps(record,allow_nan=False)+'\n');stream.flush()


def run(args,config):
    args.out.mkdir(parents=True,exist_ok=False);compact=args.out/'compact';compact.mkdir()
    (compact/'protocol.json').write_bytes(CONFIG.read_bytes())
    import dd,dd.cudd,pyagrum,stormpy
    environment=dict(run_id=int(os.environ['GITHUB_RUN_ID']),head=os.environ['GITHUB_SHA'],profile=args.profile,
        config_sha256=sha256(CONFIG.read_bytes()).hexdigest(),python=sys.version,platform=platform.platform(),
        cpu_info=Path('/proc/cpuinfo').read_text(),memory_info=Path('/proc/meminfo').read_text(),cpu_count=os.cpu_count(),
        versions=dict(dd=dd.__version__,cudd=getattr(dd.cudd,'__version__',None),pyagrum=pyagrum.__version__,stormpy=stormpy.__version__),
        packages=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    write(compact/'environment.json',environment)
    # Parent-only source integrity/validation. Workers receive neither references nor certificates.
    rows,absent,source=source_v1.prepare(args.profile,config)
    result=dict(version=config['version'],run_id=environment['run_id'],head=environment['head'],profile=args.profile,
        config_sha256=environment['config_sha256'],source=source,cases=[],absent=absent,records=[],resources=[],qualified=False,
        new_campaigns=0,full_telemetry_reconstruction_measured=False,verification_order='after_all_profile_streams')
    for case in rows:
        m=case['model'];result['cases'].append(dict(case_id=case['case_id'],model_sha256=digest(m),nodes=len(m['graph']['services']),
            edges=len(m['graph']['edges']),coordinates=len(m['signal_ids']),categories=len(m['observation_categories']),
            axis=case['axis'],parameters=case['parameters']))
        write(args.out/'inputs'/(sha256(case['case_id'].encode()).hexdigest()[:20]+'.json'),dict(case_id=case['case_id'],model=m))
    write(compact/'results.json',result)
    combinations=list(product(config['methods'],config['representations']))
    for repetition in range(config['technical_rounds']):
        for ordinal,case in enumerate(rows):
            case_key=sha256(case['case_id'].encode()).hexdigest()[:20]
            offset=(ordinal+repetition)%len(combinations);order=combinations[offset:]+combinations[:offset]
            for method,representation in order:
                dest=args.out/'workers'/f'r{repetition}'/case_key/method/representation;dest.mkdir(parents=True)
                command=['/usr/bin/time','-f','%e %U %S %M %x','-o',str(dest/'resource.txt'),sys.executable,
                    str(Path(__file__).resolve()),'worker','--input',str(args.out/'inputs'/(case_key+'.json')),
                    '--method',method,'--representation',representation,'--round',str(repetition),'--out',str(dest)]
                with (dest/'console.txt').open('w') as log:
                    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:code=process.wait(timeout=config['stream_timeout_seconds']);timed_out=False
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);code=process.wait();timed_out=True
                resource=dict(case_id=case['case_id'],method=method,representation=representation,round=repetition,returncode=code,timed_out=timed_out)
                text=(dest/'resource.txt').read_text().strip() if (dest/'resource.txt').exists() else ''
                fields=text.splitlines()[-1].split() if text else []
                if len(fields)==5:
                    resource.update(wall_seconds=float(fields[0]),user_seconds=float(fields[1]),system_seconds=float(fields[2]),
                        peak_rss_kib=int(fields[3]),exit_code=int(fields[4]))
                result['resources'].append(resource)
                records=[json.loads(line) for line in (dest/'records.jsonl').read_text().splitlines()] if (dest/'records.jsonl').exists() else []
                by_phase={r['phase']:r for r in records};require(len(by_phase)==len(records),'duplicate stream phase')
                for phase in config['phases']:
                    result['records'].append(by_phase.get(phase,dict(case_id=case['case_id'],method=method,representation=representation,
                        round=repetition,phase=phase,status='failed',error='stream_timeout' if timed_out else 'worker_exit_'+str(code))))
            if ordinal%5==0:
                # Full temporary checkpoint may contain BN cells; compact is emitted only after verification.
                write(args.out/'checkpoint.json',result)
                print(json.dumps(dict(profile=args.profile,round=repetition,case=ordinal+1,total=len(rows),
                    failures=sum(r['status']=='failed' for r in result['records']))),flush=True)
    # Disjoint verification pass in the parent, after every timed stream has exited.
    expected={}
    for case,summary in zip(rows,result['cases']):
        expected[case['case_id']]={}
        for phase,raw in snapshots(case['model']):
            validate(raw);reference=solve(raw)['estimates']
            for representation in config['representations']:
                converted=project(raw,representation);validate(converted)
                require(solve(converted)['estimates']==reference,'common projection mismatch')
            expected[case['case_id']][phase]=reference
        summary['expected']=expected[case['case_id']]
    for record in result['records']:
        cells=record.pop('verification_cells',None)
        if cells is not None:
            record['posterior_cells_valid']=all(math.isfinite(a) and math.isfinite(b) and a>=0 and b>=0 and 0<a+b<=1+1e-12 for a,b in cells)
        if record['status']=='measured':
            if record['estimates']!=expected[record['case_id']][record['phase']]:record.update(status='failed',error='exact endpoint/status mismatch')
            elif record.get('posterior_cells_valid',True) is not True:record.update(status='failed',error='invalid posterior cells')
            else:record['status']='qualified'
    result['qualified']=all(r['status']=='qualified' for r in result['records'])
    result['complete_census']=len(result['records'])==len(rows)*len(combinations)*len(config['phases'])*config['technical_rounds']
    write(compact/'results.json',result);require(result['complete_census'],'incomplete experiment census')
    print(json.dumps(dict(profile=args.profile,qualified=result['qualified'],records=len(result['records']),
        failed=sum(r['status']=='failed' for r in result['records']))),flush=True)


def main():
    require(os.environ.get('GITHUB_ACTIONS')=='true','native backends and application execution are remote only')
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['controls','run','worker'])
    parser.add_argument('--profile');parser.add_argument('--out',type=Path);parser.add_argument('--input',type=Path)
    parser.add_argument('--method',choices=METHODS);parser.add_argument('--representation',choices=REPRESENTATIONS);parser.add_argument('--round',type=int)
    args=parser.parse_args();config=json.loads(CONFIG.read_text())
    require(tuple(config['methods'])==METHODS and tuple(config['representations'])==REPRESENTATIONS and tuple(config['phases'])==PHASES,'config/code differ')
    if args.mode=='controls':controls()
    elif args.mode=='worker':worker(args,config)
    else:run(args,config)


if __name__=='__main__':main()
