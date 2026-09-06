from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.pmx_failure_semantics import (
    _stdout_aggregates,
    _trace_error_facts,
    _trace_from_options,
    _without_error_tags,
    decide,
    load_pmx_failure_semantics_config,
    validate_repository,
)
from telemetry_availability.pmx_performability import file_sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9i_pmx_failure_semantics.json"
PROTOCOL = ROOT / "docs" / "M9I_PMX_FAILURE_SEMANTICS_PROTOCOL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "m9i-pmx-failure-semantics.yml"


class PMXFailureSemanticsTests(unittest.TestCase):
    def test_frozen_contract_has_static_scope_and_remote_bounds(self) -> None:
        config = load_pmx_failure_semantics_config(CONFIG)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.confirmation_repeats, 2)
        self.assertEqual(config.raw["dynamic_pmx_invocation"], "forbidden")
        self.assertEqual(config.raw["workflow"]["dynamic_pmx_runs"], 0)
        self.assertEqual(len(config.raw["source_audit"]["bundles"]), 4)
        self.assertEqual(len(config.raw["source_audit"]["required_sources"]), 4)
        self.assertFalse(
            config.raw["decision"]["new_dynamic_control_allowed_in_m9i"]
        )

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertEqual(workflow.count("runs-on: ubuntu-latest"), 3)
        self.assertNotIn("java -jar", workflow)
        self.assertNotIn("main:main", workflow)
        self.assertNotIn("test-requests.csv", workflow)
        self.assertNotIn("scores.csv", workflow)
        self.assertNotIn("m8-preserved", workflow)

    def test_protocol_precludes_post_result_control_search(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("invoke PMX, try another tag", protocol)
        self.assertIn("complete source census", protocol)
        self.assertIn("later prospective mechanism test", protocol)
        self.assertIn("All three jobs use `timeout-minutes: 360`", protocol)
        self.assertIn("not generalized to all PMX", protocol)

    def test_repository_locks_validate(self) -> None:
        result = validate_repository(CONFIG)
        self.assertEqual(result["status"], "m9i_repository_contract_valid")
        self.assertEqual(len(result["repository_locks"]), 5)
        self.assertEqual(result["dynamic_pmx_runs"], 0)

    def test_retained_tag_and_stdout_helpers_expose_the_boundary(self) -> None:
        target = load_pmx_failure_semantics_config(CONFIG).raw["retained_boundary"][
            "target"
        ]
        payload = {
            "data": [
                {
                    "traceID": target["trace_id"],
                    "spans": [
                        {
                            "spanID": target["span_id"],
                            "operationName": target["operation"],
                            "tags": [
                                {"key": "otel.library.name", "value": "spring-webmvc"},
                                dict(target["tag"]),
                            ],
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "traces").mkdir()
            trace = root / "traces" / "control.json"
            trace.write_text(json.dumps(payload), encoding="utf-8")
            (root / "Options.txt").write_text(
                "-r reader -i traces/control.json -w writer", encoding="utf-8"
            )
            stdout = root / "stdout.log"
            stdout.write_text(
                "\n".join(
                    [
                        "Success: 10",
                        "Failure: null",
                        "Success: 10",
                        "Failure: null",
                        "Success: 9",
                        "Failure: null",
                        "Success: 10",
                        "Failure: null",
                        "Success: 1",
                        "Failure: null",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            relative, selected = _trace_from_options(root)
            facts, observed = _trace_error_facts(selected, target)
            successes, failures = _stdout_aggregates(stdout)

        self.assertEqual(relative, "traces/control.json")
        self.assertEqual(facts["error_tags"], 1)
        self.assertEqual(facts["target_error_tag"], target["tag"])
        self.assertEqual(facts["target_error_value_python_type"], "str")
        self.assertEqual(successes, [10, 10, 9, 10, 1])
        self.assertEqual(failures, [None, None, None, None, None])
        self.assertEqual(_without_error_tags(observed)["data"][0]["spans"][0]["tags"], [
            {"key": "otel.library.name", "value": "spring-webmvc"}
        ])

    def test_decision_routes_passed_evidence_to_prospective_controls(self) -> None:
        config_hash = file_sha256(CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.json"
            boundary = root / "boundary.json"
            source.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "exact_embedded_failure_sources_recovered",
                        "bundles_audited": 4,
                        "required_source_anchors_passed": 4,
                        "complete_source_census": True,
                        "dynamic_pmx_invocations": 0,
                    }
                ),
                encoding="utf-8",
            )
            boundary.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "exact_retained_failure_collapse_boundary_recovered",
                        "raw_mutation_present": True,
                        "complete_execution": True,
                        "confirmation_runs_audited": 4,
                        "dynamic_pmx_invocations": 0,
                        "stdout_failure_distinction": False,
                        "pcm_failure_distinction": False,
                    }
                ),
                encoding="utf-8",
            )
            result = decide(CONFIG, source, boundary, root / "out")

        self.assertEqual(
            result["status"],
            "pmx_exact_failure_sources_and_collapse_boundary_recovered",
        )
        self.assertEqual(
            result["earliest_observed_collapse"],
            "collapse_between_raw_tag_and_internal_operation_failure_aggregate",
        )
        self.assertEqual(
            result["next_milestone"], "m9j_source_derived_error_mapping_controls"
        )
        self.assertFalse(result["unique_root_cause_claimed_by_machine_decision"])
        self.assertFalse(result["accuracy_scoring_started"])
        self.assertTrue(result["pmx_scientific_priority_retained"])


if __name__ == "__main__":
    unittest.main()
