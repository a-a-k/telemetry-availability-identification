from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .live_fault_config import (
    LiveFaultConfig,
    LiveFaultProfile,
    select_live_fault_profile,
)
from .live_pilot import (
    _collect_telemetry,
    _deathstar_request,
    _git_head,
    _otel_request,
    _runtime_containers,
    initialize_profile,
    wait_for_frontend,
)
from .live_pilot_config import RuntimePilotProfile, select_runtime_pilot_profile
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class LiveFaultError(RuntimeError):
    """Raised when remote fault-acquisition evidence violates its contract."""


REQUEST_FIELDS = (
    "profile",
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
    "success",
    "latency_ms",
    "error",
)

INJECTION_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "period",
    "event_id",
    "mechanism",
    "targets",
    "intended_offset_seconds",
    "intended_at",
    "applied_at",
    "verified_at",
    "restored_at",
    "confirmed",
    "restored",
    "error",
)

HEALTH_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "period",
    "observed_at",
    "service",
    "container_id",
    "running",
    "paused",
    "health",
    "error",
)

TRACE_JOIN_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "period",
    "request_id",
    "trace_id",
    "request_success",
    "trace_present",
    "raw_occurrences",
)

AGGREGATE_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "requests",
    "successful_requests",
    "failed_requests",
    "success_fraction",
    "successful_requests_with_trace",
    "linked_success_fraction",
    "native_trace_count",
    "injections",
    "confirmed_injections",
    "restored_injections",
    "health_samples",
    "usable",
    "diagnostic_only",
)


