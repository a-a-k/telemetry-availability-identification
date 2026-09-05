from __future__ import annotations

import unittest
from pathlib import Path

from telemetry_availability.live_budget_recovery import (
    load_macro_budget_recovery_config,
    macro_repetition_recommendation,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m7c_macro_precision_recovery.yaml"


class MacroBudgetRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_macro_budget_recovery_config(CONFIG_PATH)

    def test_contract_narrows_estimand_without_weakening_threshold(self) -> None:
        self.assertTrue(self.config.pilot_only)
        self.assertFalse(self.config.cell_specific_precision_claim)
        self.assertEqual(self.config.expected_strata, 16)
        self.assertEqual(self.config.target_macro_half_width, 0.015)
        self.assertEqual(self.config.candidate_main_repetitions, (10, 15, 20, 30, 40))

    def test_balanced_macro_rule_uses_strata_not_requests(self) -> None:
        cells = [
            {
                "cell": f"cell-{index}",
                "pilot_pairs": 4,
                "sample_sd": 0.01 + index / 10_000,
            }
            for index in range(16)
        ]
        result = macro_repetition_recommendation(self.config, cells)
        self.assertEqual(result["selection_status"], "selected")
        self.assertEqual(result["selected_repetitions"], 10)
        self.assertEqual(result["candidates"][0]["independent_pairs_total"], 160)
        self.assertLessEqual(
            result["candidates"][0]["projected_macro_half_width"], 0.015
        )

    def test_incomplete_pilot_matrix_cannot_select(self) -> None:
        result = macro_repetition_recommendation(
            self.config,
            [{"pilot_pairs": 4, "sample_sd": 0.01}] * 15,
        )
        self.assertEqual(result["selection_status"], "invalid_pilot_matrix")
        self.assertIsNone(result["selected_repetitions"])


if __name__ == "__main__":
    unittest.main()
