from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.live_validation_analysis import (
    EvaluationRequest,
    HealthTick,
    QualifiedCell,
)
from telemetry_availability.m7_diagnostic_analysis import (
    audit_scores,
    inventory_files,
    load_artifact_inventory,
    outcome_counts,
)


class M7DiagnosticAnalysisTests(unittest.TestCase):
    def test_inventory_flattens_paginated_api_and_classifies_source_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifacts.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "artifacts": [
                                {
                                    "id": 2,
                                    "name": "m7-qualified-app-split-N-r0-42",
                                    "size_in_bytes": 20,
                                    "expired": False,
                                    "expires_at": "later",
                                    "digest": "sha256:b",
                                }
                            ]
                        },
                        {
                            "artifacts": [
                                {
                                    "id": 1,
                                    "name": "m7-frozen-analysis-42",
                                    "size_in_bytes": 10,
                                    "expired": False,
                                    "expires_at": "later",
                                    "digest": "sha256:a",
                                }
                            ]
                        },
                    ]
                ),
                encoding="utf-8",
            )
            rows = load_artifact_inventory(path, "42")
        self.assertEqual([row["artifact_id"] for row in rows], [1, 2])
        self.assertEqual([row["kind"] for row in rows], ["analysis", "qualified_cell"])

    def test_file_inventory_records_relative_path_size_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "nested"
            nested.mkdir()
            (nested / "sample.txt").write_bytes(b"evidence\n")
            rows = inventory_files({"qualified": root})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["relative_path"], "nested/sample.txt")
        self.assertEqual(rows[0]["size_in_bytes"], 9)
        self.assertEqual(len(rows[0]["sha256"]), 64)

    def test_score_is_recomputed_from_request_outcomes_and_stable_guard(self) -> None:
        cell = QualifiedCell(
            profile="app",
            placement="split",
            failure_law="N",
            repetition=0,
            target_service="target",
            learner_requests=(),
            health=(),
            test_requests=(
                EvaluationRequest("op", 10.2, 1),
                EvaluationRequest("op", 11.1, 0),
                EvaluationRequest("op", 20.0, 1),
            ),
            test_health=(
                HealthTick(9.0, 0.0, (1, 1, 1, 1)),
                HealthTick(11.0, 2.0, (0, 1, 0, 1)),
                HealthTick(19.0, 10.0, (0, 1, 0, 1)),
            ),
            boundary={"usable": True},
            directory=Path("synthetic"),
        )
        counts = outcome_counts([cell], guard_seconds=1)
        self.assertEqual(counts[("app", "split", "N", 0, "all_sequence", "op")], (3, 2))
        self.assertEqual(counts[("app", "split", "N", 0, "stable", "op")], (1, 1))
        row = {
            "profile": "app",
            "failure_law": "N",
            "repetition": "0",
            "mode": "full",
            "scope": "current",
            "source_placement": "split",
            "target_placement": "split",
            "method": "B2",
            "view": "stable",
            "operation": "op",
            "prediction": "0.75",
            "test_requests": "1",
            "test_successes": "1",
            "test_success_fraction": "1.0",
            "brier_score": "0.0625",
            "signed_prediction_error": "-0.25",
            "absolute_prediction_error": "0.25",
            "prediction_in_test_block_interval": "true",
        }
        audit = audit_scores([row], counts)
        self.assertTrue(audit[0]["matches"])
        self.assertEqual(audit[0]["recomputed_brier_score"], 0.0625)


if __name__ == "__main__":
    unittest.main()
