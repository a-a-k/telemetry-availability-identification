from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.checkout_localization import (
    CheckoutLocalizationError,
    _classify_localization,
    _decompose,
    _period_metrics,
    decide,
    load_checkout_localization_config,
    run_localization,
    validate_repository,
)
from telemetry_availability.live_validation_analysis import (
    EvaluationRequest,
    HealthTick,
)
from telemetry_availability.pmx_performability import file_sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9k_checkout_localization.json"
PROTOCOL = ROOT / "docs" / "M9K_CHECKOUT_LOCALIZATION_PROTOCOL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "m9k-checkout-localization.yml"


class CheckoutLocalizationTests(unittest.TestCase):
    def test_frozen_scope_is_single_operation_retained_and_remote_only(self) -> None:
        config = load_checkout_localization_config(CONFIG)
        self.assertEqual(config.profile, "opentelemetry_demo")
        self.assertEqual(config.operation, "checkout")
        self.assertEqual(config.placements, ("colocated", "split"))
        self.assertEqual(config.failure_laws, ("N", "ND"))
        self.assertEqual(config.repetitions, tuple(range(10)))
        self.assertEqual(config.expected_cells, 40)
        self.assertEqual(config.bootstrap_resamples, 10_000)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.raw["new_live_collection"], "forbidden")
        self.assertEqual(config.raw["pmx_invocation"], "forbidden")

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertEqual(workflow.count("runs-on: ubuntu-latest"), 3)
        self.assertIn("m8-preserved-m7-evidence-33990678586-34016153918", workflow)
        self.assertIn("m9k-checkout-localization-${{ github.run_id }}", workflow)
        self.assertNotIn("docker compose", workflow.lower())
        self.assertNotIn("main.jar", workflow)
        self.assertNotIn("java -jar", workflow)

    def test_protocol_preserves_the_article_claim_boundary(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("one operation", protocol)
        self.assertIn("diagnostic counterfactual components", protocol)
        self.assertIn("not replacement predictions", protocol)
        self.assertIn("No branch generalizes checkout", protocol)
        self.assertIn("lower end-to-end automatic", protocol)
        self.assertIn("All three jobs use `timeout-minutes: 360`", protocol)

    def test_repository_locks_validate(self) -> None:
        result = validate_repository(CONFIG)
        self.assertEqual(result["status"], "m9k_repository_contract_valid")
        self.assertEqual(len(result["repository_locks"]), 8)
        self.assertEqual(result["expected_cells"], 40)
        self.assertEqual(result["pmx_invocations"], 0)
        self.assertEqual(result["new_live_collections"], 0)

    def test_period_metrics_uses_full_path_union(self) -> None:
        ticks = (
            HealthTick(at=0.0, elapsed_seconds=0.0, signals=(1, 1, 0, 1)),
            HealthTick(at=1.0, elapsed_seconds=1.0, signals=(1, 1, 0, 1)),
            HealthTick(at=2.0, elapsed_seconds=2.0, signals=(1, 1, 0, 1)),
        )
        requests = (
            EvaluationRequest(operation="checkout", at=0.1, success=1),
            EvaluationRequest(operation="checkout", at=1.1, success=0),
            EvaluationRequest(operation="browse_product", at=2.0, success=1),
        )
        result = _period_metrics("checkout", requests, ticks, 1.25, 1)
        all_sequence = next(row for row in result if row["view"] == "all_sequence")
        stable = next(row for row in result if row["view"] == "stable")
        self.assertEqual(all_sequence["operation_requests"], 2)
        self.assertEqual(all_sequence["aligned_requests"], 2)
        self.assertEqual(all_sequence["route_up_requests"], 2)
        self.assertEqual(all_sequence["route_down_requests"], 0)
        self.assertEqual(all_sequence["empirical_success_rate"], 0.5)
        self.assertEqual(stable["view_requests"], 2)

    def test_exact_three_term_identity(self) -> None:
        metrics = {
            "view_requests": 100,
            "route_up_requests": 80,
            "route_up_successes": 60,
            "route_down_successes": 5,
        }
        result = _decompose(0.9, 0.95, metrics)
        self.assertAlmostEqual(result["model_prediction"], 0.855)
        self.assertAlmostEqual(result["observed_success_rate"], 0.65)
        self.assertAlmostEqual(result["model_minus_observed"], 0.205)
        self.assertAlmostEqual(result["route_state_exposure"], 0.135)
        self.assertAlmostEqual(result["route_up_residual_invariance"], 0.12)
        self.assertAlmostEqual(result["route_down_success_offset"], -0.05)
        self.assertAlmostEqual(result["component_sum"], 0.205)
        self.assertAlmostEqual(result["reconstruction_error"], 0.0)

    @staticmethod
    def _classification_rows(residual: float, state: float) -> list[dict[str, float]]:
        return [
            {
                "route_up_residual_invariance": residual,
                "route_state_exposure": state,
            }
            for _ in range(40)
        ]

    @staticmethod
    def _bootstrap(
        residual_lower: float,
        state_lower: float,
        residual_minus_state_lower: float,
        state_minus_residual_lower: float,
    ) -> dict[str, dict[str, float]]:
        return {
            "route_up_residual_invariance": {"lower": residual_lower},
            "route_state_exposure": {"lower": state_lower},
            "residual_minus_state": {"lower": residual_minus_state_lower},
            "state_minus_residual": {"lower": state_minus_residual_lower},
        }

    def test_dominance_rule_has_residual_state_and_unresolved_branches(self) -> None:
        calibration = self._classification_rows(0.10, 0.02)
        residual = _classify_localization(
            self._classification_rows(0.20, 0.05),
            calibration,
            self._bootstrap(0.10, 0.01, 0.08, -0.20),
            self._bootstrap(0.05, 0.00, 0.02, -0.10),
            32,
        )
        self.assertEqual(residual["classification"], "route_up_residual")
        self.assertTrue(residual["calibration_corroborated"])

        state = _classify_localization(
            self._classification_rows(0.03, 0.20),
            calibration,
            self._bootstrap(0.01, 0.10, -0.20, 0.08),
            self._bootstrap(0.05, 0.00, 0.02, -0.10),
            32,
        )
        self.assertEqual(state["classification"], "route_state_exposure")

        unresolved = _classify_localization(
            self._classification_rows(0.08, 0.07),
            calibration,
            self._bootstrap(0.01, 0.01, -0.02, -0.02),
            self._bootstrap(0.05, 0.00, 0.02, -0.10),
            32,
        )
        self.assertEqual(unresolved["classification"], "unresolved")

    def test_full_localization_is_rejected_outside_github_actions(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                CheckoutLocalizationError, "only in GitHub Actions"
            ):
                run_localization(
                    CONFIG,
                    Path("contract.json"),
                    Path("qualified"),
                    Path("analysis"),
                    Path("m8a"),
                    Path("m8b"),
                    Path("out"),
                )

    def test_decision_routes_accepted_residual_localization(self) -> None:
        config_hash = file_sha256(CONFIG)
        expected_status = (
            "checkout_overprediction_localized_to_fault_period_route_up_residual_mismatch"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "checkout_target_and_retained_evidence_verified",
                        "selected_cells": 40,
                        "pmx_invocations": 0,
                        "new_live_collections": 0,
                    }
                ),
                encoding="utf-8",
            )
            localization = root / "localization.json"
            localization.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "contract_manifest_sha256": file_sha256(contract),
                        "integrity_passed": True,
                        "cell_count": 40,
                        "decomposition_rows": 80,
                        "pmx_invocations": 0,
                        "new_live_collections": 0,
                        "status": expected_status,
                        "dominance": {
                            "classification": "route_up_residual",
                            "route_up_residual_dominant": True,
                            "route_state_exposure_dominant": False,
                            "calibration_corroborated": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = decide(CONFIG, contract, localization, root / "out")

        self.assertEqual(result["status"], expected_status)
        self.assertTrue(result["technical_evidence_accepted"])
        self.assertEqual(
            result["next_experiment"],
            "m9l_checkout_route_up_failure_cause_discrimination",
        )
        self.assertFalse(result["better_predictive_accuracy_demonstrated"])
        self.assertFalse(result["overall_article_verdict_changed"])


if __name__ == "__main__":
    unittest.main()
