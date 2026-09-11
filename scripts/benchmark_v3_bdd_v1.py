"""Remote-only, complete-census CUDD comparison on frozen joint models."""
import argparse
from collections import Counter
import gc
import gzip
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import signal
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from telemetry_availability.graph_execution_model_v1 import solve, control_ids
from telemetry_availability.graph_execution_bdd_v1 import CompiledModel, verify_result
from bdd_scaling_cases_v1 import cases as synthetic_cases
import retain_v3_comparison_compact_v4 as transport

CONFIG = ROOT/'configs/v3_bdd_comparison_v1.json'


def encoded(value): return (json.dumps(value, sort_keys=True, allow_nan=False)+'\n').encode()
def digest(value): return sha256(encoded(value)).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value))
def require(value, message):
    if not value: raise ValueError(message)


def prepare(profile, config, out):
    if profile == 'synthetic':
        rows = synthetic_cases()
        for row in rows:
            result = solve(row['model'])
            ex = result['estimates']['execution']
            require([ex['lower_exact'], ex['upper_exact']] == row['oracle'], 'artificial analytical oracle differs')
            row['reference'] = dict(estimates=result['estimates'])
            row['source'] = dict(kind='declared_artificial_grid', new_independent_campaigns=0)
        return rows, [], []
    raw = (ROOT/config['source_manifest']).read_bytes()
    require(sha256(raw).hexdigest() == config['source_manifest_sha256'], 'source archive manifest changed')
    sources = [item for part in json.loads(raw)['parts'] for item in part['sources']
               if item['name'].startswith('v3-comparison-graph-'+profile+'--')]
    require(len(sources) == 80, 'saved campaign census differs')
    design = json.loads((ROOT/'configs/v3_comparison_design_v3.json').read_text())['design']
    expected_names = {f'v3-comparison-graph-{profile}--{placement}--{law}--r{rep}-{config["main_run"]}'
                      for placement in design['placements'] for law in design['laws'] for rep in design['repetitions']}
    require({item['name'] for item in sources} == expected_names, 'source campaign identities differ')
    rows, absent, receipts = [], [], []
    for ordinal, item in enumerate(sorted(sources, key=lambda s: s['name'])):
        metadata = transport.read_api(f'actions/artifacts/{item["artifact_id"]}')
        require(metadata['name'] == item['name'] and metadata['workflow_run']['id'] == config['main_run']
                and metadata['workflow_run']['head_sha'] == config['main_head'] and not metadata['expired'], 'source provider identity differs')
        raw_zip = transport.api(f'actions/artifacts/{item["artifact_id"]}/zip')
        require(len(raw_zip) == item['bytes'] == metadata['size_in_bytes']
                and sha256(raw_zip).hexdigest() == item['sha256']
                and metadata['digest'] == 'sha256:'+item['sha256'], 'source ZIP digest/size differs')
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
            infos = archive.infolist()
            require(len(infos) == item['members'] and sum(i.file_size for i in infos) == item['uncompressed_bytes'], 'ZIP census differs')
            require(len({i.filename for i in infos}) == len(infos)
                    and all(not PurePosixPath(i.filename).is_absolute() and '..' not in PurePosixPath(i.filename).parts for i in infos)
                    and archive.testzip() is None, 'invalid ZIP members/CRC')
            models = json.loads(archive.read('candidates/models.json'))
            candidate = json.loads(archive.read('candidates/candidates.json'))
            compact = json.loads(archive.read('compact/results.json'))
        identity = candidate['identity']
        require(identity == compact['identity'] and identity['application'] == profile, 'campaign identity mismatch')
        key = profile+'--'+identity['placement']+'--'+identity['law']+'--r'+str(identity['repetition'])
        require(item['name'] == f'v3-comparison-graph-{key}-{config["main_run"]}', 'model campaign differs')
        require(set(candidate['forecasts']) == set(design['applications'][profile]), 'operation census differs')
        receipts.append(dict(artifact_id=item['artifact_id'], name=item['name'], bytes=len(raw_zip), sha256=item['sha256']))
        for op in sorted(candidate['forecasts']):
            case_id = key+'--'+op
            if op not in models['execution']:
                forecast = candidate['forecasts'][op]['Gstar']
                require(forecast['status'] == 'unsupported' and 'identified_lower' not in forecast, 'unexpected missing model')
                absent.append(dict(case_id=case_id, operation=op, identity=identity, source=receipts[-1], status='structurally_unsupported', reason=forecast['reason']))
                continue
            model = models['execution'][op]
            reference = compact['operation_diagnostics'][op]
            variants = dict(Gstar='execution', GID='reachability', Gselected='selected',
                            G_without_deadline='without_deadline', G_without_selection='without_selection', G_without_completion='without_completion')
            for method, variant in variants.items():
                f = candidate['forecasts'][op][method]; ex = reference['estimates'][variant]
                if ex['prediction'] is None:
                    require(f['status'] == 'unsupported' and f['lower_exact'] == ex['lower_exact'] and f['upper_exact'] == ex['upper_exact'], 'saved bound forecast differs')
                else:
                    require(f['status'] == 'ok' and f['exact_fraction'] == ex['lower_exact'] and f['probability'] == ex['prediction'], 'saved point forecast differs')
            rows.append(dict(case_id=case_id, model=model, reference=dict(estimates=reference['estimates']),
                             source=receipts[-1], identity=identity, operation=op, axis='application', parameters={}))
        if ordinal % 10 == 0: print(f'{profile}: verified source {ordinal+1}/80', flush=True)
    return rows, absent, receipts


