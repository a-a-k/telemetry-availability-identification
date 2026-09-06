from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .provenance import environment_manifest


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODEL_SUFFIXES = {
    ".allocation",
    ".repository",
    ".resourceenvironment",
    ".system",
    ".usagemodel",
}


@dataclass(frozen=True)
class FullPathApplication:
    id: str
    repository: str
    commit: str
    operation: str
    rules: tuple[str, ...]
    operation_markers: tuple[str, ...]
    entry_markers: tuple[str, ...]
    target_markers: tuple[str, ...]
    replica_markers: tuple[str, ...]
    domain_markers: tuple[str, ...]
    source_evidence: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class PalladioFullPathConfig:
    path: Path
    raw: Mapping[str, Any]
    id: str
    job_timeout_minutes: int
    internal_timeout_seconds: int
    applications: tuple[FullPathApplication, ...]
    required_gates: tuple[str, ...]


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _positive_integer(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}.{key} must be a positive integer")
    return value


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    values = _sequence(value, label)
    if not values or any(not isinstance(item, str) or not item for item in values):
        raise ValueError(f"{label} must contain non-empty strings")
    result = tuple(values)
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must not contain duplicates")
    return result


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _commit(value: object, label: str) -> str:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a full lowercase commit")
    return value


def _relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must be relative and remain below its root")
    return path.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as source:
        return _mapping(json.load(source), label)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(
    path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _git_head(path: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"cannot read Git head for {path}") from error
    return completed.stdout.strip()


def _validate_locked_file(record: Mapping[str, Any], label: str) -> None:
    _relative_path(record.get("path"), f"{label}.path")
    _positive_integer(record, "bytes", label)
    _sha256(record.get("sha256"), f"{label}.sha256")
    _string_tuple(record.get("markers"), f"{label}.markers")
    forbidden = record.get("forbidden_markers", [])
    if not isinstance(forbidden, list) or any(
        not isinstance(item, str) or not item for item in forbidden
    ):
        raise ValueError(f"{label}.forbidden_markers must be a string list")


def load_palladio_fullpath_config(path: Path) -> PalladioFullPathConfig:
    root = _load_json(path, "root")
    if root.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    if root.get("status") != "frozen_before_first_remote_extractor_execution":
        raise ValueError("M9E status must remain frozen before first execution")
    if root.get("diagnostic_only") is not True:
        raise ValueError("M9E must remain diagnostic_only")
    if root.get("accuracy_scoring") != "forbidden":
        raise ValueError("M9E must forbid accuracy scoring")

    runtime = _mapping(root.get("runtime"), "runtime")
    job_timeout = _positive_integer(runtime, "job_timeout_minutes", "runtime")
    if job_timeout != 360:
        raise ValueError("every M9E job timeout must be 360 minutes")
    internal_timeout = _positive_integer(
        runtime, "retriever_internal_timeout_seconds", "runtime"
    )
    if runtime.get("remote_only_full_execution") is not True:
        raise ValueError("full extractor execution must remain remote-only")

    retriever = _mapping(root.get("retriever"), "retriever")
    _commit(retriever.get("commit"), "retriever.commit")
    _sha256(retriever.get("asset_sha256"), "retriever.asset_sha256")
    _positive_integer(retriever, "asset_size_bytes", "retriever")
    _positive_integer(retriever, "asset_id", "retriever")
    locked_files = _sequence(retriever.get("source_locks"), "retriever.source_locks")
    if not locked_files:
        raise ValueError("retriever.source_locks must not be empty")
    for index, value in enumerate(locked_files):
        _validate_locked_file(
            _mapping(value, f"retriever.source_locks[{index}]"),
            f"retriever.source_locks[{index}]",
        )

    evidence = _mapping(root.get("evidence"), "evidence")
    m9c = _mapping(evidence.get("m9c_mapping"), "evidence.m9c_mapping")
    _relative_path(m9c.get("path"), "evidence.m9c_mapping.path")
    _sha256(m9c.get("sha256"), "evidence.m9c_mapping.sha256")
    m9d = _mapping(evidence.get("m9d_acceptance"), "evidence.m9d_acceptance")
    _positive_integer(m9d, "run_id", "evidence.m9d_acceptance")
    _positive_integer(m9d, "artifact_id", "evidence.m9d_acceptance")
    _positive_integer(m9d, "artifact_size_bytes", "evidence.m9d_acceptance")
    _sha256(m9d.get("artifact_sha256"), "evidence.m9d_acceptance.artifact_sha256")
    _sha256(m9d.get("manifest_sha256"), "evidence.m9d_acceptance.manifest_sha256")
    _commit(m9d.get("head_commit"), "evidence.m9d_acceptance.head_commit")

    applications: list[FullPathApplication] = []
    for index, value in enumerate(_sequence(root.get("applications"), "applications")):
        label = f"applications[{index}]"
        item = _mapping(value, label)
        source_evidence = tuple(
            _mapping(source, f"{label}.source_evidence")
            for source in _sequence(item.get("source_evidence"), f"{label}.source_evidence")
        )
        for source_index, source in enumerate(source_evidence):
            _validate_locked_file(source, f"{label}.source_evidence[{source_index}]")
            _string(source, "language", f"{label}.source_evidence[{source_index}]")
            if not isinstance(source.get("retriever_rule_support"), bool):
                raise ValueError(
                    f"{label}.source_evidence[{source_index}].retriever_rule_support "
                    "must be Boolean"
                )
        applications.append(
            FullPathApplication(
                id=_string(item, "id", label),
                repository=_string(item, "repository", label),
                commit=_commit(item.get("commit"), f"{label}.commit"),
                operation=_string(item, "operation", label),
                rules=_string_tuple(item.get("retriever_rules"), f"{label}.retriever_rules"),
                operation_markers=_string_tuple(
                    item.get("operation_markers"), f"{label}.operation_markers"
                ),
                entry_markers=_string_tuple(
                    item.get("entry_markers"), f"{label}.entry_markers"
                ),
                target_markers=_string_tuple(
                    item.get("target_markers"), f"{label}.target_markers"
                ),
                replica_markers=_string_tuple(
                    item.get("replica_markers"), f"{label}.replica_markers"
                ),
                domain_markers=_string_tuple(
                    item.get("domain_markers"), f"{label}.domain_markers"
                ),
                source_evidence=source_evidence,
            )
        )
    if {item.id for item in applications} != {
        "deathstarbench_social_network",
        "opentelemetry_demo",
    }:
        raise ValueError("M9E must audit exactly the two frozen M7 applications")

    gates = _sequence(root.get("readiness_gates"), "readiness_gates")
    gate_ids: list[str] = []
    for index, value in enumerate(gates):
        label = f"readiness_gates[{index}]"
        gate = _mapping(value, label)
        gate_ids.append(_string(gate, "id", label))
        if gate.get("required_for_ready") is not True:
            raise ValueError(f"{label} must be required for readiness")
        _string(gate, "manual_completion", label)
    if len(set(gate_ids)) != len(gate_ids):
        raise ValueError("readiness gate ids must be unique")

    candidates = _sequence(root.get("automation_candidates"), "automation_candidates")
    if {str(_mapping(item, "candidate").get("id")) for item in candidates} != {
        "PMX",
        "CIPM",
        "Retriever",
    }:
        raise ValueError("M9E must retain PMX, CIPM, and Retriever candidates")
    for index, value in enumerate(candidates):
        candidate = _mapping(value, f"automation_candidates[{index}]")
        _string(candidate, "source_url", f"automation_candidates[{index}]")
        _string(candidate, "scope", f"automation_candidates[{index}]")
        _string(candidate, "disposition", f"automation_candidates[{index}]")

    repository_locks = _sequence(
        evidence.get("repository_locks"), "evidence.repository_locks"
    )
    if not repository_locks:
        raise ValueError("evidence.repository_locks must not be empty")
    for index, value in enumerate(repository_locks):
        record = _mapping(value, f"evidence.repository_locks[{index}]")
        _relative_path(record.get("path"), f"evidence.repository_locks[{index}].path")
        _positive_integer(record, "bytes", f"evidence.repository_locks[{index}]")
        _sha256(
            record.get("sha256"), f"evidence.repository_locks[{index}].sha256"
        )
    manual_log = _mapping(evidence.get("manual_actions_log"), "evidence.manual_actions_log")
    _relative_path(manual_log.get("path"), "evidence.manual_actions_log.path")
    _positive_integer(
        manual_log, "initial_size_in_bytes", "evidence.manual_actions_log"
    )
    _sha256(
        manual_log.get("initial_sha256"),
        "evidence.manual_actions_log.initial_sha256",
    )
    if manual_log.get("append_only_after_preregistration") is not True:
        raise ValueError("M9E manual-actions log must remain append-only")

    return PalladioFullPathConfig(
        path=path,
        raw=root,
        id=_string(root, "id", "root"),
        job_timeout_minutes=job_timeout,
        internal_timeout_seconds=internal_timeout,
        applications=tuple(applications),
        required_gates=tuple(gate_ids),
    )


def _audit_file(root: Path, record: Mapping[str, Any], label: str) -> dict[str, Any]:
    relative = _relative_path(record.get("path"), f"{label}.path")
    path = root / relative
    if not path.is_file():
        raise ValueError(f"{label}: missing {relative}")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if len(content) != int(record["bytes"]):
        raise ValueError(f"{label}: byte count differs for {relative}")
    if digest != record["sha256"]:
        raise ValueError(f"{label}: SHA-256 differs for {relative}")
    text = content.decode("utf-8")
    missing = [marker for marker in record["markers"] if marker not in text]
    forbidden = [
        marker for marker in record.get("forbidden_markers", []) if marker in text
    ]
    if missing:
        raise ValueError(f"{label}: missing markers in {relative}: {missing}")
    if forbidden:
        raise ValueError(f"{label}: forbidden markers in {relative}: {forbidden}")
    return {
        "path": relative,
        "bytes": len(content),
        "sha256": digest,
        "marker_count": len(record["markers"]),
        "forbidden_marker_count": len(record.get("forbidden_markers", [])),
    }


def _artifact_digest(metadata: Mapping[str, Any]) -> str:
    value = metadata.get("digest")
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError("artifact metadata has no SHA-256 digest")
    return value.removeprefix("sha256:")


def audit_palladio_fullpath_contract(
    config_path: Path,
    retriever_checkout: Path,
    retriever_release_metadata: Path,
    m9c_config_path: Path,
    m9d_acceptance_root: Path,
    m9d_artifact_metadata: Path,
    upstream_root: Path,
    repository_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_palladio_fullpath_config(config_path)
    raw = config.raw
    evidence = _mapping(raw["evidence"], "evidence")
    retriever = _mapping(raw["retriever"], "retriever")

    lock_rows: list[dict[str, Any]] = []
    for index, value in enumerate(evidence["repository_locks"]):
        record = _mapping(value, f"repository_locks[{index}]")
        relative = str(record["path"])
        path = repository_root / relative
        if not path.is_file():
            raise ValueError(f"repository lock is missing: {relative}")
        actual_bytes = path.stat().st_size
        actual_sha = file_sha256(path)
        matches = actual_bytes == record["bytes"] and actual_sha == record["sha256"]
        lock_rows.append(
            {
                "path": relative,
                "expected_bytes": record["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": record["sha256"],
                "actual_sha256": actual_sha,
                "matches": matches,
            }
        )
        if not matches:
            raise ValueError(f"repository lock differs: {relative}")

    manual_log = _mapping(evidence["manual_actions_log"], "manual_actions_log")
    manual_path = repository_root / str(manual_log["path"])
    manual_content = manual_path.read_bytes()
    initial_size = int(manual_log["initial_size_in_bytes"])
    if len(manual_content) < initial_size:
        raise ValueError("M9E manual-actions log is shorter than its frozen prefix")
    initial_digest = hashlib.sha256(manual_content[:initial_size]).hexdigest()
    if initial_digest != manual_log["initial_sha256"]:
        raise ValueError("M9E manual-actions frozen prefix differs")
    with manual_path.open(encoding="utf-8", newline="") as source:
        manual_rows = list(csv.DictReader(source))
    if not manual_rows or set(row.get("status") for row in manual_rows) - {
        "planned",
        "completed",
    }:
        raise ValueError("M9E manual-actions statuses are invalid")

    expected_m9c = _mapping(evidence["m9c_mapping"], "evidence.m9c_mapping")
    if m9c_config_path.resolve() != (repository_root / expected_m9c["path"]).resolve():
        raise ValueError("M9C mapping path differs from the frozen path")
    if file_sha256(m9c_config_path) != expected_m9c["sha256"]:
        raise ValueError("M9C mapping SHA-256 differs")
    m9c = _load_json(m9c_config_path, "M9C mapping")
    m9c_apps = {
        str(_mapping(item, "M9C application")["id"]): _mapping(
            item, "M9C application"
        )
        for item in _sequence(m9c.get("applications"), "M9C applications")
    }

    expected_m9d = _mapping(evidence["m9d_acceptance"], "evidence.m9d_acceptance")
    m9d_manifest_path = m9d_acceptance_root / "acceptance-manifest.json"
    if file_sha256(m9d_manifest_path) != expected_m9d["manifest_sha256"]:
        raise ValueError("M9D acceptance manifest SHA-256 differs")
    m9d_manifest = _load_json(m9d_manifest_path, "M9D acceptance manifest")
    if m9d_manifest.get("technical_accepted") is not True:
        raise ValueError("M9D acceptance is not technical_accepted")
    if m9d_manifest.get("status") != "technical_bridge_passed_accuracy_descriptive_only":
        raise ValueError("unexpected M9D acceptance status")
    metadata = _load_json(m9d_artifact_metadata, "M9D artifact metadata")
    if metadata.get("id") != expected_m9d["artifact_id"]:
        raise ValueError("M9D artifact id differs")
    if metadata.get("name") != expected_m9d["artifact_name"]:
        raise ValueError("M9D artifact name differs")
    if metadata.get("size_in_bytes") != expected_m9d["artifact_size_bytes"]:
        raise ValueError("M9D artifact size differs")
    if _artifact_digest(metadata) != expected_m9d["artifact_sha256"]:
        raise ValueError("M9D artifact digest differs")

    if _git_head(retriever_checkout) != retriever["commit"]:
        raise ValueError("Retriever checkout commit differs")
    retriever_source_rows = [
        _audit_file(
            retriever_checkout,
            _mapping(value, f"retriever.source_locks[{index}]"),
            f"retriever.source_locks[{index}]",
        )
        for index, value in enumerate(retriever["source_locks"])
    ]
    release = _load_json(retriever_release_metadata, "Retriever release metadata")
    if release.get("tag_name") != retriever["tag"]:
        raise ValueError("Retriever release tag differs")
    matching_assets = [
        _mapping(item, "Retriever asset")
        for item in _sequence(release.get("assets"), "Retriever release assets")
        if _mapping(item, "Retriever asset").get("id") == retriever["asset_id"]
    ]
    if len(matching_assets) != 1:
        raise ValueError("Retriever asset id is absent or duplicated")
    asset = matching_assets[0]
    if asset.get("name") != retriever["asset_name"]:
        raise ValueError("Retriever asset name differs")
    if asset.get("size") != retriever["asset_size_bytes"]:
        raise ValueError("Retriever asset size differs")

    source_rows: list[dict[str, Any]] = []
    language_rows: list[dict[str, Any]] = []
    for application in config.applications:
        checkout = upstream_root / application.id
        if _git_head(checkout) != application.commit:
            raise ValueError(f"{application.id}: upstream commit differs")
        m9c_app = m9c_apps.get(application.id)
        if m9c_app is None:
            raise ValueError(f"{application.id}: missing from M9C mapping")
        upstream = _mapping(m9c_app.get("upstream"), "M9C upstream")
        if upstream.get("repository") != application.repository:
            raise ValueError(f"{application.id}: repository differs from M9C")
        if upstream.get("commit") != application.commit:
            raise ValueError(f"{application.id}: commit differs from M9C")
        m9c_sources = {
            str(_mapping(item, "M9C source")["path"]): _mapping(item, "M9C source")
            for item in _sequence(m9c_app.get("source_evidence"), "M9C sources")
        }
        for source_index, source in enumerate(application.source_evidence):
            relative = str(source["path"])
            prior = m9c_sources.get(relative)
            if prior is None:
                raise ValueError(f"{application.id}: {relative} is absent from M9C")
            for field in ("bytes", "sha256", "markers"):
                if source[field] != prior[field]:
                    raise ValueError(
                        f"{application.id}: {relative} {field} differs from M9C"
                    )
            audited = _audit_file(
                checkout,
                source,
                f"applications.{application.id}.source_evidence[{source_index}]",
            )
            audited["application"] = application.id
            source_rows.append(audited)
            language_rows.append(
                {
                    "application": application.id,
                    "operation": application.operation,
                    "path": relative,
                    "language": source["language"],
                    "retriever_rule_support": source["retriever_rule_support"],
                    "support_note": source["support_note"],
                }
            )

    candidate_rows = [
        {
            "candidate": item["id"],
            "source_url": item["source_url"],
            "scope": item["scope"],
            "input_contract": item["input_contract"],
            "reliability_parameter_output": item["reliability_parameter_output"],
            "disposition": item["disposition"],
            "reason": item["reason"],
        }
        for item in raw["automation_candidates"]
    ]
    boundary_rows = [dict(item) for item in raw["information_boundary"]]

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "repository-lock-audit.csv",
        (
            "path",
            "expected_bytes",
            "actual_bytes",
            "expected_sha256",
            "actual_sha256",
            "matches",
        ),
        lock_rows,
    )
    _write_csv(
        out / "retriever-source-audit.csv",
        ("path", "bytes", "sha256", "marker_count", "forbidden_marker_count"),
        retriever_source_rows,
    )
    _write_csv(
        out / "application-source-audit.csv",
        ("application", "path", "bytes", "sha256", "marker_count", "forbidden_marker_count"),
        source_rows,
    )
    _write_csv(
        out / "operation-language-coverage.csv",
        (
            "application",
            "operation",
            "path",
            "language",
            "retriever_rule_support",
            "support_note",
        ),
        language_rows,
    )
    _write_csv(
        out / "automation-candidates.csv",
        (
            "candidate",
            "source_url",
            "scope",
            "input_contract",
            "reliability_parameter_output",
            "disposition",
            "reason",
        ),
        candidate_rows,
    )
    _write_csv(
        out / "information-boundary.csv",
        (
            "element",
            "our_pipeline_input",
            "retriever_automatic_input",
            "full_path_pcm_requirement",
            "pre_result_classification",
        ),
        boundary_rows,
    )

    output_files = (
        "repository-lock-audit.csv",
        "retriever-source-audit.csv",
        "application-source-audit.csv",
        "operation-language-coverage.csv",
        "automation-candidates.csv",
        "information-boundary.csv",
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9e_full_path_feasibility_contract",
        "status": "full_path_feasibility_contract_passed",
        "config_sha256": file_sha256(config_path),
        "m9c_config_sha256": file_sha256(m9c_config_path),
        "m9d_acceptance_manifest_sha256": file_sha256(m9d_manifest_path),
        "retriever": {
            "repository": retriever["repository"],
            "tag": retriever["tag"],
            "commit": retriever["commit"],
            "asset_id": retriever["asset_id"],
            "asset_name": retriever["asset_name"],
            "asset_size_bytes": retriever["asset_size_bytes"],
            "asset_sha256": retriever["asset_sha256"],
        },
        "counts": {
            "applications": len(config.applications),
            "operation_source_files": len(source_rows),
            "retriever_source_files": len(retriever_source_rows),
            "automation_candidates": len(candidate_rows),
            "information_boundary_rows": len(boundary_rows),
        },
        "quality": {
            "repository_lock_mismatches": 0,
            "retriever_source_mismatches": 0,
            "application_source_mismatches": 0,
            "m9c_identity_mismatches": 0,
            "m9d_identity_mismatches": 0,
            "manual_action_initial_lock_mismatches": 0,
        },
        "manual_actions": {
            "rows": len(manual_rows),
            "status_counts": {
                status: sum(row.get("status") == status for row in manual_rows)
                for status in sorted({str(row.get("status")) for row in manual_rows})
            },
            "initial_sha256": initial_digest,
            "initial_size_in_bytes": initial_size,
            "current_sha256": file_sha256(manual_path),
            "current_size_in_bytes": len(manual_content),
        },
        "planning_guard": {
            "m9d_used_for": "exploratory full-path design only",
            "full_path_contrast_variance_available": False,
            "confirmation_repetition_count_frozen": False,
            "reason": (
                "No independently parameterized full-path PCM prediction exists before "
                "this feasibility gate; aligned PCM/B3 parity has zero method variance "
                "by construction and cannot size that comparison."
            ),
        },
        "accuracy_scoring_started": False,
        "m7_interpretation_changed": False,
        "files": {name: file_sha256(out / name) for name in output_files},
        "environment": environment_manifest(),
    }
    _write_json(out / "contract-manifest.json", manifest)
    return manifest


def record_palladio_retriever_probe(
    config_path: Path,
    application_id: str,
    source_root: Path,
    model_root: Path,
    log_path: Path,
    resource_usage_path: Path,
    exit_code: int,
    out: Path,
) -> Mapping[str, Any]:
    config = load_palladio_fullpath_config(config_path)
    matches = [item for item in config.applications if item.id == application_id]
    if len(matches) != 1:
        raise ValueError(f"unknown application {application_id!r}")
    application = matches[0]
    if _git_head(source_root) != application.commit:
        raise ValueError(f"{application.id}: source checkout commit differs")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code < 0:
        raise ValueError("exit_code must be a nonnegative integer")
    if not log_path.is_file() or not resource_usage_path.is_file():
        raise ValueError("probe log and resource usage must both exist")

    model_rows: list[dict[str, Any]] = []
    if model_root.is_dir():
        for path in sorted(item for item in model_root.rglob("*") if item.is_file()):
            relative = path.relative_to(model_root).as_posix()
            model_rows.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                    "suffix": path.suffix.lower(),
                }
            )
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "model-files.csv",
        ("path", "bytes", "sha256", "suffix"),
        model_rows,
    )
    record: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9e_retriever_probe_record",
        "application": application.id,
        "operation": application.operation,
        "source_repository": application.repository,
        "source_commit": application.commit,
        "retriever_rules": list(application.rules),
        "exit_code": exit_code,
        "model_file_count": len(model_rows),
        "model_bytes": sum(int(item["bytes"]) for item in model_rows),
        "model_suffix_counts": {
            suffix: sum(item["suffix"] == suffix for item in model_rows)
            for suffix in sorted({item["suffix"] for item in model_rows})
        },
        "files": {
            "model-files.csv": file_sha256(out / "model-files.csv"),
            "retriever.log": file_sha256(log_path),
            "resource-usage.txt": file_sha256(resource_usage_path),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "probe-record.json", record)
    return record


