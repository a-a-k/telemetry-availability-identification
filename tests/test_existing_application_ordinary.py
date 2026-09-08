from copy import deepcopy
import unittest

from telemetry_availability.existing_application_ordinary import technical_requests
from telemetry_availability.live_fault_campaign import make_trace_context


class RetainedNormalWindowTests(unittest.TestCase):
    def rows(self, profile):
        result = []
        for i, success in enumerate((True, False)):
            identity = f'artificial-request-{i}'
            trace, header, _ = make_trace_context(profile, identity)
            result.append(dict(profile=profile, period='baseline', request_id=identity,
                trace_id=trace, trace_header=header, semantic_success=success,
                started_at='2026-01-01T00:00:00Z', completed_at='2026-01-01T00:00:01Z'))
        return result

    def test_role_adaptation_preserves_failures_times_and_original_rows(self):
        for profile in ('deathstarbench_social_network', 'opentelemetry_demo'):
            rows = self.rows(profile)
            before = deepcopy(rows)
            adapted = technical_requests(rows, profile)
            self.assertEqual(rows, before)
            self.assertEqual(adapted, [dict(row, period='calibration') for row in before])
            self.assertEqual([row['semantic_success'] for row in adapted], [True, False])

    def test_foreign_period_identity_header_and_duplicate_are_rejected(self):
        profile = 'opentelemetry_demo'
        for field, value in (('period', 'test'), ('profile', 'another'),
                             ('trace_id', 'foreign'), ('trace_header', 'uber-trace-id')):
            rows = self.rows(profile)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                technical_requests(rows, profile)
        rows = self.rows(profile)
        with self.assertRaises(ValueError):
            technical_requests(rows + [rows[0]], profile)
