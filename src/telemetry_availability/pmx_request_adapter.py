"""Disclosed external-request projection for independently parameterized PMX."""
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from urllib.parse import urlsplit

from .pmx_observed_operations import AdapterError, NativeSpan, _digest, _id, _identity, _tag
from .pmx_request_census import truth


def epoch_microseconds(value):
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if timestamp.tzinfo is None:
        raise AdapterError('request timestamp has no timezone')
    delta = timestamp - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def qualified_operation(span):
    """Preserve native operation and an observed HTTP path when one is present."""
    method = span.attributes.get('http.request.method', span.attributes.get('http.method', ''))
    for key in ('http.route', 'url.path', 'http.target', 'http.url', 'url.full'):
        value = span.attributes.get(key)
        if isinstance(value, str) and value:
            path = urlsplit(value).path
            if path and path != '/':
                return json.dumps([span.operation, str(method), path], separators=(',', ':')), key
    return span.operation, None


def project_request(spans, request, policy, declared_host):
    if request['period'] != 'calibration':
        raise AdapterError('PMX request fitting uses calibration only')
    if policy not in ('explicit_server', 'service_boundary') or not declared_host:
        raise AdapterError('unknown operation boundary or absent declared host')
    trace_id = _id(request['trace_id'])
    by_id = {}
    for span in spans:
        if span.trace_id != trace_id:
            raise AdapterError('mixed request trace identity')
        if span.span_id in by_id and by_id[span.span_id] != span:
            raise AdapterError('conflicting duplicate span')
        by_id[span.span_id] = span
    for key in by_id:
        current, visited = key, set()
        while current in by_id:
            if current in visited:
                raise AdapterError('native parent cycle')
            visited.add(current)
            current = by_id[current].parent_id
    selected = {key: span for key, span in by_id.items() if
                (policy == 'explicit_server' and span.server) or
                (policy == 'service_boundary' and
                 (span.parent_id not in by_id or by_id[span.parent_id].service != span.service))}
    wrapper_id = _digest(['m9u-external-request-v1', trace_id, request['request_id']])[:16]
    if wrapper_id in by_id:
        raise AdapterError('synthetic wrapper identifier collision')
    request_start = epoch_microseconds(request['started_at'])
    request_end = epoch_microseconds(request['completed_at'])
    if request_start < 1 or request_end <= request_start:
        raise AdapterError('invalid request interval')
    enclosure_start = min([request_start] + [span.start_us for span in selected.values()]) - 1
    enclosure_end = max([request_end] + [span.start_us + span.duration_us for span in selected.values()]) + 1
    if enclosure_start < 0:
        raise AdapterError('negative structural enclosure time')
    wrapper = NativeSpan(
        trace_id, wrapper_id, '', 'taid.external.' + request['profile'], request['operation'],
        True, enclosure_start, enclosure_end-enclosure_start, 0, 0, {},
        {'service.instance.id': 'declared-request-boundary'}, not truth(request['semantic_success']),
        False, 'synthetic_external_request', [])
    projected = [wrapper]
    parent_records = []
    for key, span in selected.items():
        cursor, contracted = span.parent_id, []
        while cursor in by_id and cursor not in selected:
            contracted.append(cursor)
            cursor = by_id[cursor].parent_id
        parent_id = cursor if cursor in selected else wrapper_id
        label, label_source = qualified_operation(span)
        resources = dict(span.resource_attributes)
        if not any(resources.get(key) for key in
                   ('service.instance.id', 'container.id', 'container.name', 'k8s.pod.name', 'host.name')):
            if resources.get('hostname'):
                resources['host.name'] = str(resources['hostname'])
        projected.append(replace(span, parent_id=parent_id, operation=label,
                                 resource_attributes=resources))
        parent_records.append({'span_id': key, 'native_span': asdict(span),
                               'projected_parent_id': parent_id, 'contracted_ancestors': contracted,
                               'attached_to_external_wrapper': parent_id == wrapper_id,
                               'unresolved_native_parent': cursor if cursor and cursor not in selected else '',
                               'operation_label': label, 'operation_label_source': label_source})
    projected.sort(key=lambda span: (span.start_us, span.span_id))
    processes, records, mapping = {}, [], []
    for span in projected:
        component, operation, instance_key, instance_value, process_id = _identity(span)
        processes[process_id] = {'id': process_id, 'serviceName': component,
                                'tags': [_tag('host.name', declared_host)]}
        records.append({'traceID': trace_id, 'spanID': span.span_id, 'flags': 1,
                        'operationName': operation, 'processID': process_id,
                        'startTime': span.start_us, 'duration': span.duration_us,
                        'references': [] if span.span_id == wrapper_id else
                            [{'refType': 'CHILD_OF', 'traceID': trace_id, 'spanID': span.parent_id}],
                        'tags': [_tag('otel.library.name', 'adapter.spring-webmvc.m9u'),
                                 _tag('error', 'true' if span.error else 'false')], 'logs': []})
        mapping.append({'trace_id': trace_id, 'span_id': span.span_id,
                        'pmx_component': component, 'pmx_operation': operation,
                        'pmx_parent_span_id': span.parent_id, 'service': span.service,
                        'operation': span.operation, 'instance_key': instance_key,
                        'instance_value': instance_value, 'synthetic': span.span_id == wrapper_id,
                        'native_server_kind_observed': span.server if span.span_id != wrapper_id else False,
                        'error': span.error, 'declared_host': declared_host})
    wrapper_operation = next(row['pmx_operation'] for row in mapping if row['synthetic'])
    return {
        'trace': {'traceID': trace_id, 'startTime': enclosure_start, 'processes': processes, 'spans': records},
        'mapping': mapping, 'native_audit': parent_records,
        'request_audit': {'request_id': request['request_id'], 'trace_id': trace_id,
                          'request_operation': request['operation'], 'policy': policy,
                          'semantic_success': truth(request['semantic_success']),
                          'timed_out': truth(request['timed_out']),
                          'original_native_spans': len(by_id), 'selected_native_spans': len(selected),
                          'no_native_trace': not by_id, 'no_selected_native_spans': not selected,
                          'native_root_count': sum(span.parent_id not in by_id for span in by_id.values()),
                          'attached_projected_roots': sum(row['attached_to_external_wrapper'] for row in parent_records),
                          'external_wrapper_operation': wrapper_operation,
                          'external_outcome_used_for_wrapper': True,
                          'wrapper_duration_is_structural_enclosure': True,
                          'recorded_request_duration_us': request_end-request_start},
    }


