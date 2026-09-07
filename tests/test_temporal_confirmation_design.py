import copy
from pathlib import Path
import unittest

import yaml

from telemetry_availability.temporal_confirmation_design import precision_requirements, validate

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/m9o_temporal_confirmation.json"


class TemporalConfirmationDesignTests(unittest.TestCase):
    def setUp(self):
        self.config = validate(CONFIG)
        self.planning = self.config["planning"]

    def test_zero_pilot_variance_does_not_remove_minimum_replication(self):
        result = precision_requirements({name: [0.] * 4 for name in self.planning["metrics"]}, self.planning)
        self.assertEqual(result["selected_per_stratum"], 10)
        self.assertAlmostEqual(result["normal_critical_value"], 2.3939798, places=6)
        self.assertFalse(result["working_normal_approximation_is_a_precision_guarantee"])

    def test_large_variance_cannot_silently_expand_budget(self):
        result = precision_requirements({name: [1.] * 4 for name in self.planning["metrics"]}, self.planning)
        self.assertIsNone(result["selected_per_stratum"])
        self.assertEqual(result["status"], "precision_budget_requires_redesign")

    def test_symmetric_stratum_reordering_preserves_plan(self):
        variances = {name: [1e-5, 2e-5, 3e-5, 4e-5] for name in self.planning["metrics"]}
        first = precision_requirements(variances, self.planning)
        second = precision_requirements({name: values[::-1] for name, values in variances.items()}, self.planning)
        self.assertEqual(first["selected_per_stratum"], second["selected_per_stratum"])
        for name in variances:
            self.assertEqual(first["requirements"][name]["grid_half_widths"], second["requirements"][name]["grid_half_widths"])

    def test_tightening_half_width_increases_required_sample_quadratically(self):
        variances = {name: [1e-4] * 4 for name in self.planning["metrics"]}
        first = precision_requirements(variances, self.planning)
        tighter = copy.deepcopy(self.planning)
        for metric in tighter["metrics"].values():
            metric["half_width"] /= 2
        second = precision_requirements(variances, tighter)
        for name in variances:
            a = first["requirements"][name]["required_per_stratum"]
            b = second["requirements"][name]["required_per_stratum"]
            self.assertGreaterEqual(b, 4 * a - 3)
            self.assertLessEqual(b, 4 * a)

    def test_invalid_variances_are_rejected(self):
        for invalid in (-1., float("nan"), float("inf")):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "invalid planning variance"):
                precision_requirements({name: [invalid] * 4 for name in self.planning["metrics"]}, self.planning)

    def test_planning_workflow_has_three_serial_jobs_and_no_live_invocation(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/m9o-temporal-confirmation-design.yml").read_text())
        self.assertEqual(len(workflow["jobs"]), 3)
        self.assertEqual(workflow["jobs"]["precision_plan"]["needs"], ["pilot_contract"])
        self.assertEqual(workflow["jobs"]["design_audit"]["needs"], ["precision_plan"])
        for job in workflow["jobs"].values():
            self.assertEqual(job["timeout-minutes"], 360)
            for step in job["steps"]:
                for forbidden in ("docker compose", "run-frozen-live", "checkout_temporal_failover evaluate"):
                    self.assertNotIn(forbidden, step.get("run", ""))


if __name__ == "__main__":
    unittest.main()
