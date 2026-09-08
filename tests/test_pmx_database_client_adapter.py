from dataclasses import replace
import unittest
from telemetry_availability.pmx_database_client_adapter import database_endpoint,project_campaign
from telemetry_availability.pmx_database_client_controls import control
from telemetry_availability.pmx_request_context import contextualize


class DatabaseClientProjectionTest(unittest.TestCase):
    def test_observed_client_keeps_native_kind_error_parent_and_times(self):
        projected,expected,grouped,requests=control('database_propagated')
        db=[r for r in projected['native_audit'] if r['representation_role']=='observed_db_client_endpoint']
        self.assertEqual(len(db),10)
        self.assertTrue(all(r['native_span']['server'] is False and r['native_span']['native_kind']=='3' for r in db))
        self.assertEqual(sum(r['native_span']['error_tag'] for r in db),1)
        mapping=[r for r in projected['mapping'] if r['service'].startswith('taid.observed-db-client.')]
        self.assertTrue(all(not r['native_server_kind_observed'] for r in mapping))
        self.assertEqual(len({r['pmx_component'] for r in mapping}),1)
        self.assertTrue(projected['summary']['all_non_identity_envelope_fields_preserved'])
        self.assertEqual(expected,dict(inclusive=.576,conditional_local=.8))

    def test_two_callers_share_one_database_component_but_separate_call_contexts(self):
        projected,expected,grouped,requests=control('shared_database_two_callers')
        mapping=[r for r in projected['mapping'] if r['service'].startswith('taid.observed-db-client.')]
        self.assertEqual(len(mapping),20)
        self.assertEqual(len({r['pmx_component'] for r in mapping}),1)
        self.assertEqual(len({r['pmx_operation'] for r in mapping}),2)
        self.assertAlmostEqual(expected['inclusive'],.9**5)
        self.assertAlmostEqual(expected['conditional_local'],.9**2)
        # The empirical correlated outcome is .9; it is not the independent-call oracle.
        self.assertEqual(sum(r['semantic_success'] for r in requests)/10,.9)

    def test_missing_peer_is_explicitly_unsupported(self):
        _,_,grouped,requests=control('database_propagated')
        span=next(s for spans in grouped.values() for s in spans if s.native_kind=='3')
        attrs=dict(span.attributes);del attrs['server.address']
        with self.assertRaisesRegex(ValueError,'peer identity'):
            database_endpoint(replace(span,attributes=attrs))


if __name__=='__main__': unittest.main()
