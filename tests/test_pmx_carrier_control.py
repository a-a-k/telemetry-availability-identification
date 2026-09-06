from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.pmx_carrier_control import (
    _find_target_spans,
    _nonfailure_projection,
    decide,
    load_pmx_carrier_control_config,
    validate_repository,
)
from telemetry_availability.pmx_performability import file_sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9j_pmx_carrier_control.json"
PROTOCOL = ROOT / "docs" / "M9J_PMX_CARRIER_CONTROL_PROTOCOL.md"
WORKFLOW = ROOT / ".github" / "workflows" / "m9j-pmx-carrier-control.yml"


class PMXCarrierControlTests(unittest.TestCase):
    def test_frozen_pair_is_bounded_and_remote_only(self) -> None:
        config = load_pmx_carrier_control_config(CONFIG)
        self.assertEqual(config.command, "main:main -of Options.txt")
        self.assertEqual(config.repeats, 2)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.raw["workflow"]["dynamic_pmx_runs"], 4)
        self.assertEqual(
            [control["id"] for control in config.raw["controls"]],
            ["carrier_error_false", "carrier_error_true"],
        )
        self.assertEqual(
            config.raw["decision"]["next_if_both_pass"],
            "m9k_single_operation_overestimation_localization",
        )
        self.assertEqual(
            config.raw["decision"]["next_otherwise"],
            "m9k_single_operation_overestimation_localization",
        )

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertEqual(workflow.count("runs-on: ubuntu-latest"), 3)
        self.assertIn("for condition in carrier_error_false carrier_error_true", workflow)
        self.assertIn("for repeat in 1 2", workflow)
        self.assertNotIn("scores.csv", workflow)
        self.assertNotIn("test-requests.csv", workflow)

    def test_protocol_caps_external_tool_work_and_preserves_claim_boundary(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        self.assertIn("bounded end of the present external-tool diagnostic", protocol)
        self.assertIn("Every branch proceeds next to M9K", protocol)
        self.assertIn("predeclared checkout operation", protocol)
        self.assertIn("not yet demonstrate either better", protocol)
        self.assertIn("predictive accuracy or lower end-to-end cost", protocol)
        self.assertIn("All three jobs use `timeout-minutes: 360`", protocol)

    def test_repository_locks_validate(self) -> None:
        result = validate_repository(CONFIG)
        self.assertEqual(result["status"], "m9j_repository_contract_valid")
        self.assertEqual(len(result["repository_locks"]), 5)
        self.assertEqual(result["dynamic_pmx_runs"], 4)

    def test_source_derived_target_and_carrier_mutation(self) -> None:
        target = load_pmx_carrier_control_config(CONFIG).raw["target"]
        child = {
            "spanID": target["spring_child_span_id"],
            "processID": target["process_id"],
            "operationName": target["child_original_operation"],
            "references": [
                {
                    "refType": "CHILD_OF",
                    "spanID": target["surviving_carrier_span_id"],
                }
            ],
            "tags": [
                {
                    "key": "otel.library.name",
                    "value": "io.opentelemetry.spring-webmvc-6.0",
                }
            ],
        }
        carrier = {
            "spanID": target["surviving_carrier_span_id"],
            "processID": target["process_id"],
            "operationName": target["carrier_original_operation"],
            "references": [],
            "tags": [
                {
                    "key": "otel.library.name",
                    "value": "io.opentelemetry.tomcat-10.0",
                }
            ],
        }
        payload = {
            "data": [
                {
                    "traceID": target["trace_id"],
                    "spans": [carrier, child],
                }
            ]
        }
        observed_child, observed_carrier = _find_target_spans(payload, target)
        self.assertIs(observed_child, child)
        self.assertIs(observed_carrier, carrier)

        carrier["tags"].append({"key": "error", "type": "bool", "value": "true"})
        _, mutated_carrier = _find_target_spans(
            payload, {**target, "original_error_tags": 1}
        )
        self.assertEqual(mutated_carrier["tags"][-1]["value"], "true")

    def test_nonfailure_projection_ignores_only_declared_failure_structure(self) -> None:
        base = {
            "core_suffixes": [".repository", ".system"],
            "parse_errors": [],
            "entity_names": ["VisitResource.read"],
            "token_counts": {
                "resource_demanding_seff": 5,
                "external_call_action": 2,
                "entry_level_system_call": 1,
                "allocation_context": 1,
                "linking_resource": 1,
                "mttf": 1,
                "mttr": 1,
                "internal_failure_occurrence": 0,
                "software_induced_failure_type": 0,
            },
            "tag_counts": {"repository": 1, "failureProbability": 5},
        }
        positive = json.loads(json.dumps(base))
        positive["entity_names"].append("generated failure")
        positive["token_counts"]["internal_failure_occurrence"] = 1
        positive["token_counts"]["software_induced_failure_type"] = 1
        positive["tag_counts"]["failureProbability"] = 6
        positive["tag_counts"]["internalFailureOccurrenceDescriptions"] = 1
        self.assertEqual(
            _nonfailure_projection(base), _nonfailure_projection(positive)
        )

    def test_decision_routes_a_reproduced_pair_to_internal_localization(self) -> None:
        config_hash = file_sha256(CONFIG)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = root / "contract.json"
            contract.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "status": "source_implied_carrier_controls_generated",
                        "source_checks_passed": 5,
                        "controls_generated": 2,
                        "dynamic_pmx_invocations": 0,
                    }
                ),
                encoding="utf-8",
            )
            probe = root / "probe.json"
            probe.write_text(
                json.dumps(
                    {
                        "config_sha256": config_hash,
                        "control_contract_sha256": file_sha256(contract),
                        "run_count": 4,
                        "all_runs_technically_valid": True,
                        "dynamic_pmx_invocations": 4,
                        "condition_passes": {
                            "carrier_error_false": True,
                            "carrier_error_true": True,
                        },
                        "repeat_consistency": {
                            "carrier_error_false": True,
                            "carrier_error_true": True,
                        },
                        "nonfailure_structure_consistent": True,
                    }
                ),
                encoding="utf-8",
            )
            result = decide(CONFIG, contract, probe, root / "out")

        self.assertEqual(
            result["status"],
            "pmx_source_implied_carrier_failure_contract_reproduced",
        )
        self.assertTrue(result["source_implied_failure_mechanism_reproduced"])
        self.assertEqual(
            result["next_milestone"],
            "m9k_single_operation_overestimation_localization",
        )
        self.assertFalse(result["accuracy_scoring_started"])
        self.assertTrue(result["pmx_scientific_priority_retained"])


if __name__ == "__main__":
    unittest.main()
