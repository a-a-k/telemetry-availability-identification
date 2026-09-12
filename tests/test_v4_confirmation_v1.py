from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import io
import json
import unittest
from unittest.mock import patch

from test_v3_application_execution_v1 import fixture
from test_v3_comparison_pipeline_v1 import frozen_case,identity
from telemetry_availability.v4_primary_capture_v1 import bytes_record,read_health_snapshot,project_test_native,REQUEST_FIELDS,SQL
from telemetry_availability.v4_confirmation_orchestration_v1 import validate_complete
from telemetry_availability.v4_confirmation_verification_v1 import independent_petclinic,sql_rows,build_period
from telemetry_availability.v4_confirmation_candidates_v1 import fit_operation,identify_g0
from telemetry_availability.v3_application_execution_v2 import align_probe,timestamp_ns
from telemetry_availability.g0_aina_ordinary_v1 import solve as solve_g0
from telemetry_availability.v4_petclinic_capture_v1 import execute


def write_attempt():
    request_id='artificial-write';marker='study-'+sha256(request_id.encode()).hexdigest()
    payload=dict(id=123,petId=1,date='2026-09-01',description=marker)
    raw=json.dumps(payload).encode();record=bytes_record(raw)
    return dict(request_id=request_id,operation='create_visit',status_code=201,payload=payload,
        latency_ms=100,marker=marker,response_base64=record['base64'],response_bytes=record['bytes'],
        response_sha256=record['sha256']),payload


class ConfirmationTests(unittest.TestCase):
    def test_missing_numerical_pmx_blocks_even_an_integrity_valid_candidate(self):
        _,candidate,_,_,_=frozen_case()
        candidate['forecasts']['toy']['PMX']['reason']='unsupported_conditional_propagation_or_positivity'
        self.assertTrue(validate_complete(candidate,['toy']))
        for method in ('PMX','PMX_inclusive','B0'):
            changed=deepcopy(candidate)
            changed['forecasts']['toy'][method]=dict(status='missing',probability=None,reason='job missing')
            with self.assertRaises(ValueError):validate_complete(changed,['toy'])
        candidate['forecasts']['toy']['PMX']['reason']='timeout'
        with self.assertRaises(ValueError):validate_complete(candidate,['toy'])

    def test_snapshot_cannot_be_used_before_reading_finishes(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc);end=datetime(2026,1,1,0,0,2,tzinfo=timezone.utc)
        module='telemetry_availability.v4_primary_capture_v1.health_source.'
        with patch(module+'_utc_now',side_effect=[start,end]),patch(module+'_inspect_containers',return_value={}),patch(module+'_proxy_stats',return_value={}):
            _,_,timing=read_health_snapshot([],None,None,None)
        self.assertEqual(timestamp_ns(timing['observed_at']),timestamp_ns(end.isoformat()))
        probe=dict(timing,replica_a_backend_status='UP',replica_b_backend_status='UP',
            replica_a_backend_check_status='L4OK',replica_b_backend_check_status='L4OK')
        state,_=align_probe(timestamp_ns(start.isoformat())+1_000_000_000,[probe],[timestamp_ns(timing['observed_at'])],2_000_000_000,['L4OK'])
        self.assertEqual(state,dict(probe_a=None,probe_b=None))

    def test_persistence_is_not_proved_by_ack_or_stored_success_count(self):
        request,payload=write_attempt();request.update(semantic_success=True,persisted_marker_count=1)
        self.assertFalse(independent_petclinic(request,{},[])['outcome'])
        self.assertTrue(independent_petclinic(request,{},[payload])['outcome'])
        self.assertFalse(independent_petclinic(request,{},[payload,dict(payload,id=124)])['outcome'])
        self.assertFalse(independent_petclinic(request,{},[dict(payload,petId=2)])['outcome'])
        request['latency_ms']=2001
        self.assertFalse(independent_petclinic(request,{},[payload])['outcome'])

    def test_corrupt_primary_body_or_SQL_cannot_be_verified(self):
        request,payload=write_attempt();request['response_sha256']='0'*64
        with self.assertRaises(ValueError):independent_petclinic(request,{},[payload])
        record=dict(query=SQL,returncode=0,period='test',stdout=bytes_record(json.dumps(payload).encode()),stderr=bytes_record(b''))
        self.assertEqual(sql_rows(record,'test'),[payload])
        record['stdout']['bytes']+=1
        with self.assertRaises(ValueError):sql_rows(record,'test')

    def test_projection_keeps_test_identity_and_drops_privileged_attributes(self):
        data,_,request,spans,_=fixture();request['period']='test'
        for span in spans:
            span['native_links']=[]
            span['attributes']['injected.true_state']=True
            span['resource_attributes']['latent.failure']=True
        native=project_test_native({request['trace_id']:spans},[request])
        self.assertEqual(native['period'],'test')
        for span in native['spans'][request['trace_id']]:
            self.assertNotIn('injected.true_state',span['attributes'])
            self.assertNotIn('latent.failure',span['resource_attributes'])

    def test_realized_bounds_need_no_business_labels_and_keep_contradicting_proxy(self):
        data,spec,request,spans,declarations=fixture()
        declarations['backend_success_check_statuses']=['L4OK']
        data['probes.json'][0].update(replica_a_backend_status='DOWN',replica_b_backend_status='DOWN')
        model,report=fit_operation(data,'toy',spec,identity())
        self.assertEqual(report['estimates']['execution']['prediction'],1)
        self.assertEqual(solve_g0(identify_g0(model))['prediction'],0)
        request['period']='test'
        data['requests.json']=[{k:request[k] for k in REQUEST_FIELDS}]
        data['native.json'].update(period='test',external_business_outcomes_present=False,selected_trace_ids=[request['trace_id']])
        data['manifest.json']=dict(native_parse=dict(malformed_json_records=0,invalid_traces=0))
        result=build_period(data,{'toy':spec},identity(),'test')
        self.assertEqual((result['attempts']['toy'][0]['lower'],result['attempts']['toy'][0]['upper']),(1,1))
        data['requests.json'][0]['semantic_success']=False
        with self.assertRaises(ValueError):build_period(data,{'toy':spec},identity(),'test')

    def test_actual_http_capture_retains_exact_bytes(self):
        class Response(io.BytesIO):status=201
        body=b'{"id":123,"petId":1,"date":"2026-09-01","description":"fake"}'
        config=dict(write_date='2026-09-01',operation_deadline_seconds=2,response_limit_bytes=1024)
        with patch('urllib.request.urlopen',return_value=Response(body)):
            record=execute('http://artificial.invalid','create_visit','artificial-only',{},config)
        self.assertEqual(record['response_base64'],bytes_record(body)['base64'])
        self.assertEqual(record['response_sha256'],sha256(body).hexdigest())


if __name__=='__main__':unittest.main()
