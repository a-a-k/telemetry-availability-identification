from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import os
import random
import statistics
import threading
import time
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


class StochasticPilotError(RuntimeError):
    """Raised when M7C evidence violates its predeclared technical contract."""


REQUEST_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "request_id",
    "trace_id",
    "trace_header",
    "scheduled_offset_seconds",
    "started_at",
    "completed_at",
    "operation",
    "branch_class",
    "status_code",
    "immediate_success",
    "semantic_success",
    "semantic_rule",
    "semantic_reason",
    "timed_out",
    "latency_ms",
    "response_bytes",
    "response_sha256",
    "error",
)

EVENT_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "event_id",
    "factor_id",
    "mechanism",
    "effect",
    "domain",
    "targets",
    "target_count",
    "schedule_seed",
    "intended_offset_seconds",
    "intended_duration_seconds",
    "intended_at",
    "applied_at",
    "applied_offset_seconds",
    "verified_at",
    "released_at",
    "released_offset_seconds",
    "confirmed",
    "release_confirmed",
    "expected_affected_after_release",
    "observation_start_lag_seconds",
    "observation_release_lag_seconds",
    "error",
)

HEALTH_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "observed_at",
    "elapsed_seconds",
    "service",
    "role",
    "replica",
    "domain",
    "container_id",
    "running",
    "paused",
    "health",
    "network_count",
    "backend_status",
    "backend_check_status",
    "backend_sessions",
    "error",
)

TRACE_JOIN_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "request_id",
    "trace_id",
    "request_success",
    "trace_present",
    "raw_occurrences",
)

CELL_SUMMARY_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "requests",
    "semantic_successes",
    "baseline_success_fraction",
    "calibration_success_fraction",
    "test_success_fraction",
    "paired_endpoint_delta",
    "calibration_block_seconds",
    "test_block_seconds",
    "events",
    "confirmed_events",
    "released_events",
    "trace_rows",
    "trace_rows_present",
    "linked_success_fraction",
    "health_samples",
    "route_sessions_a",
    "route_sessions_b",
    "usable",
    "pilot_only",
)

PERIOD_SUMMARY_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "duration_seconds",
    "requests",
    "semantic_successes",
    "semantic_success_fraction",
    "request_block_seconds",
    "health_block_seconds",
    "block_length_seconds",
    "effective_blocks",
    "events",
    "confirmed_events",
    "released_events",
)

FACTOR_YIELD_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "factor_id",
    "mechanism",
    "targets",
    "events",
    "confirmed_events",
    "released_events",
    "intended_down_seconds",
)


@dataclass(frozen=True)
class FactorDefinition:
    factor_id: str
    mechanism: str
    effect: str
    domain: str
    targets: tuple[str, ...]


@dataclass(frozen=True)
class RenewalEvent:
    event_id: str
    factor_id: str
    mechanism: str
    effect: str
    domain: str
    targets: tuple[str, ...]
    schedule_seed: int
    offset_seconds: float
    duration_seconds: float

    @property
    def end_seconds(self) -> float:
        return self.offset_seconds + self.duration_seconds


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _stable_seed(base_seed: int, *parts: object) -> int:
    material = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def factor_definitions(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    law: str,
) -> tuple[FactorDefinition, ...]:
    if placement not in config.placement.placements:
        raise StochasticPilotError(f"unknown placement {placement!r}")
    if law not in config.laws:
        raise StochasticPilotError(f"unknown failure law {law!r}")
    assignments = config.placement.placements[placement]
    replicas = profile.replica_services
    factors: list[FactorDefinition] = []
    for mechanism in config.laws[law]:
        if mechanism == "individual":
            for replica in ("a", "b"):
                factors.append(
                    FactorDefinition(
                        factor_id=f"individual:{replica}",
                        mechanism=mechanism,
                        effect="pause",
                        domain="",
                        targets=(replicas[replica],),
                    )
                )
        elif mechanism == "communication":
            for replica in ("a", "b"):
                factors.append(
                    FactorDefinition(
                        factor_id=f"communication:{replica}",
                        mechanism=mechanism,
                        effect="network_disconnect",
                        domain="",
                        targets=(replicas[replica],),
                    )
                )
        elif mechanism == "common_domain":
            for domain in sorted(set(assignments.values())):
                targets = tuple(
                    replicas[replica]
                    for replica in ("a", "b")
                    if assignments[replica] == domain
                )
                factors.append(
                    FactorDefinition(
                        factor_id=f"common_domain:{domain}",
                        mechanism=mechanism,
                        effect="pause",
                        domain=domain,
                        targets=targets,
                    )
                )
        else:  # guarded by configuration validation
            raise StochasticPilotError(f"unsupported mechanism {mechanism!r}")
    return tuple(factors)


def renewal_schedule_seed(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    factor_id: str,
    *,
    base_seed: int | None = None,
) -> int:
    seed_root = config.pilot_base_seed if base_seed is None else base_seed
    return _stable_seed(
        seed_root,
        profile.id,
        placement,
        law,
        repetition,
        period,
        factor_id,
        "renewal",
    )


