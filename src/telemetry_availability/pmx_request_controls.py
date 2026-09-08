"""Artificial, independently specified request-boundary controls for PMX."""
from datetime import datetime, timezone

from .pmx_observed_operations import NativeSpan
from .pmx_request_adapter import project_campaign

CASES = ('nested_propagated', 'compound_http', 'absent_trace',
         'unmarked_service_boundary', 'repeated_http_and_collision', 'swallowed_child')
SUCCESS = {
    'nested_propagated': {'inclusive': .576, 'conditional_local': .8},
    'compound_http': {'inclusive': .81, 'conditional_local': .9},
    'absent_trace': {'inclusive': .8, 'conditional_local': .8},
    'unmarked_service_boundary': {'inclusive': .576, 'conditional_local': .8},
    'repeated_http_and_collision': {'inclusive': .6561, 'conditional_local': .729},
    'swallowed_child': {'inclusive': .9},
}


def fixture(case):
    if case not in CASES:
        raise ValueError('unknown artificial case')
    grouped, requests = {}, []
    policy = 'service_boundary' if case == 'unmarked_service_boundary' else 'explicit_server'
    for index in range(10):
        trace = f'{index+1:032x}'
        base = 1800000000000000 + index*100000
        def span(number, parent, service, operation, failed, offset=1000, attrs=None, server=True):
            duration = 30000 if number == 1 and case in ('nested_propagated', 'swallowed_child', 'unmarked_service_boundary') else 5000
            return NativeSpan(trace, f'{number:016x}', f'{parent:016x}' if parent else '',
                service, operation, server, base+offset, duration, 0, 0, attrs or {},
                {'service.instance.id': service+'-instance'}, failed, False,
                'SERVER' if server else 'unmarked', [])
        failed = index < (2 if case in ('nested_propagated', 'absent_trace', 'unmarked_service_boundary') else 1)
        if case == 'swallowed_child':
            failed = False
        if case in ('nested_propagated', 'swallowed_child'):
            spans = [span(1, 0, 'front', 'handle', index < 2 if case == 'nested_propagated' else False),
                     span(2, 1, 'child', 'call', index == 0, 2000),
                     span(3, 1, 'sibling', 'call', False, 9000)]
        elif case == 'unmarked_service_boundary':
            spans = [span(1, 0, 'web', 'handle', index < 2, server=False),
                     span(2, 1, 'web', 'client', index == 0, 2000, server=False),
                     span(3, 2, 'worker', 'call', index == 0, 3000, server=False)]
        elif case == 'absent_trace':
            spans = []
        else:
            paths = ['/api/products/item', '/api/cart', '/api/checkout'] if case == 'compound_http' else ['/api/cart', '/api/cart', '/api/checkout']
            spans = [span(j+1, 0, 'proxy', 'GET' if 'products' in path else 'POST',
                          index == 0 and (j == 2 or case == 'repeated_http_and_collision'),
                          1000+j*10000, {'http.method': 'GET' if 'products' in path else 'POST',
                                        'http.target': path+'?ignored=true'}) for j, path in enumerate(paths)]
        grouped[trace] = spans
        iso = lambda value: datetime.fromtimestamp(value/1000000, timezone.utc).isoformat()
        requests.append({'profile': 'fixture', 'period': 'calibration', 'operation': case,
            'request_id': str(index), 'trace_id': trace, 'started_at': iso(base),
            'completed_at': iso(base+40000), 'semantic_success': not failed,
            'timed_out': failed and case == 'absent_trace'})
    result = project_campaign(grouped, requests, policy, 'fixture-worker')
    operations = result['operation_oracle']
    expected = {'case': case, 'success': SUCCESS[case],
        'operations': {row['operation']: row['inclusive_probability'] for row in operations},
        'operation_components': {row['operation']: row['component'] for row in operations},
        'component_hosts': {row['component']: 'FIXTURE-WORKER-SRV' for row in operations},
        'edges': sorted([[row['caller'], row['callee']] for row in result['edge_oracle']]),
        'entry_operation_counts': {key: 1 for key in result['entry_counts']},
        'leaf_operation_seconds': {}, 'native_requests': len(requests),
        'conditional_supported': case != 'swallowed_child',
        'independent_software_oracle': 'explicit ten-request failure pattern and independent serial-call composition',
        'empirical_external_success': sum(row['semantic_success'] for row in requests)/10,
        'correlated_repeated_case_does_not_identify_independence': case == 'repeated_http_and_collision'}
    return result, expected, grouped, requests
