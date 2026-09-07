from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import yaml

from telemetry_availability import checkout_temporal_failover as temporal
from telemetry_availability.live_validation_analysis import HealthTick

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/m9n_checkout_temporal_failover.json"


class CheckoutTemporalFailoverTests(unittest.TestCase):
    def test_remote_boundary_and_dependencies(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/m9n-checkout-temporal-failover.yml").read_text(encoding="utf-8"))
        jobs = workflow["jobs"]
        self.assertEqual(len(jobs), 3)
        self.assertTrue(all(job["timeout-minutes"] == 360 for job in jobs.values()))
        self.assertEqual(jobs["learner_candidate_freeze"]["needs"], ["temporal_contract"])
        self.assertEqual(set(jobs["heldout_evaluation"]["needs"]), {"temporal_contract", "learner_candidate_freeze"})
        steps = jobs["learner_candidate_freeze"]["steps"]
        stage = next(i for i, step in enumerate(steps) if "stage-learner" in step.get("run", ""))
        fit = next(i for i, step in enumerate(steps) if "freeze-candidates" in step.get("run", ""))
        self.assertLess(stage, fit)
        self.assertIn('for source in m8a-preserved m9m-candidates', steps[stage]["run"])
        self.assertIn('test ! -e "workflow-input/m9n/$source"', steps[stage]["run"])
        self.assertTrue(steps[-1]["uses"].startswith("actions/upload-artifact@"))
        self.assertEqual(steps[-1]["with"]["if-no-files-found"], "error")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            for function, nargs in ((temporal.stage_learner_inputs, 7), (temporal.generate_candidates, 4), (temporal.evaluate_candidates, 6)):
                with self.subTest(function=function.__name__), self.assertRaisesRegex(ValueError, "only in GitHub Actions"):
                    function(*([Path("missing")] * nargs))

    def test_repository_contract(self):
        self.assertEqual(temporal.validate_repository(CONFIG)["status"], "m9n_repository_contract_valid")

    def test_temporal_alignment_censoring_and_physical_transition_guard(self):
        ticks = []
        for at in range(21):
            paths = (1, 0) if at < 3 or 6 <= at < 11 else (0, 1) if at < 15 and at >= 11 else (0, 0) if at >= 18 else (1, 1)
            ticks.append(HealthTick(at, at, (int(at < 8), 1, *paths)))
        requests = [SimpleNamespace(at=at, operation="checkout", success=1) for at in (0.1, 4.5, 6.5, 8.2, 9.5, 12.2, 16.2, 19.2, 100)]
        records, audit = temporal._temporal_records(requests, ticks, "checkout", 1.25, 1)
        self.assertEqual(audit["left_censored_one_path_requests"], 1)
        self.assertEqual(audit["transition_guarded_requests"], 2)
        self.assertEqual(audit["unaligned_requests"], 1)
        self.assertEqual([record.path_count for record in records], [2, 1, 1, 2, 0])
        self.assertEqual((records[1].lower_age, records[1].midpoint_age, records[1].upper_age), (3.5, 4.0, 4.5))
        self.assertAlmostEqual(records[2].midpoint_age, 1.7)
        self.assertNotEqual(records[1].episode_id, records[2].episode_id)
        self.assertEqual(audit["one_path_up_episodes"], 2)

    def test_first_both_and_neither_episodes_do_not_need_age(self):
        request = SimpleNamespace(at=0.2, operation="checkout", success=1)
        for paths in ((0, 0), (1, 1)):
            ticks = [HealthTick(at, at, (1, 1, *paths)) for at in (0, 1)]
            records, audit = temporal._temporal_records([request], ticks, "checkout", 1.25, 1)
            self.assertEqual(len(records), 1)
            self.assertEqual(audit["left_censored_one_path_requests"], 0)

    def test_route_limits_and_outcome_free_marginalization(self):
        record = temporal.TemporalRecord(0, 1, 1, 0, 0.25, 0.5)
        self.assertEqual(temporal._route_value(record, "source_500ms_failover"), 0.5)
        self.assertEqual(temporal._route_value(replace(record, midpoint_age=3), "source_500ms_failover"), 1)
        records = [replace(record, path_count=count) for count in (0, 1, 2)]
        prediction = temporal._marginal_prediction(records, 0.8, "learner_state_only", [0])
        self.assertAlmostEqual(prediction, 0.4)
        self.assertEqual(prediction, temporal._marginal_prediction([replace(row, success=1) for row in records], 0.8, "learner_state_only", [0]))
        self.assertAlmostEqual(temporal._negative_log_likelihood(np.array([0.]), [record], 0.8, "learner_state_only", 1e-12), -np.log(0.6))

    def test_logit_recovers_known_small_binomial_rates(self):
        config = temporal.load_temporal_config(CONFIG)
        rows = [temporal.TemporalRecord(int(i < successes), 1, 1, age, age, age) for age, successes in ((1., 2), (7., 8)) for i in range(10)]
        fit = temporal._fit_logit(rows, 1.0, temporal.PRIMARY_METHOD, ("synthetic", "split", "N", 0), config)
        self.assertEqual(fit["finite_starts"], 8)
        self.assertGreaterEqual(fit["converged_starts"], 1)
        self.assertLessEqual(fit["equivalent_prediction_range"], 1e-4)
        for index, expected in ((0, 0.2), (10, 0.8)):
            self.assertAlmostEqual(temporal._route_value(rows[index], temporal.PRIMARY_METHOD, fit["parameters"]), expected, places=4)

    def test_weighted_pava_and_empty_bins(self):
        np.testing.assert_allclose(temporal._weighted_pava([0.8, 0.2, 0.9], [1, 3, 1]), [0.35, 0.35, 0.9])
        rows = [temporal.TemporalRecord(int(i < successes), 1, 1, age, age, age) for age, successes in ((2.5, 8), (9., 2)) for i in range(10)]
        fit = temporal._fit_monotone_bins(rows, 1)
        self.assertTrue(all(a <= b for a, b in zip(fit["bin_values"], fit["bin_values"][1:])))
        np.testing.assert_allclose(fit["bin_values"], [0.5] * 6)

    def test_interval_sensitivity_cannot_cancel_between_cells(self):
        rows = [{"profile": "synthetic", "placement": "split", "failure_law": "N", "repetition": rep, "method": f"temporal_logit_{view}", "prediction": value} for rep, values in enumerate(((0.1, 0.5, 0.9), (0.9, 0.5, 0.1))) for view, value in zip(temporal.AGE_VIEWS, values)]
        self.assertAlmostEqual(temporal._mean_interval_prediction_span(rows), 0.8)
        with self.assertRaisesRegex(ValueError, "matrix differs"):
            temporal._mean_interval_prediction_span(rows[:-1])

    def test_paired_campaign_bootstrap_preserves_constant_difference(self):
        rows = [{"profile": "synthetic", "placement": placement, "failure_law": law, "repetition": rep, "method": method, "brier_score": rep / 100 + offset, "absolute_error": rep / 100 + offset} for placement in ("colocated", "split") for law in ("N", "ND") for rep in range(10) for method, offset in (("a", 0.1), ("b", 0.2))]
        bootstrap = temporal._bootstrap_matrix(rows, ("a", "b"), ("brier_score", "absolute_error"), {"b": "b"}, 11, 19, 0.95)
        np.testing.assert_allclose(list(bootstrap["a.delta_brier_vs_b"].values()), [-0.1] * 3)
        with self.assertRaisesRegex(ValueError, "duplicate method"):
            temporal._bootstrap_matrix(rows + rows[:1], ("a", "b"), ("brier_score",), {}, 11, 19, 0.95)

    def test_classification_requires_strong_reference_and_all_gates(self):
        primary = temporal.PRIMARY_METHOD
        marginal = {f"{primary}.signed_error": {"estimate": 0, "lower": -0.01, "upper": 0.01}, **{f"{primary}.delta_{metric}_vs_{reference}": {"upper": upper} for metric in ("brier", "absolute_error") for reference, upper in (("or", -0.01), ("b0", 0.01))}}
        conditional = {"conditional_temporal_midpoint.delta_brier_vs_state": {"upper": -0.01}}
        kwargs = dict(integrity_passed=True, calibration_signature_passed=True, interval_prediction_span=0.01, closure_margin=0.03, interval_span_limit=0.02)
        self.assertEqual(temporal.classify_evaluation(marginal, conditional, **kwargs)["branch_key"], "temporal_without_b0_advantage")
        self.assertEqual(temporal.classify_evaluation(marginal, conditional, **{**kwargs, "integrity_passed": False})["branch_key"], "integrity_fail")
        self.assertEqual(temporal.classify_evaluation(marginal, conditional, **{**kwargs, "calibration_signature_passed": False})["branch_key"], "no_recovery")
        self.assertEqual(temporal.classify_evaluation(marginal, conditional, **{**kwargs, "interval_prediction_span": 0.03})["branch_key"], "conditional_only")
        for metric in ("brier", "absolute_error"):
            marginal[f"{primary}.delta_{metric}_vs_b0"]["upper"] = -0.01
        self.assertEqual(temporal.classify_evaluation(marginal, conditional, **kwargs)["branch_key"], "temporal_with_b0_advantage")

    def test_learner_files_reject_corruption_and_evaluator_presence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            rows = []
            for name in temporal.LEARNER_FILES:
                target = root / "synthetic-cell" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("synthetic", encoding="utf-8")
                rows.append({"staged_path": target.relative_to(root).as_posix(), "bytes": target.stat().st_size, "sha256": temporal.file_sha256(target)})
            for name in ("stage-manifest.json", temporal.REFERENCE_NAME):
                (root / name).write_text("synthetic", encoding="utf-8")
            audit = root / "learner-file-audit.csv"
            temporal._write_csv(audit, list(rows[0]), rows)
            stage = {"files": {audit.name: temporal.file_sha256(audit)}}
            temporal._verify_staged_learner_files(root, stage, 1)
            evaluator = root / "synthetic-cell/evaluator"
            evaluator.mkdir()
            with self.assertRaisesRegex(ValueError, "evaluator path present"):
                temporal._verify_staged_learner_files(root, stage, 1)
            evaluator.rmdir()
            (root / "synthetic-cell/learner/requests.csv").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "byte identity differs"):
                temporal._verify_staged_learner_files(root, stage, 1)


if __name__ == "__main__":
    unittest.main()
