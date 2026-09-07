from __future__ import annotations

import os
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from telemetry_availability.checkout_routing_model import (
    ALL_METHODS,
    CheckoutRoutingModelError,
    _candidate_likelihood_data,
    _candidate_objective,
    _footprint_weights,
    classify_evaluation,
    load_checkout_routing_model_config,
    route_state_vector,
    stage_learner_inputs,
    validate_repository,
)
from telemetry_availability.live_validation_analysis import (
    HealthTick,
    QualifiedCell,
    RequestRecord,
    _likelihood_data,
    _negative_log_likelihood,
    _parameter_names,
    prepare_mode,
)
from telemetry_availability.live_validation_config import load_frozen_live_validation_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9m_checkout_routing_model.json"
PROTOCOL = ROOT / "docs" / "M9M_CHECKOUT_ROUTING_MODEL_PROTOCOL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "m9m-checkout-routing-model.yml"


class CheckoutRoutingModelTests(unittest.TestCase):
    def test_frozen_scope_boundary_and_three_remote_jobs(self) -> None:
        config = load_checkout_routing_model_config(CONFIG)
        self.assertEqual(config.profile, "opentelemetry_demo")
        self.assertEqual(config.operation, "checkout")
        self.assertEqual(config.expected_cells, 40)
        self.assertEqual(config.resamples, 10_000)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.raw["new_live_collection"], "forbidden")
        self.assertEqual(config.raw["pmx_invocation"], "forbidden")
        self.assertEqual(config.raw["models"]["primary"], "learner_trace_requirement_mixture")

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertEqual(workflow.count("runs-on: ubuntu-latest"), 3)
        self.assertIn("stage-learner", workflow)
        self.assertIn("test ! -e workflow-input/m9m/m8a-preserved", workflow)
        self.assertIn("already-frozen candidates", workflow)
        self.assertNotIn("docker compose", workflow.lower())
        self.assertNotIn("java -jar", workflow)

    def test_protocol_excludes_model_selection_and_article_claims(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("three required", protocol)
        self.assertIn("exact per-call backend decision", protocol)
        self.assertIn("copies nor parses an", protocol)
        self.assertIn("not a menu from which the", protocol)
        self.assertIn("independent confirmation", protocol)
        self.assertIn("All three jobs use", protocol)

    def test_repository_locks_validate(self) -> None:
        result = validate_repository(CONFIG)
        self.assertEqual(result["status"], "m9m_repository_contract_valid")
        self.assertEqual(len(result["repository_locks"]), 7)
        self.assertEqual(result["models"], list(ALL_METHODS))
        self.assertEqual(result["pmx_invocations"], 0)
        self.assertEqual(result["new_live_collections"], 0)

    def test_route_state_formulas_are_exact_on_four_path_states(self) -> None:
        def values(method: str) -> dict[tuple[int, int], float]:
            vector = route_state_vector(
                "split",
                method,
                {"weight_a": 0.2, "weight_b": 0.3, "weight_a_b": 0.5},
            )
            from telemetry_availability.live_validation_analysis import _latent_template

            template = _latent_template("split")
            result: dict[tuple[int, int], float] = {}
            for state, value in zip(template.signals, vector, strict=True):
                result[(int(state[2]), int(state[3]))] = float(value)
            return result

        self.assertEqual(
            values("m7_single_demand_or"),
            {(0, 0): 0.0, (0, 1): 1.0, (1, 0): 1.0, (1, 1): 1.0},
        )
        self.assertEqual(
            values("source_strict_round_robin_and"),
            {(0, 0): 0.0, (0, 1): 0.0, (1, 0): 0.0, (1, 1): 1.0},
        )
        self.assertEqual(
            values("source_three_call_independent"),
            {(0, 0): 0.0, (0, 1): 0.125, (1, 0): 0.125, (1, 1): 1.0},
        )
        self.assertEqual(
            values("source_two_client_affinity"),
            {(0, 0): 0.0, (0, 1): 0.25, (1, 0): 0.25, (1, 1): 1.0},
        )
        self.assertEqual(
            values("learner_trace_requirement_mixture"),
            {(0, 0): 0.0, (0, 1): 0.3, (1, 0): 0.2, (1, 1): 1.0},
        )

    @staticmethod
    def _cell(successes: tuple[int, int, int]) -> QualifiedCell:
        footprints = (frozenset({"a"}), frozenset({"b"}), frozenset({"a", "b"}))
        requests = tuple(
            RequestRecord(
                period="baseline",
                request_id=f"request-{index}",
                operation="checkout",
                at=float(index),
                success=success,
                trace_present=True,
                span_count=3,
                services=frozenset({"product-catalog"}),
                target_replicas=footprint,
            )
            for index, (success, footprint) in enumerate(zip(successes, footprints, strict=True))
        )
        return QualifiedCell(
            profile="opentelemetry_demo",
            placement="split",
            failure_law="N",
            repetition=0,
            target_service="product-catalog",
            learner_requests=requests,
            health=(),
            test_requests=(),
            test_health=(),
            boundary={},
            directory=Path("cell"),
        )

    def test_footprint_weights_are_outcome_blind(self) -> None:
        mode = SimpleNamespace(id="sampled_mixed", trace_keep_probability=1.0)
        analysis = SimpleNamespace(seed=17)
        first = _footprint_weights(self._cell((0, 0, 0)), mode, analysis, "checkout")
        second = _footprint_weights(self._cell((1, 1, 1)), mode, analysis, "checkout")
        for field in ("weight_a", "weight_b", "weight_a_b", "both_replica_fraction"):
            self.assertEqual(first[field], second[field])
            self.assertAlmostEqual(first[field], 1 / 3)
        self.assertFalse(first["outcomes_read_for_footprint"])

    def test_custom_or_likelihood_matches_frozen_m7_objective(self) -> None:
        frozen = load_frozen_live_validation_config(ROOT / "configs" / "m7_frozen_live.yaml")
        analysis = replace(
            frozen.analysis,
            minimum_operation_requests=5,
            minimum_trace_operation_support=5,
            minimum_replica_trace_assignments=1,
            minimum_pattern_observations=1,
        )
        mode = next(item for item in analysis.modes if item.id == "sampled_mixed")
        operations = tuple(item.id for item in analysis.operations["opentelemetry_demo"])
        requests: list[RequestRecord] = []
        for operation in operations:
            for index in range(12):
                requests.append(
                    RequestRecord(
                        period="baseline",
                        request_id=f"base-{operation}-{index}",
                        operation=operation,
                        at=900.0 + index,
                        success=1,
                        trace_present=True,
                        span_count=3,
                        services=frozenset({"frontend", "product-catalog"}),
                        target_replicas=frozenset({"a", "b"}),
                    )
                )
        ticks: list[HealthTick] = []
        for index in range(60):
            pa = int(index % 5 != 0)
            pb = int(index % 7 != 0)
            ticks.append(HealthTick(at=1000.0 + index, elapsed_seconds=index, signals=(pa, pb, pa, pb)))
            for operation_index, operation in enumerate(operations):
                requests.append(
                    RequestRecord(
                        period="calibration",
                        request_id=f"cal-{operation}-{index}",
                        operation=operation,
                        at=1000.0 + index + 0.05 * operation_index,
                        success=int(pa or pb),
                        trace_present=True,
                        span_count=3,
                        services=frozenset({"frontend", "product-catalog"}),
                        target_replicas=frozenset({"a", "b"}),
                    )
                )
        cell = QualifiedCell(
            profile="opentelemetry_demo",
            placement="split",
            failure_law="N",
            repetition=0,
            target_service="product-catalog",
            learner_requests=tuple(requests),
            health=tuple(ticks),
            test_requests=(),
            test_health=(),
            boundary={"usable": True},
            directory=Path("synthetic"),
        )
        prepared = prepare_mode(cell, mode, analysis)
        names = _parameter_names("N")
        values = np.asarray([0.82, 0.76], dtype=float)
        original = _negative_log_likelihood(
            values,
            names,
            _likelihood_data(prepared, "split", analysis),
            analysis.numerical_probability_floor,
        )
        custom = _candidate_objective(
            values,
            names,
            _candidate_likelihood_data(
                prepared,
                "split",
                "m7_single_demand_or",
                {"weight_a": 0.0, "weight_b": 0.0, "weight_a_b": 1.0},
                analysis.numerical_probability_floor,
            ),
        )
        self.assertAlmostEqual(original, custom, places=10)

    @staticmethod
    def _bootstrap(default_signed: float = 0.10) -> dict[str, dict[str, float]]:
        result: dict[str, dict[str, float]] = {}
        for method in ALL_METHODS:
            result[f"{method}.signed_error"] = {
                "estimate": default_signed,
                "lower": default_signed - 0.01,
                "upper": default_signed + 0.01,
            }
            if method != "m7_single_demand_or":
                result[f"{method}.delta_brier_vs_or"] = {
                    "estimate": -0.02,
                    "lower": -0.03,
                    "upper": -0.01,
                }
                result[f"{method}.delta_absolute_error_vs_or"] = {
                    "estimate": -0.05,
                    "lower": -0.06,
                    "upper": -0.04,
                }
        return result

    def test_frozen_decision_has_support_bracketing_and_overshoot_branches(self) -> None:
        supported = self._bootstrap()
        supported["learner_trace_requirement_mixture.signed_error"] = {
            "estimate": 0.0,
            "lower": -0.01,
            "upper": 0.01,
        }
        result = classify_evaluation(
            supported,
            integrity_passed=True,
            trace_gates_passed=True,
            bracketed_cells=40,
            closure_margin=0.03,
            minimum_bracketed=32,
        )
        self.assertEqual(result["branch"], "primary_supported")

        bracketed = self._bootstrap()
        bracketed["learner_trace_requirement_mixture.signed_error"] = {
            "estimate": -0.10,
            "lower": -0.12,
            "upper": -0.08,
        }
        bracketed["source_two_client_affinity.signed_error"] = {
            "estimate": 0.0,
            "lower": -0.01,
            "upper": 0.01,
        }
        result = classify_evaluation(
            bracketed,
            integrity_passed=True,
            trace_gates_passed=True,
            bracketed_cells=40,
            closure_margin=0.03,
            minimum_bracketed=32,
        )
        self.assertEqual(result["branch"], "bracketed_routing_law_unresolved")

        overshoot = self._bootstrap()
        overshoot["learner_trace_requirement_mixture.signed_error"] = {
            "estimate": -0.10,
            "lower": -0.12,
            "upper": -0.08,
        }
        result = classify_evaluation(
            overshoot,
            integrity_passed=True,
            trace_gates_passed=True,
            bracketed_cells=20,
            closure_margin=0.03,
            minimum_bracketed=32,
        )
        self.assertEqual(result["branch"], "primary_overshoots")

    def test_full_staging_is_rejected_outside_github_actions(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(CheckoutRoutingModelError, "only in GitHub Actions"):
                stage_learner_inputs(
                    CONFIG,
                    Path("contract.json"),
                    Path("qualified"),
                    Path("m8a"),
                    Path("out"),
                )


if __name__ == "__main__":
    unittest.main()
