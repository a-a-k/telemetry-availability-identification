import unittest

from telemetry_availability.pmx_observed_operations import from_jaeger
from telemetry_availability.pmx_request_census import census


def artificial_trace():
    trace_id = 'a' * 32
    trace = {'traceID': trace_id, 'processes': {
        'gateway': {'serviceName': 'gateway', 'tags': []},
        'worker': {'serviceName': 'worker', 'tags': []},
    }}
    spans = []
    for span_id, parent_id, service, error, kind in (
            ('01', None, 'gateway', False, ''),
            ('02', '01', 'gateway', True, 'client'),
            ('03', '02', 'worker', True, 'server')):
        span = {'traceID': trace_id, 'spanID': span_id, 'operationName': 'root' if parent_id is None else 'call',
                'processID': service, 'startTime': 100, 'duration': 10,
                'tags': [{'key': 'error', 'value': error}, {'key': 'span.kind', 'value': kind}],
                'references': [] if parent_id is None else [{'refType': 'CHILD_OF', 'spanID': parent_id}]}
        spans.append(from_jaeger(trace, span))
    return trace_id, spans


class PmxRequestCensusTests(unittest.TestCase):
    def test_census_keeps_missing_requests_and_swallowed_child_errors(self):
        trace_id, spans = artificial_trace()
        requests = [dict(period='calibration', operation='checkout', trace_id=trace_id,
                         semantic_success='True', timed_out='False'),
                    dict(period='calibration', operation='checkout', trace_id='b'*32,
                         semantic_success='False', timed_out='True')]
        result = census({trace_id: spans}, requests, {})
        counts = result['request_rows'][0]
        self.assertEqual((counts['requests'], counts['successes'], counts['missing_native_trace']), (2, 1, 1))
        self.assertEqual(counts['successful_requests_with_span_error'], 1)
        root = next(row for row in result['operation_rows'] if row['policy'] == 'service_boundary'
                    and row['service'] == 'gateway')
        self.assertEqual(root['child_error_parent_success'], 1)
        self.assertEqual(root['observed_child_calls'], 1)
        self.assertEqual(root['parent_root_invocations'], 1)
        server_rows = [row for row in result['operation_rows'] if row['policy'] == 'explicit_server']
        self.assertEqual(len(server_rows), 1)
        self.assertEqual(server_rows[0]['service'], 'worker')

    def test_test_period_is_rejected_and_invalid_trace_is_retained(self):
        request = dict(period='test', operation='checkout', trace_id='a'*32,
                       semantic_success='False', timed_out='False')
        with self.assertRaises(ValueError):
            census({}, [request], {})
        request['period'] = 'baseline'
        result = census({}, [request], {'a'*32: ['invalid']})
        self.assertEqual(result['request_rows'][0]['invalid_native_trace'], 1)
        self.assertEqual(result['operation_rows'], [])


if __name__ == '__main__':
    unittest.main()
