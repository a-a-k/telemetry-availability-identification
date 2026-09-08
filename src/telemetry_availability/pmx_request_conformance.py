"""Remote PMX extraction and pinned Palladio request-boundary controls."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import time

from .pmx_adapter_conformance import OPTIONS_SHA, compare_pcm, inspect_pcm, run_pmx
from .pmx_composition_control import SUFFIXES, _download, _hash, _read, _remote, _write
from .pmx_pmf_bridge import qualify, validate as validate_bridge
from .pmx_request_controls import CASES, fixture
from .pmx_request_pcm import bridge
from .pmx_usage_contract_audit import reconstructed_inventory


def validate(path):
    config = _read(path)
    validate_bridge(Path('configs/m9s_pmx_pmf_bridge.json'))
    for row in config['repository_locks']:
        if _hash(Path(row['path'])) != row['sha256']:
            raise ValueError('frozen request implementation differs: '+row['path'])
    if config['cases'] != list(CASES) or config['expected_models'] != 22:
        raise ValueError('unexpected request conformance matrix')
    return config


def accepted_bridge(inputs):
    acceptance = _read(Path('configs/m9s_pmf_bridge_acceptance.json'))
    artifact = dict(acceptance['artifact'], role='m9s-census')
    metadata = _download({'source_run_id': acceptance['source_run_id'],
        'source_head_sha': acceptance['source_commit'], 'artifacts': [artifact]}, inputs)
    path = inputs / artifact['role'] / artifact['file']
    if path.stat().st_size != artifact['file_bytes'] or _hash(path) != artifact['file_sha256']:
        raise ValueError('M9S accepted evidence differs')
    census = _read(path)
    if (census['status'] != acceptance['required_status'] or not census['matrix_complete']
            or census['positive_oracle_passes'] != 16 or not census['negative_boundary_reproduced']):
        raise ValueError('PMF bridge not qualified')
    return metadata


def prepare(config_path, inputs, options, out):
    _remote()
    validate(config_path)
    metadata = accepted_bridge(inputs)
    if _hash(options) != OPTIONS_SHA:
        raise ValueError('author options differ')
    original = options.read_text()
    if original.count('traces/jaegercustomers.json') != 1:
        raise ValueError('unexpected author options input')
    for case in CASES:
        result, expected, grouped, requests = fixture(case)
        root = out / 'fixtures' / case
        _write(root / 'projection.json', result)
        _write(root / 'expected.json', expected)
        _write(root / 'native.json', {key: [asdict(span) for span in spans] for key, spans in grouped.items()})
        _write(root / 'requests.json', requests)
        _write(root / 'traces/observed.json', result['envelope'])
        (root / 'Options.txt').write_text(original.replace('traces/jaegercustomers.json', 'traces/observed.json'))
    _write(out / 'input-contract.json', {'config_sha256': _hash(config_path),
        'head_sha': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID'],
        'acceptance_metadata': metadata, 'files': {p.relative_to(out).as_posix(): _hash(p)
        for p in out.rglob('*') if p.is_file()}})


def execute(config_path, contract, jar, out):
    _remote()
    config = validate(config_path)
    inputs = _read(contract / 'input-contract.json')
    if inputs['config_sha256'] != _hash(config_path) or inputs['head_sha'] != os.environ['GITHUB_SHA']:
        raise ValueError('mixed conformance input provenance')
    for name, digest in inputs['files'].items():
        if _hash(contract / name) != digest:
            raise ValueError('conformance input changed')
    rows, models = [], []
    for case in CASES:
        root = contract / 'fixtures' / case
        expected, projection = _read(root / 'expected.json'), _read(root / 'projection.json')
        for repetition in (1, 2):
            raw = out / 'raw' / case / f'r{repetition}'
            row = {'case': case, 'repetition': repetition, 'qualified': False}
            try:
                row['execution'] = run_pmx(jar, root, raw)
                actual = inspect_pcm(raw / 'results')
                row.update(compare_pcm(actual, expected))
                inventory = reconstructed_inventory((raw / 'stdout.log').read_text(errors='replace'), projection['envelope'])
                row['native_reconstruction'] = inventory
                row['qualified'] = row['qualified'] and row['execution']['exit_code'] == 0 and all(
                    inventory[key] for key in ('exact_trace_span_operation_parent_inventory',
                    'each_trace_reconstructed_once', 'reconstructed_nanosecond_bounds_match_input_microseconds'))
                _write(raw / 'resolved-pcm.json', actual)
                if not row['qualified']:
                    raise ValueError('request extraction contract not qualified')
                for variant, success in expected['success'].items():
                    model_id = f'{case}-{variant}-r{repetition}'
                    target = out / 'models' / model_id
                    target.mkdir(parents=True, exist_ok=False)
                    for suffix in SUFFIXES:
                        shutil.copyfile(raw / 'results' / ('extracted.'+suffix), target / ('extracted.'+suffix))
                    started = time.perf_counter()
                    repository = (target / 'extracted.repository').read_text()
                    updated, modifications = bridge(repository, projection['operation_oracle'], variant)
                    (target / 'extracted.repository').write_text(updated)
                    changed = [suffix for suffix in SUFFIXES if
                        _hash(target / ('extracted.'+suffix)) != _hash(raw / 'results' / ('extracted.'+suffix))]
                    if changed != ['repository']:
                        raise ValueError('unexpected changed PCM file set')
                    models.append({'model_id': model_id, 'case': case, 'variant': variant,
                        'extractor_repetition': repetition, 'expected_success': success,
                        'modifications': modifications, 'bridge_seconds': time.perf_counter()-started,
                        'files': {p.name: _hash(p) for p in target.iterdir()}})
            except Exception as exc:
                row['qualified'] = False
                row['error'] = f'{type(exc).__name__}: {exc}'
            rows.append(row)
            _write(raw / 'decision.json', row)
    complete = len(rows) == 12 and all(row['qualified'] for row in rows) and len(models) == config['expected_models']
    result = {'kind': 'm9u_request_conformance_contract', 'head_sha': os.environ['GITHUB_SHA'],
        'run_id': os.environ['GITHUB_RUN_ID'], 'config_sha256': _hash(config_path),
        'qualified': complete, 'extractor_attempts': rows, 'models': models,
        'evaluator_rows_read': 0, 'application_forecasts': 0}
    _write(out / 'request-contract.json', result)
    return result


def summarize(config_path, contract, solver, out):
    _remote()
    config = validate(config_path)
    prepared = _read(contract / 'request-contract.json')
    for key, value in (('run_id', os.environ['GITHUB_RUN_ID']), ('head_sha', os.environ['GITHUB_SHA']),
                       ('config_sha256', _hash(config_path))):
        if prepared[key] != value:
            raise ValueError('mixed solver contract provenance')
    raw_path = solver / 'raw-result.json'
    raw = _read(raw_path)['runs'] if raw_path.exists() else []
    identities = [(row.get('model_id'), row.get('repetition')) for row in raw]
    wanted = {(row['model_id'], repeat) for row in prepared['models'] for repeat in (0, 1)}
    complete = len(identities) == len(set(identities)) and set(identities) == wanted
    indexed = {(row.get('model_id'), row.get('repetition')): row for row in raw}
    rows = []
    for model in prepared['models']:
        for name, digest in model['files'].items():
            if _hash(contract / 'models' / model['model_id'] / name) != digest:
                raise ValueError('solver contract input changed')
        for repeat in (0, 1):
            row = dict(indexed.get((model['model_id'], repeat), {'status': 'missing'}))
            row.update(model_id=model['model_id'], repetition=repeat, case=model['case'],
                       variant=model['variant'], expected_success=model['expected_success'])
            row.update(qualify(row, model['expected_success']))
            rows.append(row)
    qualified = prepared['qualified'] and complete and len(rows) == 2*config['expected_models'] and all(
        row['software_oracle_pass'] for row in rows)
    result = {'status': 'request_adapter_qualified' if qualified else 'request_adapter_unresolved',
        'source_run_id': os.environ['GITHUB_RUN_ID'], 'source_commit': os.environ['GITHUB_SHA'],
        'config_sha256': _hash(config_path), 'matrix_complete': complete,
        'extractor_contract_qualified': prepared['qualified'], 'expected_records': 44,
        'retained_records': len(raw), 'oracle_passes': sum(row['software_oracle_pass'] for row in rows),
        'conditional_swallowed_child_abstention_retained': True, 'rows': rows,
        'independent_application_comparison_established': False}
    _write(out / 'request-conformance-census.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'prepare', 'execute', 'summarize'])
    parser.add_argument('--config', type=Path, default=Path('configs/m9u_pmx_request_conformance.json'))
    for key in ('inputs', 'options', 'out', 'contract', 'jar', 'solver'):
        parser.add_argument('--'+key, type=Path)
    args = parser.parse_args()
    if args.action == 'validate':
        validate(args.config)
    elif args.action == 'prepare':
        prepare(args.config, args.inputs, args.options, args.out)
    elif args.action == 'execute':
        execute(args.config, args.contract, args.jar, args.out)
    else:
        summarize(args.config, args.contract, args.solver, args.out)


if __name__ == '__main__':
    main()
