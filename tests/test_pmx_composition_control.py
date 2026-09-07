import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from telemetry_availability.pmx_composition_control import (
    _hash, contain_failure_types, failure_references, prepare, summarize,
)

XML = '''<repository:Repository xmlns:repository="urn:repository" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <components__Repository id="component"><serviceEffectSpecifications__BasicComponent id="seff">
    <steps_Behaviour id="start"/>
    <steps_Behaviour id="action"><internalFailureOccurrenceDescriptions__InternalAction failureProbability="0.2" softwareInducedFailureType__InternalFailureOccurrenceDescription="missing"/></steps_Behaviour>
  </serviceEffectSpecifications__BasicComponent></components__Repository>
</repository:Repository>'''


class PmxCompositionControlTests(unittest.TestCase):
    def test_containment_completes_the_actual_target_type_without_changing_old_nodes(self):
        self.assertFalse(failure_references(XML)[0]['resolved'])
        fixed = contain_failure_types(XML)
        row = failure_references(fixed)[0]
        self.assertTrue(row['resolved'])
        self.assertEqual(row['probability'], .2)
        self.assertEqual(row['occurrence_path'], '//@components__Repository.0/@serviceEffectSpecifications__BasicComponent.0/@steps_Behaviour.1/@internalFailureOccurrenceDescriptions__InternalAction.0')
        before, after = ET.fromstring(XML), ET.fromstring(fixed)
        new_type = after[-1]
        self.assertEqual(new_type.attrib['id'], 'missing')
        self.assertEqual(new_type.attrib['internalFailureOccurrenceDescriptions__SoftwareInducedFailureType'], row['occurrence_path'])
        after.remove(new_type)
        for tree in (before, after):
            for node in tree.iter():
                if node.text is not None and not node.text.strip():
                    node.text = None
                if node.tail is not None and not node.tail.strip():
                    node.tail = None
        self.assertEqual(ET.tostring(before), ET.tostring(after))
        self.assertEqual(contain_failure_types(fixed), fixed)

    def test_rejects_existing_wrong_type_and_duplicate_identifiers(self):
        with self.assertRaises(ValueError):
            failure_references(XML.replace('="missing"', '="action"'))
        with self.assertRaises(ValueError):
            failure_references(XML.replace('id="start"', 'id="action"'))

    def test_full_preparation_rejects_local_execution_before_input_access(self):
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}):
            with self.assertRaises(ValueError):
                prepare(Path('missing'), Path('missing'), Path('missing'))

    def test_census_keeps_missing_and_unphysical_results(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {
            'GITHUB_ACTIONS': 'true', 'GITHUB_RUN_ID': 'unit-run', 'GITHUB_SHA': 'unit-head',
        }):
            root = Path(temporary)
            config = root / 'config.json'
            config.write_text(json.dumps({'repository_locks': [], 'expected_models': 8, 'solver_passes': 2}))
            contract = root / 'contract'
            contract.mkdir()
            models = [{'model_id': str(i), 'variant': 'types', 'files': {},
                       'expected_software_success_given_resources_up': .72} for i in range(8)]
            (contract / 'composition-contract.json').write_text(json.dumps({
                'run_id': 'unit-run', 'head_sha': 'unit-head', 'config_sha256': _hash(config), 'models': models,
            }))
            solver = root / 'solver'
            solver.mkdir()
            valid = {'model_id': '0', 'repetition': 0, 'status': 'solved', 'success_probability': .72,
                     'failure_probability_sum': .28, 'physical_state_probability': 1,
                     'evaluated_physical_states': 1, 'total_physical_states': 1}
            invalid = {**valid, 'model_id': '1', 'success_probability': 1.2, 'failure_probability_sum': -.2}
            (solver / 'raw-result.json').write_text(json.dumps({'runs': [valid, invalid]}))
            result = summarize(config, contract, solver, root / 'out')
            self.assertEqual(len(result['rows']), 16)
            self.assertEqual(result['retained_records'], 2)
            self.assertEqual(result['typed_software_oracle_passes'], 1)
            self.assertEqual(sum(r['status'] == 'missing' for r in result['rows']), 14)


if __name__ == '__main__':
    unittest.main()
