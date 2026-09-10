from copy import deepcopy
import io
from hashlib import sha256
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import retain_v3_main_transport_recovery_v1 as retention


class RecoveryCompactControls(unittest.TestCase):
    def test_exact_census_contains_only_forecasts_counts_and_provenance(self):
        selected,cases=retention.choices(123)
        self.assertEqual(len(selected),10);self.assertEqual(len(cases),240)
        self.assertEqual(sum(len(c['allowed']) for c in selected.values()),4812)
        for selection in selected.values():
            self.assertFalse(any(name.endswith(('native.json','requests.json','probes.json','models.json','.jar','.repository'))
                                 for name in selection['allowed']))

    def test_unlisted_pcm_member_rejected(self):
        selected,_=retention.choices(123)
        allowed=selected['v3-main-recovery-analysis-123']['allowed']
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr('comparison.json','{}');archive.writestr('saved.repository','artificial')
        raw=buffer.getvalue();item=dict(size_in_bytes=len(raw),expired=False,digest='sha256:'+sha256(raw).hexdigest())
        with self.assertRaisesRegex(ValueError,'unlisted'):
            retention.transport.check_archive(raw,item,allowed)

    def test_running_failed_repeated_or_foreign_execution_rejected(self):
        valid=dict(id=123,path=retention.recovery.WORKFLOW,head_repository={'full_name':retention.transport.REPO},
                   event='workflow_dispatch',run_attempt=1,status='completed',conclusion='success')
        retention.run_guard(valid,123)
        for key,value in [('status','in_progress'),('conclusion','failure'),('run_attempt',2),('path','unrelated.yml')]:
            changed=deepcopy(valid);changed[key]=value
            with self.assertRaisesRegex(ValueError,'exact successful'):
                retention.run_guard(changed,123)


if __name__=='__main__':unittest.main()
