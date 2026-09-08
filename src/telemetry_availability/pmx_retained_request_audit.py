"""Remote read-only diagnosis of retained M9V trace-ID and loop representations."""
import argparse
from collections import Counter
import os
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .pmx_application_comparison import validate as validate_application
from .pmx_composition_control import _download, _hash, _read, _remote, _write
from .pmx_usage_contract_audit import reconstructed_inventory


def inventory_variable_hex_ids(stdout, envelope):
    """Resolve printed IDs against exact supplied identities, without length assumptions."""
    normalized = stdout.replace('\r\n', '\n')
    pattern = re.compile(r'^(?:osgi> )?#{42}\n(?P<spans>(?:operation_[0-9a-f]{24} / [0-9a-f]+ / (?:null|[0-9a-f]+)\n)+)#{42}\n(?P<execution>ExecutionTrace [^\n]*)$', re.M)
    records, times, traces = Counter(), {}, Counter()
    wanted, wanted_times = Counter(), {}
    for trace in envelope['data']:
        trace_id = trace['traceID']
        if not re.fullmatch(r'[0-9a-f]+', trace_id) or trace_id in wanted_times:
            raise ValueError('ambiguous input trace identity')
        wanted_times[trace_id] = [min(s['startTime'] for s in trace['spans'])*1000,
            max(s['startTime']+s['duration'] for s in trace['spans'])*1000]
        for span in trace['spans']:
            parent = span['references'][0]['spanID'] if span['references'] else ''
            wanted[trace_id, span['spanID'], span['operationName'], parent] += 1
    diagnostics = []
    for match in pattern.finditer(normalized):
        execution = match['execution']
        identities = re.findall(r'([0-9a-f]+)(operation_[0-9a-f]{24}) <NOSESSIONID>', execution)
        ids = {key for key, _ in identities}
        if len(ids) != 1 or not ids <= set(wanted_times) or 'invalidExecutions=[]' not in execution:
            diagnostics.append({'trace_ids': sorted(ids), 'invalid_executions_empty': 'invalidExecutions=[]' in execution,
                'execution_excerpt': execution[:1800]})
            continue
        trace_id = next(iter(ids))
        traces[trace_id] += 1
        bounds = re.search(r'minTin=(\d+), maxTout=(\d+)', execution)
        if bounds is None:
            raise ValueError('printed time bounds absent')
        times[trace_id] = [int(bounds[1]), int(bounds[2])]
        span_rows = [line.split(' / ') for line in match['spans'].splitlines()]
        if Counter(operation for _, operation in identities) != Counter(r[0] for r in span_rows):
            raise ValueError('execution and span inventories differ')
        for operation, span_id, parent in span_rows:
            records[trace_id, span_id, operation, '' if parent == 'null' else parent] += 1
    return {'expected_spans': sum(wanted.values()), 'reconstructed_spans': sum(records.values()),
        'exact_trace_span_operation_parent_inventory': records == wanted,
        'each_trace_reconstructed_once': traces == Counter({key: 1 for key in wanted_times}),
        'reconstructed_nanosecond_bounds_match_input_microseconds': times == wanted_times,
        'input_trace_id_lengths': dict(Counter(len(key) for key in wanted_times)),
        'unresolved_reconstructed_records': len(diagnostics), 'unresolved_examples': diagnostics[:5]}


def run(config_path, inputs, out):
    _remote()
    config = _read(config_path)
    validate_application(Path('configs/m9v_pmx_application_comparison.json'))
    for lock in config['repository_locks']:
        if _hash(Path(lock['path'])) != lock['sha256']:
            raise ValueError('retained diagnostic implementation differs')
    metadata = _download(config, inputs)
    source = inputs / 'application'
    contract = _read(source / 'application-input-contract.json')
    for name, digest in contract['files'].items():
        if _hash(source / name) != digest:
            raise ValueError('retained projection changed')
    cases = []
    for sample in contract['samples']:
        extraction = inputs / ('extract-'+sample['sample']['key'])
        for case in sample['cases']:
            projected = source / 'cases' / case['case_id']
            raw = extraction / 'raw' / case['case_id']
            envelope_path = projected / 'traces/observed.json'
            if _hash(raw / 'traces/observed.json') != _hash(envelope_path):
                raise ValueError('extractor input and sealed projection differ')
            resolved = _read(raw / 'resolved-pcm.json')
            for name, digest in resolved['model_files'].items():
                if _hash(raw / 'results' / name) != digest:
                    raise ValueError('retained native PCM changed')
            envelope = _read(envelope_path)
            stdout = (raw / 'stdout.log').read_text(errors='replace')
            try:
                original = reconstructed_inventory(stdout, envelope)
            except Exception as exc:
                original = {'error': f'{type(exc).__name__}: {exc}'}
            revised = inventory_variable_hex_ids(stdout, envelope)
            tree = ET.parse(raw / 'results/extracted.repository')
            loops = Counter(node.attrib.get('specification', '') for node in tree.iter('iterationCount_LoopAction'))
            mapping = _read(projected / 'mapping.json')
            operation_labels = {row['pmx_operation']: {key: row[key] for key in ('service', 'operation', 'instance_key', 'instance_value', 'synthetic')} for row in mapping}
            unsupported = [dict(row, native_identity=operation_labels[row['operation']]) for row in _read(projected / 'operation_oracle.json')
                if row['conditional_local_probability'] is None or not row['observed_propagation_compatible']]
            cases.append({'case_id': case['case_id'], 'original_inventory': original,
                'variable_hex_inventory': revised, 'loop_specification_counts': dict(loops),
                'unsupported_conditional_local_operations': unsupported, 'source_pcm_hashes': resolved['model_files'],
                'source_stdout_sha256': _hash(raw / 'stdout.log'), 'source_envelope_sha256': _hash(envelope_path)})
    _write(out / 'retained-request-audit.json', {'source_run_id': config['source_run_id'],
        'source_commit': config['source_head_sha'], 'audit_run_id': os.environ['GITHUB_RUN_ID'],
        'audit_commit': os.environ['GITHUB_SHA'], 'config_sha256': _hash(config_path),
        'cases': cases, 'metadata': metadata, 'new_pmx_invocations': 0,
        'new_fits': 0, 'new_solver_calls': 0, 'evaluator_rows_read': 0})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/m9v_retained_request_audit.json'))
    parser.add_argument('--inputs', type=Path, default=Path('workflow-input/m9v-retained'))
    parser.add_argument('--out', type=Path, default=Path('workflow-results/m9v-retained'))
    args = parser.parse_args()
    run(args.config, args.inputs, args.out)


if __name__ == '__main__':
    main()
