import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from telemetry_availability.pmx_application_comparison import freeze_candidates
from telemetry_availability.pmx_composition_control import _hash, _write


class ApplicationCandidateTests(unittest.TestCase):
    def build(self, root, records):
        config = root / 'config.json'
        _write(config, {})
        contract, solver, inputs = [root / name for name in ('contract', 'solver', 'inputs')]
        sample = {'profile': 'fixture', 'placement': 'colocated'}
        case = {'case_id': 'one', 'sample': sample, 'operation': 'op', 'summary': {'rejected_requests': 0}}
        model = {'model_id': 'one--inclusive', 'files': {}}
        _write(contract / 'solver-contract.json', {'head_sha': 'head', 'config_sha256': _hash(config),
            'models': [model], 'extractions': [{'cases': [{'case_id': 'one'}]}]})
        _write(solver / 'raw-result.json', {'runs': records})
        _write(inputs / 'application-input-contract.json', {'head_sha': 'head', 'config_sha256': _hash(config),
            'samples': [{'cases': [case]}], 'files': {}})
        return config, contract, solver, inputs

    def valid_record(self, repeat):
        return {'model_id': 'one--inclusive', 'repetition': repeat, 'status': 'solved',
            'success_probability': .8, 'failure_probability_sum': .2, 'physical_state_probability': 1,
            'total_physical_states': 1, 'evaluated_physical_states': 1}

    @patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_SHA': 'head', 'GITHUB_RUN_ID': '1'})
    @patch('telemetry_availability.pmx_application_comparison.validate')
    def test_valid_forecast_and_unsupported_variant_are_both_retained(self, _):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.build(root, [self.valid_record(0), self.valid_record(1)])
            freeze_candidates(*args, root / 'out')
            predictions = json.loads((root / 'out/candidate-predictions.json').read_text())
            self.assertEqual([r['prediction'] for r in predictions], [.8, ''])
            self.assertEqual(len(json.loads((root / 'out/coverage-census.json').read_text())), 2)

    @patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_SHA': 'head', 'GITHUB_RUN_ID': '1'})
    @patch('telemetry_availability.pmx_application_comparison.validate')
    def test_zero_mass_is_abstention_not_zero_availability(self, _):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            records = [dict(self.valid_record(i), success_probability=0, failure_probability_sum=0,
                            physical_state_probability=0, evaluated_physical_states=0) for i in (0, 1)]
            args = self.build(root, records)
            freeze_candidates(*args, root / 'out')
            result = json.loads((root / 'out/candidate-predictions.json').read_text())
            self.assertTrue(all(r['prediction'] == '' for r in result))

    @patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_SHA': 'head', 'GITHUB_RUN_ID': '1'})
    @patch('telemetry_availability.pmx_application_comparison.validate')
    def test_duplicate_solver_record_is_rejected(self, _):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.build(root, [self.valid_record(0), self.valid_record(0)])
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                freeze_candidates(*args, root / 'out')

    @patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'GITHUB_SHA': 'head', 'GITHUB_RUN_ID': '1'})
    @patch('telemetry_availability.pmx_application_comparison.validate')
    def test_mixed_input_provenance_rejected(self, _):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.build(root, [self.valid_record(0), self.valid_record(1)])
            contract = root / 'inputs/application-input-contract.json'
            data = json.loads(contract.read_text())
            data['head_sha'] = 'different'
            _write(contract, data)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                freeze_candidates(*args, root / 'out')
