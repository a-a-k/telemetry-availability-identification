"""Bounded truth-table oracle; the measurement workflow separately tests CUDD."""
from copy import deepcopy
from itertools import product
import unittest

from telemetry_availability.graph_execution_model_v1 import identify, predicates, solve
from telemetry_availability.graph_execution_bdd_v1 import CompiledModel, POLICIES, verify_result


class Truth:
    def __init__(self, manager, bits): self.manager, self.bits = manager, bits
    def __and__(self, other): return Truth(self.manager, self.bits & other.bits)
    def __or__(self, other): return Truth(self.manager, self.bits | other.bits)
    def __invert__(self): return Truth(self.manager, self.bits ^ self.manager.mask)
    def __eq__(self, other): return isinstance(other, Truth) and self.bits == other.bits


class TinyBDD:
    def __init__(self, **kwargs): pass
    def configure(self, **kwargs): pass
    def reorder(self): pass
    def declare(self, *names):
        if len(names) > 10: raise ValueError('bounded test only')
        self.names = names
        self.states = [dict(zip(names, values)) for values in product((False, True), repeat=len(names))]
        self.mask = (1 << len(self.states))-1
        self.true, self.false = Truth(self, self.mask), Truth(self, 0)
    def var(self, name): return Truth(self, sum(1 << i for i, row in enumerate(self.states) if row[name]))
    def cube(self, known):
        return Truth(self, sum(1 << i for i, row in enumerate(self.states) if all(row[x] == v for x, v in known.items())))
    def pick(self, root, care_vars):
        return next(row for i, row in enumerate(self.states) if root.bits & (1 << i))


def tiny_model():
    graph = dict(services=['a', 'b', 'c'], edges=[
        dict(id='ab', source='a', target='b', type='sync', factors=['shared']),
        dict(id='bc', source='b', target='c', type='sync', factors=[]),
        dict(id='ca', source='c', target='a', type='sync', factors=[]),
        dict(id='ac', source='a', target='c', type='async', factors=[])])
    replicas = dict(a=[['shared']], b=[['healthy'], []], c=[[]])
    controls = [dict(service='b', selected_signals=['d1', 'd2'])]
    bindings = [dict(edge_id='ab', signal='finished')]
    observations = [dict(shared=True, healthy=False, d1=True, d2=False, timely=True,
                         entry_completed=None, finished=None),
                    dict(shared=None, healthy=None, d1=None, d2=None, timely=None,
                         entry_completed=True, finished=None),
                    dict(shared=True, healthy=True, d1=True, d2=False, timely=True,
                         entry_completed=True, finished=True)]
    return identify(graph, replicas, dict(id='op', entry='a', required=['b', 'c'],
                    semantics='immediate_sync_all_required'), observations, controls, bindings, {})


class BDDTests(unittest.TestCase):
    def test_every_complete_state_and_policy(self):
        m = tiny_model()
        for policy in POLICIES:
            compiled = CompiledModel(m, policy, TinyBDD)
            for row in compiled.bdd.states:
                cube = compiled.bdd.cube(row)
                actual = {name: int(root & cube != compiled.bdd.false) for name, root in compiled.roots.items()}
                self.assertEqual(actual, predicates(m, row))

    def test_joint_bounds_contrasts_and_witnesses(self):
        m = tiny_model()
        reference = solve(m)
        for policy in POLICIES:
            result = CompiledModel(m, policy, TinyBDD).solve()
            checks = verify_result(m, result, reference)
            self.assertGreater(checks['witnesses_verified'], 0)
            for a, b in zip(result['category_certificates'], reference['category_certificates']):
                self.assertEqual({k: (v['minimum'], v['maximum']) for k, v in a['extrema'].items()},
                                 {k: (v['minimum'], v['maximum']) for k, v in b['extrema'].items()})

    def test_missing_required_edge_is_false(self):
        m = tiny_model(); m['required_edge_completions'][0]['edge_id'] = 'absent'
        result = CompiledModel(m, bdd_factory=TinyBDD).solve()
        verify_result(m, result, solve(m))
        self.assertEqual(result['estimates']['execution']['upper_exact'], '0')

    def test_tampered_witness_rejected(self):
        m = tiny_model(); result = CompiledModel(m, bdd_factory=TinyBDD).solve()
        for cert in result['category_certificates']:
            for ex in cert['extrema'].values():
                if ex['lower_witness']:
                    broken = deepcopy(result)
                    target = broken['category_certificates'][result['category_certificates'].index(cert)]
                    key = next(k for k, v in cert['extrema'].items() if v is ex)
                    target['extrema'][key]['lower_witness'] = ex['upper_witness']
                    with self.assertRaises(ValueError): verify_result(m, broken, solve(m))
                    return
        self.fail('test requires ambiguous witness')

    def test_gap_is_joint_functional(self):
        m = tiny_model()
        m['observation_categories'] = [dict(values=[None if x == 'shared' else True for x in m['signal_ids']], count=1)]
        m['sample_count'] = 1
        result = CompiledModel(m, bdd_factory=TinyBDD).solve()
        self.assertEqual(result['estimates']['execution']['lower_exact'], '0')
        self.assertEqual(result['estimates']['execution']['upper_exact'], '1')
        self.assertEqual(result['estimates']['without_completion_minus_execution']['upper_exact'], '0')
        verify_result(m, result, solve(m))


if __name__ == '__main__': unittest.main()
