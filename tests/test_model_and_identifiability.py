from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from telemetry_availability.config import load_config
from telemetry_availability.diagnostics import diagnose_identifiability
from telemetry_availability.estimators import fit_log_moments
from telemetry_availability.moments import (
    MomentEstimate,
    canonical_moment_estimates,
    structural_moment_rows,
)
from telemetry_availability.model import ConjunctiveModel, Factor, Observable, Target


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "rq1_synthetic.yaml"


class ModelTests(unittest.TestCase):
    def test_exact_joint_moment_uses_union_of_factors(self) -> None:
        model = ConjunctiveModel(
            id="pair",
            factors=(
                Factor("domain", 0.9, "domain"),
                Factor("a", 0.8, "instance_residual"),
                Factor("b", 0.7, "instance_residual"),
            ),
            observables=(
                Observable("health_a", ("domain", "a"), "health"),
                Observable("health_b", ("domain", "b"), "health"),
            ),
            targets=(Target("both", ("domain", "a", "b")),),
        )

        self.assertAlmostEqual(model.exact_moment(("health_a",)), 0.9 * 0.8)
        self.assertAlmostEqual(
            model.exact_moment(("health_a", "health_b")),
            0.9 * 0.8 * 0.7,
        )

    def test_joint_health_changes_structural_rank(self) -> None:
        config = load_config(CONFIG_PATH)
        family = next(item for item in config.families if item.id == "same_domain_replicas")
        full = next(item for item in config.observation_modes if item.id == "full")
        staggered = next(item for item in config.observation_modes if item.id == "no_joint_health")

        full_report = diagnose_identifiability(
            family,
            structural_moment_rows(family, full, config.max_moment_order),
        )
        staggered_report = diagnose_identifiability(
            family,
            structural_moment_rows(family, staggered, config.max_moment_order),
        )

        self.assertEqual(full_report.rank, 3)
        self.assertTrue(full_report.full_rank)
        self.assertTrue(full_report.target_identifiable["both_replicas_live"])
        self.assertEqual(staggered_report.rank, 2)
        self.assertFalse(staggered_report.full_rank)
        self.assertFalse(staggered_report.target_identifiable["both_replicas_live"])

    def test_current_target_can_be_identifiable_without_parameters(self) -> None:
        config = load_config(CONFIG_PATH)
        family = next(item for item in config.families if item.id == "mandatory_fanout")
        trace_only = next(item for item in config.observation_modes if item.id == "trace_only")
        report = diagnose_identifiability(
            family,
            structural_moment_rows(family, trace_only, config.max_moment_order),
        )

        self.assertLess(report.rank, report.parameter_count)
        self.assertTrue(report.target_identifiable["fanout_success"])
        self.assertFalse(all(report.parameter_identifiable.values()))

    def test_log_moment_fit_recovers_exact_identifiable_parameters(self) -> None:
        config = load_config(CONFIG_PATH)
        family = next(item for item in config.families if item.id == "same_domain_replicas")
        definitions = (
            ("health_a",),
            ("health_b",),
            ("health_a", "health_b"),
        )
        estimates = tuple(
            MomentEstimate(
                observable_ids=definition,
                factor_vector=family.factor_vector(
                    family.factors_for_observables(definition)
                ),
                value=family.exact_moment(definition),
                observation_count=1000,
            )
            for definition in definitions
        )
        matrix = np.vstack([item.factor_vector for item in estimates])
        report = diagnose_identifiability(family, matrix)
        fit = fit_log_moments(family, estimates, report)

        self.assertEqual(fit.status, "full_rank")
        for factor in family.factors:
            self.assertAlmostEqual(
                fit.parameter_estimates[factor.id],
                factor.probability,
                places=12,
            )
        self.assertAlmostEqual(
            fit.target_estimates["both_replicas_live"],
            family.exact_target("both_replicas_live"),
            places=12,
        )

    def test_duplicate_factor_union_uses_highest_exposure_representative(self) -> None:
        first = MomentEstimate(
            observable_ids=("request",),
            factor_vector=np.asarray([1.0, 1.0]),
            value=0.7,
            observation_count=80,
        )
        second = MomentEstimate(
            observable_ids=("call", "request"),
            factor_vector=np.asarray([1.0, 1.0]),
            value=0.75,
            observation_count=100,
        )

        selected = canonical_moment_estimates((first, second))

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].observable_ids, ("call", "request"))


if __name__ == "__main__":
    unittest.main()
