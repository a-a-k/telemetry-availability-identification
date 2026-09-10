"""Negative provenance controls for the explicitly qualified PMX binary."""
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from telemetry_availability.pmx_clock_progress_application_v1 import run_application_pmx
from telemetry_availability import v3_comparison_pmx_v3 as pmx


class PmxClockProgressProvenanceTests(unittest.TestCase):
    def test_different_binary_is_rejected_before_process_or_output_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);jar=root/'artificial.jar';jar.write_bytes(b'artificial original')
            output=root/'output'
            with patch.dict('os.environ',{'GITHUB_ACTIONS':'true'}),patch('subprocess.Popen') as process:
                with self.assertRaisesRegex(ValueError,'qualified clock-progress PMX binary differs'):
                    run_application_pmx(jar,root,output,expected_jar_sha256=sha256(b'artificial qualified').hexdigest())
                process.assert_not_called()
            self.assertFalse(output.exists())

    def test_solver_batch_cannot_mix_repaired_and_unqualified_extractors(self):
        for builds in ([None], [{'qualified':False}], [{'qualified':True,'derived_jar_sha256':'a'*64},{'qualified':True,'derived_jar_sha256':'b'*64}]):
            with self.subTest(builds=builds):
                prepared={'extractions':[{'qualified_pmx_build':b} for b in builds]}
                with self.assertRaisesRegex(ValueError,'mixed or unqualified PMX binary provenance'):
                    pmx.solver_forecasts(prepared,[])


if __name__=='__main__':unittest.main()
