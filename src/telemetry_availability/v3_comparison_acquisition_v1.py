"""Fresh whole-operation acquisition and physically separate prospective roles.

All application work is GitHub Actions only. The qualified workload, renewal,
health and Petclinic persistence routines are reused with the actual repetition.
Final collectors are stopped before native bytes are hashed and parsed.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time

from .live_evidence import _pivot_health
from .live_fault_campaign import _service_containers, _sleep_until
from .live_stochastic_pilot import (_health_sampler, _stochastic_fault_controller, _operation_order,
    _stable_seed, _utc_now, _format_time, plan_renewal_events, factor_definitions, renewal_schedule_seed)
from .live_validation_config import load_frozen_live_validation_config
from .live_placement_config import select_placement_pilot_profile
from .live_pilot_config import select_runtime_pilot_profile
from .publication_stochastic_live import (_run_period, _semantic_sentinels, initialize_profile,
    wait_for_frontend, _collect_telemetry)
from .petclinic_stochastic_preflight_v2 import config_objects, compose as petclinic_compose, request
from .petclinic_contract_v2 import adapt_fixture, execute, finalize_write
from .petclinic_runtime_v3 import command, db_records
from .pmx_observed_operations import read_native
from .v3_primary_projection import REQUEST_FIELDS, PROBE_FIELDS, write, read, sha
from .v3_comparison_roles_v1 import ordinary_projection, write_ordinary, seal_role, campaign_id

PETCLINIC = 'spring_petclinic_microservices'


def petclinic_period(config,runtime_config,profile,runtime,identity,period,duration,path,events,namespace,fixture):
    services=(*profile.replica_services.values(),profile.target_service)
    containers=_service_containers(path,services)
    # Preserve database and telemetry networks; only the application path is injected.
    networks={service:('petclinic-study-application',(service,)) for service in profile.replica_services.values()}
    seed=_stable_seed(config.pilot_base_seed,profile.id,identity['placement'],identity['failure_law'],identity['repetition'],period,'workload')
    operations=_operation_order(runtime,duration*config.request_rate_per_second,seed)
    health,event_rows=[],[]
    controller=dict(events=0,confirmed=0,released=0,active_pause_causes_at_end=0,active_network_causes_at_end=0,errors=[])
    started_at,started=_utc_now(),time.monotonic()
    stop=threading.Event()
    sampler=threading.Thread(target=_health_sampler,args=(config,profile,identity['placement'],identity['failure_law'],identity['repetition'],
        period,path,containers,started,stop,health))
    fault=threading.Thread(target=_stochastic_fault_controller,args=(profile,identity['placement'],identity['failure_law'],identity['repetition'],
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


def controller_gate(periods):
    return all(not p['controller']['errors'] and p['controller']['confirmed'] == p['planned_events']
        and p['controller']['released'] == p['planned_events']
        and p['controller']['active_pause_causes_at_end'] == 0
        and p['controller']['active_network_causes_at_end'] == 0 for p in periods.values())


def export_roles(out, identity, selected, config, profile, runtime, periods, requests, health, native_path, native_format, readiness):
    """Trusted preparation exports every planned calibration attempt independently of test qualification."""
    operations = tuple(selected['design']['applications'][profile.id])
    calibration = [r for r in requests if r['period'] == 'calibration']
    test = [r for r in requests if r['period'] == 'test']
    baseline = [r for r in requests if r['period'] == 'baseline']
    meta = dict(profile=profile.id, placement=identity['placement'], failure_law=identity['law'], repetition=identity['repetition'])
    tick = time.perf_counter()
    original_hash = sha(native_path)
    grouped, parse = read_native(native_path, {r['trace_id'] for r in calibration}, native_format)
    if sha(native_path) != original_hash:
        raise ValueError('native bytes changed during parsing despite stopped collector')
    parse_seconds = time.perf_counter()-tick
    native = dict(calibration_only=True, selected_trace_ids=sorted(r['trace_id'] for r in calibration),
        spans={key: [asdict(span) for span in spans] for key, spans in grouped.items()})
    cal_health, malformed = _pivot_health(meta, health, 'calibration')
    test_health, test_malformed = _pivot_health(meta, health, 'test')
    layer = 'L7' if profile.id == PETCLINIC else 'L4'
    declarations = dict(meta, target_service=profile.target_service, replicas=profile.replica_services,
        placements=config.placement.placements[identity['placement']], known_non_target_dependencies=[],
        source_declared_dependencies={op: [] for op in operations},
        dependency_provenance='Required call semantics are separately pinned operation source declarations; empty metadata lists mean unspecified, not no dependencies',
        backend_success_check_statuses=[layer+'OK'],
        replica_health_check='GET /actuator/health' if layer == 'L7' else 'HAProxy L4 transport connect only',
        database_shared=True if profile.id == PETCLINIC else None)
    cal_probes = [{key: row[key] for key in PROBE_FIELDS} for row in cal_health]
    expected = selected['calibration_seconds']*selected['request_rate_per_second']//len(operations)
    ordinary, audit = ordinary_projection(declarations, calibration, cal_probes, native, identity, operations, expected)
    clean_native = not parse['malformed_json_records'] and not parse['invalid_traces']
    ordinary['manifest.json'].update(calibration_native_quality=dict(qualified=clean_native,
        reason=None if clean_native else 'malformed_native_record_or_invalid_calibration_trace'),
        original_native_sha256=original_hash, calibration_probe_malformed_records=malformed)
    ordinary_hash = write_ordinary(out/'roles/ordinary', ordinary)
    # PMX receives the same whitelisted native/request pool, physically without
    # probes, inferred graph, parameters, baseline, test, or generator schedule.
    pmx_manifest = dict(identity=identity, role='pmx_calibration', native_quality=ordinary['manifest.json']['calibration_native_quality'],
        original_native_sha256=original_hash, external_attempts=len(calibration),
        declared_host='declared-physical-runner', input_pool='same whitelisted native spans and external calibration attempts as ordinary role')
    seal_role(out/'roles/pmx', 'pmx_calibration', identity,
        {'requests.json': ordinary['requests.json'], 'native.json': ordinary['native.json'], 'manifest.json': pmx_manifest})
    expected_counts = {period: selected[period+'_seconds']*selected['request_rate_per_second'] for period in ('baseline', 'calibration', 'test')}
    checks = dict(exact_all_attempts=dict(Counter(r['period'] for r in requests)) == expected_counts,
        unique_all_attempts=len({r['request_id'] for r in requests}) == len(requests),
        unique_all_traces=len({r['trace_id'] for r in requests}) == len(requests),
        startup_contracts=readiness,
        baseline_contracts=all(sum(r['semantic_success'] for r in baseline if r['operation']==op)
            >= selected['minimum_baseline_success_fraction']*expected_counts['baseline']/len(operations) for op in operations),
        all_planned_faults_confirmed_and_released=controller_gate(periods))
    failed = [key for key, value in checks.items() if not value]
    # Native/health coverage is diagnostic; it cannot select primary test attempts.
    evaluator_manifest = dict(identity=identity, role='evaluator',
        test_quality=dict(qualified=not failed, reason=','.join(failed) if failed else None, checks=checks),
        test_probe_malformed_records=test_malformed,
        native_or_health_coverage_filters_primary_attempts=False, layer=layer,
        operations=list(operations), expected_per_operation=expected)
    seal_role(out/'roles/evaluator', 'evaluator', identity,
        {'requests.json': [{key: row[key] for key in REQUEST_FIELDS} for row in test],
         'probes.json': [{key: row[key] for key in PROBE_FIELDS} for row in test_health],
         'manifest.json': evaluator_manifest})
    receipt = dict(identity=identity, campaign_id=campaign_id(identity),
        graph_input_seal_sha256=ordinary_hash, pmx_input_seal_sha256=sha(out/'roles/pmx/seal.json'),
        evaluator_seal_sha256=sha(out/'roles/evaluator/seal.json'),
        acquisition_head=os.environ['GITHUB_SHA'], acquisition_run=os.environ['GITHUB_RUN_ID'])
    write(out/'public/receipt.json', receipt)
    # Closed quality stays inside the evaluator/raw role until candidates freeze.
    write(out/'projection-audit.json', dict(identity=identity, audit=audit, native_parse=parse,
        native_parse_seconds=parse_seconds, final_native_sha256=original_hash,
        stopped_collector_input=True, calibration_attempts=len(calibration),
        cal_probes=len(cal_probes), calibration_probe_malformed_records=malformed))
    return dict(shared_native_extraction_seconds=parse_seconds, native_bytes=native_path.stat().st_size,
        ordinary_role_bytes=sum(p.stat().st_size for p in (out/'roles/ordinary').iterdir()),
        pmx_role_bytes=sum(p.stat().st_size for p in (out/'roles/pmx').iterdir()))


def acquire(settings_path, profile_id, placement, law, repetition, mode, out, bundle):
    selected = read(settings_path); out.mkdir(parents=True, exist_ok=True)
    dimensions = selected['design'] if mode == 'main' else selected['preflight']
    if (profile_id not in selected['design']['applications'] or placement not in dimensions['placements']
            or law not in dimensions['laws'] or repetition not in dimensions['repetitions']):
        raise ValueError('unplanned acquisition identity')
    identity = dict(application=profile_id, placement=placement, law=law, repetition=repetition,
        namespace=selected[mode+'_namespace'], data_role='prospective_main' if mode=='main' else 'development_preflight',
        protocol_sha256=sha(settings_path))
    seed = selected[mode+'_seed']
    namespace = '-'.join([identity['namespace'], profile_id, placement, law, str(repetition),
        'run'+os.environ['GITHUB_RUN_ID'], 'a'+os.environ['GITHUB_RUN_ATTEMPT']])
    old_identity = dict(profile=profile_id, placement=placement, failure_law=law, repetition=repetition)
    if profile_id == PETCLINIC:
        _, runtime_config, config, profile, runtime = config_objects()
        fixture = adapt_fixture(read(bundle/'fixture.json'))
        path = petclinic_compose(bundle, out, runtime_config, placement)
    else:
        config = load_frozen_live_validation_config('configs/m7_frozen_live.yaml').stochastic
        profile = select_placement_pilot_profile(config.placement, profile_id)
        runtime = select_runtime_pilot_profile(config.placement.runtime, profile_id)
        path = out/'pinned-compose.json'
        actual = subprocess.check_output(['git', '-C', 'upstream', 'rev-parse', 'HEAD'], text=True).strip()
        if actual != runtime.commit:
            raise ValueError('upstream checkout differs from source binding')
    config = replace(config, pilot_base_seed=seed, main_base_seed=seed,
        baseline_seconds=selected['baseline_seconds'], period_seconds=selected['calibration_seconds'],
        request_rate_per_second=selected['request_rate_per_second'], request_workers=selected['request_workers'])
    base = ['docker', 'compose', '-f', str(path)]
    periods = {}; requests = []; health = []; events_all = []; responses = []
    campaign_started = _utc_now(); tick = time.perf_counter()
    write(out/'identity.json', identity)
    try:
        if profile_id == PETCLINIC:
            command([*base, 'up', '-d'], log=out/'logs/compose-up.log')
            deadline = time.monotonic()+runtime_config['startup_deadline_seconds']; warmup = []
            while time.monotonic() < deadline:
                chosen = [execute(runtime.base_url, op, f'{namespace}-warmup-{len(warmup)}-{op}', fixture, runtime_config)
                    for op in ('list_owners', 'owner_details_with_visits', 'list_vets')]
                warmup.extend(chosen); write(out/'warmup.json', warmup)
                if all(r['semantic_success'] for r in chosen):
                    break
                time.sleep(5)
            else:
                raise ValueError('readiness contracts not satisfied')
            readiness = True
        else:
            wait_for_frontend(runtime, config.placement.runtime.readiness_timeout_seconds)
            time.sleep(config.placement.runtime.post_start_stabilization_seconds)
            initialize_profile(runtime)
            sentinels, sentinel_responses, effects = _semantic_sentinels(config, profile, runtime, placement, law, repetition, namespace)
            write(out/'sentinels.json', dict(requests=sentinels, responses=sentinel_responses, effects=effects))
            readiness = all(r['semantic_success'] for r in sentinels) and effects['passed']
        planned = {period: plan_renewal_events(config, profile, placement, law, repetition, period, base_seed=seed)
                   for period in ('calibration', 'test')}
        write(out/'planned-schedule.json', dict(identity=identity, base_seed=seed,
            events={p: [asdict(e) for e in es] for p, es in planned.items()},
            factor_seeds={p: {f.factor_id: renewal_schedule_seed(config, profile, placement, law, repetition, p, f.factor_id, base_seed=seed)
                for f in factor_definitions(config, profile, placement, law)} for p in planned}))
        for period in ('baseline', 'calibration', 'test'):
            if periods:
                time.sleep(selected['inter_period_recovery_seconds'])
            duration = selected[period+'_seconds']
            if profile_id == PETCLINIC:
                rows, ticks, events, metadata = petclinic_period(config, runtime_config, profile, runtime, old_identity,
                    period, duration, path, planned.get(period, ()), namespace, fixture)
            else:
                rows, response_rows, events, ticks, metadata = _run_period(config, profile, runtime, placement, law, repetition,
                    period, duration, path, planned.get(period, ()), base_seed=seed, request_namespace=namespace)
                responses.extend(response_rows)
            requests.extend(rows); health.extend(ticks); events_all.extend(events); periods[period] = metadata
            for name, value in (('requests', requests), ('responses', responses), ('health', health), ('events', events_all), ('periods', periods)):
                write(out/(name+'.json'), value)
        time.sleep(selected['trace_flush_seconds'])
        if profile_id == PETCLINIC:
            command([*base, 'stop', '-t', '30', 'collector'], log=out/'logs/collector-stop.log')
            native_path, native_format = out/'traces/native.jsonl', 'otlp_jsonl_v1'
        elif runtime.telemetry_kind == 'jaeger_api':
            _, error = _collect_telemetry(runtime, campaign_started, out)
            if error:
                raise ValueError(error)
            native_path, native_format = out/'raw-telemetry.json', 'jaeger_json_v1'
        else:
            command([*base, 'stop', '-t', '30', 'otel-collector'], log=out/'logs/collector-stop.log')
            _, error = _collect_telemetry(runtime, campaign_started, out)
            if error:
                raise ValueError(error)
            native_path, native_format = out/'raw-telemetry.log', 'otlp_jsonl_v1'
        costs = export_roles(out, identity, selected, config, profile, runtime, periods, requests, health,
            native_path, native_format, readiness)
        costs.update(acquisition_process_seconds=time.perf_counter()-tick, identity=identity)
        write(out/'costs.json', costs)
        write(out/'public/costs.json', costs)
    finally:
        # Stop residual injected states and preserve final runtime provenance.
        identifiers = command([*base, 'ps', '-aq']).splitlines()
        if identifiers:
            snapshots = json.loads(command(['docker', 'inspect', *identifiers]))
            write(out/'final-containers.json', snapshots)
            for record in snapshots:
                if record['State']['Paused']:
                    command(['docker', 'unpause', record['Id']])
        command([*base, 'logs', '--no-color'], log=out/'logs/services.log')
        command([*base, 'down'], log=out/'logs/compose-down.log')


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Application traffic/native parsing is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/v3_comparison_design_v1.json'))
    parser.add_argument('--profile', required=True)
    parser.add_argument('--placement', required=True)
    parser.add_argument('--law', required=True)
    parser.add_argument('--repetition', type=int, required=True)
    parser.add_argument('--mode', choices=['main', 'preflight'], required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, default=Path('workflow-input/petclinic-build'))
    args = parser.parse_args()
    acquire(args.config, args.profile, args.placement, args.law, args.repetition, args.mode, args.out.resolve(), args.bundle.resolve())


if __name__ == '__main__':
    main()
