from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from scipy.optimize import OptimizeResult
from scipy.special import logit

from telemetry_availability.config import load_config
from telemetry_availability.likelihood import (
    compress_observed_patterns,
    exact_target_probability,
    fit_exact_observed_likelihood,
    negative_log_likelihood,
    negative_log_likelihood_and_gradient,
)
from telemetry_availability.likelihood_reference import run_likelihood_reference
from telemetry_availability.model import ConjunctiveModel, Factor, Observable, Target
from telemetry_availability.observation import EpisodeBatch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "rq1_synthetic.yaml"


class ExactLikelihoodTests(unittest.TestCase):
    def test_analytic_gradient_matches_central_difference(self) -> None:
        config = load_config(CONFIG_PATH)
        model = next(item for item in config.families if item.id == "same_domain_replicas")
        batch = EpisodeBatch(
            values=np.asarray(
                [[False, False], [False, True], [True, False], [True, True]],
                dtype=bool,
            ),
            observed=np.ones((4, 2), dtype=bool),
        )
        table = compress_observed_patterns(model, batch)
        point = logit(np.asarray([0.81, 0.73, 0.69]))
        _, analytic = negative_log_likelihood_and_gradient(point, table)
        numerical = np.zeros_like(point)
        step = 1e-6
        for index in range(len(point)):
            left = point.copy()
            right = point.copy()
            left[index] -= step
            right[index] += step
            left_value, _ = negative_log_likelihood_and_gradient(left, table)
            right_value, _ = negative_log_likelihood_and_gradient(right, table)
            numerical[index] = (right_value - left_value) / (2.0 * step)
        np.testing.assert_allclose(analytic, numerical, rtol=1e-6, atol=1e-7)

    def test_single_factor_likelihood_recovers_empirical_probability(self) -> None:
        model = ConjunctiveModel(
            id="single",
            factors=(Factor("instance", 0.7, "instance_residual"),),
            observables=(Observable("health", ("instance",), "health"),),
            targets=(Target("live", ("instance",)),),
        )
        batch = EpisodeBatch(
            values=np.asarray([[True]] * 7 + [[False]] * 3, dtype=bool),
            observed=np.ones((10, 1), dtype=bool),
        )
        fit = fit_exact_observed_likelihood(model, compress_observed_patterns(model, batch))
        self.assertTrue(fit.converged)
        self.assertIsNotNone(fit.probabilities)
        self.assertAlmostEqual(float(fit.probabilities[0]), 0.7, places=7)

    def test_multistart_prefers_successful_solution_with_equivalent_objective(self) -> None:
        model = ConjunctiveModel(
            id="single",
            factors=(Factor("instance", 0.7, "instance_residual"),),
            observables=(Observable("health", ("instance",), "health"),),
            targets=(Target("live", ("instance",)),),
        )
        batch = EpisodeBatch(
            values=np.asarray([[True], [False]], dtype=bool),
            observed=np.ones((2, 1), dtype=bool),
        )
        table = compress_observed_patterns(model, batch)
        failed = OptimizeResult(
            x=logit(np.asarray([0.7])),
            fun=10.0,
            jac=np.asarray([1e-6]),
            nit=3,
            success=False,
            message="abnormal line search termination",
        )
        successful = OptimizeResult(
            x=logit(np.asarray([0.7000001])),
            fun=10.0 + 1e-10,
            jac=np.asarray([1e-8]),
            nit=4,
            success=True,
            message="converged",
        )
        with patch(
            "telemetry_availability.likelihood.minimize",
            side_effect=(failed, successful, successful),
        ):
            fit = fit_exact_observed_likelihood(model, table)
        self.assertTrue(fit.converged)
        self.assertEqual(fit.status, "converged")
        self.assertAlmostEqual(float(fit.negative_log_likelihood), 10.0 + 1e-10)
        self.assertEqual(fit.successful_starts, 2)

    def test_staggered_same_domain_has_equal_likelihood_on_parameter_ridge(self) -> None:
        config = load_config(CONFIG_PATH)
        model = next(item for item in config.families if item.id == "same_domain_replicas")
        batch = EpisodeBatch(
            values=np.asarray(
                [[True, False], [False, True], [False, False], [False, False]],
                dtype=bool,
            ),
            observed=np.asarray(
                [[True, False], [False, True], [True, False], [False, True]],
                dtype=bool,
            ),
        )
        table = compress_observed_patterns(model, batch)
        first = np.asarray([0.9, 0.8, 0.7])
        second = np.asarray([0.8, 0.9, 0.7875])
        self.assertAlmostEqual(
            negative_log_likelihood(first, table),
            negative_log_likelihood(second, table),
            places=12,
        )

    def test_target_oracle_uses_state_enumeration(self) -> None:
        config = load_config(CONFIG_PATH)
        model = next(item for item in config.families if item.id == "mandatory_fanout")
        target = model.targets[0]
        self.assertAlmostEqual(
            exact_target_probability(model, target.factors),
            model.exact_target(target.id),
            places=12,
        )

    def test_reference_runner_writes_matched_method_rows(self) -> None:
        config = load_config(CONFIG_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            manifest = run_likelihood_reference(
                config=config,
                config_path=CONFIG_PATH,
                output_directory=temporary,
                family_names=("same_domain_replicas",),
                mode_names=("full",),
                repetitions=1,
                sample_sizes=(100,),
            )
            self.assertEqual(manifest["row_counts"]["fits"], 2)
            self.assertEqual(manifest["row_counts"]["estimates"], 8)
            self.assertEqual(manifest["row_counts"]["summary"], 2)
            self.assertEqual(manifest["row_counts"]["paired_summary"], 1)


if __name__ == "__main__":
    unittest.main()
