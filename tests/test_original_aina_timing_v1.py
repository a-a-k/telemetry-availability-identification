import importlib.util
from pathlib import Path
import sys
import unittest

spec=importlib.util.spec_from_file_location('aina_timing',Path('scripts/audit_original_aina_timing_v1.py'))
timing=importlib.util.module_from_spec(spec)
sys.path.insert(0,str(Path('scripts').resolve()))
try:
    spec.loader.exec_module(timing)
finally:
    sys.path.pop(0)


class AinaTimingTests(unittest.TestCase):
    def test_only_explicit_read_timeout_gets_a_duration_bound(self):
        self.assertEqual(timing.error_category('HTTPConnectionPool: Read timed out. (read timeout=6)'),
                         'read_timeout_declared_6s')
        for text in ['Read timed out. (read timeout=0.6)','Read timed out. (read timeout=60)','timeout unknown']:
            self.assertEqual(timing.error_category(text),'other_timeout_unquantified')

    def test_strict_thresholds_do_not_count_fast_http_failures(self):
        slow={'status':'fail','error':'Read timed out. (read timeout=6)'}
        fast={'status':'fail','error':'500 Server Error: Internal Server Error'}
        self.assertFalse(timing.window_timing([slow]*10+[fast]*90)['exceeds_declared_60s_hold'])
        result=timing.window_timing([slow]*11+[fast]*89)
        self.assertEqual(result['conditional_duration_lower_bound_s'],66)
        self.assertTrue(result['exceeds_declared_60s_hold'])
        self.assertFalse(timing.window_timing([slow]*7)['exceeds_nominal_45s_remaining'])
        self.assertTrue(timing.window_timing([slow]*8)['exceeds_nominal_45s_remaining'])


if __name__=='__main__':
    unittest.main()
