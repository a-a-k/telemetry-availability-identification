from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.palladio_fullpath import (
    _evaluate_application_gates,
    audit_palladio_fullpath_probe,
    file_sha256,
    load_palladio_fullpath_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9e_palladio_full_path_feasibility.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m9e-palladio-full-path-feasibility.yml"


class PalladioFullPathTests(unittest.TestCase):
    def test_frozen_contract_has_remote_limits_and_no_accuracy_role(self) -> None:
        config = load_palladio_fullpath_config(CONFIG)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.internal_timeout_seconds, 5400)
        self.assertEqual(len(config.applications), 2)
        self.assertEqual(len(config.required_gates), 15)
        self.assertEqual(config.raw["accuracy_scoring"], "forbidden")
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertNotIn("test-requests.csv", workflow)
        self.assertNotIn("scores.csv", workflow)

    def test_repository_locks_match_frozen_files(self) -> None:
        config = load_palladio_fullpath_config(CONFIG)
        for record in config.raw["evidence"]["repository_locks"]:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(path.stat().st_size, record["bytes"], record["path"])
            self.assertEqual(file_sha256(path), record["sha256"], record["path"])

    def test_complete_synthetic_model_passes_all_readiness_gates(self) -> None:
        config = load_palladio_fullpath_config(CONFIG)
        application = config.applications[0]
        text = " ".join(
            (
                application.operation_markers[0],
                application.entry_markers[0],
                application.target_markers[0],
                *application.replica_markers,
                *application.domain_markers,
                "ResourceDemandingSEFF ExternalCallAction",
                "SoftwareInducedFailureType",
                "InternalFailureOccurrenceDescription",
                'MTTF="4" MTTR="1" failureProbability="0.1"',
            )
        )
        suffixes = {
            ".repository",
            ".system",
            ".allocation",
            ".resourceenvironment",
            ".usagemodel",
        }
        gates = _evaluate_application_gates(
            application, {"exit_code": 0}, text, suffixes
        )
        self.assertEqual(set(gates), set(config.required_gates))
        self.assertTrue(all(gates.values()))

    def test_repository_failure_does_not_count_as_link_failure(self) -> None:
        config = load_palladio_fullpath_config(CONFIG)
        application = config.applications[0]
        repository = " ".join(
            (
                application.operation_markers[0],
                application.entry_markers[0],
                application.target_markers[0],
                *application.replica_markers,
                *application.domain_markers,
                "ResourceDemandingSEFF ExternalCallAction",
                "SoftwareInducedFailureType",
                "InternalFailureOccurrenceDescription",
                'failureProbability="0.25"',
            )
        )
        gates = _evaluate_application_gates(
            application,
            {"exit_code": 0},
            {
                ".repository": repository,
                ".resourceenvironment": (
                    'MTTF="4" MTTR="1" failureProbability="0.0"'
                ),
                ".system": "system",
                ".allocation": "allocation",
                ".usagemodel": "usage",
            },
            {
                ".repository",
                ".resourceenvironment",
                ".system",
                ".allocation",
                ".usagemodel",
            },
        )
        self.assertTrue(gates["semantic_success_residual_present"])
        self.assertFalse(gates["nonzero_link_failure_present"])

    def _write_probe(
        self, root: Path, application_id: str, *, complete: bool
    ) -> None:
        config = load_palladio_fullpath_config(CONFIG)
        application = next(
            item for item in config.applications if item.id == application_id
        )
        app_root = root / application.id
        models = app_root / "models"
        models.mkdir(parents=True)
        contents = {
            "model.repository": " ".join(
                (
                    application.operation_markers[0],
                    application.entry_markers[0],
                    application.target_markers[0],
                    *application.replica_markers,
                    *application.domain_markers,
                    "ResourceDemandingSEFF ExternalCallAction",
                    "SoftwareInducedFailureType",
                    "InternalFailureOccurrenceDescription",
                    'failureProbability="0.1"',
                )
            ),
            "model.system": "system",
            "model.allocation": "allocation",
            "model.resourceenvironment": 'MTTF="4" MTTR="1"',
        }
        if complete:
            contents["model.usagemodel"] = "usage"
        for name, content in contents.items():
            (models / name).write_text(content, encoding="utf-8")
        rows = []
        for path in sorted(models.iterdir()):
            rows.append(
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                    "suffix": path.suffix,
                }
            )
        inventory = app_root / "model-files.csv"
        with inventory.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(
                destination, fieldnames=("path", "bytes", "sha256", "suffix")
            )
            writer.writeheader()
            writer.writerows(rows)
        record = {
            "application": application.id,
            "source_commit": application.commit,
            "retriever_rules": list(application.rules),
            "exit_code": 0,
            "files": {"model-files.csv": file_sha256(inventory)},
        }
        (app_root / "probe-record.json").write_text(
            json.dumps(record), encoding="utf-8"
        )

    def test_decision_names_partial_baseline_without_filling_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_hash = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "status": "full_path_feasibility_contract_passed",
                        "config_sha256": config_hash,
                    }
                ),
                encoding="utf-8",
            )
            probe = root / "probe"
            self._write_probe(probe, "deathstarbench_social_network", complete=True)
            self._write_probe(probe, "opentelemetry_demo", complete=False)
            manifest = audit_palladio_fullpath_probe(
                CONFIG, contract, probe, root / "out"
            )
            self.assertFalse(manifest["automatic_full_path_ready"])
            self.assertEqual(
                manifest["comparison_baseline_classification"],
                "partially_manual_PCM_required",
            )
            self.assertFalse(manifest["accuracy_scoring_started"])
            self.assertFalse(manifest["new_live_collection_authorized"])
            self.assertGreater(manifest["manual_completion_rows"], 0)

    def test_decision_rejects_a_tampered_model_after_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "status": "full_path_feasibility_contract_passed",
                        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
                    }
                ),
                encoding="utf-8",
            )
            probe = root / "probe"
            for application in load_palladio_fullpath_config(CONFIG).applications:
                self._write_probe(probe, application.id, complete=True)
            target = (
                probe
                / "deathstarbench_social_network"
                / "models"
                / "model.repository"
            )
            target.write_text("changed after inventory", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "model file differs"):
                audit_palladio_fullpath_probe(CONFIG, contract, probe, root / "out")


if __name__ == "__main__":
    unittest.main()
