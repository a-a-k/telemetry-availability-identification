"""Versioned external-operation contracts for the two existing applications.

Every prerequisite and final HTTP exchange consumes one shared 2-second budget.
One request ID/trace context covers the complete sequence; no driver retries.
"""
import base64
from datetime import datetime, timezone
import hashlib
import http.client
import json
import time
from urllib.parse import urlencode, urlsplit

from .live_fault_campaign import make_trace_context
from .live_pilot import OTEL_PRODUCT, OTEL_PERSON
from .live_placement_pilot import validate_operation_response

DEADLINE_SECONDS=2.0
MAX_RESPONSE_BYTES=1024*1024


def http_exchange(url, *, data, content_type, headers, deadline, clock=time.monotonic):
    """Bound reads by the remaining whole-operation budget, including body reads."""
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname:
        raise ValueError('unsupported HTTP URL')
    remaining=deadline-clock()
    if remaining<=0:
        raise TimeoutError('whole operation deadline expired before HTTP step')
    connection_type=http.client.HTTPSConnection if parsed.scheme=='https' else http.client.HTTPConnection
    connection=connection_type(parsed.hostname,parsed.port,timeout=remaining)
    request_headers={'User-Agent':'taid-whole-operation/1','Connection':'close',**headers}
    if content_type:
        request_headers['Content-Type']=content_type
    response=None
    try:
        connection.connect()
        transport=connection.sock
        remaining=deadline-clock()
        if remaining<=0:
            raise TimeoutError('whole operation deadline expired during connection')
        transport.settimeout(remaining)
        connection.request('POST' if data is not None else 'GET',parsed.path+('?' + parsed.query if parsed.query else ''),
                           body=data,headers=request_headers)
        remaining=deadline-clock()
        if remaining<=0:
            raise TimeoutError('whole operation deadline expired during request')
        transport.settimeout(remaining)
        response=connection.getresponse()
        body=bytearray()
        while True:
            remaining=deadline-clock()
            if remaining<=0:
                raise TimeoutError('whole operation deadline expired during response')
            transport.settimeout(remaining)
            chunk=response.read1(min(65536,MAX_RESPONSE_BYTES+1-len(body)))
            if not chunk:
                break
            body.extend(chunk)
            if len(body)>MAX_RESPONSE_BYTES:
                raise ValueError('response exceeds 1 MiB contract limit')
            if response.isclosed():
                break
        if response.length not in (None,0):
            raise http.client.IncompleteRead(bytes(body),response.length)
        return response.status,bytes(body)
    finally:
        if response is not None:
            response.close()
        connection.close()


def nonempty(value):
    return isinstance(value,str) and bool(value.strip())


def money(value):
    if not isinstance(value,dict) or value.get('currencyCode')!='USD':
        return False
    units,nanos=value.get('units'),value.get('nanos')
    if type(units) is int:
        valid_units=units>=0
    else:
        valid_units=isinstance(units,str) and units.isascii() and units.isdigit()
    return valid_units and type(nanos) is int and 0<=nanos<1000000000


def product(value):
    return (isinstance(value,dict) and value.get('id')==OTEL_PRODUCT
        and all(nonempty(value.get(k)) for k in ('name','description','picture'))
        and isinstance(value.get('categories'),list) and all(nonempty(k) for k in value['categories'])
        and money(value.get('priceUsd')))


def otel_verdict(operation, status, body, user_id):
    if status!=200:
        return False,'http_not_200'
    try:
        value=json.loads(body)
    except (ValueError,UnicodeError):
        return False,'invalid_json'
    if operation=='browse_product':
        valid=product(value)
    elif operation=='add_to_cart':
        valid=(isinstance(value,dict) and value.get('userId')==user_id
            and isinstance(value.get('items'),list) and len(value['items'])==1
            and isinstance(value['items'][0],dict) and value['items'][0].get('productId')==OTEL_PRODUCT
            and type(value['items'][0].get('quantity')) is int and value['items'][0]['quantity']==1)
    elif operation=='checkout':
        valid=(isinstance(value,dict) and nonempty(value.get('orderId')) and nonempty(value.get('shippingTrackingId'))
            and value.get('shippingAddress')==OTEL_PERSON['address'] and money(value.get('shippingCost'))
            and isinstance(value.get('items'),list) and len(value['items'])==1)
        if valid:
            ordered=value['items'][0]
            item=ordered.get('item') if isinstance(ordered,dict) else None
            valid=(isinstance(item,dict) and item.get('productId')==OTEL_PRODUCT
                and type(item.get('quantity')) is int and item['quantity']==1
                and product(item.get('product')) and money(ordered.get('cost')))
    else:
        raise ValueError('unknown OTel operation')
    return bool(valid),'' if valid else 'incomplete_or_wrong_'+operation


