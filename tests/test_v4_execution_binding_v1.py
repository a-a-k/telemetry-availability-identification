import unittest
from telemetry_availability.v4_execution_binding_v1 import logical_completion, native_admissions


PAIR=('api-gateway','visits-service')


def span(sid,parent,service,start,duration,status,kind='client'):
    return dict(span_id=sid,parent_id=parent,service=service,operation='POST',start_us=start,
        start_remainder_ns=0,duration_us=duration,duration_remainder_ns=0,server=kind=='server',
        native_kind=kind,error_tag=False,error_status=status>=400,
        attributes={'server.address':'visits-service','http.response.status_code':str(status)},
        resource_attributes={'study.replica':'a'} if kind=='server' else {})


def retry_fixture():
    first=span('first','root','api-gateway',100,500,503)
    final=span('final','root','api-gateway',610,100,201)
    receiver=span('receiver','final','visits-service',620,60,201,'server')
    evidence=dict(client_failures={PAIR},root_status=True,calls={PAIR:[dict(span=receiver,parent=final,
        optional_for_completion=False)]})
    spec=dict(client_route_names=['visits-service'],ignored_rpc_methods_by_pair={},minimum_calls_by_pair={},
              source_error_propagation_assumed=True,deadline_ns=2_000_000_000)
    return evidence,[first,final,receiver],spec


class BindingRevisionTests(unittest.TestCase):
    def test_retry_is_logical_completion_with_independent_failed_transport(self):
        e,spans,spec=retry_fixture()
        value,reason=logical_completion(PAIR,e,spans,spec,'spring_petclinic_microservices','create_visit')
        self.assertIs(value,True)
        self.assertIn('503_then_201',reason)
        self.assertEqual(e['client_failures'],{PAIR})

    def test_missing_final_response_is_unknown_not_final_failure(self):
        e,spans,spec=retry_fixture()
        value,_=logical_completion(PAIR,e,spans[:1],spec,'spring_petclinic_microservices','create_visit')
        self.assertIsNone(value)

    def test_policy_does_not_rescue_other_operation(self):
        e,spans,spec=retry_fixture()
        value,_=logical_completion(PAIR,e,spans,spec,'spring_petclinic_microservices','owner_details_with_visits')
        self.assertIs(value,False)

    def test_earlier_receiver_effect_cannot_be_assumed_away(self):
        e,spans,spec=retry_fixture(); earlier=span('earlier','first','visits-service',200,20,503,'server')
        spans.append(earlier);e['calls'][PAIR].append(dict(span=earlier,parent=spans[0],optional_for_completion=False))
        value,_=logical_completion(PAIR,e,spans,spec,'spring_petclinic_microservices','create_visit')
        self.assertIsNone(value)

    def test_receiver_proves_admission_even_if_business_response_fails(self):
        e,spans,spec=retry_fixture();receiver=spans[-1]
        receiver['attributes']['http.response.status_code']='500';receiver['error_status']=True
        declarations=dict(profile='spring_petclinic_microservices',target_service='visits-service',replicas={'a':'a','b':'b'})
        request=dict(started_at='1970-01-01T00:00:00Z',completed_at='1970-01-01T00:00:00.001000Z')
        state,_=native_admissions(e,declarations,request,spec)
        self.assertIs(state['admitted_a'],True);self.assertIsNone(state['admitted_b'])
        request['completed_at']='1970-01-01T00:00:00.000600Z'
        state,_=native_admissions(e,declarations,request,spec)
        self.assertIsNone(state['admitted_a'])


if __name__=='__main__':unittest.main()
