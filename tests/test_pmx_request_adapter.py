import unittest
from dataclasses import replace

from telemetry_availability.pmx_observed_operations import AdapterError
from telemetry_availability.pmx_request_adapter import project_campaign, project_request
from telemetry_availability.pmx_request_controls import CASES, fixture
from telemetry_availability.pmx_request_pcm import conditional_probabilities


class RequestAdapterTests(unittest.TestCase):
    def test_fixture_counts_and_independent_composition(self):
        for case in CASES:
            result, expected, _, _ = fixture(case)
            self.assertEqual(result['summary']['projected_requests'], 10)
            self.assertEqual(result['summary']['synthetic_wrappers'], 10)
            self.assertEqual(result['summary']['rejected_requests'], 0)
            for variant, probability in expected['success'].items():
                product = 1
                for row in result['operation_oracle']:
                    p = row['inclusive_probability'] if variant == 'inclusive' else row['conditional_local_probability']
                    product *= (1-p)**(row['invocations']/10)
                self.assertAlmostEqual(product, probability, places=12)
            self.assertEqual(result['summary']['unsupported_conditional_local_operations'] == 0,
                             expected['conditional_supported'])

    def test_native_provenance_and_structural_wrapper(self):
        result, _, grouped, _ = fixture('compound_http')
        self.assertEqual(len(result['native_audit']), 30)
        for trace in result['envelope']['data']:
            root = next(s for s in trace['spans'] if not s['references'])
            self.assertLess(root['startTime'], min(s.start_us for s in grouped[trace['traceID']]))
            original = {s.span_id: s for s in grouped[trace['traceID']]}
            for span in trace['spans']:
                if span['spanID'] in original:
                    self.assertEqual(span['startTime'], original[span['spanID']].start_us)
                    self.assertEqual(span['duration'], original[span['spanID']].duration_us)

    def test_contracted_and_repeated_operations(self):
        result, _, _, _ = fixture('unmarked_service_boundary')
        self.assertEqual(result['summary']['selected_native_spans'], 20)
        self.assertEqual(sum(len(row['contracted_ancestors']) for row in result['native_audit']), 10)
        result, _, _, _ = fixture('repeated_http_and_collision')
        self.assertEqual(sorted(r['invocations'] for r in result['operation_oracle']), [10, 10, 20])

    def test_reject_ambiguous_identity_and_cycles(self):
        _, _, grouped, requests = fixture('nested_propagated')
        duplicate = [requests[0], dict(requests[1], request_id=requests[0]['request_id'])]
        with self.assertRaises(AdapterError):
            project_campaign(grouped, duplicate, 'explicit_server', 'fixture')
        spans = grouped[requests[0]['trace_id']]
        spans[0] = replace(spans[0], parent_id=spans[1].span_id)
        with self.assertRaises(AdapterError):
            project_request(spans, requests[0], 'explicit_server', 'fixture')

    def test_no_trace_not_reported_as_native_and_test_rows_rejected(self):
        result, _, _, requests = fixture('absent_trace')
        self.assertEqual(result['summary']['no_native_trace_requests'], 10)
        self.assertEqual(result['summary']['selected_native_spans'], 0)
        with self.assertRaises(AdapterError):
            project_request([], dict(requests[0], period='test'), 'explicit_server', 'fixture')

    def test_parameter_change_preserves_qname_namespaces_and_rejects_swallowed(self):
        text = '<repository xmlns:seff="urn:seff"><signature id="s" entityName="op"/><serviceEffectSpecifications__BasicComponent describedService__SEFF="s"><failure failureProbability="0.2"/></serviceEffectSpecifications__BasicComponent></repository>'
        oracle = [{'operation': 'op', 'inclusive_probability': .2,
                   'conditional_local_probability': 1/9, 'observed_propagation_compatible': True}]
        result, changes = conditional_probabilities(text, oracle)
        self.assertIn('xmlns:seff="urn:seff"', result)
        self.assertAlmostEqual(changes[0]['after'], 1/9)
        oracle[0]['observed_propagation_compatible'] = False
        with self.assertRaises(ValueError):
            conditional_probabilities(text, oracle)
