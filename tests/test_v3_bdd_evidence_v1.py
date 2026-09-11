"""Compact-boundary and archive-source negative controls, artificial metadata."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from retain_v3_bdd_compact_v1 import check_compact
import archive_v3_bdd_evidence_v1 as archive


class BDDEvidenceTests(unittest.TestCase):
    def test_compact_census_and_payload_boundary(self):
        config = dict(profiles=['synthetic'], expected_models=[1], expected_cases=[1],
                      methods=['specialized','controls_first','structural','sift_once'], technical_rounds=3, warm_queries=3)
        digest = sha256((json.dumps({},sort_keys=True)+'\n').encode()).hexdigest()
        result = dict(profile='synthetic', cases=[dict(case_id='tiny',estimates={})], absent=[], qualified=True,
                      records=[dict(case_id='tiny',method=m,round=r,status='qualified',cold_ns=1,warm_ns=[1,1,1],
                                    checks=dict(exact_estimates_verified=11),category_extrema_sha256='same',exact_estimates_sha256=digest)
                               for m in config['methods'] for r in range(3)],process_resources=[{}]*12)
        check_compact(result,config)
        broken = deepcopy(result); broken['cases'][0]['model'] = {}
        with self.assertRaises(ValueError): check_compact(broken,config)
        broken = deepcopy(result); broken['records'].pop()
        with self.assertRaises(ValueError): check_compact(broken,config)
        broken = deepcopy(result); broken['records'][0]['category_extrema_sha256'] = 'different'
        with self.assertRaises(ValueError): check_compact(broken,config)
        broken = deepcopy(result); broken['cases'][0]['estimates'] = dict(tampered=True)
        with self.assertRaises(ValueError): check_compact(broken,config)

    def test_archive_rejects_wrong_source_or_missing_artifact(self):
        run_id = 34583421491; head = archive.SOURCES[run_id][0]
        run = dict(id=run_id,head_sha=head,run_attempt=1,path='.github/workflows/v3-bdd-comparison-v1.yml',
                   status='completed',conclusion='success',head_repository=dict(full_name=archive.transport.REPO))
        artifacts = [dict(id=i,name=name,size_in_bytes=10,expired=False,workflow_run=dict(id=run_id,head_sha=head))
                     for i,name in enumerate(sorted(archive.expected_names(run_id)))]
        archive.checked_source(run,artifacts)
        with self.assertRaises(ValueError): archive.checked_source(run,artifacts[:-1])
        changed = dict(run,head_sha='0'*40)
        with self.assertRaises(ValueError): archive.checked_source(changed,artifacts)


if __name__ == '__main__': unittest.main()
