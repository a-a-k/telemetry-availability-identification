"""Source-grounded integer-to-PMF bridge on retained artificial PMX models."""
import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
from urllib.request import urlopen
from xml.etree import ElementTree as ET

from .pmx_composition_control import (
    SUFFIXES, _download, _hash, _read, _remote, _write,
    failure_references, validate as validate_m9r,
)

VARIANTS = (
    ('raw', '00-raw', None),
    ('scalar_types', '01-types', None),
    ('pmf_inclusive', '01-types', .72),
    ('pmf_conditional_local', '02-conditional_local', .8),
    ('pmf_zero', '03-zero', 1.0),
    ('pmf_random_loop', '01-types', .724),
)
LOOP_TAG = 'iterationCount_LoopAction'
LOOP_TOKEN = re.compile(r'(<iterationCount_LoopAction\b[^>]*\bspecification=")([^"]*)("[^>]*/>)')


def integer_loop_pmfs(text, random_loop_id=None):
    """Preserve all XML bytes except the selected integer loop expressions.

    The optional random-loop case is a disclosed artificial semantic control,
    not an equivalent conversion of the original loop count.
    """
    root = ET.fromstring(text)
    parent = {child: node for node in root.iter() for child in node}
    counts = [node for node in root.iter() if node.tag == LOOP_TAG]
    if not counts or len(LOOP_TOKEN.findall(text)) != len(counts):
        raise ValueError('unsupported or absent loop serialization')
    changes = []
    for node in counts:
        specification = node.get('specification', '')
        if not re.fullmatch(r'0|[1-9][0-9]*', specification):
            raise ValueError('only nonnegative integer literal loops are supported')
        loop = parent[node]
        if not loop.get('{http://www.w3.org/2001/XMLSchema-instance}type', '').endswith(':LoopAction'):
            raise ValueError('iteration expression has no LoopAction owner')
        loop_id = loop.get('id')
        if not loop_id:
            raise ValueError('loop has no identifier')
        replacement = ("IntPMF[(0;0.5)(2;0.5)]" if loop_id == random_loop_id
                       else f'IntPMF[({specification};1.0)]')
        changes.append({'loop_id': loop_id, 'before': specification, 'after': replacement,
                        'equivalent_integer_law': loop_id != random_loop_id})
    if random_loop_id is not None and sum(c['loop_id'] == random_loop_id for c in changes) != 1:
        raise ValueError('random-loop control requires exactly one named loop')
    iterator = iter(changes)
    rewritten = LOOP_TOKEN.sub(lambda match: match[1] + next(iterator)['after'] + match[3], text)
    before, after = ET.fromstring(text), ET.fromstring(rewritten)
    before_nodes, after_nodes = list(before.iter()), list(after.iter())
    if len(before_nodes) != len(after_nodes):
        raise ValueError('bridge changed the repository structure')
    for original, converted in zip(before_nodes, after_nodes, strict=True):
        if original.tag == LOOP_TAG:
            converted.set('specification', original.get('specification'))
    if ET.tostring(before) != ET.tostring(after):
        raise ValueError('bridge changed something beyond loop expressions')
    return rewritten, changes


def root_loop_id(repository, usage):
    calls = list(ET.fromstring(usage).iter('operationSignature__EntryLevelSystemCall'))
    if len(calls) != 1:
        raise ValueError('control requires exactly one root entry')
    signature = calls[0].attrib['href'].split('#')[-1]
    seffs = [node for node in ET.fromstring(repository).iter()
             if node.get('describedService__SEFF') == signature]
    if len(seffs) != 1:
        raise ValueError('root entry does not resolve to exactly one SEFF')
    loops = [node for node in seffs[0] if node.get(
        '{http://www.w3.org/2001/XMLSchema-instance}type', '').endswith(':LoopAction')]
    if len(loops) != 1:
        raise ValueError('control requires one loop in the root SEFF')
    return loops[0].attrib['id']


