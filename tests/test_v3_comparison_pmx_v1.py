from copy import deepcopy
from dataclasses import asdict
import unittest

from telemetry_availability.pmx_request_controls import fixture
from telemetry_availability.pmx_database_client_controls import control as db_control
from telemetry_availability.v3_comparison_pmx_v1 import (
    projection, solver_forecasts, CONTROL_SUCCESS, DATABASE_SUCCESS)


def native(grouped, requests):
    return dict(calibration_only=True, selected_trace_ids=[r['trace_id'] for r in requests],
        spans={key: [asdict(s) for s in spans] for key, spans in grouped.items()})


def solver_fixture():
    models = []; raw = []
    def add(mid, probability):
        models.append(dict(model_id=mid))
        for repetition in (0, 1):
            raw.append(dict(model_id=mid, repetition=repetition, status='solved',
                success_probability=probability, failure_probability_sum=1-probability,
                physical_state_probability=1, total_physical_states=1, evaluated_physical_states=1))
    for case, variants in dict(CONTROL_SUCCESS, **DATABASE_SUCCESS).items():
        for variant, p in variants.items():
            add('controls--'+case+'--'+variant, p)
    add('campaign-toy--operation--inclusive', .8)
    prepared = dict(models=models, head_sha='frozen-head', extractions=[dict(sample_key='campaign-toy',
        prospective_identity={'toy': True}, input_seal_sha256='calibration-seal', stages=[], read_audit={},
        cases=[dict(case_id='campaign-toy--operation', variants=[
            dict(variant='conditional_local', status='unsupported_conditional_propagation_or_positivity'),
            dict(variant='inclusive', status='prepared')])])])
    return prepared, raw


class IndependentPmxTests(unittest.TestCase):
    def test_unmarked_deathstar_boundary_retains_real_calls(self):
        _, _, grouped, requests = fixture('unmarked_service_boundary')
        results, _ = projection(native(grouped, requests), requests, 'deathstarbench_social_network', 'fixture-worker')
        result = results['unmarked_service_boundary']
        self.assertEqual(result['summary']['projected_requests'], 10)
        self.assertEqual(result['summary']['selected_native_spans'], 20)
        self.assertEqual(result['summary']['rejected_requests'], 0)

    def test_petclinic_mysql_projection_is_exact_qualified_mapping(self):
        expected, _, grouped, requests = db_control('shared_database_two_callers')
        results, _ = projection(native(grouped, requests), requests, 'spring_petclinic_microservices', 'fixture-worker')
        self.assertEqual(results['shared_database_two_callers'], expected)

    def test_missing_native_attempts_keep_external_failure_denominator(self):
        _, _, grouped, requests = fixture('absent_trace')
        results, _ = projection(native(grouped, requests), requests, 'opentelemetry_demo', 'fixture-worker')
        result = results['absent_trace']
        self.assertEqual(result['summary']['synthetic_wrappers'], 10)
        self.assertEqual(result['summary']['no_native_trace_requests'], 10)

    def test_pmx_rejects_test_period_before_projection(self):
        _, _, grouped, requests = fixture('absent_trace')
        requests[0]['period'] = 'test'
        with self.assertRaises(ValueError):
            projection(native(grouped, requests), requests, 'opentelemetry_demo', 'fixture-worker')

    def test_primary_unsupported_retained_after_all_16_oracles_pass(self):
        prepared, raw = solver_fixture()
        candidates, controls = solver_forecasts(prepared, raw)
        self.assertTrue(controls['qualified'])
        self.assertEqual(controls['expected_two_pass_oracle_records'], 16)
        forecast = candidates[0]['forecasts']['operation']
        self.assertEqual(forecast['PMX']['status'], 'unsupported')
        self.assertIsNone(forecast['PMX']['probability'])
        self.assertEqual(forecast['PMX_inclusive']['probability'], .8)

    def test_failed_oracle_invalidates_application_points(self):
        prepared, raw = solver_fixture(); raw[0]['success_probability'] = .1
        candidates, controls = solver_forecasts(prepared, raw)
        self.assertFalse(controls['qualified'])
        self.assertIsNone(candidates[0]['forecasts']['operation']['PMX_inclusive']['probability'])

    def test_zero_physical_mass_and_nonrepeatable_solver_are_not_answers(self):
        prepared, raw = solver_fixture()
        for changed in (dict(raw[-1], physical_state_probability=0),
                        dict(raw[-1], success_probability=.7, failure_probability_sum=.3)):
            variant = deepcopy(raw); variant[-1] = changed
            candidates, _ = solver_forecasts(prepared, variant)
            self.assertEqual(candidates[0]['forecasts']['operation']['PMX_inclusive']['status'], 'failed')
        with self.assertRaises(ValueError):
            solver_forecasts(prepared, raw+[raw[0]])
