from __future__ import annotations

import base64
import copy
import csv
import hashlib
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
    PlacementPilotConfig,
    PlacementPilotEvent,
    PlacementPilotProfile,
    select_placement_pilot_profile,
)
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class PlacementPilotError(RuntimeError):
    """Raised when replicated-placement pilot evidence violates its contract."""


REQUEST_FIELDS = (
    "profile",
    "placement",
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

INJECTION_FIELDS = (
    "profile",
    "placement",
    "period",
    "event_id",
    "mechanism",
    "domain",
    "targets",
    "target_count",
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
    "placement",
    "period",
    "observed_at",
    "service",
    "role",
    "replica",
    "domain",
    "container_id",
    "running",
    "paused",
    "health",
    "network_count",
    "error",
)

TRACE_JOIN_FIELDS = (
    "profile",
    "placement",
    "period",
    "request_id",
    "trace_id",
    "request_success",
    "trace_present",
    "raw_occurrences",
)

SUMMARY_FIELDS = (
    "profile",
    "placement",
    "requests",
    "immediate_successes",
    "semantic_successes",
    "fault_period_successes",
    "linked_success_fraction",
    "native_trace_count",
    "routing_replica_a_sessions",
    "routing_replica_b_sessions",
    "injections",
    "confirmed_injections",
    "restored_injections",
    "health_samples",
    "usable",
    "pilot_only",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_seed(config: PlacementPilotConfig, *parts: object) -> int:
    material = "|".join([str(config.base_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")


def _haproxy_configuration(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
) -> str:
    replicas = profile.replica_services
    if profile.proxy_mode == "grpc_h2":
        bind_suffix = " proto h2"
        mode = "http"
        server_suffix = " check proto h2"
        log_option = "  option httplog\n"
    else:
        bind_suffix = ""
        mode = "tcp"
        server_suffix = " check"
        log_option = "  option tcplog\n"
    return (
        "global\n"
        "  log stdout format raw local0\n"
        "\n"
        "defaults\n"
        "  log global\n"
        "  timeout connect 1s\n"
        "  timeout client 15s\n"
        "  timeout server 15s\n"
        "\n"
        "frontend study_frontend\n"
        f"  bind *:{profile.target_port}{bind_suffix}\n"
        f"  mode {mode}\n"
        f"{log_option}"
        "  default_backend study_replicas\n"
        "\n"
        "backend study_replicas\n"
        f"  mode {mode}\n"
        "  balance roundrobin\n"
        "  default-server inter 500ms fall 1 rise 1\n"
        f"  server replica_a {replicas['a']}:{profile.target_port}{server_suffix}\n"
        f"  server replica_b {replicas['b']}:{profile.target_port}{server_suffix}\n"
        "\n"
        "listen study_stats\n"
        f"  bind *:{config.proxy_stats_port}\n"
        "  mode http\n"
        "  stats enable\n"
        "  stats uri /stats\n"
        "  stats show-legends\n"
        "  stats refresh 1s\n"
    )


def _labels(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, list):
        result: dict[str, str] = {}
        for item in value:
            key, _, content = str(item).partition("=")
            result[key] = content
        return result
    raise PlacementPilotError("Compose service labels must be a mapping or list")


def _annotate_environment(
    service: dict[str, Any],
    replica: str,
    domain: str,
) -> None:
    environment = service.get("environment")
    if not isinstance(environment, dict):
        return
    current = str(environment.get("OTEL_RESOURCE_ATTRIBUTES", "")).strip()
    additions = f"study.replica={replica},study.domain={domain}"
    environment["OTEL_RESOURCE_ATTRIBUTES"] = (
        f"{current},{additions}" if current else additions
    )


def prepare_placement_compose(
    config: PlacementPilotConfig,
    profile_id: str,
    placement: str,
    input_compose_path: str | Path,
    base_audit_path: str | Path,
    output_compose_path: str | Path,
    output_audit_path: str | Path,
    haproxy_config_path: str | Path,
) -> dict[str, Any]:
    if placement not in config.placements:
        raise PlacementPilotError(
            f"unknown placement {placement!r}; expected {sorted(config.placements)}"
        )
    profile = select_placement_pilot_profile(config, profile_id)
    document = json.loads(Path(input_compose_path).read_text(encoding="utf-8"))
    document = copy.deepcopy(document)
    services = document.get("services")
    if not isinstance(services, dict):
        raise PlacementPilotError("pinned Compose has no services mapping")
    original = services.get(profile.target_service)
    if not isinstance(original, dict):
        raise PlacementPilotError(
            f"pinned Compose lacks target service {profile.target_service!r}"
        )
    original_image = str(original.get("image", ""))
    if "@sha256:" not in original_image:
        raise PlacementPilotError("target service image is not digest locked")

    assignments = config.placements[placement]
    replica_services = profile.replica_services
    for replica, service_name in replica_services.items():
        clone = copy.deepcopy(original)
        clone.pop("container_name", None)
        clone.pop("ports", None)
        clone["hostname"] = service_name
        labels = _labels(clone.get("labels"))
        labels.update(
            {
                "study.role": "replica",
                "study.replica": replica,
                "study.domain": assignments[replica],
                "study.placement": placement,
            }
        )
        clone["labels"] = labels
        _annotate_environment(clone, replica, assignments[replica])
        services[service_name] = clone

    haproxy_path = Path(haproxy_config_path).resolve()
    haproxy_path.parent.mkdir(parents=True, exist_ok=True)
    haproxy_text = _haproxy_configuration(config, profile)
    haproxy_path.write_text(haproxy_text, encoding="utf-8")
    target_networks = copy.deepcopy(original.get("networks", {"default": None}))
    services[profile.target_service] = {
        "image": config.proxy_locked_image,
        "hostname": profile.target_service,
        "restart": "unless-stopped",
        "depends_on": {
            service_name: {"condition": "service_started", "required": True}
            for service_name in replica_services.values()
        },
        "networks": target_networks,
        "volumes": [
            {
                "type": "bind",
                "source": str(haproxy_path),
                "target": "/usr/local/etc/haproxy/haproxy.cfg",
                "read_only": True,
                "bind": {"create_host_path": False},
            }
        ],
        "healthcheck": {
            "test": [
                "CMD-SHELL",
                f"nc -z 127.0.0.1 {profile.target_port} && "
                f"nc -z 127.0.0.1 {config.proxy_stats_port}",
            ],
            "interval": "1s",
            "timeout": "1s",
            "retries": 30,
            "start_period": "1s",
        },
        "labels": {
            "study.role": "proxy",
            "study.placement": placement,
        },
    }

    base_audit = json.loads(Path(base_audit_path).read_text(encoding="utf-8"))
    image_rows = base_audit.get("images")
    if not isinstance(image_rows, list):
        raise PlacementPilotError("base image audit has no images list")
    original_rows = [
        row for row in image_rows if row.get("service") == profile.target_service
    ]
    if len(original_rows) != 1:
        raise PlacementPilotError("base audit must contain target service exactly once")
    original_row = original_rows[0]
    revised_rows = [
        copy.deepcopy(row)
        for row in image_rows
        if row.get("service") != profile.target_service
    ]
    for replica, service_name in replica_services.items():
        row = copy.deepcopy(original_row)
        row["service"] = service_name
        row["study_replica"] = replica
        row["study_domain"] = assignments[replica]
        revised_rows.append(row)
    revised_rows.append(
        {
            "service": profile.target_service,
            "rendered_image": config.proxy_image,
            "locked_image": config.proxy_locked_image,
            "manifest_digest": config.proxy_manifest_digest,
            "study_role": "proxy",
        }
    )
    audit = copy.deepcopy(base_audit)
    audit.update(
        {
            "schema_version": 2,
            "service_count": len(revised_rows),
            "all_services_locked": all(
                "@sha256:" in str(row.get("locked_image", "")) for row in revised_rows
            ),
            "images": sorted(revised_rows, key=lambda row: str(row["service"])),
            "placement_pilot": {
                "pilot_only": True,
                "profile": profile.id,
                "placement": placement,
                "target_service": profile.target_service,
                "target_port": profile.target_port,
                "proxy_mode": profile.proxy_mode,
                "proxy_service": profile.target_service,
                "proxy_image": config.proxy_locked_image,
                "replica_services": replica_services,
                "domain_assignments": assignments,
                "haproxy_config_sha256": hashlib.sha256(
                    haproxy_text.encode("utf-8")
                ).hexdigest(),
            },
        }
    )
    if not audit["all_services_locked"]:
        raise PlacementPilotError("placement extension produced an unlocked service")

    output_compose = Path(output_compose_path)
    output_compose.parent.mkdir(parents=True, exist_ok=True)
    output_compose.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_audit = Path(output_audit_path)
    output_audit.parent.mkdir(parents=True, exist_ok=True)
    output_audit.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def validate_operation_response(
    profile_id: str,
    operation: str,
    status: int | None,
    body: bytes,
) -> tuple[bool, str, str]:
    if status is None or not 200 <= status < 300:
        return False, "http_2xx_and_operation_shape", "http_not_2xx"
    if profile_id == "deathstarbench_social_network":
        if operation == "compose_post":
            valid = b"Successfully upload post" in body
            return (
                valid,
                "http_2xx_and_compose_acknowledgement",
                "" if valid else "missing_compose_acknowledgement",
            )
        if operation in {"read_home_timeline", "read_user_timeline"}:
            try:
                value = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False, "http_2xx_and_timeline_json", "invalid_json"
            valid_posts = isinstance(value, list) and all(
                isinstance(item, dict)
                and isinstance(item.get("post_id"), str)
                and isinstance(item.get("text"), str)
                for item in value
            )
            # The pinned DeathStarBench Lua endpoint builds timelines with an
            # initially empty Lua table. lua-cjson serializes that ambiguous
            # empty table as {}, while every non-empty timeline is an array.
            # Accept only the exact empty object as the upstream empty value;
            # arbitrary objects remain malformed responses.
            valid = valid_posts or value == {}
            return (
                valid,
                "http_2xx_and_timeline_json",
                "" if valid else "invalid_timeline",
            )
    elif profile_id == "opentelemetry_demo":
        try:
            value = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False, "http_2xx_and_expected_json", "invalid_json"
        if operation == "browse_product":
            valid = isinstance(value, dict) and value.get("id") == "OLJCESPC7Z"
            return (
                valid,
                "http_2xx_and_expected_product",
                "" if valid else "wrong_product",
            )
        if operation == "add_to_cart":
            items = value.get("items") if isinstance(value, dict) else None
            valid = False
            if isinstance(items, list):
                for item in items:
                    if (
                        not isinstance(item, dict)
                        or item.get("productId") != "OLJCESPC7Z"
                    ):
                        continue
                    try:
                        valid = int(item.get("quantity", 0)) >= 1
                    except (TypeError, ValueError):
                        valid = False
                    if valid:
                        break
            return (
                valid,
                "http_2xx_and_cart_contains_item",
                "" if valid else "missing_cart_item",
            )
        if operation == "checkout":
            valid = (
                isinstance(value, dict)
                and isinstance(value.get("orderId"), str)
                and bool(value.get("orderId"))
                and isinstance(value.get("shippingTrackingId"), str)
                and bool(value.get("shippingTrackingId"))
            )
            return (
                valid,
                "http_2xx_and_order_identifiers",
                "" if valid else "missing_order_ids",
            )
    raise PlacementPilotError(
        f"no semantic response rule for {profile_id!r}/{operation!r}"
    )


def _execute_named_request(
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    period: str,
    operation: str,
    index: int,
    timeout: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    request_id = f"{profile.id}-{placement}-{period}-{index:06d}"
    trace_id, trace_header, trace_value = make_trace_context(profile.id, request_id)
    started = _utc_now()
    monotonic_started = time.monotonic()
    if profile.id == "deathstarbench_social_network":
        status, body, error, branch = _deathstar_request(
            runtime_profile,
            operation,
            index,
            extra_headers={trace_header: trace_value},
            timeout=timeout,
        )
    elif profile.id == "opentelemetry_demo":
        status, body, error, branch = _otel_request(
            runtime_profile,
            operation,
            f"m7b-{placement}-{period}",
            index,
            extra_headers={trace_header: trace_value},
            timeout=timeout,
        )
    else:
        raise PlacementPilotError(f"no workload driver for {profile.id!r}")
    completed = _utc_now()
    semantic_success, semantic_rule, semantic_reason = validate_operation_response(
        profile.id,
        operation,
        status,
        body,
    )
    row = {
        "profile": profile.id,
        "placement": placement,
        "period": period,
        "request_id": request_id,
        "trace_id": trace_id,
        "trace_header": trace_header,
        "scheduled_offset_seconds": 0.0,
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
        "latency_ms": (time.monotonic() - monotonic_started) * 1000.0,
        "response_bytes": len(body),
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "error": error,
    }
    response = {
        "request_id": request_id,
        "status_code": status,
        "content_base64": base64.b64encode(body).decode("ascii"),
        "sha256": row["response_sha256"],
    }
    return row, response


def _timeline_has_text(body: bytes, expected: str) -> bool:
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(value, list) and any(
        isinstance(item, dict) and item.get("text") == expected for item in value
    )


def _semantic_sentinels(
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    for offset, operation in enumerate(runtime_profile.operations):
        row, response = _execute_named_request(
            profile,
            runtime_profile,
            placement,
            "sentinel",
            operation,
            90000 + offset,
            timeout,
        )
        requests.append(row)
        responses.append(response)

    if profile.id != "deathstarbench_social_network":
        return (
            requests,
            responses,
            {
                "kind": "synchronous_response_semantics",
                "applicable": False,
                "passed": True,
                "reason": "the pilot freezes immediate OTel response semantics only",
            },
        )

    expected_text = "taid pilot post 90000"
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
                and _timeline_has_text(
                    body,
                    expected_text,
                )
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


def _proxy_container_ip(compose_path: Path, proxy_service: str) -> str:
    container_id = _service_containers(compose_path, (proxy_service,))[proxy_service]
    document = _inspect_containers([container_id])[container_id]
    networks = document.get("NetworkSettings", {}).get("Networks", {})
    addresses = [
        str(values.get("IPAddress", ""))
        for values in networks.values()
        if values.get("IPAddress")
    ]
    if len(addresses) != 1:
        raise PlacementPilotError(
            f"proxy must expose exactly one bridge address, observed {addresses}"
        )
    return addresses[0]


def _proxy_stats(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    compose_path: Path,
) -> dict[str, dict[str, Any]]:
    address = _proxy_container_ip(compose_path, profile.target_service)
    url = f"http://{address}:{config.proxy_stats_port}/stats;csv"
    last_error = "not attempted"
    for _ in range(20):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                raw = response.read().decode("utf-8", errors="replace")
            reader = csv.DictReader(raw.splitlines())
            result: dict[str, dict[str, Any]] = {}
            for row in reader:
                server = str(row.get("svname", ""))
                if server not in {"replica_a", "replica_b"}:
                    continue
                result[server[-1]] = {
                    "sessions": int(row.get("stot") or 0),
                    "current_sessions": int(row.get("scur") or 0),
                    "status": str(row.get("status", "")),
                    "check_status": str(row.get("check_status", "")),
                }
            if set(result) == {"a", "b"}:
                return result
            last_error = f"missing backend rows: {sorted(result)}"
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = f"{type(error).__name__}: {error}"
        time.sleep(0.5)
    raise PlacementPilotError(f"HAProxy stats did not become readable: {last_error}")


def _routing_probe(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    compose_path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    before = _proxy_stats(config, profile, compose_path)
    with ThreadPoolExecutor(max_workers=config.routing_probe_workers) as executor:
        futures = [
            executor.submit(
                _execute_named_request,
                profile,
                runtime_profile,
                placement,
                "routing_probe",
                profile.routing_probe_operation,
                100000 + index,
                float(config.request_timeout_seconds),
            )
            for index in range(config.routing_probe_requests)
        ]
        pairs = [future.result() for future in futures]
    time.sleep(0.5)
    after = _proxy_stats(config, profile, compose_path)
    deltas = {
        replica: after[replica]["sessions"] - before[replica]["sessions"]
        for replica in ("a", "b")
    }
    requests = [pair[0] for pair in pairs]
    responses = [pair[1] for pair in pairs]
    semantic_successes = sum(bool(row["semantic_success"]) for row in requests)
    return (
        requests,
        responses,
        {
            "operation": profile.routing_probe_operation,
            "requests": len(requests),
            "semantic_successes": semantic_successes,
            "semantic_success_fraction": semantic_successes / len(requests),
            "before": before,
            "after": after,
            "session_deltas": deltas,
        },
    )


def _event_targets(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    event: PlacementPilotEvent,
) -> tuple[str, ...]:
    replicas = profile.replica_services
    if event.mechanism == "individual_a":
        return (replicas["a"],)
    if event.mechanism == "individual_b":
        return (replicas["b"],)
    if event.mechanism == "common_domain":
        return tuple(
            replicas[replica]
            for replica in ("a", "b")
            if config.placements[placement][replica] == "domain_a"
        )
    if event.mechanism == "communication":
        return (profile.target_service,)
    raise PlacementPilotError(f"unsupported placement event {event.mechanism!r}")


def _placement_fault_controller(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    period_started_at: datetime,
    period_started_monotonic: float,
    containers: dict[str, str],
    network: tuple[str, tuple[str, ...]],
    output: list[dict[str, Any]],
) -> None:
    for event in config.events:
        _sleep_until(period_started_monotonic + event.offset_seconds)
        targets = _event_targets(config, profile, placement, event)
        intended_at = period_started_at + timedelta(seconds=event.offset_seconds)
        applied_at: datetime | None = None
        verified_at: datetime | None = None
        restored_at: datetime | None = None
        confirmed = False
        restored = False
        errors: list[str] = []
        paused: list[str] = []
        disconnected = False
        try:
            if event.mechanism in {"individual_a", "individual_b", "common_domain"}:
                target_ids = [containers[target] for target in targets]
                completed = _completed(["docker", "pause", *target_ids])
                applied_at = _utc_now()
                if completed.returncode != 0:
                    raise PlacementPilotError(
                        completed.stderr.strip() or "docker pause failed"
                    )
                paused = target_ids
                confirmed = all(_is_paused(container_id) for container_id in target_ids)
                verified_at = _utc_now()
            elif event.mechanism == "communication":
                container_id = containers[profile.target_service]
                network_name, _ = network
                completed = _completed(
                    ["docker", "network", "disconnect", network_name, container_id]
                )
                applied_at = _utc_now()
                if completed.returncode != 0:
                    raise PlacementPilotError(
                        completed.stderr.strip() or "docker network disconnect failed"
                    )
                disconnected = True
                confirmed = not _has_network(container_id, network_name)
                verified_at = _utc_now()
        except Exception as error:  # retained as diagnostic evidence
            errors.append(f"{type(error).__name__}: {error}")
        try:
            time.sleep(config.fault_duration_seconds)
        finally:
            if paused:
                completed = _completed(["docker", "unpause", *paused])
                if completed.returncode != 0:
                    errors.append(completed.stderr.strip() or "docker unpause failed")
                try:
                    restored = all(
                        not _is_paused(container_id) for container_id in paused
                    )
                except Exception as error:
                    errors.append(
                        f"restore verification: {type(error).__name__}: {error}"
                    )
            elif disconnected:
                container_id = containers[profile.target_service]
                network_name, aliases = network
                command = ["docker", "network", "connect"]
                for alias in aliases:
                    command.extend(["--alias", alias])
                command.extend([network_name, container_id])
                completed = _completed(command)
                if completed.returncode != 0:
                    errors.append(
                        completed.stderr.strip() or "docker network connect failed"
                    )
                try:
                    restored = _has_network(container_id, network_name)
                except Exception as error:
                    errors.append(
                        f"restore verification: {type(error).__name__}: {error}"
                    )
            restored_at = _utc_now()
        output.append(
            {
                "profile": profile.id,
                "placement": placement,
                "period": "fault",
                "event_id": event.id,
                "mechanism": event.mechanism,
                "domain": "domain_a" if event.mechanism == "common_domain" else "",
                "targets": ";".join(targets),
                "target_count": len(targets),
                "intended_offset_seconds": event.offset_seconds,
                "intended_at": _format_time(intended_at),
                "applied_at": "" if applied_at is None else _format_time(applied_at),
                "verified_at": "" if verified_at is None else _format_time(verified_at),
                "restored_at": "" if restored_at is None else _format_time(restored_at),
                "confirmed": confirmed,
                "restored": restored,
                "error": " | ".join(errors),
            }
        )


def _placement_health_sampler(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    containers: dict[str, str],
    stop: threading.Event,
    output: list[dict[str, Any]],
) -> None:
    assignments = config.placements[placement]
    replica_by_service = {
        service: replica for replica, service in profile.replica_services.items()
    }
    services = (*profile.replica_services.values(), profile.target_service)
    ids = [containers[service] for service in services]
    while not stop.is_set():
        observed = _utc_now()
        try:
            documents = _inspect_containers(ids)
            for service, container_id in zip(services, ids, strict=True):
                state = documents[container_id].get("State", {})
                replica = replica_by_service.get(service, "")
                networks = (
                    documents[container_id]
                    .get("NetworkSettings", {})
                    .get("Networks", {})
                )
                output.append(
                    {
                        "profile": profile.id,
                        "placement": placement,
                        "period": "fault",
                        "observed_at": _format_time(observed),
                        "service": service,
                        "role": "replica" if replica else "proxy",
                        "replica": replica,
                        "domain": assignments.get(replica, ""),
                        "container_id": container_id,
                        "running": bool(state.get("Running")),
                        "paused": bool(state.get("Paused")),
                        "health": state.get("Health", {}).get("Status", "not_declared"),
                        "network_count": len(networks),
                        "error": "",
                    }
                )
        except Exception as error:  # retained as diagnostic evidence
            output.append(
                {
                    "profile": profile.id,
                    "placement": placement,
                    "period": "fault",
                    "observed_at": _format_time(observed),
                    "service": "__sampler__",
                    "role": "auditor",
                    "replica": "",
                    "domain": "",
                    "container_id": "",
                    "running": False,
                    "paused": False,
                    "health": "error",
                    "network_count": 0,
                    "error": f"{type(error).__name__}: {error}",
                }
            )
        stop.wait(config.health_poll_seconds)


def _fault_period(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    runtime_profile: RuntimePilotProfile,
    placement: str,
    compose_path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    services = (*profile.replica_services.values(), profile.target_service)
    containers = _service_containers(compose_path, services)
    network = _network_record(containers[profile.target_service])
    operations = [
        runtime_profile.operations[index % len(runtime_profile.operations)]
        for index in range(config.requests_per_fault_period)
    ]
    random.Random(
        _stable_seed(config, profile.id, placement, "fault-workload")
    ).shuffle(operations)
    requests: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    injections: list[dict[str, Any]] = []
    health: list[dict[str, Any]] = []
    stop_health = threading.Event()
    started_at = _utc_now()
    started_monotonic = time.monotonic()
    health_thread = threading.Thread(
        target=_placement_health_sampler,
        args=(config, profile, placement, containers, stop_health, health),
        daemon=True,
    )
    fault_thread = threading.Thread(
        target=_placement_fault_controller,
        args=(
            config,
            profile,
            placement,
            started_at,
            started_monotonic,
            containers,
            network,
            injections,
        ),
        daemon=True,
    )
    health_thread.start()
    fault_thread.start()
    with ThreadPoolExecutor(max_workers=config.request_workers) as executor:
        futures = []
        for index, operation in enumerate(operations):
            scheduled = index / config.request_rate_per_second
            _sleep_until(started_monotonic + scheduled)
            futures.append(
                executor.submit(
                    _execute_named_request,
                    profile,
                    runtime_profile,
                    placement,
                    "fault",
                    operation,
                    index,
                    float(config.request_timeout_seconds),
                )
            )
        pairs = [future.result() for future in futures]
    fault_thread.join(timeout=config.fault_period_seconds + 10)
    if fault_thread.is_alive():
        raise PlacementPilotError("placement fault controller did not terminate")
    stop_health.set()
    health_thread.join(timeout=5)
    if health_thread.is_alive():
        raise PlacementPilotError("placement health sampler did not terminate")
    for index, pair in enumerate(pairs):
        row, response = pair
        row["scheduled_offset_seconds"] = index / config.request_rate_per_second
        requests.append(row)
        responses.append(response)
    requests.sort(key=lambda row: row["request_id"])
    responses.sort(key=lambda row: row["request_id"])
    injections.sort(key=lambda row: row["event_id"])
    health.sort(key=lambda row: (row["observed_at"], row["service"]))
    return (
        requests,
        responses,
        injections,
        health,
        {
            "started_at": _format_time(started_at),
            "completed_at": _format_time(_utc_now()),
            "workload_seed": _stable_seed(
                config, profile.id, placement, "fault-workload"
            ),
            "planned_requests": config.requests_per_fault_period,
            "planned_operations": {
                operation: operations.count(operation)
                for operation in runtime_profile.operations
            },
            "planned_events": len(config.events),
        },
    )


def _trace_join(
    profile: PlacementPilotProfile,
    placement: str,
    requests: list[dict[str, Any]],
    raw_path: Path,
) -> list[dict[str, Any]]:
    raw = raw_path.read_text(encoding="utf-8", errors="replace").lower()
    rows: list[dict[str, Any]] = []
    for request in requests:
        trace_id = str(request["trace_id"]).lower()
        occurrences = raw.count(trace_id)
        rows.append(
            {
                "profile": profile.id,
                "placement": placement,
                "period": request["period"],
                "request_id": request["request_id"],
                "trace_id": trace_id,
                "request_success": request["semantic_success"],
                "trace_present": occurrences > 0,
                "raw_occurrences": occurrences,
            }
        )
    return rows


def _final_state(
    config: PlacementPilotConfig,
    profile: PlacementPilotProfile,
    placement: str,
    compose_path: Path,
) -> dict[str, Any]:
    services = (*profile.replica_services.values(), profile.target_service)
    containers = _service_containers(compose_path, services)
    documents = _inspect_containers(list(containers.values()))
    states = {}
    for service in services:
        document = documents[containers[service]]
        state = document.get("State", {})
        networks = document.get("NetworkSettings", {}).get("Networks", {})
        states[service] = {
            "running": bool(state.get("Running")),
            "paused": bool(state.get("Paused")),
            "health": state.get("Health", {}).get("Status", "not_declared"),
            "network_count": len(networks),
        }
    stats = _proxy_stats(config, profile, compose_path)
    clean = all(
        values["running"] and not values["paused"] and values["network_count"] == 1
        for values in states.values()
    ) and all(str(stats[replica]["status"]).startswith("UP") for replica in ("a", "b"))
    return {
        "placement": placement,
        "services": states,
        "proxy_backends": stats,
        "clean": clean,
    }


def run_placement_pilot(
    config: PlacementPilotConfig,
    profile_id: str,
    placement: str,
    checkout_directory: str | Path,
    compose_path: str | Path,
    image_audit_path: str | Path,
    haproxy_config_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise PlacementPilotError("placement pilot may run only in GitHub Actions")
    if placement not in config.placements:
        raise PlacementPilotError(
            f"unknown placement {placement!r}; expected {sorted(config.placements)}"
        )
    profile = select_placement_pilot_profile(config, profile_id)
    runtime_profile = select_runtime_pilot_profile(config.runtime, profile_id)
    checkout = Path(checkout_directory)
    compose = Path(compose_path)
    image_audit_file = Path(image_audit_path)
    haproxy_file = Path(haproxy_config_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    campaign_started = _utc_now()
    observed_commit = _git_head(checkout)
    wait_for_frontend(runtime_profile, config.runtime.readiness_timeout_seconds)
    time.sleep(config.runtime.post_start_stabilization_seconds)
    initialize_profile(runtime_profile)

    sentinel_requests, sentinel_responses, effect_audit = _semantic_sentinels(
        profile,
        runtime_profile,
        placement,
        float(config.request_timeout_seconds),
    )
    routing_requests, routing_responses, routing_audit = _routing_probe(
        config,
        profile,
        runtime_profile,
        placement,
        compose,
    )
    (
        fault_requests,
        fault_responses,
        injections,
        health,
        fault_metadata,
    ) = _fault_period(
        config,
        profile,
        runtime_profile,
        placement,
        compose,
    )
    time.sleep(config.recovery_seconds)
    final_state = _final_state(config, profile, placement, compose)

    requests = sentinel_requests + routing_requests + fault_requests
    responses = sentinel_responses + routing_responses + fault_responses
    requests.sort(key=lambda row: (row["period"], row["request_id"]))
    responses.sort(key=lambda row: row["request_id"])
    _write_csv(output / "requests.csv", REQUEST_FIELDS, requests)
    _write_csv(output / "injections.csv", INJECTION_FIELDS, injections)
    _write_csv(output / "health.csv", HEALTH_FIELDS, health)
    (output / "responses.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in responses),
        encoding="utf-8",
    )
    (output / "semantic-effect-audit.json").write_text(
        json.dumps(effect_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "routing-audit.json").write_text(
        json.dumps(routing_audit, indent=2, sort_keys=True) + "\n",
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
    join_rows = _trace_join(profile, placement, requests, raw_path)
    _write_csv(output / "trace-join.csv", TRACE_JOIN_FIELDS, join_rows)
    containers, unlocked_running = _runtime_containers(compose, output)
    image_audit = json.loads(image_audit_file.read_text(encoding="utf-8"))

    request_ids = [str(row["request_id"]) for row in requests]
    trace_ids = [str(row["trace_id"]) for row in requests]
    expected_requests = (
        len(runtime_profile.operations)
        + config.routing_probe_requests
        + config.requests_per_fault_period
    )
    semantic_successes = sum(bool(row["semantic_success"]) for row in requests)
    linked_successes = sum(
        bool(row["request_success"]) and bool(row["trace_present"]) for row in join_rows
    )
    linked_fraction = (
        linked_successes / semantic_successes if semantic_successes else 0.0
    )
    health_services = (*profile.replica_services.values(), profile.target_service)
    health_counts = {
        service: sum(row["service"] == service for row in health)
        for service in health_services
    }
    expected_targets = {
        event.id: _event_targets(config, profile, placement, event)
        for event in config.events
    }
    observed_targets = {
        str(row["event_id"]): tuple(str(row["targets"]).split(";"))
        for row in injections
    }
    placement_audit = image_audit.get("placement_pilot", {})
    placement_audit_mismatch = int(
        placement_audit.get("profile") != profile.id
        or placement_audit.get("placement") != placement
        or placement_audit.get("domain_assignments") != config.placements[placement]
        or placement_audit.get("replica_services") != profile.replica_services
        or placement_audit.get("haproxy_config_sha256") != file_sha256(haproxy_file)
    )
    routing_deltas = routing_audit["session_deltas"]
    sentinel_failures = sum(
        not bool(row["semantic_success"]) for row in sentinel_requests
    )
    routing_fraction = float(routing_audit["semantic_success_fraction"])
    operation_cells = {str(row["operation"]) for row in fault_requests}
    quality = {
        "checkout_commit_mismatches": int(observed_commit != runtime_profile.commit),
        "placement_audit_mismatches": placement_audit_mismatch,
        "request_count_mismatches": int(len(requests) != expected_requests),
        "duplicate_request_ids": len(request_ids) - len(set(request_ids)),
        "duplicate_trace_ids": len(trace_ids) - len(set(trace_ids)),
        "sentinel_semantic_failures": sentinel_failures,
        "eventual_effect_failures": int(not effect_audit["passed"]),
        "routing_semantic_success_below_minimum": int(
            routing_fraction < config.minimum_routing_semantic_success_fraction
        ),
        "unserved_replicas": sum(
            int(routing_deltas[replica]) < config.minimum_backend_sessions_per_replica
            for replica in ("a", "b")
        ),
        "unhealthy_proxy_backends": sum(
            not str(routing_audit["after"][replica]["status"]).startswith("UP")
            for replica in ("a", "b")
        ),
        "fault_operation_mismatches": len(
            set(runtime_profile.operations).symmetric_difference(operation_cells)
        ),
        "injection_count_mismatches": int(len(injections) != len(config.events)),
        "injection_target_mismatches": sum(
            observed_targets.get(event_id) != targets
            for event_id, targets in expected_targets.items()
        ),
        "unconfirmed_injections": sum(not bool(row["confirmed"]) for row in injections),
        "unrestored_injections": sum(not bool(row["restored"]) for row in injections),
        "health_services_below_minimum": sum(
            count < config.minimum_health_samples_per_service
            for count in health_counts.values()
        ),
        "health_sampling_errors": sum(bool(row["error"]) for row in health),
        "linked_success_fraction_below_minimum": int(
            linked_fraction < config.minimum_linked_success_fraction
        ),
        "telemetry_collection_errors": int(bool(telemetry_error)),
        "unlocked_rendered_services": int(
            not image_audit.get("all_services_locked", False)
        ),
        "unlocked_running_images": unlocked_running,
        "running_container_count_mismatches": int(
            len(containers) != int(image_audit.get("service_count", 0))
        ),
        "unclean_final_state": int(not final_state["clean"]),
    }
    manifest = {
        "schema_version": 1,
        "kind": "replicated_placement_and_semantics_pilot",
        "experiment_id": config.id,
        "pilot_only": True,
        "usable_for_m7_freeze": not any(quality.values()),
        "profile": profile.id,
        "placement": placement,
        "expected_checkout_commit": runtime_profile.commit,
        "observed_checkout_commit": observed_commit,
        "domain_assignments": config.placements[placement],
        "replica_services": profile.replica_services,
        "fault_period": fault_metadata,
        "semantic_effect_audit": effect_audit,
        "routing_audit": routing_audit,
        "final_state": final_state,
        "counts": {
            "requests": len(requests),
            "immediate_successes": sum(
                bool(row["immediate_success"]) for row in requests
            ),
            "semantic_successes": semantic_successes,
            "fault_period_successes": sum(
                bool(row["semantic_success"]) for row in fault_requests
            ),
            "native_trace_count": native_trace_count,
            "successful_requests_with_trace": linked_successes,
            "injections": len(injections),
            "confirmed_injections": sum(bool(row["confirmed"]) for row in injections),
            "restored_injections": sum(bool(row["restored"]) for row in injections),
            "health_samples": len(health),
            "running_containers": len(containers),
            "locked_services": int(image_audit.get("service_count", 0)),
        },
        "health_samples_by_service": health_counts,
        "linked_success_fraction": linked_fraction,
        "telemetry_kind": runtime_profile.telemetry_kind,
        "telemetry_error": telemetry_error,
        "quality": quality,
        "files": {
            "requests_sha256": file_sha256(output / "requests.csv"),
            "responses_sha256": file_sha256(output / "responses.jsonl"),
            "injections_sha256": file_sha256(output / "injections.csv"),
            "health_sha256": file_sha256(output / "health.csv"),
            "trace_join_sha256": file_sha256(output / "trace-join.csv"),
            "raw_telemetry_sha256": file_sha256(raw_path),
            "semantic_effect_audit_sha256": file_sha256(
                output / "semantic-effect-audit.json"
            ),
            "routing_audit_sha256": file_sha256(output / "routing-audit.json"),
            "final_state_sha256": file_sha256(output / "final-state.json"),
            "image_audit_sha256": file_sha256(image_audit_file),
            "haproxy_config_sha256": file_sha256(haproxy_file),
            "runtime_containers_sha256": file_sha256(
                output / "runtime-containers.json"
            ),
        },
        "environment": environment_manifest(),
    }
    (output / "placement_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if any(quality.values()):
        raise PlacementPilotError(f"placement pilot quality checks failed: {quality}")
    return manifest


def _manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    counts = manifest["counts"]
    deltas = manifest["routing_audit"]["session_deltas"]
    return {
        "profile": manifest["profile"],
        "placement": manifest["placement"],
        "requests": counts["requests"],
        "immediate_successes": counts["immediate_successes"],
        "semantic_successes": counts["semantic_successes"],
        "fault_period_successes": counts["fault_period_successes"],
        "linked_success_fraction": manifest["linked_success_fraction"],
        "native_trace_count": counts["native_trace_count"],
        "routing_replica_a_sessions": deltas["a"],
        "routing_replica_b_sessions": deltas["b"],
        "injections": counts["injections"],
        "confirmed_injections": counts["confirmed_injections"],
        "restored_injections": counts["restored_injections"],
        "health_samples": counts["health_samples"],
        "usable": manifest["usable_for_m7_freeze"],
        "pilot_only": manifest["pilot_only"],
    }


def aggregate_placement_pilots(
    config: PlacementPilotConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    manifest_paths = sorted(root.rglob("placement_manifest.json"))
    manifests = [
        json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths
    ]
    expected = {
        (profile.id, placement)
        for profile in config.profiles
        for placement in config.placements
    }
    observed = [
        (str(manifest.get("profile", "")), str(manifest.get("placement", "")))
        for manifest in manifests
    ]
    observed_set = set(observed)
    quality: dict[str, int] = {
        "missing_cells": len(expected - observed_set),
        "unexpected_cells": len(observed_set - expected),
        "duplicate_cells": len(observed) - len(observed_set),
        "non_pilot_cells": sum(
            not manifest.get("pilot_only") for manifest in manifests
        ),
        "unusable_cells": sum(
            not manifest.get("usable_for_m7_freeze") for manifest in manifests
        ),
    }
    for manifest in manifests:
        for name, value in manifest.get("quality", {}).items():
            quality[name] = quality.get(name, 0) + int(value)
    rows = sorted(
        (_manifest_summary(manifest) for manifest in manifests),
        key=lambda row: (str(row["profile"]), str(row["placement"])),
    )
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, rows)
    aggregate = {
        "schema_version": 1,
        "kind": "replicated_placement_and_semantics_pilot_aggregate",
        "experiment_id": config.id,
        "pilot_only": True,
        "expected_cells": len(expected),
        "source_cells": len(manifests),
        "quality": quality,
        "row_counts": {"summary": len(rows)},
        "source_manifest_sha256": {
            f"{manifest['profile']}:{manifest['placement']}": file_sha256(path)
            for manifest, path in zip(manifests, manifest_paths, strict=True)
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if any(quality.values()):
        raise PlacementPilotError(
            f"placement pilot aggregate quality checks failed: {quality}"
        )
    return aggregate
