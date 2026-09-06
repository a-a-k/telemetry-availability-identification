from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from telemetry_availability.palladio_bootstrap import (
    apply_palladio_target_platform_lock,
    audit_palladio_example,
    audit_palladio_product,
    audit_palladio_source,
    load_palladio_bootstrap_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9a_palladio_bootstrap.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m9a-palladio-bootstrap.yml"
HARNESS_MANIFEST = ROOT / "palladio" / "harness" / "META-INF" / "MANIFEST.MF"


class PalladioBootstrapTests(unittest.TestCase):
    def test_repository_contract_is_acceptance_ready_after_discovery(self) -> None:
        config = load_palladio_bootstrap_config(CONFIG)
        self.assertEqual(config.analyzer.bundle_version, "5.2.2")
        self.assertEqual(config.runtime.job_timeout_minutes, 360)
        self.assertTrue(config.runtime.remote_only)
        self.assertTrue(config.acceptance_ready)

    def test_timeout_change_is_rejected(self) -> None:
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        payload["runtime"]["job_timeout_minutes"] = 359
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "360-minute"):
                load_palladio_bootstrap_config(path)

    def test_product_audit_requires_exact_binary_and_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "Palladio.zip"
            with ZipFile(archive, "w") as product:
                product.writestr(
                    "Palladio/features/"
                    "org.palladiosimulator.reliability.feature_5.2.2/feature.xml",
                    b"<feature/>",
                )
                product.writestr(
                    "Palladio/features/"
                    "org.palladiosimulator.reliability.feature_5.2.2/"
                    "META-INF/MANIFEST.MF",
                    b"Manifest-Version: 1.0\n",
                )
                product.writestr(
                    "Palladio/plugins/"
                    "org.palladiosimulator.reliability.solver_5.2.2.jar",
                    b"solver",
                )
                product.writestr(
                    "Palladio/plugins/org.palladiosimulator.reliability_5.2.2.jar",
                    b"core",
                )
            payload = json.loads(CONFIG.read_text(encoding="utf-8"))
            payload["product"]["expected_bytes"] = archive.stat().st_size
            payload["product"]["sha256"] = hashlib.sha256(
                archive.read_bytes()
            ).hexdigest()
            config_path = root / "lock.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")
            output = root / "audit.json"

            audit = audit_palladio_product(config_path, archive, output)

            self.assertEqual(audit["status"], "pinned_match")
            self.assertEqual(audit["required_feature"]["packaging"], "exploded")
            self.assertEqual(len(audit["reliability_files"]), 4)
            self.assertTrue(output.is_file())

    def test_historical_target_lock_checks_and_replaces_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = json.loads(CONFIG.read_text(encoding="utf-8"))
            lock = payload["target_platform_lock"]
            original = (
                "before\n"
                + lock["mutable_repository_url"]
                + "\nafter\n"
            ).encode("utf-8")
            patched = original.replace(
                lock["mutable_repository_url"].encode("utf-8"),
                lock["pinned_repository_url"].encode("utf-8"),
            )
            target = root / "palladio.target"
            target.write_bytes(original)
            lock["artifact_bytes"] = len(original)
            lock["original_sha256"] = hashlib.sha256(original).hexdigest()
            lock["patched_sha256"] = hashlib.sha256(patched).hexdigest()
            evidence_dir = root / "evidence"
            evidence_dir.mkdir()
            evidence_payload = b"fixed repository metadata"
            (evidence_dir / "content.jar").write_bytes(evidence_payload)
            lock["repository_evidence"] = [
                {
                    "relative_path": "content.jar",
                    "bytes": len(evidence_payload),
                    "sha256": hashlib.sha256(evidence_payload).hexdigest(),
                }
            ]
            config_path = root / "lock.json"
            config_path.write_text(json.dumps(payload), encoding="utf-8")

            manifest = apply_palladio_target_platform_lock(
                config_path,
                target,
                evidence_dir,
                root / "manifest.json",
            )

            self.assertEqual(target.read_bytes(), patched)
            self.assertEqual(
                manifest["status"], "historical_dependency_lock_applied"
            )
            self.assertFalse(manifest["analyzer_checkout_modified"])

    @patch(
        "telemetry_availability.palladio_bootstrap._git_head",
        return_value="a694e570afb705dc9e0470dc321e77b7219dcea4",
    )
    def test_source_build_audit_requires_pinned_outputs(self, _mock_head: object) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = (
                root
                / "releng"
                / "org.palladiosimulator.reliability.updatesite"
                / "target"
                / "repository"
            )
            (site / "features").mkdir(parents=True)
            (site / "plugins").mkdir()
            (site / "features" / "org.palladiosimulator.reliability.feature_5.2.2.jar").write_bytes(
                b"feature"
            )
            (site / "plugins" / "org.palladiosimulator.reliability.solver_5.2.2.jar").write_bytes(
                b"solver"
            )
            log = root / "build.log"
            log.write_text("BUILD SUCCESS\n", encoding="utf-8")
            output = root / "source-audit.json"

            audit = audit_palladio_source(CONFIG, root, log, output)

            self.assertEqual(audit["status"], "source_build_passed")
            self.assertEqual(audit["analyzer_commit"], _mock_head.return_value)

    @patch(
        "telemetry_availability.palladio_bootstrap._git_head",
        side_effect=[
            "a694e570afb705dc9e0470dc321e77b7219dcea4",
            "4a8dc455216774435fefd42965b848851f7658ee",
        ],
    )
    def test_example_audit_checks_repeatability_and_mass(self, _mock_head: object) -> None:
        del _mock_head
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analyzer = root / "analyzer"
            examples = root / "examples"
            model = examples / "ReliabilityTest"
            analyzer.mkdir()
            model.mkdir(parents=True)
            for suffix in (
                ".allocation",
                ".resourceenvironment",
                ".system",
                ".usagemodel",
            ):
                (model / f"default{suffix}").write_text(suffix, encoding="utf-8")
            (model / "default.repository").write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<Repository xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <components__Repository>
    <serviceEffectSpecifications__BasicComponent>
      <steps_Behaviour xsi:type="seff:InternalAction" id="initial"
          successor_AbstractAction="recovery">
        <internalFailureOccurrenceDescriptions__InternalAction
            failureProbability="0.5"
            softwareInducedFailureType__InternalFailureOccurrenceDescription="failure" />
      </steps_Behaviour>
      <steps_Behaviour xsi:type="seff_reliability:RecoveryAction" id="recovery"
          predecessor_AbstractAction="initial"
          primaryBehaviour__RecoveryAction="primary">
        <recoveryActionBehaviours__RecoveryAction id="primary"
            failureHandlingAlternatives__RecoveryActionBehaviour="alternative">
          <steps_Behaviour xsi:type="seff:InternalAction">
            <internalFailureOccurrenceDescriptions__InternalAction
                failureProbability="0.5"
                softwareInducedFailureType__InternalFailureOccurrenceDescription="failure" />
          </steps_Behaviour>
        </recoveryActionBehaviours__RecoveryAction>
        <recoveryActionBehaviours__RecoveryAction id="alternative"
            failureTypes_FailureHandlingEntity="failure">
          <steps_Behaviour xsi:type="seff:InternalAction">
            <internalFailureOccurrenceDescriptions__InternalAction
                failureProbability="0.5"
                softwareInducedFailureType__InternalFailureOccurrenceDescription="failure" />
          </steps_Behaviour>
        </recoveryActionBehaviours__RecoveryAction>
      </steps_Behaviour>
    </serviceEffectSpecifications__BasicComponent>
  </components__Repository>
