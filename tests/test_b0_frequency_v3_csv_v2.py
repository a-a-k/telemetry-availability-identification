from copy import deepcopy
import unittest
from telemetry_availability.b0_frequency_v3 import identify as strict_identify
from telemetry_availability.b0_frequency_v3_csv_v2 import identify, decode_outcome


class B0CsvV2Tests(unittest.TestCase):
    def test_csv_false_is_false_and_true_denominators_match_original_booleans(self):
        rows=[{'request_id':str(i),'trace_id':str(i),'operation':'a','period':'calibration',
               'started_at':'2026-01-01T00:00:00Z','completed_at':'2026-01-01T00:00:01Z',
               'semantic_success':i==0,'timed_out':i==2} for i in range(3)]
        csv=deepcopy(rows)
        for row in csv:
            for field in ('semantic_success','timed_out'):row[field]=str(row[field])
        expected=strict_identify(rows,['a','b'])
        actual=identify(csv,['a','b'])
        self.assertEqual(actual['forecasts'],expected['forecasts'])
        self.assertEqual(actual['external_attempts'],expected['external_attempts'])
        self.assertFalse(decode_outcome('False'))
        self.assertTrue(decode_outcome('true'))

    def test_unknown_numeric_empty_or_null_tokens_are_not_coerced(self):
        for value in (1,0,'1','0','',None,'yes','False ',' True'):
            with self.assertRaises(ValueError):decode_outcome(value)


if __name__=='__main__':unittest.main()
