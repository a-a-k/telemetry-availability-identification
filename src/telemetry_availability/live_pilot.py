from __future__ import annotations

import csv
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .live_pilot_config import (
    RuntimePilotConfig,
    RuntimePilotProfile,
    select_runtime_pilot_profile,
)
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class RuntimePilotError(RuntimeError):
    """Raised when a predeclared runtime-pilot acceptance criterion fails."""


PILOT_REQUEST_FIELDS = (
    "request_id",
    "started_at",
    "completed_at",
    "period",
    "operation",
    "branch_class",
    "status_code",
    "success",
    "latency_ms",
    "error",
)

PILOT_SUMMARY_FIELDS = (
    "profile",
    "expected_requests",
    "observed_requests",
    "successful_requests",
    "success_fraction",
    "exported_traces",
    "running_containers",
    "locked_services",
    "pilot_status",
    "pilot_only",
)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _image_key(value: str) -> str:
    without_digest = value.split("@", 1)[0].lower()
    last = without_digest.rsplit("/", 1)[-1]
    if ":" not in last:
        without_digest += ":latest"
    for prefix in ("docker.io/library/", "docker.io/"):
        if without_digest.startswith(prefix):
            without_digest = without_digest[len(prefix) :]
            break
    return without_digest


def pin_compose_document(
    document: dict[str, Any],
    profile: RuntimePilotProfile,
) -> tuple[dict[str, Any], dict[str, Any]]:
    services = document.get("services")
    if not isinstance(services, dict) or not services:
        raise RuntimePilotError("rendered Compose document has no services")
    rendered_service_count = len(services)
    disabled = set(profile.disabled_services)
    missing_disabled = sorted(disabled - set(services))
    if missing_disabled:
        raise RuntimePilotError(
            f"disabled services are absent from rendered Compose: {missing_disabled}"
        )
    for service_name in disabled:
        services.pop(service_name)
    for raw_service in services.values():
        if not isinstance(raw_service, dict):
            continue
        dependencies = raw_service.get("depends_on")
        if isinstance(dependencies, dict):
            for service_name in disabled:
                dependencies.pop(service_name, None)
        elif isinstance(dependencies, list):
            raw_service["depends_on"] = [
                service_name
                for service_name in dependencies
                if service_name not in disabled
            ]
    locks = {_image_key(image): (image, digest) for image, digest in profile.images.items()}
    if len(locks) != len(profile.images):
        raise RuntimePilotError("image lock aliases are ambiguous")
    rows: list[dict[str, str]] = []
    for service_name, raw_service in services.items():
        if not isinstance(raw_service, dict) or not raw_service.get("image"):
            raise RuntimePilotError(f"service {service_name!r} has no rendered image")
        original = str(raw_service["image"])
        key = _image_key(original)
        if key not in locks:
            raise RuntimePilotError(
                f"service {service_name!r} image {original!r} has no digest lock"
            )
        _, digest = locks[key]
        base = original.split("@", 1)[0]
        if ":" not in base.rsplit("/", 1)[-1]:
            base += ":latest"
        pinned = f"{base}@{digest}"
        raw_service["image"] = pinned
        raw_service.pop("build", None)
        rows.append(
            {
                "service": str(service_name),
                "rendered_image": original,
                "locked_image": pinned,
                "manifest_digest": digest,
            }
        )
    used = {_image_key(row["rendered_image"]) for row in rows}
    unused = sorted(set(locks) - used)
    if unused:
        raise RuntimePilotError(f"image locks are unused by rendered Compose: {unused}")
    return document, {
        "schema_version": 1,
        "profile": profile.id,
        "rendered_service_count": rendered_service_count,
        "service_count": len(rows),
        "disabled_services": sorted(disabled),
        "all_services_locked": True,
        "images": sorted(rows, key=lambda row: row["service"]),
    }


