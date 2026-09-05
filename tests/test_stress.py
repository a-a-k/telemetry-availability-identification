from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from telemetry_availability.stress import (
    branch_target_interval,
    circular_block_indices,
    exporter_loss_batch,
    fit_selection_aware_likelihood,
    full_batch,
    iid_latent_states,
    matched_two_domain_model,
    readiness_batch,
    readiness_implication_diagnostic,
    shared_domain_model,
    shared_domain_quantity_values,
    support_diagnostic,
)
from telemetry_availability.likelihood import (
    compress_observed_patterns,
    fit_exact_observed_likelihood,
)
from telemetry_availability.stress_config import REQUIRED_SERIES, load_stress_config
from telemetry_availability.stress_experiment import run_stress_experiment
from telemetry_availability.uncertainty import quantity_values


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m5_stress.yaml"


class StressConfigTests(unittest.TestCase):
    def test_contract_contains_all_directed_series(self) -> None:
        config = load_stress_config(CONFIG)
        self.assertEqual(tuple(item.id for item in config.series), REQUIRED_SERIES)
        self.assertEqual(config.sample_sizes, (500, 2000))
        self.assertEqual(config.repetitions, 200)

    def test_exporter_variants_preserve_marginal_retention(self) -> None:
        config = load_stress_config(CONFIG)
        model = next(
            item.model
            for item in config.transfer.scenarios
            if item.id == config.base_scenario
        )
        gamma = next(
            factor.probability for factor in model.factors if factor.id == "domain_a"
        )
        series = next(item for item in config.series if item.id == "exporter_loss")
        target = float(series.settings["target_trace_retention"])
        for variant in series.variants:
            marginal = (
                gamma * float(variant.parameters["retention_when_domain_up"])
                + (1.0 - gamma)
                * float(variant.parameters["retention_when_domain_down"])
            )
            self.assertAlmostEqual(marginal, target, places=12)


class StressMechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = load_stress_config(CONFIG)
        cls.model = next(
            item.model
            for item in config.transfer.scenarios
            if item.id == config.base_scenario
        )

    def test_shared_domain_keeps_marginals_and_removes_split_benefit(self) -> None:
        matched = matched_two_domain_model(self.model, 0.94)
        shared = shared_domain_model(matched)
        assumed_marginals = {
            "replica_a": matched.factor_probabilities[0] * matched.factor_probabilities[1],
            "replica_b": matched.factor_probabilities[0] * matched.factor_probabilities[2],
            "anchor_a": matched.factor_probabilities[3] * matched.factor_probabilities[4],
            "anchor_b": matched.factor_probabilities[3] * matched.factor_probabilities[5],
        }
        shared_map = {factor.id: factor.probability for factor in shared.factors}
        for factor_id, marginal in assumed_marginals.items():
            self.assertAlmostEqual(
                shared_map["shared_domain"] * shared_map[factor_id],
                marginal,
            )
        values = shared_domain_quantity_values(shared)
        self.assertEqual(values["change_split_minus_current"], 0.0)
        self.assertEqual(
            values["split_across_domains"],
            values["current_same_domain"],
        )
        self.assertGreater(
            quantity_values(matched)["change_split_minus_current"],
            0.0,
        )

    def test_readiness_control_satisfies_and_lag_violates_implication(self) -> None:
        control = readiness_batch(
            self.model,
            500,
            0.25,
            0,
            np.random.default_rng(11),
            np.random.default_rng(12),
        )
        delayed = readiness_batch(
            self.model,
            500,
            0.25,
            3,
            np.random.default_rng(11),
            np.random.default_rng(12),
        )
        self.assertFalse(readiness_implication_diagnostic(self.model, control).flagged)
        self.assertTrue(readiness_implication_diagnostic(self.model, delayed).flagged)

    def test_unseen_branch_produces_no_point_and_wide_range(self) -> None:
        branch = np.zeros(100, dtype=bool)
        success = np.ones(100, dtype=bool)
        interval, counts = branch_target_interval(branch, success, 0.5, 0.95, 20)
        self.assertEqual(counts, (100, 0))
        self.assertIsNone(interval.point)
        self.assertGreaterEqual(interval.width or 0.0, 0.5)
        self.assertTrue(support_diagnostic(counts, 20).flagged)

    def test_circular_blocks_have_requested_shape_and_bounds(self) -> None:
        indices = circular_block_indices(103, 20, np.random.default_rng(3))
        self.assertEqual(indices.shape, (103,))
        self.assertTrue(np.all(indices >= 0))
        self.assertTrue(np.all(indices < 103))

    def test_full_batch_matches_model_shape(self) -> None:
        latent = iid_latent_states(self.model, 7, np.random.default_rng(2))
        batch = full_batch(self.model, latent)
        self.assertEqual(batch.values.shape, (7, len(self.model.observables)))
        self.assertTrue(np.all(batch.observed))

    def test_selection_aware_likelihood_corrects_domain_coupled_mask(self) -> None:
        latent = iid_latent_states(self.model, 2500, np.random.default_rng(31))
        batch = exporter_loss_batch(
            self.model,
            latent,
            0.7414893617021276,
            0.05,
            np.random.default_rng(32),
            np.random.default_rng(33),
        )
        raw = fit_exact_observed_likelihood(
            self.model,
            compress_observed_patterns(self.model, batch),
        )
        aware = fit_selection_aware_likelihood(
            self.model,
            batch,
            0.7414893617021276,
            0.05,
        )
        self.assertTrue(raw.converged)
        self.assertTrue(aware.converged)
        self.assertIsNotNone(raw.probabilities)
        self.assertIsNotNone(aware.probabilities)
        gamma_truth = self.model.factor_probabilities[0]
        self.assertLess(
            abs(float(aware.probabilities[0]) - gamma_truth),
            abs(float(raw.probabilities[0]) - gamma_truth),
        )


class StressRunnerTests(unittest.TestCase):
    def test_bounded_rare_branch_smoke_writes_complete_tables(self) -> None:
        config = load_stress_config(CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_stress_experiment(
                config,
                CONFIG,
                directory,
                series_names=("rare_branch",),
                repetitions=1,
                sample_sizes=(100,),
                bootstrap_replicates=5,
            )
            self.assertEqual(manifest["row_counts"]["campaigns"], 3)
            self.assertEqual(manifest["row_counts"]["diagnostics"], 3)
            self.assertEqual(manifest["quality"]["invalid_intervals"], 0)
            for name in (
                "estimates.csv",
                "diagnostics.csv",
                "campaigns.csv",
                "summary.csv",
                "paired_effects.csv",
                "manifest.json",
            ):
                self.assertTrue((Path(directory) / name).is_file())

    def test_delayed_readiness_never_emits_an_inverted_interval(self) -> None:
        config = load_stress_config(CONFIG)
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_stress_experiment(
                config,
                CONFIG,
                directory,
                series_names=("readiness_lag",),
                repetitions=1,
                sample_sizes=(500,),
                bootstrap_replicates=5,
            )
            self.assertEqual(manifest["quality"]["invalid_intervals"], 0)


if __name__ == "__main__":
    unittest.main()
