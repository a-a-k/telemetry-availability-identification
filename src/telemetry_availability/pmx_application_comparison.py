"""Development comparison with calibration-only independently extracted PMX models."""
import argparse
import csv
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import time

from .checkout_routing_model import _load_learner_cell
from .live_validation_analysis import prepare_mode, fit_exact_model, predict_cell
from .live_validation_config import load_frozen_live_validation_config
from .pmx_adapter_conformance import JAR_SHA, OPTIONS_SHA, compare_pcm, inspect_pcm
from .pmx_application_census import historical_learner_ids, validate as validate_application
from .pmx_composition_control import SUFFIXES, _download, _hash, _read, _remote, _write
from .pmx_observed_operations import read_native
from .pmx_pmf_bridge import qualify
from .pmx_request_adapter import project_campaign
from .pmx_request_conformance import validate as validate_request
from .pmx_request_pcm import bridge
from .pmx_request_census import truth
from .pmx_usage_contract_audit import reconstructed_inventory


def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream))


def validate(path):
    config = _read(path)
    validate_request(Path('configs/m9u_pmx_request_conformance.json'))
    for lock in config['repository_locks']:
        if _hash(Path(lock['path'])) != lock['sha256']:
            raise ValueError('frozen application comparison differs: '+lock['path'])
    return config


def accepted_request(config, inputs):
    acceptance = config['m9u_acceptance']
    metadata = _download(acceptance, inputs)
    path = inputs / 'm9u-census/request-conformance-census.json'
    if _hash(path) != acceptance['census_sha256']:
        raise ValueError('request conformance evidence differs')
    result = _read(path)
    if result['status'] != 'request_adapter_qualified' or result['oracle_passes'] != 44:
        raise ValueError('request adapter not qualified')
    return metadata


def comparator_predictions(directory):
    """The existing estimator receives learner files only, never PMX output."""
    config = load_frozen_live_validation_config('configs/m7_frozen_live.yaml')
    cell = _load_learner_cell(directory)
    results, diagnostics = [], []
    for mode in config.analysis.modes:
        if mode.id not in ('full', 'sampled_mixed'):
            continue
        started = time.perf_counter()
        prepared = prepare_mode(cell, mode, config.analysis)
        fit = fit_exact_model(cell, prepared, config.analysis)
        predictions = predict_cell(cell, prepared, fit, config.analysis, 'current')
        results.extend(row for row in predictions if row['method'] in ('proposed', 'B2', 'B0'))
        diagnostics.append({'mode': mode.id, 'preparation_and_fit_seconds': time.perf_counter()-started,
            'status': fit.status, 'current_identified': fit.current_identified,
            'trace_count': prepared.retained_traces, 'calibration_guarded': prepared.guarded_calibration,
            'calibration_unaligned': prepared.unaligned_calibration})
    for operation in config.analysis.operations[cell.profile]:
        outcomes = [r.success for r in cell.learner_requests if r.period == 'calibration' and r.operation == operation.id]
        results.append({'profile': cell.profile, 'source_placement': cell.placement,
            'target_placement': cell.placement, 'failure_law': cell.failure_law,
            'repetition': cell.repetition, 'operation': operation.id, 'method': 'endpoint_all',
            'mode': 'full', 'scope': 'current', 'prediction': sum(outcomes)/len(outcomes),
            'status': 'all_calibration_request_mle', 'calibration_requests': len(outcomes)})
    return results, diagnostics


