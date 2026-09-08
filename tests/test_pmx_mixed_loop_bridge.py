import unittest
from telemetry_availability.pmx_mixed_loop_bridge import mixed_loop_pmfs, validate_integer_pmf


class MixedLoopTests(unittest.TestCase):
    def test_native_pmf_bytes_preserved_and_integer_equivalent(self):
        pmf = 'IntPMF[(0;5.0E-1) (2;0.5)]'
        text = '<repository xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:seff="urn:seff"><step id="a" xsi:type="seff:LoopAction"><iterationCount_LoopAction specification="1"/></step><step id="b" xsi:type="seff:LoopAction"><iterationCount_LoopAction specification="'+pmf+'"/></step></repository>'
        updated, records = mixed_loop_pmfs(text)
        self.assertEqual(updated, text.replace('specification="1"', 'specification="IntPMF[(1;1.0)]"'))
        self.assertEqual([r['existing_pmf_preserved'] for r in records], [False, True])
        self.assertEqual(validate_integer_pmf(pmf), [(0, .5), (2, .5)])

    def test_negative_mass_duplicates_unbounded_and_noninteger_support_rejected(self):
        for value in ('IntPMF[(0;-0.5)(1;1.5)]', 'IntPMF[(0;0.5)(0;0.5)]', 'IntPMF[(1;0.7)]',
                      'IntPMF[(1.5;1)]', 'IntPMF[(-1;1)]', 'IntPMF[(1;1e999)]',
                      'IntPMF[(1;NaN)]', 'DoublePDF[(1;1)]', 'IntPMF[(1;1)garbage]'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_integer_pmf(value)

    def test_small_native_probability_and_spacing(self):
        value = 'IntPMF[(0;0.9991666666666666) (1;8.333333333333334E-4)]'
        law = validate_integer_pmf(value)
        self.assertAlmostEqual(sum(p for _, p in law), 1)
