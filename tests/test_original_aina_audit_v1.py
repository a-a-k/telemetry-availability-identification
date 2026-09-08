"""Small artificial controls only; original application artifacts stay remote."""
import importlib.util
from pathlib import Path
import unittest
from fractions import Fraction

spec = importlib.util.spec_from_file_location('aina_audit', Path('scripts/audit_original_aina_v1.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class OriginalAinaAuditTests(unittest.TestCase):
    def test_fixed_cardinality_replica_count_and_async_counterexample(self):
        original = audit.original_module()
        graph = {'services': ['frontend', 'a', 'b'], 'edges': [[0, 1], [0, 2]],
                 'async_edges': [[0, 2]], 'entrypoints': [0]}
        targets = {
            'a': {'entry': 'frontend', 'rule': 'all_of', 'targets': ['a'], 'exclude_async': True},
            'b': {'entry': 'frontend', 'rule': 'all_of', 'targets': ['b'], 'exclude_async': True}}
        curve = audit.exact_curve(graph, {'a': 2}, original, targets, ['frontend'])
        self.assertEqual(curve['totals'], {0: 1, 1: 3, 2: 3, 3: 1})
        self.assertEqual(audit.probability(curve, 'a', 'all-block', 2/3), Fraction(2, 3))
        self.assertEqual(audit.probability(curve, 'a', 'async', 2/3), Fraction(2, 3))
        self.assertEqual(audit.probability(curve, 'b', 'all-block', 2/3), Fraction(1, 3))
        self.assertEqual(audit.probability(curve, 'b', 'async', 2/3), Fraction(1))
        self.assertEqual(sum(curve['changed']['a'].values()), 0)
        self.assertGreater(sum(curve['changed']['b'].values()), 0)

    def test_historical_skips_remain_in_denominator_and_success_count(self):
        ep = 'POST /api/checkout'
        data = {'R_live': .5, 'per_endpoint': {ep: {'ok': 1, 'total': 2}}, 'detail': {
            'probe_ok': 1, 'probe_total': 2, 'probe_fail': 1, 'probe_detail': [
                {'endpoint': 'http://localhost/api/checkout', 'method': 'POST', 'status': 'skip', 'code': 403},
                {'endpoint': 'http://localhost/api/checkout', 'method': 'GET', 'status': 'fail'}]}}
        total, ok, status, _ = audit.probe_counts(data, [ep])
        self.assertEqual((total, ok, status['skip']), (2, 1, 1))
        data['detail']['probe_ok'] = 0
        with self.assertRaises(AssertionError):
            audit.probe_counts(data, [ep])

    def test_empty_allowlist_fallback_and_pool_limit_are_explicit(self):
        graph = {'services': ['a'], 'edges': [], 'entrypoints': [0]}
        target = {'a': {'entry': 'a', 'rule': 'all_of', 'targets': ['a']}}
        curve = audit.exact_curve(graph, {}, audit.original_module(), target, ['a'])
        self.assertTrue(curve['fallback'])
        self.assertEqual(audit.probability(curve, 'a', 'all-block', .1), 0)
        self.assertEqual(audit.kill_count(1, 0), 0)
        curve = audit.exact_curve(graph, {'a': 17}, audit.original_module(), target, [])
        self.assertFalse(curve['supported'])


if __name__ == '__main__':
    unittest.main()
