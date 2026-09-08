"""Versioned acquisition orchestration: unchanged M7 renewal/health engine, whole-operation driver.

Three orchestration functions are copied to bind the new driver without changing frozen M7 globals.
"""
from __future__ import annotations
import base64
import csv
import hashlib
import json
import math
import os
import random
import re
import statistics
import threading
import time
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
import numpy as np
from scipy.stats import chi2, t
from .live_fault_campaign import (
    _completed,
    _has_network,
    _inspect_containers,
    _is_paused,
    _network_record,
    _service_containers,
    _sleep_until,
    make_trace_context,
)
from .live_pilot import (
    _collect_telemetry,
    _deathstar_request,
    _git_head,
    _http_request,
    _otel_request,
    _runtime_containers,
    initialize_profile,
    wait_for_frontend,
)
from .live_pilot_config import RuntimePilotProfile, select_runtime_pilot_profile
from .live_placement_config import (
    PlacementPilotProfile,
    select_placement_pilot_profile,
)
from .live_placement_pilot import (
    _final_state,
    _proxy_stats,
    _timeline_has_text,
    validate_operation_response,
)
from .live_stochastic_config import StochasticPilotConfig
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv
from .live_stochastic_pilot import (
    CELL_SUMMARY_FIELDS,
    EVENT_FIELDS,
    FACTOR_YIELD_FIELDS,
    FactorDefinition,
    HEALTH_FIELDS,
    PERIOD_SUMMARY_FIELDS,
    REQUEST_FIELDS,
    RenewalEvent,
    StochasticCellPurpose,
    StochasticPilotError,
    TRACE_JOIN_FIELDS,
    _annotate_event_observation_lags,
    _container_matches_network,
    _container_matches_pause,
    _duration_recommendation,
    _factor_yields,
    _first_matching_health_offset,
    _format_time,
    _freeze_recommendation,
    _health_epoch_rows,
    _health_impairment_series,
    _health_sampler,
    _network_connect_command,
    _operation_order,
    _parse_time,
    _period_summary,
    _quantile_higher,
    _reconcile_network_states,
    _reconcile_pause_states,
    _repetition_recommendation,
    _row_effect_matches,
    _second_binned_request_series,
    _stable_seed,
    _stochastic_fault_controller,
    _targets_match_effect,
    _trace_join_rows,
    _transition_guard_recommendation,
    _transition_observation_plan,
    _utc_now,
    _write_jsonl,
    aggregate_stochastic_freeze_pilots,
    autocorrelation_block_length,
    factor_definitions,
    plan_renewal_events,
    renewal_schedule_seed,
    run_stochastic_freeze_pilot
)
from .whole_operation_contract import execute as execute_whole_operation

def _execute_request(config, profile, runtime_profile, placement, law, repetition, period,
                     scheduled_index, driver_index, operation, offset_seconds, request_namespace=''):
    namespace = f'{request_namespace}-' if request_namespace else ''
    request_id = namespace + f'{profile.id}-{placement}-{law}-r{repetition}-{period}-{scheduled_index:06d}'
    request = execute_whole_operation(runtime_profile.base_url, profile.id, operation, request_id, driver_index)
    request.update(placement=placement, failure_law=law, repetition=repetition, period=period,
                   scheduled_offset_seconds=offset_seconds)
    body = request['http_steps'][-1].get('response_base64','') if request['http_steps'] else ''
    response = dict(request_id=request_id, status_code=request['status_code'],content_base64=body,
                    sha256=request['response_sha256'],http_steps=request['http_steps'])
    return request,response

