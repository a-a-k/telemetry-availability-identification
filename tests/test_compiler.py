from __future__ import annotations

import unittest
import csv
import json
import tempfile
from pathlib import Path

import numpy as np

from telemetry_availability.compiler import (
    IdentificationStatus,
    compile_observation_model,
    exact_observable_distribution,
)
from telemetry_availability.config import load_config
from telemetry_availability.reduction_experiment import run_reduction_experiment


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "rq1_synthetic.yaml"


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG_PATH)

    def family(self, name: str):
        return next(item for item in self.config.families if item.id == name)

    def policy(self, name: str):
        return next(item for item in self.config.observation_modes if item.id == name)

    def test_trace_only_fanout_collapses_to_three_identified_products(self) -> None:
        compiled = compile_observation_model(
            self.family("mandatory_fanout"),
            self.policy("trace_only"),
        )
        self.assertIsNotNone(compiled.reduced_model)
        self.assertEqual(len(compiled.original_model.factors), 6)
        self.assertEqual(len(compiled.reduced_model.factors), 3)
        self.assertEqual(compiled.original_state_count, 64)
        self.assertEqual(compiled.reduced_state_count, 8)
        self.assertTrue(compiled.reduced_report.full_rank)
        self.assertEqual(
            compiled.target_status["fanout_success"],
            IdentificationStatus.PROVED_IDENTIFIABLE,
        )

    def test_reduction_preserves_supported_observable_distribution(self) -> None:
        for family in self.config.families:
            for policy in self.config.observation_modes:
                compiled = compile_observation_model(family, policy)
                if compiled.reduced_model is None:
                    continue
                supported_original = type(family)(
                    id=f"{family.id}-supported",
                    factors=family.factors,
                    observables=tuple(
                        family.observables[position]
                        for position in compiled.observable_positions
                    ),
                    targets=(),
                )
                original_distribution = exact_observable_distribution(supported_original)
                reduced_distribution = exact_observable_distribution(compiled.reduced_model)
                self.assertEqual(set(original_distribution), set(reduced_distribution))
                for state in original_distribution:
                    self.assertAlmostEqual(
                        original_distribution[state],
                        reduced_distribution[state],
                        places=12,
                    )

    def test_represented_target_truth_is_preserved(self) -> None:
        for family in self.config.families:
            for policy in self.config.observation_modes:
                compiled = compile_observation_model(family, policy)
                if compiled.reduced_model is None:
                    continue
                for target in family.targets:
                    mapped = compiled.target_reduced_factors[target.id]
                    if mapped is None:
                        continue
                    self.assertAlmostEqual(
                        family.exact_target(target.id),
                        compiled.reduced_model.exact_target(target.id),
                        places=12,
                    )

    def test_ambiguity_witness_preserves_observations_but_changes_target(self) -> None:
        compiled = compile_observation_model(
            self.family("same_domain_replicas"),
            self.policy("no_joint_health"),
        )
        self.assertEqual(
            compiled.target_status["both_replicas_live"],
            IdentificationStatus.PROVED_AMBIGUOUS,
        )
        witness = compiled.target_witnesses["both_replicas_live"]
        self.assertLess(witness.max_observable_moment_difference, 1e-12)
        self.assertGreater(abs(witness.first_quantity - witness.second_quantity), 1e-3)
        self.assertEqual(set(compiled.parameter_witnesses), set(compiled.original_model.factor_ids))

    def test_no_supported_observable_has_no_reduced_model(self) -> None:
        compiled = compile_observation_model(
            self.family("same_domain_replicas"),
            self.policy("trace_only"),
        )
        self.assertIsNone(compiled.reduced_model)
        self.assertEqual(set(compiled.inactive_factors), set(compiled.original_model.factor_ids))

    def test_reduction_experiment_matches_reference_objective(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest = run_reduction_experiment(
                config=self.config,
                config_path=CONFIG_PATH,
                output_directory=temporary,
                family_names=("mandatory_fanout",),
                mode_names=("trace_only",),
                repetitions=1,
                sample_sizes=(100,),
            )
            self.assertEqual(manifest["objective_equivalence_failures"], 0)
            self.assertEqual(manifest["row_counts"]["fits"], 2)
            with (Path(temporary) / "compiler.csv").open(
                "r", encoding="utf-8", newline=""
            ) as source:
                compiler = list(csv.DictReader(source))[0]
            self.assertEqual(int(compiler["original_state_count"]), 64)
            self.assertEqual(int(compiler["reduced_state_count"]), 8)
            groups = json.loads(compiler["factor_groups_json"])
            self.assertEqual(len(groups), 3)


if __name__ == "__main__":
    unittest.main()
