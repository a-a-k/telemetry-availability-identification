from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from telemetry_availability.likelihood import (
    compress_observed_patterns,
    fit_exact_observed_likelihood,
)
from telemetry_availability.observation import simulate_batch
from telemetry_availability.transfer import TARGET_SPLIT
from telemetry_availability.uncertainty import (
    CHOICE_DIFFERENCE,
    DELTA_ADD,
    QUANTITIES,
    clopper_pearson_interval,
    extract_simultaneous_evidence,
    likelihood_wald_ranges,
    quantity_values,
    simultaneous_target_ranges,
)
from telemetry_availability.uncertainty_config import load_uncertainty_config
from telemetry_availability.uncertainty_experiment import (
    aggregate_uncertainty_experiment,
    run_uncertainty_experiment,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "m4_uncertainty.yaml"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


class UncertaintyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_uncertainty_config(CONFIG_PATH)
        cls.scenario = cls.config.transfer.scenarios[1]
        cls.policies = {
            policy.id: policy
            for policy in cls.config.transfer.observation_modes
        }

    def _batch(self, mode: str, count: int = 500):
        return simulate_batch(
            self.scenario.model,
            count,
            self.policies[mode],
            np.random.default_rng(71),
            np.random.default_rng(72),
        )

    def test_clopper_pearson_handles_boundary_counts(self) -> None:
        lower, upper = clopper_pearson_interval(0, 100, 0.95)
        self.assertEqual(lower, 0.0)
        self.assertGreater(upper, 0.0)
        lower, upper = clopper_pearson_interval(100, 100, 0.95)
        self.assertLess(lower, 1.0)
        self.assertEqual(upper, 1.0)

    def test_evidence_uses_joint_health_union_without_duplicate_trace(self) -> None:
        expected = {
            "full": 8,
            "sampled_mixed": 10,
            "joint_health_only": 8,
            "no_joint_health": 6,
            "trace_only": 2,
        }
        for mode, count in expected.items():
            with self.subTest(mode=mode):
                _, _, evidence = extract_simultaneous_evidence(
                    self.scenario.model,
                    self._batch(mode),
                    self.config.confidence_level,
                )
                self.assertEqual(len(evidence), count)

    def test_outer_ranges_cover_truth_when_observable_set_does(self) -> None:
        truths = quantity_values(self.scenario.model)
        for mode in ("full", "sampled_mixed", "no_joint_health"):
            with self.subTest(mode=mode):
                batch = self._batch(mode, 2_000)
                domain_a, domain_b, evidence = extract_simultaneous_evidence(
                    self.scenario.model,
                    batch,
                    self.config.confidence_level,
                )
                self.assertTrue(all(item.covers_truth for item in evidence))
                result = simultaneous_target_ranges(
                    self.scenario.model,
                    self.policies[mode],
                    domain_a,
                    domain_b,
                    self.config.branch_tolerance,
                    self.config.branch_max_nodes_per_domain,
                )
                for quantity in QUANTITIES:
                    interval = result.intervals[quantity]
                    self.assertLessEqual(interval.lower, truths[quantity])
                    self.assertGreaterEqual(interval.upper, truths[quantity])

    def test_trace_only_returns_informative_current_but_broad_transfer(self) -> None:
        batch = self._batch("trace_only")
        domain_a, domain_b, _ = extract_simultaneous_evidence(
            self.scenario.model,
            batch,
            self.config.confidence_level,
        )
        result = simultaneous_target_ranges(
            self.scenario.model,
            self.policies["trace_only"],
            domain_a,
            domain_b,
            self.config.branch_tolerance,
            self.config.branch_max_nodes_per_domain,
        )
        self.assertEqual(result.intervals[TARGET_SPLIT].lower, 0.0)
        self.assertEqual(result.intervals[TARGET_SPLIT].upper, 1.0)
        self.assertEqual(result.intervals[CHOICE_DIFFERENCE].lower, -1.0)
        self.assertEqual(result.intervals[CHOICE_DIFFERENCE].upper, 1.0)
        self.assertEqual(result.intervals[DELTA_ADD].lower, 0.0)

    def test_wald_reference_is_available_for_identified_full_model(self) -> None:
        batch = self._batch("full")
        table = compress_observed_patterns(self.scenario.model, batch)
        fit = fit_exact_observed_likelihood(self.scenario.model, table)
        intervals = likelihood_wald_ranges(
            self.scenario.model,
            table,
            fit,
            self.config.confidence_level,
            simultaneous=True,
        )
        self.assertTrue(all(item.lower is not None for item in intervals.values()))
        self.assertTrue(all(item.upper >= item.lower for item in intervals.values()))

    def test_runner_and_aggregate_preserve_quality_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for scenario in ("weak_common_cause", "strong_common_cause"):
                run_uncertainty_experiment(
                    config=self.config,
                    config_path=CONFIG_PATH,
                    output_directory=root / scenario,
                    scenario_names=(scenario,),
                    mode_names=("full", "trace_only"),
                    repetitions=1,
                    sample_sizes=(100,),
                )
            aggregate = root.parent / f"{root.name}-aggregate"
            manifest = aggregate_uncertainty_experiment(root, aggregate)
            self.assertEqual(manifest["row_counts"]["sets"], 4)
            self.assertEqual(manifest["row_counts"]["intervals"], 120)
            self.assertTrue(all(value == 0 for value in manifest["quality"].values()))
            stored = json.loads((aggregate / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["source_shards"], 2)
            trace = [
                row
                for row in read_rows(aggregate / "intervals.csv")
                if row["observation_mode"] == "trace_only"
                and row["method"] == "proposed_simultaneous_observation_set"
                and row["quantity"] == TARGET_SPLIT
            ]
            self.assertTrue(all(row["width"] == "1.0" for row in trace))

    def test_local_execution_policy_rejects_frozen_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "os.environ",
            {"GITHUB_ACTIONS": ""},
        ):
            with self.assertRaisesRegex(RuntimeError, "GitHub Actions"):
                run_uncertainty_experiment(
                    config=self.config,
                    config_path=CONFIG_PATH,
                    output_directory=temporary,
                )


if __name__ == "__main__":
    unittest.main()
