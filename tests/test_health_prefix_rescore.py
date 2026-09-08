from types import SimpleNamespace
import unittest

from telemetry_availability.health_prefix_rescore import decode_evaluator
from telemetry_availability.live_validation_analysis import _evaluation_views


class PrefixWindowCorrectionTests(unittest.TestCase):
    def test_window_correction_preserves_every_business_outcome(self):
        meta=dict(profile='opentelemetry_demo',placement='split',failure_law='NCD',repetition=0)
        requests=[dict(operation='checkout',started_at=f'2026-09-08T00:00:0{i}+00:00',
                       semantic_success='false' if i==2 else 'true') for i in range(6)]
        health=[]
        for i in (0,2,4):
            row=dict(observed_at=f'2026-09-08T00:00:0{i}+00:00',elapsed_seconds=str(i))
            for rep in ('a','b'):
                for k,v in dict(observed='true',running='true',paused='false',network_count='1',backend_status='UP',
                                backend_check_status='* L4OK' if i==2 else 'L4OK').items():
                    row[f'replica_{rep}_{k}']=v
            health.append(row)
        old,new=decode_evaluator(meta,requests,health)
        config=SimpleNamespace(transition_guard_seconds_each_side=1,block_length_seconds=10,
                               sensitivity_block_length_seconds=20)
        a={k:r for k,n,r in _evaluation_views(old,config)}
        b={k:r for k,n,r in _evaluation_views(new,config)}
        self.assertEqual(old.test_requests,new.test_requests)
        self.assertEqual(a['all_sequence'],b['all_sequence'])
        self.assertEqual(sum(r.success for r in b['all_sequence']),5)
        self.assertLess(len(a['stable']),len(b['stable']))
        self.assertEqual(len(b['stable']),6)
        self.assertFalse(old.learner_requests or new.health)


if __name__=='__main__':unittest.main()
