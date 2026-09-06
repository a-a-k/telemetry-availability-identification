from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.pmx_performability import file_sha256
from telemetry_availability.pmx_source_entrypoint import (
    _read_entrypoint_run,
    classify_screen,
    decide,
    load_pmx_entrypoint_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9h_pmx_source_entrypoint.json"
PROTOCOL = ROOT / "docs" / "M9H_PMX_SOURCE_ENTRYPOINT_PROTOCOL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "m9h-pmx-source-entrypoint.yml"


class PMXSourceEntrypointTests(unittest.TestCase):
    def test_frozen_contract_has_one_source_command_and_remote_bounds(self) -> None:
        config = load_pmx_entrypoint_config(CONFIG)
        self.assertEqual(config.command, "main:main -of Options.txt")
        self.assertEqual(config.startup_seconds, 20)
        self.assertEqual(config.timeout_seconds, 180)
        self.assertEqual(config.confirmation_repeats, 2)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.raw["accuracy_scoring"], "forbidden")
        self.assertEqual(config.raw["m7_evidence_access"], "forbidden")
        self.assertFalse(config.raw["source_contract"]["candidate_search_allowed"])
        self.assertFalse(
            config.raw["manual_pcm_parallel"]["credited_as_pmx_automation"]
        )

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertEqual(workflow.count("SOURCE_COMMAND: main:main -of Options.txt"), 1)
        self.assertIn('STARTUP_STABILIZATION_SECONDS: "20"', workflow)
        self.assertIn('PMX_INTERNAL_TIMEOUT_SECONDS: "180"', workflow)
        self.assertIn("exit 0", workflow)
        self.assertNotIn("m8-preserved", workflow)
        self.assertNotIn("test-requests.csv", workflow)
        self.assertNotIn("scores.csv", workflow)
        self.assertNotIn("brier", workflow.lower())

    def test_protocol_precludes_a_straw_man_or_ecosystem_generalization(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("prospective source-derived test", protocol)
        self.assertIn("two independent", protocol)
        self.assertIn("remove two launcher artifacts", protocol)
        self.assertIn("not PMX, Retriever, or Palladio generally", protocol)
        self.assertIn("All three jobs use `timeout-minutes: 360`", protocol)

    def test_repository_and_manual_prefix_locks_match(self) -> None:
        config = load_pmx_entrypoint_config(CONFIG)
        for record in config.raw["repository_locks"]:
            path = ROOT / record["path"]
            self.assertEqual(path.stat().st_size, record["bytes"])
            self.assertEqual(file_sha256(path), record["sha256"])
        manual = config.raw["manual_actions_log"]
        content = (ROOT / manual["path"]).read_bytes()
        import hashlib

        self.assertEqual(
            hashlib.sha256(content[: manual["initial_size_in_bytes"]]).hexdigest(),
            manual["initial_sha256"],
        )

    def test_rejected_exact_command_is_detected_from_bounded_smoke(self) -> None:
        config = load_pmx_entrypoint_config(CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "results").mkdir()
            values = {
                "exit-code.txt": "0\n",
                "elapsed-seconds.txt": "21\n",
                "started-at-utc.txt": "2026-09-06T00:00:00Z\n",
                "command-sent-at-utc.txt": "2026-09-06T00:00:20Z\n",
                "finished-at-utc.txt": "2026-09-06T00:00:21Z\n",
                "stdin.txt": "main:main -of Options.txt\nexit 0\n",
                "stdout.log": "osgi> gogo: CommandNotFoundException: Command not found: main:main\n",
                "resource-usage.txt": "Exit status: 0\n",
            }
            for name, value in values.items():
                (run / name).write_text(value, encoding="utf-8")
            result = _read_entrypoint_run(config, run, "smoke")
        self.assertTrue(result["source_command_rejected"])
        self.assertFalse(result["source_command_entered"])
        self.assertFalse(result["output_eligible_as_original"])
        self.assertEqual(result["result_files"], 0)

    def test_screen_classification_uses_output_not_exit_code(self) -> None:
        fake = {
            "exit_code": 124,
            "timed_out": True,
            "output_eligible_as_original": True,
        }
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "screen.json"
            with patch(
                "telemetry_availability.pmx_source_entrypoint._read_entrypoint_run",
                return_value=fake,
            ):
                result = classify_screen(CONFIG, Path(temporary), out)
        self.assertTrue(result["output_eligible"])
        self.assertEqual(result["run"]["exit_code"], 124)
        self.assertFalse(result["accuracy_outcomes_used"])

    def test_decision_routes_reproduced_mechanism_to_adapter_prototype(self) -> None:
        config_hash = file_sha256(CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            probe = root / "probe.json"
            contract.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "exact_source_declared_command_audited",
                    }
                ),
                encoding="utf-8",
            )
            probe.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "source_command_entered": True,
                        "original_output_confirmed": True,
                        "launcher_terminates_cleanly": True,
                        "operation_failure_mechanism_reproduced": True,
                    }
                ),
                encoding="utf-8",
            )
            result = decide(CONFIG, contract, probe, root / "out")
        self.assertEqual(
            result["status"],
            "pmx_source_entrypoint_and_failure_mechanism_reproduced",
        )
        self.assertEqual(
            result["next_milestone"], "m9i_learner_only_pmx_adapter_prototype"
        )
        self.assertTrue(result["pmx_scientific_priority_retained"])
        self.assertFalse(result["manual_pcm_credited_as_pmx"])
        self.assertFalse(result["accuracy_scoring_started"])
        self.assertFalse(result["m7_interpretation_changed"])


if __name__ == "__main__":
    unittest.main()