def project_campaign(grouped, requests, policy, declared_host, invalid=None):
    invalid = invalid or {}
    identities = [(row['request_id'], _id(row['trace_id'])) for row in requests]
    if (len({key[0] for key in identities}) != len(identities)
            or len({key[1] for key in identities}) != len(identities)):
        raise AdapterError('duplicate request or trace identity')
    traces, mapping, native_audit, request_audit, rejected = [], [], [], [], []
    for request in requests:
        trace_id = _id(request['trace_id'])
        if trace_id in invalid:
            rejected.append({'request_id': request['request_id'], 'trace_id': trace_id,
                             'status': 'invalid_native_trace', 'reasons': invalid[trace_id]})
            continue
        projected = project_request(grouped.get(trace_id, []), request, policy, declared_host)
        traces.append(projected['trace'])
        mapping.extend(projected['mapping'])
        native_audit.extend(projected['native_audit'])
        request_audit.append(projected['request_audit'])
    operations, edges, entries = {}, Counter(), Counter()
    for trace in traces:
        spans = {span['spanID']: span for span in trace['spans']}
        children = defaultdict(list)
        for span in spans.values():
            if span['references']:
                children[span['references'][0]['spanID']].append(span)
            else:
                entries[span['operationName']] += 1
        error = lambda span: any(tag['key'] == 'error' and tag['value'] == 'true' for tag in span['tags'])
        for span in spans.values():
            operation = span['operationName']
            row = operations.setdefault(operation, {'operation': operation,
                'component': trace['processes'][span['processID']]['serviceName'],
                'invocations': 0, 'inclusive_errors': 0, 'child_error_parent_success': 0,
                'no_child_error_invocations': 0, 'local_errors_without_child_error': 0})
            failed, child_failed = error(span), any(error(child) for child in children[span['spanID']])
            row['invocations'] += 1
            row['inclusive_errors'] += failed
            row['child_error_parent_success'] += child_failed and not failed
            row['no_child_error_invocations'] += not child_failed
            row['local_errors_without_child_error'] += failed and not child_failed
            if span['references']:
                parent = spans[span['references'][0]['spanID']]
                edges[(parent['operationName'], operation)] += 1
    for row in operations.values():
        row['inclusive_probability'] = row['inclusive_errors'] / row['invocations']
        denominator = row['no_child_error_invocations']
        row['conditional_local_probability'] = (row['local_errors_without_child_error'] / denominator
                                                if denominator else None)
        row['observed_propagation_compatible'] = row['child_error_parent_success'] == 0
    return {'envelope': {'data': traces}, 'mapping': mapping, 'native_audit': native_audit,
            'request_audit': request_audit, 'rejected_requests': rejected,
            'operation_oracle': sorted(operations.values(), key=lambda row: row['operation']),
            'edge_oracle': [{'caller': key[0], 'callee': key[1], 'calls': value}
                            for key, value in sorted(edges.items())],
            'entry_counts': dict(entries), 'summary': {
                'requests': len(requests), 'projected_requests': len(traces), 'rejected_requests': len(rejected),
                'selected_native_spans': len(native_audit), 'synthetic_wrappers': len(traces),
                'no_native_trace_requests': sum(row['no_native_trace'] for row in request_audit),
                'unsupported_conditional_local_operations': sum(row['conditional_local_probability'] is None
                     or not row['observed_propagation_compatible'] for row in operations.values()),
                'native_input_independent_of_proposed_fits': True, 'evaluator_rows_read': 0,
                'external_semantic_outcomes_are_additional_inputs': True}}
