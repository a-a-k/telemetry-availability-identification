import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetry_availability.pmx_pmf_bridge import (
    VARIANTS, integer_loop_pmfs, root_loop_id, qualify, prepare, summarize,
)
from telemetry_availability.pmx_composition_control import _hash

XML = '''<repository:Repository xmlns:repository="urn:repository" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<serviceEffectSpecifications__BasicComponent describedService__SEFF="child">
  <steps_Behaviour xsi:type="seff:LoopAction" id="child-loop"><iterationCount_LoopAction specification="0"/></steps_Behaviour>
</serviceEffectSpecifications__BasicComponent>
<serviceEffectSpecifications__BasicComponent describedService__SEFF="root">
  <steps_Behaviour xsi:type="seff:InternalAction" id="work"><resourceDemand_Action specification="1"/></steps_Behaviour>
  <steps_Behaviour xsi:type="seff:LoopAction" id="root-loop"><iterationCount_LoopAction specification="1"/></steps_Behaviour>
</serviceEffectSpecifications__BasicComponent>
</repository:Repository>'''
USAGE = '<usage><operationSignature__EntryLevelSystemCall href="extracted.repository#root"/></usage>'


class PmxPmfBridgeTests(unittest.TestCase):
    def test_integer_law_preserves_all_other_xml_bytes(self):
        rewritten, changes = integer_loop_pmfs(XML)
        expected = XML.replace('iterationCount_LoopAction specification="0"',
                               'iterationCount_LoopAction specification="IntPMF[(0;1.0)]"')
        expected = expected.replace('iterationCount_LoopAction specification="1"',
                                    'iterationCount_LoopAction specification="IntPMF[(1;1.0)]"')
        self.assertEqual(rewritten, expected)
        self.assertTrue(all(change['equivalent_integer_law'] for change in changes))
        self.assertIn('resourceDemand_Action specification="1"', rewritten)

    def test_rejects_noninteger_and_unsupported_loop_expressions(self):
        for expression in ('-1', '1.0', 'count.VALUE', '1+2', 'IntPMF[(1;1.0)]'):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                integer_loop_pmfs(XML.replace('iterationCount_LoopAction specification="1"',
                                              f'iterationCount_LoopAction specification="{expression}"'))

    def test_random_control_resolves_root_through_usage_entry(self):
        self.assertEqual(root_loop_id(XML, USAGE), 'root-loop')
        rewritten, changes = integer_loop_pmfs(XML, root_loop_id(XML, USAGE))
        self.assertIn('IntPMF[(0;0.5)(2;0.5)]', rewritten)
        self.assertEqual(sum(not change['equivalent_integer_law'] for change in changes), 1)
        with self.assertRaises(ValueError):
            integer_loop_pmfs(XML, 'absent')

    def test_probability_gate_rejects_zero_mass_nonfinite_and_partial_states(self):
        valid = dict(status='solved', success_probability=.72, failure_probability_sum=.28,
                     physical_state_probability=1.0, evaluated_physical_states=1, total_physical_states=1)
        self.assertTrue(qualify(valid, .72)['software_oracle_pass'])
        self.assertFalse(qualify(valid, .8)['software_oracle_pass'])
        for overrides in (dict(success_probability=0, failure_probability_sum=0,
                               physical_state_probability=0, evaluated_physical_states=0),
                          dict(success_probability=float('nan')),
                          dict(success_probability='NaN'), dict(total_physical_states=0),
                          dict(total_physical_states=2), dict(failure_probability_sum=-.1)):
            with self.subTest(overrides=overrides):
                self.assertFalse(qualify({**valid, **overrides}, .72)['valid_probability'])

    def test_live_preparation_is_remote_before_any_input_read(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}), self.assertRaises(ValueError):
            prepare(Path('missing'), Path('missing'), Path('missing'))

    def test_census_requires_every_positive_and_negative_without_duplicate_rescue(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            'GITHUB_ACTIONS': 'true', 'GITHUB_RUN_ID': 'unit-run', 'GITHUB_SHA': 'unit-head',
        }), patch('telemetry_availability.pmx_pmf_bridge.validate', return_value={'probability_tolerance': 1e-12}):
            root = Path(temporary)
            config = root / 'config.json'
            config.write_text('{}')
            contract, solver = root / 'contract', root / 'solver'
            contract.mkdir()
            solver.mkdir()
            models = [dict(model_id=f'{variant}-r{repeat}', variant=variant, expected_success=expected,
                           files={}) for variant, _, expected in VARIANTS for repeat in (1, 2)]
            (contract / 'pmf-bridge-contract.json').write_text(json.dumps({
                'run_id': 'unit-run', 'head_sha': 'unit-head', 'config_sha256': _hash(config), 'models': models}))
            rows = []
            for model in models:
                for repeat in (0, 1):
                    row = dict(model_id=model['model_id'], repetition=repeat, status='error')
                    if model['expected_success'] is not None:
                        row.update(status='solved', success_probability=model['expected_success'],
                                   failure_probability_sum=1-model['expected_success'],
                                   physical_state_probability=1.0, total_physical_states=1,
                                   evaluated_physical_states=1)
                    rows.append(row)
            result_path = solver / 'raw-result.json'
            result_path.write_text(json.dumps({'runs': rows}))
            result = summarize(config, contract, solver, root / 'out')
            self.assertEqual(result['status'], 'pmf_bridge_qualified')
            self.assertEqual(result['positive_oracle_passes'], 16)
            for invalid in (rows + [rows[0]], rows[:-1]):
                result_path.write_text(json.dumps({'runs': invalid}))
                result = summarize(config, contract, solver, root / 'out')
                self.assertEqual(result['status'], 'pmf_bridge_unresolved')
                self.assertEqual(len(result['rows']), 24)
                self.assertFalse(result['matrix_complete'])


if __name__ == '__main__':
    unittest.main()
