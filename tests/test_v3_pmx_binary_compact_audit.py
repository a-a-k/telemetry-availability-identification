"""Ensure compact evidence rejects a foreign binary or diagnostic-only launcher."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_v3_preflight_compact_v3 as preflight
import audit_v3_main_compact_v2 as main_audit


class BinaryEvidenceTests(unittest.TestCase):
    def fixture(self):
        identity={'application':'artificial','repetition':0}
        expected={'qualified':True,'derived_jar_sha256':'a'*64}
        operations=['first','last']
        records=[dict(case_id='campaign-'+preflight.digest(identity)[:20]+'--'+op,qualified=True,
            execution=dict(exit_code=0,jar_sha256='a'*64,startup_seconds=20,internal_watchdog_seconds=1800)) for op in operations]
        pmx={'read-audit.json':{'qualified_pmx_build':expected},'costs.json':{'extraction_and_bridge_records':records}}
        return pmx,identity,operations,expected

    def test_both_admission_and_main_require_every_case_to_use_qualified_binary(self):
        for auditor in (preflight,main_audit):
            pmx,identity,operations,expected=self.fixture()
            auditor.pmx_binary_provenance(pmx,identity,operations,expected)
            pmx['costs.json']['extraction_and_bridge_records'][-1]['execution']['jar_sha256']='b'*64
            with self.assertRaisesRegex(ValueError,'different binary'):
                auditor.pmx_binary_provenance(pmx,identity,operations,expected)

    def test_short_diagnostic_launcher_cannot_be_credited_as_production(self):
        for auditor in (preflight,main_audit):
            pmx,identity,operations,expected=self.fixture()
            pmx['costs.json']['extraction_and_bridge_records'][-1]['execution']['internal_watchdog_seconds']=120
            with self.assertRaisesRegex(ValueError,'production launcher settings differ'):
                auditor.pmx_binary_provenance(pmx,identity,operations,expected)


if __name__=='__main__':unittest.main()
