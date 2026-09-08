from copy import deepcopy

import pytest

from telemetry_availability.petclinic_contract import response_verdict


@pytest.fixture
def fixture():
    visit = dict(id=1, petId=7, date='2010-03-04', description='rabies shot')
    owner = dict(id=6, firstName='Jean', lastName='Coleman', pets=[dict(id=7, name='Samantha')])
    details = deepcopy(owner)
    details['pets'][0]['visits'] = [visit]
    return dict(owners=[owner], details=details, vets=[dict(id=1, firstName='James', lastName='Carter', specialties=[])])


@pytest.mark.parametrize('operation,key', [('list_owners', 'owners'), ('owner_details_with_visits', 'details'), ('list_vets', 'vets')])
def test_read_requires_complete_timely_semantics(operation, key, fixture):
    assert response_verdict(operation, 200, fixture[key], .1, fixture)['semantic_success']
    assert not response_verdict(operation, 503, fixture[key], .1, fixture)['semantic_success']
    assert not response_verdict(operation, 200, fixture[key], 2.01, fixture)['semantic_success']


def test_success_status_and_missing_span_errors_cannot_hide_empty_visits(fixture):
    payload = deepcopy(fixture['details'])
    payload['pets'][0]['visits'] = []
    result = response_verdict('owner_details_with_visits', 200, payload, .1, fixture)
    assert not result['semantic_success']
    assert result['semantic_reason'] == 'incomplete_or_duplicate_list'


def test_partial_owner_or_duplicate_vet_is_not_success(fixture):
    assert not response_verdict('list_owners', 200, [], .1, fixture)['semantic_success']
    duplicated = fixture['vets']*2
    assert not response_verdict('list_vets', 200, duplicated, .1, fixture)['semantic_success']


@pytest.mark.parametrize('status,elapsed,count,expected', [(201,.1,1,True), (201,.1,0,False),
    (201,.1,2,False), (201,2.01,1,False), (None,2.01,1,False), (503,.1,1,False)])
def test_write_requires_timely_ack_and_exactly_one_persisted_marker(status, elapsed, count, expected, fixture):
    payload = dict(id=5, petId=1, date='2026-09-01', description='study-marker')
    persisted = [dict(payload, id=5+i) for i in range(count)]
    result = response_verdict('create_visit', status, payload, elapsed, fixture, 'study-marker', persisted)
    assert result['semantic_success'] is expected
    assert result['write_found_without_timely_success'] is (count > 0 and not expected)


def test_wrong_acknowledged_id_and_pending_audit_are_failures(fixture):
    payload = dict(id=5, petId=1, date='2026-09-01', description='study-marker')
    assert response_verdict('create_visit', 201, payload, .1, fixture, 'study-marker')['semantic_reason'] == 'persistence_audit_pending'
    assert not response_verdict('create_visit', 201, payload, .1, fixture, 'study-marker', [dict(payload, id=6)])['semantic_success']
