from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.live_fault_campaign import (
    LiveFaultError,
    aggregate_live_fault_diagnostics,
    make_trace_context,
    plan_fault_events,
    run_live_fault_diagnostic,
)
from telemetry_availability.live_fault_config import (
    EXPECTED_LAWS,
    load_live_fault_config,
    select_live_fault_profile,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "m7a_fault_acquisition.yaml"


class LiveFaultCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_live_fault_config(CONFIG)

    def test_contract_matrix_and_budget_are_explicit(self) -> None:
        self.assertTrue(self.config.diagnostic_only)
        self.assertEqual(self.config.laws, EXPECTED_LAWS)
        self.assertEqual(self.config.requests_per_period, 120)
        self.assertEqual(self.config.repetitions, 1)
        self.assertEqual(
            {profile.id for profile in self.config.profiles},
            {profile.id for profile in self.config.runtime.profiles},
        )

    def test_fault_plan_exercises_every_declared_mechanism_inside_period(self) -> None:
        for profile in self.config.profiles:
            for law, expected in self.config.laws.items():
                plans = plan_fault_events(
                    self.config,
                    profile,
                    law,
                    seed=12345,
                    period="calibration",
                )
                self.assertEqual({plan.mechanism for plan in plans}, set(expected))
                self.assertTrue(
                    all(
                        plan.offset_seconds + plan.duration_seconds
                        < self.config.period_seconds
                        for plan in plans
                    )
                )
                self.assertEqual(
                    [plan.offset_seconds for plan in plans],
                    sorted(plan.offset_seconds for plan in plans),
                )

    def test_trace_context_is_deterministic_unique_and_native(self) -> None:
        death = make_trace_context("deathstarbench_social_network", "request-a")
        death_again = make_trace_context(
            "deathstarbench_social_network",
            "request-a",
        )
        otel = make_trace_context("opentelemetry_demo", "request-a")
        self.assertEqual(death, death_again)
        self.assertEqual(len(death[0]), 16)
        self.assertEqual(death[1], "uber-trace-id")
        self.assertTrue(death[2].endswith(":0:1"))
        self.assertEqual(len(otel[0]), 32)
        self.assertEqual(otel[1], "traceparent")
        self.assertTrue(otel[2].startswith("00-"))
        self.assertNotEqual(
            otel[0],
            make_trace_context("opentelemetry_demo", "request-b")[0],
        )

    def test_profile_fault_targets_are_in_health_audit(self) -> None:
        for profile in self.config.profiles:
            selected = select_live_fault_profile(self.config, profile.id)
            targets = {
                selected.individual_service,
                selected.communication_service,
                *selected.common_domain_services,
            }
            self.assertTrue(targets.issubset(set(selected.health_services)))

    def test_runtime_execution_is_forbidden_locally(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LiveFaultError, "only in GitHub Actions"):
                run_live_fault_diagnostic(
                    self.config,
                    "opentelemetry_demo",
                    "N",
                    0,
                    ROOT,
                    ROOT / "missing-compose.json",
                    ROOT / "missing-audit.json",
                    ROOT / ".smoke" / "forbidden-fault-diagnostic",
                )

    def test_aggregate_requires_and_preserves_all_diagnostic_cells(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shards = root / "shards"
            for profile in self.config.profiles:
                for law in self.config.laws:
                    cell = shards / profile.id / law
                    cell.mkdir(parents=True)
                    manifest = {
                        "profile": profile.id,
                        "failure_law": law,
                        "repetition": 0,
                        "diagnostic_only": True,
                        "usable_for_m7_design": True,
                        "counts": {
                            "requests": 240,
                            "successful_requests": 200,
                            "failed_requests": 40,
                            "successful_requests_with_trace": 190,
                            "native_trace_count": 210,
                            "injections": 6,
                            "confirmed_injections": 6,
                            "restored_injections": 6,
                            "health_samples": 120,
                        },
                        "success_fraction": 200 / 240,
                        "linked_success_fraction": 190 / 200,
                        "quality": {
                            "checkout_commit_mismatches": 0,
                            "request_count_mismatches": 0,
                        },
                    }
                    (cell / "campaign_manifest.json").write_text(
                        json.dumps(manifest),
                        encoding="utf-8",
                    )
            output = root / "aggregate"
            aggregate = aggregate_live_fault_diagnostics(
                self.config,
                shards,
                output,
            )
            self.assertTrue(aggregate["diagnostic_only"])
            self.assertEqual(aggregate["source_cells"], 8)
            self.assertEqual(set(aggregate["quality"].values()), {0})
            self.assertTrue((output / "summary.csv").is_file())


if __name__ == "__main__":
    unittest.main()
