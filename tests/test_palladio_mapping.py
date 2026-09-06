from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.palladio_mapping import (
    audit_palladio_application_models,
    audit_palladio_application_results,
    expected_application_success,
    generate_palladio_application_models,
    load_palladio_mapping_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9c_palladio_application_mapping.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m9c-palladio-application-mapping.yml"
PROTOCOL = ROOT / "docs" / "M9C_PALLADIO_APPLICATION_MAPPING_PROTOCOL.md"
HARNESS = (
    ROOT
    / "palladio"
    / "harness"
    / "src"
    / "org"
    / "palladiosimulator"
    / "reliability"
    / "tests"
    / "SemanticControlsTest.java"
)


class PalladioApplicationMappingTests(unittest.TestCase):
    def _generate_and_audit(self, root: Path) -> tuple[Path, Path, dict]:
        models = root / "models"
        generate_palladio_application_models(CONFIG, models, root / "generation.json")
        manifest_path = root / "model-contract.json"
        manifest = audit_palladio_application_models(
            CONFIG, models, ROOT, manifest_path
        )
        return models, manifest_path, dict(manifest)

    def test_frozen_contract_has_complete_mapping_and_remote_limits(self) -> None:
        config = load_palladio_mapping_config(CONFIG)
        self.assertEqual(len(config.applications), 2)
        self.assertEqual(len(config.models), 4)
        self.assertEqual(config.repeat_runs, 2)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(
            {item.operation for item in config.applications},
            {"read_user_timeline", "browse_product"},
        )
        expected_elements = {
            "request_success",
            "operation_path",
            "replication",
            "individual_failure",
            "communication_failure",
            "common_domain",
            "parameters",
            "placement",
        }
        for application in config.applications:
            self.assertEqual(
                {row["element"] for row in application.mapping}, expected_elements
            )
        self.assertAlmostEqual(
            expected_application_success(config, "colocated"), 0.7740018, places=15
        )
        self.assertAlmostEqual(
            expected_application_success(config, "split"), 0.81140112, places=15
        )

    def test_generator_and_independent_structural_audit_agree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            models, _, manifest = self._generate_and_audit(Path(temporary))
            self.assertEqual(manifest["status"], "application_model_contract_passed")
            self.assertEqual(manifest["model_count"], 4)
            self.assertEqual(manifest["scenario_count"], 4)
            self.assertEqual(len(list(models.rglob("default.*"))), 20)
            for model in manifest["models"]:
                self.assertFalse(model["automatic_allocation_replication_used"])
                self.assertFalse(model["literal_haproxy_retry_claimed"])

    def test_model_audit_rejects_a_post_generation_link_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models, _, _ = self._generate_and_audit(root)
            environment = (
                models
                / "opentelemetry_demo__browse_product__split"
                / "default.resourceenvironment"
            )
            text = environment.read_text(encoding="utf-8")
            environment.write_text(
                text.replace(
                    'failureProbability="0.051316701949486232"',
                    'failureProbability="0.2"',
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "link"):
                audit_palladio_application_models(
                    CONFIG, models, ROOT, root / "rejected.json"
                )

    def test_result_audit_accepts_only_complete_repeated_oracles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models, model_manifest_path, _ = self._generate_and_audit(root)
            config = load_palladio_mapping_config(CONFIG)
            config_hash = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
            evidence_path = root / "evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "status": "application_mapping_evidence_passed",
                        "config_sha256": config_hash,
                    }
                ),
                encoding="utf-8",
            )
            runs = []
            for model in config.models:
                for repetition in range(config.repeat_runs):
                    runs.append(
                        {
                            "model_id": model.id,
                            "scenario_id": model.operation,
                            "repetition": repetition,
                            "success_probability": model.expected_success_probability,
                            "failure_probability_sum": 1.0
                            - model.expected_success_probability,
                            "physical_state_probability": 1.0,
                            "evaluated_physical_states": model.expected_physical_states,
                            "total_physical_states": model.expected_physical_states,
                        }
                    )
            result_path = root / "result.json"
            result_path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
            manifest = audit_palladio_application_results(
                CONFIG,
                evidence_path,
                model_manifest_path,
                result_path,
                models,
                root / "acceptance.json",
            )
            self.assertEqual(
                manifest["status"], "application_mapping_and_models_passed"
            )
            self.assertEqual(manifest["raw_run_count"], 8)
            self.assertFalse(
                manifest["scientific_interpretation"]["accuracy_comparison_started"]
            )
            self.assertFalse(
                manifest["scientific_interpretation"]["m7_interpretation_changed"]
            )

    def test_result_audit_rejects_a_favorable_unregistered_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            models, model_manifest_path, _ = self._generate_and_audit(root)
            config = load_palladio_mapping_config(CONFIG)
            config_hash = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
            evidence_path = root / "evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "status": "application_mapping_evidence_passed",
                        "config_sha256": config_hash,
                    }
                ),
                encoding="utf-8",
            )
            runs = []
            for model in config.models:
                for repetition in range(config.repeat_runs):
                    success = model.expected_success_probability
                    if not runs:
                        success = min(1.0, success + 0.01)
                    runs.append(
                        {
                            "model_id": model.id,
                            "scenario_id": model.operation,
                            "repetition": repetition,
                            "success_probability": success,
                            "failure_probability_sum": 1.0 - success,
                            "physical_state_probability": 1.0,
                            "evaluated_physical_states": model.expected_physical_states,
                            "total_physical_states": model.expected_physical_states,
                        }
                    )
            result_path = root / "result.json"
            result_path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "predeclared success oracle"):
                audit_palladio_application_results(
                    CONFIG,
                    evidence_path,
                    model_manifest_path,
                    result_path,
                    models,
                    root / "rejected.json",
                )

    def test_workflow_has_three_360_minute_jobs_and_remote_evidence(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        for job in ("evidence_contract:", "application_models:", "acceptance_audit:"):
            self.assertIn(f"  {job}", workflow)
        self.assertIn("gh run download", workflow)
        self.assertIn("raw.githubusercontent.com", workflow)
        self.assertIn("needs: [evidence_contract, application_models]", workflow)

    def test_protocol_and_harness_keep_the_claim_boundary(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("Status: frozen before the first remote Palladio execution", protocol)
        self.assertIn("not an accuracy comparison", protocol)
        self.assertIn("not literal round-robin", protocol)
        self.assertIn("timeout-minutes: 360", protocol)
        harness = HARNESS.read_text(encoding="utf-8")
        self.assertIn("TAID_EXPECTED_MODEL_COUNT", harness)
        self.assertNotIn("TAID_EXPECTED_SUCCESS", harness)


if __name__ == "__main__":
    unittest.main()
