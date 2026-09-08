from copy import deepcopy
import unittest

from telemetry_availability.pmx_request_context import contextualize, control
from telemetry_availability.pmx_request_controls import fixture
from telemetry_availability.pmx_observed_operations import AdapterError


class ContextProjectionTests(unittest.TestCase):
    def test_native_recursive_identity_becomes_finite_dag_without_evidence_change(self):
        base,result,_=control('recursive_native_name')
        self.assertTrue(any(e['caller']==e['callee'] for e in base['edge_oracle']))
        self.assertTrue(all(e['caller']!=e['callee'] for e in result['edge_oracle']))
        self.assertEqual(base['native_audit'],result['native_audit'])
        self.assertTrue(result['summary']['all_non_identity_envelope_fields_preserved'])
        self.assertEqual(result['summary']['context_operations'],4)
        self.assertEqual(result['summary']['unsupported_conditional_local_operations'],0)
        self.assertEqual(sum(r['inclusive_errors'] for r in base['operation_oracle']),
                         sum(r['inclusive_errors'] for r in result['operation_oracle']))

    def test_cross_trace_reverse_call_order_splits_even_without_native_recursion(self):
        base,result,_=control('cross_trace_call_order')
        edges={(r['caller'],r['callee']) for r in base['edge_oracle']}
        self.assertTrue(any((b,a) in edges for a,b in edges))
        self.assertEqual(result['summary']['base_operations'],3)
        self.assertEqual(result['summary']['context_operations'],5)
        self.assertTrue(result['summary']['context_operation_graph_acyclic'])
        self.assertEqual(contextualize(base),result)

    def test_repeated_siblings_keep_one_context_and_both_invocations(self):
        base,*_=fixture('repeated_http_and_collision')
        result=contextualize(base)
        self.assertEqual(len(base['operation_oracle']),len(result['operation_oracle']))
        self.assertEqual(sorted(r['invocations'] for r in base['operation_oracle']),
                         sorted(r['invocations'] for r in result['operation_oracle']))
        self.assertIn(20,[r['invocations'] for r in result['operation_oracle']])
        base,*_=fixture('swallowed_child')
        self.assertGreater(contextualize(base)['summary']['unsupported_conditional_local_operations'],0)

    def test_rejects_actual_missing_or_cyclic_parents_and_incomplete_provenance(self):
        base,*_=control('recursive_native_name')
        for parent in ('ffffffffffffffff',base['envelope']['data'][0]['spans'][1]['spanID']):
            bad=deepcopy(base)
            span=bad['envelope']['data'][0]['spans'][1]
            span['references'][0]['spanID']=parent
            with self.assertRaises(AdapterError):contextualize(bad)
        bad=deepcopy(base);bad['mapping'].pop()
        with self.assertRaisesRegex(AdapterError,'incomplete provenance'):contextualize(bad)


if __name__=='__main__':unittest.main()
