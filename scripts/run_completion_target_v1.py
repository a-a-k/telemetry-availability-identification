"""One fixed saved-data experiment: three R routes, E/R adequacy and masks."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import sys
import time

import retain_v3_comparison_compact_v4 as transport
from benchmark_v3_pipeline_v1 import replicate, timed, command_ok
from run_v4_missingness_v3 import fetch, SOURCE_RUN, SOURCE_HEAD
from v4_confirmed_source_v3 import require_source
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
from telemetry_availability.v3_comparison_roles_v1 import load_role
from telemetry_availability.v3_ordinary_identity_v2 import load_bundle
from telemetry_availability.v4_primary_capture_v1 import load
from telemetry_availability.v3_primary_projection import read, write, sha
from telemetry_availability.completion_target_v1 import (
    full_identify, direct_records, direct_identify, query_full_r, query_reduced, project_full,
    reduced_from_rows, binding, JointBounds)
from telemetry_availability.completion_target_analysis_v1 import analyze, metrics

CONFIG = Path('configs/v5_completion_target_v1.json')
ROOT = Path('workflow-results/completion-target')
WORK = Path('workflow-input/completion-target')
BASE = {'requests.json', 'native.json', 'probes.json', 'declarations.json', 'manifest.json', 'seal.json'}
GRAPH = {'candidates/candidates.json', 'candidates/models.json', 'candidates/costs.json',
         'candidates/read-audit.json', 'candidates/seal.json', 'compact/results.json', 'compact/replay.json',
         'compact/resource-summary.json', 'compact/build-resource-usage.txt', 'compact/replay-resource-usage.txt'}
BOUNDS = {'compact.json', 'sealed/bounds.json', 'sealed/receipt.json', 'sealed/read-audit.json', 'sealed/seal.json'}


def source(case, role, artifacts, receipts):
    allowed = dict(ordinary=BASE, graph=GRAPH, bounds=BOUNDS,
                   **{'test-binding': BASE | ({'controls.json'} if case['profile'] == 'spring_petclinic_microservices' else set()),
                      'primary-full': {'test.json', 'controls.json'} if case['profile'] == 'spring_petclinic_microservices' else {'test.json'},
                      'primary-compact': {'compact.json'}})[role]
    root = WORK/'source'/case['key']/role
    key = f"v4-confirmation-{role}-{case['key']}-{SOURCE_RUN}"
    if not root.exists():
        receipts[key] = fetch(artifacts, key, allowed, root)
    return root


def prepare_cost(case, artifacts, receipts):
    root = source(case, 'ordinary', artifacts, receipts)
    data, _ = load_bundle(root)
    if data['manifest.json']['identity'] != case['identity']: raise ValueError('calibration identity differs')
    for multiplier in (1, 2, 4):
        target = WORK/'volumes'/f'x{multiplier}'; copied = deepcopy(data)
        copied['requests.json'], copied['native.json'] = replicate(data['requests.json'], data['native.json'], multiplier, case['profile'])
        identity = dict(case['identity'], namespace=f'v5-completion-cost-x{multiplier}', data_role='artificial_control')
        copied['manifest.json'].update(identity=identity, external_attempts=len(copied['requests.json']))
        for name, value in copied.items(): write(target/'ordinary'/name, value)
        settings = read('configs/v4_confirmation_execution_v1.json')
        for spec in settings['profiles'][case['profile']]['operations'].values(): spec['expected_attempts'] *= multiplier
        write(target/'execution.json', settings)
        write(target/'workload.json', dict(profile=case['profile'], identity=identity, multiplier=multiplier,
            attempts=len(copied['requests.json']), spans=sum(len(v) for v in copied['native.json']['spans'].values()),
            new_independent_observations=0, source_identity=case['identity']))
        write(ROOT/'full'/'workloads'/f'x{multiplier}.json', dict(workload=read(target/'workload.json'),
              files={p.relative_to(target).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
                     for p in target.rglob('*') if p.is_file()}))


def costs(config, profile):
    rows = []; routes = config['routes']
    for repetition, volumes in enumerate(config['scale_orders']):
        for multiplier in volumes:
            offset = (repetition + (1, 2, 4).index(multiplier)) % 3
            order = routes[offset:] + routes[:offset]
            for position, route in enumerate(order):
                inputs = WORK/'volumes'/f'x{multiplier}'
                out = ROOT/'full'/'trials'/f'r{repetition}-x{multiplier}'/route
                # Byte-only warmup is identical for all routes, outside timing.
                for file in sorted((inputs/'ordinary').glob('*.json')):
                    with file.open('rb') as stream:
                        while stream.read(1024*1024): pass
                row = dict(profile=profile, repetition=repetition, multiplier=multiplier, route=route,
                           position=position, order=order, status='measured_awaiting_verification')
                start = time.perf_counter_ns()
                try:
                    process = timed([sys.executable, 'scripts/measure_completion_target_v1.py', '--input', inputs,
                                     '--output', out, '--route', route], out/'process', dict(os.environ), timeout=600)
                    row['process'] = process; command_ok(process)
                    measurement = read(out/'measurement.json')
                    elapsed = (measurement['first_saved_ns']-start)/1e9
                    if not 0 < elapsed <= process['wall_seconds']+1: raise ValueError('first-answer clock differs')
                    row.update(first_answer_seconds=elapsed, **measurement)
                except Exception as exc:
                    row.update(status='failed', error=type(exc).__name__+': '+str(exc))
                rows.append(row)
                write(ROOT/'compact/timings.json', dict(records=rows, all_extra_verification_after_measurements=True))
                print(json.dumps(dict(stage='cost', route=route, multiplier=multiplier, repetition=repetition, status=row['status'])), flush=True)
    return rows


def qualify_costs(rows, config):
    for row in rows:
        if row['status'] == 'failed': continue
        try:
            target = ROOT/'full'/'trials'/f"r{row['repetition']}-x{row['multiplier']}"/row['route']
            models = read(target/'models.json'); answers = read(target/'answers.json')
            for op, model in models.items():
                replay = query_full_r(model) if row['route'] == 'full' else query_reduced(model)
                if answers[op] != dict(support='supported', **replay): raise ValueError('saved R replay differs')
            for warm in row['warm_queries']:
                if dict(support='supported', **warm['answer']) != answers[warm['operation']]:
                    raise ValueError('ready-query R changed')
            base = ROOT/'full'/'trials'/f"r{row['repetition']}-x{row['multiplier']}"
            full = read(base/'full/models.json'); direct = read(base/'direct/models.json')
            projected = read(base/'projected/models.json')
            if set(full) != set(projected) or set(full) != set(direct):
                raise ValueError('timed routes have unequal target/support census')
            for op in full:
                if project_full(full[op]) != projected[op] or projected[op] != direct[op]:
                    raise ValueError('paired same-R representation differs')
                if read(base/'full/answers.json')[op] != read(base/'direct/answers.json')[op]:
                    raise ValueError('paired same-R answer differs')
            # All cloned volumes must preserve the baseline probability/status.
            original = read(ROOT/'full/trials/r0-x1'/row['route']/'answers.json')
            for op, value in answers.items():
                if {k:v for k,v in value.items() if k!='samples'} != {k:v for k,v in original[op].items() if k!='samples'}:
                    raise ValueError('computational copies changed R')
            row['status'] = 'qualified'
        except Exception as exc:
            row.update(status='failed', error=type(exc).__name__+': '+str(exc))
    write(ROOT/'compact/timings.json', dict(records=rows, all_extra_verification_after_measurements=True))


def semantics(case, period, config, artifacts, receipts):
    if period == 'calibration':
        data, _ = load_bundle(source(case, 'ordinary', artifacts, receipts))
        candidate, _ = load_role(source(case, 'graph', artifacts, receipts)/'candidates', 'graph_candidates', case['identity'])
        originals = candidate['models.json']['execution']
        absent = {op: r['Gstar'] for op, r in candidate['candidates.json']['forecasts'].items() if op not in originals}
        outcomes = None
    else:
        data, _ = load(source(case, 'test-binding', artifacts, receipts), 'test_binding', case['identity'])
        bounded, _ = load(source(case, 'bounds', artifacts, receipts)/'sealed', 'realized_bounds', case['identity'])
        originals = bounded['bounds.json']['models']
        absent = {r['operation']: r for r in bounded['bounds.json']['operations'] if r['status']=='unsupported'}
        primary = read(source(case, 'primary-full', artifacts, receipts)/'test.json')
        compact = read(source(case, 'primary-compact', artifacts, receipts)/'compact.json')
        if (primary['independently_verified_attempts'] != 3600 or primary['primary_attempts'] != 3600
            or len(primary['primary_verdicts']) != 3600 or primary['selected_by_E_equals_Y'] is not False
            or compact['identity'] != case['identity'] or compact['head'] != SOURCE_HEAD):
            raise ValueError('unqualified primary population')
        outcomes = {key: value['outcome'] for key, value in primary['primary_verdicts'].items()}
    if data['manifest.json']['identity'] != case['identity']: raise ValueError('input identity differs')
    specs = read('configs/v4_confirmation_execution_v1.json')['profiles'][case['profile']]['operations']
    operations = []
    for operation, spec in specs.items():
        full = fr = None; direct = dr = signals = None; full_reason = direct_reason = None
        try: full, fr = full_identify(data, operation, spec, case['identity'])
        except binding.BindingUnsupported as exc: full_reason = str(exc)
        if full is not None:
            if operation not in originals or full != originals[operation]:
                raise ValueError('full identification changed original model: '+case['key']+'/'+period+'/'+operation)
        elif operation not in absent: raise ValueError('new unexplained full support refusal')
        try:
            dr, signals = direct_records(data, operation, spec, case['identity'])
            direct = reduced_from_rows(dr, signals, operation)
        except binding.BindingUnsupported as exc: direct_reason = str(exc)
        row = dict(operation=operation, attempts=spec['expected_attempts'],
                   full_support=full is not None, direct_support=direct is not None,
                   full_reason=full_reason, direct_reason=direct_reason, full_original_reproduced=True)
        if full is not None and direct is None: raise ValueError('direct unexpectedly excludes full supported case')
        if direct is not None:
            ys = {r['request_id']: outcomes[r['request_id']] for r in dr} if outcomes is not None else None
            if period == 'test':
                result = analyze(full, fr, dr, signals, operation, ys, config)
            else:
                joint = JointBounds(full) if full is not None else None
                baseline, patterns = metrics(fr, dr, signals, joint, None)
                if full is not None:
                    if project_full(full) != direct or query_full_r(full) != query_reduced(direct):
                        raise ValueError('calibration same-R mismatch')
                    for left, right in zip(fr, dr, strict=True):
                        if left['request_id'] != right['request_id'] or any(left['observation'][k] != v for k,v in right['observation'].items()):
                            raise ValueError('calibration primitive interpretation differs')
                result = dict(baseline=baseline, baseline_patterns=patterns, settings=[], patterns=[], masks=[],
                              R=query_reduced(direct), same_R_routes_qualified=True,
                              witnesses=joint.verify() if joint is not None else [], distinct_joint_masks=len(joint.cache) if joint else 0)
            # The public direct entrypoint is checked separately against its
            # independent atomic-record route, without any external outcome.
            direct_check, check_rows = direct_identify(data, operation, spec, case['identity'])
            if direct_check != direct or check_rows != dr: raise ValueError('public direct route differs')
            path = ROOT/'full/semantics'/case['key']/period/operation
            write(path/'observations.json', dict(full=full, direct=direct, full_attempts=fr, direct_attempts=dr, outcomes=ys))
            for field in ('masks', 'witnesses', 'patterns', 'baseline_patterns'):
                write(path/(field+'.json'), result.pop(field))
            row.update(result)
        operations.append(row)
        print(json.dumps(dict(stage='semantics', case=case['key'], period=period, operation=operation,
                              full=row['full_support'], direct=row['direct_support'])), flush=True)
    return dict(identity=case['identity'], period=period, operations=operations)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--profile', required=True); args=p.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_RUN_ATTEMPT')!='1':
        raise ValueError('original remote run required')
    config=read(CONFIG)
    for name, expected in config['source_locks'].items():
        if sha(Path(name)) != expected: raise ValueError('fixed extension source changed: '+name)
    source_status=require_source(); _, _, cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'), 'main')
    cases=[c for c in cases if c['profile']==args.profile]
    if len(cases)!=6: raise ValueError('unplanned application census')
    artifacts=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/artifacts','artifacts'); by_name={a['name']:a for a in artifacts}
    for expected in config['source_artifacts']:
        actual=by_name[expected['name']]
        if any(actual[k]!=v for k,v in expected.items()): raise ValueError('original source artifact changed')
    receipts={}; baseline=next(c for c in cases if c['identity']['law']=='N' and c['identity']['repetition']==0)
    write(ROOT/'compact/protocol.json', config)
    write(ROOT/'compact/environment.json', dict(profile=args.profile, head=os.environ['GITHUB_SHA'],
        run=os.environ['GITHUB_RUN_ID'], source_status=source_status, python=sys.version, platform=platform.platform(),
        cpu_count=os.cpu_count(), cpu_info=Path('/proc/cpuinfo').read_text(), memory_info=Path('/proc/meminfo').read_text()))
    try:
        prepare_cost(baseline, artifacts, receipts)
        rows=costs(config, args.profile)
        qualify_costs(rows, config)
        result=[]
        for case in cases:
            for period in ('calibration', 'test'):
                result.append(semantics(case, period, config, artifacts, receipts))
                write(ROOT/'compact/semantics.json', dict(cases=result))
        expected=config['operation_cases'][args.profile]
        if sum(len(c['operations']) for c in result)!=2*expected: raise ValueError('incomplete semantic census')
        if len(rows)!=27 or any(r['status']!='qualified' for r in rows): raise ValueError('cost qualification failed')
        write(ROOT/'compact/receipt.json', dict(run=os.environ['GITHUB_RUN_ID'], head=os.environ['GITHUB_SHA'],
            profile=args.profile, source_run=SOURCE_RUN, source_head=SOURCE_HEAD, config_sha256=sha(CONFIG),
            source_artifacts=receipts, cost_processes=len(rows), operation_positions=2*expected,
            status='qualified', Y_used_only_for_validation=True, new_independent_observations=0))
    except Exception as exc:
        write(ROOT/'compact/failure.json', dict(type=type(exc).__name__, message=str(exc), source_artifacts=receipts))
        raise


if __name__ == '__main__': main()
