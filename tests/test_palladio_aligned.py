from __future__ import annotations

import hashlib
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from telemetry_availability.cli import build_parser
from telemetry_availability.palladio_aligned import (
    PalladioAlignedError,
    _audit_one_application_model,
    _canonical_witness,
    _compare_replay,
    _fake_mapping_config,
    _load_learner_only_cell,
    _model_payloads,
    _oracle,
    _paired_interval,
    _score,
    _state_count,
    audit_palladio_aligned_results,
    load_palladio_aligned_config,
    prepare_palladio_aligned_models,
    stage_palladio_aligned_learner_input,
)
from telemetry_availability.palladio_mapping import (
    ApplicationModel,
    load_palladio_mapping_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9d_palladio_aligned_comparison.json"
M9C_CONFIG = ROOT / "configs" / "m9c_palladio_application_mapping.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m9d-palladio-aligned-comparison.yml"
PROTOCOL = ROOT / "docs" / "M9D_PALLADIO_ALIGNED_INPUT_PROTOCOL.md"
MANUAL_LOG = ROOT / "docs" / "M9D_MANUAL_ACTIONS.csv"
HARNESS = (
    ROOT
    / "palladio"
    / "harness"
    / "src"
    / "org"
    / "palladiosimulator"
    / "reliability"
    / "tests"
    / "AlignedComparisonTest.java"
)


class PalladioAlignedTests(unittest.TestCase):
    def test_frozen_contract_has_exact_population_runtime_and_role(self) -> None:
        config = load_palladio_aligned_config(CONFIG)
        self.assertEqual(config.observation_mode, "sampled_mixed")
        self.assertEqual(config.expected_models, 184)
        self.assertEqual(config.expected_raw_runs, 368)
        self.assertEqual(config.technical_repetitions, 2)
        self.assertEqual(config.expected_opportunities["total"], 240)
        self.assertEqual(config.expected_missing["total"], 56)
        self.assertEqual(config.expected_state_models, {4: 153, 8: 31})
        self.assertEqual(
            config.raw["runtime"]["python"], "CPython 3.13.15"
        )
        self.assertFalse(config.raw["analysis"]["compute_p_values"])
        self.assertFalse(
            config.raw["mapping"]["individual_parameters_are_causally_identified"]
        )

    def test_config_rejects_a_post_freeze_timeout_change(self) -> None:
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        payload["runtime"]["job_timeout_minutes"] = 359
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "changed.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(PalladioAlignedError, "360-minute"):
                load_palladio_aligned_config(path)

    def test_cli_registers_all_five_workflow_commands(self) -> None:
        parser = build_parser()
        commands = {
            action.dest: set(action.choices)
            for action in parser._actions
            if hasattr(action, "choices") and action.choices
        }["command"]
        self.assertTrue(
            {
                "validate-palladio-aligned-comparison",
                "audit-palladio-aligned-evidence",
                "stage-palladio-aligned-learner-input",
                "prepare-palladio-aligned-models",
                "audit-palladio-aligned-results",
            }.issubset(commands)
        )

    def test_workflow_has_three_remote_jobs_with_six_hour_timeouts(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        workflow = yaml.safe_load(text)
        self.assertEqual(
            set(workflow["jobs"]),
            {"aligned_input_contract", "palladio_solver", "acceptance_and_scoring"},
        )
        self.assertTrue(
            all(job["timeout-minutes"] == 360 for job in workflow["jobs"].values())
        )
        self.assertEqual(text.count('python-version: "3.13.15"'), 3)
        for command in (
            "validate-palladio-aligned-comparison",
            "audit-palladio-aligned-evidence",
            "stage-palladio-aligned-learner-input",
            "prepare-palladio-aligned-models",
            "audit-palladio-aligned-results",
        ):
            self.assertIn(command, text)
        self.assertLess(
            text.index("Retain raw untuned solver output"),
            text.index("Re-download preserved evaluator evidence only after solving"),
        )

    def test_heavy_fit_and_scoring_are_guarded_from_local_execution(self) -> None:
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(PalladioAlignedError, "only in GitHub Actions"):
                prepare_palladio_aligned_models(
                    CONFIG,
                    ROOT / "missing-learner",
                    ROOT / "missing-analysis",
                    ROOT / "missing-evidence.json",
                    ROOT / "missing-models",
                    ROOT / "missing-output",
                )
            with self.assertRaisesRegex(PalladioAlignedError, "only in GitHub Actions"):
                audit_palladio_aligned_results(
                    CONFIG,
                    ROOT / "missing-contract",
                    ROOT / "missing-result.json",
                    ROOT / "missing-qualified",
                    ROOT / "missing-analysis",
                    ROOT / "missing-audit",
                    ROOT / "missing-preserved-metadata.json",
                    ROOT / "missing-audit-metadata.json",
                    ROOT / "missing-output",
                )

    def test_staging_copies_only_learner_and_audit_trees(self) -> None:
        config = load_palladio_aligned_config(CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            qualified = root / "qualified"
            for profile in config.operations:
                for placement in ("colocated", "split"):
                    for law in config.failure_laws:
                        for repetition in range(config.repetitions):
                            cell = (
                                qualified
                                / f"cell-{profile}-{placement}-{law}-{repetition}"
                            )
                            (cell / "learner").mkdir(parents=True)
                            (cell / "audit").mkdir()
                            (cell / "evaluator").mkdir()
                            (cell / "learner" / "manifest.json").write_text(
                                json.dumps(
                                    {
                                        "profile": profile,
                                        "placement": placement,
                                        "failure_law": law,
                                        "repetition": repetition,
                                    }
                                ),
                                encoding="utf-8",
                            )
                            (cell / "learner" / "marker.txt").write_text(
                                "learner", encoding="utf-8"
                            )
                            (cell / "audit" / "boundary.json").write_text(
                                '{"note":"test-requests.csv is named only as text"}',
                                encoding="utf-8",
                            )
                            (cell / "evaluator" / "test-requests.csv").write_text(
                                "held-out", encoding="utf-8"
                            )
            staged = root / "staged"
            manifest = stage_palladio_aligned_learner_input(
                CONFIG, qualified, staged
            )
            self.assertEqual(manifest["cells"], 160)
            self.assertFalse(manifest["contains_evaluator_data"])
            self.assertFalse(any(path.name == "evaluator" for path in staged.rglob("*")))
            loader_source = inspect.getsource(_load_learner_only_cell)
            self.assertNotIn('cell_root / "evaluator"', loader_source)
            self.assertIn("test_requests=()", loader_source)

    def test_one_model_xml_smoke_and_independent_oracles(self) -> None:
        base = load_palladio_mapping_config(M9C_CONFIG)
        witness = _canonical_witness(
            "NCD",
            {"g": 0.91, "ea": 0.92, "eb": 0.88, "ca": 0.94, "cb": 0.9},
            0.96,
        )
        oracle = _oracle(witness, "colocated")
        self.assertEqual(_state_count(witness, "colocated"), 8)
        self.assertEqual(_state_count(witness, "split"), 4)
        model = ApplicationModel(
            id="m9d-unit-smoke",
            application="deathstarbench_social_network",
            operation="read_user_timeline",
            placement="colocated",
            expected_physical_states=8,
            expected_success_probability=oracle,
        )
        fake = _fake_mapping_config(base, model, witness, CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            model_root = Path(temporary)
            for name, payload in _model_payloads(fake, model).items():
                (model_root / name).write_text(payload, encoding="utf-8")
            audit = _audit_one_application_model(fake, model, model_root)
            self.assertAlmostEqual(
                audit["expected_success_probability"], oracle, places=15
            )
            self.assertEqual(audit["expected_physical_states"], 8)

    def test_scoring_replay_and_interval_helpers(self) -> None:
        base = {
            "profile": "p",
            "failure_law": "N",
            "repetition": 0,
            "mode": "sampled_mixed",
            "scope": "current",
            "source_placement": "colocated",
            "target_placement": "colocated",
            "view": "stable",
            "block_length_seconds": 23,
            "operation": "op",
        }
        score = _score(base, "B0", 0.75, 4, 3, 0.5, 1.0)
        self.assertAlmostEqual(score["brier_score"], 0.1875)
        self.assertEqual(score["test_successes"], 3)
        interval = _paired_interval({("a",): [-0.1, -0.2], ("b",): [0.0, -0.1]}, 0.95)
        self.assertAlmostEqual(interval["estimate"], -0.1)
        replay = {
            "requires_target_group": "True",
            "status": "ok",
            "fit_status": "regular",
            "identification_rank": "2",
            "identification_dimension": "2",
            "prediction": 0.8,
            "route_prediction": 0.9,
            "residual_success_probability": 0.95,
            "fit_nll": 1.2,
            "target_gradient_residual": 0.0,
            "multistart_prediction_range": 0.0,
        }
        self.assertEqual(_compare_replay(replay, dict(replay), 1e-12), [])
        changed = dict(replay, prediction=0.7)
        self.assertEqual(_compare_replay(changed, replay, 1e-12), ["prediction"])

    def test_protocol_and_java_harness_preclude_the_straw_man_claim(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("It does not infer", protocol)
        self.assertIn("No `PCM+B2` topology is constructed", protocol)
        self.assertIn("would create a straw-man comparison", protocol)
        self.assertIn("M9D computes no p-values", protocol)
        harness = HARNESS.read_text(encoding="utf-8")
        self.assertIn("TAID_EXPECTED_MODEL_COUNT", harness)
        self.assertIn("TAID_M9D_WARMUP_START", harness)
        self.assertNotIn("TAID_EXPECTED_SUCCESS", harness)

    def test_manual_log_prefix_and_repository_locks_are_byte_exact(self) -> None:
        payload = json.loads(CONFIG.read_text(encoding="utf-8"))
        manual = payload["evidence"]["manual_actions_log"]
        prefix = MANUAL_LOG.read_bytes()[: manual["initial_size_in_bytes"]]
        self.assertEqual(hashlib.sha256(prefix).hexdigest(), manual["initial_sha256"])
        for lock in payload["evidence"]["repository_locks"]:
            path = ROOT / lock["path"]
            self.assertTrue(path.is_file(), lock["path"])
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                lock["sha256"],
                lock["path"],
            )


if __name__ == "__main__":
    unittest.main()