def _contains_any(text: str, markers: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def _contains_all(text: str, markers: Sequence[str]) -> bool:
    lowered = text.lower()
    return all(marker.lower() in lowered for marker in markers)


def _numeric_attribute_values(text: str, name: str) -> tuple[float, ...]:
    pattern = re.compile(rf"\b{re.escape(name)}\s*=\s*[\"']([^\"']+)[\"']", re.I)
    result: list[float] = []
    for match in pattern.finditer(text):
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if math.isfinite(value):
            result.append(value)
    return tuple(result)


def _evaluate_application_gates(
    application: FullPathApplication,
    record: Mapping[str, Any],
    model_text: str | Mapping[str, str],
    suffixes: set[str],
) -> Mapping[str, bool]:
    if isinstance(model_text, str):
        # Retain the compact form for hand-checkable unit controls.  The
        # artifact audit below supplies suffix-separated text so a nonzero
        # internal failure cannot masquerade as a communication-link value.
        all_text = model_text
        repository_text = model_text
        resource_environment_text = model_text
    else:
        all_text = "\n".join(model_text.values())
        repository_text = model_text.get(".repository", "")
        resource_environment_text = model_text.get(".resourceenvironment", "")
    mttf = _numeric_attribute_values(resource_environment_text, "MTTF")
    mttr = _numeric_attribute_values(resource_environment_text, "MTTR")
    link_failures = _numeric_attribute_values(
        resource_environment_text, "failureProbability"
    )
    repository_failure_values = _numeric_attribute_values(
        repository_text, "failureProbability"
    )
    return {
        "extractor_exit_zero": record.get("exit_code") == 0,
        "repository_model_present": ".repository" in suffixes,
        "system_model_present": ".system" in suffixes,
        "allocation_model_present": ".allocation" in suffixes,
        "resource_environment_present": ".resourceenvironment" in suffixes,
        "usage_model_present": ".usagemodel" in suffixes,
        "selected_operation_present": _contains_any(
            all_text, application.operation_markers
        ),
        "entry_and_target_present": _contains_any(
            all_text, application.entry_markers
        )
        and _contains_any(all_text, application.target_markers),
        "operation_call_behavior_present": (
            "resourcedemandingseff" in repository_text.lower()
            and "externalcallaction" in repository_text.lower()
        ),
        "two_explicit_replicas_present": _contains_all(
            all_text, application.replica_markers
        ),
        "logical_failure_domains_present": _contains_all(
            all_text, application.domain_markers
        ),
        "reliability_failure_types_present": any(
            marker in repository_text.lower()
            for marker in (
                "softwareinducedfailuretype",
                "hardwareinducedfailuretype",
                "internalfailureoccurrencedescription",
            )
        ),
        "resource_mttf_mttr_present": bool(mttf)
        and bool(mttr)
        and all(value > 0.0 for value in (*mttf, *mttr)),
        "nonzero_link_failure_present": any(
            0.0 < value <= 1.0 for value in link_failures
        ),
        "semantic_success_residual_present": (
            "internalfailureoccurrencedescription" in repository_text.lower()
            and any(0.0 < value <= 1.0 for value in repository_failure_values)
        ),
    }


def audit_palladio_fullpath_probe(
    config_path: Path,
    contract_manifest_path: Path,
    probe_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_palladio_fullpath_config(config_path)
    contract = _load_json(contract_manifest_path, "M9E contract manifest")
    if contract.get("status") != "full_path_feasibility_contract_passed":
        raise ValueError("M9E contract did not pass")
    if contract.get("config_sha256") != file_sha256(config_path):
        raise ValueError("M9E contract/config identity differs")

    gate_specs = {
        str(item["id"]): _mapping(item, "readiness gate")
        for item in config.raw["readiness_gates"]
    }
    gate_rows: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []
    manual_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []

    for application in config.applications:
        application_root = probe_root / application.id
        model_root = application_root / "models"
        record_path = application_root / "probe-record.json"
        record = _load_json(record_path, f"{application.id} probe record")
        if record.get("application") != application.id:
            raise ValueError(f"{application.id}: probe identity differs")
        if record.get("source_commit") != application.commit:
            raise ValueError(f"{application.id}: source commit differs")
        if tuple(record.get("retriever_rules", [])) != application.rules:
            raise ValueError(f"{application.id}: Retriever rules differ")

        listed_rows: list[Mapping[str, Any]] = []
        inventory_path = application_root / "model-files.csv"
        with inventory_path.open(encoding="utf-8", newline="") as source:
            listed_rows = list(csv.DictReader(source))
        if file_sha256(inventory_path) != record["files"]["model-files.csv"]:
            raise ValueError(f"{application.id}: model inventory hash differs")
        actual_paths = sorted(
            path.relative_to(model_root).as_posix()
            for path in model_root.rglob("*")
            if path.is_file()
        )
        listed_paths = sorted(str(item["path"]) for item in listed_rows)
        if actual_paths != listed_paths:
            raise ValueError(f"{application.id}: model inventory paths differ")

        pieces_by_suffix: dict[str, list[str]] = {}
        suffixes: set[str] = set()
        for item in listed_rows:
            relative = _relative_path(item["path"], "model inventory path")
            path = model_root / relative
            expected_sha = _sha256(item["sha256"], "model inventory sha256")
            expected_bytes = int(item["bytes"])
            if path.stat().st_size != expected_bytes or file_sha256(path) != expected_sha:
                raise ValueError(f"{application.id}: model file differs: {relative}")
            suffix = path.suffix.lower()
            suffixes.add(suffix)
            inventory_rows.append(
                {
                    "application": application.id,
                    "path": relative,
                    "bytes": expected_bytes,
                    "sha256": expected_sha,
                    "suffix": suffix,
                }
            )
            if suffix in _MODEL_SUFFIXES:
                pieces_by_suffix.setdefault(suffix, []).append(
                    path.read_text(encoding="utf-8", errors="replace")
                )
        model_text = {
            suffix: "\n".join(pieces)
            for suffix, pieces in pieces_by_suffix.items()
        }
        gates = _evaluate_application_gates(application, record, model_text, suffixes)
        if set(gates) != set(config.required_gates):
            missing = sorted(set(config.required_gates) - set(gates))
            extra = sorted(set(gates) - set(config.required_gates))
            raise ValueError(f"gate implementation/config mismatch: {missing=} {extra=}")
        ready = all(gates[gate] for gate in config.required_gates)
        for gate_id in config.required_gates:
            passed = gates[gate_id]
            spec = gate_specs[gate_id]
            gate_rows.append(
                {
                    "application": application.id,
                    "operation": application.operation,
                    "gate": gate_id,
                    "passed": passed,
                    "required_for_ready": True,
                    "evidence_rule": spec["evidence_rule"],
                }
            )
            if not passed:
                manual_rows.append(
                    {
                        "application": application.id,
                        "operation": application.operation,
                        "failed_gate": gate_id,
                        "manual_completion": spec["manual_completion"],
                        "allowed_provenance": spec["allowed_provenance"],
                    }
                )
        readiness_rows.append(
            {
                "application": application.id,
                "operation": application.operation,
                "extractor_exit_code": record["exit_code"],
                "model_files": len(listed_rows),
                "passed_gates": sum(gates.values()),
                "required_gates": len(config.required_gates),
                "automatic_full_path_ready": ready,
            }
        )

    automatic_ready = all(row["automatic_full_path_ready"] for row in readiness_rows)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "readiness-gates.csv",
        (
            "application",
            "operation",
            "gate",
            "passed",
            "required_for_ready",
            "evidence_rule",
        ),
        gate_rows,
    )
    _write_csv(
        out / "application-readiness.csv",
        (
            "application",
            "operation",
            "extractor_exit_code",
            "model_files",
            "passed_gates",
            "required_gates",
            "automatic_full_path_ready",
        ),
        readiness_rows,
    )
    _write_csv(
        out / "manual-completion-required.csv",
        (
            "application",
            "operation",
            "failed_gate",
            "manual_completion",
            "allowed_provenance",
        ),
        manual_rows,
    )
    _write_csv(
        out / "model-file-inventory.csv",
        ("application", "path", "bytes", "sha256", "suffix"),
        inventory_rows,
    )

    output_files = (
        "readiness-gates.csv",
        "application-readiness.csv",
        "manual-completion-required.csv",
        "model-file-inventory.csv",
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9e_full_path_feasibility_decision",
        "status": "feasibility_audit_completed",
        "config_sha256": file_sha256(config_path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "applications": readiness_rows,
        "automatic_full_path_ready": automatic_ready,
        "comparison_baseline_classification": (
            "automatically_extracted_PCM_candidate"
            if automatic_ready
            else "partially_manual_PCM_required"
        ),
        "manual_completion_rows": len(manual_rows),
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "confirmation_repetition_count_frozen": False,
        "interpretation": {
            "failed_gate_is_an_accuracy_result": False,
            "retriever_represents_all_pcm_automation": False,
            "partially_manual_baseline_must_be_named": not automatic_ready,
            "m7_interpretation_changed": False,
        },
        "files": {name: file_sha256(out / name) for name in output_files},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="palladio-fullpath")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("--config", required=True, type=Path)

    contract = commands.add_parser("audit-contract")
    contract.add_argument("--config", required=True, type=Path)
    contract.add_argument("--retriever-checkout", required=True, type=Path)
    contract.add_argument("--retriever-release-metadata", required=True, type=Path)
    contract.add_argument("--m9c-config", required=True, type=Path)
    contract.add_argument("--m9d-acceptance-root", required=True, type=Path)
    contract.add_argument("--m9d-artifact-metadata", required=True, type=Path)
    contract.add_argument("--upstream-root", required=True, type=Path)
    contract.add_argument("--repository-root", required=True, type=Path)
    contract.add_argument("--out", required=True, type=Path)

    record = commands.add_parser("record-probe")
    record.add_argument("--config", required=True, type=Path)
    record.add_argument("--application", required=True)
    record.add_argument("--source-root", required=True, type=Path)
    record.add_argument("--model-root", required=True, type=Path)
    record.add_argument("--log", required=True, type=Path)
    record.add_argument("--resource-usage", required=True, type=Path)
    record.add_argument("--exit-code", required=True, type=int)
    record.add_argument("--out", required=True, type=Path)

    audit = commands.add_parser("audit-probe")
    audit.add_argument("--config", required=True, type=Path)
    audit.add_argument("--contract-manifest", required=True, type=Path)
    audit.add_argument("--probe-root", required=True, type=Path)
    audit.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        config = load_palladio_fullpath_config(args.config)
        result: Mapping[str, Any] = {
            "status": "valid",
            "experiment_id": config.id,
            "role": "full_path_automation_feasibility_gate",
            "applications": [item.id for item in config.applications],
            "readiness_gates": len(config.required_gates),
            "accuracy_scoring": "forbidden",
            "job_timeout_minutes": config.job_timeout_minutes,
            "retriever_internal_timeout_seconds": config.internal_timeout_seconds,
            "remote_only_full_execution": True,
        }
    elif args.command == "audit-contract":
        result = audit_palladio_fullpath_contract(
            args.config,
            args.retriever_checkout,
            args.retriever_release_metadata,
            args.m9c_config,
            args.m9d_acceptance_root,
            args.m9d_artifact_metadata,
            args.upstream_root,
            args.repository_root,
            args.out,
        )
    elif args.command == "record-probe":
        result = record_palladio_retriever_probe(
            args.config,
            args.application,
            args.source_root,
            args.model_root,
            args.log,
            args.resource_usage,
            args.exit_code,
            args.out,
        )
    elif args.command == "audit-probe":
        result = audit_palladio_fullpath_probe(
            args.config,
            args.contract_manifest,
            args.probe_root,
            args.out,
        )
    else:
        raise AssertionError(f"unhandled command {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
