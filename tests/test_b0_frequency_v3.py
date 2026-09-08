from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from telemetry_availability.b0_frequency_v3 import identify, fit
from telemetry_availability.v3_primary_projection import VERSION, FILES
from telemetry_availability.v3_graph_input_inventory import ReadBoundary


def requests():
    return [{'request_id':str(i),'trace_id':str(i),'operation':'a','period':'calibration',
             'started_at':'2026-01-01T00:00:00Z','completed_at':'2026-01-01T00:00:01Z',
             'semantic_success':i==0,'timed_out':i==2} for i in range(3)]


class B0FrequencyV3Tests(unittest.TestCase):
    def test_all_attempt_denominator_no_prior_and_empty_operation(self):
        result=identify(requests(),['a','b'])
        self.assertEqual(result['forecasts']['a']['exact_fraction'],'1/3')
        self.assertEqual(result['forecasts']['a']['probability'],1/3)
        self.assertEqual(result['forecasts']['a']['timeouts'],1)
        self.assertIsNone(result['forecasts']['b']['probability'])
        all_failed=requests();all_failed[0]['semantic_success']=False
        self.assertEqual(identify(all_failed,['a'])['forecasts']['a']['probability'],0)

    def test_duplicates_test_data_and_invalid_outcomes_rejected(self):
        cases=[]
        base=requests();cases.append(base+[base[0]])
        data=deepcopy(base);data[0]['period']='test';cases.append(data)
        data=deepcopy(base);data[0]['semantic_success']=1;cases.append(data)
        data=deepcopy(base);data[0]['timed_out']=True;cases.append(data)
        data=deepcopy(base);data[0]['docker_state']='running';cases.append(data)
        for data in cases:
            with self.assertRaises(AssertionError):identify(data,['a'])

    def test_only_request_and_seal_files_read_during_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();out=root/'out';out.mkdir()
            payload=json.dumps(requests()).encode();(root/'requests.json').write_bytes(payload)
            seal={'version':VERSION,'files':{name:'not-provided' for name in FILES}}
            seal['files']['requests.json']=sha256(payload).hexdigest()
            (root/'seal.json').write_text(json.dumps(seal),encoding='utf-8')
            (root/'test-outcomes.json').write_text('[]',encoding='utf-8')
            boundary=ReadBoundary(root,out);boundary.allowed={root/'requests.json',root/'seal.json'}
            sys.addaudithook(boundary.hook)
            try:
                model=fit(root,['a'])
                self.assertEqual(model['forecasts']['a']['probability'],1/3)
                self.assertEqual(boundary.reads,{str(root/'requests.json'),str(root/'seal.json')})
                with self.assertRaises(PermissionError):(root/'test-outcomes.json').read_bytes()
            finally:boundary.active=False
            (root/'requests.json').write_bytes(b'[]')
            with self.assertRaises(AssertionError):fit(root,['a'])


if __name__=='__main__':unittest.main()
