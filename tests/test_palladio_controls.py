from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.palladio_controls import (
    audit_palladio_capability_source,
    audit_palladio_control_models,
    audit_palladio_control_results,
    expected_control_success,
    generate_palladio_control_models,
    load_palladio_controls_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9b_palladio_semantic_controls.json"
BOOTSTRAP = ROOT / "configs" / "m9a_palladio_bootstrap.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m9b-palladio-semantic-controls.yml"
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
HARNESS_MANIFEST = ROOT / "palladio" / "harness" / "META-INF" / "MANIFEST.MF"


class PalladioControlsTests(unittest.TestCase):
    def _fixture_config(
        self,
        root: Path,
        ecore_payload: bytes,
        visitor_payload: bytes | None = None,
    ) -> tuple[Path, Path]:
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        payload["pcm_metamodel"]["ecore_bytes"] = len(ecore_payload)
        payload["pcm_metamodel"]["ecore_sha256"] = hashlib.sha256(
            ecore_payload
        ).hexdigest()
        bootstrap_path = root / "configs" / "m9a_palladio_bootstrap.json"
        bootstrap_path.parent.mkdir(parents=True)
        bootstrap_payload = BOOTSTRAP.read_bytes()
        bootstrap_path.write_bytes(bootstrap_payload)
        payload["bootstrap_lock"]["config_sha256"] = hashlib.sha256(
            bootstrap_payload
        ).hexdigest()
        if visitor_payload is not None:
            payload["analyzer"]["visitor_bytes"] = len(visitor_payload)
            payload["analyzer"]["visitor_sha256"] = hashlib.sha256(
                visitor_payload
            ).hexdigest()
        config_path = root / "m9b.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        return config_path, bootstrap_path

    def _generate_and_audit(
        self, root: Path
    ) -> tuple[Path, Path, Path, object]:
        marker = json.loads(CONFIG.read_text(encoding="utf-8"))["pcm_metamodel"][
            "network_documentation_marker"
        ]
        ecore_payload = f"<ecore>{marker}</ecore>".encode()
        config_path, bootstrap_path = self._fixture_config(root, ecore_payload)
        ecore_path = root / "pcm.ecore"
        ecore_path.write_bytes(ecore_payload)
        models = root / "models"
        generate_palladio_control_models(
            config_path, models, root / "generation.json"
        )
        manifest = audit_palladio_control_models(
            config_path,
            models,
            ecore_path,
            bootstrap_path,
            root / "model-audit.json",
        )
        return config_path, models, root / "model-audit.json", manifest

    def test_frozen_config_has_all_oracles_and_remote_limits(self) -> None:
        config = load_palladio_controls_config(CONFIG)
        self.assertEqual(len(config.models), 7)
        self.assertEqual(len(config.cases), 15)
        self.assertEqual(config.repeat_runs, 2)
        self.assertTrue(config.remote_only)
        self.assertEqual(config.job_timeout_minutes, 360)
        for case in config.cases:
            self.assertAlmostEqual(
                expected_control_success(case.kind, case.parameters),
                case.expected_success_probability,
                places=15,
            )

    def test_generator_and_independent_model_audit_agree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            _, models, _, manifest = self._generate_and_audit(Path(temporary))
            self.assertEqual(manifest["status"], "model_contract_passed")
            self.assertEqual(manifest["model_count"], 7)
            self.assertEqual(manifest["case_count"], 15)
            self.assertEqual(len(list(models.rglob("default.*"))), 35)

    def test_model_audit_rejects_post_generation_parameter_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path, models, _, _ = self._generate_and_audit(root)
            environment = (
                models / "network_q10_raw" / "default.resourceenvironment"
            )
            environment.write_text(
                environment.read_text(encoding="utf-8").replace(
                    'failureProbability="0.10000000000000001"',
                    'failureProbability="0.2"',
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "link_failure_probability"):
                audit_palladio_control_models(
                    config_path,
                    models,
                    root / "pcm.ecore",
                    root / "configs" / "m9a_palladio_bootstrap.json",
                    root / "rejected.json",
                )

    def test_capability_source_audit_pins_replication_and_two_transfers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = json.loads(CONFIG.read_text(encoding="utf-8"))
            markers = base["analyzer"]["source_markers"]
            visitor_payload = (
                "\n".join(markers)
                + "\nprivate MarkovChain caseExternalCallActionInsideSystem() {\n"
                + "caseMessageTransfer(commLink);\n"
                + "caseMessageTransfer(commLink);\n}\n"
                + "private MarkovChain caseExternalCallActionOutsideSystem() {}\n"
            ).encode()
            config_path, _ = self._fixture_config(
                root, b"unused ecore", visitor_payload
            )
            checkout = root / "analyzer"
            visitor = checkout / Path(base["analyzer"]["visitor_path"])
            visitor.parent.mkdir(parents=True)
            visitor.write_bytes(visitor_payload)
            with patch(
                "telemetry_availability.palladio_controls._git_head",
                return_value=base["analyzer"]["commit"],
            ):
                manifest = audit_palladio_capability_source(
                    config_path, checkout, root / "capability.json"
                )
            self.assertEqual(
                manifest["internal_call_message_transfer_expansions"], 2
            )
            self.assertFalse(
                manifest["automatic_allocation_replication"]["supported"]
            )

    def _synthetic_result_fixture(
        self, root: Path
    ) -> tuple[Path, Path, Path, Path, Path]:
        config_path, models, model_manifest, _ = self._generate_and_audit(root)
        config = load_palladio_controls_config(config_path)
        capability = {
            "status": "capability_source_audit_passed",
            "analyzer_commit": config.analyzer_commit,
            "automatic_allocation_replication": {
                "supported": False,
                "observed_behavior": "fixture",
                "control_encoding": "fixture",
            },
        }
        capability_path = root / "capability.json"
        capability_path.write_text(json.dumps(capability), encoding="utf-8")
        runs = []
        for model in config.models:
            for case in model.cases:
                for repetition in range(config.repeat_runs):
                    runs.append(
                        {
                            "model_id": model.id,
                            "scenario_id": case.id,
                            "repetition": repetition,
                            "success_probability": case.expected_success_probability,
                            "failure_probability_sum": 1.0
                            - case.expected_success_probability,
                            "physical_state_probability": 1.0,
                            "evaluated_physical_states": model.expected_physical_states,
                            "total_physical_states": model.expected_physical_states,
                        }
                    )
        result_path = root / "raw-result.json"
        result_path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
        return config_path, model_manifest, capability_path, result_path, models

    def test_result_audit_accepts_exact_repeated_solver_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._synthetic_result_fixture(root)
            manifest = audit_palladio_control_results(
                *fixture, root / "acceptance.json"
            )
            self.assertEqual(
                manifest["status"],
                "semantic_controls_passed_with_mapping_constraints",
            )
            self.assertEqual(manifest["raw_run_count"], 30)
            self.assertFalse(
                manifest["scientific_interpretation"]["m7_interpretation_changed"]
            )

    def test_result_audit_rejects_one_wrong_solver_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._synthetic_result_fixture(root)
            result_path = fixture[3]
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            payload["runs"][0]["success_probability"] = 0.99
            payload["runs"][0]["failure_probability_sum"] = 0.01
            result_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "success oracle"):
                audit_palladio_control_results(
                    *fixture, root / "rejected.json"
                )

    def test_workflow_has_three_360_minute_jobs(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        for job in ("model_contract:", "semantic_controls:", "acceptance_audit:"):
            self.assertIn(f"  {job}", workflow)
        self.assertIn("needs: [model_contract, semantic_controls]", workflow)

    def test_harness_reports_named_scenarios_without_expected_values(self) -> None:
        harness = HARNESS.read_text(encoding="utf-8")
        self.assertIn('getEStructuralFeature("entityName")', harness)
        self.assertIn("result.getScenario().eGet(nameFeature)", harness)
        self.assertNotIn("getScenario().getEntityName()", harness)
        self.assertIn("TAID_EXPECTED_CASE_COUNT", harness)
        self.assertNotIn("TAID_EXPECTED_SUCCESS", harness)

    def test_harness_declares_direct_pcm_and_emf_runtime_dependencies(self) -> None:
        manifest = HARNESS_MANIFEST.read_text(encoding="utf-8")
        self.assertIn(" org.eclipse.emf.ecore,", manifest)
        self.assertIn(" org.palladiosimulator.pcm,", manifest)


if __name__ == "__main__":
    unittest.main()
