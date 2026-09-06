from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.pmx_performability import file_sha256
from telemetry_availability.pmx_recovery import (
    _audit_jaeger_raw,
    _audit_otlp_raw,
    _learner_trace_ids,
    decide,
    load_pmx_recovery_config,
    select_launcher,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9g_pmx_recovery.json"
PROTOCOL = ROOT / "docs" / "M9G_PMX_RECOVERY_AND_APPLICATION_DELTA_PROTOCOL.md"
MANUAL = ROOT / "docs" / "M9G_MANUAL_ACTIONS.csv"
WORKFLOW = ROOT / ".github" / "workflows" / "m9g-pmx-recovery.yml"


class PMXRecoveryTests(unittest.TestCase):
    def test_frozen_contract_retains_priority_boundaries_and_remote_limits(self) -> None:
        config = load_pmx_recovery_config(CONFIG)
        self.assertEqual(config.timeout_seconds, 120)
        self.assertEqual(config.confirmation_repeats, 2)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.raw["accuracy_scoring"], "forbidden")
        self.assertEqual(config.raw["new_live_collection"], "forbidden")
        self.assertTrue(
            config.raw["scientific_priority"][
                "persists_if_application_cost_is_high"
            ]
        )
        self.assertFalse(
            config.raw["scientific_priority"][
                "tested_artifacts_represent_all_pmx_or_palladio"
            ]
        )
        self.assertFalse(
            config.raw["scientific_priority"][
                "retriever_result_generalizes_to_ecosystem"
            ]
        )

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertIn('SCREEN_TIMEOUT_SECONDS: "120"', workflow)
        self.assertIn(".launcher.candidate_order[]", workflow)
        self.assertIn("select-launcher", workflow)
        self.assertIn("audit-application-delta", workflow)
        self.assertNotIn("test-requests.csv", workflow)
        self.assertNotIn("test-health.csv", workflow)
        self.assertNotIn("scores.csv", workflow)
        self.assertNotIn("brier", workflow.lower())

    def test_repository_and_manual_prefix_locks_match(self) -> None:
        config = load_pmx_recovery_config(CONFIG)
        for record in config.raw["repository_locks"]:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(path.stat().st_size, record["bytes"], record["path"])
            self.assertEqual(file_sha256(path), record["sha256"], record["path"])
        manual = config.raw["manual_actions_log"]
        prefix = (ROOT / manual["path"]).read_bytes()[
            : manual["initial_size_in_bytes"]
        ]
        import hashlib

        self.assertEqual(hashlib.sha256(prefix).hexdigest(), manual["initial_sha256"])

    def test_protocol_explicitly_separates_output_launcher_and_accuracy(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("Historical output recovery does not prove", protocol)
        self.assertIn("Missing application support is cost", protocol)
        self.assertIn("all 160 `learner/` directories", protocol)
        self.assertIn("reads no M7 evaluator file", protocol)
        self.assertIn("All three use `timeout-minutes: 360`", protocol)

    def test_launcher_selection_uses_first_eligible_frozen_candidate(self) -> None:
        def fake_read_run(config: object, root: Path, label: str) -> dict[str, object]:
            del config, root
            eligible = label in {"gogo_scoped_execute", "gogo_scoped_main"}
            return {
                "label": label,
                "exit_code": 124 if eligible else 0,
                "timed_out": eligible,
                "output_eligible_as_original": eligible,
            }

        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "selection.json"
            with patch(
                "telemetry_availability.pmx_recovery._read_run",
                side_effect=fake_read_run,
            ):
                result = select_launcher(CONFIG, Path(temporary), out)
        self.assertEqual(result["selected"]["id"], "gogo_scoped_execute")
        self.assertEqual(result["selected"]["rank"], 2)
        self.assertTrue(result["selected"]["screen_timed_out"])
        self.assertFalse(result["accuracy_outcomes_used"])

    def test_trace_join_selects_learner_periods_without_using_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace-join.csv"
            path.write_text(
                "period,trace_id,request_success\n"
                "baseline,LEARN-A,false\n"
                "calibration,LEARN-B,true\n"
                "sentinel,SENTINEL,true\n"
                "test,TEST-A,false\n",
                encoding="utf-8",
            )
            selected, forbidden = _learner_trace_ids(
                path, {"baseline", "calibration"}, {"test"}
            )
        self.assertEqual(selected, {"learn-a", "learn-b"})
        self.assertEqual(forbidden, {"test-a"})

    def test_small_jaeger_schema_smoke_is_learner_filtered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "raw.json"
            payload = {
                "data": [
                    {
                        "traceID": "learn",
                        "processes": {
                            "p1": {
                                "serviceName": "catalog",
                                "tags": [
                                    {"key": "host.name", "value": "host-a"},
                                    {"key": "service.instance.id", "value": "instance-a"},
                                ],
                            }
                        },
                        "spans": [
                            {
                                "spanID": "span-a",
                                "operationName": "Catalog.get",
                                "startTime": 1,
                                "duration": 2,
                                "tags": [
                                    {"key": "otel.library.name", "value": "spring-webmvc"},
                                    {"key": "error", "value": True},
                                    {"key": "http.status_code", "value": 500},
                                ],
                            }
                        ],
                    },
                    {
                        "traceID": "test",
                        "processes": {},
                        "spans": [
                            {
                                "spanID": "hidden",
                                "operationName": "Hidden.test",
                                "startTime": 1,
                                "duration": 2,
                                "tags": [],
                            }
                        ],
                    },
                ]
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = _audit_jaeger_raw(path, {"learn"}, {"test"})
        self.assertEqual(result["selected_traces_present"], 1)
        self.assertEqual(result["selected_unique_spans"], 1)
        self.assertEqual(result["services"], 1)
        self.assertEqual(result["spring_webmvc_spans"], 1)
        self.assertEqual(result["direct_error_true_spans"], 1)
        self.assertEqual(result["forbidden_trace_spans_selected"], 0)
        self.assertEqual(result["malformed_jsonl_records"], 0)

    def test_small_otlp_schema_smoke_does_not_count_unselected_resources(self) -> None:
        def resource(service: str, trace: str, span: str) -> dict[str, object]:
            return {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service}},
                        {"key": "host.name", "value": {"stringValue": service + "-host"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "custom.instrumentation"},
                        "spans": [
                            {
                                "traceId": trace,
                                "spanId": span,
                                "name": "operation",
                                "startTimeUnixNano": "1",
                                "endTimeUnixNano": "2",
                                "attributes": [
                                    {
                                        "key": "http.response.status_code",
                                        "value": {"intValue": "500"},
                                    }
                                ],
                                "status": {"code": "STATUS_CODE_ERROR"},
                            }
                        ],
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "raw.log"
            path.write_text(
                json.dumps(
                    {
                        "resourceSpans": [
                            resource("selected-service", "learn", "span-a"),
                            resource("test-service", "test", "span-b"),
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = _audit_otlp_raw(path, {"learn"}, {"test"})
        self.assertTrue(result["schema_adapter_required"])
        self.assertEqual(result["selected_unique_spans"], 1)
        self.assertEqual(result["services"], 1)
        self.assertEqual(result["host_identifiers"], 1)
        self.assertEqual(result["otlp_error_status_spans"], 1)
        self.assertEqual(result["spring_webmvc_spans"], 0)

    def test_joint_decision_preserves_scientific_and_m7_guards(self) -> None:
        config_hash = file_sha256(CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            launcher = root / "launcher.json"
            application = root / "application.json"
            contract.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "historical_output_and_launcher_contract_audited",
                    }
                ),
                encoding="utf-8",
            )
            launcher.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "byte_pinned_gogo_output_recovered": False,
                        "launcher_terminates_cleanly": False,
                        "operation_failure_mechanism_reproduced": False,
                    }
                ),
                encoding="utf-8",
            )
            application.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "all_160_direct_raw_input_coverage": False,
                        "raw_subset_schema_adaptable": True,
                        "raw_subset_direct_instrumentation_semantics": False,
                        "additional_deployment_lifecycle_communication_mapping_required": True,
                    }
                ),
                encoding="utf-8",
            )
            result = decide(CONFIG, contract, launcher, application, root / "out")
        self.assertEqual(result["status"], "historical_output_recovered_launcher_unresolved")
        self.assertTrue(result["pmx_scientific_priority_retained"])
        self.assertFalse(result["tested_artifacts_represent_all_pmx_or_palladio"])
        self.assertFalse(result["retriever_result_generalizes_to_ecosystem"])
        self.assertFalse(result["accuracy_scoring_started"])
        self.assertFalse(result["m7_interpretation_changed"])


if __name__ == "__main__":
    unittest.main()
