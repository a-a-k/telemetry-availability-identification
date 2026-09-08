"""Learner-only request/operation correspondence census; no fit or PMX call."""
import argparse
from collections import Counter, defaultdict
import csv
import os
from pathlib import Path
import time

from .pmx_composition_control import _download, _hash, _read, _remote, _write
from .pmx_application_census import historical_learner_ids, validate as validate_application
from .pmx_observed_operations import AdapterError, read_native


def truth(value):
    if value in (True, 'True', 'true', '1'):
        return True
    if value in (False, 'False', 'false', '0'):
        return False
    raise ValueError('invalid outcome value')


def census(grouped, requests, invalid):
    request_counts = defaultdict(Counter)
    operations = defaultdict(Counter)
    edges = Counter()
    for request in requests:
        if request['period'] not in ('baseline', 'calibration'):
            raise ValueError('request census must contain learner periods only')
        group = (request['period'], request['operation'])
        result = request_counts[group]
        success = truth(request['semantic_success'])
        result['requests'] += 1
        result['successes'] += success
        result['timeouts'] += truth(request['timed_out'])
        trace_id = request['trace_id'].lower()
        if trace_id in invalid:
            result['invalid_native_trace'] += 1
            continue
        if not grouped.get(trace_id):
            result['missing_native_trace'] += 1
            result['missing_trace_successes'] += success
            continue
        spans = grouped[trace_id]
        by_id = {}
        for span in spans:
            if span.span_id in by_id and span != by_id[span.span_id]:
                raise AdapterError('conflicting duplicate span')
            by_id[span.span_id] = span
        for span in by_id.values():
            seen, current = set(), span.span_id
            while current in by_id:
                if current in seen:
                    raise AdapterError('cyclic native trace')
                seen.add(current)
                current = by_id[current].parent_id
        result['native_spans'] += len(by_id)
        result['duplicate_records'] += len(spans) - len(by_id)
        roots = [span for span in by_id.values() if span.parent_id not in by_id]
        result['single_native_root_requests'] += len(roots) == 1
        result['multiple_native_root_requests'] += len(roots) > 1
        result['any_span_error_requests'] += any(span.error for span in by_id.values())
        result['successful_requests_with_span_error'] += success and any(span.error for span in by_id.values())
        for policy in ('all_observed_spans', 'explicit_server', 'service_boundary'):
            selected = {key: span for key, span in by_id.items() if
                        policy == 'all_observed_spans' or
                        (policy == 'explicit_server' and span.server) or
                        (policy == 'service_boundary' and
                         (span.parent_id not in by_id or by_id[span.parent_id].service != span.service))}
            parents, children = {}, defaultdict(list)
            for key, span in selected.items():
                parent = span.parent_id
                while parent in by_id and parent not in selected:
                    parent = by_id[parent].parent_id
                parents[key] = parent if parent in selected else None
                if parent in selected:
                    children[parent].append(span)
            observed_in_request = Counter()
            for key, span in selected.items():
                signature = (*group, policy, span.service, span.operation, span.native_kind)
                row = operations[signature]
                row['invocations'] += 1
                row['inclusive_errors'] += span.error
                row['parent_root_invocations'] += parents[key] is None
                row['on_successful_request_invocations'] += success
                row['error_on_successful_request_invocations'] += span.error and success
                child_error = any(child.error for child in children[key])
                row['invocations_with_child_error'] += child_error
                row['joint_parent_child_errors'] += span.error and child_error
                row['child_error_parent_success'] += child_error and not span.error
                row['invocations_without_child_error'] += not child_error
                row['parent_error_without_child_error'] += span.error and not child_error
                row['observed_child_calls'] += len(children[key])
                observed_in_request[signature] += 1
                if parents[key] is not None:
                    parent = selected[parents[key]]
                    edges[(*group, policy, parent.service, parent.operation, span.service, span.operation)] += 1
            for signature, count in observed_in_request.items():
                operations[signature]['requests_with_operation'] += 1
                operations[signature]['maximum_calls_in_one_request'] = max(
                    operations[signature]['maximum_calls_in_one_request'], count)
    return {
        'request_rows': [dict(period=key[0], request_operation=key[1], **value)
                         for key, value in sorted(request_counts.items())],
        'operation_rows': [dict(period=key[0], request_operation=key[1], policy=key[2],
                               service=key[3], span_operation=key[4], native_kind=key[5], **value)
                           for key, value in sorted(operations.items())],
        'edge_rows': [dict(period=key[0], request_operation=key[1], policy=key[2],
                          caller_service=key[3], caller_operation=key[4], callee_service=key[5],
                          callee_operation=key[6], calls=value) for key, value in sorted(edges.items())],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('configs/m9t_pmx_request_census.json'))
    parser.add_argument('--out', type=Path, default=Path('workflow-results/m9t-request-census'))
    parser.add_argument('--inputs', type=Path, default=Path('workflow-input/m9t-request-census'))
    args = parser.parse_args()
    _remote()
    config = _read(args.config)
    for lock in config['repository_locks']:
        if _hash(Path(lock['path'])) != lock['sha256']:
            raise ValueError('request census implementation differs')
    application = validate_application(Path('configs/m9q_application_census.json'))
    metadata = _download(config, args.inputs)
    source = args.inputs / 'preserved/m8-preserved'
    inventory_path = args.inputs / 'inventory/file-inventory.csv'
    if _hash(inventory_path) != application['inventory_file_sha256']:
        raise ValueError('source inventory differs')
    with inventory_path.open(newline='', encoding='utf-8-sig') as stream:
        inventory = {row['relative_path'].replace('\\', '/'): row for row in csv.DictReader(stream)
                     if row['evidence_group'] == 'raw_audit_sample'}
    learner_manifests = {}
    for path in (source / 'qualified').rglob('learner/manifest.json'):
        manifest = _read(path)
        if manifest.get('failure_law') == 'NCD' and manifest.get('repetition') == 0:
            key = (manifest['profile'], manifest['placement'])
            if key in learner_manifests:
                raise ValueError('duplicate learner identity')
            learner_manifests[key] = (path, manifest)
    reports = []
    for sample in application['samples']:
        started = time.perf_counter()
        raw = source / 'raw-audit-samples' / sample['artifact_directory']
        for name in ('campaign-manifest.json', 'trace-join.csv', sample['native_file']):
            path = raw / name
            record = inventory[sample['artifact_directory'] + '/' + name]
            if _hash(path) != record['sha256'] or path.stat().st_size != int(record['size_in_bytes']):
                raise ValueError('native source file differs')
        learner_path, learner = learner_manifests[(sample['profile'], sample['placement'])]
        requests_path = learner_path.parent / 'requests.csv'
        if _hash(requests_path) != learner['files']['requests_sha256']:
            raise ValueError('learner requests differ')
        with requests_path.open(newline='', encoding='utf-8-sig') as stream:
            requests = list(csv.DictReader(stream))
        selected, selection = historical_learner_ids(raw / 'trace-join.csv')
        if len(requests) != 3840 or {row['trace_id'].lower() for row in requests} != selected:
            raise ValueError('learner membership differs')
        grouped, parse = read_native(raw / sample['native_file'], selected, sample['native_format'])
        report = census(grouped, requests, parse['invalid_traces'])
        report.update(sample=sample, selection=selection, parse_invalid_traces=len(parse['invalid_traces']),
                      malformed_json_records=parse['malformed_json_records'],
                      source_learner_sha256=_hash(requests_path),
                      source_native_sha256=_hash(raw / sample['native_file']),
                      native_file_bytes=(raw / sample['native_file']).stat().st_size,
                      elapsed_seconds=time.perf_counter()-started)
        _write(args.out / (sample['key'] + '.json'), report)
        reports.append({key: value for key, value in report.items()
                        if key not in ('operation_rows', 'edge_rows')})
    _write(args.out / 'request-census.json', {
        'status': 'learner_request_correspondence_census_complete',
        'source_run_id': os.environ['GITHUB_RUN_ID'], 'source_commit': os.environ['GITHUB_SHA'],
        'config_sha256': _hash(args.config), 'historical_artifacts': metadata,
        'samples': reports, 'pmx_invocations': 0, 'fits': 0, 'evaluator_rows_read': 0,
        'new_live_campaigns': 0, 'availability_forecasts': 0,
        'candidate_policies_are_descriptive': True,
    })


if __name__ == '__main__':
    main()
