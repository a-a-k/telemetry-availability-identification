import base64
from hashlib import sha256
import json
import unittest
from telemetry_availability.primary_verdict_audit_v1 import accept_response, http_evidence, matches_fixture, petclinic_evidence


class IndependentVerdictTests(unittest.TestCase):
    def test_cart_requires_exact_user_and_quantity(self):
        payload = dict(userId='u', items=[dict(productId='p', quantity=1)])
        args = ('opentelemetry_demo','add_to_cart',200)
        self.assertTrue(accept_response(*args, json.dumps(payload).encode(), 'u','p',{}))
        self.assertFalse(accept_response(*args, json.dumps(payload).encode(), 'other','p',{}))
        payload['items'][0]['quantity'] = True
        self.assertFalse(accept_response(*args, json.dumps(payload).encode(), 'u','p',{}))

    def test_response_hash_and_deadline_not_stored_label(self):
        body = b'Successfully upload post'
        step = dict(operation='compose_post', status_code=200, response_base64=base64.b64encode(body).decode(),
            response_sha256=sha256(body).hexdigest(), response_bytes=len(body), completed_offset_seconds=0.1)
        request = dict(profile='deathstarbench_social_network',operation='compose_post',http_steps=[step],
                       latency_ms=100,error='',semantic_success=False)
        self.assertTrue(http_evidence(request,'p',{})['outcome'])
        request['latency_ms'] = 2001
        self.assertFalse(http_evidence(request,'p',{})['outcome'])
        step['response_sha256'] = 'bad'
        with self.assertRaises(ValueError): http_evidence(request,'p',{})

    def test_persistence_not_inferred_from_created_ack(self):
        request = dict(operation='create_visit',status_code=201,latency_ms=10,marker='m',
            payload=dict(id=3,petId=1,date='2026-09-01',description='m'),persisted_marker_count=1,semantic_success=True)
        result = petclinic_evidence(request,{})
        self.assertIsNone(result['outcome'])
        self.assertFalse(result['persistence_independently_verified'])

    def test_fixture_rejects_duplicate_id(self):
        self.assertFalse(matches_fixture([dict(id=1),dict(id=1)], [dict(id=1),dict(id=2)]))
        self.assertTrue(matches_fixture([dict(id=2),dict(id=1)], [dict(id=1),dict(id=2)]))


if __name__ == '__main__': unittest.main()
