from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml

from telemetry_availability import temporal_confirmation_live as live
from telemetry_availability.live_stochastic_pilot import factor_definitions, renewal_schedule_seed
from telemetry_availability.live_validation_config import load_frozen_live_validation_config


class TemporalConfirmationLiveTests(unittest.TestCase):
    def test_design_and_acquisition_semantics(self):
        live.validate()
        old = load_frozen_live_validation_config(live.ROOT / "configs/m7_frozen_live.yaml").stochastic
        for scope, count, seed in (("preflight", 4, 2026090702), ("full", 120, 2026090701)):
            config = live.stochastic_config(scope)
            self.assertEqual(config.expected_cells, count)
            self.assertEqual(config.main_base_seed, seed)
            self.assertEqual((config.baseline_seconds, config.period_seconds, config.request_rate_per_second), (60, 900, 4))
            for name in ("renewal_processes", "health_poll_seconds", "request_timeout_seconds", "request_workers", "minimum_linked_success_fraction"):
                self.assertEqual(getattr(config, name), getattr(old, name))
            self.assertEqual(config.placement.runtime.profiles[0].commit, "8c47d47c9ac27710d2b2a153bcd53e483bffe66d")

    def test_seed_separation_for_factors_and_periods(self):
        seen = set()
        for scope in ("preflight", "full"):
            config = live.stochastic_config(scope)
            profile = config.placement.profiles[0]
            # A bounded configuration-only check, not a live matrix or fit.
            for placement in ("colocated", "split"):
                for law in ("N", "ND"):
                    for period in ("calibration", "test"):
                        for factor in factor_definitions(config, profile, placement, law):
                            seed = renewal_schedule_seed(config, profile, placement, law, 0, period, factor.factor_id, base_seed=config.main_base_seed)
                            self.assertNotIn(seed, seen)
                            seen.add(seed)

    def test_retry_request_namespace_is_distinct(self):
        values = {live.namespace(scope, run, attempt) for scope in ("preflight", "full") for run in (100, 101) for attempt in (1, 2)}
        self.assertEqual(len(values), 8)
        self.assertTrue(live.namespace("full", 100, 1).startswith("m9p-temporal-confirm-v1-"))

    def test_no_local_collection_or_data_processing(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            for function, args in ((live.run_cell, ["preflight", "split", "ND", 0, "missing", "missing", "missing", "missing"]),
                                   (live.qualify, ["missing", "missing", "preflight"]),
                                   (live.audit_preflight, ["missing", "missing"])):
                with self.assertRaisesRegex(ValueError, "only in GitHub Actions"):
                    function(*args)

    def test_allowlist_detects_corruption_and_empty_evaluator_directory(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in live.LEARNER_FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic", encoding="utf-8")
            live.seal(root, {})
            live.verify_seal(root, live.LEARNER_FILES)
            (root / "evaluator").mkdir()
            with self.assertRaisesRegex(ValueError, "evaluator directory"):
                live.verify_seal(root, live.LEARNER_FILES)
            (root / "evaluator").rmdir()
            (root / "learner/health.csv").write_text("corruption", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sealed bytes"):
                live.verify_seal(root, live.LEARNER_FILES)

    def test_preflight_has_no_analysis_command_and_retains_all_attempts(self):
        workflow = yaml.safe_load((live.ROOT / ".github/workflows/m9p-temporal-preflight.yml").read_text())
        jobs = workflow["jobs"]
        self.assertEqual(jobs["audit"]["needs"], "campaign")
        for job in jobs.values():
            self.assertEqual(job["timeout-minutes"], 360)
            for step in job["steps"]:
                command = step.get("run", "")
                self.assertNotIn("freeze-candidates", command)
                self.assertNotIn("evaluate-candidates", command)
        matrix = jobs["campaign"]["strategy"]["matrix"]
        self.assertEqual(matrix["law"], ["N", "ND"])
        self.assertEqual(matrix["repetition"], [0])
        raw = next(step for step in jobs["campaign"]["steps"] if step.get("name") == "Preserve original source attempt")
        self.assertEqual(raw["if"], "${{ always() }}")
        self.assertIn("github.run_attempt", raw["with"]["name"])


if __name__ == "__main__":
    unittest.main()
