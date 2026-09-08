from copy import deepcopy

import unittest

from telemetry_availability.petclinic_contract import response_verdict


def fixture():
    visit = dict(id=1, petId=7, date='2010-03-04', description='rabies shot')
    owner = dict(id=6, firstName='Jean', lastName='Coleman', pets=[dict(id=7, name='Samantha')])
    details = deepcopy(owner)
    details['pets'][0]['visits'] = [visit]
    return dict(owners=[owner], details=details, vets=[dict(id=1, firstName='James', lastName='Carter', specialties=[])])


class PetclinicContractTests(unittest.TestCase):
    def test_complete_read_scenarios(self):
        f = fixture()
        for operation, key in [('list_owners', 'owners'), ('owner_details_with_visits', 'details'), ('list_vets', 'vets')]:
            with self.subTest(operation=operation):
                self.assertTrue(response_verdict(operation, 200, f[key], .1, f)['semantic_success'])
                self.assertFalse(response_verdict(operation, 503, f[key], .1, f)['semantic_success'])
                self.assertFalse(response_verdict(operation, 200, f[key], 2.01, f)['semantic_success'])

    def test_empty_visits_fallback_is_not_success(self):
        f = fixture()
        payload = deepcopy(f['details'])
        payload['pets'][0]['visits'] = []
        result = response_verdict('owner_details_with_visits', 200, payload, .1, f)
        self.assertFalse(result['semantic_success'])
        self.assertEqual(result['semantic_reason'], 'incomplete_or_duplicate_list')

    def test_partial_and_duplicate_lists(self):
        f = fixture()
        self.assertFalse(response_verdict('list_owners', 200, [], .1, f)['semantic_success'])
        self.assertFalse(response_verdict('list_vets', 200, f['vets']*2, .1, f)['semantic_success'])

    def test_six_write_ack_and_persistence_scenarios(self):
        f = fixture()
        payload = dict(id=5, petId=1, date='2026-09-01', description='study-marker')
        for status, elapsed, count, expected in [(201,.1,1,True),(201,.1,0,False),(201,.1,2,False),(201,2.01,1,False),(None,2.01,1,False),(503,.1,1,False)]:
            with self.subTest(status=status, elapsed=elapsed, count=count):
                persisted = [dict(payload,id=5+i) for i in range(count)]
                result = response_verdict('create_visit',status,payload,elapsed,f,'study-marker',persisted)
                self.assertIs(result['semantic_success'],expected)
                self.assertIs(result['write_found_without_timely_success'],count > 0 and not expected)

    def test_pending_audit_and_wrong_ack_id(self):
        f = fixture()
        payload = dict(id=5,petId=1,date='2026-09-01',description='study-marker')
        self.assertEqual(response_verdict('create_visit',201,payload,.1,f,'study-marker')['semantic_reason'],'persistence_audit_pending')
        self.assertFalse(response_verdict('create_visit',201,payload,.1,f,'study-marker',[dict(payload,id=6)])['semantic_success'])
