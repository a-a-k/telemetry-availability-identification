"""Remote matched pipeline timings and deterministic telemetry-volume scaling.

Scientific implementation and original accuracy results are unchanged. Copies
are computational workloads, never additional independent observations.
"""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import zipfile

from archive_h_exec_evidence_v1 import require, verify_zip
import retain_v3_comparison_compact_v4 as transport

ROOT = Path('workflow-benchmark')
CONFIG = Path('configs/v3_pipeline_benchmark_v1.json')
SCIENTIFIC_HEAD = 'd857ea65ca9da7fa9ae4ee1198317487475246a7'


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(transport.encoded(value))


def file_sha(path):
    h = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def replicate(requests, native, multiplier):
    """Preserve each observation, mask, time and edge; only rename copy IDs."""
    require(type(multiplier) is int and multiplier in (1, 2, 4), 'unsupported workload multiplier')
    require(len({r['trace_id'] for r in requests}) == len(requests), 'duplicate source traces')
    output = []
    traces = dict(calibration_only=True, selected_trace_ids=[], spans={})
    for copy in range(multiplier):
        for original in requests:
            old_trace = original['trace_id']
            new_trace = old_trace if copy == 0 else sha256(f'{copy}/{old_trace}'.encode()).hexdigest()[:len(old_trace)]
            row = deepcopy(original)
            row['trace_id'] = new_trace
            if copy:
                row['request_id'] = str(original['request_id']) + f'-benchmark-copy-{copy}'
            output.append(row)
            traces['selected_trace_ids'].append(new_trace)
            if old_trace in native['spans']:
                spans = deepcopy(native['spans'][old_trace])
                id_map = {s[key]: sha256(f'{copy}/{old_trace}/{s[key]}'.encode()).hexdigest()[:len(s[key])]
                          for s in spans for key in ('span_id', 'parent_id') if s[key]}
                for span in spans:
                    span['trace_id'] = new_trace
                    if copy:
                        span['span_id'] = id_map[span['span_id']]
                        if span['parent_id']:
                            span['parent_id'] = id_map[span['parent_id']]
                traces['spans'][new_trace] = spans
    require(len({r['trace_id'] for r in output}) == len(output)
            and len({r['request_id'] for r in output}) == len(output), 'copy ID collision')
    return output, traces


def download(item, destination):
    destination.mkdir(parents=True, exist_ok=False)
    data = transport.api(f'actions/artifacts/{item["id"]}/zip')
    archive = destination/'source.zip'
    archive.write_bytes(data)
    info = verify_zip(archive, item)
    require(info['uncompressed_bytes'] <= 800_000_000, 'oversized source role')
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(destination/'files')
    write(destination/'receipt.json', dict(artifact=item, verification=info))
    return destination/'files'


def prepare(profile):
    from telemetry_availability.v3_ordinary_identity_v2 import load_bundle
    from telemetry_availability.v3_comparison_roles_v1 import load_role, seal_role, write_ordinary
    config = read(CONFIG)
    sources = config['applications'][profile]
    ordinary_root = download(sources['ordinary'], ROOT/'source/ordinary')
    pmx_root = download(sources['pmx'], ROOT/'source/pmx')
    download(config['controls'], ROOT/'source/controls')
    ordinary, _ = load_bundle(ordinary_root)
    pmx, _ = load_role(pmx_root, 'pmx_calibration')
    require(ordinary['requests.json'] == pmx['requests.json'], 'methods receive different request pools')
    require(ordinary['manifest.json']['identity'] == sources['identity'], 'source identity differs')
    for multiplier in config['multipliers']:
        target = ROOT/'inputs'/f'x{multiplier}'
        identity = dict(sources['identity'], namespace=f'v3-computational-benchmark-x{multiplier}', data_role='artificial_control')
        data = deepcopy(ordinary)
        data['requests.json'], data['native.json'] = replicate(ordinary['requests.json'], ordinary['native.json'], multiplier)
        data['manifest.json'].update(identity=identity, data_role='artificial_control', external_attempts=len(data['requests.json']))
        write_ordinary(target/'ordinary', data)
        del data
        data = deepcopy(pmx)
        data['requests.json'], data['native.json'] = replicate(pmx['requests.json'], pmx['native.json'], multiplier)
        data['manifest.json'].update(identity=identity, computational_replication=multiplier)
        seal_role(target/'pmx', 'pmx_calibration', identity, data)
        request_count = len(data['requests.json'])
        span_count = sum(len(x) for x in data['native.json']['spans'].values())
        del data
        settings = read('configs/v3_comparison_execution_v3.json')
        for spec in settings['profiles'][profile]['operations'].values():
            spec['expected_attempts'] *= multiplier
        write(target/'execution.json', settings)
        write(target/'workload.json', dict(multiplier=multiplier, attempts=request_count, native_spans=span_count,
              probe_observations=len(ordinary['probes.json']), source_identity=sources['identity'],
              independent_new_observations=0, identity=identity,
              files={p.relative_to(target).as_posix(): dict(bytes=p.stat().st_size,sha256=file_sha(p))
                     for p in target.rglob('*') if p.is_file()}))
    write(ROOT/'compact/protocol.json', config)
    write(ROOT/'compact/environment.json', dict(profile=profile, workflow_head=os.environ['GITHUB_SHA'],
          scientific_head=SCIENTIFIC_HEAD, workflow_run=os.environ['GITHUB_RUN_ID'], python=sys.version,
          platform=platform.platform(), cpu_count=os.cpu_count(),
          cpu_info=Path('/proc/cpuinfo').read_text(), memory_info=Path('/proc/meminfo').read_text(),
          source_artifacts={key:sources[key] for key in ('ordinary','pmx')}, source_models_previously_opened=True))


