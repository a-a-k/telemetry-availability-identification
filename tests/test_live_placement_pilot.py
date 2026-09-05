from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.live_placement_config import (
    load_placement_pilot_config,
    select_placement_pilot_profile,
)
from telemetry_availability.live_placement_pilot import (
    PlacementPilotError,
    _event_targets,
    aggregate_placement_pilots,
    prepare_placement_compose,
    run_placement_pilot,
    validate_operation_response,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m7b_placement_pilot.yaml"


class PlacementPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_placement_pilot_config(CONFIG_PATH)

    def test_contract_is_pilot_only_and_freezes_two_placements(self) -> None:
        self.assertTrue(self.config.pilot_only)
        self.assertEqual(set(self.config.placements), {"colocated", "split"})
        self.assertEqual(
            self.config.placements["colocated"],
            {"a": "domain_a", "b": "domain_a"},
        )
        self.assertEqual(
            self.config.placements["split"],
            {"a": "domain_a", "b": "domain_b"},
        )
        self.assertEqual(self.config.requests_per_fault_period, 160)
        self.assertEqual(len(self.config.events), 4)

    def _prepare(self, profile_id: str, placement: str) -> tuple[dict, dict, str]:
        profile = select_placement_pilot_profile(self.config, profile_id)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = {
                "services": {
                    profile.target_service: {
                        "image": "application:1@sha256:" + "a" * 64,
                        "container_name": profile.target_service,
                        "hostname": profile.target_service,
                        "ports": [{"target": profile.target_port}],
                        "environment": {"OTEL_RESOURCE_ATTRIBUTES": "existing=yes"},
                        "networks": {"default": None},
                    },
                    "caller": {
                        "image": "caller:1@sha256:" + "b" * 64,
                        "depends_on": {
                            profile.target_service: {"condition": "service_started"}
                        },
                    },
                }
            }
            base_audit = {
                "schema_version": 1,
                "profile": profile_id,
                "rendered_service_count": 2,
                "service_count": 2,
                "all_services_locked": True,
                "images": [
                    {
                        "service": profile.target_service,
                        "rendered_image": "application:1",
                        "locked_image": "application:1@sha256:" + "a" * 64,
                        "manifest_digest": "sha256:" + "a" * 64,
                    },
                    {
                        "service": "caller",
                        "rendered_image": "caller:1",
                        "locked_image": "caller:1@sha256:" + "b" * 64,
                        "manifest_digest": "sha256:" + "b" * 64,
                    },
                ],
            }
            (root / "input.json").write_text(json.dumps(document), encoding="utf-8")
            (root / "base-audit.json").write_text(
                json.dumps(base_audit), encoding="utf-8"
            )
            audit = prepare_placement_compose(
                self.config,
                profile_id,
                placement,
                root / "input.json",
                root / "base-audit.json",
                root / "compose.json",
                root / "audit.json",
                root / "haproxy.cfg",
            )
            revised = json.loads((root / "compose.json").read_text(encoding="utf-8"))
            haproxy = (root / "haproxy.cfg").read_text(encoding="utf-8")
        return revised, audit, haproxy

    def test_prepare_split_h2_proxy_creates_two_real_replicas(self) -> None:
        document, audit, haproxy = self._prepare("opentelemetry_demo", "split")
        services = document["services"]
        self.assertIn("product-catalog-replica-a", services)
        self.assertIn("product-catalog-replica-b", services)
        self.assertNotIn("container_name", services["product-catalog-replica-a"])
        self.assertNotIn("ports", services["product-catalog-replica-b"])
        self.assertEqual(
            services["product-catalog-replica-a"]["labels"]["study.domain"],
            "domain_a",
        )
        self.assertEqual(
            services["product-catalog-replica-b"]["labels"]["study.domain"],
            "domain_b",
        )
        self.assertIn("proto h2", haproxy)
        self.assertEqual(audit["service_count"], 4)
        self.assertTrue(audit["all_services_locked"])
        self.assertIn("@sha256:", services["product-catalog"]["image"])
        self.assertIn("product-catalog", services["caller"]["depends_on"])

    def test_prepare_colocated_tcp_proxy_assigns_one_domain(self) -> None:
        document, audit, haproxy = self._prepare(
            "deathstarbench_social_network", "colocated"
        )
        self.assertNotIn("proto h2", haproxy)
        assignments = audit["placement_pilot"]["domain_assignments"]
        self.assertEqual(assignments["a"], assignments["b"])
        proxy = document["services"]["user-timeline-service"]
        self.assertEqual(proxy["labels"]["study.role"], "proxy")

    def test_common_domain_event_targets_follow_placement(self) -> None:
        profile = select_placement_pilot_profile(
            self.config, "deathstarbench_social_network"
        )
        event = next(
            item for item in self.config.events if item.mechanism == "common_domain"
        )
        self.assertEqual(
            len(_event_targets(self.config, profile, "colocated", event)), 2
        )
        self.assertEqual(len(_event_targets(self.config, profile, "split", event)), 1)

    def test_operation_semantics_reject_malformed_2xx(self) -> None:
        valid, _, _ = validate_operation_response(
            "deathstarbench_social_network",
            "compose_post",
            200,
            b"Successfully upload post\n",
        )
        self.assertTrue(valid)
        valid, _, reason = validate_operation_response(
            "deathstarbench_social_network", "read_user_timeline", 200, b"{}"
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "invalid_timeline")
        valid, _, _ = validate_operation_response(
            "opentelemetry_demo",
            "browse_product",
            200,
            b'{"id":"OLJCESPC7Z"}',
        )
        self.assertTrue(valid)
        valid, _, reason = validate_operation_response(
            "opentelemetry_demo", "checkout", 200, b"{}"
        )
        self.assertFalse(valid)
        self.assertEqual(reason, "missing_order_ids")

    def test_runtime_is_forbidden_locally(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PlacementPilotError, "only in GitHub Actions"):
                run_placement_pilot(
                    self.config,
                    "opentelemetry_demo",
                    "split",
                    ROOT,
                    ROOT / "absent-compose.json",
                    ROOT / "absent-audit.json",
                    ROOT / "absent-haproxy.cfg",
                    ROOT / ".smoke" / "forbidden-placement-pilot",
                )

    def test_aggregate_requires_complete_usable_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_root = root / "input"
            for profile in self.config.profiles:
                for placement in self.config.placements:
                    directory = input_root / profile.id / placement
                    directory.mkdir(parents=True)
                    manifest = {
                        "profile": profile.id,
                        "placement": placement,
                        "pilot_only": True,
                        "usable_for_m7_freeze": True,
                        "counts": {
                            "requests": 211,
                            "immediate_successes": 200,
                            "semantic_successes": 200,
                            "fault_period_successes": 149,
                            "native_trace_count": 210,
                            "injections": 4,
                            "confirmed_injections": 4,
                            "restored_injections": 4,
                            "health_samples": 120,
                        },
                        "linked_success_fraction": 1.0,
                        "routing_audit": {"session_deltas": {"a": 24, "b": 24}},
                        "quality": {},
                    }
                    (directory / "placement_manifest.json").write_text(
                        json.dumps(manifest), encoding="utf-8"
                    )
            aggregate = aggregate_placement_pilots(
                self.config, input_root, root / "aggregate"
            )
            self.assertEqual(aggregate["source_cells"], 4)
            self.assertFalse(any(aggregate["quality"].values()))


if __name__ == "__main__":
    unittest.main()
