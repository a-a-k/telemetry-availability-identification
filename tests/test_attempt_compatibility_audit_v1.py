import unittest
from telemetry_availability.attempt_compatibility_audit_v1 import compatibility, summarize_attempts


class AttemptCompatibilityTests(unittest.TestCase):
    def test_both_directions_and_partial_ambiguity(self):
        self.assertEqual(compatibility(0, True, 0), 'success_excluded')
        self.assertEqual(compatibility(1, False, 1), 'failure_excluded')
        for y in (False, True):
            self.assertEqual(compatibility(0, y, 1), 'compatible')

    def test_opposite_errors_cancel_in_aggregate(self):
        rows = [dict(lower=0, upper=0, outcome=True, fully_observed=False,
                     compatibility='success_excluded'),
                dict(lower=1, upper=1, outcome=False, fully_observed=True,
                     compatibility='failure_excluded')]
        result = summarize_attempts(rows)
        self.assertTrue(result['aggregate_contains_b0'])
        self.assertTrue(result['incompatible_despite_aggregate_containment'])
        self.assertEqual(result['incompatible_attempts'], 2)
        self.assertEqual(result['fully_observed_mismatches'], 1)
        self.assertEqual(result['lower_exact'], result['b0_exact'])

    def test_invalid_bounds_rejected(self):
        with self.assertRaises(ValueError): compatibility(1, True, 0)
        with self.assertRaises(ValueError): compatibility(0, 1, 1)


if __name__ == '__main__': unittest.main()
