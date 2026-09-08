import unittest
from telemetry_availability.pmx_retained_request_audit import inventory_variable_hex_ids
from telemetry_availability.pmx_usage_contract_audit import reconstructed_inventory


class PrintedTraceIdentityTests(unittest.TestCase):
    def inputs(self, width):
        trace = 'a'*width
        operation = 'operation_'+'b'*24
        span = 'c'*16
        envelope = {'data': [{'traceID': trace, 'spans': [{'spanID': span, 'operationName': operation,
            'startTime': 100, 'duration': 50, 'references': []}]}]}
        divider = '#'*42
        log = f'{divider}\n{operation} / {span} / null\n{divider}\nExecutionTrace minTin=100000, maxTout=150000, executions=[{trace}{operation} <NOSESSIONID>], invalidExecutions=[]\n'
        return log, envelope

    def test_short_native_trace_id_is_not_a_missing_execution(self):
        log, envelope = self.inputs(16)
        with self.assertRaisesRegex(Exception, 'unresolved_reconstructed_trace'):
            reconstructed_inventory(log, envelope)
        result = inventory_variable_hex_ids(log, envelope)
        self.assertTrue(result['exact_trace_span_operation_parent_inventory'])
        self.assertTrue(result['each_trace_reconstructed_once'])
        self.assertTrue(result['reconstructed_nanosecond_bounds_match_input_microseconds'])

    def test_existing_long_trace_contract_is_preserved(self):
        log, envelope = self.inputs(32)
        result = inventory_variable_hex_ids(log, envelope)
        original = reconstructed_inventory(log, envelope)
        self.assertTrue(all(result[key] == value for key, value in original.items()))

    def test_wrong_identity_and_invalid_execution_remain_failures(self):
        log, envelope = self.inputs(16)
        for altered in (log.replace('a'*16, 'd'*16), log.replace('invalidExecutions=[]', 'invalidExecutions=[bad]')):
            result = inventory_variable_hex_ids(altered, envelope)
            self.assertFalse(result['exact_trace_span_operation_parent_inventory'])
            self.assertEqual(result['unresolved_reconstructed_records'], 1)