def resource_record(path):
    from telemetry_availability.v3_resource_summary_v1 import summarize
    path = Path(path)
    return next(r for r in summarize(path.parent)['records'] if r['path'] == path.name)


def timed(command, prefix, env, timeout=1800):
    prefix.parent.mkdir(parents=True, exist_ok=True)
    resource_path = prefix.with_name(prefix.name+'-resource-usage.txt')
    started = time.perf_counter()
    with prefix.with_suffix('.log').open('wb') as stream:
        process = subprocess.Popen(['/usr/bin/time','-v','-o',str(resource_path),*map(str,command)],
                                   stdout=stream,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        expired = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            expired = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    return dict(command=list(map(str,command)), wall_seconds=time.perf_counter()-started,
                exit_code=process.returncode, timed_out=expired,
                resource=resource_record(resource_path) if resource_path.exists() else None)


def command_ok(record):
    require(record['exit_code'] == 0 and not record['timed_out'], 'benchmark command failed: '+str(record['command']))


def signatures(forecasts):
    return {op:{name:{k:v for k,v in f.items() if k in ('status','probability','reason','identified_lower','identified_upper')}
                for name,f in methods.items()} for op,methods in forecasts.items()}


def graph_trial(target, inputs, env):
    tick = time.perf_counter()
    base = [sys.executable,'-m','telemetry_availability.v3_comparison_candidates_v1']
    stages = {}
    stages['build'] = timed(base+['build','--input',inputs/'ordinary','--output',target/'graph',
                           '--config',inputs/'execution.json'],target/'graph-build',env)
    command_ok(stages['build'])
    stages['replay'] = timed(base+['replay','--input',target/'graph/candidates','--output',target/'graph/replay',
                            '--config',inputs/'execution.json'],target/'graph-replay',env)
    command_ok(stages['replay'])
    seconds = time.perf_counter()-tick
    candidate = read(target/'graph/candidates/candidates.json')
    models = read(target/'graph/candidates/models.json')['execution']
    return dict(wall_seconds=seconds, stages=stages, forecasts=signatures(candidate['forecasts']),
                model_structure={op:dict(nodes=len(m['graph']['services']),edges=len(m['graph']['edges']),
                     coordinates=len(m['signal_ids']),categories=len(m['observation_categories']),samples=m['sample_count'])
                     for op,m in models.items()}, saved_candidate_sha256=file_sha(target/'graph/candidates/candidates.json'))


def pmx_trial(target, inputs, env, profile):
    tick = time.perf_counter()
    base = [sys.executable,'-m','telemetry_availability.v3_comparison_pmx_v3']
    stages = {}
    pmx_env = dict(env, JAVA_HOME=os.environ['PMX_JAVA_HOME'],
                   PATH=os.environ['PMX_JAVA_HOME']+'/bin'+os.pathsep+env['PATH'])
    stages['extract'] = timed(base+['extract','--source',inputs/'pmx','--out',target/'extractions/application',
             '--config',inputs/'execution.json','--options','workflow-input/Options.txt',
             '--jar','workflow-input/pmx-clock-build/main-clock-progress-v1.jar'],target/'pmx-extract',pmx_env)
    command_ok(stages['extract'])
    # Link verified control records and models without including their original native projections.
    controls = ROOT/'source/controls/files'
    for record in controls.glob('extraction-*.json'):
        (target/'extractions'/record.name).symlink_to(record.resolve())
    (target/'extractions/models').symlink_to((controls/'models').resolve(),target_is_directory=True)
    stages['collect'] = timed(base+['collect','--source',target/'extractions','--out',target/'pmx-contract',
                                   '--profile',profile],target/'pmx-collect',env)
    command_ok(stages['collect'])
    prepared = read(target/'pmx-contract/solver-contract.json')
    solve_env = dict(env, TAID_PALLADIO_ALIGNED_ROOT=str((target/'pmx-contract/models').resolve()),
                     TAID_PALLADIO_RESULT=str((target/'pmx-solver/raw-result.json').resolve()),
                     TAID_REPEAT_RUNS='2',TAID_EXPECTED_MODEL_COUNT=str(prepared['model_count']),
                     TAID_EXPECTED_CASE_COUNT=str(prepared['model_count']),TAID_PROBABILITY_TOLERANCE='1e-12')
    (target/'pmx-solver').mkdir()
    stages['solve'] = timed(['xvfb-run','-a','mvn','-B','-ntp',
          '-Dmaven.repo.local='+os.environ['PETCLINIC_PMX_MAVEN_REPO'], '-f','palladio-source/pom.xml','verify'],
          target/'pmx-solve',solve_env)
    command_ok(stages['solve'])
    stages['freeze'] = timed(base+['freeze','--source',target/'pmx-contract','--out',target/'pmx-candidates',
                                  '--solver',target/'pmx-solver'],target/'pmx-freeze',env)
    command_ok(stages['freeze'])
    seconds = time.perf_counter()-tick
    controls_result = read(target/'pmx-candidates/controls.json')
    require(controls_result['qualified'], 'known-probability solver controls failed')
    paths = list((target/'pmx-candidates').glob('campaign-*/candidates.json'))
    require(len(paths) == 1, 'one campaign expected')
    candidate = read(paths[0])
    return dict(wall_seconds=seconds, stages=stages, forecasts=signatures(candidate['forecasts']),
          models=prepared['model_count'], controls_qualified=True,
          saved_candidate_sha256=file_sha(paths[0]),
          solver_records=read(target/'pmx-solver/raw-result.json')['runs'])


def check_forecasts(actual, expected):
    require(set(actual) == set(expected), 'operation forecast census changed')
    for op, methods in expected.items():
        for name, forecast in methods.items():
            current = actual[op][name]
            require(current['status'] == forecast['status'], 'forecast support changed')
            for key in ('probability','identified_lower','identified_upper'):
                a,b = current.get(key),forecast.get(key)
                require((a is None and b is None) or (a is not None and b is not None and abs(a-b)<=1e-12),
                        'replicated workload forecast changed')


def run(profile):
    config = read(CONFIG)
    env = dict(os.environ,GITHUB_SHA=SCIENTIFIC_HEAD)
    results = dict(version='v3-pipeline-benchmark-v1',profile=profile,workflow_head=os.environ['GITHUB_SHA'],
                   run_id=int(os.environ['GITHUB_RUN_ID']),config_sha256=file_sha(CONFIG),
                   scientific_head=SCIENTIFIC_HEAD,new_independent_campaigns=0,records=[])
    for repetition, order in enumerate(config['scale_orders']):
        for multiplier in order:
            inputs = ROOT/'inputs'/f'x{multiplier}'
            target = ROOT/'trials'/f'r{repetition}-x{multiplier}'
            target.mkdir(parents=True)
            methods = ['graph','pmx'] if (repetition+config['multipliers'].index(multiplier))%2==0 else ['pmx','graph']
            row = dict(repetition=repetition,multiplier=multiplier,method_order=methods,
                       workload=read(inputs/'workload.json'),status='running')
            try:
                for method in methods:
                    print(json.dumps(dict(stage='benchmark',profile=profile,repetition=repetition,multiplier=multiplier,method=method)),flush=True)
                    row[method] = graph_trial(target,inputs,env) if method=='graph' else pmx_trial(target,inputs,env,profile)
                    check_forecasts(row[method]['forecasts'],config['applications'][profile]['expected'][method])
                row.update(status='qualified',original_forecasts_preserved=True,
                           speedup_pmx_over_graph=row['pmx']['wall_seconds']/row['graph']['wall_seconds'])
            except Exception as exc:
                row.update(status='failed',error=type(exc).__name__+': '+str(exc))
            results['records'].append(row)
            write(ROOT/'compact/results.json',results)
            print(json.dumps({k:row[k] for k in ('repetition','multiplier','status')}),flush=True)
    require(all(r['status']=='qualified' for r in results['records']), 'one or more benchmark trials failed; original records retained')


def main():
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_RUN_ATTEMPT')=='1', 'benchmark is remote only')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run'])
    parser.add_argument('--profile',required=True)
    args = parser.parse_args()
    require(args.profile in read(CONFIG)['applications'], 'unplanned application')
    (prepare if args.mode=='prepare' else run)(args.profile)


if __name__=='__main__':
    main()
