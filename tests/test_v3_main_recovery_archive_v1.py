from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import archive_v3_main_recovery_evidence_v1 as archive


class RecoveryArchiveControls(unittest.TestCase):
    def fixture(self):
        run=dict(id=archive.RUN,head_sha=archive.HEAD,run_attempt=1,
            path='.github/workflows/v3-main-transport-recovery-v1.yml',status='completed',conclusion='success',
            head_repository={'full_name':archive.transport.REPO})
        items=[dict(id=i+1,name=n,size_in_bytes=100,expired=False,workflow_run={'id':archive.RUN,'head_sha':archive.HEAD})
               for i,n in enumerate(sorted(archive.expected_names()))]
        return run,items

    def test_exact_sixteen_artifact_census_and_missing_foreign_duplicate_rejection(self):
        run,items=self.fixture();archive.checked_source(run,items)
        for changed in (items[:-1],items[:-1]+[items[0]]):
            with self.assertRaisesRegex(ValueError,'census'):archive.checked_source(run,changed)
        foreign=deepcopy(items);foreign[0]['workflow_run']['id']=1
        with self.assertRaisesRegex(ValueError,'source/size'):archive.checked_source(run,foreign)

    def test_early_failed_repeated_and_oversized_source_rejected(self):
        run,items=self.fixture()
        for key,value in [('status','in_progress'),('conclusion','failure'),('run_attempt',2)]:
            changed=dict(run);changed[key]=value
            with self.assertRaisesRegex(ValueError,'incomplete'):archive.checked_source(changed,items)
        large=deepcopy(items)
        for item in large:item['size_in_bytes']=100_000_000
        with self.assertRaisesRegex(ValueError,'bounded'):archive.checked_source(run,large)


if __name__=='__main__':unittest.main()
