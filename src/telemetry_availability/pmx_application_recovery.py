"""Solve retained M9V models after exact trace-ID and mixed-loop repairs."""
import argparse
import os
from pathlib import Path
import shutil

from .pmx_adapter_conformance import compare_pcm, inspect_pcm
from .pmx_application_comparison import freeze_candidates, evaluate, validate as validate_m9v
from .pmx_composition_control import SUFFIXES, _download, _hash, _read, _remote, _write
from .pmx_mixed_loop_bridge import bridge, mixed_loop_pmfs
from .pmx_pmf_bridge import qualify
from .pmx_retained_request_audit import inventory_variable_hex_ids


def validate(path):
    validate_m9v(Path('configs/m9v_pmx_application_comparison.json'))
    config = _read(path)
    for lock in config['repository_locks']:
        if _hash(Path(lock['path'])) != lock['sha256']:
            raise ValueError('retained recovery implementation differs: '+lock['path'])
    if config['expected_application_models'] != 18 or config['expected_control_models'] != 2:
        raise ValueError('unexpected recovery matrix')
    return config


def prepare(config_path, inputs, out):
    _remote()
    config = validate(config_path)
    metadata = _download(config, inputs)
    source = inputs / 'application'
    contract = _read(source / 'application-input-contract.json')
    if contract['head_sha'] != config['source_head_sha'] or contract['run_id'] != str(config['source_run_id']):
        raise ValueError('retained source contract provenance differs')
    for name, digest in contract['files'].items():
        if _hash(source / name) != digest:
            raise ValueError('retained application input changed')
    models, extractions = [], []
    for sample in contract['samples']:
        extraction = inputs / ('extract-'+sample['sample']['key'])
        cases = []
        for case in sample['cases']:
            projected = source / 'cases' / case['case_id']
            raw = extraction / 'raw' / case['case_id']
            original = _read(extraction / 'decisions' / (case['case_id']+'.json'))
            resolved = _read(raw / 'resolved-pcm.json')
            for name, digest in resolved['model_files'].items():
                if _hash(raw / 'results' / name) != digest:
                    raise ValueError('retained native PCM differs')
            envelope = projected / 'traces/observed.json'
            if _hash(raw / 'traces/observed.json') != _hash(envelope):
                raise ValueError('extractor received a different envelope')
            comparison = compare_pcm(inspect_pcm(raw / 'results'), _read(projected / 'expected.json'))
            inventory = inventory_variable_hex_ids((raw / 'stdout.log').read_text(errors='replace'), _read(envelope))
            if not comparison['qualified'] or not all(inventory[key] for key in (
                    'exact_trace_span_operation_parent_inventory', 'each_trace_reconstructed_once',
                    'reconstructed_nanosecond_bounds_match_input_microseconds')) or inventory['unresolved_reconstructed_records']:
                raise ValueError('retained application structural contract failed')
            row = {'case_id': case['case_id'], 'qualified': True, 'checks': comparison['checks'],
                'reconstruction': inventory, 'original_m9v_decision': original, 'variants': []}
            oracle = _read(projected / 'operation_oracle.json')
            for variant in ('inclusive', 'conditional_local'):
                if variant == 'conditional_local' and case['summary']['unsupported_conditional_local_operations']:
                    row['variants'].append({'variant': variant, 'status': 'unsupported_conditional_propagation_or_positivity'})
                    continue
                model_id = case['case_id']+'--'+variant
                target = out / 'models' / model_id
                target.mkdir(parents=True, exist_ok=False)
                for suffix in SUFFIXES:
                    shutil.copyfile(raw / 'results' / ('extracted.'+suffix), target / ('extracted.'+suffix))
                updated, changes = bridge((target / 'extracted.repository').read_text(), oracle, variant)
                (target / 'extracted.repository').write_text(updated)
                if any(_hash(target / ('extracted.'+suffix)) != _hash(raw / 'results' / ('extracted.'+suffix)) for suffix in SUFFIXES if suffix != 'repository'):
                    raise ValueError('non-repository PCM file changed')
                model = {'model_id': model_id, 'case_id': case['case_id'], 'variant': variant,
                    'sample': case['sample'], 'operation': case['operation'], 'changes': changes,
                    'files': {p.name: _hash(p) for p in target.iterdir()}, 'source_files': resolved['model_files']}
                models.append(model)
                row['variants'].append({'variant': variant, 'status': 'prepared', 'model_id': model_id})
            cases.append(row)
        extractions.append({'sample_key': sample['sample']['key'], 'cases': cases,
            'original_extraction_artifact_role': 'extract-'+sample['sample']['key']})
    if len(models) != config['expected_application_models']:
        raise ValueError('application support differs from retained audit')
    control_metadata = _download(config['control_source'], inputs / 'controls')
    control_root = inputs / 'controls/contract'
    if _hash(control_root / 'pmf-bridge-contract.json') != config['control_source']['contract_sha256']:
        raise ValueError('accepted M9S model contract differs')
    controls = _read(control_root / 'pmf-bridge-contract.json')
    for repetition in (1, 2):
        source_id = '05-pmf_random_loop-r'+str(repetition)
        source_model = next(r for r in controls['models'] if r['model_id'] == source_id)
        source_dir = control_root / 'models' / source_id
        for name, digest in source_model['files'].items():
            if _hash(source_dir / name) != digest:
                raise ValueError('accepted artificial control differs')
        model_id = 'control-mixed-native-pmf-r'+str(repetition)
        target = out / 'models' / model_id
        shutil.copytree(source_dir, target)
        text = (target / 'extracted.repository').read_text()
        if text.count('IntPMF[(0;0.5)(2;0.5)]') != 1 or text.count('IntPMF[(1;1.0)]') != 2:
            raise ValueError('unexpected M9S random-loop control inventory')
        mixed = text.replace('IntPMF[(0;0.5)(2;0.5)]', 'IntPMF[(0;5.0E-1) (2;0.5)]').replace('IntPMF[(1;1.0)]', '1')
        updated, changes = mixed_loop_pmfs(mixed)
        if updated != text.replace('IntPMF[(0;0.5)(2;0.5)]', 'IntPMF[(0;5.0E-1) (2;0.5)]'):
            raise ValueError('mixed control conversion not equivalent')
        (target / 'extracted.repository').write_text(updated)
        models.append({'model_id': model_id, 'control': True, 'expected_success': .724,
            'changes': changes, 'source_model_id': source_id,
            'files': {p.name: _hash(p) for p in target.iterdir()}})
    shutil.copytree(source, out / 'application-input')
    derived = dict(contract, original_input_contract_sha256=_hash(source / 'application-input-contract.json'),
        original_source_run_id=config['source_run_id'], original_source_commit=config['source_head_sha'],
        head_sha=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'], config_sha256=_hash(config_path),
        adoption='unchanged historical learner projections and comparator fits; only provenance re-sealed for retained-model recovery')
    _write(out / 'application-input/application-input-contract.json', derived)
    _write(out / 'solver-contract.json', {'models': models, 'extractions': extractions,
        'model_count': len(models), 'config_sha256': _hash(config_path), 'head_sha': os.environ['GITHUB_SHA'],
        'run_id': os.environ['GITHUB_RUN_ID'], 'source_artifacts': metadata, 'control_artifacts': control_metadata,
        'new_pmx_invocations': 0, 'new_comparator_fits': 0, 'evaluator_rows_read': 0})


