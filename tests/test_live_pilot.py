from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.live_pilot import (
    RuntimePilotError,
    _collect_telemetry,
    _deathstar_request,
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
        self.assertEqual(self.config.post_start_stabilization_seconds, 30)
        self.assertEqual(
            {profile.id for profile in self.config.profiles},
            {"deathstarbench_social_network", "opentelemetry_demo"},
        )
        otel = select_runtime_pilot_profile(self.config, "opentelemetry_demo")
        self.assertEqual(otel.disabled_services, ("load-generator",))

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
            disabled_services=(),
            images={"known:1": "sha256:" + "a" * 64},
        )
        with self.assertRaisesRegex(RuntimePilotError, "no digest lock"):
            pin_compose_document(
                {"services": {"unknown": {"image": "unknown:1"}}},
                profile,
            )
        with self.assertRaisesRegex(RuntimePilotError, "unused"):
            pin_compose_document(
                {
                    "services": {
                        "known": {"image": "known:1"},
                        "other": {"image": "known:1"},
                    }
                },
                replace(
                    profile,
                    disabled_services=(),
                    images={
                        "known:1": "sha256:" + "a" * 64,
                        "unused:1": "sha256:" + "b" * 64,
                    },
                ),
            )

    def test_pin_compose_removes_declared_external_generator_and_dependencies(
        self,
    ) -> None:
        original = select_runtime_pilot_profile(self.config, "opentelemetry_demo")
        profile = replace(
            original,
            disabled_services=("driver",),
            images={"application:1": "sha256:" + "a" * 64},
        )
        document = {
            "services": {
                "application": {
                    "image": "application:1",
                    "depends_on": {"driver": {"condition": "service_started"}},
                },
                "driver": {"image": "unlocked-driver:1"},
            }
        }
        pinned, audit = pin_compose_document(document, profile)
        self.assertNotIn("driver", pinned["services"])
        self.assertNotIn("driver", pinned["services"]["application"]["depends_on"])
        self.assertEqual(audit["rendered_service_count"], 2)
        self.assertEqual(audit["service_count"], 1)
        self.assertEqual(audit["disabled_services"], ["driver"])

    def test_pin_compose_mounts_lossless_otel_study_sink(self) -> None:
        original = select_runtime_pilot_profile(self.config, "opentelemetry_demo")
        profile = replace(
            original,
            disabled_services=(),
            images={"collector:1": "sha256:" + "a" * 64},
        )
        document = {
            "services": {
                "otel-collector": {"image": "collector:1", "volumes": []},
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            pinned, audit = pin_compose_document(
                document,
                profile,
                telemetry_output_directory=temporary,
            )
        mount = pinned["services"]["otel-collector"]["volumes"][-1]
        self.assertEqual(mount["target"], "/study-output")
        self.assertFalse(mount["read_only"])
        self.assertEqual(
            audit["study_telemetry_sink"]["kind"],
            "mounted_otlp_json_lines",
        )

    def test_collect_telemetry_prefers_mounted_otel_json_lines(self) -> None:
        profile = select_runtime_pilot_profile(self.config, "opentelemetry_demo")
        trace_id = "0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "raw-telemetry.log").write_text(
                json.dumps({"resourceSpans": [{"traceId": trace_id}]}) + "\n",
                encoding="utf-8",
            )
            count, error = _collect_telemetry(
                profile,
                datetime.now(timezone.utc),
                output,
            )
        self.assertEqual(count, 1)
        self.assertEqual(error, "")

    def test_deathstar_home_read_targets_initialized_follower(self) -> None:
        profile = select_runtime_pilot_profile(
            self.config, "deathstarbench_social_network"
        )
        with patch(
            "telemetry_availability.live_pilot._http_request",
            return_value=(200, b"[]", ""),
        ) as request:
            _deathstar_request(profile, "read_home_timeline", 0)
        self.assertIn("user_id=1", request.call_args.args[0])

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
