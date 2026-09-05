from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.live_evidence import (
    parse_jaeger_trace_evidence,
    parse_otlp_jsonl_trace_evidence,
    qualify_evidence_cell,
)
from telemetry_availability.live_evidence_config import (
    load_evidence_boundary_config,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m7d_evidence_boundary.yaml"


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class LiveEvidenceBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_evidence_boundary_config(CONFIG_PATH)

    def test_contract_separates_allowed_and_privileged_sources(self) -> None:
        self.assertTrue(self.config.diagnostic_only)
        self.assertFalse(self.config.main_effectiveness)
        self.assertEqual(self.config.expected_source_cells, 64)
        self.assertEqual(self.config.learner_period, "calibration")
        self.assertEqual(self.config.source_manifest_file, "pilot-manifest.json")
        self.assertEqual(self.config.required_source_labels, {"pilot_only": True})
        self.assertFalse(
            set(self.config.allowed_source_files).intersection(
                self.config.privileged_source_files
            )
        )
        self.assertIn("events.csv", self.config.privileged_source_files)

    def test_jaeger_parser_recovers_trace_graph_and_replica(self) -> None:
        profile = self.config.profile("deathstarbench_social_network")
        document = {
            "data": [
                {
                    "traceID": "0123456789abcdef",
                    "processes": {
                        "front": {
                            "serviceName": "frontend",
                            "tags": [{"key": "hostname", "value": "frontend"}],
                        },
                        "target": {
                            "serviceName": "user-timeline-service",
                            "tags": [
                                {
                                    "key": "hostname",
                                    "value": "user-timeline-service-replica-a",
                                }
                            ],
                        },
                    },
                    "spans": [
                        {
                            "spanID": "0000000000000001",
                            "processID": "front",
                            "operationName": "request",
                            "references": [],
                        },
                        {
                            "spanID": "0000000000000002",
                            "processID": "target",
                            "operationName": "read",
                            "references": [
                                {
                                    "refType": "CHILD_OF",
                                    "spanID": "0000000000000001",
                                }
                            ],
                        },
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "traces.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            parsed = parse_jaeger_trace_evidence(profile, path, ["0123456789abcdef"])
        spans = parsed.spans_by_trace["0123456789abcdef"]
        self.assertEqual(len(spans), 2)
        self.assertEqual({row.target_replica for row in spans}, {"", "a"})
        self.assertEqual(parsed.invalid_records, 0)
        self.assertEqual(parsed.unknown_target_instances, 0)
        self.assertEqual(parsed.truncated_tail_records, 0)

    def test_otlp_jsonl_parser_filters_to_expected_trace_and_replica(self) -> None:
        profile = self.config.profile("opentelemetry_demo")
        expected = "0123456789abcdef0123456789abcdef"
        document = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "product-catalog"},
                            },
                            {
                                "key": "study.replica",
                                "value": {"stringValue": "b"},
                            },
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": expected,
                                    "spanId": "0000000000000001",
                                    "name": "get-product",
                                },
                                {
                                    "traceId": "f" * 32,
                                    "spanId": "0000000000000002",
                                    "name": "not-calibration",
                                },
                            ]
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "traces.log"
            path.write_text(json.dumps(document) + "\n", encoding="utf-8")
            parsed = parse_otlp_jsonl_trace_evidence(profile, path, [expected])
        self.assertEqual(set(parsed.spans_by_trace), {expected})
        self.assertEqual(parsed.spans_by_trace[expected][0].target_replica, "b")
        self.assertEqual(parsed.invalid_records, 0)
        self.assertEqual(parsed.truncated_tail_records, 0)

    def test_otlp_parser_tolerates_only_nonlearner_unterminated_tail(self) -> None:
        profile = self.config.profile("opentelemetry_demo")
        expected = "0123456789abcdef0123456789abcdef"
        valid = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": "product-catalog"},
                            },
                            {
                                "key": "study.replica",
                                "value": {"stringValue": "a"},
                            },
                        ]
                    },
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": expected,
                                    "spanId": "0000000000000001",
                                    "name": "get-product",
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        cases = (
            ('{"resourceSpans":[{"unrelated":', 0, 1),
            ('{"traceId":"' + expected + '",', 1, 0),
            ('{"resourceSpans":[}\n', 1, 0),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "traces.log"
            for tail, expected_invalid, expected_tolerated in cases:
                path.write_text(json.dumps(valid) + "\n" + tail, encoding="utf-8")
                parsed = parse_otlp_jsonl_trace_evidence(profile, path, [expected])
                self.assertEqual(parsed.invalid_records, expected_invalid)
                self.assertEqual(
                    parsed.truncated_tail_records,
                    expected_tolerated,
                )

    def test_cell_qualification_physically_sequesters_test_and_events(self) -> None:
        profile = self.config.profile("deathstarbench_social_network")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            calibration_ids = ("0123456789abcdef", "fedcba9876543210")
            manifest = {
                "experiment_id": self.config.source_experiment_id,
                "pilot_only": True,
                "usable_for_m7_freeze": True,
                "profile": profile.id,
                "placement": "split",
                "failure_law": "NCD",
                "repetition": 0,
                "period_summaries": {
                    "calibration": {"requests": 2},
                    "test": {"requests": 1},
                },
            }
            (source / self.config.source_manifest_file).write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            request_rows = [
                {
                    "period": "calibration",
                    "request_id": f"cal-{index}",
                    "trace_id": trace_id,
                    "operation": "read",
                    "branch_class": "observed_mix",
                    "started_at": f"2026-01-01T00:00:0{index}Z",
                    "completed_at": f"2026-01-01T00:00:0{index}.1Z",
                    "semantic_success": True,
                    "timed_out": False,
                }
                for index, trace_id in enumerate(calibration_ids)
            ]
            request_rows.append(
                {
                    "period": "test",
                    "request_id": "test-0",
                    "trace_id": "aaaaaaaaaaaaaaaa",
                    "operation": "read",
                    "branch_class": "observed_mix",
                    "started_at": "2026-01-01T00:01:00Z",
                    "completed_at": "2026-01-01T00:01:00.1Z",
                    "semantic_success": True,
                    "timed_out": False,
                }
            )
            _write_csv(source / "requests.csv", request_rows)
            _write_csv(
                source / "trace-join.csv",
                [
                    {
                        "period": "calibration",
                        "request_id": f"cal-{index}",
                        "trace_present": True,
                    }
                    for index in range(2)
                ],
            )
            health_rows = []
            for role, replica, service in (
                ("proxy", "", "user-timeline-service"),
                ("replica", "a", "user-timeline-service-replica-a"),
                ("replica", "b", "user-timeline-service-replica-b"),
            ):
                health_rows.append(
                    {
                        "period": "calibration",
                        "observed_at": "2026-01-01T00:00:00Z",
                        "elapsed_seconds": 0,
                        "role": role,
                        "replica": replica,
                        "service": service,
                        "running": True,
                        "paused": False,
                        "health": "healthy",
                        "network_count": 1,
                        "backend_status": "UP" if replica else "",
                        "backend_check_status": "L4OK" if replica else "",
                        "error": "",
                    }
                )
            health_rows.extend(
                {
                    **row,
                    "period": "test",
                    "observed_at": "2026-01-01T00:01:00Z",
                }
                for row in tuple(health_rows)
            )
            _write_csv(source / "health.csv", health_rows)
            traces = []
            for trace_id, replica in zip(calibration_ids, ("a", "b"), strict=True):
                traces.append(
                    {
                        "traceID": trace_id,
                        "processes": {
                            "p1": {
                                "serviceName": "frontend",
                                "tags": [{"key": "hostname", "value": "front"}],
                            },
                            "p2": {
                                "serviceName": "user-timeline-service",
                                "tags": [
                                    {
                                        "key": "hostname",
                                        "value": (
                                            "user-timeline-service-replica-" + replica
                                        ),
                                    }
                                ],
                            },
                        },
                        "spans": [
                            {
                                "spanID": f"{1 + 2 * len(traces):016x}",
                                "processID": "p1",
                                "operationName": "request",
                                "references": [],
                            },
                            {
                                "spanID": f"{2 + 2 * len(traces):016x}",
                                "processID": "p2",
                                "operationName": "read",
                                "references": [
                                    {
                                        "refType": "CHILD_OF",
                                        "spanID": f"{1 + 2 * len(traces):016x}",
                                    }
                                ],
                            },
                        ],
                    }
                )
            (source / profile.raw_telemetry_file).write_text(
                json.dumps({"data": traces}), encoding="utf-8"
            )
            image_audit = {
                "placement_pilot": {
                    "target_service": "user-timeline-service",
                    "proxy_service": "user-timeline-service",
                    "replica_services": {
                        "a": "user-timeline-service-replica-a",
                        "b": "user-timeline-service-replica-b",
                    },
                    "domain_assignments": {
                        "a": "domain_a",
                        "b": "domain_b",
                    },
                }
            }
            (source / "image-lock-audit.json").write_text(
                json.dumps(image_audit), encoding="utf-8"
            )
            (source / "events.csv").write_text(
                "event_id,cause\nprivileged,domain\n", encoding="utf-8"
            )

            summary = qualify_evidence_cell(self.config, source, output)

            self.assertTrue(summary["usable"])
            self.assertEqual(summary["calibration_requests"], 2)
            self.assertEqual(summary["test_requests_sequestered"], 1)
            self.assertEqual(summary["test_health_ticks_sequestered"], 1)
            learner_text = (output / "learner" / "requests.csv").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("test-0", learner_text)
            self.assertFalse((output / "learner" / "events.csv").exists())
            self.assertTrue((output / "evaluator" / "test-health.csv").is_file())
            audit = json.loads(
                (output / "audit" / "boundary.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["quality"]["learner_test_request_overlap"], 0)
            self.assertEqual(audit["privileged_files_parsed_for_learner"], [])


if __name__ == "__main__":
    unittest.main()