def qualify(row, expected, tolerance=1e-12):
    """A returned zero-mass object is not a reliability answer."""
    keys = ('success_probability', 'failure_probability_sum', 'physical_state_probability')
    values = [row.get(key) for key in keys]
    finite = all(type(value) in (int, float) and math.isfinite(value) for value in values)
    valid = (row.get('status') == 'solved' and finite
             and all(0 <= value <= 1 for value in values)
             and abs(values[0] + values[1] - 1) <= tolerance
             and abs(values[2] - 1) <= tolerance
             and type(row.get('total_physical_states')) is int
             and row['total_physical_states'] >= 1
             and row.get('evaluated_physical_states') == row['total_physical_states'])
    matches = valid and expected is not None and abs(values[0] - expected) <= tolerance
    return {'valid_probability': bool(valid), 'software_oracle_pass': bool(matches)}


def validate(config_path):
    config = _read(config_path)
    validate_m9r(Path('configs/m9r_pmx_composition.json'))
    for lock in config['repository_locks']:
        if _hash(Path(lock['path'])) != lock['sha256']:
            raise ValueError('frozen implementation differs: ' + lock['path'])
    if (config['expected_models'], config['solver_passes']) != (12, 2):
        raise ValueError('unexpected control matrix')
    if config['source_run_id'] != 34131147623:
        raise ValueError('unexpected retained source run')
    return config


def prepare(config_path, inputs, out):
    _remote()
    config = validate(config_path)
    metadata = _download(config, inputs)
    for source_lock in config['source_artifacts']:
        source_file = out / 'source' / source_lock['name']
        source_file.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(source_lock['url'], timeout=120) as response:
            source_file.write_bytes(response.read())
        if source_file.stat().st_size != source_lock['bytes'] or _hash(source_file) != source_lock['sha256']:
            raise ValueError('diagnostic source artifact differs')
    source_root = inputs / 'contract'
    contract_path = source_root / 'composition-contract.json'
    if _hash(contract_path) != config['source_contract_sha256']:
        raise ValueError('retained M9R contract differs')
    source_contract = _read(contract_path)
    source_models = {model['model_id']: model for model in source_contract['models']}
    models = []
    for index, (variant, source_prefix, expected) in enumerate(VARIANTS):
        for repetition in (1, 2):
            source_id = f'{source_prefix}-r{repetition}'
            source = source_root / 'models' / source_id
            source_record = source_models[source_id]
            for name, digest in source_record['files'].items():
                if _hash(source / name) != digest:
                    raise ValueError('retained model hash differs')
            model_id = f'{index:02d}-{variant}-r{repetition}'
            target = out / 'models' / model_id
            target.mkdir(parents=True, exist_ok=False)
            for suffix in SUFFIXES:
                name = 'extracted.' + suffix
                (target / name).write_bytes((source / name).read_bytes())
            changes = []
            if variant.startswith('pmf_'):
                text = (source / 'extracted.repository').read_text()
                loop_id = (root_loop_id(text, (source / 'extracted.usagemodel').read_text())
                           if variant == 'pmf_random_loop' else None)
                updated, changes = integer_loop_pmfs(text, loop_id)
                if len(changes) != 3 or any(c['before'] != '1' for c in changes):
                    raise ValueError('unexpected retained artificial loop inventory')
                (target / 'extracted.repository').write_text(updated)
                if failure_references(text) != failure_references(updated):
                    raise ValueError('PMF bridge changed failure references or probabilities')
            changed = [f'extracted.{suffix}' for suffix in SUFFIXES
                       if _hash(target / f'extracted.{suffix}') != _hash(source / f'extracted.{suffix}')]
            if changed != (['extracted.repository'] if changes else []):
                raise ValueError('unexpected changed file')
            models.append({'model_id': model_id, 'variant': variant,
                           'source_model_id': source_id, 'expected_success': expected,
                           'loop_expression_changes': changes, 'changed_files': changed,
                           'source_files': source_record['files'],
                           'files': {p.name: _hash(p) for p in target.iterdir()}})
    result = {'kind': 'm9s_retained_pmf_bridge_contract', 'run_id': os.environ['GITHUB_RUN_ID'],
              'head_sha': os.environ['GITHUB_SHA'], 'config_sha256': _hash(config_path),
              'models': models, 'artifact_metadata': metadata,
              'new_pmx_invocations': 0, 'live_data_rows': 0, 'evaluator_rows_read': 0}
    _write(out / 'pmf-bridge-contract.json', result)
    return result