def prepare(config_path, inputs, options, out):
    _remote()
    config = validate(config_path)
    accepted = accepted_request(config, inputs)
    application = validate_application(Path('configs/m9q_application_census.json'))
    metadata = _download(_read(Path('configs/m9t_pmx_request_census.json')), inputs)
    source = inputs / 'preserved/m8-preserved'
    inventory_path = inputs / 'inventory/file-inventory.csv'
    if _hash(inventory_path) != application['inventory_file_sha256']:
        raise ValueError('source inventory differs')
    inventory = {row['relative_path'].replace('\\', '/'): row for row in rows(inventory_path)
                 if row['evidence_group'] == 'raw_audit_sample'}
    learners = {}
    for path in (source / 'qualified').rglob('learner/manifest.json'):
        manifest = _read(path)
        if manifest.get('failure_law') == 'NCD' and manifest.get('repetition') == 0:
            key = manifest['profile'], manifest['placement']
            if key in learners:
                raise ValueError('duplicate learner identity')
            learners[key] = path, manifest
    if _hash(options) != OPTIONS_SHA:
        raise ValueError('PMX options differ')
    original_options = options.read_text()
    if original_options.count('traces/jaegercustomers.json') != 1:
        raise ValueError('PMX input path differs')
    sample_reports = []
    for sample in application['samples']:
        started = time.perf_counter()
        raw = source / 'raw-audit-samples' / sample['artifact_directory']
        for name in ('campaign-manifest.json', 'trace-join.csv', sample['native_file']):
            record = inventory[sample['artifact_directory']+'/'+name]
            path = raw / name
            if _hash(path) != record['sha256'] or path.stat().st_size != int(record['size_in_bytes']):
                raise ValueError('native source differs')
        manifest_path, manifest = learners[sample['profile'], sample['placement']]
        learner = manifest_path.parent
        for filename, key in (('requests.csv', 'requests_sha256'), ('health.csv', 'health_sha256'),
                              ('deployment.json', 'deployment_sha256'), ('topology-edges.csv', 'topology_edges_sha256')):
            if _hash(learner / filename) != manifest['files'][key]:
                raise ValueError('learner source differs: '+filename)
        requests = rows(learner / 'requests.csv')
        selected, selection = historical_learner_ids(raw / 'trace-join.csv')
        if len(requests) != 3840 or {row['trace_id'].lower() for row in requests} != selected:
            raise ValueError('learner membership differs')
        calibration = [row for row in requests if row['period'] == 'calibration']
        analysis = load_frozen_live_validation_config('configs/m7_frozen_live.yaml').analysis
        if ({r['operation'] for r in calibration} != {operation.id for operation in analysis.operations[sample['profile']]}
                or len(calibration) != 3600):
            raise ValueError('user-operation calibration matrix differs')
        native_started = time.perf_counter()
        grouped, parse = read_native(raw / sample['native_file'], {r['trace_id'] for r in calibration}, sample['native_format'])
        native_seconds = time.perf_counter()-native_started
        policy = 'explicit_server' if sample['profile'] == 'opentelemetry_demo' else 'service_boundary'
        cases = []
        for operation in sorted({r['operation'] for r in calibration}):
            projection_started = time.perf_counter()
            selected_requests = [r for r in calibration if r['operation'] == operation]
            result = project_campaign(grouped, selected_requests, policy, sample['declared_host'], parse['invalid_traces'])
            case_id = sample['key']+'--'+operation
            root = out / 'cases' / case_id
            for key in ('mapping', 'native_audit', 'request_audit', 'rejected_requests', 'operation_oracle', 'edge_oracle', 'summary'):
                _write(root / (key+'.json'), result[key])
            _write(root / 'traces/observed.json', result['envelope'])
            (root / 'Options.txt').write_text(original_options.replace('traces/jaegercustomers.json', 'traces/observed.json'))
            expected = {'operations': {r['operation']: r['inclusive_probability'] for r in result['operation_oracle']},
                'operation_components': {r['operation']: r['component'] for r in result['operation_oracle']},
                'component_hosts': {r['pmx_component']: sample['declared_host'].upper()+'-SRV' for r in result['mapping']},
                'edges': sorted([[r['caller'], r['callee']] for r in result['edge_oracle']]),
                'entry_operation_counts': {key: 1 for key in result['entry_counts']}, 'leaf_operation_seconds': {}}
            _write(root / 'expected.json', expected)
            cases.append({'case_id': case_id, 'operation': operation, 'sample': sample,
                'summary': result['summary'], 'projection_seconds': time.perf_counter()-projection_started,
                'files': {p.relative_to(root).as_posix(): _hash(p) for p in root.rglob('*') if p.is_file()}})
        predictions, diagnostics = comparator_predictions(learner.parent)
        _write(out / 'comparators' / (sample['key']+'.json'), {'predictions': predictions, 'diagnostics': diagnostics,
            'learner_files': manifest['files'], 'evaluator_rows_read': 0})
        sample_reports.append({'sample': sample, 'cases': cases, 'parse': parse, 'selection': selection,
            'native_parse_seconds': native_seconds, 'prepare_seconds': time.perf_counter()-started,
            'native_file_bytes': (raw / sample['native_file']).stat().st_size,
            'learner_relative_path': learner.parent.relative_to(source).as_posix(),
            'source_native_sha256': _hash(raw / sample['native_file']), 'source_learner_files': manifest['files']})
    _write(out / 'application-input-contract.json', {'head_sha': os.environ['GITHUB_SHA'],
        'run_id': os.environ['GITHUB_RUN_ID'], 'config_sha256': _hash(config_path),
        'samples': sample_reports, 'source_artifacts': metadata, 'request_acceptance': accepted,
        'evaluator_rows_read': 0, 'development_data': True,
        'files': {p.relative_to(out).as_posix(): _hash(p) for p in out.rglob('*') if p.is_file()}})


