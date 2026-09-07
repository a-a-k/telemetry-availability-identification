import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetry_availability.pmx_application_census import AdapterError, prepare, summarize
from telemetry_availability.pmx_observed_operations import file_sha256


class ApplicationCensusTests(unittest.TestCase):
    def test_rejected_acceptance_prevents_historical_input_access(self):
        with patch.dict('os.environ', {'GITHUB_ACTIONS': 'true'}), \
             patch('telemetry_availability.pmx_application_census.validate', return_value={}), \
             patch('telemetry_availability.pmx_application_census.check_gate', side_effect=AdapterError('gate_rejected')), \
             patch('telemetry_availability.pmx_application_census._metadata') as metadata, \
             patch('telemetry_availability.pmx_application_census.read_native') as reader:
            with self.assertRaisesRegex(AdapterError, 'gate_rejected'):
                prepare(*([Path('unused')] * 7))
            metadata.assert_not_called()
            reader.assert_not_called()

    def test_missing_and_unfavorable_samples_remain_in_the_census(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / 'config.json'
            config_path.write_text('{}')
            inputs = root / 'inputs'
            inputs.mkdir()
            sample_config = {'samples': [{'key': key} for key in ('a', 'b', 'c', 'd')]}
            for key, good in [('a', True), ('b', False)]:
                path = inputs / key
                path.mkdir()
                (path / 'application-fidelity.json').write_text(json.dumps({
                    'sample': {'key': key}, 'config_sha256': file_sha256(config_path), 'run_id': '123', 'head_sha': 'commit',
                    'projection_fidelity_passed': good, 'dynamic_invocations': 1, 'status': 'passed' if good else 'mismatch',
                }))
            env = {'GITHUB_ACTIONS': 'true', 'GITHUB_RUN_ID': '123', 'GITHUB_SHA': 'commit'}
            with patch.dict('os.environ', env), patch('telemetry_availability.pmx_application_census.validate', return_value=sample_config):
                result = summarize(config_path, inputs, root / 'out')
                self.assertEqual(result['completed_samples'], 2)
                self.assertEqual(result['missing_samples'], ['c', 'd'])
                self.assertEqual(result['projection_fidelity_passed_samples'], 1)
                self.assertEqual(result['dynamic_invocations'], 2)
                self.assertFalse(result['full_external_request_mapping_established'])
                path = inputs / 'b' / 'application-fidelity.json'
                record = json.loads(path.read_text())
                record['head_sha'] = 'different-commit'
                path.write_text(json.dumps(record))
                with self.assertRaisesRegex(AdapterError, 'provenance_differs'):
                    summarize(config_path, inputs, root / 'bad')

    def test_local_full_census_is_rejected_before_inputs(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(AdapterError, 'remote_only'):
                summarize(Path('missing'), Path('missing'), Path('missing'))


if __name__ == '__main__':
    unittest.main()
