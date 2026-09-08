"""Explicit full observed caller context, preserving M9U request evidence."""
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace

from .pmx_observed_operations import AdapterError, _digest
from .pmx_request_adapter import project_campaign
from .pmx_request_controls import fixture

CONTEXT_VERSION = 'observed-full-caller-context-v1'
CONTROL_SUCCESS = {
    'recursive_native_name': {'inclusive': .576, 'conditional_local': .8},
    'cross_trace_call_order': {'inclusive': 1., 'conditional_local': 1.},
}


def contextualize(projection):
    result = deepcopy(projection)
    contexts, new_to_context = {}, {}
    source_count = 0
    for trace in result['envelope']['data']:
        spans = {s['spanID']: s for s in trace['spans']}
        if len(spans) != len(trace['spans']):
            raise AdapterError('duplicate projected span')
        original = {sid: span['operationName'] for sid, span in spans.items()}
        paths = {}
        for sid in spans:
            cursor, ancestors, visited = sid, [], set()
            while cursor:
                if cursor in visited or cursor not in spans:
                    raise AdapterError('projected parent cycle or missing parent')
                visited.add(cursor)
                ancestors.append(original[cursor])
                refs = spans[cursor]['references']
                if len(refs) > 1 or (refs and refs[0]['traceID'] != trace['traceID']):
                    raise AdapterError('unsupported projected parent reference')
                cursor = refs[0]['spanID'] if refs else ''
            path = tuple(reversed(ancestors))
            operation = 'operation_' + _digest([CONTEXT_VERSION, *path])[:24]
            if operation in new_to_context and new_to_context[operation] != path:
                raise AdapterError('context identity hash collision')
            new_to_context[operation] = path
            paths[sid] = path
            identity = (trace['traceID'], sid)
            if identity in contexts:
                raise AdapterError('duplicate request trace/span identity')
            contexts[identity] = (operation, path, original[sid])
        for sid, span in spans.items():
            operation, _, _ = contexts[trace['traceID'], sid]
            span['operationName'] = operation
            if span['references']:
                parent = span['references'][0]['spanID']
                assert len(paths[sid]) == len(paths[parent]) + 1
            source_count += 1
    mapping_ids, wrappers_by_trace = set(), defaultdict(list)
    for row in result['mapping']:
        identity = (row['trace_id'], row['span_id'])
        if identity in mapping_ids:
            raise AdapterError('duplicate provenance mapping')
        mapping_ids.add(identity)
        operation, path, original = contexts[identity]
        if row['pmx_operation'] != original:
            raise AdapterError('provenance operation differs from envelope')
        row.update(pmx_operation=operation, base_pmx_operation=original,
                   observed_caller_operation_path=list(path), operation_identity_version=CONTEXT_VERSION)
        if row['synthetic']:
            wrappers_by_trace[row['trace_id']].append(row)
    if mapping_ids != set(contexts):
        raise AdapterError('incomplete provenance mapping')
    for request in result['request_audit']:
        trace_id = request['trace_id']
        wrappers = wrappers_by_trace[trace_id]
        if len(wrappers) != 1:
            raise AdapterError('external request wrapper is not unique')
        request['base_external_wrapper_operation'] = request['external_wrapper_operation']
        request['external_wrapper_operation'] = wrappers[0]['pmx_operation']

    operations, edges, entries = {}, Counter(), Counter()
    for trace in result['envelope']['data']:
        spans = {s['spanID']:s for s in trace['spans']}
        children = defaultdict(list)
        for span in spans.values():
            if span['references']:
                children[span['references'][0]['spanID']].append(span)
            else:
                entries[span['operationName']] += 1
        failed = lambda span: any(t['key']=='error' and t['value']=='true' for t in span['tags'])
        for span in spans.values():
            operation = span['operationName']
            component = trace['processes'][span['processID']]['serviceName']
            row = operations.setdefault(operation,dict(operation=operation,component=component,
                invocations=0,inclusive_errors=0,child_error_parent_success=0,
                no_child_error_invocations=0,local_errors_without_child_error=0))
            assert row['component'] == component
            error, child_error = failed(span), any(failed(s) for s in children[span['spanID']])
            row['invocations'] += 1
            row['inclusive_errors'] += error
            row['child_error_parent_success'] += child_error and not error
            row['no_child_error_invocations'] += not child_error
            row['local_errors_without_child_error'] += error and not child_error
            if span['references']:
                parent = spans[span['references'][0]['spanID']]
                edges[(parent['operationName'],operation)] += 1
    for row in operations.values():
        row['inclusive_probability'] = row['inclusive_errors']/row['invocations']
        denominator = row['no_child_error_invocations']
        row['conditional_local_probability'] = row['local_errors_without_child_error']/denominator if denominator else None
        row['observed_propagation_compatible'] = row['child_error_parent_success']==0
    # Every edge strictly increases observed path length, so the operation graph is a DAG.
    assert all(len(new_to_context[b]) == len(new_to_context[a])+1 for a,b in edges)
    result.update(operation_oracle=sorted(operations.values(),key=lambda r:r['operation']),
                  edge_oracle=[dict(caller=a,callee=b,calls=n) for (a,b),n in sorted(edges.items())],
                  entry_counts=dict(entries))
    result['summary'].update(operation_identity_version=CONTEXT_VERSION,
        base_operations=len({v[2] for v in contexts.values()}),context_operations=len(operations),
        context_edges_strictly_increase_depth=True,context_operation_graph_acyclic=True,
        projected_spans=source_count,
        unsupported_conditional_local_operations=sum(r['conditional_local_probability'] is None or not r['observed_propagation_compatible'] for r in operations.values()))
    # Establish exact invariance of every envelope field other than operation identity.
    restored = deepcopy(result['envelope'])
    for trace in restored['data']:
        for span in trace['spans']:
            span['operationName'] = contexts[trace['traceID'],span['spanID']][2]
    if restored != projection['envelope']:
        raise AdapterError('context projection changed native evidence')
    if result['native_audit'] != projection['native_audit']:
        raise AdapterError('context projection changed native provenance')
    result['summary']['all_non_identity_envelope_fields_preserved'] = True
    return result


