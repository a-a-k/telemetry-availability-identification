from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

import yaml

from .live_config import BenchmarkProfile, LiveHarnessConfig
from .live_ingestion import IngestedLiveBundle, ingest_live_bundle, write_ingested_bundle
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class LiveHarnessError(ValueError):
    """Raised when a frozen benchmark checkout violates its harness profile."""


PROFILE_SUMMARY_FIELDS = (
    "benchmark_id",
    "repository",
    "pinned_commit",
    "trace_format",
    "required_path_count",
    "required_service_count",
    "operation_count",
    "external_requests",
    "traced_external_requests",
    "requests_without_exported_trace",
    "untraced_external_failures",
    "spans",
    "deployments",
    "health_records",
    "mesh_records",
    "injections",
    "root_trace_coverage",
    "deterministic_reingestion",
    "fixture_only",
)


def select_live_profile(config: LiveHarnessConfig, benchmark_id: str) -> BenchmarkProfile:
    matches = [item for item in config.benchmarks if item.id == benchmark_id]
    if len(matches) != 1:
        known = [item.id for item in config.benchmarks]
        raise LiveHarnessError(
            f"unknown benchmark {benchmark_id!r}; expected one of {known}"
        )
    return matches[0]


def _checkout_commit(checkout: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise LiveHarnessError(f"cannot inspect benchmark checkout {checkout}") from error
    return completed.stdout.strip().lower()


def _checkout_repository(checkout: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(checkout), "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise LiveHarnessError(f"cannot inspect benchmark remote in {checkout}") from error
    return completed.stdout.strip()


def _normalized_repository(value: str) -> str:
    return value.strip().lower().rstrip("/").removesuffix(".git")


def _checked_path(checkout: Path, relative_path: str) -> Path:
    root = checkout.resolve()
    path = (root / Path(relative_path)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise LiveHarnessError(f"required upstream path is missing: {relative_path}")
    return path


def _compose_services(paths: Iterable[Path]) -> set[str]:
    services: set[str] = set()
    for path in paths:
        if path.name not in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}:
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or not isinstance(document.get("services"), dict):
            raise LiveHarnessError(f"upstream compose file has no services mapping: {path.name}")
        services.update(str(value) for value in document["services"])
    if not services:
        raise LiveHarnessError("profile has no inspectable Compose service declaration")
    return services


def _bundle_fingerprint(bundle: IngestedLiveBundle) -> str:
    payload = {
        "manifest": bundle.manifest,
        "periods": {
            key: {
                "start": value.start.isoformat(),
                "end": value.end.isoformat(),
                "workload_seed": value.workload_seed,
                "failure_seed": value.failure_seed,
                "sampling_seed": value.sampling_seed,
            }
            for key, value in sorted(bundle.periods.items())
        },
        "operations": bundle.operations,
        "requests": bundle.requests,
        "spans": bundle.spans,
        "deployments": bundle.deployments,
        "health": bundle.health,
        "mesh": bundle.mesh,
        "injections": bundle.injections,
        "audit": bundle.audit,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def verify_live_profile(
    config: LiveHarnessConfig,
    benchmark_id: str,
    checkout_directory: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    profile = select_live_profile(config, benchmark_id)
    checkout = Path(checkout_directory)
    observed_commit = _checkout_commit(checkout)
    if observed_commit != profile.commit:
        raise LiveHarnessError(
            f"upstream checkout is {observed_commit}, expected {profile.commit}"
        )
    observed_repository = _checkout_repository(checkout)
    if _normalized_repository(observed_repository) != _normalized_repository(
        profile.repository
    ):
        raise LiveHarnessError(
            f"upstream remote is {observed_repository!r}, expected {profile.repository!r}"
        )

    required = {
        relative: _checked_path(checkout, relative)
        for relative in profile.required_paths
    }
    services = _compose_services(required.values())
    missing_services = sorted(set(profile.required_services) - services)
    if missing_services:
        raise LiveHarnessError(
            f"upstream Compose files miss required services: {missing_services}"
        )

    operation_evidence: list[dict[str, Any]] = []
    for operation in profile.operations:
        path = required[operation.workload_path]
        source = path.read_text(encoding="utf-8")
        missing_markers = [marker for marker in operation.markers if marker not in source]
        if missing_markers:
            raise LiveHarnessError(
                f"upstream workload evidence for {operation.id!r} misses {missing_markers}"
            )
        operation_evidence.append(
            {
                "operation": operation.id,
                "workload_path": operation.workload_path,
                "markers": list(operation.markers),
                "source_sha256": file_sha256(path),
            }
        )

    first = ingest_live_bundle(profile.fixture_bundle, config.contract, profile)
    second = ingest_live_bundle(profile.fixture_bundle, config.contract, profile)
    first_fingerprint = _bundle_fingerprint(first)
    second_fingerprint = _bundle_fingerprint(second)
    deterministic = first_fingerprint == second_fingerprint
    if not deterministic:
        raise LiveHarnessError("fixture re-ingestion is nondeterministic")

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    normalized_manifest = write_ingested_bundle(first, output / "normalized")
    report = {
        "schema_version": 1,
        "kind": "live_harness_profile_verification",
        "benchmark_id": profile.id,
        "repository": profile.repository,
        "observed_repository": observed_repository,
        "pinned_commit": profile.commit,
        "observed_checkout_commit": observed_commit,
        "trace_format": profile.trace_format,
        "fixture_only": True,
        "fixture_bundle_id": first.manifest["bundle_id"],
        "required_paths": [
            {
                "path": relative,
                "sha256": file_sha256(path),
            }
            for relative, path in sorted(required.items())
        ],
        "required_services": list(profile.required_services),
        "operation_evidence": operation_evidence,
        "fixture_audit": first.audit,
        "reingestion": {
            "deterministic": deterministic,
            "first_fingerprint": first_fingerprint,
            "second_fingerprint": second_fingerprint,
        },
        "normalized_manifest": normalized_manifest,
        "quality": {
            "upstream_commit_mismatches": 0,
            "upstream_repository_mismatches": 0,
            "missing_required_paths": 0,
            "missing_required_services": 0,
            "missing_operation_markers": 0,
            "nondeterministic_reingestions": 0,
            "contract_quality_failures": sum(first.audit["quality"].values()),
            "unpreserved_untraced_failures": int(
                first.audit["counts"]["untraced_external_failures"] < 1
            ),
        },
        "environment": environment_manifest(),
    }
    failures = {key: value for key, value in report["quality"].items() if value}
    if failures:
        raise LiveHarnessError(f"live harness profile quality failures: {failures}")
    (output / "profile_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _summary_row(report: dict[str, Any]) -> dict[str, Any]:
    counts = report["fixture_audit"]["counts"]
    return {
        "benchmark_id": report["benchmark_id"],
        "repository": report["repository"],
        "pinned_commit": report["pinned_commit"],
        "trace_format": report["trace_format"],
        "required_path_count": len(report["required_paths"]),
        "required_service_count": len(report["required_services"]),
        "operation_count": len(report["operation_evidence"]),
        "external_requests": counts["external_requests"],
        "traced_external_requests": counts["traced_external_requests"],
        "requests_without_exported_trace": counts["requests_without_exported_trace"],
        "untraced_external_failures": counts["untraced_external_failures"],
        "spans": counts["spans"],
        "deployments": counts["deployments"],
        "health_records": counts["health_records"],
        "mesh_records": counts["mesh_records"],
        "injections": counts["injections"],
        "root_trace_coverage": report["fixture_audit"]["root_trace_coverage"],
        "deterministic_reingestion": report["reingestion"]["deterministic"],
        "fixture_only": report["fixture_only"],
    }


def aggregate_live_harness(
    config: LiveHarnessConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    paths = sorted(Path(input_root).rglob("profile_report.json"))
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    expected = {profile.id for profile in config.benchmarks}
    observed = [str(report.get("benchmark_id", "")) for report in reports]
    duplicates = len(observed) - len(set(observed))
    missing = expected - set(observed)
    unknown = set(observed) - expected
    if missing or unknown or duplicates:
        raise LiveHarnessError(
            f"profile aggregate mismatch: missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}, duplicates={duplicates}"
        )
    quality_names = sorted(
        {
            name
            for report in reports
            for name in report.get("quality", {})
        }
    )
    quality = {
        name: sum(int(report.get("quality", {}).get(name, 0)) for report in reports)
        for name in quality_names
    }
    quality.update(
        {
            "missing_profiles": len(missing),
            "unknown_profiles": len(unknown),
            "duplicate_profiles": duplicates,
        }
    )
    if any(quality.values()):
        raise LiveHarnessError(f"aggregate live-harness quality failures: {quality}")
    rows = sorted((_summary_row(report) for report in reports), key=lambda row: row["benchmark_id"])
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "summary.csv", PROFILE_SUMMARY_FIELDS, rows)
    manifest = {
        "schema_version": 1,
        "kind": "live_harness_aggregate",
        "contract": {
            "id": config.contract.id,
            "version": config.contract.version,
        },
        "profiles": sorted(observed),
        "source_profiles": len(reports),
        "fixture_only": True,
        "quality": quality,
        "row_counts": {"summary": len(rows)},
        "source_report_sha256": {
            report["benchmark_id"]: file_sha256(path)
            for report, path in zip(reports, paths)
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
