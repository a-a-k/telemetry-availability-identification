"""Paired revised telemetry-to-first-answer costs; all extra checks follow timing."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import benchmark_v3_pipeline_v1 as fixed
from benchmark_v3_pipeline_v1 import read,write,file_sha,timed,command_ok,signatures,check_forecasts,require,ROOT
from v4_confirmed_source_v3 import require_source,SOURCE_RUN,SOURCE_HEAD

CONFIG=Path('configs/v4_pipeline_benchmark_v1.json')
PMX=[sys.executable,'-m','telemetry_availability.v3_comparison_pmx_v3']
GRAPH=[sys.executable,'-m','telemetry_availability.v4_confirmation_candidates_v1']


def first_forecasts(prepared,raw):
    """Serialize a first answer; repeat/control qualification is explicitly deferred."""
    from telemetry_availability.pmx_pmf_bridge import qualify
    models={m['model_id']for m in prepared['models']}
    require(len(raw)==len(models) and {r['model_id']for r in raw}==models
        and all(r['repetition']==0 and qualify(r,None)['valid_probability']for r in raw),'incomplete/invalid first Palladio answers')
    indexed={r['model_id']:r for r in raw};forecasts={}
    require(len(prepared['extractions'])==1,'first answer must contain exactly one application extraction')
    for case in prepared['extractions'][0]['cases']:
        operation=case['case_id'].split('--',1)[1];forecasts[operation]={}
        for variant,method in [('conditional_local','PMX'),('inclusive','PMX_inclusive')]:
            mid=case['case_id']+'--'+variant
            if mid in indexed:forecast=dict(status='ok',probability=indexed[mid]['success_probability'],reason=None)
            else:
                decision=next((v for v in case['variants']if v['variant']==variant),{})
                reason=decision.get('status',case.get('error','extraction_unavailable'))
                require(reason=='unsupported_conditional_propagation_or_positivity','unexplained missing application model')
                forecast=dict(status='unsupported',probability=None,reason=reason)
            forecasts[operation][method]=forecast
    return dict(forecasts=forecasts,extra_verification_complete=False)


def verify_locks():
    config=read(CONFIG)
    for lock in config['repository_locks']:
        require(file_sha(lock['path'])==lock['sha256'],'declared measurement source changed: '+lock['path'])
    return config


def prepare(profile):
    from telemetry_availability.v3_ordinary_identity_v2 import load_bundle
    from telemetry_availability.v3_comparison_roles_v1 import load_role,seal_role,write_ordinary
    config=verify_locks();source_status=require_source();source=config['applications'][profile]
    ordinary_root=fixed.download(source['ordinary'],ROOT/'source/ordinary')
    pmx_root=fixed.download(source['pmx'],ROOT/'source/pmx')
    ordinary,_=load_bundle(ordinary_root);pmx,_=load_role(pmx_root,'pmx_calibration')
    require(ordinary['requests.json']==pmx['requests.json'],'different input request populations')
    require(ordinary['manifest.json']['identity']==source['identity'],'source identity differs')
    require(file_sha(ordinary_root/'seal.json')==source['ordinary_seal_sha256']
        and file_sha(pmx_root/'seal.json')==source['pmx_seal_sha256'],'original role seals differ')
    for multiplier in config['multipliers']:
        target=ROOT/'inputs'/f'x{multiplier}'
        identity=dict(source['identity'],namespace=f'v4-computational-benchmark-v1-x{multiplier}',data_role='artificial_control')
        data=deepcopy(ordinary)
        data['requests.json'],data['native.json']=fixed.replicate(ordinary['requests.json'],ordinary['native.json'],multiplier,profile)
        data['manifest.json'].update(identity=identity,data_role='artificial_control',external_attempts=len(data['requests.json']))
        write_ordinary(target/'ordinary',data);del data
        data=deepcopy(pmx)
        data['requests.json'],data['native.json']=fixed.replicate(pmx['requests.json'],pmx['native.json'],multiplier,profile)
        data['manifest.json'].update(identity=identity,computational_replication=multiplier)
        seal_role(target/'pmx','pmx_calibration',identity,data)
        count=len(data['requests.json']);spans=sum(len(v)for v in data['native.json']['spans'].values());del data
        settings=read('configs/v4_confirmation_execution_v1.json')
        for spec in settings['profiles'][profile]['operations'].values():spec['expected_attempts']*=multiplier
        write(target/'execution.json',settings)
        write(target/'workload.json',dict(multiplier=multiplier,attempts=count,native_spans=spans,
            probe_observations=len(ordinary['probes.json']),source_identity=source['identity'],independent_new_observations=0,identity=identity,
            files={p.relative_to(target).as_posix():dict(bytes=p.stat().st_size,sha256=file_sha(p))for p in target.rglob('*')if p.is_file()}))
    write(ROOT/'compact/protocol.json',config)
    write(ROOT/'compact/environment.json',dict(profile=profile,workflow_head=os.environ['GITHUB_SHA'],
        scientific_head=SOURCE_HEAD,workflow_run=os.environ['GITHUB_RUN_ID'],python=sys.version,platform=platform.platform(),
        cpu_count=os.cpu_count(),cpu_info=Path('/proc/cpuinfo').read_text(),memory_info=Path('/proc/meminfo').read_text(),
        source_artifacts={k:source[k]for k in ('ordinary','pmx')},source_admission=source_status,
        source_models_previously_opened=True,extra_checks_after_all_measurement_streams=True))


def palladio(contract,result_dir,env,passes,prefix):
    result_dir.mkdir(parents=True,exist_ok=False)
    prepared=read(contract/'solver-contract.json')
    solver_env=dict(env,TAID_PALLADIO_ALIGNED_ROOT=str((contract/'models').resolve()),
        TAID_PALLADIO_RESULT=str((result_dir/'raw-result.json').resolve()),TAID_REPEAT_RUNS=str(passes),
        TAID_EXPECTED_MODEL_COUNT=str(prepared['model_count']),TAID_EXPECTED_CASE_COUNT=str(prepared['model_count']),
        TAID_PROBABILITY_TOLERANCE='1e-12')
    return timed(['xvfb-run','-a','mvn','-B','-ntp','-Dmaven.repo.local='+os.environ['PETCLINIC_PMX_MAVEN_REPO'],
        '-f','palladio-source/pom.xml','verify'],prefix,solver_env)


def graph_trial(target,inputs,env):
    tick=time.perf_counter()
    stage=timed(GRAPH+['build','--input',inputs/'ordinary','--output',target/'graph','--config',inputs/'execution.json'],target/'graph-build',env)
    command_ok(stage)
    return dict(wall_seconds=time.perf_counter()-tick,stages=dict(build=stage))


def pmx_trial(target,inputs,env,profile):
    tick=time.perf_counter();stages={}
    pmx_env=dict(env,JAVA_HOME=os.environ['PMX_JAVA_HOME'],PATH=os.environ['PMX_JAVA_HOME']+'/bin'+os.pathsep+env['PATH'])
    stages['extract']=timed(PMX+['extract','--source',inputs/'pmx','--out',target/'extractions/application',
        '--config',inputs/'execution.json','--options','workflow-input/Options.txt','--jar','workflow-input/pmx-clock-build/main-clock-progress-v1.jar'],target/'pmx-extract',pmx_env)
    command_ok(stages['extract'])
    stages['collect']=timed(PMX+['collect','--source',target/'extractions','--out',target/'pmx-contract','--profile',profile],target/'pmx-collect',env)
    command_ok(stages['collect'])
    stages['solve']=palladio(target/'pmx-contract',target/'pmx-first',env,1,target/'pmx-solve');command_ok(stages['solve'])
    stages['save']=timed([sys.executable,__file__,'save-first','--target',target],target/'pmx-save',env);command_ok(stages['save'])
    return dict(wall_seconds=time.perf_counter()-tick,stages=stages)


def verify_trial(row,target,inputs,env,config,profile,controls,control_raw):
    from telemetry_availability.v3_comparison_pmx_v3 import solver_forecasts
    stages={}
    stages['graph_replay']=timed(GRAPH+['replay','--input',target/'graph/candidates','--output',target/'graph/replay',
        '--config',inputs/'execution.json'],target/'verification/graph-replay',env);command_ok(stages['graph_replay'])
    stages['pmx_repeat']=palladio(target/'pmx-contract',target/'pmx-repeat',env,1,target/'verification/pmx-repeat');command_ok(stages['pmx_repeat'])
    prepared=read(target/'pmx-contract/solver-contract.json')
    combined=dict(prepared,models=prepared['models']+controls['models'],extractions=prepared['extractions']+controls['extractions'])
    first=read(target/'pmx-first/raw-result.json')['runs'];second=read(target/'pmx-repeat/raw-result.json')['runs']
    raw=first+[dict(r,repetition=1)for r in second]+control_raw
    candidates,qualification=solver_forecasts(combined,raw)
    require(qualification['qualified'] and len(candidates)==1,'independent repeat/control qualification failed')
    graph=read(target/'graph/candidates/candidates.json');pmx=read(target/'pmx-first/candidates.json')
    for key,value in [('graph',graph),('pmx',pmx)]:
        row[key]['forecasts']=signatures(value['forecasts'])
        check_forecasts(row[key]['forecasts'],config['applications'][profile]['expected'][key])
    check_forecasts(row['pmx']['forecasts'],signatures(candidates[0]['forecasts']))
    models=read(target/'graph/candidates/models.json')['execution']
    row['graph']['model_structure']={op:dict(nodes=len(m['graph']['services']),edges=len(m['graph']['edges']),
        coordinates=len(m['signal_ids']),categories=len(m['observation_categories']),samples=m['sample_count'])for op,m in models.items()}
    row['graph']['saved_candidate_sha256']=file_sha(target/'graph/candidates/candidates.json')
    row['pmx'].update(models=prepared['model_count'],controls_qualified=True,saved_candidate_sha256=file_sha(target/'pmx-first/candidates.json'),solver_records=first)
    row.update(status='qualified',original_forecasts_preserved=True,extra_verification_stages=stages,
        extra_verification_after_all_measurements=True,speedup_pmx_over_graph=row['pmx']['wall_seconds']/row['graph']['wall_seconds'])
    write(target/'verification/qualification.json',dict(controls=qualification,repeat_reindexed_from_separate_one_pass_process=True,
        first_raw_sha256=file_sha(target/'pmx-first/raw-result.json'),repeat_raw_sha256=file_sha(target/'pmx-repeat/raw-result.json'),
        reference_frozen_candidates_sha256=config['applications'][profile]['frozen_candidates_sha256']))


def run(profile):
    config=verify_locks();env=dict(os.environ)
    results=dict(version=config['version'],profile=profile,workflow_head=os.environ['GITHUB_SHA'],run_id=int(os.environ['GITHUB_RUN_ID']),
        config_sha256=file_sha(CONFIG),scientific_head=SOURCE_HEAD,new_independent_campaigns=0,records=[])
    for repetition,order in enumerate(config['scale_orders']):
        for multiplier in order:
            inputs=ROOT/'inputs'/f'x{multiplier}';target=ROOT/'trials'/f'r{repetition}-x{multiplier}';target.mkdir(parents=True)
            methods=['graph','pmx']if (repetition+config['multipliers'].index(multiplier))%2==0 else ['pmx','graph']
            row=dict(repetition=repetition,multiplier=multiplier,method_order=methods,workload=read(inputs/'workload.json'),status='running')
            try:
                for method in methods:
                    print(json.dumps(dict(stage='measurement',profile=profile,repetition=repetition,multiplier=multiplier,method=method)),flush=True)
                    row[method]=graph_trial(target,inputs,env)if method=='graph'else pmx_trial(target,inputs,env,profile)
                row['status']='measured_awaiting_independent_checks'
            except Exception as exc:row.update(status='failed',error=type(exc).__name__+': '+str(exc))
            results['records'].append(row);write(ROOT/'compact/results.json',results)
    # No model replay, reference-forecast comparison or known-probability control
    # is executed until every planned measurement process has exited.
    control_stage=palladio(ROOT/'controls/contract',ROOT/'controls/solver',env,2,ROOT/'controls/verify')
    results['control_verification']=control_stage;command_ok(control_stage)
    controls=read(ROOT/'controls/contract/solver-contract.json');control_raw=read(ROOT/'controls/solver/raw-result.json')['runs']
    for row in results['records']:
        if row['status']=='failed':continue
        target=ROOT/'trials'/f"r{row['repetition']}-x{row['multiplier']}";inputs=ROOT/'inputs'/f"x{row['multiplier']}"
        try:verify_trial(row,target,inputs,env,config,profile,controls,control_raw)
        except Exception as exc:row.update(status='failed',error=type(exc).__name__+': '+str(exc))
        write(ROOT/'compact/results.json',results)
    require(all(r['status']=='qualified'for r in results['records']),'a paired trial failed; all original measurements retained')


def main():
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1','remote first attempt required')
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run','save-first']);p.add_argument('--profile');p.add_argument('--target',type=Path)
    args=p.parse_args()
    if args.mode=='save-first':
        target=args.target
        write(target/'pmx-first/candidates.json',first_forecasts(read(target/'pmx-contract/solver-contract.json'),read(target/'pmx-first/raw-result.json')['runs']))
    else:
        require(args.profile in read(CONFIG)['applications'],'unplanned application')
        (prepare if args.mode=='prepare'else run)(args.profile)


if __name__=='__main__':main()
