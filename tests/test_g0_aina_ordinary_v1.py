from copy import deepcopy
from fractions import Fraction
import importlib.util
from itertools import combinations
from pathlib import Path
import unittest
from unittest.mock import patch

from test_graph_execution_model_v1 import make, row
from telemetry_availability.g0_aina_ordinary_v1 import identify_from_observed_graph, solve, source_k
from telemetry_availability.graph_execution_model_v1 import solve as solve_joint


def predecessor():
    path = Path(__file__).resolve().parents[1]/'docs/evidence/aina-execution-source-a8bc5a2/scripts/resilience.py'
    spec = importlib.util.spec_from_file_location('frozen_aina_source_oracle', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class G0AdaptationTests(unittest.TestCase):
    def test_exact_uniform_subsets_match_actual_frozen_source(self):
        src = predecessor()
        graph = dict(services=['entry', 'service', 'optional'], edges=[[0, 1], [0, 2]], async_edges=[[0, 2]])
        src.prepare_graph(graph)
        operation = dict(entry='entry', rule='all_of', targets=['service'], exclude_async=False)
        model = identify_from_observed_graph(make([row()]))
        for failed, slots in [(0, 20), (1, 20), (5, 20), (10, 20), (15, 20), (20, 20)]:
            model['eligibility_observation_counts'] = dict(known_failed=failed, masked=0, slots=slots, attempts=10)
            result = solve(model); p = Fraction(failed, slots); k = source_k(2, p)
            expected = []
            for subset in combinations(range(2), k):
                def sample(pool, size):
                    self.assertEqual(size, k)
                    return [pool[i] for i in subset]
                with patch.object(src.random, 'sample', sample):
                    alive = src.draw_alive_fixed([1], [1, 2, 1], [0, 1, 1, 2], float(p))
                failed_services = {s for s, okay in zip(graph['services'], alive) if not okay}
                expected.append(src.endpoint_success(graph, failed_services, operation, 'all-block'))
            self.assertEqual(result['lower_exact'], str(Fraction(sum(expected), len(expected))))

    def test_same_mean_failure_fraction_does_not_identify_joint_graph_probability(self):
        common = make([row(a=False, b=False)] * 3 + [row()] * 7)
        separate = make([row(a=False)] * 3 + [row(b=False, da=True, db=False)] * 3 + [row()] * 4)
        first = solve(identify_from_observed_graph(common)); second = solve(identify_from_observed_graph(separate))
        self.assertEqual(first['p_lower_exact'], '3/10')
        self.assertEqual(first, second)
        self.assertEqual(first['prediction'], 1)
        self.assertEqual(solve_joint(common)['estimates']['reachability']['lower_exact'], '7/10')
        self.assertEqual(solve_joint(separate)['estimates']['reachability']['lower_exact'], '1')

    def test_masks_retain_entire_denominator_and_can_change_discrete_count(self):
        model = identify_from_observed_graph(make([row(a=False, b=None)]))
        result = solve(model)
        self.assertEqual((result['p_lower_exact'], result['p_upper_exact']), ('1/2', '1'))
        self.assertEqual(result['possible_fixed_counts'], [1, 2])
        self.assertEqual((result['lower_exact'], result['upper_exact']), ('0', '1'))
        self.assertIsNone(result['prediction'])

    def test_target_can_be_singleton_while_mean_fraction_is_ambiguous(self):
        model = identify_from_observed_graph(make([row(a=True, b=None)]))
        result = solve(model)
        self.assertEqual(result['possible_fixed_counts'], [0, 1])
        self.assertFalse(result['point_p_identified'])
        self.assertEqual(result['prediction'], 1)

    def test_completion_demand_and_deadline_do_not_enter_predecessor_parameters(self):
        a = make([row(a=False)])
        b = make([row(a=False, da=False, db=True, timely=False, entry_completed=False, call_completed=False)])
        self.assertEqual(identify_from_observed_graph(a), identify_from_observed_graph(b))

    def test_rounding_empty_pool_and_structure_are_explicit(self):
        self.assertEqual([source_k(2, p) for p in (0, Fraction(1, 100), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4), 1)],
                         [0, 1, 1, 1, 2, 2])
        model = identify_from_observed_graph(make([row()]))
        model['graph']['edges'] = [e for e in model['graph']['edges'] if e['target'] != 'service']
        self.assertEqual(solve(model)['prediction'], 0)
        empty = make([row()]); empty['replicas']['service'] = [[]]
        result = solve(identify_from_observed_graph(empty))
        self.assertEqual(result['eligible_replica_count'], 0)
        self.assertEqual(result['prediction'], 1)
        self.assertIsNone(result['p_lower_exact'])

    def test_unsupported_compound_replica_gate_is_rejected(self):
        m = make([row()]); m['replicas']['service'] = [['a', 'b']]
        with self.assertRaises(ValueError):
            identify_from_observed_graph(m)
