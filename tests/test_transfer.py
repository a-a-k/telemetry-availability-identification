from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from telemetry_availability.observation import simulate_batch, simulate_observable_values
from telemetry_availability.transfer import (
    TARGET_ADD,
    TARGET_SPLIT,
    fit_available_domain_moments,
    transfer_probabilities,
)
from telemetry_availability.transfer_config import load_transfer_config
from telemetry_availability.transfer_experiment import (
    METHOD_B3,
    METHOD_PROPOSED,
    run_transfer_experiment,
)
from telemetry_availability.transfer_identifiability import (
    PROVED_AMBIGUOUS,
    PROVED_IDENTIFIABLE,
    ambiguity_witnesses,
    diagnose_transfer_targets,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "m3_transfer.yaml"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


class TransferDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_transfer_config(CONFIG_PATH)

    def test_scenarios_hold_health_marginals_fixed_but_reverse_choice(self) -> None:
        truths = {
            scenario.id: transfer_probabilities(scenario.model)
            for scenario in self.config.scenarios
        }
        for scenario in self.config.scenarios:
            factors = {factor.id: factor.probability for factor in scenario.model.factors}
            self.assertAlmostEqual(factors["domain_a"] * factors["replica_a"], 0.90)
            self.assertAlmostEqual(factors["domain_a"] * factors["replica_b"], 0.88)
            self.assertAlmostEqual(factors["domain_b"] * factors["anchor_a"], 0.91)
            self.assertAlmostEqual(factors["domain_b"] * factors["anchor_b"], 0.89)
        self.assertGreater(
            truths["weak_common_cause"][TARGET_ADD],
            truths["weak_common_cause"][TARGET_SPLIT],
        )
        for name in ("medium_common_cause", "strong_common_cause"):
            self.assertGreater(truths[name][TARGET_SPLIT], truths[name][TARGET_ADD])

    def test_boolean_trace_is_or_of_replica_health(self) -> None:
        model = self.config.scenarios[0].model
        values = simulate_observable_values(model, 500, np.random.default_rng(17))
        positions = {
            observable.id: index
            for index, observable in enumerate(model.observables)
        }
        np.testing.assert_array_equal(
            values[:, positions["current_success"]],
            values[:, positions["replica_a_health"]]
            | values[:, positions["replica_b_health"]],
        )
        np.testing.assert_array_equal(
            values[:, positions["anchor_success"]],
            values[:, positions["anchor_a_health"]]
            | values[:, positions["anchor_b_health"]],
        )

    def test_heterogeneous_marginals_and_traces_identify_transfer(self) -> None:
        policies = {policy.id: policy for policy in self.config.observation_modes}
        no_joint = diagnose_transfer_targets(policies["no_joint_health"])
        trace_only = diagnose_transfer_targets(policies["trace_only"])
        self.assertEqual(no_joint[TARGET_SPLIT].status, PROVED_IDENTIFIABLE)
        self.assertEqual(no_joint[TARGET_ADD].status, PROVED_IDENTIFIABLE)
        self.assertEqual(trace_only[TARGET_SPLIT].status, PROVED_AMBIGUOUS)
        self.assertEqual(trace_only[TARGET_ADD].status, PROVED_AMBIGUOUS)

    def test_ambiguity_witness_preserves_supported_distribution(self) -> None:
        scenario = self.config.scenarios[1]
        policy = next(
            item for item in self.config.observation_modes if item.id == "trace_only"
        )
        witnesses = ambiguity_witnesses(scenario.model, policy)
        self.assertEqual({item.target for item in witnesses}, {TARGET_SPLIT, TARGET_ADD})
        for witness in witnesses:
            self.assertLess(witness.max_observable_difference, 1e-12)
            self.assertGreater(abs(witness.first_target - witness.second_target), 1e-4)

    def test_available_moment_baseline_uses_trace_closure(self) -> None:
        scenario = self.config.scenarios[1]
        policy = next(
            item
            for item in self.config.observation_modes
            if item.id == "no_joint_health"
        )
        batch = simulate_batch(
            scenario.model,
            10_000,
            policy,
            np.random.default_rng(31),
            np.random.default_rng(32),
        )
        fit = fit_available_domain_moments(scenario.model, batch, minimum=100)
        self.assertIsNotNone(fit.probabilities)
        self.assertIn("health_marginals_plus_or_trace", fit.source)
        truth = {factor.id: factor.probability for factor in scenario.model.factors}
        for factor_id, estimate in fit.probabilities.items():
            self.assertAlmostEqual(estimate, truth[factor_id], delta=0.05)

    def test_runner_keeps_raw_b3_point_but_gates_ambiguous_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = run_transfer_experiment(
                config=self.config,
                config_path=CONFIG_PATH,
                output_directory=temporary,
                scenario_names=("medium_common_cause",),
                mode_names=("full", "trace_only"),
                repetitions=1,
                sample_sizes=(100,),
                validation_episodes=100,
            )
            output = Path(temporary)
            predictions = read_rows(output / "predictions.csv")
            trace_transfer = [
                row
                for row in predictions
                if row["observation_mode"] == "trace_only"
                and row["target"] in {TARGET_SPLIT, TARGET_ADD}
            ]
            b3 = [row for row in trace_transfer if row["method"] == METHOD_B3]
            proposed = [
                row for row in trace_transfer if row["method"] == METHOD_PROPOSED
            ]
            self.assertTrue(all(row["estimate"] for row in b3))
            self.assertTrue(all(not row["estimate"] for row in proposed))
            self.assertEqual(manifest["row_counts"]["fits"], 12)
            self.assertEqual(manifest["row_counts"]["witnesses"], 2)

    def test_local_execution_policy_rejects_frozen_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "os.environ",
            {"GITHUB_ACTIONS": ""},
        ):
            with self.assertRaisesRegex(RuntimeError, "GitHub Actions"):
                run_transfer_experiment(
                    config=self.config,
                    config_path=CONFIG_PATH,
                    output_directory=temporary,
                )


if __name__ == "__main__":
    unittest.main()