def pin_compose_files(
    config: RuntimePilotConfig,
    profile_id: str,
    input_path: str | Path,
    output_path: str | Path,
    audit_path: str | Path,
) -> dict[str, Any]:
    profile = select_runtime_pilot_profile(config, profile_id)
    document = json.loads(Path(input_path).read_text(encoding="utf-8"))
    pinned, audit = pin_compose_document(document, profile)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pinned, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_output = Path(audit_path)
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    audit_output.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return audit


def _http_request(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 10.0,
) -> tuple[int | None, bytes, str]:
    headers = {"User-Agent": "taid-runtime-pilot/1"}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read(), ""
    except urllib.error.HTTPError as error:
        return int(error.code), error.read(), f"HTTPError: {error.reason}"
    except (OSError, TimeoutError, urllib.error.URLError) as error:
        return None, b"", f"{type(error).__name__}: {error}"


def wait_for_frontend(profile: RuntimePilotProfile, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "not attempted"
    while time.monotonic() < deadline:
        status, _, error = _http_request(
            profile.base_url + profile.readiness_path,
            timeout=5,
        )
        if status is not None and 200 <= status < 500:
            return
        last_error = error or f"HTTP {status}"
        time.sleep(2)
    raise RuntimePilotError(f"frontend did not become reachable: {last_error}")


def _form(values: dict[str, Any]) -> bytes:
    return urllib.parse.urlencode(values).encode("utf-8")


def _json(values: dict[str, Any]) -> bytes:
    return json.dumps(values, separators=(",", ":")).encode("utf-8")


def _deathstar_request(
    profile: RuntimePilotProfile,
    operation: str,
    index: int,
) -> tuple[int | None, bytes, str, str]:
    if operation == "compose_post":
        branch = "with_media" if index % 2 else "text_only"
        media_ids = '["123456789012345678"]' if branch == "with_media" else "[]"
        media_types = '["png"]' if branch == "with_media" else "[]"
        status, body, error = _http_request(
            profile.base_url + "/wrk2-api/post/compose",
            data=_form(
                {
                    "username": "username_0",
                    "user_id": "0",
                    "text": f"taid pilot post {index}",
                    "media_ids": media_ids,
                    "media_types": media_types,
                    "post_type": "0",
                }
            ),
            content_type="application/x-www-form-urlencoded",
        )
        return status, body, error, branch
    if operation == "read_home_timeline":
        status, body, error = _http_request(
            profile.base_url + "/wrk2-api/home-timeline/read?user_id=0&start=0&stop=10"
        )
        return status, body, error, "observed_mix"
    if operation == "read_user_timeline":
        status, body, error = _http_request(
            profile.base_url + "/wrk2-api/user-timeline/read?user_id=0&start=0&stop=10"
        )
        return status, body, error, "observed_mix"
    raise RuntimePilotError(f"unsupported DeathStarBench operation {operation!r}")


OTEL_PRODUCT = "OLJCESPC7Z"
OTEL_PERSON = {
    "email": "taid-pilot@example.com",
    "address": {
        "streetAddress": "1600 Amphitheatre Parkway",
        "zipCode": "94043",
        "city": "Mountain View",
        "state": "CA",
        "country": "United States",
    },
    "userCurrency": "USD",
    "creditCard": {
        "creditCardNumber": "4432-8015-6152-0454",
        "creditCardExpirationMonth": 1,
        "creditCardExpirationYear": 2039,
        "creditCardCvv": 672,
    },
}


def _otel_add_cart(profile: RuntimePilotProfile, user_id: str) -> tuple[int | None, bytes, str]:
    product_status, _, product_error = _http_request(
        profile.base_url + f"/api/products/{OTEL_PRODUCT}"
    )
    if product_status is None or not 200 <= product_status < 300:
        return product_status, b"", product_error or "product prerequisite failed"
    return _http_request(
        profile.base_url + "/api/cart",
        data=_json(
            {
                "item": {"productId": OTEL_PRODUCT, "quantity": 1},
                "userId": user_id,
            }
        ),
        content_type="application/json",
    )


def _otel_request(
    profile: RuntimePilotProfile,
    operation: str,
    period: str,
    index: int,
) -> tuple[int | None, bytes, str, str]:
    if operation == "browse_product":
        status, body, error = _http_request(
            profile.base_url + f"/api/products/{OTEL_PRODUCT}"
        )
        return status, body, error, "catalog_request"
    user_id = f"taid-{period}-{index}"
    if operation == "add_to_cart":
        status, body, error = _otel_add_cart(profile, user_id)
        return status, body, error, "new_item"
    if operation == "checkout":
        status, _, error = _otel_add_cart(profile, user_id)
        if status is None or not 200 <= status < 300:
            return status, b"", error or "cart prerequisite failed", "single_item"
        payload = {**OTEL_PERSON, "userId": user_id}
        status, body, error = _http_request(
            profile.base_url + "/api/checkout",
            data=_json(payload),
            content_type="application/json",
        )
        return status, body, error, "single_item"
    raise RuntimePilotError(f"unsupported OTel Demo operation {operation!r}")


def initialize_profile(profile: RuntimePilotProfile) -> None:
    if profile.id != "deathstarbench_social_network":
        return
    actions: list[tuple[str, str, dict[str, str]]] = []
    for user_id in ("0", "1"):
        actions.append(
            (
                f"register user {user_id}",
                "/wrk2-api/user/register",
                {
                    "first_name": f"first_name_{user_id}",
                    "last_name": f"last_name_{user_id}",
                    "username": f"username_{user_id}",
                    "password": f"password_{user_id}",
                    "user_id": user_id,
                },
            )
        )
    for user_id, followee_id in (("0", "1"), ("1", "0")):
        actions.append(
            (
                f"follow {user_id} -> {followee_id}",
                "/wrk2-api/user/follow",
                {
                    "user_name": f"username_{user_id}",
                    "followee_name": f"username_{followee_id}",
                },
            )
        )
    for label, path, payload in actions:
        last = "not attempted"
        for _ in range(30):
            status, body, error = _http_request(
                profile.base_url + path,
                data=_form(payload),
                content_type="application/x-www-form-urlencoded",
            )
            last = error or body.decode("utf-8", errors="replace")[:200]
            if status is not None and 200 <= status < 300:
                break
            time.sleep(2)
        else:
            raise RuntimePilotError(
                f"DeathStarBench initialization action {label!r} failed: {last}"
            )


def _run_period(
    config: RuntimePilotConfig,
    profile: RuntimePilotProfile,
    period: str,
    seed: int,
) -> tuple[list[dict[str, Any]], datetime, datetime]:
    order = [
        operation
        for operation in profile.operations
        for _ in range(config.requests_per_operation_per_period)
    ]
    random.Random(seed).shuffle(order)
    period_start = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for index, operation in enumerate(order):
        started = datetime.now(timezone.utc)
        if profile.id == "deathstarbench_social_network":
            status, _, error, branch = _deathstar_request(profile, operation, index)
        elif profile.id == "opentelemetry_demo":
            status, _, error, branch = _otel_request(profile, operation, period, index)
        else:
            raise RuntimePilotError(f"no workload driver for {profile.id!r}")
        completed = datetime.now(timezone.utc)
        success = status is not None and 200 <= status < 300
        rows.append(
            {
                "request_id": f"{profile.id}-{period}-{index:04d}",
                "started_at": _format_time(started),
                "completed_at": _format_time(completed),
                "period": period,
                "operation": operation,
                "branch_class": branch,
                "status_code": status,
                "success": success,
                "latency_ms": (completed - started).total_seconds() * 1000,
                "error": error,
            }
        )
    period_end = datetime.now(timezone.utc)
    return rows, period_start, period_end


def _collect_telemetry(
    profile: RuntimePilotProfile,
    since: datetime,
    output: Path,
) -> tuple[int, str]:
    if profile.telemetry_kind == "jaeger_api":
        status, body, error = _http_request(profile.telemetry_source, timeout=30)
        path = output / "raw-telemetry.json"
        path.write_bytes(body)
        if status is None or not 200 <= status < 300:
            return 0, error or f"Jaeger HTTP {status}"
        try:
            document = json.loads(body)
            count = len(document.get("data", []))
        except (json.JSONDecodeError, AttributeError) as parse_error:
            return 0, f"invalid Jaeger response: {parse_error}"
        return count, ""
    completed = subprocess.run(
        [
            "docker",
            "logs",
            "--since",
            _format_time(since),
            profile.telemetry_source,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    raw = completed.stdout + completed.stderr
    path = output / "raw-telemetry.log"
    path.write_text(raw, encoding="utf-8")
    trace_ids = set(
        re.findall(r"Trace ID\s*:\s*([0-9a-f]{16,32})", raw, flags=re.IGNORECASE)
    )
    return len(trace_ids), "" if completed.returncode == 0 else "docker logs failed"


def _runtime_containers(compose_path: Path, output: Path) -> tuple[list[dict[str, Any]], int]:
    listed = subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "ps", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    container_ids = [value for value in listed.stdout.splitlines() if value]
    records: list[dict[str, Any]] = []
    unlocked = 0
    for container_id in container_ids:
        inspected = subprocess.run(
            ["docker", "inspect", container_id],
            capture_output=True,
            text=True,
            check=False,
        )
        if inspected.returncode != 0:
            continue
        document = json.loads(inspected.stdout)[0]
        configured_image = str(document.get("Config", {}).get("Image", ""))
        unlocked += int("@sha256:" not in configured_image)
        records.append(
            {
                "id": document.get("Id"),
                "name": str(document.get("Name", "")).lstrip("/"),
                "configured_image": configured_image,
                "image_id": document.get("Image"),
                "status": document.get("State", {}).get("Status"),
                "health": document.get("State", {}).get("Health", {}).get("Status"),
            }
        )
    (output / "runtime-containers.json").write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records, unlocked


def _git_head(checkout: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip().lower()


def run_runtime_pilot(
    config: RuntimePilotConfig,
    profile_id: str,
    checkout_directory: str | Path,
    compose_path: str | Path,
    image_audit_path: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimePilotError("runtime pilots may run only in GitHub Actions")
    profile = select_runtime_pilot_profile(config, profile_id)
    checkout = Path(checkout_directory)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    pilot_started = datetime.now(timezone.utc)
    observed_commit = _git_head(checkout)
    wait_for_frontend(profile, config.readiness_timeout_seconds)
    time.sleep(config.post_start_stabilization_seconds)
    initialize_profile(profile)
    calibration, calibration_start, calibration_end = _run_period(
        config,
        profile,
        "calibration",
        7101 if profile.id == "deathstarbench_social_network" else 7201,
    )
    time.sleep(config.inter_period_gap_seconds)
    test, test_start, test_end = _run_period(
        config,
        profile,
        "test",
        8101 if profile.id == "deathstarbench_social_network" else 8201,
    )
    rows = calibration + test
    _write_csv(output / "requests.csv", PILOT_REQUEST_FIELDS, rows)
    time.sleep(config.trace_flush_seconds)
    exported_traces, telemetry_error = _collect_telemetry(
        profile,
        pilot_started,
        output,
    )
    containers, unlocked_running = _runtime_containers(Path(compose_path), output)
    image_audit = json.loads(Path(image_audit_path).read_text(encoding="utf-8"))
    expected_requests = (
        2 * len(profile.operations) * config.requests_per_operation_per_period
    )
    successful = sum(bool(row["success"]) for row in rows)
    success_fraction = successful / len(rows) if rows else 0.0
    quality = {
        "checkout_commit_mismatches": int(observed_commit != profile.commit),
        "request_count_mismatches": int(len(rows) != expected_requests),
        "below_success_threshold": int(
            success_fraction < config.minimum_success_fraction
        ),
        "insufficient_exported_traces": int(
            exported_traces < config.minimum_exported_traces
        ),
        "telemetry_collection_errors": int(bool(telemetry_error)),
        "unlocked_rendered_services": int(
            not image_audit.get("all_services_locked", False)
        ),
        "unlocked_running_images": unlocked_running,
        "missing_running_containers": int(not containers),
    }
    manifest = {
        "schema_version": 1,
        "kind": "runtime_feasibility_pilot",
        "experiment_id": config.id,
        "profile": profile.id,
        "pilot_only": True,
        "usable_for_main_design": not any(quality.values()),
        "observed_checkout_commit": observed_commit,
        "expected_checkout_commit": profile.commit,
        "periods": {
            "calibration": {
                "start": _format_time(calibration_start),
                "end": _format_time(calibration_end),
                "workload_seed": 7101
                if profile.id == "deathstarbench_social_network"
                else 7201,
            },
            "test": {
                "start": _format_time(test_start),
                "end": _format_time(test_end),
                "workload_seed": 8101
                if profile.id == "deathstarbench_social_network"
                else 8201,
            },
        },
        "counts": {
            "expected_requests": expected_requests,
            "observed_requests": len(rows),
            "successful_requests": successful,
            "failed_requests": len(rows) - successful,
            "exported_traces": exported_traces,
            "running_containers": len(containers),
            "locked_services": int(image_audit.get("service_count", 0)),
        },
        "success_fraction": success_fraction,
        "telemetry_kind": profile.telemetry_kind,
        "telemetry_error": telemetry_error,
        "quality": quality,
        "files": {
            "requests_sha256": file_sha256(output / "requests.csv"),
            "image_audit_sha256": file_sha256(image_audit_path),
            "runtime_containers_sha256": file_sha256(
                output / "runtime-containers.json"
            ),
            "raw_telemetry_sha256": file_sha256(
                output
                / (
                    "raw-telemetry.json"
                    if profile.telemetry_kind == "jaeger_api"
                    else "raw-telemetry.log"
                )
            ),
        },
        "environment": environment_manifest(),
    }
    (output / "pilot_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise RuntimePilotError(f"runtime pilot acceptance failures: {failures}")
    return manifest


def aggregate_runtime_pilots(
    config: RuntimePilotConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    paths = sorted(Path(input_root).rglob("pilot_manifest.json"))
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    expected = {profile.id for profile in config.profiles}
    observed = [str(manifest.get("profile", "")) for manifest in manifests]
    if set(observed) != expected or len(observed) != len(expected):
        raise RuntimePilotError(
            f"runtime pilot profile mismatch: expected={sorted(expected)}, observed={observed}"
        )
    quality_names = sorted(
        {name for manifest in manifests for name in manifest.get("quality", {})}
    )
    quality = {
        name: sum(int(manifest["quality"].get(name, 0)) for manifest in manifests)
        for name in quality_names
    }
    quality["unusable_profiles"] = sum(
        not bool(manifest.get("usable_for_main_design")) for manifest in manifests
    )
    rows = []
    for manifest in manifests:
        counts = manifest["counts"]
        rows.append(
            {
                "profile": manifest["profile"],
                **counts,
                "success_fraction": manifest["success_fraction"],
                "pilot_status": "usable"
                if manifest["usable_for_main_design"]
                else "not_usable",
                "pilot_only": manifest["pilot_only"],
            }
        )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output / "summary.csv",
        PILOT_SUMMARY_FIELDS,
        sorted(rows, key=lambda row: row["profile"]),
    )
    aggregate = {
        "schema_version": 1,
        "kind": "runtime_feasibility_pilot_aggregate",
        "experiment_id": config.id,
        "pilot_only": True,
        "profiles": sorted(observed),
        "source_profiles": len(manifests),
        "quality": quality,
        "row_counts": {"summary": len(rows)},
        "source_manifest_sha256": {
            manifest["profile"]: file_sha256(path)
            for manifest, path in zip(manifests, paths)
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if any(quality.values()):
        raise RuntimePilotError(f"runtime pilot aggregate failures: {quality}")
    return aggregate
