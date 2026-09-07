"""Bounded retained-model Palladio control; no PMX invocation or live data."""
import argparse
from collections import Counter
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import subprocess
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr
from zipfile import ZipFile

SUFFIXES = ('repository', 'system', 'allocation', 'resourceenvironment', 'usagemodel')
FAILURE_LINK = 'softwareInducedFailureType__InternalFailureOccurrenceDescription'
RELIABILITY = 'http://palladiosimulator.org/PalladioComponentModel/Reliability/5.2'


def _read(path):
    return json.loads(path.read_text())


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + '\n')


def _remote():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise ValueError('full retained-model preparation and solving run remotely')


def validate(config_path):
    config = _read(config_path)
    for row in config['repository_locks']:
        assert _hash(Path(row['path'])) == row['sha256'], row['path']
    assert config['expected_models'] == 8 and config['solver_passes'] == 2
    return config


def failure_references(text):
    root = ET.fromstring(text)
    identified = [node for node in root.iter() if 'id' in node.attrib]
    ids = {node.attrib['id']: node for node in identified}
    if len(ids) != len(identified):
        raise ValueError('duplicate repository identifier')
    rows = []
    def visit(node, path):
        if FAILURE_LINK in node.attrib:
            target = node.attrib[FAILURE_LINK]
            if not target or any(x in target for x in (' ', '#', '/', '"', '<', '>')):
                raise ValueError('unsupported software failure reference')
            if target in ids and not ids[target].get('{http://www.w3.org/2001/XMLSchema-instance}type', '').endswith(':SoftwareInducedFailureType'):
                raise ValueError('failure reference resolves to the wrong object type')
            probability = float(node.attrib['failureProbability'])
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError('invalid software failure probability')
            rows.append({'reference': target, 'resolved': target in ids,
                         'probability': probability, 'occurrence_path': '/' + path})
        counts = Counter()
        for child in node:
            tag = child.tag.rsplit('}', 1)[-1]
            index = counts[tag]
            counts[tag] += 1
            visit(child, path + f'/@{tag}.{index}')
    visit(root, '')
    return rows


def contain_failure_types(text):
    """Add referenced containment objects without changing existing XML tokens."""
    refs = failure_references(text)
    missing = [row for row in refs if not row['resolved']]
    if len({r['reference'] for r in missing}) != len(missing):
        raise ValueError('this bridge requires one occurrence per missing type')
    if not missing:
        return text
    if text.count('</repository:Repository>') != 1 or 'xmlns:reliability=' in text:
        raise ValueError('unexpected retained repository envelope')
    text = text.replace('<repository:Repository ', f'<repository:Repository xmlns:reliability="{RELIABILITY}" ', 1)
    additions = ''.join('  <failureTypes__Repository xsi:type="reliability:SoftwareInducedFailureType" '
                        f'id={quoteattr(r["reference"])} entityName={quoteattr("retained-" + r["reference"])} '
                        f'internalFailureOccurrenceDescriptions__SoftwareInducedFailureType={quoteattr(r["occurrence_path"])}/>\n'
                        for r in missing)
    return text.replace('</repository:Repository>', additions + '</repository:Repository>')


def _download(config, root):
    metadata = []
    for lock in config['artifacts']:
        endpoint = f'repos/{os.environ["GITHUB_REPOSITORY"]}/actions/artifacts/{lock["id"]}'
        actual = json.loads(subprocess.check_output(['gh', 'api', endpoint]))
        for key in ('id', 'name', 'size_in_bytes', 'digest'):
            assert actual[key] == lock[key]
        assert not actual['expired']
        assert actual['workflow_run']['id'] == config['source_run_id']
        assert actual['workflow_run']['head_sha'] == config['source_head_sha']
        archive = subprocess.check_output(['gh', 'api', endpoint + '/zip'])
        assert len(archive) == lock['size_in_bytes']
        assert 'sha256:' + sha256(archive).hexdigest() == lock['digest']
        with ZipFile(io.BytesIO(archive)) as zipped:
            for name in zipped.namelist():
                relative = PurePosixPath(name)
                assert not relative.is_absolute() and '..' not in relative.parts
            zipped.extractall(root / lock['role'])
        metadata.append(actual)
    return metadata