</Repository>
""",
                encoding="utf-8",
            )
            result = root / "result.json"
            result.write_text(
                json.dumps(
                    {
                        "repetitions": [
                            {
                                "success_probability": 0.375,
                                "failure_probability_sum": 0.625,
                                "physical_state_probability": 1.0,
                            },
                            {
                                "success_probability": 0.375,
                                "failure_probability_sum": 0.625,
                                "physical_state_probability": 1.0,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            audit = audit_palladio_example(
                CONFIG,
                result,
                analyzer,
                examples,
                root / "example-audit.json",
            )

            self.assertEqual(audit["status"], "pinned_match")
            self.assertEqual(audit["success_probabilities"], [0.375, 0.375])
            self.assertEqual(
                audit["independent_oracle"]["success_probability"], 0.375
            )

    def test_remote_workflow_has_three_360_minute_jobs(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        for job in ("source_build:", "product_audit:", "official_example:"):
            self.assertIn(f"  {job}", workflow)
        self.assertEqual(workflow.count("lock-palladio-target-platform"), 2)

    def test_headless_harness_includes_pcm_pathmap_resources(self) -> None:
        manifest = HARNESS_MANIFEST.read_text(encoding="utf-8")
        self.assertIn("org.palladiosimulator.pcm.resources", manifest)


if __name__ == "__main__":
    unittest.main()
