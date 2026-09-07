import math
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from telemetry_availability import temporal_confirmation_analysis as analysis
from telemetry_availability import temporal_confirmation_live as live


class TemporalConfirmationAnalysisTests(unittest.TestCase):
    def test_matched_endpoint_is_count_estimate_without_q_multiplier(self):
        self.assertEqual(analysis.endpoint_probability(0, 1), 0.25)
        self.assertEqual(analysis.endpoint_probability(1, 1), 0.75)
        self.assertAlmostEqual(analysis.endpoint_probability(60, 99), 0.605)
        with self.assertRaises(ValueError):
            analysis.endpoint_probability(0, 0)

    def test_bernoulli_score_equals_direct_request_loss(self):
        outcomes = [1, 0, 1, 1, 0, 0, 1]
        for probability in (0, 0.37, 1):
            direct = sum((probability - y) ** 2 for y in outcomes) / len(outcomes)
            self.assertAlmostEqual(analysis.bernoulli_brier(probability, sum(outcomes) / len(outcomes)), direct)
        for probability in (-0.1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                analysis.bernoulli_brier(probability, 0.5)

    def test_paired_stratified_bootstrap_preserves_constant_differences(self):
        values = {(live.PROFILE, p, law, r): (-0.02, 0., 0.01)
                  for p in ("colocated", "split") for law in ("N", "ND") for r in range(2)}
        result = analysis.bootstrap_family(values, repetitions=2, resamples=100)
        for name, expected in zip(analysis.METRICS, (-0.02, 0, 0.01), strict=True):
            for field in ("estimate", "lower", "upper"):
                self.assertAlmostEqual(result[name][field], expected)
            self.assertAlmostEqual(result[name]["confidence_level"], 1 - 0.05 / 3)
        missing = dict(values)
        missing.pop(next(iter(missing)))
        with self.assertRaisesRegex(ValueError, "incomplete"):
            analysis.bootstrap_family(missing, repetitions=2, resamples=100)

    def test_campaign_weighting_is_equal_across_strata(self):
        values = {(live.PROFILE, p, law, r): (float(10 * i + r), 0., 0.)
                  for i, (p, law) in enumerate((('colocated', 'N'), ('colocated', 'ND'), ('split', 'N'), ('split', 'ND')))
                  for r in range(2)}
        result = analysis.bootstrap_family(values, repetitions=2, resamples=100)
        self.assertEqual(result[analysis.METRICS[0]]["estimate"], 15.5)

    def test_three_questions_require_whole_intervals_and_integrity(self):
        intervals = dict(zip(analysis.METRICS, (
            {"lower": -0.02, "upper": -0.001},
            {"lower": -0.001, "upper": 0.001},
            {"lower": -0.025, "upper": 0.025}), strict=True))
        result = analysis.classify(intervals, True)
        self.assertEqual(result["conditional_temporal_information"], "replicated")
        self.assertEqual(result["marginal_increment"], "practically_equivalent")
        self.assertEqual(result["mean_marginal_calibration"], "adequate")
        intervals[analysis.METRICS[1]] = {"lower": -0.004, "upper": -0.001}
        intervals[analysis.METRICS[2]] = {"lower": -0.031, "upper": 0.01}
        result = analysis.classify(intervals, True)
        self.assertEqual(result["marginal_increment"], "unresolved")
        self.assertEqual(result["mean_marginal_calibration"], "not_confirmed")
        intervals[analysis.METRICS[1]]["upper"] = -0.0021
        self.assertEqual(analysis.classify(intervals, True)["marginal_increment"], "material_temporal_advantage")
        self.assertFalse(analysis.classify(intervals, False)["inferential_claims_admissible"])
        self.assertEqual(analysis.classify(intervals, False)["conditional_temporal_information"], "inadequate_confirmation")

    def test_configuration_preserves_age_and_optimizer_gates(self):
        config = analysis.analysis_config()
        self.assertEqual(config.seed, 2026090703)
        self.assertEqual(config.resamples, 10000)
        audit = dict(stable_aligned_requests=500, maximum_age_interval_width=1.1,
                     one_path_up_requests=100, one_path_up_episodes=8,
                     early_one_path_requests=20, late_one_path_requests=20)
        self.assertTrue(analysis.adequacy_passed(audit, config))
        audit["one_path_up_episodes"] = 7
        self.assertFalse(analysis.adequacy_passed(audit, config))
        self.assertTrue(analysis.adequacy_passed(audit, config, test=True))
        fit = dict(finite_starts=8, converged_starts=1, equivalent_prediction_range=1e-4)
        self.assertTrue(analysis.optimizer_passed(fit, config))
        fit["finite_starts"] = 7
        self.assertFalse(analysis.optimizer_passed(fit, config))

    def test_physical_evaluator_tree_is_rejected_before_candidate_loading(self):
        with TemporaryDirectory() as temp:
            (Path(temp) / "hidden/evaluator").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "held-out evaluator"):
                analysis.discover_bundles(temp, live.LEARNER_FILES)

    def test_local_full_analysis_is_rejected_before_data_access(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(ValueError, "only in GitHub Actions"):
                analysis.freeze_candidates("missing", "missing")
            with self.assertRaisesRegex(ValueError, "only in GitHub Actions"):
                analysis.evaluate("missing", "missing", "missing")

    def test_synthetic_pipeline_freezes_before_test_and_reports_inadequacy(self):
        # Four tiny, artificial, all-up cells exercise serialization and the
        # evaluator boundary; this is not a local campaign analysis.
        keys = {(live.PROFILE, p, law, 0) for p in ("colocated", "split") for law in ("N", "ND")}
        config = replace(analysis.analysis_config(), repetitions=(0,), expected_cells=4, resamples=20)
        bootstrap = analysis.bootstrap_family
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for key in keys:
                cell = dict(zip(live.IDENTITY, key, strict=True))
                directory = root / "learner" / (key[1] + key[2])
                live.write_json(directory / "learner/manifest.json", cell)
                live.write_json(directory / "learner/deployment.json", {"target_service": "product-catalog"})
                live.write_json(directory / "audit/boundary.json", {"usable": True})
                requests = [{"period": period, "request_id": f"synthetic-{period}-{i}", "operation": "checkout",
                             "started_at": f"2026-09-07T01:00:{at:02d}Z", "semantic_success": True,
                             "trace_present": False, "span_count": 0, "services": "", "target_replicas": ""}
                            for period, i, at in (("baseline", 0, 1), ("baseline", 1, 2),
                                                  ("calibration", 0, 10), ("calibration", 1, 11), ("calibration", 2, 12), ("calibration", 3, 13))]
                live.write_csv(directory / "learner/requests.csv", requests)
                ticks = []
                for at in range(10, 21):
                    row = {"observed_at": f"2026-09-07T01:00:{at:02d}Z", "elapsed_seconds": at - 10}
                    for replica in ("a", "b"):
                        row.update({f"replica_{replica}_observed": True, f"replica_{replica}_running": True,
                                    f"replica_{replica}_paused": False, f"replica_{replica}_network_count": 1,
                                    f"replica_{replica}_backend_status": "UP", f"replica_{replica}_backend_check_status": "L4OK"})
                    ticks.append(row)
                live.write_csv(directory / "learner/health.csv", ticks)
                metadata = {**cell, "scope": "full", "source_run_id": "synthetic", "source_commit": "synthetic",
                            "source_attempt": "1", "config_sha256": live.file_sha256(live.CONFIG)}
                live.seal(directory, metadata)
                evaluator = root / "evaluator" / (key[1] + key[2])
                live.write_csv(evaluator / "evaluator/test-health.csv", ticks)
                live.write_csv(evaluator / "evaluator/test-requests.csv", [
                    {"operation": "checkout", "started_at": f"2026-09-07T01:00:{at:02d}Z", "semantic_success": success}
                    for at, success in ((11, True), (12, False), (13, True))])
                live.seal(evaluator, metadata)
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ID": "synthetic", "GITHUB_SHA": "synthetic", "GITHUB_RUN_ATTEMPT": "1"}), \
                 patch.object(live, "expected_identities", return_value=keys), \
                 patch.object(analysis, "analysis_config", return_value=config), \
                 patch.object(analysis, "bootstrap_family", side_effect=lambda values, **kwargs: bootstrap(values, repetitions=1, **kwargs)), \
                 patch("builtins.print"):
                frozen = analysis.freeze_candidates(root / "learner", root / "candidates")
                before = (root / "candidates/candidate-predictions.csv").read_bytes()
                result = analysis.evaluate(root / "evaluator", root / "candidates", root / "result")
                self.assertEqual(before, (root / "candidates/candidate-predictions.csv").read_bytes())
                self.assertFalse(frozen["test_outcomes_accessed"])
                self.assertEqual(frozen["candidate_rows"], 28)
                self.assertEqual(set(result["intervals"]), set(analysis.METRICS))
                self.assertEqual(result["status"], "independent_confirmation_inadequate")
                self.assertFalse(result["inferential_claims_admissible"])
                self.assertAlmostEqual(result["intervals"][analysis.METRICS[1]]["estimate"], 0)

    def test_main_workflow_enforces_upload_before_evaluator(self):
        workflow = yaml.safe_load((live.ROOT / ".github/workflows/m9p-temporal-confirmation.yml").read_text())
        jobs = workflow["jobs"]
        self.assertEqual(set(jobs), {"readiness", "campaign", "candidates", "evaluation", "audit"})
        self.assertTrue(all(job["timeout-minutes"] == 360 for job in jobs.values()))
        self.assertEqual(jobs["campaign"]["needs"], "readiness")
        self.assertEqual(jobs["candidates"]["needs"], "campaign")
        self.assertIn("candidates", jobs["evaluation"]["needs"])
        candidate_downloads = [step["with"] for step in jobs["candidates"]["steps"] if step.get("uses", "").startswith("actions/download-artifact")]
        self.assertEqual(len(candidate_downloads), 1)
        self.assertTrue(candidate_downloads[0]["pattern"].startswith("m9p-main-learner-"))
        evaluation = jobs["evaluation"]["steps"]
        gate = next(i for i, step in enumerate(evaluation) if "before-evaluator" in step.get("run", ""))
        download = next(i for i, step in enumerate(evaluation) if step.get("with", {}).get("pattern", "").startswith("m9p-main-evaluator-"))
        self.assertLess(gate, download)
        matrix = jobs["campaign"]["strategy"]["matrix"]
        self.assertEqual(len(matrix["application"]) * len(matrix["placement"]) * len(matrix["law"]) * len(matrix["repetition"]), 120)


if __name__ == "__main__":
    unittest.main()