def summarize(config_path, contract_root, solver_root, out):
    _remote()
    config = validate(config_path)
    contract = _read(contract_root / 'pmf-bridge-contract.json')
    for key, value in (('run_id', os.environ['GITHUB_RUN_ID']), ('head_sha', os.environ['GITHUB_SHA']),
                       ('config_sha256', _hash(config_path))):
        if contract[key] != value:
            raise ValueError('mixed contract provenance')
    for model in contract['models']:
        for name, digest in model['files'].items():
            if _hash(contract_root / 'models' / model['model_id'] / name) != digest:
                raise ValueError('prepared model hash differs')
    result_path = solver_root / 'raw-result.json'
    raw = _read(result_path)['runs'] if result_path.exists() else []
    identities = [(row.get('model_id'), row.get('repetition')) for row in raw]
    expected_ids = {(model['model_id'], repetition) for model in contract['models'] for repetition in (0, 1)}
    unique = len(set(identities)) == len(identities)
    matrix_complete = unique and set(identities) == expected_ids
    indexed = {(row.get('model_id'), row.get('repetition')): row for row in raw}
    rows = []
    for model in contract['models']:
        for repetition in (0, 1):
            row = dict(indexed.get((model['model_id'], repetition), {'status': 'missing'}))
            row.update(model_id=model['model_id'], repetition=repetition, variant=model['variant'],
                       expected_success=model['expected_success'])
            row.update(qualify(row, model['expected_success'], config['probability_tolerance']))
            rows.append(row)
    positives = [row for row in rows if row['expected_success'] is not None]
    negatives = [row for row in rows if row['expected_success'] is None]
    negative_boundary_reproduced = all(not row['valid_probability'] and row['status'] != 'missing'
                                      for row in negatives)
    accepted = (matrix_complete and len(positives) == 16
                and all(row['software_oracle_pass'] for row in positives)
                and negative_boundary_reproduced)
    result = {'status': 'pmf_bridge_qualified' if accepted else 'pmf_bridge_unresolved',
              'source_run_id': os.environ['GITHUB_RUN_ID'], 'source_commit': os.environ['GITHUB_SHA'],
              'config_sha256': _hash(config_path), 'contract_sha256': _hash(contract_root / 'pmf-bridge-contract.json'),
              'expected_records': 24, 'retained_records': len(raw), 'matrix_complete': matrix_complete,
              'unexpected_or_duplicate_records': [row for row in raw if
                   (row.get('model_id'), row.get('repetition')) not in expected_ids
                   or Counter(identities)[(row.get('model_id'), row.get('repetition'))] > 1],
              'positive_oracle_passes': sum(row['software_oracle_pass'] for row in positives),
              'negative_boundary_reproduced': negative_boundary_reproduced, 'rows': rows,
              'new_pmx_invocations': 0, 'live_availability_forecasts': 0, 'evaluator_rows_read': 0}
    _write(out / 'pmf-bridge-census.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'prepare', 'summarize'])
    parser.add_argument('--config', type=Path, default=Path('configs/m9s_pmx_pmf_bridge.json'))
    for arg in ('inputs', 'out', 'contract-root', 'solver-root'):
        parser.add_argument('--' + arg, type=Path)
    args = parser.parse_args()
    if args.action == 'validate':
        validate(args.config)
    elif args.action == 'prepare':
        prepare(args.config, args.inputs, args.out)
    else:
        summarize(args.config, args.contract_root, args.solver_root, args.out)


if __name__ == '__main__':
    main()
