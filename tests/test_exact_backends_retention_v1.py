"""Negative controls for compact evidence and the fixed measurement census."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from retain_v3_exact_backends_v1 import validate_compact
from test_graph_execution_bdd_v1 import tiny_model
from telemetry_availability.graph_execution_model_v1 import solve


class RetentionTests(unittest.TestCase):
    def setUp(self):
        ex=solve(tiny_model())['estimates']
        self.config=dict(profiles=['control'],expected_models=[1],expected_original_absences=[0],
                         methods=['control'],technical_rounds=1,phases=['initial'])
        self.result=dict(profile='control',cases=[dict(case_id='tiny',expected=dict(initial=ex))],absent=[],
                         records=[dict(case_id='tiny',method='control',round=0,phase='initial',status='qualified',
                                       estimates=deepcopy(ex),total_ns=2,query_including_update_ns=1,key_check_ns=0)],
                         resources=[dict(case_id='tiny',method='control',round=0)],complete_census=True,qualified=True)

    def test_valid_and_explicit_failure(self):
        validate_compact(self.result,self.config)
        row=self.result['records'][0];row.update(status='failed',error='stream_timeout')
        self.result['qualified']=False
        validate_compact(self.result,self.config)

    def test_rejects_full_payload_at_any_depth(self):
        self.result['records'][0]['stats']={'nested':{'model':{}}}
        with self.assertRaisesRegex(ValueError,'full model'):validate_compact(self.result,self.config)

    def test_rejects_changed_exact_answer(self):
        self.result['records'][0]['estimates']['execution']['upper_exact']='99/100'
        with self.assertRaisesRegex(ValueError,'exact reference'):validate_compact(self.result,self.config)

    def test_rejects_duplicate_or_missing_measurement(self):
        self.result['records']*=2
        with self.assertRaisesRegex(ValueError,'census'):validate_compact(self.result,self.config)

    def test_rejects_foreign_resource_identity(self):
        self.result['resources'][0]['method']='foreign'
        with self.assertRaisesRegex(ValueError,'resource census'):validate_compact(self.result,self.config)


if __name__=='__main__':unittest.main()
