import unittest

from telemetry_availability.pmx_usage_contract_audit import aggregated_entry_counts, reconstructed_inventory


class UsageOracleReviewTests(unittest.TestCase):
    def test_source_aggregation_is_not_raw_count_or_bankers_rounding(self):
        self.assertEqual(aggregated_entry_counts({"a": 10, "b": 10}), {"a": 1, "b": 1})
        self.assertEqual(aggregated_entry_counts({"a": 2, "b": 5}), {"a": 1, "b": 3})
        self.assertEqual(aggregated_entry_counts({"a": 3, "b": 10}), {"a": 1, "b": 3})

    def test_inventory_compares_trace_span_parent_and_time(self):
        trace, operation = "a" * 32, "operation_" + "b" * 24
        log = ("osgi> " + "#" * 42 + "\n" + operation + " / 01 / null\n" + "#" * 42 + "\n"
               + f"ExecutionTrace [minTin=1000000, maxTout=2000000, set=[{trace}{operation} <NOSESSIONID>], invalidExecutions=[]]\n")
        envelope = {"data": [{"traceID": trace, "spans": [{"spanID": "01", "operationName": operation,
                     "startTime": 1000, "duration": 1000, "references": []}]}]}
        good = reconstructed_inventory(log, envelope)
        self.assertTrue(good["exact_trace_span_operation_parent_inventory"])
        self.assertTrue(good["reconstructed_nanosecond_bounds_match_input_microseconds"])
        self.assertFalse(reconstructed_inventory(log.replace(" / 01 /", " / 02 /"), envelope)["exact_trace_span_operation_parent_inventory"])
        self.assertFalse(reconstructed_inventory(log.replace("maxTout=2000000", "maxTout=3000000"), envelope)["reconstructed_nanosecond_bounds_match_input_microseconds"])
        self.assertFalse(reconstructed_inventory(log + log, envelope)["each_trace_reconstructed_once"])
        self.assertFalse(reconstructed_inventory("", envelope)["exact_trace_span_operation_parent_inventory"])


if __name__ == "__main__":
    unittest.main()
