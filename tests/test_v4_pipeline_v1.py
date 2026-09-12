from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_v4_pipeline_v1 import first_forecasts


class FirstPalladioAnswerTests(unittest.TestCase):
    def test_missing_duplicate_invalid_and_extra_passes_are_not_first_answers(self):
        ids=['campaign--operation--conditional_local','campaign--operation--inclusive']
        prepared=dict(models=[dict(model_id=i)for i in ids],extractions=[dict(cases=[dict(case_id='campaign--operation',variants=[])])])
        rows=[dict(model_id=i,repetition=0,status='solved',success_probability=.75,failure_probability_sum=.25,
            physical_state_probability=1.,total_physical_states=1,evaluated_physical_states=1)for i in ids]
        value=first_forecasts(prepared,rows)
        self.assertFalse(value['extra_verification_complete'])
        self.assertEqual(value['forecasts']['operation']['PMX']['probability'],.75)
        for bad in (rows[:1],rows+[rows[0]],[rows[0],rows[0]],[dict(r,repetition=1)for r in rows],
                    [dict(r,physical_state_probability=0)for r in rows]):
            with self.assertRaises(ValueError):first_forecasts(prepared,bad)

    def test_harness_only_changes_number_of_passes_not_solver_or_output(self):
        root=Path(__file__).resolve().parents[1]
        original=(root/'palladio/harness/src/org/palladiosimulator/reliability/tests/PmxContextBridgeTest.java').read_text(encoding='utf-8')
        expected=original.replace('        for (int repetition = 0; repetition < 2; repetition++) {',
            '        final int passes = Integer.parseInt(requiredEnvironment("TAID_REPEAT_RUNS"));\n        assertTrue(passes == 1 || passes == 2);\n        for (int repetition = 0; repetition < passes; repetition++) {')
        expected=expected.replace('assertEquals(2 * models.size(), records.size());','assertEquals(passes * models.size(), records.size());')
        self.assertNotEqual(original,expected)
        self.assertEqual(expected,(root/'palladio/harness-v4-pipeline/PmxContextBridgeTest.java').read_text(encoding='utf-8'))