def execute(base_url, profile, operation, request_id, index, *,
            exchange=http_exchange, clock=time.monotonic, wall_clock=time.time):
    trace_id,trace_header,trace_value=make_trace_context(profile,request_id)
    headers={trace_header:trace_value,'X-Study-Request-ID':request_id}
    started_epoch=wall_clock();started=clock();deadline=started+DEADLINE_SECONDS
    user_id='taid-'+hashlib.sha256(request_id.encode()).hexdigest()
    branch='complete_'+operation
    steps=[];status=None;body=b'';error='';semantic_reason='';semantic_success=False;timed_out=False
    try:
        if profile=='deathstarbench_social_network':
            if operation=='compose_post':
                branch='with_media' if index%2 else 'text_only'
                payload=dict(username='username_0',user_id='0',text=f'taid pilot post {index}',
                    media_ids='["123456789012345678"]' if index%2 else '[]',media_types='["png"]' if index%2 else '[]',post_type='0')
                plan=[(operation,'/wrk2-api/post/compose',urlencode(payload).encode(),'application/x-www-form-urlencoded')]
            elif operation in ('read_home_timeline','read_user_timeline'):
                kind,user=('home','1') if operation=='read_home_timeline' else ('user','0')
                plan=[(operation,f'/wrk2-api/{kind}-timeline/read?user_id={user}&start=0&stop=10',None,None)]
            else:
                raise ValueError('unknown DeathStar operation')
        elif profile=='opentelemetry_demo':
            if operation not in ('browse_product','add_to_cart','checkout'):
                raise ValueError('unknown OTel operation')
            plan=[('browse_product',f'/api/products/{OTEL_PRODUCT}',None,None)]
            if operation in ('add_to_cart','checkout'):
                plan.append(('add_to_cart','/api/cart',json.dumps(dict(item=dict(productId=OTEL_PRODUCT,quantity=1),userId=user_id)).encode(),'application/json'))
            if operation=='checkout':
                plan.append(('checkout','/api/checkout',json.dumps(dict(OTEL_PERSON,userId=user_id)).encode(),'application/json'))
        else:
            raise ValueError('unknown profile')
        for step_operation,path,data,content_type in plan:
            if clock()>=deadline:
                raise TimeoutError('whole operation deadline expired before prerequisite')
            step_started=clock()
            record=dict(operation=step_operation,path=path,request_id=request_id,trace_id=trace_id,
                request_body_sha256=hashlib.sha256(data or b'').hexdigest(),remaining_budget_seconds=deadline-step_started,
                started_offset_seconds=step_started-started,status_code=None,semantic_success=False)
            steps.append(record)
            try:
                status,body=exchange(base_url+path,data=data,content_type=content_type,headers=headers,deadline=deadline,clock=clock)
                valid,reason=(otel_verdict(step_operation,status,body,user_id) if profile=='opentelemetry_demo'
                    else (lambda r:(r[0],r[2]))(validate_operation_response(profile,step_operation,status,body)))
                record.update(status_code=status,response_sha256=hashlib.sha256(body).hexdigest(),
                    response_bytes=len(body),response_base64=base64.b64encode(body).decode(),semantic_success=valid,semantic_reason=reason)
            finally:
                record['completed_offset_seconds']=clock()-started
            if clock()>deadline:
                raise TimeoutError('whole operation deadline exceeded by HTTP response or semantic validation')
            if not valid:
                semantic_reason='prerequisite_'+reason if step_operation!=operation else reason
                break
        else:
            semantic_success=True
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        timed_out=isinstance(exc,TimeoutError) or clock()>deadline
        semantic_reason='whole_operation_timeout' if timed_out else 'driver_or_transport_error'
        if steps:
            steps[-1]['error']=error
    completed=wall_clock();elapsed=clock()-started
    if elapsed>DEADLINE_SECONDS:
        semantic_success=False;timed_out=True;semantic_reason='whole_operation_timeout'
    return dict(profile=profile,operation=operation,request_id=request_id,trace_id=trace_id,trace_header=trace_header,
        started_at=datetime.fromtimestamp(started_epoch,timezone.utc).isoformat(),completed_at=datetime.fromtimestamp(completed,timezone.utc).isoformat(),
        branch_class=branch,status_code='' if status is None else status,immediate_success=status is not None and 200<=status<300,
        semantic_success=semantic_success,semantic_rule='whole_operation_contract_v1',semantic_reason=semantic_reason,
        timed_out=timed_out,latency_ms=elapsed*1000,response_bytes=len(body),response_sha256=hashlib.sha256(body).hexdigest(),
        error=error,deadline_seconds=DEADLINE_SECONDS,http_steps=steps,trace_presence_used_for_verdict=False,
        write_side_effect_audit='not_claimed_for_this_application',request_user_id=user_id if profile=='opentelemetry_demo' else None)
