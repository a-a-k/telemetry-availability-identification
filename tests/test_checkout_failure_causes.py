from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.checkout_failure_causes import (
    CALIBRATION_CLASSES,
    CheckoutFailureCauseError,
    _bootstrap_summary,
    _classify_dominance,
    _request_facts,
    _summary_for_class,
    decide,
    load_checkout_failure_cause_config,
    run_discrimination,
    validate_repository,
)
from telemetry_availability.live_validation_analysis import HealthTick, _timestamp
from telemetry_availability.pmx_performability import file_sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9l_checkout_failure_causes.json"
PROTOCOL = ROOT / "docs" / "M9L_CHECKOUT_FAILURE_CAUSES_PROTOCOL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "m9l-checkout-failure-causes.yml"


class CheckoutFailureCauseTests(unittest.TestCase):
    @staticmethod
    def _request(
        *,
        start: str = "1970-01-01T00:16:40Z",
        completion: str = "1970-01-01T00:16:42Z",
        success: bool = False,
        trace_present: bool = True,
        span_count: int = 4,
        replicas: str = "a",
        replica_count: int = 1,
    ) -> dict[str, str]:
        return {
            "request_id": "request-1",
            "period": "calibration",
            "operation": "checkout",
            "started_at": start,
            "completed_at": completion,
            "semantic_success": str(success).lower(),
            "timed_out": "false",
            "trace_present": str(trace_present).lower(),
            "span_count": str(span_count),
            "target_replicas": replicas,
            "target_replica_count": str(replica_count),
        }

    @staticmethod
    def _ticks(signals: list[tuple[int, int, int, int]]) -> tuple[HealthTick, ...]:
        start = _timestamp("1970-01-01T00:16:40Z")
        return tuple(
            HealthTick(at=start + index, elapsed_seconds=index, signals=value)
            for index, value in enumerate(signals)
        )

    def test_frozen_scope_is_retained_diagnostic_and_remote_only(self) -> None:
        config = load_checkout_failure_cause_config(CONFIG)
        self.assertEqual(config.profile, "opentelemetry_demo")
        self.assertEqual(config.operation, "checkout")
        self.assertEqual(config.expected_cells, 40)
        self.assertEqual(config.resamples, 10_000)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.raw["new_live_collection"], "forbidden")
        self.assertEqual(config.raw["pmx_invocation"], "forbidden")
        self.assertEqual(tuple(config.raw["classification"]["precedence"]), CALIBRATION_CLASSES)

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertEqual(workflow.count("runs-on: ubuntu-latest"), 3)
        self.assertIn("m8-preserved-m7-evidence-33990678586-34016153918", workflow)
        self.assertIn("m9l-failure-cause-discrimination-${{ github.run_id }}", workflow)
        self.assertNotIn("docker compose", workflow.lower())
        self.assertNotIn("main.jar", workflow)

    def test_protocol_guards_missingness_and_claims(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("Every M9K route-up request enters exactly one class", protocol)
        self.assertIn("additional post-result diagnostic evidence", protocol)
        self.assertIn("Missingness is neither imputed nor dropped", protocol)
        self.assertIn("not an exact per-call timestamp", protocol)
        self.assertIn("No branch generalizes beyond checkout", protocol)
        self.assertIn("All three jobs use `timeout-minutes: 360`", protocol)

    def test_repository_locks_validate(self) -> None:
        result = validate_repository(CONFIG)
        self.assertEqual(result["status"], "m9l_repository_contract_valid")
        self.assertEqual(len(result["repository_locks"]), 7)
        self.assertEqual(result["pmx_invocations"], 0)
        self.assertEqual(result["new_live_collections"], 0)

    def test_exhaustive_classification_precedence(self) -> None:
        union_lost = _request_facts(
            self._request(),
            self._ticks([(1, 1, 1, 1), (1, 1, 0, 0), (1, 1, 1, 1)]),
            1.25,
            0,
            allow_trace=True,
        )
        self.assertEqual(
            union_lost["class"], "aggregate_union_lost_during_request"
        )

        target_down = _request_facts(
            self._request(replicas="b"),
            self._ticks([(1, 1, 1, 0), (1, 1, 1, 0), (1, 1, 1, 0)]),
            1.25,
            0,
            allow_trace=True,
        )
        self.assertEqual(
            target_down["class"], "target_path_down_at_start_union_continuous"
        )

        target_lost = _request_facts(
            self._request(replicas="a"),
            self._ticks([(1, 1, 1, 1), (1, 1, 0, 1), (1, 1, 0, 1)]),
            1.25,
            0,
            allow_trace=True,
        )
        self.assertEqual(
            target_lost["class"],
            "target_path_lost_during_request_union_continuous",
        )

        continuous = _request_facts(
            self._request(replicas="a;b", replica_count=2),
            self._ticks([(1, 1, 1, 1), (1, 1, 1, 1), (1, 1, 1, 1)]),
            1.25,
            0,
            allow_trace=True,
        )
        self.assertEqual(continuous["class"], "target_paths_continuously_up")

        unresolved = _request_facts(
            self._request(trace_present=False, span_count=0, replicas="", replica_count=0),
            self._ticks([(1, 1, 1, 1), (1, 1, 1, 1), (1, 1, 1, 1)]),
            1.25,
            0,
            allow_trace=True,
        )
        self.assertEqual(
            unresolved["class"], "trace_target_unresolved_union_continuous"
        )

    def test_class_contributions_exactly_allocate_baseline_residual(self) -> None:
        identity = ("opentelemetry_demo", "colocated", "N", 0)
        facts = [
            {"class": "target_paths_continuously_up", "success": 0, "timed_out": 0},
            {"class": "target_paths_continuously_up", "success": 1, "timed_out": 0},
            {
                "class": "trace_target_unresolved_union_continuous",
                "success": 0,
                "timed_out": 1,
            },
        ]
        summaries = [
            _summary_for_class(identity, "calibration", name, facts, 0.9, 5)
            for name in CALIBRATION_CLASSES
        ]
        contribution = sum(
            float(row["excess_residual_contribution"]) for row in summaries
        )
        self.assertAlmostEqual(contribution, (2 - 0.1 * 3) / 5)

    @staticmethod
    def _campaign_rows(winner: str, coverage: float = 0.9) -> list[dict[str, float | str]]:
        rows: list[dict[str, float | str]] = []
        for placement in ("colocated", "split"):
            for law in ("N", "ND"):
                for repetition in range(10):
                    candidates = {
                        "aggregate_interval_loss": 0.01,
                        "observed_replica_path_loss": 0.02,
                        "observed_paths_continuously_up": 0.03,
                        "evidence_unresolved": 0.015,
                    }
                    candidates[winner] = 0.20
                    rows.append(
                        {
                            "placement": placement,
                            "failure_law": law,
                            "repetition": repetition,
                            **candidates,
                            "calibration_residual": sum(candidates.values()),
                            "resolved_target_trace_fraction": coverage,
                            "resolution_failure_minus_success": 0.0,
                            "test_aggregate_interval_loss": (
                                0.20 if winner == "aggregate_interval_loss" else 0.01
                            ),
                            "test_aggregate_union_continuous": (
                                0.02 if winner == "aggregate_interval_loss" else 0.20
                            ),
                            "test_completion_unresolved": 0.0,
                            "test_residual": 0.22,
                        }
                    )
        return rows

    def test_dominance_applies_trace_and_test_adequacy(self) -> None:
        continuous_rows = self._campaign_rows("observed_paths_continuously_up")
        continuous_bootstrap = _bootstrap_summary(continuous_rows, 200, 7, 0.95)
        continuous = _classify_dominance(
            continuous_rows, continuous_bootstrap, 32, 0.60, 0.10
        )
        self.assertEqual(
            continuous["classification"], "observed_paths_continuously_up"
        )
        self.assertTrue(continuous["trace_adequacy_passed"])

        inadequate_rows = self._campaign_rows(
            "observed_paths_continuously_up", coverage=0.4
        )
        inadequate_bootstrap = _bootstrap_summary(inadequate_rows, 200, 7, 0.95)
        inadequate = _classify_dominance(
            inadequate_rows, inadequate_bootstrap, 32, 0.60, 0.10
        )
        self.assertEqual(inadequate["classification"], "evidence_unresolved")

        aggregate_rows = self._campaign_rows("aggregate_interval_loss")
        aggregate_bootstrap = _bootstrap_summary(aggregate_rows, 200, 7, 0.95)
        aggregate = _classify_dominance(
            aggregate_rows, aggregate_bootstrap, 32, 0.60, 0.10
        )
        self.assertEqual(aggregate["classification"], "aggregate_interval_loss")
        self.assertTrue(aggregate["test_aggregate_interval_corroborated"])

    def test_full_discrimination_is_rejected_outside_github_actions(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                CheckoutFailureCauseError, "only in GitHub Actions"
            ):
                run_discrimination(
                    CONFIG,
                    Path("contract.json"),
                    Path("qualified"),
                    Path("m8a"),
                    Path("m9k"),
                    Path("out"),
                )

    def test_decision_routes_accepted_continuously_up_result(self) -> None:
        config_hash = file_sha256(CONFIG)
        expected_status = (
            "checkout_residual_persists_with_observed_target_paths_continuously_up"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "m9k_route_up_residual_and_retained_evidence_verified",
                        "selected_cells": 40,
                        "pmx_invocations": 0,
                        "new_live_collections": 0,
                    }
                ),
                encoding="utf-8",
            )
            discrimination = root / "discrimination.json"
            discrimination.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "contract_manifest_sha256": file_sha256(contract),
                        "integrity_passed": True,
                        "cell_count": 40,
                        "test_trace_graph_accessed": False,
                        "pmx_invocations": 0,
                        "new_live_collections": 0,
                        "status": expected_status,
                        "discrimination": {
                            "classification": "observed_paths_continuously_up",
                            "raw_dominant_candidate": "observed_paths_continuously_up",
                            "trace_adequacy_passed": True,
                            "test_aggregate_interval_corroborated": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = decide(CONFIG, contract, discrimination, root / "out")

        self.assertEqual(result["status"], expected_status)
        self.assertTrue(result["technical_evidence_accepted"])
        self.assertEqual(
            result["next_experiment"],
            "m9m_checkout_dependency_and_timeout_semantics",
        )
        self.assertFalse(result["physical_cause_uniquely_identified"])
        self.assertFalse(result["overall_article_verdict_changed"])


if __name__ == "__main__":
    unittest.main()
