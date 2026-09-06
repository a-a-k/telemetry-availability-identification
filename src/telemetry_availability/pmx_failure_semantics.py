from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import shlex
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pmx_performability import file_sha256
from .provenance import environment_manifest


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_CORE_SUFFIXES = {
    ".repository",
    ".system",
    ".allocation",
    ".resourceenvironment",
    ".usagemodel",
}


class PMXFailureSemanticsError(ValueError):
    pass


@dataclass(frozen=True)
class PMXFailureSemanticsConfig:
    path: Path
    raw: Mapping[str, Any]
    job_timeout_minutes: int
    confirmation_repeats: int


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PMXFailureSemanticsError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PMXFailureSemanticsError(f"{label} must be a list")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PMXFailureSemanticsError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PMXFailureSemanticsError(f"{label} must be an integer")
    return value


def _positive(value: object, label: str) -> int:
    result = _integer(value, label)
    if result <= 0:
        raise PMXFailureSemanticsError(f"{label} must be positive")
    return result


def _sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if not _SHA256_RE.fullmatch(result):
        raise PMXFailureSemanticsError(f"{label} must be a lowercase SHA-256")
    return result


def _commit(value: object, label: str) -> str:
    result = _string(value, label)
    if not _COMMIT_RE.fullmatch(result):
        raise PMXFailureSemanticsError(f"{label} must be a full lowercase commit")
    return result


def _relative(value: object, label: str) -> Path:
    text = _string(value, label).replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise PMXFailureSemanticsError(f"{label} must remain below its root")
    return path


