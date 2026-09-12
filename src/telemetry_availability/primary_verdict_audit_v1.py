"""Independent, label-free checks of saved external protocol evidence.

No graph coordinates, inferred model or stored semantic_success are inputs to
the acceptance functions. Persistence is never inferred from an HTTP response.
"""
import base64
from datetime import date
from hashlib import sha256
import json
import re


def nonempty(value): return isinstance(value, str) and bool(value.strip())


def usd(value):
    if not isinstance(value, dict) or value.get('currencyCode') != 'USD': return False
    units = value.get('units'); nanos = value.get('nanos')
    valid_units = type(units) is int and units >= 0 or (
        isinstance(units, str) and units.isascii() and units.isdigit())
    return bool(valid_units and type(nanos) is int and 0 <= nanos < 10**9)


def product_record(value, product_id):
    return (isinstance(value, dict) and value.get('id') == product_id
        and all(nonempty(value.get(k)) for k in ('name','description','picture'))
        and isinstance(value.get('categories'), list) and all(nonempty(k) for k in value['categories'])
        and usd(value.get('priceUsd')))


def accept_response(profile, operation, status, body, user_id, product_id, address):
    if profile == 'deathstarbench_social_network':
        if type(status) is not int or not 200 <= status < 300: return False
        if operation == 'compose_post': return b'Successfully upload post' in body
        if operation not in ('read_home_timeline','read_user_timeline'): raise ValueError('unknown DS operation')
        try: payload = json.loads(body)
        except (ValueError, UnicodeError): return False
        return payload == {} or isinstance(payload, list) and all(
            isinstance(p, dict) and isinstance(p.get('post_id'), str) and isinstance(p.get('text'), str) for p in payload)
    if profile != 'opentelemetry_demo': raise ValueError('unknown profile')
    if status != 200: return False
    try: payload = json.loads(body)
    except (ValueError, UnicodeError): return False
    if operation == 'browse_product': return product_record(payload, product_id)
    if not isinstance(payload, dict): return False
    items = payload.get('items')
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict): return False
    if operation == 'add_to_cart':
        item = items[0]
        return (payload.get('userId') == user_id and item.get('productId') == product_id
            and type(item.get('quantity')) is int and item['quantity'] == 1)
    if operation != 'checkout': raise ValueError('unknown OTel operation')
    item = items[0].get('item')
    return (nonempty(payload.get('orderId')) and nonempty(payload.get('shippingTrackingId'))
        and payload.get('shippingAddress') == address and usd(payload.get('shippingCost'))
        and isinstance(item, dict) and item.get('productId') == product_id
        and type(item.get('quantity')) is int and item['quantity'] == 1
        and product_record(item.get('product'), product_id) and usd(items[0].get('cost')))


def http_evidence(request, product_id, address):
    profile = request['profile']; op = request['operation']; steps = request['http_steps']
    plan = [op] if profile == 'deathstarbench_social_network' else {
        'browse_product':['browse_product'], 'add_to_cart':['browse_product','add_to_cart'],
        'checkout':['browse_product','add_to_cart','checkout']}[op]
    if [s['operation'] for s in steps] != plan[:len(steps)] or len(steps) > len(plan):
        raise ValueError('primary HTTP sequence differs from operation contract')
    verdicts = []; hashes = 0
    for step in steps:
        if 'response_base64' not in step:
            verdicts.append(False); continue
        body = base64.b64decode(step['response_base64'], validate=True)
        if sha256(body).hexdigest() != step['response_sha256'] or len(body) != step['response_bytes']:
            raise ValueError('primary HTTP response hash/length differs')
        hashes += 1
        verdicts.append(bool(accept_response(profile, step['operation'], step['status_code'], body,
            request.get('request_user_id'), product_id, address)))
    accepted = (len(steps) == len(plan) and all(verdicts) and not request['error']
                and request['latency_ms'] <= 2000 and all(s['completed_offset_seconds'] <= 2 for s in steps))
    return dict(outcome=bool(accepted), verification='whole_http_contract_from_primary_response_bytes',
        checked_response_hashes=hashes, persistence_claimed=False)


def matches_fixture(actual, expected, field=''):
    if field == 'birthDate':
        if not isinstance(actual, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T00:00:00(?:\.0+)?(?:Z|\+00:00))?', actual): return False
        try: return date.fromisoformat(actual[:10]) == date.fromisoformat(expected[:10])
        except ValueError: return False
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(expected) <= set(actual) and all(matches_fixture(actual[k], v, k) for k,v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected): return False
        if any(not isinstance(r, dict) or type(r.get('id')) is not int for r in actual): return False
        indexed = {r['id']:r for r in actual}
        return len(indexed) == len(actual) and all(r['id'] in indexed and matches_fixture(indexed[r['id']], r) for r in expected)
    return type(actual) is type(expected) and actual == expected


def petclinic_evidence(request, fixture):
    op = request['operation']; status = request['status_code']; payload = request['payload']
    timely = request['latency_ms'] <= 2000
    if op != 'create_visit':
        key = {'list_owners':'owners','owner_details_with_visits':'details','list_vets':'vets'}[op]
        outcome = status == 200 and timely and matches_fixture(payload, fixture[key])
        return dict(outcome=bool(outcome), verification='parsed_primary_payload_against_pinned_SQL_fixture',
            original_response_bytes_retained=False, persistence_claimed=False)
    ack = (status == 201 and timely and isinstance(payload, dict) and type(payload.get('id')) is int
        and payload['id'] > 0 and matches_fixture(payload,
            dict(id=payload['id'], petId=1, date='2026-09-01', description=request['marker'])))
    # A count emitted by finalize_write is derived evidence. It cannot substitute
    # for the original SELECT rows proving marker/id/pet/date and uniqueness.
    return dict(outcome=False if not ack else None,
        verification='write_failure_verified' if not ack else 'ack_verified_persistence_primary_rows_not_retained',
        acknowledged_response_valid=bool(ack), original_response_bytes_retained=False,
        persistence_independently_verified=False)