def freeze(config_path, contract, solver, out):
    _remote()
    validate(config_path)
    prepared = _read(contract / 'solver-contract.json')
    raw_path = solver / 'raw-result.json'
    raw = _read(raw_path)['runs'] if raw_path.exists() else []
    control_rows = []
    for model in prepared['models']:
        if not model.get('control'):
            continue
        for name, digest in model['files'].items():
            if _hash(contract / 'models' / model['model_id'] / name) != digest:
                raise ValueError('mixed control input changed')
        for repeat in (0, 1):
            matches = [r for r in raw if r.get('model_id') == model['model_id'] and r.get('repetition') == repeat]
            passed = len(matches) == 1 and qualify(matches[0], .724)['software_oracle_pass']
            control_rows.append({'model_id': model['model_id'], 'repetition': repeat, 'passed': passed, 'raw': matches})
    _write(out / 'mixed-pmf-control-census.json', control_rows)
    if len(control_rows) != 4 or not all(r['passed'] for r in control_rows):
        raise ValueError('mixed integer/native-PMF controls not qualified')
    freeze_candidates(config_path, contract, solver, contract / 'application-input', out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'prepare', 'freeze', 'evaluate'))
    parser.add_argument('--config', type=Path, default=Path('configs/m9v_retained_application_recovery.json'))
    for key in ('inputs', 'out', 'contract', 'solver', 'candidates', 'source-inputs'):
        parser.add_argument('--'+key, type=Path)
    args = parser.parse_args()
    if args.action == 'validate':
        validate(args.config)
    elif args.action == 'prepare':
        prepare(args.config, args.inputs, args.out)
    elif args.action == 'freeze':
        freeze(args.config, args.contract, args.solver, args.out)
    else:
        evaluate(args.config, args.contract / 'application-input', args.candidates, args.source_inputs, args.out)


if __name__ == '__main__':
    main()