def _load_json(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise PMXFailureSemanticsError(f"cannot read {label}: {path}") from error


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(path: Path, fields: Sequence[str], rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _audit_file(path: Path, record: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PMXFailureSemanticsError(f"{label} is missing: {path}")
    expected_bytes = _positive(record.get("bytes"), f"{label}.bytes")
    expected_sha = _sha256(record.get("sha256"), f"{label}.sha256")
    actual_bytes = path.stat().st_size
    actual_sha = file_sha256(path)
    if actual_bytes != expected_bytes or actual_sha != expected_sha:
        raise PMXFailureSemanticsError(f"{label} byte identity differs")
    return {
        "path": str(path),
        "bytes": actual_bytes,
        "sha256": actual_sha,
        "matches": True,
    }


def load_pmx_failure_semantics_config(
    path: str | Path,
) -> PMXFailureSemanticsConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9I config"), "root")
    expected = {
        "schema_version": 1,
        "id": "m9i_pmx_failure_semantics_source_diagnostic",
        "status": "frozen_before_first_m9i_remote_audit",
        "diagnostic_only": True,
        "dynamic_pmx_invocation": "forbidden",
        "accuracy_scoring": "forbidden",
        "m7_evidence_access": "forbidden",
        "new_live_collection": "forbidden",
    }
    for key, value in expected.items():
        if root.get(key) != value:
            raise PMXFailureSemanticsError(f"M9I {key} differs from frozen value")

    priority = _object(root.get("scientific_priority"), "scientific_priority")
    if dict(priority) != {
        "method": "PMX_performability_extension",
        "persists_if_application_cost_is_high": True,
        "tested_binary_represents_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "m7_interpretation_changes": False,
    }:
        raise PMXFailureSemanticsError("scientific-priority guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    m9h = _object(evidence.get("m9h"), "evidence.m9h")
    if (
        m9h.get("run_id") != 34050900275
        or _commit(m9h.get("head_sha"), "m9h.head_sha")
        != "5ec6a33ce51d426ac412006b418632986db4cc9a"
        or m9h.get("conclusion") != "success"
        or m9h.get("decision_status")
        != "pmx_source_entrypoint_reproduced_failure_semantics_unresolved"
    ):
        raise PMXFailureSemanticsError("accepted M9H anchor differs")
    artifacts = _object(m9h.get("artifacts"), "m9h.artifacts")
    if set(artifacts) != {"source_contract", "probe", "decision"}:
        raise PMXFailureSemanticsError("M9I requires all three M9H artifacts")
    for role, value in artifacts.items():
        record = _object(value, f"m9h.artifacts.{role}")
        _positive(record.get("id"), f"{role}.id")
        _positive(record.get("size_in_bytes"), f"{role}.size_in_bytes")
        _sha256(record.get("sha256"), f"{role}.sha256")
        _relative(record.get("manifest_path"), f"{role}.manifest_path")
        _positive(record.get("manifest_bytes"), f"{role}.manifest_bytes")
        _sha256(record.get("manifest_sha256"), f"{role}.manifest_sha256")

    demonstration = _object(evidence.get("demonstration"), "demonstration")
    if _commit(demonstration.get("commit"), "demonstration.commit") != (
        "9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2"
    ):
        raise PMXFailureSemanticsError("demonstration commit differs")
    jar = _object(demonstration.get("jar"), "demonstration.jar")
    if jar.get("bytes") != 65729095 or _sha256(
        jar.get("sha256"), "jar.sha256"
    ) != "befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013":
        raise PMXFailureSemanticsError("PMX JAR lock differs")

    source_audit = _object(root.get("source_audit"), "source_audit")
    if source_audit.get("extract_all_java_sources") is not True:
        raise PMXFailureSemanticsError("complete Java source census is required")
    bundles = _list(source_audit.get("bundles"), "source_audit.bundles")
    if len(bundles) != 4:
        raise PMXFailureSemanticsError("exactly four source bundles are required")
    bundle_ids: set[str] = set()
    for value in bundles:
        bundle = _object(value, "source bundle")
        bundle_id = _string(bundle.get("id"), "bundle.id")
        if bundle_id in bundle_ids:
            raise PMXFailureSemanticsError("source bundle IDs must be unique")
        bundle_ids.add(bundle_id)
        _relative(bundle.get("path"), "bundle.path")
        _positive(bundle.get("bytes"), "bundle.bytes")
        _sha256(bundle.get("sha256"), "bundle.sha256")
    required = _list(
        source_audit.get("required_sources"), "source_audit.required_sources"
    )
    if len(required) != 4:
        raise PMXFailureSemanticsError("exactly four pinned sources are required")
    for value in required:
        source = _object(value, "required source")
        if source.get("bundle_id") not in bundle_ids:
            raise PMXFailureSemanticsError("required source names an unknown bundle")
        _relative(source.get("path"), "required source.path")
        _positive(source.get("bytes"), "required source.bytes")
        _sha256(source.get("sha256"), "required source.sha256")
        markers = _list(source.get("markers"), "required source.markers")
        if not markers or not all(isinstance(item, str) and item for item in markers):
            raise PMXFailureSemanticsError("required source markers differ")
    vocabulary = _list(source_audit.get("line_vocabulary"), "line_vocabulary")
    if vocabulary != [
        "error",
        "failure",
        "success",
        "status",
        "getValue",
        "setFailureProbability",
        "countOfFails",
        "countOfSuccesses",
    ]:
        raise PMXFailureSemanticsError("source line vocabulary differs")

    boundary = _object(root.get("retained_boundary"), "retained_boundary")
    runs_csv = _object(boundary.get("entrypoint_runs_csv"), "entrypoint_runs_csv")
    _relative(runs_csv.get("path"), "entrypoint_runs_csv.path")
    _positive(runs_csv.get("bytes"), "entrypoint_runs_csv.bytes")
    _sha256(runs_csv.get("sha256"), "entrypoint_runs_csv.sha256")
    repeats = _positive(boundary.get("confirmation_repeats"), "confirmation repeats")
    if repeats != 2:
        raise PMXFailureSemanticsError("M9I requires two retained confirmations")
    if boundary.get("conditions") != ["published_original", "single_error_control"]:
        raise PMXFailureSemanticsError("retained conditions differ")
    target = _object(boundary.get("target"), "retained_boundary.target")
    if (
        target.get("trace_id") != "af0f0df51dfdfc3ca3e2eae9b00b114e"
        or target.get("span_id") != "b2adec3b558fff51"
        or target.get("operation") != "VisitResource.read"
        or target.get("tag") != {"key": "error", "type": "bool", "value": "true"}
        or target.get("unchanged_error_tags") != 0
        or target.get("control_error_tags") != 1
        or target.get("eligible_operation_occurrences") != 10
        or target.get("expected_failure_probability") != 0.1
    ):
        raise PMXFailureSemanticsError("retained target contract differs")
    accepted = _object(boundary.get("accepted_observations"), "accepted_observations")
    if accepted.get("success_aggregates") != [10, 10, 9, 10, 1] or accepted.get(
        "failure_aggregates"
    ) != [None, None, None, None, None]:
        raise PMXFailureSemanticsError("retained stdout oracle differs")

    decision = _object(root.get("decision"), "decision")
    if decision.get("new_dynamic_control_allowed_in_m9i") is not False:
        raise PMXFailureSemanticsError("M9I must forbid dynamic controls")
    if decision.get("next_milestone_if_evidence_passes") != (
        "m9j_source_derived_error_mapping_controls"
    ):
        raise PMXFailureSemanticsError("next-milestone rule differs")

    workflow = _object(root.get("workflow"), "workflow")
    if (
        workflow.get("jobs") != 3
        or workflow.get("job_timeout_minutes") != 360
        or workflow.get("source_downloads_only_in_github_actions") is not True
        or workflow.get("dynamic_pmx_runs") != 0
        or workflow.get("artifact_retention_days") != 90
    ):
        raise PMXFailureSemanticsError("workflow contract differs")
    guards = _object(root.get("interpretation_guardrails"), "guardrails")
    if any(value is not False for value in guards.values()):
        raise PMXFailureSemanticsError("all M9I interpretation guards must be false")

    return PMXFailureSemanticsConfig(
        path=config_path,
        raw=root,
        job_timeout_minutes=360,
        confirmation_repeats=repeats,
    )


def validate_repository(config_path: str | Path) -> Mapping[str, Any]:
    config = load_pmx_failure_semantics_config(config_path)
    root = config.path.resolve().parents[1]
    rows: list[dict[str, Any]] = []
    for value in _list(config.raw.get("repository_locks"), "repository_locks"):
        record = _object(value, "repository lock")
        relative = _relative(record.get("path"), "repository lock.path")
        rows.append(_audit_file(root / relative, record, str(relative)))
    manual = root / _relative(config.raw.get("manual_actions_log"), "manual log")
    if not manual.is_file() or manual.stat().st_size <= 100:
        raise PMXFailureSemanticsError("M9I manual-actions log is missing or empty")
    return {
        "schema_version": 1,
        "kind": "m9i_repository_validation",
        "status": "m9i_repository_contract_valid",
        "config_sha256": file_sha256(config.path),
        "repository_locks": rows,
        "manual_log": str(manual.relative_to(root)),
        "dynamic_pmx_runs": 0,
        "job_timeout_minutes": config.job_timeout_minutes,
    }


def audit_embedded_sources(
    config_path: str | Path, jar_path: Path, out: Path
) -> Mapping[str, Any]:
    config = load_pmx_failure_semantics_config(config_path)
    jar_record = _object(
        _object(config.raw["evidence"], "evidence")["demonstration"]["jar"],
        "jar",
    )
    _audit_file(jar_path, jar_record, "PMX main.jar")
    source_spec = _object(config.raw["source_audit"], "source_audit")
    bundles = {
        str(_object(value, "bundle")["id"]): _object(value, "bundle")
        for value in source_spec["bundles"]
    }
    required_by_pair = {
        (str(_object(value, "required source")["bundle_id"]), str(_object(value, "required source")["path"])): _object(value, "required source")
        for value in source_spec["required_sources"]
    }
    vocabulary = [str(value) for value in source_spec["line_vocabulary"]]
    lowered_vocabulary = [value.lower() for value in vocabulary]
    bundle_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    observed_required: set[tuple[str, str]] = set()
    out.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(jar_path) as outer:
        outer_names = set(outer.namelist())
        for bundle_id, bundle in bundles.items():
            bundle_path = str(bundle["path"])
            if bundle_path not in outer_names:
                raise PMXFailureSemanticsError(
                    f"embedded source bundle is missing: {bundle_path}"
                )
            bundle_bytes = outer.read(bundle_path)
            if (
                len(bundle_bytes) != bundle["bytes"]
                or _bytes_sha256(bundle_bytes) != bundle["sha256"]
            ):
                raise PMXFailureSemanticsError(
                    f"embedded source bundle identity differs: {bundle_id}"
                )
            with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as nested:
                java_names = sorted(
                    name
                    for name in nested.namelist()
                    if name.startswith("OSGI-OPT/src/") and name.endswith(".java")
                )
                if not java_names:
                    raise PMXFailureSemanticsError(
                        f"embedded source bundle has no Java source: {bundle_id}"
                    )
                for source_path in java_names:
                    source_bytes = nested.read(source_path)
                    source_text = source_bytes.decode("utf-8")
                    pair = (bundle_id, source_path)
                    required = required_by_pair.get(pair)
                    if required is not None:
                        if (
                            len(source_bytes) != required["bytes"]
                            or _bytes_sha256(source_bytes) != required["sha256"]
                        ):
                            raise PMXFailureSemanticsError(
                                f"pinned source identity differs: {required['id']}"
                            )
                        missing = [
                            marker
                            for marker in required["markers"]
                            if marker not in source_text
                        ]
                        if missing:
                            raise PMXFailureSemanticsError(
                                f"pinned source markers differ: {required['id']}: {missing}"
                            )
                        observed_required.add(pair)

                    relative_source = _relative(
                        source_path.removeprefix("OSGI-OPT/src/"),
                        "embedded source output path",
                    )
                    output_path = out / "sources" / bundle_id / relative_source
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(source_bytes)
                    matching_lines = 0
                    for line_number, line in enumerate(source_text.splitlines(), start=1):
                        lowered = line.lower()
                        matches = [
                            vocabulary[index]
                            for index, token in enumerate(lowered_vocabulary)
                            if token in lowered
                        ]
                        if matches:
                            matching_lines += 1
                            evidence_rows.append(
                                {
                                    "bundle_id": bundle_id,
                                    "source_path": source_path,
                                    "line_number": line_number,
                                    "matched_vocabulary": "|".join(matches),
                                    "line": line.rstrip(),
                                }
                            )
                    source_rows.append(
                        {
                            "bundle_id": bundle_id,
                            "source_path": source_path,
                            "bytes": len(source_bytes),
                            "sha256": _bytes_sha256(source_bytes),
                            "required_anchor": required is not None,
                            "required_id": required["id"] if required else "",
                            "vocabulary_lines": matching_lines,
                        }
                    )
            bundle_rows.append(
                {
                    "bundle_id": bundle_id,
                    "path": bundle_path,
                    "bytes": len(bundle_bytes),
                    "sha256": _bytes_sha256(bundle_bytes),
                    "java_sources": len(java_names),
                    "matches": True,
                }
            )

    missing_required = sorted(set(required_by_pair) - observed_required)
    if missing_required:
        raise PMXFailureSemanticsError(
            f"required embedded sources are missing: {missing_required}"
        )
    _write_csv(
        out / "bundle-inventory.csv",
        ["bundle_id", "path", "bytes", "sha256", "java_sources", "matches"],
        bundle_rows,
    )
    _write_csv(
        out / "source-inventory.csv",
        [
            "bundle_id",
            "source_path",
            "bytes",
            "sha256",
            "required_anchor",
            "required_id",
            "vocabulary_lines",
        ],
        source_rows,
    )
    _write_csv(
        out / "source-vocabulary-lines.csv",
        [
            "bundle_id",
            "source_path",
            "line_number",
            "matched_vocabulary",
            "line",
        ],
        evidence_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9i_embedded_source_audit",
        "status": "exact_embedded_failure_sources_recovered",
        "config_sha256": file_sha256(config.path),
        "jar": {
            "bytes": jar_path.stat().st_size,
            "sha256": file_sha256(jar_path),
        },
        "bundles_audited": len(bundle_rows),
        "java_sources_recovered": len(source_rows),
        "required_source_anchors_passed": len(observed_required),
        "vocabulary_lines": len(evidence_rows),
        "complete_source_census": True,
        "dynamic_pmx_invocations": 0,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "bundle-inventory.csv",
                "source-inventory.csv",
                "source-vocabulary-lines.csv",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "source-audit-manifest.json", manifest)
    return manifest


def _audit_artifact_metadata(
    metadata_path: Path, record: Mapping[str, Any], role: str, run_id: int, head_sha: str
) -> Mapping[str, Any]:
    metadata = _object(_load_json(metadata_path, f"{role} artifact metadata"), role)
    checks = {
        "id": metadata.get("id") == record["id"],
        "name": metadata.get("name") == record["name"],
        "size": metadata.get("size_in_bytes") == record["size_in_bytes"],
        "digest": metadata.get("digest") == f"sha256:{record['sha256']}",
        "not_expired": metadata.get("expired") is False,
    }
    workflow_run = _object(metadata.get("workflow_run"), f"{role}.workflow_run")
    checks["run"] = workflow_run.get("id") == run_id
    checks["commit"] = workflow_run.get("head_sha") == head_sha
    expires = _string(metadata.get("expires_at"), f"{role}.expires_at")
    try:
        expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    except ValueError as error:
        raise PMXFailureSemanticsError(f"{role} expiry is invalid") from error
    checks["future_expiry"] = expires_at > datetime.now(timezone.utc)
    if not all(checks.values()):
        raise PMXFailureSemanticsError(
            f"{role} artifact metadata differs: {checks}"
        )
    return {"checks": checks, "metadata": metadata}


def _trace_from_options(run_root: Path) -> tuple[str, Path]:
    options_path = run_root / "Options.txt"
    if not options_path.is_file():
        raise PMXFailureSemanticsError(f"retained options are missing: {options_path}")
    tokens = shlex.split(options_path.read_text(encoding="utf-8"), posix=True)
    if tokens.count("-i") != 1:
        raise PMXFailureSemanticsError("retained options must contain one -i")
    position = tokens.index("-i")
    if position + 1 >= len(tokens):
        raise PMXFailureSemanticsError("retained -i has no trace path")
    relative_text = tokens[position + 1]
    relative = _relative(relative_text, "retained trace path")
    trace_path = run_root / relative
    if not trace_path.is_file():
        raise PMXFailureSemanticsError(f"retained trace is missing: {trace_path}")
    return relative_text, trace_path


def _trace_error_facts(
    trace_path: Path, target: Mapping[str, Any]
) -> tuple[dict[str, Any], Mapping[str, Any]]:
    payload = _object(_load_json(trace_path, "retained trace"), "trace root")
    traces = _list(payload.get("data"), "trace data")
    error_tags: list[Mapping[str, Any]] = []
    target_span: Mapping[str, Any] | None = None
    for trace_value in traces:
        trace = _object(trace_value, "trace")
        for span_value in _list(trace.get("spans"), "trace spans"):
            span = _object(span_value, "span")
            tags = _list(span.get("tags"), "span tags")
            for tag_value in tags:
                tag = _object(tag_value, "span tag")
                if tag.get("key") == "error":
                    error_tags.append(tag)
            if (
                trace.get("traceID") == target["trace_id"]
                and span.get("spanID") == target["span_id"]
            ):
                if target_span is not None:
                    raise PMXFailureSemanticsError("retained target span is duplicated")
                target_span = span
    if target_span is None:
        raise PMXFailureSemanticsError("retained target span is missing")
    if target_span.get("operationName") != target["operation"]:
        raise PMXFailureSemanticsError("retained target operation differs")
    target_tags = [
        _object(value, "target tag")
        for value in _list(target_span.get("tags"), "target tags")
        if isinstance(value, Mapping) and value.get("key") == "error"
    ]
    facts = {
        "error_tags": len(error_tags),
        "target_error_tags": len(target_tags),
        "target_error_tag": dict(target_tags[0]) if len(target_tags) == 1 else None,
        "target_error_value_python_type": (
            type(target_tags[0].get("value")).__name__ if len(target_tags) == 1 else ""
        ),
        "trace_bytes": trace_path.stat().st_size,
        "trace_sha256": file_sha256(trace_path),
    }
    return facts, payload


def _without_error_tags(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    result = copy.deepcopy(payload)
    for trace in result.get("data", []):
        for span in trace.get("spans", []):
            span["tags"] = [tag for tag in span.get("tags", []) if tag.get("key") != "error"]
    return result


def _stdout_aggregates(path: Path) -> tuple[list[int], list[str | None]]:
    if not path.is_file():
        raise PMXFailureSemanticsError(f"retained stdout is missing: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    success = [int(value) for value in re.findall(r"(?m)^Success:\s*(\d+)\s*$", text)]
    raw_failures = re.findall(r"(?m)^Failure:\s*(.*?)\s*$", text)
    failures: list[str | None] = [
        None if value.strip().lower() == "null" else value.strip()
        for value in raw_failures
    ]
    return success, failures


def audit_retained_boundary(
    config_path: str | Path,
    source_metadata: Path,
    probe_metadata: Path,
    decision_metadata: Path,
    source_root: Path,
    probe_root: Path,
    decision_root: Path,
    source_audit_manifest: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_failure_semantics_config(config_path)
    evidence = _object(config.raw["evidence"], "evidence")
    m9h = _object(evidence["m9h"], "m9h")
    artifact_specs = _object(m9h["artifacts"], "m9h.artifacts")
    roots = {
        "source_contract": source_root,
        "probe": probe_root,
        "decision": decision_root,
    }
    metadata_paths = {
        "source_contract": source_metadata,
        "probe": probe_metadata,
        "decision": decision_metadata,
    }
    metadata_audits: dict[str, Any] = {}
    manifest_audits: dict[str, Any] = {}
    for role in ("source_contract", "probe", "decision"):
        record = _object(artifact_specs[role], f"artifact.{role}")
        metadata_audits[role] = _audit_artifact_metadata(
            metadata_paths[role], record, role, int(m9h["run_id"]), str(m9h["head_sha"])
        )
        manifest_record = {
            "bytes": record["manifest_bytes"],
            "sha256": record["manifest_sha256"],
        }
        manifest_audits[role] = _audit_file(
            roots[role] / _relative(record["manifest_path"], "manifest path"),
            manifest_record,
            f"{role} manifest",
        )

    source_manifest = _object(
        _load_json(source_audit_manifest, "M9I source audit manifest"),
        "source audit manifest",
    )
    if (
        source_manifest.get("config_sha256") != file_sha256(config.path)
        or source_manifest.get("status") != "exact_embedded_failure_sources_recovered"
        or source_manifest.get("dynamic_pmx_invocations") != 0
    ):
        raise PMXFailureSemanticsError("M9I source audit manifest differs")

    probe_manifest = _object(
        _load_json(probe_root / "entrypoint-probe-manifest.json", "M9H probe manifest"),
        "M9H probe manifest",
    )
    decision_manifest = _object(
        _load_json(decision_root / "decision-manifest.json", "M9H decision manifest"),
        "M9H decision manifest",
    )
    if probe_manifest.get("status") != "pmx_source_entrypoint_reproduced_failure_control_unresolved":
        raise PMXFailureSemanticsError("retained M9H probe status differs")
    if decision_manifest.get("status") != m9h["decision_status"]:
        raise PMXFailureSemanticsError("retained M9H decision status differs")

    boundary = _object(config.raw["retained_boundary"], "retained_boundary")
    runs_record = _object(boundary["entrypoint_runs_csv"], "entrypoint_runs_csv")
    runs_path = probe_root / _relative(runs_record["path"], "entrypoint runs path")
    _audit_file(runs_path, runs_record, "M9H entrypoint runs CSV")
    with runs_path.open(encoding="utf-8", newline="") as source:
        run_rows = list(csv.DictReader(source))
    confirmations = {
        (row["condition"], int(row["repeat"])): row
        for row in run_rows
        if row["phase"] == "confirmation"
    }
    expected_keys = {
        (condition, repeat)
        for condition in boundary["conditions"]
        for repeat in range(1, config.confirmation_repeats + 1)
    }
    if set(confirmations) != expected_keys:
        raise PMXFailureSemanticsError("retained confirmation matrix differs")

    target = _object(boundary["target"], "target")
    accepted = _object(boundary["accepted_observations"], "accepted_observations")
    row_output: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    trace_payloads: dict[tuple[str, int], Mapping[str, Any]] = {}
    stdout_hashes: dict[tuple[str, int], str] = {}
    raw_mutation_present = True
    complete_execution = True
    stdout_failure_distinction = False
    pcm_failure_distinction = False

    for condition, repeat in sorted(expected_keys):
        run_root = probe_root / "raw" / "confirmation" / condition / f"repeat-{repeat}"
        trace_relative, trace_path = _trace_from_options(run_root)
        trace_facts, trace_payload = _trace_error_facts(trace_path, target)
        trace_payloads[(condition, repeat)] = trace_payload
        expected_error_tags = (
            target["unchanged_error_tags"]
            if condition == "published_original"
            else target["control_error_tags"]
        )
        if trace_facts["error_tags"] != expected_error_tags:
            raise PMXFailureSemanticsError(
                f"{condition}/{repeat}: retained error-tag count differs"
            )
        if condition == "single_error_control":
            raw_mutation_present = raw_mutation_present and (
                trace_facts["target_error_tag"] == target["tag"]
                and trace_facts["target_error_value_python_type"] == "str"
            )

        stdout_path = run_root / "stdout.log"
        log_path = run_root / "results" / "log.txt"
        if not log_path.is_file():
            raise PMXFailureSemanticsError(f"retained PMX log is missing: {log_path}")
        success_values, failure_values = _stdout_aggregates(stdout_path)
        if success_values != accepted["success_aggregates"]:
            raise PMXFailureSemanticsError(
                f"{condition}/{repeat}: retained success aggregates differ"
            )
        if failure_values != accepted["failure_aggregates"]:
            stdout_failure_distinction = True
        stdout_hashes[(condition, repeat)] = file_sha256(stdout_path)

        csv_row = confirmations[(condition, repeat)]
        csv_complete = (
            csv_row["source_command_entered"] == "True"
            and csv_row["log_sequence_complete"] == "True"
            and csv_row["semantic_signature"]
            == boundary["historical_semantic_signature"]
            and int(csv_row["internal_failure_occurrence_count"]) == 0
            and int(csv_row["software_failure_type_count"]) == 0
        )
        complete_execution = complete_execution and csv_complete
        pcm_failure_distinction = pcm_failure_distinction or (
            int(csv_row["internal_failure_occurrence_count"]) > 0
            or int(csv_row["software_failure_type_count"]) > 0
            or bool(csv_row["nonzero_repository_failure_probabilities"])
        )
        model_files = sorted(
            path
            for path in (run_root / "results").iterdir()
            if path.is_file() and path.suffix.lower() in _CORE_SUFFIXES
        )
        if {path.suffix.lower() for path in model_files} != _CORE_SUFFIXES:
            raise PMXFailureSemanticsError(
                f"{condition}/{repeat}: retained core model set differs"
            )
        for path in [run_root / "Options.txt", trace_path, stdout_path, log_path, *model_files]:
            file_rows.append(
                {
                    "condition": condition,
                    "repeat": repeat,
                    "path": path.relative_to(probe_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
        row_output.append(
            {
                "condition": condition,
                "repeat": repeat,
                "trace_path": trace_relative,
                "trace_bytes": trace_facts["trace_bytes"],
                "trace_sha256": trace_facts["trace_sha256"],
                "error_tags": trace_facts["error_tags"],
                "target_error_tags": trace_facts["target_error_tags"],
                "target_value_python_type": trace_facts[
                    "target_error_value_python_type"
                ],
                "success_aggregates": "|".join(map(str, success_values)),
                "failure_aggregates": "|".join(
                    "null" if value is None else value for value in failure_values
                ),
                "stdout_sha256": stdout_hashes[(condition, repeat)],
                "semantic_signature": csv_row["semantic_signature"],
                "command_and_log_complete": csv_complete,
                "internal_failure_occurrences": int(
                    csv_row["internal_failure_occurrence_count"]
                ),
                "software_failure_types": int(csv_row["software_failure_type_count"]),
            }
        )

    for repeat in range(1, config.confirmation_repeats + 1):
        original = trace_payloads[("published_original", repeat)]
        control = trace_payloads[("single_error_control", repeat)]
        if _without_error_tags(control) != original:
            raw_mutation_present = False
        if stdout_hashes[("published_original", repeat)] != stdout_hashes[
            ("single_error_control", repeat)
        ]:
            stdout_failure_distinction = True
    stdout_equal = not stdout_failure_distinction
    if stdout_equal is not accepted["stdout_equal_across_conditions"]:
        raise PMXFailureSemanticsError("retained stdout equality differs")
    if not raw_mutation_present:
        raise PMXFailureSemanticsError("the retained raw mutation is not exact")
    if not complete_execution:
        raise PMXFailureSemanticsError("the retained command/log/model path is incomplete")
    if pcm_failure_distinction:
        raise PMXFailureSemanticsError("retained PCM unexpectedly distinguishes control")

    earliest = "collapse_between_raw_tag_and_internal_operation_failure_aggregate"
    _write_csv(
        out / "boundary-runs.csv",
        [
            "condition",
            "repeat",
            "trace_path",
            "trace_bytes",
            "trace_sha256",
            "error_tags",
            "target_error_tags",
            "target_value_python_type",
            "success_aggregates",
            "failure_aggregates",
            "stdout_sha256",
            "semantic_signature",
            "command_and_log_complete",
            "internal_failure_occurrences",
            "software_failure_types",
        ],
        row_output,
    )
    _write_csv(
        out / "boundary-files.csv",
        ["condition", "repeat", "path", "bytes", "sha256"],
        file_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9i_retained_failure_boundary_audit",
        "status": "exact_retained_failure_collapse_boundary_recovered",
        "config_sha256": file_sha256(config.path),
        "m9h_artifact_metadata": metadata_audits,
        "m9h_manifest_audits": manifest_audits,
        "source_audit_sha256": file_sha256(source_audit_manifest),
        "confirmation_runs_audited": len(row_output),
        "raw_mutation_present": raw_mutation_present,
        "control_value_json_type": "string",
        "complete_execution": complete_execution,
        "stdout_equal_across_conditions": stdout_equal,
        "stdout_failure_distinction": stdout_failure_distinction,
        "pcm_failure_distinction": pcm_failure_distinction,
        "earliest_observed_collapse": earliest,
        "dynamic_pmx_invocations": 0,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "files": {
            "boundary-runs.csv": file_sha256(out / "boundary-runs.csv"),
            "boundary-files.csv": file_sha256(out / "boundary-files.csv"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "boundary-audit-manifest.json", manifest)
    return manifest


def decide(
    config_path: str | Path,
    source_manifest_path: Path,
    boundary_manifest_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_failure_semantics_config(config_path)
    source = _object(_load_json(source_manifest_path, "source manifest"), "source")
    boundary = _object(
        _load_json(boundary_manifest_path, "boundary manifest"), "boundary"
    )
    config_hash = file_sha256(config.path)
    source_pass = (
        source.get("config_sha256") == config_hash
        and source.get("status") == "exact_embedded_failure_sources_recovered"
        and source.get("bundles_audited") == 4
        and source.get("required_source_anchors_passed") == 4
        and source.get("complete_source_census") is True
        and source.get("dynamic_pmx_invocations") == 0
    )
    boundary_pass = (
        boundary.get("config_sha256") == config_hash
        and boundary.get("status")
        == "exact_retained_failure_collapse_boundary_recovered"
        and boundary.get("raw_mutation_present") is True
        and boundary.get("complete_execution") is True
        and boundary.get("confirmation_runs_audited") == 4
        and boundary.get("dynamic_pmx_invocations") == 0
    )
    decision_rules = _object(config.raw["decision"], "decision")
    if not source_pass or not boundary_pass:
        status = str(decision_rules["evidence_mismatch"])
        earliest = "not_classified"
        next_milestone = "repeat_m9i_after_integrity_repair"
        technical_evidence_accepted = False
    else:
        stdout_failure = bool(boundary.get("stdout_failure_distinction"))
        pcm_failure = bool(boundary.get("pcm_failure_distinction"))
        if not stdout_failure and not pcm_failure:
            earliest = str(
                decision_rules[
                    "raw_mutation_and_complete_execution_without_stdout_failure"
                ]
            )
        elif stdout_failure and not pcm_failure:
            earliest = str(decision_rules["stdout_failure_without_pcm_failure"])
        else:
            earliest = str(decision_rules["stdout_and_pcm_failure"])
        status = "pmx_exact_failure_sources_and_collapse_boundary_recovered"
        next_milestone = str(decision_rules["next_milestone_if_evidence_passes"])
        technical_evidence_accepted = True

    rows = [
        {
            "question": "exact_source_census_recovered",
            "value": source_pass,
            "interpretation": "four byte-pinned bundles and four prior source anchors",
        },
        {
            "question": "exact_raw_mutation_present",
            "value": boundary.get("raw_mutation_present", False),
            "interpretation": "one retained tag on the frozen trace and span",
        },
        {
            "question": "command_log_model_path_complete",
            "value": boundary.get("complete_execution", False),
            "interpretation": "launcher failure is not the M9H control explanation",
        },
        {
            "question": "stdout_distinguishes_control",
            "value": boundary.get("stdout_failure_distinction", False),
            "interpretation": "internal operation aggregate boundary",
        },
        {
            "question": "pcm_distinguishes_control",
            "value": boundary.get("pcm_failure_distinction", False),
            "interpretation": "downstream failure occurrence and probability",
        },
        {
            "question": "dynamic_control_run_in_m9i",
            "value": False,
            "interpretation": "a source-derived control must be frozen prospectively",
        },
    ]
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "decision-matrix.csv",
        ["question", "value", "interpretation"],
        rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9i_pmx_failure_semantics_decision",
        "status": status,
        "config_sha256": config_hash,
        "source_manifest_sha256": file_sha256(source_manifest_path),
        "boundary_manifest_sha256": file_sha256(boundary_manifest_path),
        "technical_evidence_accepted": technical_evidence_accepted,
        "exact_source_census_recovered": source_pass,
        "retained_boundary_recovered": boundary_pass,
        "earliest_observed_collapse": earliest,
        "unique_root_cause_claimed_by_machine_decision": False,
        "next_milestone": next_milestone,
        "dynamic_pmx_invocations": 0,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "pmx_scientific_priority_retained": True,
        "tested_binary_represents_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "manual_pcm_credited_as_pmx": False,
        "m7_interpretation_changed": False,
        "files": {"decision-matrix.csv": file_sha256(out / "decision-matrix.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M9I PMX failure-semantics audit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--config", type=Path, required=True)

    source = subparsers.add_parser("audit-sources")
    source.add_argument("--config", type=Path, required=True)
    source.add_argument("--jar", type=Path, required=True)
    source.add_argument("--out", type=Path, required=True)

    boundary = subparsers.add_parser("audit-boundary")
    boundary.add_argument("--config", type=Path, required=True)
    boundary.add_argument("--source-metadata", type=Path, required=True)
    boundary.add_argument("--probe-metadata", type=Path, required=True)
    boundary.add_argument("--decision-metadata", type=Path, required=True)
    boundary.add_argument("--source-root", type=Path, required=True)
    boundary.add_argument("--probe-root", type=Path, required=True)
    boundary.add_argument("--decision-root", type=Path, required=True)
    boundary.add_argument("--source-audit-manifest", type=Path, required=True)
    boundary.add_argument("--out", type=Path, required=True)

    decision = subparsers.add_parser("decide")
    decision.add_argument("--config", type=Path, required=True)
    decision.add_argument("--source-manifest", type=Path, required=True)
    decision.add_argument("--boundary-manifest", type=Path, required=True)
    decision.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        payload = validate_repository(args.config)
    elif args.command == "audit-sources":
        payload = audit_embedded_sources(args.config, args.jar, args.out)
    elif args.command == "audit-boundary":
        payload = audit_retained_boundary(
            args.config,
            args.source_metadata,
            args.probe_metadata,
            args.decision_metadata,
            args.source_root,
            args.probe_root,
            args.decision_root,
            args.source_audit_manifest,
            args.out,
        )
    else:
        payload = decide(
            args.config, args.source_manifest, args.boundary_manifest, args.out
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