def run_application_pmx(jar, root, out, limit=1800):
    _remote()
    if _hash(jar) != JAR_SHA:
        raise ValueError('PMX binary differs')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'results').mkdir()
    shutil.copyfile(root / 'Options.txt', out / 'Options.txt')
    shutil.copytree(root / 'traces', out / 'traces')
    commands = 'main:main -of Options.txt\nexit 0\n'
    (out / 'stdin.txt').write_text(commands)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    with (out / 'stdout.log').open('wb') as stream:
        process = subprocess.Popen(['/usr/bin/time', '-v', '-o', 'resource-usage.txt', 'timeout',
            '--signal=TERM', '--kill-after=10s', str(limit)+'s', 'java',
            '-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector',
            '-jar', str(jar.resolve())], cwd=out, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT)
        time.sleep(20)
        process.communicate(commands.encode(), timeout=limit+30)
    result = {'elapsed_seconds': time.perf_counter()-started, 'started_at': started_at,
        'finished_at': datetime.now(timezone.utc).isoformat(), 'exit_code': process.returncode,
        'startup_seconds': 20, 'internal_watchdog_seconds': limit, 'jar_sha256': JAR_SHA}
    _write(out / 'execution.json', result)
    return result


def extract(config_path, contract, sample_key, jar, out):
    _remote()
    validate(config_path)
    inputs = _read(contract / 'application-input-contract.json')
    if inputs['head_sha'] != os.environ['GITHUB_SHA'] or inputs['config_sha256'] != _hash(config_path):
        raise ValueError('mixed application input provenance')
    sample = next(row for row in inputs['samples'] if row['sample']['key'] == sample_key)
    rows_out, models = [], []
    for case in sample['cases']:
        root = contract / 'cases' / case['case_id']
        for name, digest in case['files'].items():
            if _hash(root / name) != digest:
                raise ValueError('projection input differs')
        row = {'case_id': case['case_id'], 'qualified': False, 'variants': []}
        raw = out / 'raw' / case['case_id']
        try:
            if case['summary']['rejected_requests'] or case['summary']['projected_requests'] != 1200:
                raise ValueError('incomplete request population')
            row['execution'] = run_application_pmx(jar, root, raw)
            actual = inspect_pcm(raw / 'results')
            _write(raw / 'resolved-pcm.json', actual)
            row.update(compare_pcm(actual, _read(root / 'expected.json')))
            inventory = reconstructed_inventory((raw / 'stdout.log').read_text(errors='replace'), _read(root / 'traces/observed.json'))
            row['reconstruction'] = inventory
            row['qualified'] = row['qualified'] and row['execution']['exit_code'] == 0 and all(value for value in inventory.values() if isinstance(value, bool))
            if not row['qualified']:
                raise ValueError('application projection fidelity differs')
            oracle = _read(root / 'operation_oracle.json')
            for variant in ('inclusive', 'conditional_local'):
                if variant == 'conditional_local' and case['summary']['unsupported_conditional_local_operations']:
                    row['variants'].append({'variant': variant, 'status': 'unsupported_conditional_propagation_or_positivity'})
                    continue
                try:
                    model_id = case['case_id']+'--'+variant
                    target = out / 'models' / model_id
                    target.mkdir(parents=True, exist_ok=False)
                    for suffix in SUFFIXES:
                        shutil.copyfile(raw / 'results' / ('extracted.'+suffix), target / ('extracted.'+suffix))
                    started = time.perf_counter()
                    updated, changes = bridge((target / 'extracted.repository').read_text(), oracle, variant)
                    (target / 'extracted.repository').write_text(updated)
                    model = {'model_id': model_id, 'case_id': case['case_id'], 'variant': variant,
                        'sample': case['sample'], 'operation': case['operation'], 'changes': changes,
                        'bridge_seconds': time.perf_counter()-started, 'files': {p.name: _hash(p) for p in target.iterdir()}}
                    models.append(model)
                    row['variants'].append({'variant': variant, 'status': 'prepared', 'model_id': model_id})
                except Exception as exc:
                    row['variants'].append({'variant': variant, 'status': 'bridge_error', 'error': f'{type(exc).__name__}: {exc}'})
        except Exception as exc:
            row['qualified'] = False
            row['error'] = f'{type(exc).__name__}: {exc}'
        _write(out / 'decisions' / (case['case_id']+'.json'), row)
        rows_out.append(row)
    _write(out / ('extraction-'+sample_key+'.json'), {'sample_key': sample_key, 'cases': rows_out,
        'models': models, 'head_sha': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID'],
        'config_sha256': _hash(config_path), 'evaluator_rows_read': 0})


