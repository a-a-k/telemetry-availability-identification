from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.live_pilot import (
    RuntimePilotError,
    aggregate_runtime_pilots,
    pin_compose_document,
    run_runtime_pilot,
)
from telemetry_availability.live_pilot_config import (
    load_runtime_pilot_config,
    select_runtime_pilot_profile,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m7_runtime_pilot.yaml"


class RuntimePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_runtime_pilot_config(CONFIG_PATH)

    def test_contract_is_explicitly_pilot_only(self) -> None:
        self.assertTrue(self.config.pilot_only)
        self.assertEqual(len(self.config.profiles), 2)
        self.assertEqual(self.config.requests_per_operation_per_period, 20)
        self.assertEqual(
            {profile.id for profile in self.config.profiles},
            {"deathstarbench_social_network", "opentelemetry_demo"},
        )

    def test_pin_compose_replaces_tags_and_removes_build(self) -> None:
        original = select_runtime_pilot_profile(
            self.config,
            "deathstarbench_social_network",
        )
        profile = replace(
            original,
            images={
                "redis:latest": "sha256:" + "a" * 64,
                "mongo:4.4.6": "sha256:" + "b" * 64,
            },
        )
        document = {
            "services": {
                "cache": {"image": "redis", "build": {"context": "."}},
                "store": {"image": "mongo:4.4.6"},
            }
        }
        pinned, audit = pin_compose_document(document, profile)
        self.assertEqual(audit["service_count"], 2)
        self.assertTrue(audit["all_services_locked"])
        self.assertNotIn("build", pinned["services"]["cache"])
        self.assertEqual(
            pinned["services"]["cache"]["image"],
            "redis:latest@sha256:" + "a" * 64,
        )

    def test_pin_compose_rejects_unlocked_or_unused_images(self) -> None:
        original = select_runtime_pilot_profile(
            self.config,
            "opentelemetry_demo",
        )
        profile = replace(
            original,
            images={"known:1": "sha256:" + "a" * 64},
        )
        with self.assertRaisesRegex(RuntimePilotError, "no digest lock"):
            pin_compose_document(
                {"services": {"unknown": {"image": "unknown:1"}}},
                profile,
            )
        with self.assertRaisesRegex(RuntimePilotError, "unused"):
            pin_compose_document(
                {"services": {"known": {"image": "known:1"}, "other": {"image": "known:1"}}},
                replace(
                    profile,
                    images={
                        "known:1": "sha256:" + "a" * 64,
                        "unused:1": "sha256:" + "b" * 64,
                    },
                ),
            )

    def test_runtime_workload_is_forbidden_locally(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimePilotError, "only in GitHub Actions"):
                run_runtime_pilot(
                    self.config,
                    "opentelemetry_demo",
                    ROOT,
                    ROOT / "absent-compose.json",
                    ROOT / "absent-audit.json",
                    ROOT / ".smoke" / "forbidden-pilot",
                )

    def test_aggregate_preserves_pilot_label_and_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for profile in self.config.profiles:
                shard = root / "shards" / profile.id
                shard.mkdir(parents=True)
                manifest = {
                    "profile": profile.id,
                    "pilot_only": True,
                    "usable_for_main_design": True,
                    "counts": {
                        "expected_requests": 120,
                        "observed_requests": 120,
                        "successful_requests": 120,
                        "failed_requests": 0,
                        "exported_traces": 10,
                        "running_containers": 5,
                        "locked_services": 5,
                    },
                    "success_fraction": 1.0,
                    "quality": {
                        "checkout_commit_mismatches": 0,
                        "request_count_mismatches": 0,
                        "below_success_threshold": 0,
                        "insufficient_exported_traces": 0,
                        "telemetry_collection_errors": 0,
                        "unlocked_rendered_services": 0,
                        "unlocked_running_images": 0,
                        "missing_running_containers": 0,
                    },
                }
                (shard / "pilot_manifest.json").write_text(
                    json.dumps(manifest),
                    encoding="utf-8",
                )
            output = root / "aggregate"
            aggregate = aggregate_runtime_pilots(
                self.config,
                root / "shards",
                output,
            )
            self.assertTrue(aggregate["pilot_only"])
            self.assertEqual(aggregate["source_profiles"], 2)
            self.assertEqual(set(aggregate["quality"].values()), {0})


if __name__ == "__main__":
    unittest.main()
