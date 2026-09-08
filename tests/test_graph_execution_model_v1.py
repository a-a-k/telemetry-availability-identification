from copy import deepcopy
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from telemetry_availability.graph_execution_model_v1 import identify, predicates, solve


def make(rows):
    return identify(dict(services=['entry', 'service', 'optional'], edges=[
        dict(id='call', source='entry', target='service', type='sync', factors=[]),
        dict(id='optional', source='entry', target='optional', type='async', factors=[])]),
        dict(entry=[[]], service=[['a'], ['b']], optional=[[]]),
        dict(id='toy', entry='entry', required=['service'], semantics='immediate_sync_all_required'),
        rows, [dict(service='service', selected_signals=['da', 'db'])],
        [dict(edge_id='call', signal='call_completed')], dict(scope='bounded artificial'))


def row(**changes):
    return dict(dict(a=True, b=True, da=True, db=False, timely=True,
                     entry_completed=True, call_completed=True), **changes)


class ExecutionCoreTests(unittest.TestCase):
    def test_every_mask_fiber_matches_independent_full_enumeration(self):
        prototype = make([row()]); ids = prototype['signal_ids']
        table = [(bits, predicates(prototype, dict(zip(ids, bits)))) for bits in product((False, True), repeat=7)]
        # All 3^7 masks/values, compared with every compatible one of 2^7 states.
        for values in product((None, False, True), repeat=7):
            m = deepcopy(prototype); m['observation_categories'] = [dict(values=list(values), count=1)]
            result = solve(m)['estimates']
            compatible = [v for bits, v in table if all(x is None or x == b for x, b in zip(values, bits))]
            for name, estimate in result.items():
                self.assertEqual(estimate['lower'], min(int(v[name]) for v in compatible))
                self.assertEqual(estimate['upper'], max(int(v[name]) for v in compatible))

    def test_known_completion_failure_resolves_unknown_route(self):
        m = make([row(a=None, b=None, da=None, db=None, call_completed=False)])
        result = solve(m)['estimates']
        self.assertIsNone(result['reachability']['prediction'])
        self.assertEqual(result['execution']['prediction'], 0)

    def test_live_transport_does_not_imply_call_success_or_timeliness(self):
        m = make([row(call_completed=False), row(timely=False), row()])
        r = solve(m)['estimates']
        self.assertEqual(r['reachability']['lower_exact'], '1')
        self.assertEqual(r['without_deadline']['lower_exact'], '2/3')
        self.assertEqual(r['execution']['lower_exact'], '1/3')

    def test_joint_route_dependence_and_repeated_calls(self):
        good = make([row(a=False, da=False, db=True), row(b=False, da=True, db=False)])
        bad = make([row(a=False, da=True, db=True), row(b=False, da=True, db=True)])
        self.assertEqual(solve(good)['estimates']['execution']['prediction'], 1)
        self.assertEqual(solve(bad)['estimates']['execution']['prediction'], 0)

    def test_structure_optional_async_and_equivalent_order(self):
        m = make([row()]); r = solve(m)
        equivalent = deepcopy(m); equivalent['graph']['edges'].reverse()
        self.assertEqual(solve(equivalent), r)
        optional = deepcopy(m); optional['graph']['edges'] = optional['graph']['edges'][:1]
        self.assertEqual(solve(optional)['estimates'], r['estimates'])
        removed = deepcopy(m); removed['graph']['edges'] = removed['graph']['edges'][1:]
        self.assertEqual(solve(removed)['estimates']['execution']['prediction'], 0)

    def test_ambiguity_witnesses_and_no_physical_identification(self):
        m = make([row(call_completed=None)] * 3 + [row(timely=False)])
        r = solve(m); e = r['estimates']['execution']
        self.assertEqual((e['lower_exact'], e['upper_exact']), ('0', '3/4'))
        self.assertIsNone(e['prediction'])
        c = next(x for x in r['category_certificates'] if x['count'] == 3)['extrema']['execution']
        for key, expected in [('lower_witness', False), ('upper_witness', True)]:
            self.assertEqual(predicates(m, dict(zip(m['signal_ids'], c[key])))['execution'], expected)
        self.assertFalse(r['physical_capabilities_identified'])

    def test_fresh_process_replays_only_saved_model(self):
        m = make([row(), row(a=False), row(call_completed=None)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.json'; path.write_text(json.dumps(m))
            code = ('import json,sys;from telemetry_availability.graph_execution_model_v1 import solve;'
                    'print(json.dumps(solve(json.load(open(sys.argv[1])))))')
            actual = json.loads(subprocess.check_output([sys.executable, '-c', code, str(path)]))
        self.assertEqual(actual, solve(m))

    def test_invalid_observations_aliases_and_semantics_rejected(self):
        with self.assertRaises(ValueError):
            make([row(a=1)])
        for key, value in [('timely_signal', 'a'), ('execution_class', 'arbitrary_rescued_retries')]:
            bad = make([row()]); bad[key] = value
            with self.assertRaises(ValueError):
                solve(bad)
