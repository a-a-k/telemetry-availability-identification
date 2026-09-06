from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from telemetry_availability.pmx_performability import (
    _eligible_spring_span,
    create_error_control,
    file_sha256,
    load_pmx_performability_config,
    summarize_pcm_results,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m9f_pmx_performability_audit.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m9f-pmx-performability-audit.yml"


class PMXPerformabilityTests(unittest.TestCase):
    def test_frozen_contract_keeps_priority_limits_and_no_accuracy_role(self) -> None:
        config = load_pmx_performability_config(CONFIG)
        self.assertEqual(config.job_timeout_minutes, 360)
        self.assertEqual(config.internal_timeout_seconds, 900)
        self.assertEqual(config.raw["runtime"]["headless_job_safety_minutes"], 60)
        self.assertEqual(config.raw["runtime"]["progress_interval_seconds"], 30)
        self.assertEqual(
            config.raw["runtime_amendment"]["superseded_run_id"], 34040388551
        )
        self.assertFalse(
            config.raw["runtime_amendment"][
                "generated_pcm_inspected_before_amendment"
            ]
        )
        self.assertEqual(config.repeat_count, 2)
        self.assertEqual(config.raw["accuracy_scoring"], "forbidden")
        self.assertEqual(config.raw["new_live_collection"], "forbidden")
        self.assertTrue(
            config.raw["scientific_priority"]["persists_if_application_cost_is_high"]
        )
        self.assertFalse(
            config.raw["scientific_priority"][
                "retriever_result_generalizes_to_ecosystem"
            ]
        )

        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("timeout-minutes: 360"), 3)
        self.assertIn('PMX_INTERNAL_TIMEOUT_SECONDS: "900"', workflow)
        self.assertIn('PMX_PROGRESS_INTERVAL_SECONDS: "30"', workflow)
        self.assertIn("event=heartbeat", workflow)
        self.assertIn(
            "-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector",
            workflow,
        )
        self.assertIn("published_original single_error_control", workflow)
        self.assertNotIn("test-requests.csv", workflow)
        self.assertNotIn("scores.csv", workflow)
        self.assertNotIn("brier", workflow.lower())

    def test_frozen_repository_locks_match(self) -> None:
        config = load_pmx_performability_config(CONFIG)
        for record in config.raw["repository_locks"]:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(path.stat().st_size, record["bytes"], record["path"])
            self.assertEqual(file_sha256(path), record["sha256"], record["path"])
        manual = config.raw["manual_actions_log"]
        content = (ROOT / manual["path"]).read_bytes()
        prefix = content[: manual["initial_size_in_bytes"]]
        import hashlib

        self.assertEqual(hashlib.sha256(prefix).hexdigest(), manual["initial_sha256"])

    def test_spring_span_filter_is_specific(self) -> None:
        eligible = {
            "operationName": "VisitResource.read",
            "tags": [
                {
                    "key": "otel.library.name",
                    "type": "string",
                    "value": "io.opentelemetry.spring-webmvc-5.3",
                }
            ],
        }
        self.assertTrue(_eligible_spring_span(eligible))
        self.assertFalse(
            _eligible_spring_span(
                {**eligible, "operationName": "BasicErrorController.error"}
            )
        )
        self.assertFalse(
            _eligible_spring_span(
                {
                    "operationName": "VisitResource.read",
                    "tags": [{"key": "otel.scope.name", "value": "custom"}],
                }
            )
        )

    def test_error_control_changes_exactly_the_predeclared_span(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            demo = root / "demo"
            (demo / "traces").mkdir(parents=True)
            config_payload = json.loads(CONFIG.read_text(encoding="utf-8"))
            control = next(
                item
                for item in config_payload["conditions"]
                if item["id"] == "single_error_control"
            )
            spans = []
            for index in range(10):
                spans.append(
                    {
                        "spanID": control["span_id"] if index == 0 else f"span-{index}",
                        "operationName": control["operation"],
                        "tags": [
                            {
                                "key": "otel.library.name",
                                "type": "string",
                                "value": "spring-webmvc",
                            }
                        ],
                    }
                )
            payload = {"data": [{"traceID": control["trace_id"], "spans": spans}]}
            source_trace = demo / control["source_trace_path"]
            source_trace.write_text(json.dumps(payload), encoding="utf-8")
            options = demo / "Options.txt"
            options.write_text(
                f"-r reader -i {control['source_trace_path']} -w writer", encoding="utf-8"
            )
            for record in config_payload["demonstration"]["files"]:
                if record["path"] == control["source_trace_path"]:
                    record["bytes"] = source_trace.stat().st_size
                    record["sha256"] = file_sha256(source_trace)
                elif record["path"] == "Options.txt":
                    record["bytes"] = options.stat().st_size
                    record["sha256"] = file_sha256(options)
            temporary_config = root / "config.json"
            temporary_config.write_text(json.dumps(config_payload), encoding="utf-8")
            output_trace = root / "control" / "traces" / control["trace_path"].split("/")[-1]
            output_options = root / "control" / "Options.txt"
            manifest_path = root / "control" / "manifest.json"

            manifest = create_error_control(
                temporary_config,
                demo,
                output_trace,
                output_options,
                manifest_path,
            )
            generated = json.loads(output_trace.read_text(encoding="utf-8"))
            generated_spans = generated["data"][0]["spans"]
            error_spans = [
                span
                for span in generated_spans
                if any(tag.get("key") == "error" for tag in span["tags"])
            ]
            self.assertEqual(len(error_spans), 1)
            self.assertEqual(error_spans[0]["spanID"], control["span_id"])
            self.assertEqual(manifest["expected_failure_probability"], 0.1)
            self.assertIn(control["trace_path"], output_options.read_text(encoding="utf-8"))

    def test_pcm_summary_separates_operation_and_link_probabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "model.repository").write_text(
                """<?xml version="1.0"?>
<Repository>
  <ResourceDemandingSEFF entityName="VisitResource.read">
    <InternalAction>
      <InternalFailureOccurrenceDescription failureProbability="0.1">
        <SoftwareInducedFailureType />
      </InternalFailureOccurrenceDescription>
    </InternalAction>
  </ResourceDemandingSEFF>
</Repository>
""",
                encoding="utf-8",
            )
            (root / "model.resourceenvironment").write_text(
                """<?xml version="1.0"?>
<ResourceEnvironment>
  <LinkingResource failureProbability="0.0" MTTF="10" MTTR="1" />
</ResourceEnvironment>
""",
                encoding="utf-8",
            )
            (root / "model.system").write_text("<System />", encoding="utf-8")
            (root / "model.allocation").write_text(
                "<Allocation><AllocationContext /></Allocation>", encoding="utf-8"
            )
            (root / "model.usagemodel").write_text(
                "<UsageModel><EntryLevelSystemCall /></UsageModel>", encoding="utf-8"
            )

            summary = summarize_pcm_results(root)
            self.assertFalse(summary["missing_core_suffixes"])
            self.assertFalse(summary["parse_errors"])
            self.assertEqual(summary["nonzero_repository_failure_probabilities"], [0.1])
            self.assertEqual(summary["nonzero_link_failure_probabilities"], [])
            self.assertGreater(summary["token_counts"]["internal_failure_occurrence"], 0)
            self.assertGreater(summary["token_counts"]["mttf"], 0)


if __name__ == "__main__":
    unittest.main()