def expected_pcm(projection):
    operations = projection['operation_oracle']
    return dict(operations={r['operation']:r['inclusive_probability'] for r in operations},
                operation_components={r['operation']:r['component'] for r in operations},
                component_hosts={r['pmx_component']:r['declared_host'].upper()+'-SRV' for r in projection['mapping']},
                edges=sorted([[r['caller'],r['callee']] for r in projection['edge_oracle']]),
                entry_operation_counts={k:1 for k in projection['entry_counts']},leaf_operation_seconds={})


def control(case):
    _, _, grouped, requests = fixture('nested_propagated')
    if case not in CONTROL_SUCCESS:
        raise ValueError('unknown context control')
    for index, request in enumerate(requests):
        request['operation'] = case
        spans = grouped[request['trace_id']]
        if case == 'recursive_native_name':
            spans[1] = replace(spans[1],service=spans[0].service,operation=spans[0].operation,
                               resource_attributes=dict(spans[0].resource_attributes))
        else:
            labels = ('A','B') if index%2==0 else ('B','A')
            spans = [replace(s,service=label,operation=label,
                             resource_attributes={'service.instance.id':label+'-instance'},
                             error_tag=False,error_status=False) for s,label in zip(spans[:2],labels)]
            request['semantic_success'] = True
        grouped[request['trace_id']] = spans
    base = project_campaign(grouped,requests,'explicit_server','fixture-worker')
    projected = contextualize(base)
    expected = expected_pcm(projected)
    expected['success'] = CONTROL_SUCCESS[case]
    return base, projected, expected
