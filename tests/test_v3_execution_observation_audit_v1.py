import copy
import unittest

from telemetry_availability.v3_execution_observation_audit_v1 import (
    boundary_context, interval_union_ns, summarize, timestamp_ns)


class ExecutionObservationAuditTests(unittest.TestCase):
    def fixture(self):
        profile = 'opentelemetry_demo'
        trace, parent = boundary_context(profile, 'r1')
        request = dict(request_id='r1', trace_id=trace, operation='checkout', period='calibration',
            started_at='2026-09-08T00:00:00+00:00', completed_at='2026-09-08T00:00:02.001+00:00',
            semantic_success='false', timed_out='true')
        base = timestamp_ns(request['started_at']) // 1000
        def span(name, start, duration, service):
            return dict(trace_id=trace, span_id=name, parent_id=parent, service=service,
                server=True, error_tag=False, error_status=False, start_us=base+start,
                duration_us=duration, start_remainder_ns=0, duration_remainder_ns=0,
                attributes={}, resource_attributes={})
        # Two overlapping roots: sum 3s, union 1.7s; neither means the full event succeeded.
        spans = [span('1', 0, 1500000, 'frontend'), span('2', 200000, 1500000, 'frontend')]
        native = dict(calibration_only=True, selected_trace_ids=[trace], spans={trace: spans})
        declarations = dict(profile=profile, target_service='catalog', replicas={'a': {}, 'b': {}})
        return [request], native, declarations

    def test_timeout_without_native_errors_and_overlapping_roots_stay_visible(self):
        report = summarize(*self.fixture(), ['checkout'])
        row = report['operations']['checkout']
        counts = row['census']
        self.assertEqual(counts['attempts'], 1)
        self.assertEqual(counts['failures'], 1)
        self.assertEqual(counts['attempts_with_native_but_no_error_flag'], 1)
        self.assertEqual(counts['attempts_with_multiple_external_roots'], 1)
        self.assertEqual(counts['attempts_with_root_sum_above_deadline'], 1)
        self.assertEqual(counts['attempts_with_root_union_above_deadline'], 0)
        self.assertEqual(row['outcome_census']['timeout']['attempts'], 1)
        self.assertFalse(report['no_error_flag_is_semantic_success'])
        self.assertIsNone(row['forecast'])

    def test_absent_native_and_absent_replica_are_not_invented(self):
        requests, native, declarations = self.fixture()
        native['spans'] = {}
        row = summarize(requests, native, declarations, ['checkout'])['operations']['checkout']
        self.assertEqual(row['census']['attempts_without_native'], 1)
        self.assertEqual(row['target_instance_span_counts'], {})
        requests, native, declarations = self.fixture()
        next(iter(native['spans'].values()))[0]['service'] = 'catalog'
        row = summarize(requests, native, declarations, ['checkout'])['operations']['checkout']
        self.assertEqual(row['target_instance_span_counts'], {'<missing>': 1})
        self.assertEqual(row['census']['attempts_with_target_instance_for_every_observed_server'], 0)

    def test_census_invalid_roles_and_context_are_rejected(self):
        for field, value in [('period', 'test'), ('trace_id', 'wrong'), ('semantic_success', '0')]:
            requests, native, declarations = self.fixture()
            requests[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize(requests, native, declarations, ['checkout'])
        requests, native, declarations = self.fixture()
        with self.assertRaises(ValueError):
            summarize(requests + copy.deepcopy(requests), native, declarations, ['checkout'])

    def test_integer_timestamp_and_interval_boundaries(self):
        self.assertEqual(timestamp_ns('1970-01-01T03:00:00.000001+03:00'), 1000)
        self.assertEqual(interval_union_ns([(0, 10), (2, 5), (8, 12), (15, 20)]), 17)
        self.assertEqual(interval_union_ns([]), 0)
        with self.assertRaises(ValueError):
            timestamp_ns('2026-09-08T00:00:00')