def endpoint_hash(result):
    return digest([{name: [ex['minimum'], ex['maximum']] for name, ex in cert['extrema'].items()}
                   for cert in result['category_certificates']])


def timeout_handler(signum, frame): raise TimeoutError('declared 60-second case budget exceeded')


def worker(args, config):
    import dd.cudd as native
    require(Path(native.__file__).suffix == '.so', 'native CUDD extension required')
    rows = json.loads(args.input.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGALRM, timeout_handler)
    records = []
    with gzip.open(args.out/'certificates.jsonl.gz', 'wt') as full:
        for ordinal, row in enumerate(rows):
            model = row['model']; compiled = None; current = None; result = None
            record = dict(case_id=row['case_id'], method=args.method, round=args.round, status='failed')
            try:
                gc.collect()
                signal.alarm(config['case_timeout_seconds'])
                cpu = time.process_time_ns(); tick = time.perf_counter_ns()
                if args.method == 'specialized': result = solve(model)
                else:
                    compiled = CompiledModel(model, args.method)
                    result = compiled.solve()
                cold = time.perf_counter_ns()-tick; cold_cpu = time.process_time_ns()-cpu
                checks = verify_result(model, result, row['reference'])
                reference_hash = endpoint_hash(result)
                warm, warm_cpu = [], []
                for _ in range(config['warm_queries']):
                    cpu = time.process_time_ns(); tick = time.perf_counter_ns()
                    current = solve(model) if compiled is None else compiled.solve()
                    warm.append(time.perf_counter_ns()-tick); warm_cpu.append(time.process_time_ns()-cpu)
                    verify_result(model, current, row['reference'])
                    require(endpoint_hash(current) == reference_hash, 'warm category extrema differ')
                    current = None
                stats = None if compiled is None else compiled.statistics()
                record.update(status='qualified', cold_ns=cold, cold_cpu_ns=cold_cpu, warm_ns=warm, warm_cpu_ns=warm_cpu,
                    build_seconds=0.0 if compiled is None else compiled.build_seconds,
                    reorder_seconds=0.0 if compiled is None else compiled.reorder_seconds,
                    exact_estimates_sha256=digest(result['estimates']), category_extrema_sha256=reference_hash,
                    checks=checks, evaluated_states=result.get('evaluated_states'),
                    cudd=None if stats is None else dict(execution_dag_nodes=stats['root_dag_nodes']['execution'],
                        manager_nodes=stats['manager']['n_nodes'], manager_peak_nodes=stats['manager']['peak_nodes'],
                        manager_bytes=stats['manager']['mem'], reorderings=stats['manager']['n_reorderings']))
                full.write(json.dumps(dict(case_id=row['case_id'], method=args.method, round=args.round,
                                            result=result, statistics=stats), allow_nan=False)+'\n')
            except Exception as exc:
                record['error'] = type(exc).__name__+': '+str(exc)
            finally:
                signal.alarm(0)
            records.append(record)
            if ordinal % 50 == 0: print(f'{args.method} round {args.round}: {ordinal+1}/{len(rows)} {record["status"]}', flush=True)
            result = None; current = None; compiled = None
    write(args.out/'records.json', records)
    require(all(r['status'] == 'qualified' for r in records), 'worker has failed cases')


