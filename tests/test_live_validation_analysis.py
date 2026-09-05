from __future__ import annotations

import math
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from telemetry_availability.live_validation_analysis import (
    EvaluationRequest,
    HealthTick,
    QualifiedCell,
    RequestRecord,
    fit_exact_model,
    predict_cell,
    prepare_mode,
    route_probability,
)
from telemetry_availability.live_validation_config import (
    load_frozen_live_validation_config,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m7_frozen_live.yaml"


class FrozenLiveAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_frozen_live_validation_config(CONFIG_PATH)
        cls.analysis = replace(
            cls.config.analysis,
            optimizer_starts=4,
            optimizer_max_iterations=300,
            minimum_signal_observations=10,
            minimum_pattern_observations=5,
            minimum_operation_requests=10,
            minimum_trace_operation_support=10,
            minimum_replica_trace_assignments=2,
            multistart_prediction_tolerance=0.01,
        )
        cls.cell = cls._synthetic_cell()

    @classmethod
    def _synthetic_cell(cls) -> QualifiedCell:
        generator = np.random.default_rng(705)
        start = 1_800_000_000.0
        health = []
        test_health = []
        learner = []
        evaluation = []
        operations = tuple(item.id for item in cls.analysis.operations["opentelemetry_demo"])
        for operation_index, operation in enumerate(operations):
            for index in range(30):
                learner.append(
                    RequestRecord(
                        period="baseline",
                        request_id=f"base-{operation}-{index}",
                        operation=operation,
                        at=start - 60 + index,
                        success=int(index != 0),
                        trace_present=True,
                        span_count=3,
                        services=frozenset({"frontend", "product-catalog"}),
                        target_replicas=frozenset({"a" if index % 2 == 0 else "b"}),
                    )
                )
        for index in range(240):
            g = int(generator.random() < 0.84)
            ea = int(generator.random() < 0.91)
            eb = int(generator.random() < 0.88)
            ca = int(generator.random() < 0.93)
            cb = int(generator.random() < 0.90)
            signals = (g * ea, g * eb, g * ea * ca, g * eb * cb)
            health.append(HealthTick(start + index, float(index), signals))
            test_health.append(
                HealthTick(start + 1000 + index, float(index), signals)
            )
            route = int(signals[2] or signals[3])
            for operation_index, operation in enumerate(operations):
                success = int(route and generator.random() < 0.96)
                learner.append(
                    RequestRecord(
                        period="calibration",
                        request_id=f"cal-{operation}-{index}",
                        operation=operation,
                        at=start + index + 0.1 + operation_index * 0.05,
                        success=success,
                        trace_present=True,
                        span_count=4,
                        services=frozenset({"frontend", "product-catalog"}),
                        target_replicas=frozenset({"a" if index % 2 == 0 else "b"}),
                    )
                )
                evaluation.append(
                    EvaluationRequest(
                        operation=operation,
                        at=start + 1000 + index + 0.1 + operation_index * 0.05,
                        success=int(route and generator.random() < 0.96),
                    )
                )
        return QualifiedCell(
            profile="opentelemetry_demo",
            placement="colocated",
            failure_law="NCD",
            repetition=0,
            target_service="product-catalog",
            learner_requests=tuple(learner),
            health=tuple(health),
            test_requests=tuple(evaluation),
            test_health=tuple(test_health),
            boundary={"usable": True},
            directory=Path("synthetic"),
        )

    def test_route_formula_distinguishes_colocated_and_split_domains(self) -> None:
        parameters = {"g": 0.8, "ea": 0.9, "eb": 0.85, "ca": 0.95, "cb": 0.9}
        colocated = route_probability(parameters, "colocated")
        split = route_probability(parameters, "split")
        expected_colocated = 0.8 * (
            1 - (1 - 0.9 * 0.95) * (1 - 0.85 * 0.9)
        )
        expected_split = 1 - (1 - 0.8 * 0.9 * 0.95) * (
            1 - 0.8 * 0.85 * 0.9
        )
        self.assertAlmostEqual(colocated, expected_colocated)
        self.assertAlmostEqual(split, expected_split)
        self.assertGreater(split, colocated)

    def test_masks_are_deterministic_and_staggering_has_no_joint_replica(self) -> None:
        mode_lookup = {mode.id: mode for mode in self.analysis.modes}
        first = prepare_mode(self.cell, mode_lookup["sampled_mixed"], self.analysis)
        second = prepare_mode(self.cell, mode_lookup["sampled_mixed"], self.analysis)
        self.assertEqual(first.ticks, second.ticks)
        staggered = prepare_mode(
            self.cell, mode_lookup["no_joint_health"], self.analysis
        )
        for tick in staggered.ticks:
            observed_a = tick.observed[0] is not None or tick.observed[2] is not None
            observed_b = tick.observed[1] is not None or tick.observed[3] is not None
            self.assertNotEqual(observed_a, observed_b)
        trace_only = prepare_mode(
            self.cell, mode_lookup["trace_only"], self.analysis
        )
        self.assertTrue(
            all(all(value is None for value in tick.observed) for tick in trace_only.ticks)
        )

    def test_matched_b3_and_proposed_predictions_agree_when_identified(self) -> None:
        mode = next(item for item in self.analysis.modes if item.id == "full")
        prepared = prepare_mode(self.cell, mode, self.analysis)
        self.assertTrue(
            all(item.status == "confirmed" for item in prepared.topology.values())
        )
        fit = fit_exact_model(self.cell, prepared, self.analysis)
        self.assertIsNotNone(fit.best)
        self.assertTrue(math.isfinite(fit.best.nll))  # type: ignore[union-attr]
        self.assertTrue(fit.current_identified)
        current = predict_cell(self.cell, prepared, fit, self.analysis, "current")
        b3 = {
            row["operation"]: float(row["prediction"])
            for row in current
            if row["method"] == "B3"
        }
        proposed = {
            row["operation"]: float(row["prediction"])
            for row in current
            if row["method"] == "proposed"
        }
        self.assertEqual(b3, proposed)

    def test_trace_only_guards_transfer_but_retains_direct_endpoint(self) -> None:
        mode = next(item for item in self.analysis.modes if item.id == "trace_only")
        prepared = prepare_mode(self.cell, mode, self.analysis)
        fit = fit_exact_model(self.cell, prepared, self.analysis)
        current = predict_cell(self.cell, prepared, fit, self.analysis, "current")
        transfer = predict_cell(self.cell, prepared, fit, self.analysis, "transfer")
        b2_current = [row for row in current if row["method"] == "B2"]
        self.assertTrue(all(row["prediction"] != "" for row in b2_current))
        proposed_transfer = [
            row for row in transfer if row["method"] == "proposed"
        ]
        self.assertTrue(all(row["prediction"] == "" for row in proposed_transfer))
        b4_transfer = [row for row in transfer if row["method"] == "B4"]
        self.assertTrue(all(row["prediction"] == "" for row in b4_transfer))


if __name__ == "__main__":
    unittest.main()
