"""The frozen Petclinic HTTP contract with original response bytes retained.

Only the returned evidence gains response_base64; request, timeout and business
verdict code are copied verbatim from petclinic_contract_v2.execute.
"""
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from .petclinic_contract_v2 import CONFIG, response_verdict


def execute(base_url, operation, request_id, fixture, config=None):
    config = config or json.loads(CONFIG.read_text())
    trace_id = hashlib.sha256(request_id.encode()).hexdigest()[:32]
    parent_id = hashlib.sha256(('client:'+request_id).encode()).hexdigest()[:16]
    marker = 'study-'+hashlib.sha256(request_id.encode()).hexdigest()
    method, path, data = 'GET', {'list_owners': '/api/customer/owners',
        'owner_details_with_visits': '/api/gateway/owners/6', 'list_vets': '/api/vet/vets',
        'create_visit': '/api/visit/owners/1/pets/1/visits'}[operation], None
    if operation == 'create_visit':
        method, data = 'POST', json.dumps(dict(date=config['write_date'], description=marker)).encode()
    request = urllib.request.Request(base_url+path, data=data, method=method, headers={
        'traceparent': f'00-{trace_id}-{parent_id}-01', 'X-Study-Request-Id': request_id,
        'Content-Type': 'application/json', 'Connection': 'close'})
    started, epoch = time.monotonic(), time.time()
    body, status, error, payload = b'', None, '', None
    try:
        with urllib.request.urlopen(request, timeout=config['operation_deadline_seconds']) as response:
            status = response.status
            body = response.read(config['response_limit_bytes']+1)
        if len(body) > config['response_limit_bytes']:
            raise ValueError('response_exceeds_declared_limit')
        payload = json.loads(body)
    except urllib.error.HTTPError as exc:
        status, error = exc.code, str(exc)
        body = exc.read(config['response_limit_bytes']+1)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    elapsed = time.monotonic()-started
    verdict = response_verdict(operation, status, payload, elapsed, fixture, marker=marker,
                               deadline=config['operation_deadline_seconds'])
    return dict(request_id=request_id, trace_id=trace_id, client_parent_id=parent_id,
                operation=operation, method=method, path=path, marker=marker if operation == 'create_visit' else '',
                started_epoch=epoch, completed_epoch=time.time(), latency_ms=elapsed*1000,
                status_code=status, error=error, payload=payload, response_sha256=hashlib.sha256(body).hexdigest(),
                response_bytes=len(body), response_base64=base64.b64encode(body).decode('ascii'), **verdict)
