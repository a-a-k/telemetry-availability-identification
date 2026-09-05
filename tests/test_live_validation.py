from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.live_stochastic_pilot import StochasticPilotError
from telemetry_availability.live_validation import (
    frozen_live_matrix,
    frozen_live_preflight_matrix,
    run_frozen_live_cell,
)
from telemetry_availability.live_validation_config import (
    EXPECTED_METHODS,
    load_frozen_live_validation_config,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIRECTORY = ROOT / "configs"


class FrozenLiveValidationTests(unittest.TestCase):
    def _write_config(self, directory: Path) -> Path:
        for name in (
            "m7_frozen_live.yaml",
            "m7c_stochastic_freeze_pilot.yaml",
            "m7b_placement_pilot.yaml",
            "m7_runtime_pilot.yaml",
        ):
            shutil.copyfile(CONFIG_DIRECTORY / name, directory / name)
        return directory / "m7_frozen_live.yaml"

    def test_freeze_hash_and_matrix_are_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_config(Path(temporary))
            config = load_frozen_live_validation_config(path)
        self.assertTrue(config.main_effectiveness)
        self.assertFalse(config.stochastic.pilot_only)
        self.assertEqual(config.stochastic.period_seconds, 900)
        self.assertEqual(config.repetitions, 10)
        self.assertEqual(config.stochastic.pilot_base_seed, 770034)
        self.assertEqual(config.resource_recovery_run_id, "33982201605")
        self.assertEqual(config.analysis.methods, EXPECTED_METHODS)
        self.assertEqual(config.analysis.primary_metric, "brier_score")
        self.assertEqual(config.analysis.block_length_seconds, 23)
        self.assertEqual(config.preflight_base_seed, 770036)
        self.assertNotEqual(config.preflight_request_namespace, config.request_namespace)
        matrix = frozen_live_matrix(config)
        self.assertEqual(len(matrix), 160)
        identities = {
            (
                row["profile"],
                row["placement"],
                row["law"],
                row["repetition"],
            )
            for row in matrix
        }
        self.assertEqual(len(identities), len(matrix))
        self.assertTrue(all(not row["repository"].endswith(".git") for row in matrix))
        preflight = frozen_live_preflight_matrix(config)
        self.assertEqual(len(preflight), 4)
        self.assertEqual({row["law"] for row in preflight}, {"NCD"})
        self.assertEqual({row["repetition"] for row in preflight}, {0})

    def test_main_runtime_is_forbidden_locally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = self._write_config(Path(temporary))
            config = load_frozen_live_validation_config(path)
            with self.assertRaises(StochasticPilotError):
                run_frozen_live_cell(
                    config,
                    "deathstarbench_social_network",
                    "colocated",
                    "N",
                    0,
                    "missing-checkout",
                    "missing-compose",
                    "missing-audit",
                    Path(temporary) / "output",
                )


if __name__ == "__main__":
    unittest.main()
