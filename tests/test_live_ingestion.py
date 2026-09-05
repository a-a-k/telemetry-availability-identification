from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from telemetry_availability.live_config import load_live_harness_config
from telemetry_availability.live_harness import (
    _bundle_fingerprint,
    aggregate_live_harness,
    select_live_profile,
)
from telemetry_availability.live_ingestion import (
    LiveContractError,
    _validate_span_graph,
    ingest_live_bundle,
    write_ingested_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m6_live_harness.yaml"


class LiveIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_live_harness_config(CONFIG_PATH)

    def _bundle(self, benchmark_id: str):
        profile = select_live_profile(self.config, benchmark_id)
        return profile, ingest_live_bundle(
            profile.fixture_bundle,
            self.config.contract,
            profile,
        )

    def test_config_freezes_two_adapters_and_workload_markers(self) -> None:
        self.assertEqual(
            {profile.trace_format for profile in self.config.benchmarks},
            {"jaeger_json_v1", "otlp_json_v1"},
        )
        for profile in self.config.benchmarks:
            self.assertEqual(len(profile.operations), 3)
            self.assertTrue(all(operation.markers for operation in profile.operations))
            self.assertTrue(
                all(
                    operation.workload_path in profile.required_paths
                    for operation in profile.operations
                )
            )

    def test_both_fixtures_preserve_the_external_request_census(self) -> None:
        for profile in self.config.benchmarks:
            with self.subTest(profile=profile.id):
                bundle = ingest_live_bundle(
                    profile.fixture_bundle,
                    self.config.contract,
                    profile,
                )
                counts = bundle.audit["counts"]
                self.assertEqual(counts["external_requests"], 8)
                self.assertEqual(counts["traced_external_requests"], 6)
                self.assertEqual(counts["untraced_external_failures"], 2)
                self.assertEqual(counts["spans"], 12)
                self.assertTrue(all(value == 0 for value in bundle.audit["quality"].values()))

    def test_reingestion_is_deterministic(self) -> None:
        for profile in self.config.benchmarks:
            with self.subTest(profile=profile.id):
                first = ingest_live_bundle(
                    profile.fixture_bundle,
                    self.config.contract,
                    profile,
                )
                second = ingest_live_bundle(
                    profile.fixture_bundle,
                    self.config.contract,
                    profile,
                )
                self.assertEqual(_bundle_fingerprint(first), _bundle_fingerprint(second))

    def test_normalized_tables_include_untraced_failures(self) -> None:
        _, bundle = self._bundle("opentelemetry_demo")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            manifest = write_ingested_bundle(bundle, output)
            normalized = (output / "requests.csv").read_text(encoding="utf-8")
            self.assertIn("otel-c-004,,", normalized)
            self.assertEqual(manifest["row_counts"]["requests"], 8)
            self.assertEqual(set(manifest["quality"].values()), {0})

    def test_digest_tampering_is_rejected(self) -> None:
        profile = select_live_profile(self.config, "deathstarbench_social_network")
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "bundle"
            shutil.copytree(profile.fixture_bundle, copied)
            with (copied / "requests.csv").open("a", encoding="utf-8") as destination:
                destination.write("\n")
            with self.assertRaisesRegex(LiveContractError, "digest mismatch"):
                ingest_live_bundle(copied, self.config.contract, profile)

    def test_overlapping_periods_are_rejected(self) -> None:
        profile = select_live_profile(self.config, "opentelemetry_demo")
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "bundle"
            shutil.copytree(profile.fixture_bundle, copied)
            path = copied / "manifest.yaml"
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            manifest["periods"]["test"]["start"] = "2026-08-01T00:05:00Z"
            path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            with self.assertRaisesRegex(LiveContractError, "periods overlap"):
                ingest_live_bundle(copied, self.config.contract, profile)

    def test_span_ids_may_repeat_across_distinct_traces(self) -> None:
        rows = [
            {
                "trace_id": trace,
                "span_id": "same-span-id",
                "parent_span_id": "",
                "service": "service",
                "instance_id": "instance",
            }
            for trace in ("trace-a", "trace-b")
        ]
        _validate_span_graph(rows)

    def test_duplicate_trace_span_identity_is_rejected(self) -> None:
        row = {
            "trace_id": "trace-a",
            "span_id": "span-a",
            "parent_span_id": "",
            "service": "service",
            "instance_id": "instance",
        }
        with self.assertRaisesRegex(LiveContractError, "repeat trace/span"):
            _validate_span_graph([row, dict(row)])

    def test_aggregate_requires_and_summarizes_both_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for profile in self.config.benchmarks:
                bundle = ingest_live_bundle(
                    profile.fixture_bundle,
                    self.config.contract,
                    profile,
                )
                report = {
                    "benchmark_id": profile.id,
                    "repository": profile.repository,
                    "pinned_commit": profile.commit,
                    "trace_format": profile.trace_format,
                    "fixture_only": True,
                    "required_paths": list(profile.required_paths),
                    "required_services": list(profile.required_services),
                    "operation_evidence": list(profile.operation_ids),
                    "fixture_audit": bundle.audit,
                    "reingestion": {"deterministic": True},
                    "quality": {
                        "upstream_commit_mismatches": 0,
                        "upstream_repository_mismatches": 0,
                        "missing_required_paths": 0,
                        "missing_required_services": 0,
                        "missing_operation_markers": 0,
                        "nondeterministic_reingestions": 0,
                        "contract_quality_failures": 0,
                        "unpreserved_untraced_failures": 0,
                    },
                }
                shard = root / "shards" / profile.id
                shard.mkdir(parents=True)
                (shard / "profile_report.json").write_text(
                    json.dumps(report),
                    encoding="utf-8",
                )
            output = root / "aggregate"
            manifest = aggregate_live_harness(self.config, root / "shards", output)
            self.assertEqual(manifest["source_profiles"], 2)
            self.assertEqual(manifest["row_counts"]["summary"], 2)
            self.assertTrue(manifest["fixture_only"])


if __name__ == "__main__":
    unittest.main()