def collect(config_path, extractions, out):
    _remote()
    validate(config_path)
    records, models = [], []
    for path in sorted(extractions.rglob('extraction-*.json')):
        record = _read(path)
        if record['head_sha'] != os.environ['GITHUB_SHA'] or record['config_sha256'] != _hash(config_path):
            raise ValueError('mixed extraction provenance')
        for model in record['models']:
            source = path.parent / 'models' / model['model_id']
            for name, digest in model['files'].items():
                if _hash(source / name) != digest:
                    raise ValueError('extracted model differs')
            shutil.copytree(source, out / 'models' / model['model_id'])
            models.append(model)
        records.append(record)
    if len(records) != 4 or len({r['sample_key'] for r in records}) != 4:
        raise ValueError('incomplete extraction job census')
    _write(out / 'solver-contract.json', {'models': models, 'extractions': records,
        'model_count': len(models), 'config_sha256': _hash(config_path),
        'head_sha': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID']})


def freeze_candidates(config_path, contract, solver, inputs, out):
    _remote()
    validate(config_path)
    prepared = _read(contract / 'solver-contract.json')
    if prepared['head_sha'] != os.environ['GITHUB_SHA'] or prepared['config_sha256'] != _hash(config_path):
        raise ValueError('mixed solver model provenance')
    raw_path = solver / 'raw-result.json'
    raw = _read(raw_path)['runs'] if raw_path.exists() else []
    keys = [(r.get('model_id'), r.get('repetition')) for r in raw]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate solver result')
    model_lookup = {r['model_id']: r for r in prepared['models']}
    wanted = {(key, repeat) for key in model_lookup for repeat in (0, 1)}
    if any(key not in wanted for key in keys):
        raise ValueError('unexpected solver result')
    predictions, census = [], []
    for path in sorted((inputs / 'comparators').glob('*.json')):
        predictions.extend(_read(path)['predictions'])
    application = _read(inputs / 'application-input-contract.json')
    if application['head_sha'] != os.environ['GITHUB_SHA'] or application['config_sha256'] != _hash(config_path):
        raise ValueError('mixed comparison input provenance')
    for name, digest in application['files'].items():
        if _hash(inputs / name) != digest:
            raise ValueError('comparison input changed')
    extraction_cases = {case['case_id']: case for record in prepared['extractions'] for case in record['cases']}
    for sample in application['samples']:
        for case in sample['cases']:
            for variant in ('inclusive', 'conditional_local'):
                model_id = case['case_id']+'--'+variant
                results = [r for r in raw if r.get('model_id') == model_id]
                valid = (len(results) == 2 and all(qualify(r, None)['valid_probability'] for r in results)
                    and abs(results[0]['success_probability']-results[1]['success_probability']) <= 1e-12)
                model = model_lookup.get(model_id)
                if model:
                    for name, digest in model['files'].items():
                        if _hash(contract / 'models' / model_id / name) != digest:
                            raise ValueError('solved input model changed')
                source = case['sample']
                prediction = {'profile': source['profile'], 'source_placement': source['placement'],
                    'target_placement': source['placement'], 'failure_law': 'NCD', 'repetition': 0,
                    'operation': case['operation'], 'method': 'PMX_'+variant, 'mode': 'full',
                    'scope': 'current', 'prediction': results[0]['success_probability'] if valid else '',
                    'status': 'valid_independent_pmx_forecast' if valid else 'no_valid_pmx_forecast'}
                predictions.append(prediction)
                census.append({'model_id': model_id, 'case_id': case['case_id'], 'variant': variant,
                    'valid_prediction': valid, 'solver_records': results,
                    'projection': case['summary'], 'extraction': extraction_cases[case['case_id']]})
    _write(out / 'candidate-predictions.json', predictions)
    _write(out / 'coverage-census.json', census)
    _write(out / 'candidate-manifest.json', {'head_sha': os.environ['GITHUB_SHA'],
        'run_id': os.environ['GITHUB_RUN_ID'], 'config_sha256': _hash(config_path),
        'prediction_file_sha256': _hash(out / 'candidate-predictions.json'),
        'coverage_file_sha256': _hash(out / 'coverage-census.json'),
        'solver_matrix_complete': set(keys) == wanted, 'retained_solver_records': len(raw),
        'evaluator_rows_read': 0, 'development_data': True})


def evaluate(config_path, inputs, candidates, source_inputs, out):
    _remote()
    validate(config_path)
    manifest = _read(candidates / 'candidate-manifest.json')
    if manifest['head_sha'] != os.environ['GITHUB_SHA'] or manifest['config_sha256'] != _hash(config_path):
        raise ValueError('mixed candidate provenance')
    if _hash(candidates / 'candidate-predictions.json') != manifest['prediction_file_sha256']:
        raise ValueError('candidate predictions changed before scoring')
    predictions = _read(candidates / 'candidate-predictions.json')
    metadata = _download(_read(Path('configs/m9t_pmx_request_census.json')), source_inputs)
    source = source_inputs / 'preserved/m8-preserved'
    application = _read(inputs / 'application-input-contract.json')
    from .live_validation_analysis import load_qualified_cell, score_predictions
    analysis = load_frozen_live_validation_config('configs/m7_frozen_live.yaml').analysis
    scores, coverage = [], []
    for sample in application['samples']:
        cell = load_qualified_cell(source / sample['learner_relative_path'])
        matching = [r for r in predictions if r['profile'] == cell.profile and r['target_placement'] == cell.placement]
        scores.extend(score_predictions(matching, cell, analysis))
        coverage.extend({'profile': cell.profile, 'placement': cell.placement, 'method': r['method'],
            'mode': r['mode'], 'operation': r['operation'], 'available': r['prediction'] != '',
            'status': r['status']} for r in matching)
    groups = {}
    for row in scores:
        key = row['method'], row['mode'], row['view']
        groups.setdefault(key, []).append(row)
    aggregate = []
    for (method, mode, view), values in sorted(groups.items()):
        aggregate.append({'method': method, 'mode': mode, 'view': view, 'available_operation_cells': len(values),
            'expected_operation_cells': 12, **{field: sum(r[field] for r in values)/len(values) for field in
            ('prediction', 'test_success_fraction', 'brier_score', 'signed_prediction_error', 'absolute_prediction_error')}})
    paired = []
    score_lookup = {(r['profile'], r['target_placement'], r['operation'], r['method'], r['mode'], r['view']): r for r in scores}
    for row in scores:
        if row['method'] not in ('PMX_inclusive', 'PMX_conditional_local'):
            continue
        for comparator in ('proposed', 'B2', 'B0', 'endpoint_all'):
            key = row['profile'], row['target_placement'], row['operation'], comparator, 'full', row['view']
            reference = score_lookup.get(key)
            if reference is not None:
                paired.append({'profile': row['profile'], 'placement': row['target_placement'],
                    'operation': row['operation'], 'view': row['view'], 'method': row['method'],
                    'comparator': comparator, 'brier_difference_pmx_minus_comparator': row['brier_score']-reference['brier_score'],
                    'absolute_error_difference_pmx_minus_comparator': row['absolute_prediction_error']-reference['absolute_prediction_error']})
    _write(out / 'paired-operation-contrasts.json', paired)
    _write(out / 'scores.json', scores)
    _write(out / 'prediction-coverage.json', coverage)
    _write(out / 'development-summary.json', {'head_sha': os.environ['GITHUB_SHA'],
        'run_id': os.environ['GITHUB_RUN_ID'], 'config_sha256': _hash(config_path),
        'candidate_manifest_sha256': _hash(candidates / 'candidate-manifest.json'),
        'development_only': True, 'whole_traffic_primary_view': 'all_sequence',
        'aggregates': aggregate, 'partial_coverage_averages_not_directly_comparable': True,
        'source_artifacts': metadata, 'scores_sha256': _hash(out / 'scores.json')})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'prepare', 'extract', 'collect', 'freeze', 'evaluate'))
    parser.add_argument('--config', type=Path, default=Path('configs/m9v_pmx_application_comparison.json'))
    for key in ('inputs', 'options', 'out', 'contract', 'jar', 'solver', 'extractions', 'candidates', 'source-inputs'):
        parser.add_argument('--'+key, type=Path)
    parser.add_argument('--sample')
    args = parser.parse_args()
    if args.action == 'validate':
        validate(args.config)
    elif args.action == 'prepare':
        prepare(args.config, args.inputs, args.options, args.out)
    elif args.action == 'extract':
        extract(args.config, args.contract, args.sample, args.jar, args.out)
    elif args.action == 'collect':
        collect(args.config, args.extractions, args.out)
    elif args.action == 'freeze':
        freeze_candidates(args.config, args.contract, args.solver, args.inputs, args.out)
    else:
        evaluate(args.config, args.inputs, args.candidates, args.source_inputs, args.out)


if __name__ == '__main__':
    main()
