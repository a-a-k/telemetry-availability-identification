from copy import deepcopy
from itertools import product
import unittest
from unittest.mock import patch

from telemetry_availability import completion_target_v1 as c
from telemetry_availability.completion_target_analysis_v1 import order_cells, analyze
from test_graph_execution_model_v1 import make, row


class CompletionTargetTests(unittest.TestCase):
    def test_all_cartesian_masks_match_independent_truth_table(self):
        model = make([row()]); ids = model['signal_ids']; joint = c.JointBounds(model)
        states = [dict(zip(ids, bits)) for bits in product((False, True), repeat=len(ids))]
        truth = [(s, c.predicates(model, s)['execution'], s['timely'] and s['entry_completed'] and s['call_completed']) for s in states]
        for values in product((None, False, True), repeat=len(ids)):
            obs = dict(zip(ids, values)); result = joint(obs)
            feasible = [(int(e), int(r), int(r)-int(e)) for s, e, r in truth
                        if all(v is None or v == s[k] for k, v in obs.items())]
            for j, name in enumerate(('E', 'R', 'R_minus_E')):
                self.assertEqual(result[name], (min(v[j] for v in feasible), max(v[j] for v in feasible)))
            m = c.full_with_rows(model, [dict(observation=obs)])
            self.assertEqual(c.query_full_r(m), c.query_reduced(c.project_full(m)))
        self.assertTrue(joint.verify())

    def test_confirmed_completion_with_unknown_controls_and_equal_marginals(self):
        joint = c.JointBounds(make([row()]))
        observed = row(a=None, b=None, da=None, db=None)
        self.assertEqual(joint(observed)['E'], (0, 1)); self.assertEqual(joint(observed)['R'], (1, 1))
        observed['call_completed'] = None
        result = joint(observed)
        self.assertEqual(result['E'], result['R']); self.assertEqual(result['R_minus_E'], (0, 1))

    def test_known_false_is_masked_before_conjunction(self):
        records = [dict(request_id='one', observation={'timely': True, 'x': False, 'y': None})]
        before = c.reduced_from_rows(records, ['x', 'y'], 'toy')
        after = c.reduced_from_rows(c.mask_rows(records, {'one': {'x'}}), ['x', 'y'], 'toy')
        self.assertEqual(c.query_reduced(before)['upper_exact'], '0')
        self.assertEqual(c.query_reduced(after)['upper_exact'], '1')

    def test_reduced_law_keeps_dependence_and_discards_K_information(self):
        a = make([row(timely=False), row(entry_completed=False)])
        b = make([row(), row(timely=False, entry_completed=False)])
        self.assertEqual(c.query_full_r(a)['upper_exact'], '0')
        self.assertEqual(c.query_full_r(b)['upper_exact'], '1/2')
        good = make([row()]); bad = make([row(a=False, b=False)])
        self.assertEqual(c.project_full(good), c.project_full(bad))
        self.assertNotEqual(c.JointBounds(good)(row())['E'], c.JointBounds(bad)(row(a=False, b=False))['E'])

    def test_direct_support_does_not_require_full_graph_or_outcomes(self):
        data = {'requests.json': [{'request_id': 'one', 'trace_id': 'trace', 'operation': 'op'}],
                'native.json': {'spans': {}}, 'declarations.json': {}}
        spec = dict(expected_attempts=1, entry='entry', allowed_native_services=['entry', 'missing'],
                    required_native_services=['missing'], required_native_pairs=[['entry', 'missing']])
        evidence = dict(root_status=None, timely=True, calls={}, db_records={}, nodes={})
        with patch.object(c.binding, 'request_evidence', return_value=evidence), patch.object(
                c.binding, 'logical_completion', return_value=(None, 'missing')), patch.object(
                c.binding, 'fit_operation', side_effect=AssertionError('full construction forbidden')), patch.object(
                c.binding, 'identify', side_effect=AssertionError('full identify forbidden')):
            model, records = c.direct_identify(data, 'op', spec, {'application': 'test'})
            changed = deepcopy(data); changed['requests.json'][0]['semantic_success'] = False
            model2, _ = c.direct_identify(changed, 'op', spec, {'application': 'test'})
        self.assertEqual(model, model2)
        self.assertEqual(c.query_reduced(model)['status'], 'interval')
        self.assertFalse(any(k.startswith(('admitted_', 'demand_')) for k in records[0]['observation']))

    def test_mask_plan_does_not_consult_external_outcome(self):
        records = [dict(request_id=str(i), observation={'timely': True, 'entry_completed': v}, outcome=y)
                   for i, (v, y) in enumerate([(False, True), (True, False)])]
        changed = [dict(r, outcome=not r['outcome']) for r in records]
        for mechanism in ('uniform_coordinates', 'native_failure_associated_coordinates', 'whole_native_attempt'):
            self.assertEqual(order_cells(records, ['entry_completed', 'timely'], mechanism, 1, ['entry_completed']),
                             order_cells(changed, ['entry_completed', 'timely'], mechanism, 1, ['entry_completed']))

    def test_all_mask_settings_preserve_direct_route_and_restore_unknowns(self):
        observed = [row(a=None, b=None, da=None, db=None), row(entry_completed=None)]
        model = make(observed)
        full = [dict(request_id=str(i), observation=r) for i, r in enumerate(observed)]
        names = model['completion_signals']
        direct = [dict(request_id=r['request_id'], observation={k:r['observation'][k] for k in names+['timely']}) for r in full]
        config = dict(levels=[0,.1,.25,.5,.75,1], seed=771622,
                      mechanisms=['uniform_coordinates','native_failure_associated_coordinates','whole_native_attempt'])
        result = analyze(model, full, direct, names, 'toy', {'0':True,'1':False}, config)
        self.assertEqual(len(result['settings']),90)
        self.assertTrue(all(r['same_R_routes_qualified'] for r in result['settings']))
        self.assertEqual(result['baseline']['R_point_attempts'],1)
        self.assertEqual(result['baseline']['event_difference_undecided'],1)
        self.assertTrue(result['witnesses'])


if __name__ == '__main__': unittest.main()
