import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from telemetry_availability.pmx_observed_operations import (
    AdapterError, NativeSpan, convert, from_jaeger, from_otlp,
    project_trace, read_native, select_learner_ids,
)


def native(span_id="1", parent="", server=True, **kwargs):
    values = dict(trace_id="a" * 32, span_id=span_id, parent_id=parent,
                  service="service", operation="call", server=server,
                  start_us=1800000000000000, duration_us=1000,
                  start_remainder_ns=0, duration_remainder_ns=0,
                  attributes={}, resource_attributes={"service.instance.id": "instance-a"},
                  error_tag=False, error_status=False, native_kind="2", native_links=[])
    return NativeSpan(**(values | kwargs))


class ObservedOperationTests(unittest.TestCase):
    def test_otlp_integer_time_quantization_and_error_sources(self):
        resource = {"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "checkout"}}]}}
        source = {"traceId": "A" * 32, "spanId": "B" * 16, "name": "rpc", "kind": 2,
                  "startTimeUnixNano": "1800000000000000123", "endTimeUnixNano": "1800000000005000999",
                  "status": {"code": 2}, "attributes": [{"key": "error", "value": {"boolValue": False}}]}
        span = from_otlp(resource, {"scope": {"name": "native-scope"}}, source)
        self.assertEqual((span.start_us, span.duration_us), (1800000000000000, 5000))
        self.assertEqual((span.start_remainder_ns, span.duration_remainder_ns), (123, 876))
        self.assertFalse(span.error_tag)
        self.assertTrue(span.error_status)
        self.assertEqual(span.attributes["adapter.original.scope"], {"name": "native-scope"})
        for update in ({"endTimeUnixNano": source["startTimeUnixNano"]},
                       {"startTimeUnixNano": 1800000000000000123.0}, {"endTimeUnixNano": "broken"}):
            with self.assertRaises(AdapterError):
                from_otlp(resource, {}, source | update)

    def test_jaeger_units_tags_and_ambiguous_parent(self):
        trace = {"traceID": "a" * 32, "processes": {"p1": {"serviceName": "A", "tags": []}}}
        span = {"spanID": "1", "processID": "p1", "operationName": "query", "startTime": 10000,
                "duration": 4321, "tags": [{"key": "span.kind", "value": "server"},
                                            {"key": "error", "value": "TRUE"}]}
        result = from_jaeger(trace, span)
        self.assertEqual((result.start_us, result.duration_us), (10000, 4321))
        self.assertTrue(result.error)
        refs = [{"refType": "CHILD_OF", "spanID": "2"}, {"refType": "CHILD_OF", "spanID": "3"}]
        with self.assertRaisesRegex(AdapterError, "ambiguous_parent"):
            from_jaeger(trace, span | {"references": refs})

    def test_contract_observed_ancestry_split_forest_and_retain_nonserver_error(self):
        spans = [native(), native("2", "1", False, error_tag=True), native("3", "2"), native("4", "ff")]
        traces, mapping, audit = project_trace(spans, "worker")
        self.assertEqual(len(traces), 2)
        self.assertEqual({m["span_id"] for m in mapping}, {"1", "3", "4"})
        child = next(m for m in mapping if m["span_id"] == "3")
        self.assertEqual(child["pmx_parent_span_id"], "1")
        self.assertEqual(child["contracted_intermediate_spans"], 1)
        self.assertEqual(audit["missing_parent_roots"], 1)
        self.assertEqual(audit["nonserver_errors"], 1)
        self.assertFalse(audit["complete_single_observed_tree"])
        self.assertFalse(any(m["error_tag"] for m in mapping))

    def test_qualified_names_and_instances_preserve_collisions(self):
        spans = [native(operation="Handler"), native("2", "1", operation="Handler", service="other"),
                 native("3", "1", operation="Handler", resource_attributes={"service.instance.id": "instance-b"})]
        result = convert({"a" * 32: spans}, {"a" * 32}, "physical-worker")
        self.assertEqual(len(result["operation_oracle"]), 3)
        self.assertEqual(len({m["pmx_component"] for m in result["mapping"]}), 3)
        self.assertTrue(all("Handler" not in m["pmx_operation"] for m in result["mapping"]))
        self.assertEqual(len(result["edge_oracle"]), 2)

    def test_conflicts_and_cycles_reject_whole_trace(self):
        for spans in ([native(), native(error_tag=True)], [native(parent="2"), native("2", "1")]):
            result = convert({"a" * 32: spans}, {"a" * 32}, "worker")
            self.assertEqual(result["census"][0]["status"], "invalid_native_trace")
            self.assertEqual(result["envelope"]["data"], [])
        _, mapping, audit = project_trace([native(), native()], "worker")
        self.assertEqual(len(mapping), 1)
        self.assertEqual(audit["identical_duplicates"], 1)

    def test_operation_error_denominators_and_absent_coverage(self):
        grouped = {f"{i:032x}": [replace(native(), trace_id=f"{i:032x}", error_tag=i == 0)] for i in range(10)}
        selected = set(grouped) | {"f" * 32}
        result = convert(grouped, selected, "worker")
        self.assertEqual(result["operation_oracle"][0]["invocations"], 10)
        self.assertEqual(result["operation_oracle"][0]["error_probability"], .1)
        self.assertEqual(result["summary"]["status_counts"], {"adapted": 10, "absent_from_raw": 1})
        self.assertEqual(result["summary"]["external_request_forecasts"], 0)

    def test_no_server_no_error_imputation_and_unresolved_instance(self):
        _, mapping, audit = project_trace([native(server=False, error_tag=True)], "worker")
        self.assertEqual(mapping, [])
        self.assertEqual(audit["nonserver_errors"], 1)
        _, mapping, audit = project_trace([native(resource_attributes={})], "worker")
        self.assertEqual(audit["unresolved_instance_spans"], 1)
        self.assertEqual(mapping[0]["instance_key"], "unresolved")

    def test_learner_membership_never_uses_success_and_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace-join.csv"
            path.write_text("period,trace_id,request_success\nbaseline,aa,do-not-parse\ncalibration,bb,do-not-parse\ntest,cc,do-not-parse\n")
            self.assertEqual(select_learner_ids(path), {"aa", "bb"})
            with path.open("a") as output:
                output.write("test,aa,do-not-parse\n")
            with self.assertRaisesRegex(AdapterError, "learner_test_overlap"):
                select_learner_ids(path)

    def test_native_selection_precedes_invalid_test_span_and_keeps_invalid_learner(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw.json"
            path.write_text(json.dumps({"data": [
                {"traceID": "aa", "spans": [{"spanID": "1"}], "processes": {}},
                {"traceID": "bb", "spans": [None]},
            ]}))
            grouped, audit = read_native(path, {"aa"}, "jaeger_json_v1")
            self.assertIn("aa", audit["invalid_traces"])
            self.assertNotIn("bb", audit["invalid_traces"])
            self.assertEqual(convert(grouped, {"aa"}, "worker", audit["invalid_traces"])["census"][0]["status"], "invalid_native_trace")


if __name__ == "__main__":
    unittest.main()
