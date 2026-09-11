from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from summarize_v3_pipeline_benchmark_v1 import measurement,stats


class PipelineCostAccountingControls(unittest.TestCase):
    def test_sequential_cpu_sum_memory_max_and_outer_wall(self):
        record=dict(wall_seconds=13,stages={
            'build':dict(wall_seconds=10,resource=dict(user_seconds=8,system_seconds=2,maximum_rss_bytes=100*2**20)),
            'replay':dict(wall_seconds=2,resource=dict(user_seconds=1,system_seconds=.5,maximum_rss_bytes=40*2**20))})
        result=measurement(record)
        self.assertEqual(result['wall_seconds'],13)
        self.assertEqual(result['summed_timed_command_cpu_seconds'],11.5)
        self.assertEqual(result['largest_process_peak_rss_mib'],100)
        self.assertEqual(result['outer_minus_command_wall_seconds'],1)

    def test_missing_resources_are_not_zero(self):
        result=measurement(dict(wall_seconds=3,stages={'run':dict(wall_seconds=2,resource=None)}))
        self.assertIsNone(result['summed_timed_command_cpu_seconds'])
        self.assertIsNone(result['largest_process_peak_rss_mib'])
        self.assertIsNone(stats([],'ratio')['ratio_median'])


if __name__=='__main__':unittest.main()
