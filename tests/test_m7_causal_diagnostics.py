from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.live_validation_analysis import HealthTick, QualifiedCell
from telemetry_availability.m7_causal_diagnostics import (
    _nearest_index,
    _transitions,
    raw_semantic_rows,
    run_m7_causal_diagnostics,
)
from telemetry_availability.m7_diagnostic_analysis import M7DiagnosticError


class M7CausalDiagnosticTests(unittest.TestCase):
    def test_transition_direction_uses_route_union(self) -> None:
        cell = QualifiedCell(
            profile="app",
            placement="split",
            failure_law="NCD",
            repetition=0,
            target_service="target",
            learner_requests=(),
            health=(),
            test_requests=(),
            test_health=(
                HealthTick(1.0, 0.0, (1, 1, 1, 1)),
                HealthTick(2.0, 1.0, (0, 0, 0, 0)),
                HealthTick(3.0, 2.0, (1, 0, 1, 0)),
                HealthTick(4.0, 3.0, (1, 1, 1, 0)),
            ),
            boundary={"usable": True},
            directory=Path("synthetic"),
        )
        self.assertEqual(
            [row["direction"] for row in _transitions(cell)],
            ["route_degradation", "route_recovery", "other_signal_change"],
        )

    def test_nearest_index_handles_boundaries_and_empty_series(self) -> None:
        index, distance = _nearest_index(2.6, (1.0, 3.0, 8.0))
        self.assertEqual(index, 1)
        self.assertAlmostEqual(distance, 0.4)
        index, distance = _nearest_index(2.0, ())
        self.assertEqual(index, -1)
        self.assertGreater(distance, 1e100)

    def test_raw_semantics_distinguish_http_and_semantic_success(self) -> None:
        fields = (
            "profile",
            "placement",
            "failure_law",
            "repetition",
            "period",
            "operation",
            "status_code",
            "immediate_success",
            "semantic_success",
            "semantic_reason",
            "timed_out",
            "error",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample" / "requests.csv"
            path.parent.mkdir()
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "profile": "app",
                            "placement": "split",
                            "failure_law": "NCD",
                            "repetition": 0,
                            "period": "test",
                            "operation": "op",
                            "status_code": 200,
                            "immediate_success": True,
                            "semantic_success": False,
                            "semantic_reason": "wrong_payload",
                            "timed_out": False,
                            "error": "",
                        },
                        {
                            "profile": "app",
                            "placement": "split",
                            "failure_law": "NCD",
                            "repetition": 0,
                            "period": "test",
                            "operation": "op",
                            "status_code": 503,
                            "immediate_success": False,
                            "semantic_success": False,
                            "semantic_reason": "",
                            "timed_out": False,
                            "error": "",
                        },
                    ]
                )
            rows, reasons, paths = raw_semantic_rows(Path(temporary))
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["http_2xx_semantic_failures"], 1)
        self.assertEqual(rows[0]["immediate_semantic_disagreements"], 1)
        self.assertEqual(rows[0]["non_2xx"], 1)
        self.assertEqual(sum(row["count"] for row in reasons), 2)

    def test_full_diagnostic_is_forbidden_locally(self) -> None:
        with self.assertRaisesRegex(M7DiagnosticError, "only in GitHub Actions"):
            run_m7_causal_diagnostics(  # type: ignore[arg-type]
                None, None, Path("missing"), Path("missing"), Path("missing"), Path("out")
            )


if __name__ == "__main__":
    unittest.main()