def plan_renewal_events(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    *,
    duration_seconds: int | None = None,
    base_seed: int | None = None,
) -> tuple[RenewalEvent, ...]:
    duration = config.period_seconds if duration_seconds is None else duration_seconds
    events: list[RenewalEvent] = []
    for factor in factor_definitions(config, profile, placement, law):
        process = config.renewal_processes[factor.mechanism]
        schedule_seed = renewal_schedule_seed(
            config,
            profile,
            placement,
            law,
            repetition,
            period,
            factor.factor_id,
            base_seed=base_seed,
        )
        rng = random.Random(schedule_seed)
        cursor = 0.0
        event_index = 0
        exponential_mean = process.mean_up_seconds - process.minimum_up_seconds
        while True:
            up_seconds = process.minimum_up_seconds + rng.expovariate(
                1.0 / exponential_mean
            )
            offset = cursor + up_seconds
            down_seconds = rng.uniform(
                process.minimum_down_seconds,
                process.maximum_down_seconds,
            )
            # Reserve two audit ticks after release so the ordinary sampler can
            # observe recovery before the period is closed.
            if offset + down_seconds + 2 * config.health_poll_seconds >= duration:
                break
            events.append(
                RenewalEvent(
                    event_id=(
                        f"{period}-{factor.factor_id.replace(':', '_')}-"
                        f"{event_index:03d}"
                    ),
                    factor_id=factor.factor_id,
                    mechanism=factor.mechanism,
                    effect=factor.effect,
                    domain=factor.domain,
                    targets=factor.targets,
                    schedule_seed=schedule_seed,
                    offset_seconds=offset,
                    duration_seconds=down_seconds,
                )
            )
            cursor = offset + down_seconds
            event_index += 1
    events.sort(key=lambda item: (item.offset_seconds, item.event_id))
    return tuple(events)


