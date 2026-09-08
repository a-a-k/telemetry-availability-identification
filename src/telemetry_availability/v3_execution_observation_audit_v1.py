"""Census execution evidence in the ordinary role; never infer success from no error."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from .b0_frequency_v3_csv_v2 import decode_outcome
from .v3_graph_input_inventory import ReadBoundary, inventory
from .v3_primary_projection import read, write

VERSION = 'v3-execution-observation-audit-v1'
STATUS_FIELDS = ('http.response.status_code', 'http.status_code',
                 'rpc.grpc.status_code', 'rpc.response.status_code', 'rpc.status_code')


def timestamp_ns(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('request timestamp lacks timezone')
    delta = stamp.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds) * 1000


def boundary_context(profile, request_id):
    if profile == 'spring_petclinic_microservices':
        return (hashlib.sha256(request_id.encode()).hexdigest()[:32],
                hashlib.sha256(('client:' + request_id).encode()).hexdigest()[:16])
    digest = hashlib.sha256((profile + '|' + request_id).encode()).hexdigest()
    if profile not in ('deathstarbench_social_network', 'opentelemetry_demo'):
        raise ValueError('unknown request context contract')
    return digest[:16] if profile == 'deathstarbench_social_network' else digest[:32], digest[32:48]


def span_interval(span):
    fields = ('start_us', 'start_remainder_ns', 'duration_us', 'duration_remainder_ns')
    if any(type(span[k]) is not int for k in fields):
        raise ValueError('noninteger span time')
    if (span['start_us'] < 0 or span['duration_us'] < 0 or
            not 0 <= span['start_remainder_ns'] < 1000 or
            not 0 <= span['duration_remainder_ns'] < 1000):
        raise ValueError('invalid span time')
    start = span['start_us'] * 1000 + span['start_remainder_ns']
    duration = span['duration_us'] * 1000 + span['duration_remainder_ns']
    if duration <= 0:
        raise ValueError('nonpositive span duration')
    return start, start + duration


def interval_union_ns(intervals):
    total = 0
    end = None
    for left, right in sorted(intervals):
        if right < left:
            raise ValueError('reversed interval')
        total += right - left if end is None or left >= end else max(0, right - end)
        end = right if end is None else max(end, right)
    return total


def summarize(requests, native, declarations, operations, deadline_ns=2000000000):
    """All attempts, outcome-specific coverage, exact timestamps; no fitted probability."""
    if type(deadline_ns) is not int or deadline_ns <= 0:
        raise ValueError('invalid declared deadline')
    if not operations or len(operations) != len(set(operations)):
        raise ValueError('invalid operation census')
    ids = set()
    traces = set()
    for row in requests:
        if (row['request_id'] in ids or row['trace_id'] in traces or
                row['period'] != 'calibration' or row['operation'] not in operations):
            raise ValueError('duplicate identity or invalid operation/period')
        ids.add(row['request_id']); traces.add(row['trace_id'])
    if (native['calibration_only'] is not True or set(native['selected_trace_ids']) != traces or
            len(native['selected_trace_ids']) != len(traces) or not set(native['spans']) <= traces):
        raise ValueError('native role/census mismatch')
    output = {}
    target = declarations['target_service']
    for operation in operations:
        rows = [r for r in requests if r['operation'] == operation]
        totals = Counter()
        hist = defaultdict(Counter)
        by_outcome = {key: Counter() for key in ('success', 'failure', 'timeout')}
        services = defaultdict(Counter)
        target_instances = Counter()
        target_replicas = Counter()
        status_values = {key: Counter() for key in STATUS_FIELDS}
        for row in rows:
            success = decode_outcome(row['semantic_success'])
            timeout = decode_outcome(row['timed_out'])
            if success and timeout:
                raise ValueError('successful timeout')
            started = timestamp_ns(row['started_at'])
            completed = timestamp_ns(row['completed_at'])
            if completed < started:
                raise ValueError('reversed request timestamps')
            trace, external_parent = boundary_context(declarations['profile'], row['request_id'])
            if trace != row['trace_id']:
                raise ValueError('external trace context mismatch')
            spans = native['spans'].get(trace, [])
            indexed = {s['span_id']: s for s in spans}
            if len(indexed) != len(spans) or any(s['trace_id'] != trace for s in spans):
                raise ValueError('duplicate/conflicting native span identity')
            roots = [s for s in spans if s['parent_id'] == external_parent]
            orphan = [s for s in spans if s['parent_id'] not in indexed and s['parent_id'] != external_parent]
            target_server = [s for s in spans if s['service'] == target and s['server']]
            for span in spans:
                if any(type(span[k]) is not bool for k in ('server', 'error_tag', 'error_status')):
                    raise ValueError('invalid normalized span flags')
                span_interval(span)
                key = span['service']
                services[key]['spans'] += 1
                services[key]['server_spans'] += span['server']
                services[key]['error_flagged_spans'] += span['error_tag'] or span['error_status']
                services[key]['spans_with_status_attribute'] += any(k in span['attributes'] for k in STATUS_FIELDS)
                services[key]['spans_with_instance_id'] += bool(span['resource_attributes'].get('service.instance.id'))
                for attr in STATUS_FIELDS:
                    if attr in span['attributes']:
                        status_values[attr][str(span['attributes'][attr])] += 1
            for span in target_server:
                resource = span['resource_attributes']
                target_instances[str(resource.get('service.instance.id') or '<missing>')] += 1
                target_replicas[str(resource.get('study.replica') or '<missing>')] += 1
            errors = sum(s['error_tag'] or s['error_status'] for s in spans)
            root_intervals = [span_interval(s) for s in roots]
            sum_root = sum(right - left for left, right in root_intervals)
            union_root = interval_union_ns(root_intervals)
            facts = dict(attempts=1, successes=int(success), failures=int(not success), timeouts=int(timeout),
                attempts_with_native=int(bool(spans)), attempts_without_native=int(not spans),
                attempts_with_native_error=int(errors > 0),
                attempts_with_native_but_no_error_flag=int(bool(spans) and errors == 0),
                attempts_with_target_server=int(bool(target_server)),
                attempts_with_unexplained_parent=int(bool(orphan)),
                attempts_with_multiple_external_roots=int(len(roots) > 1),
                attempts_with_target_instance_for_every_observed_server=int(bool(target_server) and all(
                    s['resource_attributes'].get('service.instance.id') for s in target_server)),
                attempts_with_target_replica_for_every_observed_server=int(bool(target_server) and all(
                    s['resource_attributes'].get('study.replica') in declarations['replicas'] for s in target_server)),
                attempts_with_native_end_after_external_completion=int(any(span_interval(s)[1] > completed for s in spans)),
                attempts_with_native_end_after_declared_deadline=int(any(span_interval(s)[1] > started + deadline_ns for s in spans)),
                attempts_with_root_sum_above_deadline=int(sum_root > deadline_ns),
                attempts_with_root_union_above_deadline=int(union_root > deadline_ns),
                attempts_with_overlapping_external_roots=int(sum_root > union_root),
                external_elapsed_above_deadline=int(completed - started > deadline_ns),
                spans=len(spans), native_error_spans=errors, unexplained_parent_spans=len(orphan))
            totals.update(facts)
            by_outcome['success' if success else 'failure'].update(facts)
            if timeout:
                by_outcome['timeout'].update(facts)
            for key, value in [('external_root_count', len(roots)), ('target_server_count', len(target_server)),
                               ('native_error_span_count', errors), ('unexplained_parent_count', len(orphan))]:
                hist[key][str(value)] += 1
        output[operation] = dict(census=dict(totals),
            outcome_census={k: {field: v[field] for field in totals} for k, v in by_outcome.items()},
            histograms={k: dict(sorted(v.items())) for k, v in hist.items()},
            service_evidence={k: dict(v) for k, v in sorted(services.items())},
            target_instance_span_counts=dict(target_instances), target_replica_span_counts=dict(target_replicas),
            native_status_attribute_counts={k: dict(v) for k, v in status_values.items()},
            forecast=None, forecast_status='observation_audit_only')
    return dict(version=VERSION, operations=output, external_attempts=len(requests),
        declared_deadline_ns=deadline_ns, main_campaigns=0, model_fits=0,
        no_error_flag_is_semantic_success=False, timeout_census_overlaps_failure_census=True,
        cross_service_clock_alignment_assumed_for_timing_diagnostics=True,
        sum_of_span_durations_is_whole_operation_duration=False,
        complete_execution_or_routing_identity_inferred_from_missing_spans=False)


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Native application audit is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--operations', nargs='+', required=True)
    args = parser.parse_args()
    root = args.input.resolve(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    boundary = ReadBoundary(root, out)
    started = time.perf_counter(); sys.addaudithook(boundary.hook)
    try:
        graph = inventory(root)
        report = summarize(read(root/'requests.json'), read(root/'native.json'),
                           read(root/'declarations.json'), args.operations)
        assert set(graph['graphs']) == set(report['operations'])
        assert graph['manifest']['external_attempts'] == report['external_attempts']
        report['input_seal'] = graph['original_input_seal']
        report['manifest'] = graph['manifest']
        report['graph_inventory'] = graph['graphs']
        assert not boundary.blocked and boundary.reads == {str(p) for p in boundary.allowed}
    finally:
        boundary.active = False
        write(out/'consumer-read-audit.json', dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
            ordinary_files_only=True, boundary_covers_all_loading=True))
    report['elapsed_seconds'] = time.perf_counter() - started
    write(out/'execution-observation-audit.json', report)


if __name__ == '__main__':
    main()
