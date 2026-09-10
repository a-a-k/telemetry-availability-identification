"""Exact eight-field request-role controls for the versioned PMX profile bridge."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetry_availability.pmx_request_controls import fixture
from telemetry_availability.pmx_database_client_controls import control as db_control
from telemetry_availability.v3_primary_projection import REQUEST_FIELDS
from telemetry_availability.v3_comparison_roles_v1 import seal_role
from telemetry_availability import v3_comparison_pmx_v1 as old
from telemetry_availability import v3_comparison_pmx_v2 as new


def input_case(profile, absent=False):
    if profile=='spring_petclinic_microservices' and not absent:
        _,_,grouped,requests=db_control('shared_database_two_callers')
    else:
        _,_,grouped,requests=fixture('absent_trace' if absent else ('unmarked_service_boundary' if profile=='deathstarbench_social_network' else 'nested_propagated'))
    rows=[{key:row[key] for key in REQUEST_FIELDS} for row in requests]
    native=dict(calibration_only=True,selected_trace_ids=[r['trace_id'] for r in rows],spans={key:[asdict(span) for span in spans] for key,spans in grouped.items()})
    return native,rows


class PmxProfileBridgeTests(unittest.TestCase):
    def test_exact_sealed_schema_reproduces_v1_failure_and_v2_matches_declared_legacy_bridge(self):
        for profile in new.POLICIES:
            with self.subTest(profile=profile):
                native,rows=input_case(profile);before=deepcopy((native,rows))
                self.assertTrue(all(set(row)==set(REQUEST_FIELDS) for row in rows))
                with self.assertRaisesRegex(KeyError,'profile'):
                    old.projection(native,rows,profile,'fixture-worker')
                expected,_=old.projection(native,[dict(row,profile=profile) for row in rows],profile,'fixture-worker')
                actual,_=new.projection(native,rows,profile,'fixture-worker')
                self.assertEqual(actual,expected)
                self.assertEqual((native,rows),before)
                for result in actual.values():self.assertEqual(result['summary']['projected_requests'],len(rows))

    def test_extra_spoofed_profile_and_closed_outcomes_rejected(self):
        native,rows=input_case('opentelemetry_demo')
        for extra in ({'profile':'spring_petclinic_microservices'},{'test_success':True}):
            changed=deepcopy(rows);changed[0].update(extra)
            with self.assertRaisesRegex(ValueError,'field whitelist'):
                new.projection(native,changed,'opentelemetry_demo','fixture-worker')
        changed=deepcopy(rows);changed[0]['period']='test'
        with self.assertRaisesRegex(ValueError,'another period'):
            new.projection(native,changed,'opentelemetry_demo','fixture-worker')

    def test_untraced_failures_keep_all_attempts(self):
        for profile in new.POLICIES:
            native,rows=input_case(profile,absent=True)
            result,_=new.projection(native,rows,profile,'fixture-worker')
            summary=result['absent_trace']['summary']
            self.assertEqual(summary['synthetic_wrappers'],10)
            self.assertEqual(summary['no_native_trace_requests'],10)

    def test_real_role_boundary_with_artificial_rows_supplies_profile_from_identity(self):
        for profile in new.POLICIES:
            with self.subTest(profile=profile),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve();source=root/'role';out=root/'projection';out.mkdir()
                native,rows=input_case(profile)
                identity=dict(application=profile,placement='colocated',law='N',repetition=0,namespace='artificial-role',data_role='artificial_control',protocol_sha256='c'*64)
                manifest=dict(identity=identity,native_quality=dict(qualified=True),declared_host='fixture-worker')
                seal_role(source,'pmx_calibration',identity,{'native.json':native,'requests.json':rows,'manifest.json':manifest})
                options=root/'Options.txt';options.write_bytes(b'ArtificialOptions traces/jaegercustomers.json')
                settings=dict(identity_protocol_sha256='c'*64,profiles={profile:dict(operations={rows[0]['operation']:dict(expected_attempts=len(rows))})})
                with patch.object(new,'OPTIONS_SHA',sha256(options.read_bytes()).hexdigest()),patch.dict('os.environ',{'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'artificial'}):
                    new.prepare(source,options,out,settings)
                contract=json.loads((out/'application-input-contract.json').read_bytes())
                self.assertEqual(contract['prospective_identity'],identity)
                self.assertEqual(contract['samples'][0]['cases'][0]['expected_requests'],10)
                audit=contract['read_audit']
                self.assertEqual(audit['blocked'],[]);self.assertEqual(len(audit['actual_data_reads']),4)
                self.assertEqual(audit['health_or_our_model_or_evaluator_inputs'],0)
                self.assertEqual(audit['external_wrapper_profile_source'],'sealed campaign identity.application; not an extra request field')
                self.assertEqual(json.loads((source/'requests.json').read_bytes()),rows)


if __name__=='__main__':unittest.main()