def autocorrelation_block_length(
    values: Iterable[float],
    threshold: float,
    consecutive_lags: int,
    max_lag: int,
) -> int:
    series = np.asarray(tuple(values), dtype=float)
    if series.size < 3 or float(np.var(series)) <= 1e-15:
        return 1
    centered = series - float(np.mean(series))
    denominator = float(np.dot(centered, centered))
    usable_max = min(max_lag, max(1, series.size // 3))
    below = 0
    for lag in range(1, usable_max + 1):
        correlation = float(np.dot(centered[:-lag], centered[lag:]) / denominator)
        if abs(correlation) <= threshold:
            below += 1
            if below >= consecutive_lags:
                return lag - consecutive_lags + 1
        else:
            below = 0
    return usable_max


def _operation_order(
    runtime_profile: RuntimePilotProfile,
    count: int,
    seed: int,
) -> list[str]:
    operations = [
        runtime_profile.operations[index % len(runtime_profile.operations)]
        for index in range(count)
    ]
    random.Random(seed).shuffle(operations)
    return operations


def _execute_request(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    scheduled_index: int,
    driver_index: int,
    operation: str,
    offset_seconds: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_id = (
        f"{profile.id}-{placement}-{law}-r{repetition}-{period}-{scheduled_index:06d}"
    )
    trace_id, trace_header, trace_value = make_trace_context(profile.id, request_id)
    started = _utc_now()
    started_monotonic = time.monotonic()
    try:
        if profile.id == "deathstarbench_social_network":
            status, body, error, branch = _deathstar_request(
                runtime_profile,
                operation,
                driver_index,
                extra_headers={trace_header: trace_value},
                timeout=float(config.request_timeout_seconds),
            )
        elif profile.id == "opentelemetry_demo":
            status, body, error, branch = _otel_request(
                runtime_profile,
                operation,
                f"m7c-{placement}-{law}-r{repetition}-{period}",
                driver_index,
                extra_headers={trace_header: trace_value},
                timeout=float(config.request_timeout_seconds),
            )
        else:
            raise StochasticPilotError(f"no request driver for {profile.id!r}")
    except Exception as request_error:  # retained in the complete external census
        status = None
        body = b""
        branch = "driver_error"
        error = f"{type(request_error).__name__}: {request_error}"
    completed = _utc_now()
    semantic_success, semantic_rule, semantic_reason = validate_operation_response(
        profile.id,
        operation,
        status,
        body,
    )
    response_sha = hashlib.sha256(body).hexdigest()
    request = {
        "profile": profile.id,
        "placement": placement,
        "failure_law": law,
        "repetition": repetition,
        "period": period,
        "request_id": request_id,
        "trace_id": trace_id,
        "trace_header": trace_header,
        "scheduled_offset_seconds": offset_seconds,
        "started_at": _format_time(started),
        "completed_at": _format_time(completed),
        "operation": operation,
        "branch_class": branch,
        "status_code": "" if status is None else status,
        "immediate_success": status is not None and 200 <= status < 300,
        "semantic_success": semantic_success,
        "semantic_rule": semantic_rule,
        "semantic_reason": semantic_reason,
        "timed_out": "timeout" in error.lower(),
        "latency_ms": (time.monotonic() - started_monotonic) * 1000.0,
        "response_bytes": len(body),
        "response_sha256": response_sha,
        "error": error,
    }
    response = {
        "request_id": request_id,
        "status_code": status,
        "content_base64": base64.b64encode(body).decode("ascii"),
        "sha256": response_sha,
    }
    return request, response


def _semantic_sentinels(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    law: str,
    repetition: int,
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


def _container_matches_pause(container_id: str, expected: bool) -> bool:
    return _is_paused(container_id) is expected


def _container_matches_network(
    container_id: str,
    network_name: str,
    expected_disconnected: bool,
) -> bool:
    return _has_network(container_id, network_name) is (not expected_disconnected)


def _reconcile_pause_states(
    services: Iterable[str],
    containers: dict[str, str],
    active_causes: dict[str, set[str]],
) -> list[str]:
    errors: list[str] = []
    to_pause: list[str] = []
    to_unpause: list[str] = []
    for service in sorted(set(services)):
        container_id = containers[service]
        desired = bool(active_causes[service])
        try:
            actual = _is_paused(container_id)
        except Exception as error:
            errors.append(f"inspect {service}: {type(error).__name__}: {error}")
            continue
        if desired and not actual:
            to_pause.append(container_id)
        elif not desired and actual:
            to_unpause.append(container_id)
    for action, identifiers in (("pause", to_pause), ("unpause", to_unpause)):
        if not identifiers:
            continue
        completed = _completed(["docker", action, *identifiers])
        if completed.returncode != 0:
            errors.append(completed.stderr.strip() or f"docker {action} failed")
    return errors


def _network_connect_command(
    container_id: str,
    network: tuple[str, tuple[str, ...]],
) -> list[str]:
    network_name, aliases = network
    command = ["docker", "network", "connect"]
    for alias in aliases:
        command.extend(["--alias", alias])
    command.extend([network_name, container_id])
    return command


def _reconcile_network_states(
    services: Iterable[str],
    containers: dict[str, str],
    networks: dict[str, tuple[str, tuple[str, ...]]],
    active_causes: dict[str, set[str]],
) -> list[str]:
    errors: list[str] = []
    for service in sorted(set(services)):
        container_id = containers[service]
        network_name, _ = networks[service]
        desired_disconnected = bool(active_causes[service])
        try:
            connected = _has_network(container_id, network_name)
        except Exception as error:
            errors.append(f"inspect {service}: {type(error).__name__}: {error}")
            continue
        if desired_disconnected and connected:
            completed = _completed(
                ["docker", "network", "disconnect", network_name, container_id]
            )
            if completed.returncode != 0:
                errors.append(
                    completed.stderr.strip() or "docker network disconnect failed"
                )
        elif not desired_disconnected and not connected:
            completed = _completed(
                _network_connect_command(container_id, networks[service])
            )
            if completed.returncode != 0:
                errors.append(
                    completed.stderr.strip() or "docker network connect failed"
                )
    return errors


def _targets_match_effect(
    event: RenewalEvent,
    containers: dict[str, str],
    networks: dict[str, tuple[str, tuple[str, ...]]],
    pause_causes: dict[str, set[str]],
    network_causes: dict[str, set[str]],
) -> bool:
    try:
        if event.effect == "pause":
            return all(
                _container_matches_pause(containers[target], bool(pause_causes[target]))
                for target in event.targets
            )
        return all(
            _container_matches_network(
                containers[target],
                networks[target][0],
                bool(network_causes[target]),
            )
            for target in event.targets
        )
    except Exception:
        return False


def _stochastic_fault_controller(
    profile: PlacementPilotProfile,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    period_started_at: datetime,
    period_started_monotonic: float,
    events: tuple[RenewalEvent, ...],
    containers: dict[str, str],
    networks: dict[str, tuple[str, tuple[str, ...]]],
    output: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    replica_services = tuple(profile.replica_services.values())
    pause_causes = {service: set() for service in replica_services}
    network_causes = {service: set() for service in replica_services}
    records: dict[str, dict[str, Any]] = {}
    transitions: list[tuple[float, int, RenewalEvent]] = []
    for event in events:
        transitions.append((event.offset_seconds, 1, event))
        transitions.append((event.end_seconds, 0, event))
        records[event.event_id] = {
            "profile": profile.id,
            "placement": placement,
            "failure_law": law,
            "repetition": repetition,
            "period": period,
            "event_id": event.event_id,
            "factor_id": event.factor_id,
            "mechanism": event.mechanism,
            "effect": event.effect,
            "domain": event.domain,
            "targets": ";".join(event.targets),
            "target_count": len(event.targets),
            "schedule_seed": event.schedule_seed,
            "intended_offset_seconds": event.offset_seconds,
            "intended_duration_seconds": event.duration_seconds,
            "intended_at": _format_time(
                period_started_at + timedelta(seconds=event.offset_seconds)
            ),
            "applied_at": "",
            "applied_offset_seconds": "",
            "verified_at": "",
            "released_at": "",
            "released_offset_seconds": "",
            "confirmed": False,
            "release_confirmed": False,
            "expected_affected_after_release": "",
            "observation_start_lag_seconds": "",
            "observation_release_lag_seconds": "",
            "error": "",
        }
    transitions.sort(key=lambda item: (item[0], item[1], item[2].event_id))
    controller_errors: list[str] = []

    for offset, transition_kind, event in transitions:
        _sleep_until(period_started_monotonic + offset)
        record = records[event.event_id]
        errors: list[str] = []
        if transition_kind == 1:
            causes = pause_causes if event.effect == "pause" else network_causes
            for target in event.targets:
                causes[target].add(event.event_id)
            if event.effect == "pause":
                errors.extend(
                    _reconcile_pause_states(event.targets, containers, pause_causes)
                )
            else:
                errors.extend(
                    _reconcile_network_states(
                        event.targets,
                        containers,
                        networks,
                        network_causes,
                    )
                )
            applied_at = _utc_now()
            record["applied_at"] = _format_time(applied_at)
            record["applied_offset_seconds"] = (
                time.monotonic() - period_started_monotonic
            )
            record["confirmed"] = _targets_match_effect(
                event,
                containers,
                networks,
                pause_causes,
                network_causes,
            )
            record["verified_at"] = _format_time(_utc_now())
        else:
            causes = pause_causes if event.effect == "pause" else network_causes
            for target in event.targets:
                causes[target].discard(event.event_id)
            if event.effect == "pause":
                errors.extend(
                    _reconcile_pause_states(event.targets, containers, pause_causes)
                )
                remaining = [target for target in event.targets if pause_causes[target]]
            else:
                errors.extend(
                    _reconcile_network_states(
                        event.targets,
                        containers,
                        networks,
                        network_causes,
                    )
                )
                remaining = [
                    target for target in event.targets if network_causes[target]
                ]
            released_at = _utc_now()
            record["released_at"] = _format_time(released_at)
            record["released_offset_seconds"] = (
                time.monotonic() - period_started_monotonic
            )
            record["expected_affected_after_release"] = ";".join(remaining)
            record["release_confirmed"] = _targets_match_effect(
                event,
                containers,
                networks,
                pause_causes,
                network_causes,
            )
        if errors:
            existing = str(record["error"])
            record["error"] = " | ".join([item for item in (existing, *errors) if item])
            controller_errors.extend(errors)

    controller_errors.extend(
        _reconcile_pause_states(replica_services, containers, pause_causes)
    )
    controller_errors.extend(
        _reconcile_network_states(
            replica_services,
            containers,
            networks,
            network_causes,
        )
    )
    output.extend(records[event.event_id] for event in events)
    summary.update(
        {
            "events": len(events),
            "confirmed": sum(bool(row["confirmed"]) for row in records.values()),
            "released": sum(bool(row["release_confirmed"]) for row in records.values()),
            "active_pause_causes_at_end": sum(map(len, pause_causes.values())),
            "active_network_causes_at_end": sum(map(len, network_causes.values())),
            "errors": controller_errors,
        }
    )


def _health_sampler(
    config: StochasticPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    compose_path: Path,
    containers: dict[str, str],
    started_monotonic: float,
    stop: threading.Event,
    output: list[dict[str, Any]],
) -> None:
    assignments = config.placement.placements[placement]
    replicas = profile.replica_services
    replica_by_service = {service: key for key, service in replicas.items()}
    services = (*replicas.values(), profile.target_service)
    identifiers = [containers[service] for service in services]
    while not stop.is_set():
        observed = _utc_now()
        elapsed = time.monotonic() - started_monotonic
        try:
            documents = _inspect_containers(identifiers)
            proxy = _proxy_stats(config.placement, profile, compose_path)
            for service, container_id in zip(services, identifiers, strict=True):
                state = documents[container_id].get("State", {})
                networks = (
                    documents[container_id]
                    .get("NetworkSettings", {})
                    .get("Networks", {})
                )
                replica = replica_by_service.get(service, "")
                backend = proxy.get(replica, {}) if replica else {}
                output.append(
                    {
                        "profile": profile.id,
                        "placement": placement,
                        "failure_law": law,
                        "repetition": repetition,
                        "period": period,
                        "observed_at": _format_time(observed),
                        "elapsed_seconds": elapsed,
                        "service": service,
                        "role": "replica" if replica else "proxy",
                        "replica": replica,
                        "domain": assignments.get(replica, ""),
                        "container_id": container_id,
                        "running": bool(state.get("Running")),
                        "paused": bool(state.get("Paused")),
                        "health": state.get("Health", {}).get("Status", "not_declared"),
                        "network_count": len(networks),
                        "backend_status": backend.get("status", ""),
                        "backend_check_status": backend.get("check_status", ""),
                        "backend_sessions": backend.get("sessions", ""),
                        "error": "",
                    }
                )
        except Exception as error:  # evidence remains explicit and countable
            output.append(
                {
                    "profile": profile.id,
                    "placement": placement,
                    "failure_law": law,
                    "repetition": repetition,
                    "period": period,
                    "observed_at": _format_time(observed),
                    "elapsed_seconds": elapsed,
                    "service": "__sampler__",
                    "role": "auditor",
                    "replica": "",
                    "domain": "",
                    "container_id": "",
                    "running": "",
                    "paused": "",
                    "health": "unknown",
                    "network_count": "",
                    "backend_status": "",
                    "backend_check_status": "",
                    "backend_sessions": "",
                    "error": f"{type(error).__name__}: {error}",
                }
            )
        stop.wait(config.health_poll_seconds)


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
        config.pilot_base_seed,
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
                )
            )
        pairs = [future.result() for future in futures]
    if fault_thread is not None:
        fault_thread.join(timeout=duration_seconds + 30)
        if fault_thread.is_alive():
            raise StochasticPilotError("stochastic fault controller did not terminate")
    stop_health.set()
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


def _health_epoch_rows(
    health: list[dict[str, Any]],
) -> list[tuple[float, dict[str, dict[str, Any]]]]:
    epochs: dict[float, dict[str, dict[str, Any]]] = {}
    for row in health:
        if row["role"] != "replica" or row["error"]:
            continue
        elapsed = float(row["elapsed_seconds"])
        epochs.setdefault(elapsed, {})[str(row["service"])] = row
    return sorted(epochs.items())


def _row_effect_matches(
    row: dict[str, Any],
    effect: str,
    expected_affected: bool,
) -> bool:
    if effect == "pause":
        return bool(row["paused"]) is expected_affected
    disconnected = int(row["network_count"]) == 0
    return disconnected is expected_affected


def _first_matching_health_offset(
    epochs: list[tuple[float, dict[str, dict[str, Any]]]],
    after_seconds: float,
    targets: tuple[str, ...],
    effect: str,
    expected_affected: set[str],
) -> float | None:
    for elapsed, rows in epochs:
        if elapsed < after_seconds or any(target not in rows for target in targets):
            continue
        if all(
            _row_effect_matches(
                rows[target],
                effect,
                target in expected_affected,
            )
            for target in targets
        ):
            return elapsed
    return None


def _annotate_event_observation_lags(
    event_rows: list[dict[str, Any]],
    health: list[dict[str, Any]],
) -> None:
    epochs = _health_epoch_rows(health)
    for row in event_rows:
        targets = tuple(item for item in str(row["targets"]).split(";") if item)
        applied = float(row["applied_offset_seconds"])
        released = float(row["released_offset_seconds"])
        start_observed = _first_matching_health_offset(
            epochs,
            applied,
            targets,
            str(row["effect"]),
            set(targets),
        )
        remaining = {
            item
            for item in str(row["expected_affected_after_release"]).split(";")
            if item
        }
        release_observed = _first_matching_health_offset(
            epochs,
            released,
            targets,
            str(row["effect"]),
            remaining,
        )
        row["observation_start_lag_seconds"] = (
            "" if start_observed is None else max(0.0, start_observed - applied)
        )
        row["observation_release_lag_seconds"] = (
            "" if release_observed is None else max(0.0, release_observed - released)
        )


def _second_binned_request_series(
    requests: list[dict[str, Any]], duration_seconds: int
) -> list[float]:
    bins: dict[int, list[float]] = {index: [] for index in range(duration_seconds)}
    for row in requests:
        second = min(
            duration_seconds - 1,
            max(0, int(float(row["scheduled_offset_seconds"]))),
        )
        bins[second].append(float(bool(row["semantic_success"])))
    return [statistics.fmean(bins[index]) if bins[index] else 0.0 for index in bins]


def _health_impairment_series(
    health: list[dict[str, Any]], duration_seconds: int
) -> list[float]:
    bins: dict[int, list[float]] = {index: [] for index in range(duration_seconds)}
    for elapsed, rows in _health_epoch_rows(health):
        second = min(duration_seconds - 1, max(0, int(elapsed)))
        values = []
        for row in rows.values():
            backend_up = str(row["backend_status"]).startswith("UP")
            impaired = (
                bool(row["paused"]) or int(row["network_count"]) == 0 or not backend_up
            )
            values.append(float(impaired))
        if values:
            bins[second].append(statistics.fmean(values))
    series: list[float] = []
    previous = 0.0
    for second in range(duration_seconds):
        if bins[second]:
            previous = statistics.fmean(bins[second])
        series.append(previous)
    return series


def _period_summary(
    config: StochasticPilotConfig,
    profile_id: str,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    duration_seconds: int,
    requests: list[dict[str, Any]],
    events: list[dict[str, Any]],
    health: list[dict[str, Any]],
) -> dict[str, Any]:
    semantic_successes = sum(bool(row["semantic_success"]) for row in requests)
    request_block = autocorrelation_block_length(
        _second_binned_request_series(requests, duration_seconds),
        config.design_selection.acf_absolute_threshold,
        config.design_selection.acf_consecutive_lags,
        config.design_selection.acf_max_lag_seconds,
    )
    health_block = autocorrelation_block_length(
        _health_impairment_series(health, duration_seconds),
        config.design_selection.acf_absolute_threshold,
        config.design_selection.acf_consecutive_lags,
        config.design_selection.acf_max_lag_seconds,
    )
    block = max(request_block, health_block)
    return {
        "profile": profile_id,
        "placement": placement,
        "failure_law": law,
        "repetition": repetition,
        "period": period,
        "duration_seconds": duration_seconds,
        "requests": len(requests),
        "semantic_successes": semantic_successes,
        "semantic_success_fraction": (
            semantic_successes / len(requests) if requests else 0.0
        ),
        "request_block_seconds": request_block,
        "health_block_seconds": health_block,
        "block_length_seconds": block,
        "effective_blocks": duration_seconds / block,
        "events": len(events),
        "confirmed_events": sum(bool(row["confirmed"]) for row in events),
        "released_events": sum(bool(row["release_confirmed"]) for row in events),
    }


def _factor_yields(
    profile_id: str,
    placement: str,
    law: str,
    repetition: int,
    period: str,
    factors: tuple[FactorDefinition, ...],
    event_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for factor in factors:
        selected = [row for row in event_rows if row["factor_id"] == factor.factor_id]
        rows.append(
            {
                "profile": profile_id,
                "placement": placement,
                "failure_law": law,
                "repetition": repetition,
                "period": period,
                "factor_id": factor.factor_id,
                "mechanism": factor.mechanism,
                "targets": ";".join(factor.targets),
                "events": len(selected),
                "confirmed_events": sum(bool(row["confirmed"]) for row in selected),
                "released_events": sum(
                    bool(row["release_confirmed"]) for row in selected
                ),
                "intended_down_seconds": sum(
                    float(row["intended_duration_seconds"]) for row in selected
                ),
            }
        )
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _trace_join_rows(
    requests: list[dict[str, Any]], raw_path: Path
) -> list[dict[str, Any]]:
    raw = raw_path.read_text(encoding="utf-8", errors="replace").lower()
    rows = []
    for request in requests:
        trace_id = str(request["trace_id"]).lower()
        occurrences = raw.count(trace_id)
        rows.append(
            {
                "profile": request["profile"],
                "placement": request["placement"],
                "failure_law": request["failure_law"],
                "repetition": request["repetition"],
                "period": request["period"],
                "request_id": request["request_id"],
                "trace_id": trace_id,
                "request_success": request["semantic_success"],
                "trace_present": occurrences > 0,
                "raw_occurrences": occurrences,
            }
        )
    return rows


def run_stochastic_freeze_pilot(
    config: StochasticPilotConfig,
    profile_id: str,
    placement: str,
    law: str,
    repetition: int,
    checkout_directory: str | Path,
    compose_path: str | Path,
    image_audit_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise StochasticPilotError(
            "stochastic freeze pilot may run only in GitHub Actions"
        )
    if repetition < 0 or repetition >= config.pilot_repetitions:
        raise StochasticPilotError(
            f"repetition must lie in [0, {config.pilot_repetitions - 1}]"
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
        )
        for period in ("calibration", "test")
    }
    schedule_document = {
        "schema_version": 1,
        "pilot_only": True,
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
        "unobserved_event_transitions": sum(
            row["observation_start_lag_seconds"] == ""
            or row["observation_release_lag_seconds"] == ""
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
        "kind": "stochastic_schedule_and_budget_freeze_pilot",
        "experiment_id": config.id,
        "pilot_only": True,
        "usable_for_m7_freeze": not any(quality.values()),
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
                if row["observation_start_lag_seconds"] != ""
            ],
            "release": [
                float(row["observation_release_lag_seconds"])
                for row in all_events
                if row["observation_release_lag_seconds"] != ""
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
    (output / "pilot-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise StochasticPilotError(f"M7C cell acceptance failures: {failures}")
    return manifest


def _quantile_higher(values: Iterable[float], probability: float) -> float:
    array = np.asarray(tuple(values), dtype=float)
    if not array.size:
        return 0.0
    return float(np.quantile(array, probability, method="higher"))


def _duration_recommendation(
    config: StochasticPilotConfig,
    manifests: list[dict[str, Any]],
) -> dict[str, Any]:
    pilot_blocks = [
        int(manifest["period_summaries"][period]["block_length_seconds"])
        for manifest in manifests
        for period in ("calibration", "test")
    ]
    block_p90 = max(1, int(_quantile_higher(pilot_blocks, 0.90)))
    maximum_repetitions = max(config.design_selection.candidate_main_repetitions)
    candidates = []
    for duration in config.design_selection.candidate_period_seconds:
        counts: list[int] = []
        strata: dict[str, list[int]] = {}
        for profile in config.placement.profiles:
            for placement in config.placement.placements:
                for law in config.laws:
                    for repetition in range(maximum_repetitions):
                        for period in ("calibration", "test"):
                            events = plan_renewal_events(
                                config,
                                profile,
                                placement,
                                law,
                                repetition,
                                period,
                                duration_seconds=duration,
                                base_seed=config.main_base_seed,
                            )
                            by_factor = {
                                factor.factor_id: sum(
                                    event.factor_id == factor.factor_id
                                    for event in events
                                )
                                for factor in factor_definitions(
                                    config, profile, placement, law
                                )
                            }
                            for factor_id, count in by_factor.items():
                                counts.append(count)
                                key = f"{profile.id}:{placement}:{law}:{factor_id}"
                                strata.setdefault(key, []).append(count)
        fraction = sum(
            count >= config.design_selection.minimum_events_per_factor_period
            for count in counts
        ) / len(counts)
        stratum_p10 = {
            key: _quantile_higher(values, 0.10)
            for key, values in sorted(strata.items())
        }
        worst_stratum_p10 = min(stratum_p10.values())
        effective_blocks = duration / block_p90
        passed = (
            fraction >= config.design_selection.minimum_schedule_fraction
            and worst_stratum_p10
            >= config.design_selection.minimum_events_per_factor_period
            and effective_blocks
            >= config.design_selection.minimum_effective_blocks_per_period
        )
        candidates.append(
            {
                "period_seconds": duration,
                "factor_periods": len(counts),
                "fraction_meeting_event_minimum": fraction,
                "minimum_event_count": min(counts),
                "p10_event_count": _quantile_higher(counts, 0.10),
                "worst_stratum_p10_event_count": worst_stratum_p10,
                "pilot_block_p90_seconds": block_p90,
                "projected_effective_blocks": effective_blocks,
                "passed": passed,
            }
        )
    selected = next((row for row in candidates if row["passed"]), None)
    return {
        "selection_status": "selected" if selected is not None else "no_candidate_met",
        "selected_period_seconds": (
            None if selected is None else selected["period_seconds"]
        ),
        "event_minimum": config.design_selection.minimum_events_per_factor_period,
        "schedule_fraction_requirement": (
            config.design_selection.minimum_schedule_fraction
        ),
        "effective_block_requirement": (
            config.design_selection.minimum_effective_blocks_per_period
        ),
        "pilot_block_p90_seconds": block_p90,
        "candidates": candidates,
        "selection_inputs": (
            "pre-generated main event schedules and the pilot p90 dependence "
            "block; no method error or placement-effect contrast"
        ),
        "main_schedule_seed": config.main_base_seed,
    }


def _repetition_recommendation(
    config: StochasticPilotConfig,
    manifests: list[dict[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[float]] = {}
    for manifest in manifests:
        key = f"{manifest['profile']}:{manifest['placement']}:{manifest['failure_law']}"
        calibration = float(
            manifest["period_summaries"]["calibration"]["semantic_success_fraction"]
        )
        test = float(manifest["period_summaries"]["test"]["semantic_success_fraction"])
        grouped.setdefault(key, []).append(test - calibration)

    cell_rows = []
    alpha = 1.0 - config.design_selection.sd_upper_confidence_level
    for key, values in sorted(grouped.items()):
        if len(values) < 2:
            standard_deviation = 0.0
            upper = math.inf
        else:
            standard_deviation = statistics.stdev(values)
            degrees = len(values) - 1
            lower_chi = float(chi2.ppf(alpha, degrees))
            upper = (
                standard_deviation * math.sqrt(degrees / lower_chi)
                if standard_deviation > 0
                else 0.0
            )
        planning_sd = max(config.design_selection.planning_sd_floor, upper)
        cell_rows.append(
            {
                "cell": key,
                "pilot_pairs": len(values),
                "paired_deltas": values,
                "sample_sd": standard_deviation,
                "one_sided_upper_sd": upper,
                "planning_sd": planning_sd,
            }
        )
    worst_planning_sd = max(row["planning_sd"] for row in cell_rows)
    confidence = config.design_selection.paired_confidence_level
    candidates = []
    for repetitions in config.design_selection.candidate_main_repetitions:
        critical = float(t.ppf(0.5 + confidence / 2.0, repetitions - 1))
        half_width = critical * worst_planning_sd / math.sqrt(repetitions)
        candidates.append(
            {
                "repetitions": repetitions,
                "worst_projected_half_width": half_width,
                "passed": (
                    half_width <= config.design_selection.target_paired_half_width
                ),
            }
        )
    selected = next((row for row in candidates if row["passed"]), None)
    return {
        "selection_status": "selected" if selected is not None else "no_candidate_met",
        "selected_repetitions": (None if selected is None else selected["repetitions"]),
        "planning_quantity": (
            "calibration-to-test semantic endpoint-rate difference; this is a "
            "resource proxy, not the future full-method-minus-B2 contrast"
        ),
        "target_half_width": config.design_selection.target_paired_half_width,
        "confidence_level": confidence,
        "sd_upper_confidence_level": (
            config.design_selection.sd_upper_confidence_level
        ),
        "planning_sd_floor": config.design_selection.planning_sd_floor,
        "worst_planning_sd": worst_planning_sd,
        "cells": cell_rows,
        "candidates": candidates,
    }


def _transition_guard_recommendation(
    config: StochasticPilotConfig,
    manifests: list[dict[str, Any]],
) -> dict[str, Any]:
    values = [
        float(value)
        for manifest in manifests
        for kind in ("start", "release")
        for value in manifest["transition_lags_seconds"][kind]
    ]
    quantile = _quantile_higher(values, config.design_selection.transition_lag_quantile)
    selected = next(
        (
            candidate
            for candidate in config.design_selection.transition_guard_candidates_seconds
            if candidate >= quantile
        ),
        None,
    )
    return {
        "selection_status": "selected" if selected is not None else "no_candidate_met",
        "selected_guard_seconds_each_side": selected,
        "lag_quantile_probability": config.design_selection.transition_lag_quantile,
        "lag_quantile_seconds": quantile,
        "maximum_observed_lag_seconds": max(values) if values else None,
        "observed_transitions": len(values),
        "candidates_seconds": list(
            config.design_selection.transition_guard_candidates_seconds
        ),
    }


def _freeze_recommendation(
    config: StochasticPilotConfig,
    manifests: list[dict[str, Any]],
) -> dict[str, Any]:
    duration = _duration_recommendation(config, manifests)
    repetitions = _repetition_recommendation(config, manifests)
    transition = _transition_guard_recommendation(config, manifests)
    selected = {
        "period_seconds": duration["selected_period_seconds"],
        "repetitions": repetitions["selected_repetitions"],
        "transition_guard_seconds_each_side": transition[
            "selected_guard_seconds_each_side"
        ],
        "request_rate_per_second": config.request_rate_per_second,
        "main_base_seed": config.main_base_seed,
        "laws": config.laws,
        "placements": config.placement.placements,
        "renewal_processes": {
            name: asdict(process) for name, process in config.renewal_processes.items()
        },
    }
    freeze_ready = all(
        item["selection_status"] == "selected"
        for item in (duration, repetitions, transition)
    )
    canonical = json.dumps(selected, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": 1,
        "kind": "m7_stochastic_design_recommendation",
        "pilot_only": True,
        "freeze_ready": freeze_ready,
        "duration": duration,
        "repetitions": repetitions,
        "transition_guard": transition,
        "selected_design": selected,
        "selected_design_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "inference_boundary": (
            "M7C selects engineering duration and repetition budget only; its "
            "requests cannot enter M7 estimation or effectiveness comparisons"
        ),
    }


def aggregate_stochastic_freeze_pilots(
    config: StochasticPilotConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    paths = sorted(root.rglob("pilot-manifest.json"))
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    expected = {
        (profile.id, placement, law, repetition)
        for profile in config.placement.profiles
        for placement in config.placement.placements
        for law in config.laws
        for repetition in range(config.pilot_repetitions)
    }
    observed = [
        (
            str(manifest.get("profile", "")),
            str(manifest.get("placement", "")),
            str(manifest.get("failure_law", "")),
            int(manifest.get("repetition", -1)),
        )
        for manifest in manifests
    ]
    observed_set = set(observed)
    quality_names = sorted(
        {name for manifest in manifests for name in manifest.get("quality", {})}
    )
    quality = {
        name: sum(int(manifest["quality"].get(name, 0)) for manifest in manifests)
        for name in quality_names
    }
    request_ids: list[str] = []
    trace_ids: list[str] = []
    for path in root.rglob("trace-join.csv"):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                request_ids.append(str(row["request_id"]))
                trace_ids.append(str(row["trace_id"]))
    quality.update(
        {
            "missing_cells": len(expected - observed_set),
            "unexpected_cells": len(observed_set - expected),
            "duplicate_cells": len(observed) - len(observed_set),
            "unusable_cells": sum(
                not bool(manifest.get("usable_for_m7_freeze")) for manifest in manifests
            ),
            "non_pilot_cells": sum(
                manifest.get("pilot_only") is not True for manifest in manifests
            ),
            "cross_cell_duplicate_request_ids": len(request_ids)
            - len(set(request_ids)),
            "cross_cell_duplicate_trace_ids": len(trace_ids) - len(set(trace_ids)),
        }
    )

    cell_rows = []
    period_rows = []
    factor_rows = []
    for manifest in manifests:
        counts = manifest["counts"]
        summaries = manifest["period_summaries"]
        cell_rows.append(
            {
                "profile": manifest["profile"],
                "placement": manifest["placement"],
                "failure_law": manifest["failure_law"],
                "repetition": manifest["repetition"],
                "requests": counts["requests"],
                "semantic_successes": counts["semantic_successes"],
                "baseline_success_fraction": summaries["baseline"][
                    "semantic_success_fraction"
                ],
                "calibration_success_fraction": summaries["calibration"][
                    "semantic_success_fraction"
                ],
                "test_success_fraction": summaries["test"]["semantic_success_fraction"],
                "paired_endpoint_delta": (
                    summaries["test"]["semantic_success_fraction"]
                    - summaries["calibration"]["semantic_success_fraction"]
                ),
                "calibration_block_seconds": summaries["calibration"][
                    "block_length_seconds"
                ],
                "test_block_seconds": summaries["test"]["block_length_seconds"],
                "events": counts["events"],
                "confirmed_events": counts["confirmed_events"],
                "released_events": counts["released_events"],
                "trace_rows": counts["trace_rows"],
                "trace_rows_present": counts["trace_rows_present"],
                "linked_success_fraction": manifest["linked_success_fraction"],
                "health_samples": counts["health_samples"],
                "route_sessions_a": manifest["routing_audit"]["session_deltas"]["a"],
                "route_sessions_b": manifest["routing_audit"]["session_deltas"]["b"],
                "usable": manifest["usable_for_m7_freeze"],
                "pilot_only": manifest["pilot_only"],
            }
        )
        period_rows.extend(summaries.values())
        factor_rows.extend(manifest["factor_yields"])
    cell_rows.sort(
        key=lambda row: (
            row["profile"],
            row["placement"],
            row["failure_law"],
            row["repetition"],
        )
    )
    period_rows.sort(
        key=lambda row: (
            row["profile"],
            row["placement"],
            row["failure_law"],
            row["repetition"],
            row["period"],
        )
    )
    factor_rows.sort(
        key=lambda row: (
            row["profile"],
            row["placement"],
            row["failure_law"],
            row["repetition"],
            row["period"],
            row["factor_id"],
        )
    )

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "cells.csv", CELL_SUMMARY_FIELDS, cell_rows)
    _write_csv(output / "periods.csv", PERIOD_SUMMARY_FIELDS, period_rows)
    _write_csv(output / "factor-yields.csv", FACTOR_YIELD_FIELDS, factor_rows)

    technical_failures = {name: value for name, value in quality.items() if value}
    recommendation = (
        _freeze_recommendation(config, manifests)
        if not technical_failures and len(manifests) == len(expected)
        else {
            "schema_version": 1,
            "kind": "m7_stochastic_design_recommendation",
            "pilot_only": True,
            "freeze_ready": False,
            "reason": "technical pilot matrix is incomplete or unusable",
        }
    )
    (output / "recommendation.json").write_text(
        json.dumps(recommendation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    quality["design_selection_failures"] = int(
        not bool(recommendation.get("freeze_ready"))
    )
    aggregate = {
        "schema_version": 1,
        "kind": "stochastic_schedule_and_budget_freeze_pilot_aggregate",
        "experiment_id": config.id,
        "pilot_only": True,
        "source_cells": len(manifests),
        "expected_cells": len(expected),
        "quality": quality,
        "row_counts": {
            "cells": len(cell_rows),
            "periods": len(period_rows),
            "factor_yields": len(factor_rows),
            "trace_join_rows": len(request_ids),
        },
        "recommendation": recommendation,
        "source_manifest_sha256": {
            f"{profile}:{placement}:{law}:r{repetition}": file_sha256(path)
            for (profile, placement, law, repetition), path in zip(
                observed, paths, strict=True
            )
        },
        "files": {
            "cells_sha256": file_sha256(output / "cells.csv"),
            "periods_sha256": file_sha256(output / "periods.csv"),
            "factor_yields_sha256": file_sha256(output / "factor-yields.csv"),
            "recommendation_sha256": file_sha256(output / "recommendation.json"),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise StochasticPilotError(f"M7C aggregate acceptance failures: {failures}")
    return aggregate
