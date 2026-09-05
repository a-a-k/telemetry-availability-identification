from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.config import load_config
from telemetry_availability.runner import aggregate_results, run_experiment


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPOSITORY_ROOT / "configs" / "rq1_synthetic.yaml"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


class RunnerTests(unittest.TestCase):
    def test_local_execution_policy_rejects_full_matrix(self) -> None:
        config = load_config(CONFIG_PATH)
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            "os.environ",
            {"GITHUB_ACTIONS": ""},
        ):
            with self.assertRaisesRegex(RuntimeError, "GitHub Actions"):
                run_experiment(
                    config=config,
                    config_path=CONFIG_PATH,
                    output_directory=temporary,
                )

    def test_small_run_writes_deterministic_nested_campaigns(self) -> None:
        config = load_config(CONFIG_PATH)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            arguments = {
                "config": config,
                "config_path": CONFIG_PATH,
                "family_names": ("same_domain_replicas",),
                "mode_names": ("full", "no_joint_health"),
                "repetitions": 2,
                "sample_sizes": (100,),
            }
            run_experiment(output_directory=first, **arguments)
            run_experiment(output_directory=second, **arguments)

            first_path = Path(first)
            second_path = Path(second)
            self.assertEqual(read_rows(first_path / "runs.csv"), read_rows(second_path / "runs.csv"))
            self.assertEqual(
                read_rows(first_path / "parameters.csv"),
                read_rows(second_path / "parameters.csv"),
            )
            self.assertEqual(len(read_rows(first_path / "runs.csv")), 4)
            manifest = json.loads((first_path / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["row_counts"]["runs"], 4)
            self.assertEqual(manifest["sample_sizes"], [100])

    def test_aggregate_combines_family_shards(self) -> None:
        config = load_config(CONFIG_PATH)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for family in ("same_domain_replicas", "communication_bottleneck"):
                run_experiment(
                    config=config,
                    config_path=CONFIG_PATH,
                    output_directory=root / family,
                    family_names=(family,),
                    mode_names=("full",),
                    repetitions=1,
                    sample_sizes=(100,),
                )
            manifest = aggregate_results(root, root.parent / f"{root.name}-aggregate")
            self.assertEqual(manifest["source_shards"], 2)
            self.assertEqual(manifest["row_counts"]["runs"], 2)
            self.assertEqual(manifest["row_counts"]["summary"], 2)


if __name__ == "__main__":
    unittest.main()