def prepare(config_path, inputs, out):
    _remote()
    config = validate(config_path)
    metadata = _download(config, inputs)
    contract = _read(inputs / 'contract/contract-manifest.json')
    for name, digest in contract['files'].items():
        assert _hash(inputs / 'contract' / name) == digest
    envelope = _read(inputs / 'contract/nested_errors/traces/observed.json')
    roots, child_errors, joint_errors = 0, 0, 0
    for trace in envelope['data']:
        root = next(s for s in trace['spans'] if not s['references'])
        error = lambda s: any(t['key'] == 'error' and t['value'] == 'true' for t in s['tags'])
        children_fail = any(error(s) for s in trace['spans'] if s['references'])
        roots += error(root)
        child_errors += children_fail
        joint_errors += error(root) and children_fail
    assert (len(envelope['data']), roots, child_errors, joint_errors) == (10, 2, 1, 1)
    models = []
    variants = [('raw', None), ('types', .72), ('conditional_local', .8), ('zero', 1.0)]
    for variant_index, (variant, expected) in enumerate(variants):
        for repetition in (1, 2):
            source = inputs / f'probe/raw/nested_errors/repeat-{repetition}'
            resolved = _read(source / 'resolved-pcm.json')
            for name, digest in resolved['model_files'].items():
                assert _hash(source / 'results' / name) == digest
            repository = (source / 'results/extracted.repository').read_text()
            refs = failure_references(repository)
            assert len(refs) == 2 and all(not r['resolved'] for r in refs)
            assert sorted(r['probability'] for r in refs) == [.1, .2]
            model_id = f'{variant_index:02d}-{variant}-r{repetition}'
            target = out / 'models' / model_id
            target.mkdir(parents=True, exist_ok=False)
            for suffix in SUFFIXES:
                original = source / f'results/extracted.{suffix}'
                (target / original.name).write_bytes(original.read_bytes())
            if variant != 'raw':
                updated = contain_failure_types(repository)
                if variant == 'conditional_local':
                    assert updated.count('failureProbability="0.2"') == 1
                    updated = updated.replace('failureProbability="0.2"', 'failureProbability="0.1111111111111111"')
                elif variant == 'zero':
                    for value in ('0.1', '0.2'):
                        assert updated.count(f'failureProbability="{value}"') == 1
                        updated = updated.replace(f'failureProbability="{value}"', 'failureProbability="0.0"')
                (target / 'extracted.repository').write_text(updated)
                assert all(r['resolved'] for r in failure_references(updated))
            changed = [f'extracted.{s}' for s in SUFFIXES
                       if _hash(target / f'extracted.{s}') != _hash(source / f'results/extracted.{s}')]
            assert changed == ([] if variant == 'raw' else ['extracted.repository'])
            models.append({'model_id': model_id, 'variant': variant, 'source_repetition': repetition,
                           'expected_software_success_given_resources_up': expected,
                           'reference_inclusive_root_success': .8, 'changed_files': changed,
                           'original_missing_failure_types': 2,
                           'failure_references': failure_references((target / 'extracted.repository').read_text()),
                           'source_files': resolved['model_files'],
                           'files': {p.name: _hash(p) for p in target.iterdir()}})
    result = {'kind': 'm9r_retained_composition_contract', 'run_id': os.environ['GITHUB_RUN_ID'],
              'head_sha': os.environ['GITHUB_SHA'], 'config_sha256': _hash(config_path),
              'models': models, 'artifact_metadata': metadata, 'new_pmx_invocations': 0,
              'live_data_rows': 0, 'evaluator_rows_read': 0, 'reference_patterns': 10}
    _write(out / 'composition-contract.json', result)
    return result


def summarize(config_path, contract_root, solver_root, out):
    _remote()
    config = validate(config_path)
    contract = _read(contract_root / 'composition-contract.json')
    assert contract['run_id'] == os.environ['GITHUB_RUN_ID']
    assert contract['head_sha'] == os.environ['GITHUB_SHA']
    assert contract['config_sha256'] == _hash(config_path)
    for model in contract['models']:
        for name, digest in model['files'].items():
            assert _hash(contract_root / 'models' / model['model_id'] / name) == digest
    path = solver_root / 'raw-result.json'
    raw = _read(path)['runs'] if path.exists() else []
    index = {(row['model_id'], row['repetition']): row for row in raw}
    wanted = {(model['model_id'], rep) for model in contract['models'] for rep in (0, 1)}
    assert len(index) == len(raw) and set(index).issubset(wanted)
    rows = []
    for model in contract['models']:
        for repetition in (0, 1):
            row = index.get((model['model_id'], repetition))
            result = {'model_id': model['model_id'], 'variant': model['variant'],
                      'repetition': repetition, 'raw': row, 'status': 'missing' if row is None else row['status'],
                      'source_references_complete': model['variant'] != 'raw',
                      'software_oracle': model['expected_software_success_given_resources_up'],
                      'software_oracle_pass': False}
            if row and row['status'] == 'solved':
                values = [row[k] for k in ('success_probability', 'failure_probability_sum', 'physical_state_probability')]
                finite = all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
                physical = (finite and 0 <= values[0] <= 1 and 0 <= values[1] <= 1
                            and abs(values[0] + values[1] - 1) <= 1e-12
                            and abs(values[2] - 1) <= 1e-12
                            and row['evaluated_physical_states'] == row['total_physical_states'])
                expected = result['software_oracle']
                result['physical_result_valid'] = physical
                result['software_oracle_pass'] = physical and expected is not None and abs(values[0] - expected) <= 1e-12
                result['success_minus_inclusive_root_frequency'] = values[0] - .8 if finite else None
            rows.append(result)
    result = {'kind': 'm9r_retained_composition_census', 'run_id': os.environ['GITHUB_RUN_ID'],
              'head_sha': os.environ['GITHUB_SHA'], 'config_sha256': _hash(config_path),
              'contract_sha256': _hash(contract_root / 'composition-contract.json'),
              'expected_records': 16, 'retained_records': len(raw), 'rows': rows,
              'typed_software_oracle_passes': sum(r['software_oracle_pass'] for r in rows),
              'new_pmx_invocations': 0, 'evaluator_rows_read': 0, 'live_availability_forecasts': 0,
              'raw_native_failure_references_qualified': False}
    _write(out / 'composition-census.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'prepare', 'summarize'])
    parser.add_argument('--config', type=Path, default=Path('configs/m9r_pmx_composition.json'))
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