@dataclass(frozen=True)
class FaultEventPlan:
    event_id: str
    mechanism: str
    offset_seconds: float
    duration_seconds: float
    targets: tuple[str, ...]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _seed(config: LiveFaultConfig, *parts: object) -> int:
    material = "|".join([str(config.base_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")


def make_trace_context(profile_id: str, request_id: str) -> tuple[str, str, str]:
    digest = hashlib.sha256(f"{profile_id}|{request_id}".encode("utf-8")).hexdigest()
    span_id = digest[32:48]
    if profile_id == "deathstarbench_social_network":
        trace_id = digest[:16]
        value = f"{trace_id}:{span_id}:0:1"
        return trace_id, "uber-trace-id", value
    if profile_id == "opentelemetry_demo":
        trace_id = digest[:32]
        value = f"00-{trace_id}-{span_id}-01"
        return trace_id, "traceparent", value
    raise LiveFaultError(f"no trace-context format for profile {profile_id!r}")


def plan_fault_events(
    config: LiveFaultConfig,
    profile: LiveFaultProfile,
    law: str,
    seed: int,
    period: str,
) -> tuple[FaultEventPlan, ...]:
    if law not in config.laws:
        raise LiveFaultError(f"unknown failure law {law!r}")
    mechanisms = list(config.laws[law])
    random.Random(seed).shuffle(mechanisms)
    rng = random.Random(seed ^ 0xA71F5EED)
    plans: list[FaultEventPlan] = []
    index = 0
    while True:
        nominal = config.first_fault_offset_seconds + index * config.fault_gap_seconds
        offset = nominal + rng.uniform(
            -config.fault_jitter_seconds,
            config.fault_jitter_seconds,
        )
        if offset + config.fault_duration_seconds >= config.period_seconds:
            break
        mechanism = mechanisms[index % len(mechanisms)]
        if mechanism == "individual":
            targets = (profile.individual_service,)
        elif mechanism == "communication":
            targets = (profile.communication_service,)
        else:
            targets = profile.common_domain_services
        plans.append(
            FaultEventPlan(
                event_id=f"{period}-{index:02d}",
                mechanism=mechanism,
                offset_seconds=offset,
                duration_seconds=float(config.fault_duration_seconds),
                targets=targets,
            )
        )
        index += 1
    missing = set(config.laws[law]) - {plan.mechanism for plan in plans}
    if missing:
        raise LiveFaultError(
            f"period is too short to exercise all mechanisms for {law}: {sorted(missing)}"
        )
    return tuple(plans)


def _completed(
    arguments: list[str],
    *,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        capture_output=True,
        text=True,
        check=check,
    )


def _service_containers(
    compose_path: Path,
    services: tuple[str, ...],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for service in services:
        completed = _completed(
            ["docker", "compose", "-f", str(compose_path), "ps", "-q", service]
        )
        identifiers = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if completed.returncode != 0 or len(identifiers) != 1:
            raise LiveFaultError(
                f"expected exactly one running container for service {service!r}: "
                f"returncode={completed.returncode}, ids={identifiers}, "
                f"stderr={completed.stderr[:200]}"
            )
        result[service] = identifiers[0]
    return result


def _inspect_containers(container_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not container_ids:
        return {}
    completed = _completed(["docker", "inspect", *container_ids])
    if completed.returncode != 0:
        raise LiveFaultError(f"docker inspect failed: {completed.stderr[:300]}")
    documents = json.loads(completed.stdout)
    if len(documents) != len(container_ids):
        raise LiveFaultError(
            f"docker inspect returned {len(documents)} records for "
            f"{len(container_ids)} containers"
        )
    return dict(zip(container_ids, documents, strict=True))


def _network_record(container_id: str) -> tuple[str, tuple[str, ...]]:
    document = _inspect_containers([container_id])[container_id]
    networks = document.get("NetworkSettings", {}).get("Networks", {})
    if not isinstance(networks, dict) or len(networks) != 1:
        raise LiveFaultError(
            f"communication target must start on exactly one network: {sorted(networks)}"
        )
    name, values = next(iter(networks.items()))
    aliases = tuple(
        sorted(
            {
                str(alias)
                for alias in (values.get("Aliases") or [])
                if alias
            }
        )
    )
    return str(name), aliases


def _is_paused(container_id: str) -> bool:
    document = _inspect_containers([container_id])[container_id]
    return bool(document.get("State", {}).get("Paused"))


def _has_network(container_id: str, network_name: str) -> bool:
    document = _inspect_containers([container_id])[container_id]
    networks = document.get("NetworkSettings", {}).get("Networks", {})
    return network_name in networks


def _sleep_until(deadline: float) -> None:
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 0.25))


def _fault_controller(
    config: LiveFaultConfig,
    profile: LiveFaultProfile,
    law: str,
    repetition: int,
    period: str,
    period_started_at: datetime,
    period_started_monotonic: float,
    plans: tuple[FaultEventPlan, ...],
    containers: dict[str, str],
    network: tuple[str, tuple[str, ...]],
    output: list[dict[str, Any]],
) -> None:
    for plan in plans:
        _sleep_until(period_started_monotonic + plan.offset_seconds)
        intended_at = period_started_at + timedelta(seconds=plan.offset_seconds)
        applied_at: datetime | None = None
        verified_at: datetime | None = None
        restored_at: datetime | None = None
        confirmed = False
        restored = False
        errors: list[str] = []
        paused: list[str] = []
        disconnected = False
        try:
            if plan.mechanism in {"individual", "common_domain"}:
                target_ids = [containers[target] for target in plan.targets]
                completed = _completed(["docker", "pause", *target_ids])
                applied_at = _utc_now()
                if completed.returncode != 0:
                    raise LiveFaultError(completed.stderr.strip() or "docker pause failed")
                paused = target_ids
                confirmed = all(_is_paused(container_id) for container_id in target_ids)
                verified_at = _utc_now()
            elif plan.mechanism == "communication":
                container_id = containers[plan.targets[0]]
                network_name, _ = network
                completed = _completed(
                    ["docker", "network", "disconnect", network_name, container_id]
                )
                applied_at = _utc_now()
                if completed.returncode != 0:
                    raise LiveFaultError(
                        completed.stderr.strip() or "docker network disconnect failed"
                    )
                disconnected = True
                confirmed = not _has_network(container_id, network_name)
                verified_at = _utc_now()
            else:
                raise LiveFaultError(f"unsupported mechanism {plan.mechanism!r}")
            time.sleep(plan.duration_seconds)
        except Exception as error:  # retained as diagnostic evidence
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            if paused:
                completed = _completed(["docker", "unpause", *paused])
                if completed.returncode != 0:
                    errors.append(completed.stderr.strip() or "docker unpause failed")
                try:
                    restored = all(not _is_paused(container_id) for container_id in paused)
                except Exception as error:
                    errors.append(f"restore verification: {type(error).__name__}: {error}")
            elif disconnected:
                container_id = containers[plan.targets[0]]
                network_name, aliases = network
                command = ["docker", "network", "connect"]
                for alias in aliases:
                    command.extend(["--alias", alias])
                command.extend([network_name, container_id])
                completed = _completed(command)
                if completed.returncode != 0:
                    errors.append(completed.stderr.strip() or "docker network connect failed")
                try:
                    restored = _has_network(container_id, network_name)
                except Exception as error:
                    errors.append(f"restore verification: {type(error).__name__}: {error}")
            restored_at = _utc_now()
        output.append(
            {
                "profile": profile.id,
                "failure_law": law,
                "repetition": repetition,
                "period": period,
                "event_id": plan.event_id,
                "mechanism": plan.mechanism,
                "targets": ";".join(plan.targets),
                "intended_offset_seconds": plan.offset_seconds,
                "intended_at": _format_time(intended_at),
                "applied_at": "" if applied_at is None else _format_time(applied_at),
                "verified_at": "" if verified_at is None else _format_time(verified_at),
                "restored_at": "" if restored_at is None else _format_time(restored_at),
                "confirmed": confirmed,
                "restored": restored,
                "error": " | ".join(errors),
            }
        )


def _health_sampler(
    config: LiveFaultConfig,
    profile: LiveFaultProfile,
    law: str,
    repetition: int,
    period: str,
    containers: dict[str, str],
    stop: threading.Event,
    output: list[dict[str, Any]],
) -> None:
    services = tuple(profile.health_services)
    ids = [containers[service] for service in services]
    while not stop.is_set():
        observed = _utc_now()
        try:
            documents = _inspect_containers(ids)
            for service, container_id in zip(services, ids, strict=True):
                state = documents[container_id].get("State", {})
                output.append(
                    {
                        "profile": profile.id,
                        "failure_law": law,
                        "repetition": repetition,
                        "period": period,
                        "observed_at": _format_time(observed),
                        "service": service,
                        "container_id": container_id,
                        "running": bool(state.get("Running")),
                        "paused": bool(state.get("Paused")),
                        "health": state.get("Health", {}).get("Status", "not_declared"),
                        "error": "",
                    }
                )
        except Exception as error:
            for service, container_id in zip(services, ids, strict=True):
                output.append(
                    {
                        "profile": profile.id,
                        "failure_law": law,
                        "repetition": repetition,
                        "period": period,
                        "observed_at": _format_time(observed),
                        "service": service,
                        "container_id": container_id,
                        "running": "",
                        "paused": "",
                        "health": "unknown",
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
        stop.wait(config.health_poll_seconds)


def _request_row(
    config: LiveFaultConfig,
    runtime_profile: RuntimePilotProfile,
    law: str,
    repetition: int,
    period: str,
    index: int,
    operation: str,
    offset_seconds: float,
) -> dict[str, Any]:
    request_id = f"{runtime_profile.id}-{law}-r{repetition}-{period}-{index:04d}"
    trace_id, header_name, header_value = make_trace_context(
        runtime_profile.id,
        request_id,
    )
    started = _utc_now()
    try:
        if runtime_profile.id == "deathstarbench_social_network":
            status, _, error, branch = _deathstar_request(
                runtime_profile,
                operation,
                index,
                extra_headers={header_name: header_value},
                timeout=float(config.request_timeout_seconds),
            )
        elif runtime_profile.id == "opentelemetry_demo":
            status, _, error, branch = _otel_request(
                runtime_profile,
                operation,
                f"{law}-r{repetition}-{period}",
                index,
                extra_headers={header_name: header_value},
                timeout=float(config.request_timeout_seconds),
            )
        else:
            raise LiveFaultError(f"no workload driver for {runtime_profile.id!r}")
    except Exception as request_error:
        status = None
        branch = "driver_error"
        error = f"{type(request_error).__name__}: {request_error}"
    completed = _utc_now()
    return {
        "profile": runtime_profile.id,
        "failure_law": law,
        "repetition": repetition,
        "period": period,
        "request_id": request_id,
        "trace_id": trace_id,
        "trace_header": header_name,
        "scheduled_offset_seconds": offset_seconds,
        "started_at": _format_time(started),
        "completed_at": _format_time(completed),
        "operation": operation,
        "branch_class": branch,
        "status_code": status,
        "success": status is not None and 200 <= status < 300,
        "latency_ms": (completed - started).total_seconds() * 1000,
        "error": error,
    }


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


def _run_period(
    config: LiveFaultConfig,
    profile: LiveFaultProfile,
    runtime_profile: RuntimePilotProfile,
    law: str,
    repetition: int,
    period: str,
    workload_seed: int,
    fault_seed: int,
    compose_path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    containers = _service_containers(compose_path, profile.health_services)
    network = _network_record(containers[profile.communication_service])
    plans = plan_fault_events(config, profile, law, fault_seed, period)
    request_count = config.requests_per_period
    operations = _operation_order(runtime_profile, request_count, workload_seed)

    requests: list[dict[str, Any]] = []
    injections: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []
    stop_health = threading.Event()
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    health_thread = threading.Thread(
        target=_health_sampler,
        args=(
            config,
            profile,
            law,
            repetition,
            period,
            containers,
            stop_health,
            health,
        ),
        name=f"health-{profile.id}-{law}-{period}",
    )
    fault_thread = threading.Thread(
        target=_fault_controller,
        args=(
            config,
            profile,
            law,
            repetition,
            period,
            started_at,
            started_monotonic,
            plans,
            containers,
            network,
            injections,
        ),
        name=f"fault-{profile.id}-{law}-{period}",
    )
    health_thread.start()
    fault_thread.start()
    futures: list[Future[dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=config.request_workers) as executor:
        for index, operation in enumerate(operations):
            offset = index / config.request_rate_per_second
            _sleep_until(started_monotonic + offset)
            futures.append(
                executor.submit(
                    _request_row,
                    config,
                    runtime_profile,
                    law,
                    repetition,
                    period,
                    index,
                    operation,
                    offset,
                )
            )
        requests = [future.result() for future in futures]
    fault_thread.join(timeout=config.period_seconds + config.fault_duration_seconds + 10)
    if fault_thread.is_alive():
        raise LiveFaultError("fault controller did not finish within the period bound")
    stop_health.set()
    health_thread.join(timeout=5)
    if health_thread.is_alive():
        raise LiveFaultError("health sampler did not stop")
    completed_at = _utc_now()
    requests.sort(key=lambda row: row["request_id"])
    injections.sort(key=lambda row: row["event_id"])
    health.sort(key=lambda row: (row["observed_at"], row["service"]))
    metadata = {
        "started_at": _format_time(started_at),
        "completed_at": _format_time(completed_at),
        "workload_seed": workload_seed,
        "fault_seed": fault_seed,
        "planned_requests": request_count,
        "planned_events": len(plans),
        "planned_mechanisms": [plan.mechanism for plan in plans],
    }
    return requests, injections, health, metadata


def _trace_join_rows(
    profile: LiveFaultProfile,
    law: str,
    repetition: int,
    requests: list[dict[str, Any]],
    raw_path: Path,
) -> list[dict[str, Any]]:
    raw = raw_path.read_text(encoding="utf-8", errors="replace").lower()
    rows = []
    for request in requests:
        trace_id = str(request["trace_id"]).lower()
        occurrences = raw.count(trace_id)
        rows.append(
            {
                "profile": profile.id,
                "failure_law": law,
                "repetition": repetition,
                "period": request["period"],
                "request_id": request["request_id"],
                "trace_id": trace_id,
                "request_success": request["success"],
                "trace_present": occurrences > 0,
                "raw_occurrences": occurrences,
            }
        )
    return rows


def run_live_fault_diagnostic(
    config: LiveFaultConfig,
    profile_id: str,
    law: str,
    repetition: int,
    checkout_directory: str | Path,
    compose_path: str | Path,
    image_audit_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise LiveFaultError("live fault diagnostics may run only in GitHub Actions")
    if repetition < 0 or repetition >= config.repetitions:
        raise LiveFaultError(
            f"repetition must lie in [0, {config.repetitions - 1}]"
        )
    if law not in config.laws:
        raise LiveFaultError(f"unknown failure law {law!r}")
    profile = select_live_fault_profile(config, profile_id)
    runtime_profile = select_runtime_pilot_profile(config.runtime, profile_id)
    checkout = Path(checkout_directory)
    compose = Path(compose_path)
    image_audit_file = Path(image_audit_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    campaign_started = _utc_now()
    observed_commit = _git_head(checkout)
    wait_for_frontend(runtime_profile, config.runtime.readiness_timeout_seconds)
    time.sleep(config.runtime.post_start_stabilization_seconds)
    initialize_profile(runtime_profile)

    all_requests: list[dict[str, Any]] = []
    all_injections: list[dict[str, Any]] = []
    all_health: list[dict[str, Any]] = []
    periods: dict[str, Any] = {}
    for period in ("calibration", "test"):
        workload_seed = _seed(
            config,
            profile.id,
            law,
            repetition,
            period,
            "workload",
        )
        fault_seed = _seed(
            config,
            profile.id,
            law,
            repetition,
            period,
            "fault",
        )
        requests, injections, health, metadata = _run_period(
            config,
            profile,
            runtime_profile,
            law,
            repetition,
            period,
            workload_seed,
            fault_seed,
            compose,
        )
        periods[period] = metadata
        all_requests.extend(requests)
        all_injections.extend(injections)
        all_health.extend(health)
        if period == "calibration":
            time.sleep(config.inter_period_gap_seconds)

    _write_csv(output / "requests.csv", REQUEST_FIELDS, all_requests)
    _write_csv(output / "injections.csv", INJECTION_FIELDS, all_injections)
    _write_csv(output / "health.csv", HEALTH_FIELDS, all_health)
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
    join_rows = _trace_join_rows(
        profile,
        law,
        repetition,
        all_requests,
        raw_path,
    )
    _write_csv(output / "trace-join.csv", TRACE_JOIN_FIELDS, join_rows)
    containers, unlocked_running = _runtime_containers(compose, output)
    image_audit = json.loads(image_audit_file.read_text(encoding="utf-8"))

    expected_requests = 2 * config.requests_per_period
    request_ids = [str(row["request_id"]) for row in all_requests]
    trace_ids = [str(row["trace_id"]) for row in all_requests]
    operation_cells = {
        (str(row["period"]), str(row["operation"])) for row in all_requests
    }
    expected_operation_cells = {
        (period, operation)
        for period in ("calibration", "test")
        for operation in runtime_profile.operations
    }
    successful = sum(bool(row["success"]) for row in all_requests)
    linked_success = sum(
        bool(row["request_success"]) and bool(row["trace_present"])
        for row in join_rows
    )
    linked_success_fraction = linked_success / successful if successful else 0.0
    expected_events = sum(int(periods[period]["planned_events"]) for period in periods)
    health_counts = {
        (period, service): sum(
            row["period"] == period and row["service"] == service
            for row in all_health
        )
        for period in ("calibration", "test")
        for service in profile.health_services
    }
    quality = {
        "checkout_commit_mismatches": int(observed_commit != runtime_profile.commit),
        "request_count_mismatches": int(len(all_requests) != expected_requests),
        "duplicate_request_ids": len(request_ids) - len(set(request_ids)),
        "duplicate_trace_ids": len(trace_ids) - len(set(trace_ids)),
        "operation_cell_mismatches": len(
            expected_operation_cells.symmetric_difference(operation_cells)
        ),
        "period_seed_collisions": int(
            periods["calibration"]["workload_seed"]
            == periods["test"]["workload_seed"]
            or periods["calibration"]["fault_seed"]
            == periods["test"]["fault_seed"]
        ),
        "injection_count_mismatches": int(len(all_injections) != expected_events),
        "unconfirmed_injections": sum(
            not bool(row["confirmed"]) for row in all_injections
        ),
        "unrestored_injections": sum(
            not bool(row["restored"]) for row in all_injections
        ),
        "health_service_periods_below_minimum": sum(
            count < config.minimum_health_samples_per_service_period
            for count in health_counts.values()
        ),
        "health_sampling_errors": sum(bool(row["error"]) for row in all_health),
        "linked_success_fraction_below_minimum": int(
            linked_success_fraction < config.minimum_linked_success_fraction
        ),
        "telemetry_collection_errors": int(bool(telemetry_error)),
        "unlocked_rendered_services": int(
            not image_audit.get("all_services_locked", False)
        ),
        "unlocked_running_images": unlocked_running,
        "running_container_count_mismatches": int(
            len(containers) != int(image_audit.get("service_count", 0))
        ),
    }
    manifest = {
        "schema_version": 1,
        "kind": "fault_and_trace_linkage_diagnostic",
        "experiment_id": config.id,
        "diagnostic_only": True,
        "usable_for_m7_design": not any(quality.values()),
        "profile": profile.id,
        "failure_law": law,
        "repetition": repetition,
        "expected_checkout_commit": runtime_profile.commit,
        "observed_checkout_commit": observed_commit,
        "periods": periods,
        "counts": {
            "requests": len(all_requests),
            "successful_requests": successful,
            "failed_requests": len(all_requests) - successful,
            "successful_requests_with_trace": linked_success,
            "native_trace_count": native_trace_count,
            "injections": len(all_injections),
            "confirmed_injections": sum(
                bool(row["confirmed"]) for row in all_injections
            ),
            "restored_injections": sum(
                bool(row["restored"]) for row in all_injections
            ),
            "health_samples": len(all_health),
            "running_containers": len(containers),
            "locked_services": int(image_audit.get("service_count", 0)),
        },
        "success_fraction": successful / len(all_requests) if all_requests else 0.0,
        "linked_success_fraction": linked_success_fraction,
        "health_samples_by_service_period": {
            f"{period}:{service}": count
            for (period, service), count in sorted(health_counts.items())
        },
        "telemetry_kind": runtime_profile.telemetry_kind,
        "telemetry_error": telemetry_error,
        "quality": quality,
        "files": {
            "requests_sha256": file_sha256(output / "requests.csv"),
            "injections_sha256": file_sha256(output / "injections.csv"),
            "health_sha256": file_sha256(output / "health.csv"),
            "trace_join_sha256": file_sha256(output / "trace-join.csv"),
            "raw_telemetry_sha256": file_sha256(raw_path),
            "image_audit_sha256": file_sha256(image_audit_file),
            "runtime_containers_sha256": file_sha256(
                output / "runtime-containers.json"
            ),
        },
        "environment": environment_manifest(),
    }
    (output / "campaign_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise LiveFaultError(f"live fault diagnostic acceptance failures: {failures}")
    return manifest


def aggregate_live_fault_diagnostics(
    config: LiveFaultConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    paths = sorted(Path(input_root).rglob("campaign_manifest.json"))
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    expected = {
        (profile.id, law, repetition)
        for profile in config.profiles
        for law in config.laws
        for repetition in range(config.repetitions)
    }
    observed = [
        (
            str(manifest.get("profile", "")),
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
    quality.update(
        {
            "missing_cells": len(expected - observed_set),
            "unexpected_cells": len(observed_set - expected),
            "duplicate_cells": len(observed) - len(observed_set),
            "unusable_cells": sum(
                not bool(manifest.get("usable_for_m7_design")) for manifest in manifests
            ),
            "non_diagnostic_cells": sum(
                manifest.get("diagnostic_only") is not True for manifest in manifests
            ),
        }
    )
    rows = []
    for manifest in manifests:
        counts = manifest["counts"]
        rows.append(
            {
                "profile": manifest["profile"],
                "failure_law": manifest["failure_law"],
                "repetition": manifest["repetition"],
                "requests": counts["requests"],
                "successful_requests": counts["successful_requests"],
                "failed_requests": counts["failed_requests"],
                "success_fraction": manifest["success_fraction"],
                "successful_requests_with_trace": counts[
                    "successful_requests_with_trace"
                ],
                "linked_success_fraction": manifest["linked_success_fraction"],
                "native_trace_count": counts["native_trace_count"],
                "injections": counts["injections"],
                "confirmed_injections": counts["confirmed_injections"],
                "restored_injections": counts["restored_injections"],
                "health_samples": counts["health_samples"],
                "usable": manifest["usable_for_m7_design"],
                "diagnostic_only": manifest["diagnostic_only"],
            }
        )
    rows.sort(key=lambda row: (row["profile"], row["failure_law"], row["repetition"]))
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "summary.csv", AGGREGATE_FIELDS, rows)
    aggregate = {
        "schema_version": 1,
        "kind": "fault_and_trace_linkage_diagnostic_aggregate",
        "experiment_id": config.id,
        "diagnostic_only": True,
        "source_cells": len(manifests),
        "expected_cells": len(expected),
        "quality": quality,
        "row_counts": {"summary": len(rows)},
        "source_manifest_sha256": {
            (
                f"{manifest['profile']}:{manifest['failure_law']}:"
                f"r{manifest['repetition']}"
            ): file_sha256(path)
            for manifest, path in zip(manifests, paths, strict=True)
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise LiveFaultError(f"live fault diagnostic aggregate failures: {failures}")
    return aggregate