def _semantic_sentinels(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    law: str,
    repetition: int,
    request_namespace: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    law_index = list(config.laws).index(law)
    driver_base = 9_000_000 + repetition * 100 + law_index * 10
    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    for offset, operation in enumerate(runtime_profile.operations):
        request, response = _execute_request(
            config,
            profile,
            runtime_profile,
            placement,
            law,
            repetition,
            "sentinel",
            offset,
            driver_base + offset,
            operation,
            0.0,
            request_namespace,
        )
        requests.append(request)
        responses.append(response)

    if profile.id != "deathstarbench_social_network":
        return (
            requests,
            responses,
            {
                "kind": "synchronous_response_semantics",
                "applicable": False,
                "passed": True,
                "reason": "OTel pilot freezes synchronous response predicates only",
            },
        )

    expected_text = f"taid pilot post {driver_base}"
    locations = {
        "user_timeline_owner": (
            runtime_profile.base_url
            + "/wrk2-api/user-timeline/read?user_id=0&start=0&stop=1000"
        ),
        "home_timeline_follower": (
            runtime_profile.base_url
            + "/wrk2-api/home-timeline/read?user_id=1&start=0&stop=1000"
        ),
    }
    evidence: dict[str, Any] = {}
    for label, url in locations.items():
        deadline = time.monotonic() + 15.0
        attempts = 0
        status: int | None = None
        body = b""
        error = "not attempted"
        found = False
        while time.monotonic() < deadline:
            attempts += 1
            status, body, error = _http_request(url, timeout=2)
            found = (
                status is not None
                and 200 <= status < 300
                and _timeline_has_text(body, expected_text)
            )
            if found:
                break
            time.sleep(0.5)
        evidence[label] = {
            "attempts": attempts,
            "status_code": status,
            "found": found,
            "response_sha256": hashlib.sha256(body).hexdigest(),
            "error": error,
        }
    return (
        requests,
        responses,
        {
            "kind": "deathstarbench_compose_eventual_fanout",
            "applicable": True,
            "expected_text_sha256": hashlib.sha256(
                expected_text.encode("utf-8")
            ).hexdigest(),
            "locations": evidence,
            "passed": all(item["found"] for item in evidence.values()),
        },
    )


def _run_period(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    duration_seconds: int,
    compose_path: Path,
    events: tuple[RenewalEvent, ...],
    *,
    base_seed: int | None = None,
    request_namespace: str = "",
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    services = (*profile.replica_services.values(), profile.target_service)
    containers = _service_containers(compose_path, services)
    networks = {
        service: _network_record(containers[service])
        for service in profile.replica_services.values()
    }
    request_count = duration_seconds * config.request_rate_per_second
    workload_seed = _stable_seed(
        config.pilot_base_seed if base_seed is None else base_seed,
        profile.id,
        placement,
        law,
        repetition,
        period,
        "workload",
    )
    operations = _operation_order(runtime_profile, request_count, workload_seed)
    period_offset = {
        "baseline": 1_000_000,
        "calibration": 2_000_000,
        "test": 3_000_000,
    }[period]

    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []
    controller_summary: dict[str, Any] = {
        "events": 0,
        "confirmed": 0,
        "released": 0,
        "active_pause_causes_at_end": 0,
        "active_network_causes_at_end": 0,
        "errors": [],
    }
    stop_health = threading.Event()
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    health_thread = threading.Thread(
        target=_health_sampler,
        args=(
            config,
            profile,
            placement,
            law,
            repetition,
            period,
            compose_path,
            containers,
            started_monotonic,
            stop_health,
            health,
        ),
        name=f"m7c-health-{profile.id}-{placement}-{law}-{repetition}-{period}",
    )
    fault_thread: threading.Thread | None = None
    health_thread.start()
    if events:
        fault_thread = threading.Thread(
            target=_stochastic_fault_controller,
            args=(
                profile,
                placement,
                law,
                repetition,
                period,
                started_at,
                started_monotonic,
                events,
                duration_seconds,
                config.health_poll_seconds,
                config.transition_observation_minimum_ticks,
                containers,
                networks,
                event_rows,
                controller_summary,
            ),
            name=f"m7c-fault-{profile.id}-{placement}-{law}-{repetition}-{period}",
        )
        fault_thread.start()

    futures: list[Future[tuple[dict[str, Any], dict[str, Any]]]] = []
    with ThreadPoolExecutor(max_workers=config.request_workers) as executor:
        for index, operation in enumerate(operations):
            offset = index / config.request_rate_per_second
            _sleep_until(started_monotonic + offset)
            futures.append(
                executor.submit(
                    _execute_request,
                    config,
                    profile,
                    runtime_profile,
                    placement,
                    law,
                    repetition,
                    period,
                    index,
                    period_offset + index,
                    operation,
                    offset,
                    request_namespace,
                )
            )
        _sleep_until(started_monotonic + duration_seconds)
        stop_health.set()
        pairs = [future.result() for future in futures]
    if fault_thread is not None:
        fault_thread.join(timeout=duration_seconds + 30)
        if fault_thread.is_alive():
            raise StochasticPilotError("stochastic fault controller did not terminate")
    health_thread.join(timeout=15)
    if health_thread.is_alive():
        raise StochasticPilotError("stochastic health sampler did not terminate")
    completed_at = _utc_now()
    requests = [pair[0] for pair in pairs]
    responses = [pair[1] for pair in pairs]
    requests.sort(key=lambda row: row["request_id"])
    responses.sort(key=lambda row: row["request_id"])
    event_rows.sort(
        key=lambda row: (float(row["intended_offset_seconds"]), row["event_id"])
    )
    health.sort(key=lambda row: (float(row["elapsed_seconds"]), row["service"]))
    metadata = {
        "started_at": _format_time(started_at),
        "completed_at": _format_time(completed_at),
        "duration_seconds": duration_seconds,
        "workload_seed": workload_seed,
        "planned_requests": request_count,
        "planned_operations": {
            operation: operations.count(operation)
            for operation in runtime_profile.operations
        },
        "planned_events": len(events),
        "controller": controller_summary,
    }
    return requests, responses, event_rows, health, metadata


def _run_stochastic_cell(
    config: StochasticPilotConfig,
    profile_id: str,
    placement: str,
    law: str,
    repetition: int,
    checkout_directory: str | Path,
    compose_path: str | Path,
    image_audit_path: str | Path,
    output_directory: str | Path,
    purpose: StochasticCellPurpose,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise StochasticPilotError(
            "stochastic live cells may run only in GitHub Actions"
        )
    if repetition < 0 or repetition >= purpose.repetition_count:
        raise StochasticPilotError(
            f"repetition must lie in [0, {purpose.repetition_count - 1}]"
        )
    if law not in config.laws:
        raise StochasticPilotError(f"unknown failure law {law!r}")
    if placement not in config.placement.placements:
        raise StochasticPilotError(f"unknown placement {placement!r}")

    profile = select_placement_pilot_profile(config.placement, profile_id)
    runtime_profile = select_runtime_pilot_profile(config.placement.runtime, profile_id)
    checkout = Path(checkout_directory)
    compose = Path(compose_path)
    image_audit_file = Path(image_audit_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    campaign_started = _utc_now()
    observed_commit = _git_head(checkout)

    factors = factor_definitions(config, profile, placement, law)
    schedules = {
        period: plan_renewal_events(
            config,
            profile,
            placement,
            law,
            repetition,
            period,
            base_seed=purpose.base_seed,
        )
        for period in ("calibration", "test")
    }
    schedule_document = {
        "schema_version": 1,
        **purpose.role_fields,
        "profile": profile.id,
        "placement": placement,
        "failure_law": law,
        "repetition": repetition,
        "period_seconds": config.period_seconds,
        "factors": [asdict(factor) for factor in factors],
        "factor_schedule_seeds": {
            period: {
                factor.factor_id: renewal_schedule_seed(
                    config,
                    profile,
                    placement,
                    law,
                    repetition,
                    period,
                    factor.factor_id,
                    base_seed=purpose.base_seed,
                )
                for factor in factors
            }
            for period in ("calibration", "test")
        },
        "periods": {
            period: [asdict(event) for event in events]
            for period, events in schedules.items()
        },
    }
    (output / "planned-schedule.json").write_text(
        json.dumps(schedule_document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    wait_for_frontend(
        runtime_profile, config.placement.runtime.readiness_timeout_seconds
    )
    time.sleep(config.placement.runtime.post_start_stabilization_seconds)
    initialize_profile(runtime_profile)
    routing_before = _proxy_stats(config.placement, profile, compose)
    sentinel_requests, sentinel_responses, effect_audit = _semantic_sentinels(
        config,
        profile,
        runtime_profile,
        placement,
        law,
        repetition,
        purpose.request_namespace,
    )

    period_requests: dict[str, list[dict[str, Any]]] = {}
    period_responses: dict[str, list[dict[str, Any]]] = {}
    period_events: dict[str, list[dict[str, Any]]] = {}
    period_health: dict[str, list[dict[str, Any]]] = {}
    periods: dict[str, dict[str, Any]] = {}
    cleanups: dict[str, dict[str, Any]] = {}

    baseline = _run_period(
        config,
        profile,
        runtime_profile,
        placement,
        law,
        repetition,
        "baseline",
        config.baseline_seconds,
        compose,
        (),
        base_seed=purpose.base_seed,
        request_namespace=purpose.request_namespace,
    )
    (
        period_requests["baseline"],
        period_responses["baseline"],
        period_events["baseline"],
        period_health["baseline"],
        periods["baseline"],
    ) = baseline

    for period in ("calibration", "test"):
        result = _run_period(
            config,
            profile,
            runtime_profile,
            placement,
            law,
            repetition,
            period,
            config.period_seconds,
            compose,
            schedules[period],
            base_seed=purpose.base_seed,
            request_namespace=purpose.request_namespace,
        )
        (
            period_requests[period],
            period_responses[period],
            period_events[period],
            period_health[period],
            periods[period],
        ) = result
        _annotate_event_observation_lags(period_events[period], period_health[period])
        time.sleep(config.inter_period_recovery_seconds)
        cleanups[period] = _final_state(
            config.placement,
            profile,
            placement,
            compose,
        )

    routing_after = _proxy_stats(config.placement, profile, compose)
    routing_audit = {
        "before": routing_before,
        "after": routing_after,
        "session_deltas": {
            replica: (
                routing_after[replica]["sessions"] - routing_before[replica]["sessions"]
            )
            for replica in ("a", "b")
        },
    }
    final_state = cleanups["test"]

    all_requests = [
        row
        for period in ("baseline", "calibration", "test")
        for row in period_requests[period]
    ]
    all_responses = [
        row
        for period in ("baseline", "calibration", "test")
        for row in period_responses[period]
    ]
    all_events = [
        row for period in ("calibration", "test") for row in period_events[period]
    ]
    all_health = [
        row
        for period in ("baseline", "calibration", "test")
        for row in period_health[period]
    ]
    all_trace_requests = [*sentinel_requests, *all_requests]
    all_response_rows = [*sentinel_responses, *all_responses]

    _write_csv(output / "requests.csv", REQUEST_FIELDS, all_requests)
    _write_csv(output / "sentinel-requests.csv", REQUEST_FIELDS, sentinel_requests)
    _write_jsonl(output / "responses.jsonl", all_response_rows)
    _write_csv(output / "events.csv", EVENT_FIELDS, all_events)
    _write_csv(output / "health.csv", HEALTH_FIELDS, all_health)
    (output / "semantic-effect-audit.json").write_text(
        json.dumps(effect_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "routing-audit.json").write_text(
        json.dumps(routing_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "period-cleanup.json").write_text(
        json.dumps(cleanups, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "final-state.json").write_text(
        json.dumps(final_state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    time.sleep(config.trace_flush_seconds)
    native_trace_count, telemetry_error = _collect_telemetry(
        runtime_profile,
        campaign_started,
        output,
    )
    raw_path = output / (
        "raw-telemetry.json"
        if runtime_profile.telemetry_kind == "jaeger_api"
        else "raw-telemetry.log"
    )
    trace_join = _trace_join_rows(all_trace_requests, raw_path)
    _write_csv(output / "trace-join.csv", TRACE_JOIN_FIELDS, trace_join)

    running_containers, unlocked_running = _runtime_containers(compose, output)
    image_audit = json.loads(image_audit_file.read_text(encoding="utf-8"))
    period_summaries = {
        period: _period_summary(
            config,
            profile.id,
            placement,
            law,
            repetition,
            period,
            (
                config.baseline_seconds
                if period == "baseline"
                else config.period_seconds
            ),
            period_requests[period],
            period_events[period],
            period_health[period],
        )
        for period in ("baseline", "calibration", "test")
    }
    factor_yields = [
        row
        for period in ("calibration", "test")
        for row in _factor_yields(
            profile.id,
            placement,
            law,
            repetition,
            period,
            factors,
            period_events[period],
        )
    ]

    expected_period_requests = config.baseline_requests + 2 * config.requests_per_period
    expected_trace_rows = expected_period_requests + len(runtime_profile.operations)
    request_ids = [str(row["request_id"]) for row in all_trace_requests]
    trace_ids = [str(row["trace_id"]) for row in all_trace_requests]
    successful = sum(bool(row["semantic_success"]) for row in all_trace_requests)
    period_semantic_successes = sum(
        bool(row["semantic_success"]) for row in all_requests
    )
    linked_successful = sum(
        bool(row["request_success"]) and bool(row["trace_present"])
        for row in trace_join
    )
    linked_fraction = linked_successful / successful if successful else 0.0
    expected_events = sum(len(events) for events in schedules.values())
    actual_plan = {
        (
            row["period"],
            row["event_id"],
            row["factor_id"],
            row["targets"],
        )
        for row in all_events
    }
    expected_plan = {
        (
            period,
            event.event_id,
            event.factor_id,
            ";".join(event.targets),
        )
        for period, events in schedules.items()
        for event in events
    }
    services = (*profile.replica_services.values(), profile.target_service)
    minimum_health = {
        "baseline": math.floor(
            config.baseline_seconds
            / config.health_poll_seconds
            * config.minimum_health_observation_fraction
        ),
        "calibration": math.floor(
            config.period_seconds
            / config.health_poll_seconds
            * config.minimum_health_observation_fraction
        ),
        "test": math.floor(
            config.period_seconds
            / config.health_poll_seconds
            * config.minimum_health_observation_fraction
        ),
    }
    health_counts = {
        (period, service): sum(
            row["period"] == period and row["service"] == service and not row["error"]
            for row in all_health
        )
        for period in ("baseline", "calibration", "test")
        for service in services
    }
    workload_seeds = [periods[name]["workload_seed"] for name in periods]
    schedule_seed_records = {
        (
            period,
            factor.factor_id,
            renewal_schedule_seed(
                config,
                profile,
                placement,
                law,
                repetition,
                period,
                factor.factor_id,
                base_seed=purpose.base_seed,
            ),
        )
        for period in ("calibration", "test")
        for factor in factors
    }
    schedule_seed_values = [record[2] for record in schedule_seed_records]
    sentinel_failures = sum(
        not bool(row["semantic_success"]) for row in sentinel_requests
    )
    baseline_fraction = period_summaries["baseline"]["semantic_success_fraction"]
    quality = {
        "checkout_commit_mismatches": int(observed_commit != runtime_profile.commit),
        "request_count_mismatches": int(len(all_requests) != expected_period_requests),
        "trace_row_count_mismatches": int(len(trace_join) != expected_trace_rows),
        "duplicate_request_ids": len(request_ids) - len(set(request_ids)),
        "duplicate_trace_ids": len(trace_ids) - len(set(trace_ids)),
        "workload_seed_collisions": len(workload_seeds) - len(set(workload_seeds)),
        "schedule_seed_collisions": len(schedule_seed_values)
        - len(set(schedule_seed_values)),
        "operation_count_mismatches": sum(
            abs(
                sum(row["operation"] == operation for row in period_requests[period])
                - count
            )
            for period, metadata in periods.items()
            for operation, count in metadata["planned_operations"].items()
        ),
        "sentinel_semantic_failures": sentinel_failures,
        "eventual_effect_failures": int(not effect_audit["passed"]),
        "baseline_success_below_minimum": int(
            baseline_fraction < config.minimum_baseline_semantic_success_fraction
        ),
        "schedule_event_count_mismatches": int(len(all_events) != expected_events),
        "schedule_mapping_mismatches": len(
            actual_plan.symmetric_difference(expected_plan)
        ),
        "unconfirmed_events": sum(not bool(row["confirmed"]) for row in all_events),
        "unreleased_events": sum(
            not bool(row["release_confirmed"]) for row in all_events
        ),
        "event_controller_errors": sum(bool(row["error"]) for row in all_events),
        "controller_summary_errors": sum(
            len(periods[period]["controller"]["errors"])
            for period in ("calibration", "test")
        ),
        "active_causes_at_period_end": sum(
            periods[period]["controller"]["active_pause_causes_at_end"]
            + periods[period]["controller"]["active_network_causes_at_end"]
            for period in ("calibration", "test")
        ),
        "unobserved_eligible_event_transitions": sum(
            (
                bool(row["observation_start_eligible"])
                and row["observation_start_lag_seconds"] == ""
            )
            + (
                bool(row["observation_release_eligible"])
                and row["observation_release_lag_seconds"] == ""
            )
            for row in all_events
        ),
        "health_service_periods_below_minimum": sum(
            count < minimum_health[period]
            for (period, _), count in health_counts.items()
        ),
        "health_sampling_errors": sum(bool(row["error"]) for row in all_health),
        "linked_success_fraction_below_minimum": int(
            linked_fraction < config.minimum_linked_success_fraction
        ),
        "telemetry_collection_errors": int(bool(telemetry_error)),
        "unserved_replicas": sum(
            routing_audit["session_deltas"][replica]
            < config.minimum_backend_sessions_per_replica
            for replica in ("a", "b")
        ),
        "unlocked_rendered_services": int(
            not image_audit.get("all_services_locked", False)
        ),
        "unlocked_running_images": unlocked_running,
        "running_container_count_mismatches": int(
            len(running_containers) != int(image_audit.get("service_count", 0))
        ),
        "unclean_period_boundaries": sum(
            not bool(state["clean"]) for state in cleanups.values()
        ),
        "unclean_final_state": int(not final_state["clean"]),
    }
    manifest = {
        "schema_version": 1,
        "kind": purpose.kind,
        "experiment_id": config.id,
        **purpose.role_fields,
        purpose.usability_field: not any(quality.values()),
        "profile": profile.id,
        "placement": placement,
        "failure_law": law,
        "repetition": repetition,
        "expected_checkout_commit": runtime_profile.commit,
        "observed_checkout_commit": observed_commit,
        "periods": periods,
        "period_summaries": period_summaries,
        "factor_yields": factor_yields,
        "transition_lags_seconds": {
            "start": [
                float(row["observation_start_lag_seconds"])
                for row in all_events
                if row["observation_start_eligible"]
                and row["observation_start_lag_seconds"] != ""
            ],
            "release": [
                float(row["observation_release_lag_seconds"])
                for row in all_events
                if row["observation_release_eligible"]
                and row["observation_release_lag_seconds"] != ""
            ],
        },
        "routing_audit": routing_audit,
        "semantic_effect_audit": effect_audit,
        "cleanups": cleanups,
        "final_state": final_state,
        "counts": {
            "requests": len(all_requests),
            "sentinel_requests": len(sentinel_requests),
            "trace_requests": len(all_trace_requests),
            "immediate_successes": sum(
                bool(row["immediate_success"]) for row in all_trace_requests
            ),
            "semantic_successes": period_semantic_successes,
            "sentinel_semantic_successes": sum(
                bool(row["semantic_success"]) for row in sentinel_requests
            ),
            "total_semantic_successes": successful,
            "events": len(all_events),
            "confirmed_events": sum(bool(row["confirmed"]) for row in all_events),
            "released_events": sum(
                bool(row["release_confirmed"]) for row in all_events
            ),
            "observable_transitions_required": sum(
                bool(row["observation_start_required"])
                + bool(row["observation_release_required"])
                for row in all_events
            ),
            "observable_transitions_eligible": sum(
                bool(row["observation_start_eligible"])
                + bool(row["observation_release_eligible"])
                for row in all_events
            ),
            "resolution_limited_transitions": sum(
                (
                    bool(row["observation_start_required"])
                    and not bool(row["observation_start_eligible"])
                )
                + (
                    bool(row["observation_release_required"])
                    and not bool(row["observation_release_eligible"])
                )
                for row in all_events
            ),
            "eligible_transitions_observed": sum(
                (
                    bool(row["observation_start_eligible"])
                    and row["observation_start_lag_seconds"] != ""
                )
                + (
                    bool(row["observation_release_eligible"])
                    and row["observation_release_lag_seconds"] != ""
                )
                for row in all_events
            ),
            "health_samples": len(all_health),
            "trace_rows": len(trace_join),
            "trace_rows_present": sum(bool(row["trace_present"]) for row in trace_join),
            "successful_requests_with_trace": linked_successful,
            "native_trace_count": native_trace_count,
            "running_containers": len(running_containers),
            "locked_services": int(image_audit.get("service_count", 0)),
        },
        "linked_success_fraction": linked_fraction,
        "health_samples_by_service_period": {
            f"{period}:{service}": count
            for (period, service), count in sorted(health_counts.items())
        },
        "telemetry_kind": runtime_profile.telemetry_kind,
        "telemetry_error": telemetry_error,
        "quality": quality,
        "files": {
            "requests_sha256": file_sha256(output / "requests.csv"),
            "sentinel_requests_sha256": file_sha256(output / "sentinel-requests.csv"),
            "responses_sha256": file_sha256(output / "responses.jsonl"),
            "events_sha256": file_sha256(output / "events.csv"),
            "health_sha256": file_sha256(output / "health.csv"),
            "trace_join_sha256": file_sha256(output / "trace-join.csv"),
            "raw_telemetry_sha256": file_sha256(raw_path),
            "schedule_sha256": file_sha256(output / "planned-schedule.json"),
            "image_audit_sha256": file_sha256(image_audit_file),
            "runtime_containers_sha256": file_sha256(
                output / "runtime-containers.json"
            ),
        },
        "environment": environment_manifest(),
    }
    (output / purpose.manifest_filename).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise StochasticPilotError(
            f"{purpose.failure_label} cell acceptance failures: {failures}"
        )
    return manifest
