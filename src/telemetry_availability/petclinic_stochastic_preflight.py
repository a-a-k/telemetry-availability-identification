"""Eight remote technical Petclinic conditions with separate learner/test artifacts."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from .live_evidence import (LEARNER_REQUEST_FIELDS, EVALUATOR_REQUEST_FIELDS, LEARNER_HEALTH_FIELDS,
    TOPOLOGY_EDGE_FIELDS, SpanRecord, _pivot_health, _topology_rows)
from .live_fault_campaign import _service_containers, _sleep_until
from .live_pilot_config import RuntimePilotProfile
from .live_placement_config import PlacementPilotProfile
from .live_stochastic_pilot import (_health_sampler, _stochastic_fault_controller, _operation_order, _stable_seed,
    _utc_now, _format_time, plan_renewal_events, factor_definitions, renewal_schedule_seed)
from .live_validation_config import load_frozen_live_validation_config
from .petclinic_contract_v2 import adapt_fixture, execute, finalize_write
from .petclinic_runtime_v3 import compose, command, db_records, digest, write
from .pmx_observed_operations import read_native
from .runner import _write_csv

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'configs/petclinic_stochastic_preflight.json'
PROFILE = 'spring_petclinic_microservices'


def config_objects():
    selected = json.loads(CONFIG.read_text())
    acceptance=selected['accepted_runtime']
    assert digest(ROOT/acceptance['summary_file'])==acceptance['summary_sha256']
    qualified=json.loads((ROOT/acceptance['summary_file']).read_text())
    assert qualified['qualified'] and all(qualified['checks'].values())
    assert qualified['study_head']==acceptance['head_sha'] and qualified['run_id']==str(acceptance['run_id'])
    for relative,expected in selected.get('repository_locks',{}).items():
        assert digest(ROOT/relative)==expected,relative
    runtime_config = json.loads((ROOT/selected['runtime_config']).read_text())
    old = load_frozen_live_validation_config(ROOT/selected['source_renewal_config']).stochastic
    profile = PlacementPilotProfile(PROFILE,'visits-service',8080,'http','owner_details_with_visits')
    runtime = RuntimePilotProfile(PROFILE,runtime_config['source_repository'],runtime_config['source_commit'],
        'compose.json','http://localhost:18080','/actuator/health','otlp_jsonl_v1','traces/native.jsonl',
        tuple(runtime_config['operations']),(),{})
    placement = replace(old.placement, profiles=(profile,),
        runtime=replace(old.placement.runtime,profiles=(runtime,)),proxy_stats_port=8404)
    config = replace(old,id=selected['stage'],pilot_only=True,placement=placement,pilot_repetitions=1,
        baseline_seconds=selected['baseline_seconds'],period_seconds=selected['calibration_seconds'],
        request_rate_per_second=selected['request_rate_per_second'],request_workers=selected['request_workers'],
        pilot_base_seed=selected['base_seed'],main_base_seed=selected['base_seed'])
    assert selected['calibration_seconds']==selected['test_seconds']==900
    assert selected['expected_campaigns']==8 and selected['expected_operation_cells']==32
    return selected,runtime_config,config,profile,runtime


def seal(root, metadata):
    files={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file() and p.name!='seal.json'}
    write(root/'seal.json',dict(metadata=metadata,files=files))


def request(config,runtime_config,profile,runtime,identity,period,index,operation,offset,namespace,fixture):
    request_id=f'{namespace}-{period}-{index:06d}-{operation}'
    row=execute(runtime.base_url,operation,request_id,fixture,runtime_config)
    row.update(identity,period=period,branch_class='complete_'+operation,scheduled_offset_seconds=offset,
        started_at=datetime.fromtimestamp(row['started_epoch'],timezone.utc).isoformat(),
        completed_at=datetime.fromtimestamp(row['completed_epoch'],timezone.utc).isoformat())
    return row


def period_run(config,runtime_config,profile,runtime,identity,period,duration,path,events,namespace,fixture):
    services=(*profile.replica_services.values(),profile.target_service)
    containers=_service_containers(path,services)
    # Preserve database and telemetry networks; only the application path is injected.
    networks={service:('petclinic-study-application',(service,)) for service in profile.replica_services.values()}
    seed=_stable_seed(config.pilot_base_seed,profile.id,identity['placement'],identity['failure_law'],0,period,'workload')
    operations=_operation_order(runtime,duration*config.request_rate_per_second,seed)
    health,event_rows=[],[]
    controller=dict(events=0,confirmed=0,released=0,active_pause_causes_at_end=0,active_network_causes_at_end=0,errors=[])
    started_at,started=_utc_now(),time.monotonic()
    stop=threading.Event()
    sampler=threading.Thread(target=_health_sampler,args=(config,profile,identity['placement'],identity['failure_law'],0,
        period,path,containers,started,stop,health))
    fault=threading.Thread(target=_stochastic_fault_controller,args=(profile,identity['placement'],identity['failure_law'],0,
        period,started_at,started,events,duration,config.health_poll_seconds,config.transition_observation_minimum_ticks,
        containers,networks,event_rows,controller)) if events else None
    sampler.start()
    if fault: fault.start()
    try:
        with ThreadPoolExecutor(max_workers=config.request_workers) as executor:
            futures=[]
            for index,operation in enumerate(operations):
                offset=index/config.request_rate_per_second
                _sleep_until(started+offset)
                futures.append(executor.submit(request,config,runtime_config,profile,runtime,identity,period,index,
                    operation,offset,namespace,fixture))
            _sleep_until(started+duration)
            rows=[future.result() for future in futures]
    finally:
        stop.set()
        sampler.join(timeout=30)
        if fault: fault.join(timeout=30)
    if sampler.is_alive() or (fault and fault.is_alive()):
        raise ValueError('sampler/controller did not terminate')
    # Retain all attempts; deferred persistence verification does not change the original response/deadline.
    persisted=db_records(path)
    for row in rows:
        if row['operation']=='create_visit': finalize_write(row,persisted.get(row['marker'],[]),fixture)
    metadata=dict(started_at=_format_time(started_at),completed_at=_format_time(_utc_now()),duration_seconds=duration,
                  planned_requests=len(operations),planned_operations=dict(Counter(operations)),workload_seed=seed,
                  planned_events=len(events),controller=controller)
    return rows,health,event_rows,metadata


def qualify(out,identity,periods,requests,health,config,profile,selected,namespace):
    calibration=[r for r in requests if r['period']=='calibration']
    baseline=[r for r in requests if r['period']=='baseline']
    test=[r for r in requests if r['period']=='test']
    native=out/'traces/native.jsonl'
    native_started=time.monotonic()
    grouped,parse=read_native(native,{r['trace_id'] for r in baseline+calibration},'otlp_jsonl_v1')
    parse_seconds=time.monotonic()-native_started
    learner=out/'learner-bundle'
    evaluator=out/'evaluator-bundle'
    learner_rows=[]
    for row in baseline+calibration:
        spans=grouped.get(row['trace_id'],[])
        replicas=sorted({s.resource_attributes.get('study.replica') for s in spans if s.service==profile.target_service
                         and s.resource_attributes.get('study.replica') in ('a','b')})
        learner_rows.append({k:row[k] for k in LEARNER_REQUEST_FIELDS if k in row} | dict(trace_present=bool(spans),
            span_count=len(spans),services=';'.join(sorted({s.service for s in spans})),target_replicas=';'.join(replicas),
            target_replica_count=len(replicas)))
    calibration_health,malformed=_pivot_health(identity,health,'calibration')
    test_health,test_malformed=_pivot_health(identity,health,'test')
    expected=dict(baseline=240,calibration=3600,test=3600)
    counts=Counter(r['period'] for r in requests)
    baseline_rates={operation:sum(r['semantic_success'] for r in baseline if r['operation']==operation)/60
                    for operation in selected_runtime_operations()}
    successful=[r for r in learner_rows if r['period']=='calibration' and r['semantic_success']]
    link_fraction=sum(r['trace_present'] for r in successful)/len(successful) if successful else 0
    assignments={replica:sum(replica in r['target_replicas'].split(';') for r in successful) for replica in ('a','b')}
    controller_ok=all(not p['controller']['errors'] and p['controller']['confirmed']==p['planned_events']
        and p['controller']['released']==p['planned_events'] and p['controller']['active_pause_causes_at_end']==0
        and p['controller']['active_network_causes_at_end']==0 for p in periods.values())
    checks=dict(exact_all_attempts=dict(counts)==expected and len({r['request_id'] for r in requests})==7440,
        fresh_namespace=all(r['request_id'].startswith(namespace+'-') for r in requests),
        baseline_all_operations=all(v>=selected['minimum_baseline_success_fraction_each_operation'] for v in baseline_rates.values()),
        successful_calibration_linkage=link_fraction>=selected['minimum_successful_trace_link_fraction'],
        clean_calibration_native=not parse['malformed_json_records'] and not parse['invalid_traces'],
        calibration_health=malformed==0 and len(calibration_health)>=900*selected['minimum_health_observation_fraction'],
        test_health=test_malformed==0 and len(test_health)>=900*selected['minimum_health_observation_fraction'],
        both_replicas_observed=all(v>=selected['minimum_successful_assignments_each_replica'] for v in assignments.values()),
        all_faults_confirmed_and_released=controller_ok)
    metadata=dict(identity,scope=selected['scope'],source_run=os.environ['GITHUB_RUN_ID'],study_head=os.environ['GITHUB_SHA'],
        config_sha256=digest(CONFIG),runtime_config_sha256=digest(ROOT/selected['runtime_config']),namespace=namespace,
        usable=all(checks.values()))
    _write_csv(learner/'learner/requests.csv',LEARNER_REQUEST_FIELDS,learner_rows)
    _write_csv(learner/'learner/health.csv',LEARNER_HEALTH_FIELDS,calibration_health)
    span_records={key:tuple(SpanRecord(s.trace_id,s.span_id,s.parent_id,s.service,s.operation,
        str(s.resource_attributes.get('study.replica','')) if s.service==profile.target_service else '') for s in spans)
        for key,spans in grouped.items()}
    _write_csv(learner/'learner/topology-edges.csv',TOPOLOGY_EDGE_FIELDS,_topology_rows(identity,span_records))
    dependencies={'list_owners':[['api-gateway','customers-service'],['customers-service','database']],
        'owner_details_with_visits':[['api-gateway','customers-service'],['customers-service','database'],
            ['api-gateway','visits-service'],['visits-service','database']],
        'create_visit':[['api-gateway','visits-service'],['visits-service','database']],
        'list_vets':[['api-gateway','vets-service'],['vets-service','database']]}
    write(learner/'learner/deployment.json',dict(identity,target_service=profile.target_service,
        replicas=profile.replica_services,placements=config.placement.placements[identity['placement']],
        known_non_target_dependencies=selected['known_non_target_dependencies'],source_declared_dependencies=dependencies,
        dependency_provenance='Pinned controllers/clients and SQL FK; declaration, not inferred causal necessity',
        backend_success_check_statuses=['L7OK'],replica_health_check='GET /actuator/health',database_shared=True))
    write(learner/'learner/manifest.json',metadata)
    write(learner/'audit/boundary.json',dict(metadata,checks=checks,fit_count=0,evaluator_files_in_learner_bundle=0))
    selected_ids={r['trace_id'] for r in calibration}
    write(learner/'native/calibration-native.json',dict(spans={key:[asdict(s) for s in value] for key,value in grouped.items() if key in selected_ids},
        selected_trace_ids=sorted(selected_ids),calibration_only=True,parse=parse,original_native_sha256=digest(native)))
    _write_csv(evaluator/'evaluator/test-requests.csv',EVALUATOR_REQUEST_FIELDS,
               [{k:r[k] for k in EVALUATOR_REQUEST_FIELDS} for r in test])
    _write_csv(evaluator/'evaluator/test-health.csv',LEARNER_HEALTH_FIELDS,test_health)
    seal(learner,metadata)
    seal(evaluator,metadata)
    summary=dict(metadata,checks=checks,period_counts=dict(counts),baseline_success_fractions=baseline_rates,
        successful_calibration_trace_fraction=link_fraction,successful_replica_assignments=assignments,
        calibration_health_ticks=len(calibration_health),test_health_ticks=len(test_health),
        native_parse_seconds=parse_seconds,native_bytes=native.stat().st_size,parse=parse,
        periods=periods,model_fits=0,main_campaigns=0,
        operation_summary=[dict(period=period,operation=operation,attempts=len(chosen),successes=sum(r['semantic_success'] for r in chosen),
            timed_out=sum(r['timed_out'] for r in chosen),write_side_effect_without_success=sum(r['write_found_without_timely_success'] for r in chosen))
            for period in expected for operation in selected_runtime_operations()
            for chosen in [[r for r in requests if r['period']==period and r['operation']==operation]]])
    write(out/'technical-summary.json',summary)
    return summary


def selected_runtime_operations():
    return ('list_owners','owner_details_with_visits','create_visit','list_vets')


def run(bundle,out,placement,law):
    selected,runtime_config,config,profile,runtime=config_objects()
    assert placement in selected['placements'] and law in selected['laws']
    identity=dict(profile=PROFILE,placement=placement,failure_law=law,repetition=0)
    namespace=f"petclinic-tech-v1-run{os.environ['GITHUB_RUN_ID']}-a{os.environ['GITHUB_RUN_ATTEMPT']}-{placement}-{law}"
    fixture=adapt_fixture(json.loads((bundle/'fixture.json').read_text()))
    path=compose(bundle,out,runtime_config,placement)
    base=['docker','compose','-f',str(path)]
    periods,requests,health,events_all={ },[],[],[]
    try:
        command([*base,'up','-d'],log=out/'logs/compose-up.log')
        deadline=time.monotonic()+runtime_config['startup_deadline_seconds']
        warmup=[]
        while time.monotonic()<deadline:
            chosen=[execute(runtime.base_url,op,f'{namespace}-warmup-{len(warmup)}-{op}',fixture,runtime_config)
                    for op in ('list_owners','owner_details_with_visits','list_vets')]
            warmup.extend(chosen)
            write(out/'warmup.json',warmup)
            if all(r['semantic_success'] for r in chosen): break
            time.sleep(5)
        else: raise ValueError('readiness contracts not satisfied')
        planned={period:plan_renewal_events(config,profile,placement,law,0,period,base_seed=selected['base_seed'])
                 for period in ('calibration','test')}
        write(out/'planned-schedule.json',dict(identity,base_seed=selected['base_seed'],
            events={p:[asdict(e) for e in es] for p,es in planned.items()},
            factor_seeds={period:{factor.factor_id:renewal_schedule_seed(config,profile,placement,law,0,period,factor.factor_id,
                base_seed=selected['base_seed']) for factor in factor_definitions(config,profile,placement,law)} for period in planned}))
        for period,duration in (('baseline',60),('calibration',900),('test',900)):
            if periods: time.sleep(selected['inter_period_recovery_seconds'])
            rows,ticks,events,metadata=period_run(config,runtime_config,profile,runtime,identity,period,duration,path,
                planned.get(period,()),namespace,fixture)
            requests.extend(rows);health.extend(ticks);events_all.extend(events);periods[period]=metadata
            write(out/'requests.json',requests)
            write(out/'health.json',health)
            write(out/'events.json',events_all)
            write(out/'periods.json',periods)
        time.sleep(selected['trace_flush_seconds'])
        summary=qualify(out,identity,periods,requests,health,config,profile,selected,namespace)
        if not summary['usable']: raise ValueError('technical qualification failed; complete source/absence census retained')
    finally:
        identifiers=command([*base,'ps','-aq']).splitlines()
        if identifiers:
            snapshots=json.loads(command(['docker','inspect',*identifiers]))
            write(out/'final-containers.json',snapshots)
            for record in snapshots:
                if record['State']['Paused']: command(['docker','unpause',record['Id']])
        command([*base,'logs','--no-color'],log=out/'logs/services.log')
        command([*base,'down'],log=out/'logs/compose-down.log')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--placement',choices=('colocated','split'),required=True)
    parser.add_argument('--law',choices=('N','NC','ND','NCD'),required=True)
    args=parser.parse_args()
    assert os.environ.get('GITHUB_ACTIONS')=='true','Live acquisition and native parsing are GitHub Actions only'
    run(args.bundle.resolve(),args.out.resolve(),args.placement,args.law)


if __name__=='__main__': main()
