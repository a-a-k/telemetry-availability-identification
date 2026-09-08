from copy import deepcopy
import unittest

from telemetry_availability.petclinic_contract_v2 import adapt_fixture, birth_date, response_verdict


class PetclinicDTOTests(unittest.TestCase):
    def fixture(self):
        pet = dict(id=7, name='Samantha', birthDate='1995-09-04', type=dict(id=1, name='cat'))
        owner = dict(id=6, firstName='Jean', pets=[pet])
        details = deepcopy(owner)
        details['pets'][0]['visits'] = [dict(id=1, petId=7, date='2010-03-04', description='rabies shot')]
        return adapt_fixture(dict(owners=[owner], details=details, vets=[]))

    def test_public_dto_and_utc_midnight_date_are_supported(self):
        f = self.fixture()
        payload = deepcopy(f['details'])
        payload['pets'][0]['birthDate'] = '1995-09-04T00:00:00.000Z'
        self.assertEqual(payload['pets'][0]['type'], dict(name='cat'))
        self.assertTrue(response_verdict('owner_details_with_visits',200,payload,.1,f)['semantic_success'])
        self.assertTrue(response_verdict('list_owners',200,f['owners'],.1,f)['semantic_success'])

    def test_birth_date_rejects_wrong_day_time_and_offset(self):
        for value in ('1995-09-04T01:00:00.000Z','1995-09-04T00:00:00+03:00','1995-02-30',1995,None):
            with self.subTest(value=value), self.assertRaises(ValueError): birth_date(value)
        f = self.fixture()
        payload = deepcopy(f['details'])
        payload['pets'][0]['birthDate'] = '1995-09-05T00:00:00.000Z'
        self.assertFalse(response_verdict('owner_details_with_visits',200,payload,.1,f)['semantic_success'])

    def test_dto_correction_does_not_accept_missing_visits_or_wrong_type(self):
        f = self.fixture()
        for change in ('visits','type'):
            payload = deepcopy(f['details'])
            payload['pets'][0][change] = [] if change == 'visits' else dict(name='dog')
            self.assertFalse(response_verdict('owner_details_with_visits',200,payload,.1,f)['semantic_success'])

    def test_customers_endpoint_still_requires_type_id(self):
        f = self.fixture()
        payload = deepcopy(f['owners'])
        del payload[0]['pets'][0]['type']['id']
        self.assertFalse(response_verdict('list_owners',200,payload,.1,f)['semantic_success'])

    def test_write_side_effect_still_does_not_repair_timeout_or_duplicate(self):
        f = self.fixture()
        payload=dict(id=9,petId=1,date='2026-09-01',description='study-marker')
        for elapsed, persisted in [(2.1,[payload]),(.1,[payload,dict(payload,id=10)])]:
            result=response_verdict('create_visit',201,payload,elapsed,f,'study-marker',persisted)
            self.assertFalse(result['semantic_success'])
            self.assertTrue(result['write_found_without_timely_success'])
