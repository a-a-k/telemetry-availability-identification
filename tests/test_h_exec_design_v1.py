from fractions import Fraction
import unittest

from telemetry_availability.h_exec_design_v1 import assignments, exact_paired_test, routing_control, instrument_haproxy, ARMS


class ProspectiveExecutionDesignTests(unittest.TestCase):
    def test_block_randomization_contains_every_arm_once_and_is_reproducible(self):
        plan = assignments(8, 2026090811)
        self.assertEqual(plan, assignments(8, 2026090811))
        self.assertEqual(len({(r['block'],r['slot']) for r in plan}), 32)
        for block in range(8):
            self.assertEqual({r['arm'] for r in plan if r['block']==block}, set(ARMS))

    def test_exact_randomization_known_extremes_and_balanced_null(self):
        result = exact_paired_test([Fraction(1,2)]*8)
        self.assertEqual(result['assignments'], 256)
        self.assertEqual(result['exceed_or_tie'], 2)
        self.assertEqual(result['two_sided_p'], 1/128)
        self.assertEqual(exact_paired_test([0]*8)['two_sided_p'], 1)
        self.assertEqual(exact_paired_test([1,-1]*4)['two_sided_p'], 1)

    def test_exact_semantic_bridge_and_repeated_call_counterexample(self):
        result = routing_control()
        self.assertEqual(len(result['controls']), 19)
        self.assertEqual(result['controls'][-1]['sequence_success'], '1/8')
        self.assertEqual(result['controls'][-1]['ideal'], '1')

    def test_proxy_instrumentation_preserves_policy_and_rejects_reapplication(self):
        source = 'global\n  log stdout format raw local0\ndefaults\n  log global\nfrontend study_frontend\n  option httplog\n  default_backend study_replicas\nbackend study_replicas\n  balance roundrobin\n'
        actual = instrument_haproxy(source)
        self.assertIn('balance roundrobin', actual)
        self.assertIn('capture request header traceparent len 128', actual)
        self.assertIn('server=%s', actual)
        self.assertIn('defaults\n  log global\n', actual)
        self.assertEqual(actual.count('stats socket'), 1)
        with self.assertRaises(ValueError):
            instrument_haproxy(actual)
