from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from v4_confirmed_source_v3 import validate,SOURCE_RUN,SOURCE_HEAD


class SourceTests(unittest.TestCase):
    def test_only_the_unrelated_summary_failure_can_be_admitted(self):
        run=dict(id=SOURCE_RUN,head_sha=SOURCE_HEAD,path='.github/workflows/v4-confirmation-v2.yml',status='completed',run_attempt=1,conclusion='failure')
        jobs=[dict(name=f'{phase} (artificial-{i})',conclusion='success')for phase in ('acquire','graph','pmx','freeze','bounds','evaluate','primary')for i in range(18)]
        jobs.append(dict(name='analysis',conclusion='failure'))
        self.assertTrue(validate(run,jobs)['all_scientific_jobs_succeeded'])
        for phase in ('acquire','graph','pmx','freeze','bounds','evaluate','primary'):
            changed=deepcopy(jobs);next(j for j in changed if j['name'].startswith(phase+' ('))['conclusion']='failure'
            with self.assertRaises(ValueError):validate(run,changed)
        with self.assertRaises(ValueError):validate(run,jobs[1:])
        with self.assertRaises(ValueError):validate(dict(run,head_sha='changed'),jobs)
