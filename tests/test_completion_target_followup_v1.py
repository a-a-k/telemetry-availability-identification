from copy import deepcopy
import unittest

from telemetry_availability import completion_target_v1 as target
from telemetry_availability import completion_target_profile_v1 as profile
from telemetry_availability.v3_execution_observation_audit_v1 import boundary_context
from telemetry_availability.graph_execution_model_v1 import solve
from test_graph_execution_model_v1 import make, row
from test_v4_execution_binding_v1 import span


def fixture():
    app='deathstarbench_social_network'; trace,parent=boundary_context(app,'toy')
    native=[span('root',parent,'entry',100,800,200,'server'),span('child','root','service',200,100,200,'server')]
    data={'requests.json':[dict(request_id='toy',trace_id=trace,operation='op',period='calibration',
        started_at='1970-01-01T00:00:00Z',completed_at='1970-01-01T00:00:00.001Z',semantic_success=False)],
        'native.json':{'spans':{trace:native}},'probes.json':[],
        'declarations.json':dict(profile=app,target_service='service',replicas={'a':'a','b':'b'},backend_success_check_statuses=['L4OK'])}
    spec=dict(expected_attempts=1,entry='entry',allowed_native_services=['entry','service'],required_native_services=['service'],
        required_native_pairs=[['entry','service']],target_calls=1,external_roots=1,minimum_calls_by_pair={},
        ignored_rpc_methods_by_pair={},source_error_propagation_assumed=True,client_route_names=['service'],database_peers=[],
        deadline_ns=2_000_000,maximum_probe_age_ns=1_000_000,assumptions={})
    return data,spec,dict(application=app)


class FollowupTests(unittest.TestCase):
    def test_instrumentation_preserves_binding_and_direct_law(self):
        data,spec,identity=fixture()
        for direct in (False,True):
            expected,rows=(target.direct_identify if direct else target.full_identify)(data,'op',spec,identity)
            actual,actual_rows,times,calls=profile.identify(data,'op',spec,identity,direct=direct)
            self.assertEqual(actual,expected); self.assertEqual(actual_rows,rows)
            self.assertTrue(all(v>=0 for v in times.values()))
            self.assertAlmostEqual(times['total_identification_seconds'],sum(v for k,v in times.items() if k!='total_identification_seconds'))
            self.assertEqual(calls['request_evidence'],1)
            changed=deepcopy(data); changed['requests.json'][0]['semantic_success']=True
            self.assertEqual(actual,profile.identify(changed,'op',spec,identity,direct=direct)[0])

    def test_E_control_preserves_original_exact_target(self):
        for observations in ([row()], [row(),row(a=False,b=False)],
                             [row(a=None,b=None,da=None,db=None,call_completed=None),row(timely=False)]):
            model=make(observations); expected=solve(model)['estimates']['execution']; actual=profile.query_e(model)
            self.assertEqual((actual['lower_exact'],actual['upper_exact']),(expected['lower_exact'],expected['upper_exact']))


if __name__=='__main__':unittest.main()