def run(args, config):
    import dd
    import dd.cudd as native
    require(Path(native.__file__).suffix == '.so', 'native CUDD extension required')
    require(sha256((ROOT/'src/telemetry_availability/graph_execution_model_v1.py').read_bytes()).hexdigest() == config['frozen_core_sha256'], 'frozen exact core changed')
    args.out.mkdir(parents=True, exist_ok=False)
    compact = args.out/'compact'; compact.mkdir()
    (compact/'protocol.json').write_bytes(CONFIG.read_bytes())
    environment = dict(profile=args.profile, run_id=int(os.environ['GITHUB_RUN_ID']), head=os.environ['GITHUB_SHA'],
        config_sha256=sha256(CONFIG.read_bytes()).hexdigest(), python=sys.version, platform=platform.platform(),
        cpu_count=os.cpu_count(), cpu_info=Path('/proc/cpuinfo').read_text(), memory_info=Path('/proc/meminfo').read_text(),
        dd_version=dd.__version__, native_version=getattr(native, '__version__', None), native_file=native.__file__,
        native_sha256=sha256(Path(native.__file__).read_bytes()).hexdigest(),
        installed_packages=subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True))
    write(compact/'environment.json', environment)
    rows, absent, receipts = prepare(args.profile, config, args.out)
    rows.sort(key=lambda row: row['case_id'])
    index = config['profiles'].index(args.profile)
    require(len(rows) == config['expected_models'][index] and len(rows)+len(absent) == config['expected_cases'][index], 'case/model census differs')
    require(sum(r['reference']['estimates']['execution']['prediction'] is None for r in rows) == config['expected_intervals'][index], 'interval census differs')
    input_path = args.out/'full-inputs.json'; write(input_path, rows)
    cases = []
    for row in rows:
        model = row['model']; controls = control_ids(model)
        cases.append(dict(case_id=row['case_id'], axis=row['axis'], parameters=row['parameters'], source=row['source'],
            model_sha256=digest(model), estimates=row['reference']['estimates'],
            nodes=len(model['graph']['services']), edges=len(model['graph']['edges']),
            controls=len(controls), completions=len(model['completion_signals']), coordinates=len(model['signal_ids']),
            categories=len(model['observation_categories']), sample_count=model['sample_count'],
            max_unknown_controls=max(sum(value is None and name in controls for name, value in zip(model['signal_ids'], cat['values'])) for cat in model['observation_categories'])))
    summary = dict(version=config['version'], profile=args.profile, run_id=environment['run_id'], head=environment['head'],
                   config_sha256=environment['config_sha256'], cases=cases, absent=absent, sources=receipts,
                   records=[], process_resources=[], new_application_campaigns=0, qualified=False)
    write(compact/'results.json', summary)
    for repetition in range(config['technical_rounds']):
        offset = (index+repetition) % 4
        methods = config['methods'][offset:]+config['methods'][:offset]
        for method in methods:
            dest = args.out/'workers'/f'r{repetition}-{method}'; dest.mkdir(parents=True)
            command = ['/usr/bin/time', '-f', '%e %U %S %M %x', '-o', str(dest/'resource.txt'), sys.executable,
                str(Path(__file__).resolve()), 'worker', '--input', str(input_path), '--out', str(dest),
                '--method', method, '--round', str(repetition)]
            started = time.perf_counter()
            try:
                completed = subprocess.run(command, timeout=config['worker_timeout_seconds'], check=False)
                returncode, timed_out = completed.returncode, False
            except subprocess.TimeoutExpired:
                returncode, timed_out = None, True
            resource = dict(method=method, round=repetition, returncode=returncode, timed_out=timed_out,
                            parent_wall_seconds=time.perf_counter()-started)
            if (dest/'resource.txt').exists():
                values = (dest/'resource.txt').read_text().strip().splitlines()[-1].split()
                if len(values) == 5:
                    resource.update(wall_seconds=float(values[0]), user_seconds=float(values[1]), system_seconds=float(values[2]),
                                    peak_rss_kib=int(values[3]), resource_exit_code=int(values[4]))
            summary['process_resources'].append(resource)
            found = json.loads((dest/'records.json').read_text()) if (dest/'records.json').exists() else []
            require(len({r['case_id'] for r in found}) == len(found), 'duplicate worker case')
            by_id = {r['case_id']:r for r in found}
            require(set(by_id) <= {r['case_id'] for r in rows}, 'unplanned worker case')
            for row in rows:
                summary['records'].append(by_id.get(row['case_id'], dict(case_id=row['case_id'], method=method,
                    round=repetition, status='failed', error='worker failed or timed out before persistent record')))
            write(compact/'results.json', summary)
    for case in cases:
        values = [r for r in summary['records'] if r['case_id'] == case['case_id']]
        require(len(values) == 12, 'planned comparison census differs')
        hashes = {r.get('category_extrema_sha256') for r in values}
        if all(r['status'] == 'qualified' for r in values) and len(hashes) != 1:
            for r in values: r.update(status='failed', error='category extrema disagree across exact solvers')
    summary['qualified'] = all(r['status'] == 'qualified' for r in summary['records']) and all(r['returncode'] == 0 for r in summary['process_resources'])
    write(compact/'results.json', summary)
    print(json.dumps(dict(profile=args.profile, models=len(cases), absent=len(absent), records=len(summary['records']),
                          statuses=dict(Counter(r['status'] for r in summary['records'])), qualified=summary['qualified'])), flush=True)
    require(summary['qualified'], 'comparison has unresolved failures')


def main():
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'real model parsing and benchmarks run only in GitHub Actions')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['run', 'worker'])
    parser.add_argument('--profile'); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--input', type=Path); parser.add_argument('--method'); parser.add_argument('--round', type=int)
    args = parser.parse_args(); config = json.loads(CONFIG.read_text())
    (worker if args.mode == 'worker' else run)(args, config)


if __name__ == '__main__': main()
