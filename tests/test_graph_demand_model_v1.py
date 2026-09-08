from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from telemetry_availability.graph_demand_model_v1 import identify, predicates, solve


def model(rows):
    graph = dict(services=['entry', 'catalog', 'db'], edges=[
        dict(source='entry', target='catalog', type='sync', factors=[]),
        dict(source='catalog', target='db', type='sync', factors=[])])
    return identify(graph, dict(entry=[[]], catalog=[['a'], ['b']], db=[[]]),
        dict(id='artificial', entry='entry', required=['catalog', 'db'], semantics='immediate_sync_all_required'),
        ['a', 'b', 'da', 'db', 't'], rows,
        [dict(service='catalog', selected_signals=['da', 'db'])], 't',
        dict(scope='artificial controls; static capabilities, no rescued failed calls'))


class GraphDemandTests(unittest.TestCase):
    def test_routing_repair_and_deadline_are_distinct_predicates(self):
        m = model([dict(a=False, b=True, da=True, db=True, t=True)])
        p = solve(m)['estimates']
        self.assertEqual(p['reachability']['prediction'], 1)
        self.assertEqual(p['selected_replicas']['prediction'], 0)
        self.assertEqual(p['reachability_minus_execution']['lower_exact'], '1')
        state = dict(a=False, b=True, da=False, db=True, t=True)
        self.assertTrue(predicates(m, state)['selected_replicas_and_deadline'])
        state['t'] = False
        self.assertTrue(predicates(m, state)['selected_replicas'])
        self.assertFalse(predicates(m, state)['selected_replicas_and_deadline'])

    def test_same_per_call_marginals_do_not_identify_joint_demand_success(self):
        # Two required calls: AA/BB and AB/BA have identical per-slot 1/2 marginals.
        # With a down and b up, only BB succeeds. No independence assumption is used.
        persistent = model([dict(a=False, b=True, da=True, db=False, t=True),
                            dict(a=False, b=True, da=False, db=True, t=True)])
        alternating = model([dict(a=False, b=True, da=True, db=True, t=True)] * 2)
        self.assertEqual(solve(persistent)['estimates']['selected_replicas_and_deadline']['lower_exact'], '1/2')
        self.assertEqual(solve(alternating)['estimates']['selected_replicas_and_deadline']['lower_exact'], '0')

    def test_masked_demands_and_deadline_produce_attainable_ambiguity(self):
        m = model([dict(a=False, b=True, da=None, db=True, t=True)] * 3 +
                  [dict(a=False, b=False, da=None, db=None, t=None)])
        report = solve(m)
        result = report['estimates']['selected_replicas_and_deadline']
        self.assertIsNone(result['prediction'])
        self.assertEqual((result['lower_exact'], result['upper_exact']), ('0', '3/4'))
        cell = next(c for c in report['category_certificates'] if c['count'] == 3)
        witness = cell['extrema']['selected_replicas_and_deadline']
        for key, expected in [('lower_witness', False), ('upper_witness', True)]:
            self.assertEqual(predicates(m, dict(zip(m['signal_ids'], witness[key])))['selected_replicas_and_deadline'], expected)

    def test_capability_and_routing_dependence_cannot_be_split_into_marginals(self):
        adaptive = model([dict(a=False, b=True, da=False, db=True, t=True),
                          dict(a=True, b=False, da=True, db=False, t=True)])
        adverse = model([dict(a=False, b=True, da=True, db=False, t=True),
                         dict(a=True, b=False, da=False, db=True, t=True)])
        self.assertEqual(solve(adaptive)['estimates']['selected_replicas_and_deadline']['prediction'], 1)
        self.assertEqual(solve(adverse)['estimates']['selected_replicas_and_deadline']['prediction'], 0)
        for index in range(4):
            self.assertEqual(sum(r['values'][index] * r['count'] for r in adaptive['observation_categories']),
                             sum(r['values'][index] * r['count'] for r in adverse['observation_categories']))

    def test_target_can_be_identified_despite_unknown_unused_replica_capability(self):
        m = model([dict(a=None, b=True, da=False, db=True, t=True)])
        report = solve(m)
        self.assertEqual(report['estimates']['selected_replicas_and_deadline']['prediction'], 1)
        self.assertFalse(report['physical_cause_parameters_identified'])

    def test_paired_gap_bounds_use_one_joint_completion(self):
        m = model([dict(a=None, b=None, da=True, db=True, t=True)])
        result = solve(m)['estimates']
        self.assertEqual((result['reachability_minus_execution']['lower_exact'],
                          result['reachability_minus_execution']['upper_exact']), ('0', '1'))
        self.assertEqual(result['reachability']['lower'], 0)
        self.assertEqual(result['selected_replicas_and_deadline']['upper'], 1)
        # Subtracting separate marginal ranges would wrongly permit a negative gap.
        self.assertGreaterEqual(result['reachability_minus_execution']['lower'], 0)

    def test_graph_mutation_and_representation_equivalence(self):
        m = model([dict(a=False, b=True, da=False, db=True, t=True)])
        original = solve(m)
        permuted = deepcopy(m); permuted['graph']['edges'].reverse()
        self.assertEqual(solve(permuted), original)
        removed = deepcopy(m); removed['graph']['edges'] = removed['graph']['edges'][:1]
        self.assertEqual(solve(removed)['estimates']['selected_replicas_and_deadline']['prediction'], 0)

    def test_saved_model_replays_in_separate_process(self):
        m = model([dict(a=False, b=True, da=False, db=True, t=True)])
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'model.json'; source.write_text(json.dumps(m))
            script = ('import json,sys;from telemetry_availability.graph_demand_model_v1 import solve;'
                      'print(json.dumps(solve(json.load(open(sys.argv[1])))))')
            actual = json.loads(subprocess.check_output([sys.executable, '-c', script, str(source)]))
        self.assertEqual(actual, solve(m))

    def test_aliased_signals_and_unqualified_semantics_are_rejected(self):
        m = model([dict(a=False, b=True, da=False, db=True, t=True)])
        bad = deepcopy(m); bad['timely_signal'] = 'b'
        with self.assertRaises(ValueError):
            solve(bad)
        bad = deepcopy(m); bad['execution_class'] = 'arbitrary_retries'
        with self.assertRaises(ValueError):
            solve(bad)
