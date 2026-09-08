import copy
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telemetry_availability.whole_operation_contract import execute, http_exchange, otel_verdict
from telemetry_availability.live_pilot import OTEL_PERSON, OTEL_PRODUCT


MONEY=dict(currencyCode='USD',units='12',nanos=500000000)
PRODUCT=dict(id=OTEL_PRODUCT,name='Fixture',description='Fixture description',picture='/fixture.png',categories=['test'],priceUsd=MONEY)
ORDER=dict(orderId='order-1',shippingTrackingId='tracking-1',shippingAddress=OTEL_PERSON['address'],shippingCost=MONEY,
           items=[dict(item=dict(productId=OTEL_PRODUCT,quantity=1,product=PRODUCT),cost=MONEY)])


class OperationContractTest(unittest.TestCase):
    def fake(self,durations,alter=None):
        state=dict(now=0,headers=[],deadlines=[])
        def exchange(url,**kwargs):
            i=len(state['headers']);state['now']+=durations[i]
            state['headers'].append(kwargs['headers']);state['deadlines'].append(kwargs['deadline'])
            if '/products/' in url: payload=copy.deepcopy(PRODUCT)
            elif url.endswith('/cart'):
                request=json.loads(kwargs['data']);payload=dict(userId=request['userId'],items=[request['item']])
            else: payload=copy.deepcopy(ORDER)
            if alter: payload=alter(i,payload)
            return 200,json.dumps(payload).encode()
        def run():
            return execute('http://unused','opentelemetry_demo','checkout','unique-external-request',0,
                exchange=exchange,clock=lambda:state['now'],wall_clock=lambda:1700000000+state['now'])
        return state,run

    def test_three_roots_share_one_budget_id_and_final_outcome(self):
        state,run=self.fake([.4,.6,.5]);row=run()
        self.assertTrue(row['semantic_success']);self.assertEqual(len(row['http_steps']),3)
        self.assertEqual(state['deadlines'],[2,2,2])
        self.assertEqual(len({h['traceparent'] for h in state['headers']}),1)
        self.assertEqual(len({h['X-Study-Request-ID'] for h in state['headers']}),1)
        self.assertFalse(row['trace_presence_used_for_verdict'])

    def test_each_step_under_two_seconds_still_fails_whole_deadline(self):
        state,run=self.fake([.8,.8,.8]);row=run()
        self.assertEqual(row['status_code'],200)
        self.assertTrue(row['timed_out']);self.assertFalse(row['semantic_success'])
        self.assertEqual(row['semantic_reason'],'whole_operation_timeout')

    def test_successful_status_with_wrong_prerequisite_stops_sequence(self):
        state,run=self.fake([.1,.1,.1],lambda i,p:dict(p,id='wrong-product') if i==0 else p)
        row=run();self.assertFalse(row['semantic_success']);self.assertEqual(len(state['headers']),1)
        self.assertIn('prerequisite_',row['semantic_reason'])

    def test_partial_checkout_duplicate_item_and_wrong_user_rejected(self):
        self.assertTrue(otel_verdict('checkout',200,json.dumps(ORDER).encode(),'user')[0])
        partial=copy.deepcopy(ORDER);del partial['items']
        self.assertFalse(otel_verdict('checkout',200,json.dumps(partial).encode(),'user')[0])
        for items,user in [([dict(productId=OTEL_PRODUCT,quantity=1)]*2,'user'),
                           ([dict(productId=OTEL_PRODUCT,quantity=1)],'wrong-user'),
                           ([dict(productId=OTEL_PRODUCT,quantity=True)],'user')]:
            self.assertFalse(otel_verdict('add_to_cart',200,json.dumps(dict(userId=user,items=items)).encode(),'user')[0])

    def test_deathstar_partial_timeline_is_not_success(self):
        for body,expected in [(b'{}',True),(b'[]',True),(b'[{"post_id":"1"}]',False)]:
            row=execute('http://unused','deathstarbench_social_network','read_user_timeline','ds-control',0,
                exchange=lambda *a,**kw:(200,body))
            self.assertEqual(row['semantic_success'],expected)

    def test_real_transport_consumes_finite_body_and_bounds_dribble(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Length','4');self.end_headers()
                try:
                    for b in b'test':
                        self.wfile.write(bytes([b]));self.wfile.flush()
                        if self.path=='/slow': time.sleep(.08)
                except ConnectionError: pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            status,body=http_exchange(url+'/fast',data=None,content_type=None,headers={},deadline=time.monotonic()+1)
            self.assertEqual((status,body),(200,b'test'))
            before=time.monotonic()
            with self.assertRaises(TimeoutError):
                http_exchange(url+'/slow',data=None,content_type=None,headers={},deadline=before+.15)
            self.assertLess(time.monotonic()-before,.4)
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__': unittest.main()
