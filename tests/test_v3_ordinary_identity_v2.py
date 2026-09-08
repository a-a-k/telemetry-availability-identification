from copy import deepcopy
import unittest

from telemetry_availability.v3_ordinary_identity_v2 import extend_identity, replica_identity, demand_census
from telemetry_availability.v3_primary_projection import DECLARATION_FIELDS, project


class OrdinaryIdentityTests(unittest.TestCase):
    def declarations(self):
        result = {key: None for key in DECLARATION_FIELDS}
        result.update(profile='deathstarbench_social_network', target_service='user-timeline-service',
            replicas={'a': 'timeline-a', 'b': 'timeline-b'}, placement='colocated', failure_law='N', repetition=0)
        return result

    def test_exact_native_names_and_conflicts_are_preserved(self):
        span = dict(service='user-timeline-service', resource_attributes={'hostname': 'timeline-a'})
        self.assertEqual(replica_identity(span, self.declarations())['replica'], 'a')
        span['resource_attributes']['study.replica'] = 'b'
        result = replica_identity(span, self.declarations())
        self.assertIsNone(result['replica'])
        self.assertEqual(result['reason'], 'conflicting_native_identity')
        span['resource_attributes'] = {'hostname': 'timeline-a.other-domain'}
        self.assertIsNone(replica_identity(span, self.declarations())['replica'])

    def fixture(self):
        request = dict(request_id='r', trace_id='1', operation='read_user_timeline', period='calibration',
            started_at='2026-09-08T00:00:00Z', completed_at='2026-09-08T00:00:00.1Z',
            semantic_success='true', timed_out='false')
        span = dict(trace_id='1', span_id='2', parent_id='1', service='user-timeline-service',
            operation='read_user_timeline_server', server=False, start_us=1, duration_us=1,
            start_remainder_ns=0, duration_remainder_ns=0, error_tag=False, error_status=False,
            native_kind='', native_links=[], attributes={}, resource_attributes={'hostname': 'timeline-a'})
        native = dict(calibration_only=True, selected_trace_ids=['1'], spans={'1': [span]})
        return request, span, native

    def test_identity_extension_requires_exact_old_projection_and_changes_only_identity(self):
        request, span, native = self.fixture()
        data, _ = project(self.declarations(), [request], [], native)
        original = deepcopy(data)
        extended, audit = extend_identity(data, native)
        self.assertEqual(data, original)
        self.assertEqual(audit['added_native_identity_counts'], {'hostname': 1})
        self.assertNotIn('hostname', data['native.json']['spans']['1'][0]['resource_attributes'])
        self.assertEqual(extended['native.json']['spans']['1'][0]['resource_attributes']['hostname'], 'timeline-a')
        for key in ('requests.json', 'probes.json', 'declarations.json'):
            self.assertEqual(extended[key], data[key])
        native['spans']['1'][0]['duration_us'] = 2
        with self.assertRaises(ValueError):
            extend_identity(data, native)

    def test_source_declared_entry_and_failed_missing_call_are_not_fabricated_servers(self):
        request, span, native = self.fixture()
        parent = dict(span, span_id='1', parent_id='', service='nginx', operation='root', resource_attributes={})
        native['spans']['1'].append(parent)
        failed = dict(request, request_id='r2', trace_id='3', semantic_success='false', timed_out='true')
        native['selected_trace_ids'].append('3')
        report = demand_census([request, failed], native, self.declarations(), {'read_user_timeline': 1})['read_user_timeline']
        self.assertEqual(report['census']['attempts'], 2)
        self.assertEqual(report['census']['observed_entries_and_identities_complete'], 1)
        self.assertEqual(report['entry_kinds'], {'source_declared_unlabelled_entry': 1})
        self.assertFalse(span['server'])
        self.assertEqual(sum(r['attempts'] for r in report['footprint_census']), 2)
        span['operation'] = 'guessed_server_suffix'
        report = demand_census([request], native, self.declarations(), {'read_user_timeline': 1})['read_user_timeline']
        self.assertEqual(report['census']['unclassified_target_boundaries'], 1)
        self.assertEqual(report['census']['observed_entries'], 0)
