"""V2 Petclinic DTO/date contract; preserves v1 evidence and complete outcome rules."""
import ast
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT/'configs/petclinic_runtime_v2.json'


def fixture_from_source(source):
    """Read immutable upstream SQL seeds; never learn expected payloads from live responses."""
    tables, hashes = {}, {}
    for service in ('customers', 'visits', 'vets'):
        path = source/f'spring-petclinic-{service}-service/src/main/resources/db/mysql/data.sql'
        hashes[path.relative_to(source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        for table, fields in re.findall(r'INSERT IGNORE INTO (\w+) VALUES \((.*?)\);', path.read_text()):
            tables.setdefault(table, []).append(ast.literal_eval('('+fields+',)'))
    types = {i: dict(id=i, name=name) for i, name in tables['types']}
    owners = []
    for owner in tables['owners']:
        row = dict(zip(('id', 'firstName', 'lastName', 'address', 'city', 'telephone'), owner))
        row['pets'] = [dict(id=i, name=name, birthDate=date, type=types[kind])
                       for i, name, date, kind, oid in tables['pets'] if oid == row['id']]
        owners.append(row)
    details = json.loads(json.dumps(next(r for r in owners if r['id'] == 6)))
    for pet in details['pets']:
        pet['visits'] = [dict(id=i, petId=pid, date=date, description=description)
                         for i, pid, date, description in tables['visits'] if pid == pet['id']]
    assert len(details['pets']) == 2 and sum(len(p['visits']) for p in details['pets']) == 4
    specialties = {i: dict(id=i, name=name) for i, name in tables['specialties']}
    vets = [dict(id=i, firstName=first, lastName=last,
                 specialties=[specialties[sid] for vid, sid in tables['vet_specialties'] if vid == i])
            for i, first, last in tables['vets']]
    return dict(owners=owners, details=details, vets=vets, seed_sha256=hashes)


def adapt_fixture(fixture):
    result = json.loads(json.dumps(fixture))
    # The pinned Gateway PetType record contains name only; Customers' type entity retains its ID.
    for pet in result['details']['pets']:
        pet['type'] = {'name': pet['type']['name']}
    return result


def birth_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T00:00:00(?:\.0+)?(?:Z|\+00:00))?', value):
        raise ValueError('invalid_date_or_nonmidnight_timestamp')
    from datetime import date
    return date.fromisoformat(value[:10]).isoformat()


def canonical(actual, expected):
    """Compare all declared semantic fields, accepting only list order and extra metadata."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or not set(expected) <= set(actual):
            raise ValueError('missing_object_fields')
        return {key: canonical(birth_date(actual[key]), birth_date(value)) if key == 'birthDate'
                else canonical(actual[key], value) for key, value in expected.items()}
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError('incomplete_or_duplicate_list')
        # Every declared entity list has stable IDs. Duplicate IDs cannot match a set.
        ids = [row['id'] for row in actual]
        if len(set(ids)) != len(ids):
            raise ValueError('duplicate_entity_id')
        actual_by_id = {row['id']: row for row in actual}
        return [canonical(actual_by_id[row['id']], row) for row in sorted(expected, key=lambda r: r['id'])]
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError('semantic_value_mismatch')
    return actual


def response_verdict(operation, status, payload, elapsed, fixture, marker='', persisted=None, deadline=2.0):
    """One whole-operation verdict; a late persisted write remains a failed request."""
    result = dict(semantic_success=False, timed_out=elapsed > deadline,
                  semantic_reason='whole_operation_deadline_exceeded' if elapsed > deadline else '',
                  write_audit_required=operation == 'create_visit', write_found_without_timely_success=False)
    timely = elapsed <= deadline
    try:
        if operation == 'create_visit':
            exact = (isinstance(persisted, list) and len(persisted) == 1
                     and persisted[0]['description'] == marker and persisted[0]['petId'] == 1
                     and persisted[0]['date'] == '2026-09-01')
            result['persisted_marker_count'] = None if persisted is None else len(persisted)
            result['write_found_without_timely_success'] = bool(persisted) and not (timely and status == 201)
            if status != 201:
                raise ValueError('write_without_created_acknowledgment')
            expected = dict(id=payload['id'], petId=1, date='2026-09-01', description=marker)
            if type(payload['id']) is not int or payload['id'] < 1:
                raise ValueError('invalid_created_id')
            canonical(payload, expected)
            if persisted is None:
                raise ValueError('persistence_audit_pending')
            if not exact or persisted[0]['id'] != payload['id']:
                raise ValueError('not_persisted_exactly_once_with_acknowledged_id')
        else:
            if status != 200:
                raise ValueError('read_without_ok_status')
            key = {'list_owners': 'owners', 'owner_details_with_visits': 'details', 'list_vets': 'vets'}[operation]
            canonical(payload, fixture[key])
        result.update(semantic_success=timely, semantic_reason='complete_timely_semantic_result' if timely
                      else 'whole_operation_deadline_exceeded')
    except (ValueError, KeyError, TypeError) as exc:
        if timely:
            result['semantic_reason'] = str(exc)
    if operation == 'create_visit':
        result['write_found_without_timely_success'] = bool(persisted) and not result['semantic_success']
    return result


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
                response_bytes=len(body), **verdict)


def finalize_write(row, persisted, fixture, deadline=2.0):
    assert row['operation'] == 'create_visit'
    row.update(response_verdict(row['operation'], row['status_code'], row['payload'], row['latency_ms']/1000,
                               fixture, marker=row['marker'], persisted=persisted, deadline=deadline))
