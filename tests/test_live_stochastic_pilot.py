from __future__ import annotations

import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from telemetry_availability.live_placement_config import (
    select_placement_pilot_profile,
)
from telemetry_availability.live_stochastic_config import (
    load_stochastic_pilot_config,
)
from telemetry_availability.live_stochastic_pilot import (
    RenewalEvent,
    StochasticPilotError,
    _stochastic_fault_controller,
    _trace_join_rows,
    aggregate_stochastic_freeze_pilots,
    autocorrelation_block_length,
    factor_definitions,
    plan_renewal_events,
    run_stochastic_freeze_pilot,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "m7c_stochastic_freeze_pilot.yaml"


class StochasticFreezePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_stochastic_pilot_config(CONFIG_PATH)

    def test_contract_is_pilot_only_and_expands_to_64_cells(self) -> None:
        self.assertTrue(self.config.pilot_only)
        self.assertEqual(self.config.pilot_repetitions, 4)
        self.assertEqual(self.config.expected_cells, 64)
        self.assertEqual(self.config.baseline_requests, 240)
        self.assertEqual(self.config.requests_per_period, 1200)
        self.assertNotEqual(self.config.pilot_base_seed, self.config.main_base_seed)

    def test_factor_mapping_uses_real_replicas_and_placement_domains(self) -> None:
        profile = select_placement_pilot_profile(
            self.config.placement, "deathstarbench_social_network"
        )
        colocated = factor_definitions(self.config, profile, "colocated", "NCD")
        split = factor_definitions(self.config, profile, "split", "NCD")
        self.assertEqual(len(colocated), 5)
        self.assertEqual(len(split), 6)
        common_colocated = next(
            item for item in colocated if item.factor_id == "common_domain:domain_a"
        )
        self.assertEqual(len(common_colocated.targets), 2)
        common_split = [item for item in split if item.mechanism == "common_domain"]
        self.assertEqual(
            {item.domain for item in common_split}, {"domain_a", "domain_b"}
        )
        communications = [item for item in split if item.mechanism == "communication"]
        self.assertEqual(
            {item.targets[0] for item in communications},
            set(profile.replica_services.values()),
        )
        self.assertNotIn(
            profile.target_service, {item.targets[0] for item in communications}
        )

    def test_renewal_schedules_are_deterministic_independent_and_bounded(self) -> None:
        profile = select_placement_pilot_profile(
            self.config.placement, "opentelemetry_demo"
        )
        first = plan_renewal_events(
            self.config, profile, "split", "NCD", 0, "calibration"
        )
        repeated = plan_renewal_events(
            self.config, profile, "split", "NCD", 0, "calibration"
        )
        test = plan_renewal_events(self.config, profile, "split", "NCD", 0, "test")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, test)
        self.assertTrue(first)
        self.assertTrue(
            all(event.end_seconds < self.config.period_seconds for event in first)
        )
        by_factor: dict[str, list] = {}
        for event in first:
            by_factor.setdefault(event.factor_id, []).append(event)
        for events in by_factor.values():
            ordered = sorted(events, key=lambda item: item.offset_seconds)
            self.assertTrue(
                all(
                    left.end_seconds < right.offset_seconds
                    for left, right in zip(ordered, ordered[1:])
                )
            )
        overlaps = [
            (left, right)
            for index, left in enumerate(first)
            for right in first[index + 1 :]
            if left.factor_id != right.factor_id
            and left.offset_seconds < right.end_seconds
            and right.offset_seconds < left.end_seconds
        ]
        self.assertTrue(overlaps)

    def test_block_length_detects_dependence_but_not_constant_series(self) -> None:
        constant = autocorrelation_block_length([1.0] * 60, 0.1, 3, 20)
        dependent = autocorrelation_block_length(
            [0.0] * 20 + [1.0] * 20 + [0.0] * 20,
            0.1,
            3,
            20,
        )
        self.assertEqual(constant, 1)
        self.assertGreater(dependent, 1)

    def test_trace_join_scans_raw_telemetry_once_and_matches_exact_tokens(self) -> None:
        requests = [
            {
                "profile": "p",
                "placement": "split",
                "failure_law": "N",
                "repetition": 0,
                "period": "test",
                "request_id": "r1",
                "trace_id": "0123456789abcdef",
                "semantic_success": True,
            },
            {
                "profile": "p",
                "placement": "split",
                "failure_law": "N",
                "repetition": 0,
                "period": "test",
                "request_id": "r2",
                "trace_id": "fedcba98765432100123456789abcdef",
                "semantic_success": False,
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            raw_path = Path(temporary) / "raw.log"
            raw_path.write_text(
                "0123456789ABCDEF 0123456789abcdef "
                "fedcba98765432100123456789abcdef "
                "a0123456789abcdef0\n",
                encoding="utf-8",
            )
            rows = _trace_join_rows(requests, raw_path)
        self.assertEqual([row["raw_occurrences"] for row in rows], [2, 1])
        self.assertTrue(all(row["trace_present"] for row in rows))

    def test_overlap_controller_does_not_release_an_active_cause(self) -> None:
        profile = select_placement_pilot_profile(
            self.config.placement, "deathstarbench_social_network"
        )
        service = profile.replica_services["a"]
        events = (
            RenewalEvent(
                "first",
                "individual:a",
                "individual",
                "pause",
                "",
                (service,),
                1,
                0.0,
                2.0,
            ),
            RenewalEvent(
                "second",
                "common_domain:domain_a",
                "common_domain",
                "pause",
                "domain_a",
                (service,),
                2,
                1.0,
                2.0,
            ),
        )
        rows: list[dict] = []
        summary: dict = {}
        with (
            patch("telemetry_availability.live_stochastic_pilot._sleep_until"),
            patch(
                "telemetry_availability.live_stochastic_pilot._reconcile_pause_states",
                return_value=[],
            ),
            patch(
                "telemetry_availability.live_stochastic_pilot._reconcile_network_states",
                return_value=[],
            ),
            patch(
                "telemetry_availability.live_stochastic_pilot._targets_match_effect",
                return_value=True,
            ),
        ):
            _stochastic_fault_controller(
                profile,
                "colocated",
                "ND",
                0,
                "calibration",
                datetime_for_test(),
                0.0,
                events,
                {service: "container-a"},
                {service: ("network", (service,))},
                rows,
                summary,
            )
        by_id = {row["event_id"]: row for row in rows}
        self.assertEqual(by_id["first"]["expected_affected_after_release"], service)
        self.assertEqual(by_id["second"]["expected_affected_after_release"], "")
        self.assertEqual(summary["active_pause_causes_at_end"], 0)

    def test_runtime_is_forbidden_locally(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(StochasticPilotError, "only in GitHub Actions"):
                run_stochastic_freeze_pilot(
                    self.config,
                    "opentelemetry_demo",
                    "split",
                    "NCD",
                    0,
                    ROOT,
                    ROOT / "absent-compose.json",
                    ROOT / "absent-image-audit.json",
                    ROOT / ".smoke" / "forbidden-m7c",
                )

    def test_aggregate_requires_complete_matrix_and_freezes_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root / "inputs"
            for profile in self.config.placement.profiles:
                for placement in self.config.placement.placements:
                    for law in self.config.laws:
                        for repetition in range(self.config.pilot_repetitions):
                            cell = (
                                inputs / profile.id / placement / law / f"r{repetition}"
                            )
                            cell.mkdir(parents=True)
                            calibration = 0.90 + repetition * 0.001
                            test = calibration + (0.004 if repetition % 2 else -0.004)
                            summaries = {
                                period: {
                                    "profile": profile.id,
                                    "placement": placement,
                                    "failure_law": law,
                                    "repetition": repetition,
                                    "period": period,
                                    "duration_seconds": 60
                                    if period == "baseline"
                                    else 300,
                                    "requests": 240 if period == "baseline" else 1200,
                                    "semantic_successes": 240
                                    if period == "baseline"
                                    else 1080,
                                    "semantic_success_fraction": (
                                        1.0
                                        if period == "baseline"
                                        else calibration
                                        if period == "calibration"
                                        else test
                                    ),
                                    "request_block_seconds": 4,
                                    "health_block_seconds": 8,
                                    "block_length_seconds": 8,
                                    "effective_blocks": 37.5,
                                    "events": 0 if period == "baseline" else 20,
                                    "confirmed_events": 0
                                    if period == "baseline"
                                    else 20,
                                    "released_events": 0
                                    if period == "baseline"
                                    else 20,
                                }
                                for period in ("baseline", "calibration", "test")
                            }
                            manifest = {
                                "profile": profile.id,
                                "placement": placement,
                                "failure_law": law,
                                "repetition": repetition,
                                "pilot_only": True,
                                "usable_for_m7_freeze": True,
                                "counts": {
                                    "requests": 2640,
                                    "semantic_successes": 2400,
                                    "events": 40,
                                    "confirmed_events": 40,
                                    "released_events": 40,
                                    "trace_rows": 2643,
                                    "trace_rows_present": 2643,
                                    "health_samples": 1980,
                                },
                                "linked_success_fraction": 1.0,
                                "routing_audit": {
                                    "session_deltas": {"a": 100, "b": 100}
                                },
                                "period_summaries": summaries,
                                "factor_yields": [],
                                "transition_lags_seconds": {
                                    "start": [0.8, 1.2],
                                    "release": [1.0, 1.5],
                                },
                                "quality": {},
                            }
                            (cell / "pilot-manifest.json").write_text(
                                json.dumps(manifest), encoding="utf-8"
                            )
                            with (cell / "trace-join.csv").open(
                                "w", encoding="utf-8", newline=""
                            ) as handle:
                                writer = csv.DictWriter(
                                    handle, fieldnames=TRACE_FIXTURE_FIELDS
                                )
                                writer.writeheader()
                                writer.writerow(
                                    {
                                        "request_id": (
                                            f"{profile.id}-{placement}-{law}-r{repetition}"
                                        ),
                                        "trace_id": hashlib_for_test(
                                            profile.id, placement, law, repetition
                                        ),
                                    }
                                )
            aggregate = aggregate_stochastic_freeze_pilots(
                self.config, inputs, root / "aggregate"
            )
            self.assertEqual(aggregate["source_cells"], 64)
            self.assertTrue(aggregate["recommendation"]["freeze_ready"])
            self.assertIsNotNone(
                aggregate["recommendation"]["selected_design"]["period_seconds"]
            )
            self.assertIsNotNone(
                aggregate["recommendation"]["selected_design"]["repetitions"]
            )
            self.assertFalse(any(aggregate["quality"].values()))


TRACE_FIXTURE_FIELDS = ("request_id", "trace_id")


def hashlib_for_test(*parts: object) -> str:
    import hashlib

    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32]


def datetime_for_test():
    from datetime import datetime, timezone

    return datetime(2026, 9, 5, tzinfo=timezone.utc)


if __name__ == "__main__":
    unittest.main()
