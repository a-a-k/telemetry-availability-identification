from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import benchmark_v3_pipeline_v1 as bench


class PipelineBenchmarkControls(unittest.TestCase):
    def fixture(self):
        rows=[dict(request_id='request-1',trace_id='a'*32,period='calibration',
                   operation='op',semantic_success=False,timed_out=True,start_ns=100,duration_ns=200),
              dict(request_id='request-2',trace_id='b'*32,period='calibration',
                   operation='op',semantic_success=True,timed_out=False,start_ns=400,duration_ns=50)]
        spans=[dict(trace_id='a'*32,span_id='c'*16,parent_id='',start_us=0,duration_us=1,error_tag=True),
               dict(trace_id='a'*32,span_id='d'*16,parent_id='c'*16,start_us=0,duration_us=1,error_tag=False)]
        return rows,dict(calibration_only=True,selected_trace_ids=['a'*32,'b'*32],spans={'a'*32:spans})

    def test_one_copy_exact_values_and_no_mutation(self):
        rows,native=self.fixture(); original=deepcopy((rows,native))
        copied,traces=bench.replicate(rows,native,1)
        self.assertEqual((copied,traces),original)
        self.assertEqual((rows,native),original)

    def test_copy_preserves_failure_missingness_timing_and_parent_edges(self):
        rows,native=self.fixture()
        copied,traces=bench.replicate(rows,native,4)
        self.assertEqual(len(copied),8)
        self.assertEqual(len(traces['spans']),4)
        self.assertEqual(sum(r['timed_out'] for r in copied),4)
        for index in range(4):
            a,b=copied[2*index:2*index+2]
            self.assertNotIn(b['trace_id'],traces['spans'])
            parent,child=traces['spans'][a['trace_id']]
            self.assertEqual(parent['trace_id'],a['trace_id'])
            self.assertEqual(child['parent_id'],parent['span_id'])
            self.assertEqual(a['duration_ns'],rows[0]['duration_ns'])
            self.assertTrue(parent['error_tag'])
            if index:self.assertNotEqual(parent['span_id'],'c'*16)

    def test_invalid_volume_and_duplicate_source_rejected(self):
        rows,native=self.fixture()
        for volume in (0,3,True):
            with self.assertRaises(ValueError):bench.replicate(rows,native,volume)
        with self.assertRaises(ValueError):bench.replicate(rows+rows,native,2)

    def test_forecast_invariance_distinguishes_zero_bounds_and_missing(self):
        expected={'op':{'Gstar':dict(status='ok',probability=0.0)}}
        bench.check_forecasts(expected,expected)
        for forecast in (dict(status='ok',probability=None),dict(status='unsupported',probability=None),
                         dict(status='ok',probability=0.01)):
            with self.assertRaises(ValueError):bench.check_forecasts({'op':{'Gstar':forecast}},expected)
        bound={'op':{'Gstar':dict(status='unsupported',probability=None,identified_lower=0,identified_upper=.5)}}
        changed=deepcopy(bound);changed['op']['Gstar']['identified_upper']=.6
        with self.assertRaises(ValueError):bench.check_forecasts(changed,bound)


if __name__=='__main__':unittest.main()
