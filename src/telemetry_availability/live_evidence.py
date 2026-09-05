from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .live_evidence_config import EvidenceBoundaryConfig, EvidenceProfile
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class EvidenceBoundaryError(RuntimeError):
    """Raised when pilot evidence cannot be separated without leakage."""


LEARNER_REQUEST_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "request_id",
    "trace_id",
    "operation",
    "branch_class",
    "started_at",
    "completed_at",
    "semantic_success",
    "timed_out",
    "trace_present",
    "span_count",
    "services",
    "target_replicas",
    "target_replica_count",
)

LEARNER_HEALTH_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "observed_at",
    "elapsed_seconds",
    "proxy_observed",
    "proxy_running",
    "proxy_paused",
    "proxy_health",
    "replica_a_observed",
    "replica_a_running",
    "replica_a_paused",
    "replica_a_health",
    "replica_a_network_count",
    "replica_a_backend_status",
    "replica_a_backend_check_status",
    "replica_b_observed",
    "replica_b_running",
    "replica_b_paused",
    "replica_b_health",
    "replica_b_network_count",
    "replica_b_backend_status",
    "replica_b_backend_check_status",
)

TOPOLOGY_EDGE_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "source_service",
    "target_service",
    "supporting_spans",
    "supporting_traces",
)

EVALUATOR_REQUEST_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "request_id",
    "operation",
    "branch_class",
    "started_at",
    "completed_at",
    "semantic_success",
    "timed_out",
)

CELL_SUMMARY_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "calibration_requests",
    "calibration_semantic_successes",
    "calibration_traces_present",
    "calibration_traces_parsed",
    "calibration_trace_link_fraction",
    "calibration_health_ticks",
    "topology_edges",
    "replica_a_trace_assignments",
    "replica_b_trace_assignments",
    "test_requests_sequestered",
    "test_health_ticks_sequestered",
    "quality_failures",
    "usable",
)


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    span_id: str
    parent_span_id: str
    service: str
    operation: str
    target_replica: str


@dataclass(frozen=True)
class ParsedTraceEvidence:
    spans_by_trace: dict[str, tuple[SpanRecord, ...]]
    invalid_records: int
    duplicate_spans: int
    unknown_target_instances: int


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return [dict(row) for row in csv.DictReader(source)]


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _attributes(values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(values, list):
        return result
    for item in values:
        if not isinstance(item, dict) or "key" not in item:
            continue
        value = item.get("value", {})
        if not isinstance(value, dict):
            continue
        scalar = next(
            (
                value[key]
                for key in (
                    "stringValue",
                    "boolValue",
                    "intValue",
                    "doubleValue",
                    "bytesValue",
                )
                if key in value
            ),
            None,
        )
        result[str(item["key"])] = scalar
    return result


def _jaeger_attributes(values: Any) -> dict[str, Any]:
    if not isinstance(values, list):
        return {}
    return {
        str(item["key"]): item.get("value")
        for item in values
        if isinstance(item, dict) and "key" in item
    }


def _target_replica(
    profile: EvidenceProfile,
    service: str,
    attributes: dict[str, Any],
) -> tuple[str, bool]:
    if service != profile.target_service:
        return "", False
    raw = str(attributes.get(profile.replica_attribute, ""))
    replica = profile.replica_values.get(raw, "")
    return replica, not bool(replica)


def _deduplicate_spans(
    records: Iterable[SpanRecord],
    invalid_records: int,
    unknown_target_instances: int,
) -> ParsedTraceEvidence:
    unique: dict[tuple[str, str], SpanRecord] = {}
    duplicates = 0
    for row in records:
        key = (row.trace_id, row.span_id)
        if key in unique:
            duplicates += 1
            continue
        unique[key] = row
    grouped: dict[str, list[SpanRecord]] = defaultdict(list)
    for row in unique.values():
        grouped[row.trace_id].append(row)
    return ParsedTraceEvidence(
        spans_by_trace={
            trace_id: tuple(sorted(rows, key=lambda item: item.span_id))
            for trace_id, rows in grouped.items()
        },
        invalid_records=invalid_records,
        duplicate_spans=duplicates,
        unknown_target_instances=unknown_target_instances,
    )


def parse_jaeger_trace_evidence(
    profile: EvidenceProfile,
    path: str | Path,
    expected_trace_ids: Iterable[str],
) -> ParsedTraceEvidence:
    expected = {str(value).lower() for value in expected_trace_ids}
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    traces = document.get("data", []) if isinstance(document, dict) else []
    records: list[SpanRecord] = []
    invalid = 0
    unknown = 0
    for trace in traces:
        if not isinstance(trace, dict):
            invalid += 1
            continue
        trace_id = str(trace.get("traceID", "")).lower()
        if trace_id not in expected:
            continue
        raw_processes = trace.get("processes", {})
        processes = raw_processes if isinstance(raw_processes, dict) else {}
        for span in trace.get("spans", []):
            if not isinstance(span, dict):
                invalid += 1
                continue
            process = processes.get(str(span.get("processID", "")), {})
            if not isinstance(process, dict):
                process = {}
            attributes = _jaeger_attributes(process.get("tags", []))
            service = str(process.get("serviceName", ""))
            replica, is_unknown = _target_replica(profile, service, attributes)
            unknown += int(is_unknown)
            references = span.get("references", [])
            if not isinstance(references, list):
                references = []
            parent = next(
                (
                    str(reference.get("spanID", "")).lower()
                    for reference in references
                    if isinstance(reference, dict)
                    and str(reference.get("refType", "")) == "CHILD_OF"
                ),
                "",
            )
            span_id = str(span.get("spanID", "")).lower()
            if not trace_id or not span_id or not service:
                invalid += 1
                continue
            records.append(
                SpanRecord(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=parent,
                    service=service,
                    operation=str(span.get("operationName", "")),
                    target_replica=replica,
                )
            )
    return _deduplicate_spans(records, invalid, unknown)


def _iter_otlp_documents(path: Path) -> Iterator[tuple[dict[str, Any] | None, bool]]:
    with path.open(encoding="utf-8", errors="replace") as source:
        for raw in source:
            line = raw.strip()
            if not line:
                continue
            try:
                document = json.loads(line)
            except json.JSONDecodeError:
                yield None, True
                continue
            yield (
                (document if isinstance(document, dict) else None),
                not isinstance(document, dict),
            )


def parse_otlp_jsonl_trace_evidence(
    profile: EvidenceProfile,
    path: str | Path,
    expected_trace_ids: Iterable[str],
) -> ParsedTraceEvidence:
    expected = {str(value).lower() for value in expected_trace_ids}
    records: list[SpanRecord] = []
    invalid = 0
    unknown = 0
    for document, malformed in _iter_otlp_documents(Path(path)):
        invalid += int(malformed)
        if document is None:
            continue
        resource_spans = document.get("resourceSpans", [])
        if not isinstance(resource_spans, list):
            invalid += 1
            continue
        for resource_item in resource_spans:
            if not isinstance(resource_item, dict):
                invalid += 1
                continue
            resource = resource_item.get("resource", {})
            resource = resource if isinstance(resource, dict) else {}
            resource_attributes = _attributes(resource.get("attributes", []))
            service = str(resource_attributes.get("service.name", ""))
            replica, is_unknown = _target_replica(profile, service, resource_attributes)
            scope_spans = resource_item.get("scopeSpans", [])
            if not isinstance(scope_spans, list):
                invalid += 1
                continue
            for scope in scope_spans:
                if not isinstance(scope, dict):
                    invalid += 1
                    continue
                spans = scope.get("spans", [])
                if not isinstance(spans, list):
                    invalid += 1
                    continue
                for span in spans:
                    if not isinstance(span, dict):
                        invalid += 1
                        continue
                    trace_id = str(span.get("traceId", "")).lower()
                    if trace_id not in expected:
                        continue
                    span_id = str(span.get("spanId", "")).lower()
                    if not trace_id or not span_id or not service:
                        invalid += 1
                        continue
                    unknown += int(is_unknown)
                    records.append(
                        SpanRecord(
                            trace_id=trace_id,
                            span_id=span_id,
                            parent_span_id=str(span.get("parentSpanId", "")).lower(),
                            service=service,
                            operation=str(span.get("name", "")),
                            target_replica=replica,
                        )
                    )
    return _deduplicate_spans(records, invalid, unknown)


def parse_trace_evidence(
    profile: EvidenceProfile,
    path: str | Path,
    expected_trace_ids: Iterable[str],
) -> ParsedTraceEvidence:
    if profile.trace_format == "jaeger_json_v1":
        return parse_jaeger_trace_evidence(profile, path, expected_trace_ids)
    if profile.trace_format == "otlp_jsonl_v1":
        return parse_otlp_jsonl_trace_evidence(profile, path, expected_trace_ids)
    raise EvidenceBoundaryError(f"unsupported trace format {profile.trace_format!r}")


def _trace_features(
    spans: tuple[SpanRecord, ...],
) -> tuple[int, str, str, int]:
    services = sorted({span.service for span in spans})
    replicas = sorted({span.target_replica for span in spans if span.target_replica})
    return len(spans), ";".join(services), ";".join(replicas), len(replicas)


def _topology_rows(
    identity: dict[str, Any],
    spans_by_trace: dict[str, tuple[SpanRecord, ...]],
) -> list[dict[str, Any]]:
    span_support: Counter[tuple[str, str]] = Counter()
    trace_support: dict[tuple[str, str], set[str]] = defaultdict(set)
    for trace_id, spans in spans_by_trace.items():
        by_id = {span.span_id: span for span in spans}
        for span in spans:
            parent = by_id.get(span.parent_span_id)
            if parent is None or parent.service == span.service:
                continue
            edge = (parent.service, span.service)
            span_support[edge] += 1
            trace_support[edge].add(trace_id)
    return [
        {
            **identity,
            "source_service": source,
            "target_service": target,
            "supporting_spans": span_support[(source, target)],
            "supporting_traces": len(trace_support[(source, target)]),
        }
        for source, target in sorted(span_support)
    ]


def _health_value(row: dict[str, str], key: str) -> Any:
    if key in {"running", "paused"}:
        return _bool(row.get(key, ""))
    return row.get(key, "")


def _pivot_health(
    identity: dict[str, Any],
    rows: Iterable[dict[str, str]],
    period: str,
) -> tuple[list[dict[str, Any]], int]:
    selected = [row for row in rows if row.get("period") == period]
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected:
        grouped[str(row.get("observed_at", ""))].append(row)
    output: list[dict[str, Any]] = []
    malformed = 0
    for observed_at, group in sorted(grouped.items()):
        roles: dict[str, dict[str, str]] = {}
        for row in group:
            key = (
                f"replica_{row.get('replica')}"
                if row.get("role") == "replica"
                else "proxy"
                if row.get("role") == "proxy"
                else ""
            )
            if not key or key in roles or row.get("error"):
                malformed += 1
                continue
            roles[key] = row
        record: dict[str, Any] = {
            **identity,
            "period": period,
            "observed_at": observed_at,
            "elapsed_seconds": next(
                (row.get("elapsed_seconds", "") for row in group), ""
            ),
        }
        proxy = roles.get("proxy")
        record.update(
            {
                "proxy_observed": proxy is not None,
                "proxy_running": False
                if proxy is None
                else _health_value(proxy, "running"),
                "proxy_paused": False
                if proxy is None
                else _health_value(proxy, "paused"),
                "proxy_health": "" if proxy is None else proxy.get("health", ""),
            }
        )
        for replica in ("a", "b"):
            row = roles.get(f"replica_{replica}")
            prefix = f"replica_{replica}"
            record.update(
                {
                    f"{prefix}_observed": row is not None,
                    f"{prefix}_running": False
                    if row is None
                    else _health_value(row, "running"),
                    f"{prefix}_paused": False
                    if row is None
                    else _health_value(row, "paused"),
                    f"{prefix}_health": "" if row is None else row.get("health", ""),
                    f"{prefix}_network_count": ""
                    if row is None
                    else row.get("network_count", ""),
                    f"{prefix}_backend_status": ""
                    if row is None
                    else row.get("backend_status", ""),
                    f"{prefix}_backend_check_status": ""
                    if row is None
                    else row.get("backend_check_status", ""),
                }
            )
        malformed += sum(
            key not in roles for key in ("proxy", "replica_a", "replica_b")
        )
        output.append(record)
    return output, malformed


def _denied_output_fields(
    learner_directory: Path, denied_tokens: Iterable[str]
) -> list[str]:
    denied = tuple(token.lower() for token in denied_tokens)
    violations: set[str] = set()
    for path in learner_directory.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as source:
                fields = csv.DictReader(source).fieldnames or []
        elif path.suffix == ".json":
            document = json.loads(path.read_text(encoding="utf-8"))
            fields = _json_keys(document)
        else:
            fields = []
        for field in fields:
            normalized = field.lower()
            if any(token in normalized for token in denied):
                violations.add(field)
    return sorted(violations)


def _json_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [
            key
            for raw_key, item in value.items()
            for key in (str(raw_key), *_json_keys(item))
        ]
    if isinstance(value, list):
        return [key for item in value for key in _json_keys(item)]
    return []


def qualify_evidence_cell(
    config: EvidenceBoundaryConfig,
    cell_directory: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    source = Path(cell_directory)
    output = Path(output_directory)
    learner = output / "learner"
    evaluator = output / "evaluator"
    audit_directory = output / "audit"
    learner.mkdir(parents=True, exist_ok=True)
    evaluator.mkdir(parents=True, exist_ok=True)
    audit_directory.mkdir(parents=True, exist_ok=True)

    manifest_path = source / "pilot-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = config.profile(str(manifest.get("profile", "")))
    identity = {
        "profile": profile.id,
        "placement": str(manifest.get("placement", "")),
        "failure_law": str(manifest.get("failure_law", "")),
        "repetition": int(manifest.get("repetition", -1)),
    }
    missing_allowed = [
        name
        for name in config.allowed_source_files
        if name not in {"raw-telemetry.json", "raw-telemetry.log"}
        and not (source / name).is_file()
    ]
    raw_path = source / profile.raw_telemetry_file
    if not raw_path.is_file():
        missing_allowed.append(profile.raw_telemetry_file)

    requests = _csv_rows(source / "requests.csv")
    trace_join = _csv_rows(source / "trace-join.csv")
    health = _csv_rows(source / "health.csv")
    calibration = [
        row for row in requests if row.get("period") == config.learner_period
    ]
    evaluation = [row for row in requests if row.get("period") == "test"]
    joins = {
        row["request_id"]: row
        for row in trace_join
        if row.get("period") == config.learner_period
    }
    expected_trace_ids = [row["trace_id"] for row in calibration]
    parsed = parse_trace_evidence(profile, raw_path, expected_trace_ids)

    learner_rows = []
    for request in calibration:
        trace_id = str(request["trace_id"]).lower()
        spans = parsed.spans_by_trace.get(trace_id, ())
        span_count, services, replicas, replica_count = _trace_features(spans)
        joined = joins.get(request["request_id"], {})
        learner_rows.append(
            {
                **identity,
                "period": config.learner_period,
                "request_id": request["request_id"],
                "trace_id": trace_id,
                "operation": request["operation"],
                "branch_class": request["branch_class"],
                "started_at": request["started_at"],
                "completed_at": request["completed_at"],
                "semantic_success": _bool(request["semantic_success"]),
                "timed_out": _bool(request["timed_out"]),
                "trace_present": _bool(joined.get("trace_present", False)),
                "span_count": span_count,
                "services": services,
                "target_replicas": replicas,
                "target_replica_count": replica_count,
            }
        )
    health_rows, malformed_health = _pivot_health(
        identity, health, config.learner_period
    )
    test_health_rows, malformed_test_health = _pivot_health(identity, health, "test")
    topology_rows = _topology_rows(identity, parsed.spans_by_trace)
    evaluation_rows = [
        {
            **identity,
            "period": "test",
            "request_id": request["request_id"],
            "operation": request["operation"],
            "branch_class": request["branch_class"],
            "started_at": request["started_at"],
            "completed_at": request["completed_at"],
            "semantic_success": _bool(request["semantic_success"]),
            "timed_out": _bool(request["timed_out"]),
        }
        for request in evaluation
    ]

    image_audit_path = source / "image-lock-audit.json"
    image_audit = json.loads(image_audit_path.read_text(encoding="utf-8"))
    placement = image_audit.get("placement_pilot", {})
    deployment = {
        "schema_version": 1,
        **identity,
        "target_service": placement.get("target_service"),
        "proxy_service": placement.get("proxy_service"),
        "replica_services": placement.get("replica_services"),
        "domain_assignments": placement.get("domain_assignments"),
        "routing_policy": "haproxy_round_robin",
        "provenance": "declared deployment metadata; not inferred failure causes",
    }

    _write_csv(learner / "requests.csv", LEARNER_REQUEST_FIELDS, learner_rows)
    _write_csv(learner / "health.csv", LEARNER_HEALTH_FIELDS, health_rows)
    _write_csv(learner / "topology-edges.csv", TOPOLOGY_EDGE_FIELDS, topology_rows)
    (learner / "deployment.json").write_text(
        json.dumps(deployment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(
        evaluator / "test-requests.csv",
        EVALUATOR_REQUEST_FIELDS,
        evaluation_rows,
    )
    _write_csv(
        evaluator / "test-health.csv",
        LEARNER_HEALTH_FIELDS,
        test_health_rows,
    )

    learner_ids = {row["request_id"] for row in learner_rows}
    evaluation_ids = {row["request_id"] for row in evaluation_rows}
    semantic_successes = sum(row["semantic_success"] for row in learner_rows)
    linked_successes = sum(
        row["semantic_success"] and row["trace_present"] for row in learner_rows
    )
    linked_fraction = (
        linked_successes / semantic_successes if semantic_successes else 0.0
    )
    parsed_linked = sum(
        row["trace_present"] and row["span_count"] > 0 for row in learner_rows
    )
    present = sum(row["trace_present"] for row in learner_rows)
    replica_counts = Counter(
        replica
        for row in learner_rows
        for replica in str(row["target_replicas"]).split(";")
        if replica
    )
    expected_calibration = int(
        manifest.get("period_summaries", {})
        .get(config.learner_period, {})
        .get("requests", -1)
    )
    expected_test = int(
        manifest.get("period_summaries", {}).get("test", {}).get("requests", -1)
    )

    learner_manifest = {
        "schema_version": 1,
        "kind": "learner_calibration_evidence",
        "diagnostic_only": True,
        "source_experiment_id": config.source_experiment_id,
        **identity,
        "period": config.learner_period,
        "allowed_evidence": (
            "external semantic request outcomes; native trace graph and replica "
            "identity; independent health/lifecycle/network observations; declared "
            "deployment and routing metadata"
        ),
        "row_counts": {
            "requests": len(learner_rows),
            "health_ticks": len(health_rows),
            "topology_edges": len(topology_rows),
        },
        "files": {
            "requests_sha256": file_sha256(learner / "requests.csv"),
            "health_sha256": file_sha256(learner / "health.csv"),
            "topology_edges_sha256": file_sha256(learner / "topology-edges.csv"),
            "deployment_sha256": file_sha256(learner / "deployment.json"),
        },
    }
    (learner / "manifest.json").write_text(
        json.dumps(learner_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    denied_fields = _denied_output_fields(learner, config.denied_learner_field_tokens)
    quality = {
        "source_experiment_mismatches": int(
            manifest.get("experiment_id") != config.source_experiment_id
        ),
        "source_not_pilot_only": int(manifest.get("pilot_only") is not True),
        "source_unusable": int(manifest.get("usable_for_m7_freeze") is not True),
        "missing_allowed_source_files": len(missing_allowed),
        "calibration_request_count_mismatches": int(
            len(learner_rows) != expected_calibration
        ),
        "test_request_count_mismatches": int(len(evaluation_rows) != expected_test),
        "duplicate_calibration_request_ids": len(learner_rows) - len(learner_ids),
        "learner_test_request_overlap": len(learner_ids.intersection(evaluation_ids)),
        "trace_join_request_mismatches": len(
            learner_ids.symmetric_difference(set(joins))
        ),
        "linked_traces_without_parsed_spans": present - parsed_linked,
        "invalid_trace_records": parsed.invalid_records,
        "duplicate_trace_spans": parsed.duplicate_spans,
        "unknown_target_trace_instances": parsed.unknown_target_instances,
        "trace_link_fraction_below_minimum": int(
            linked_fraction < config.minimum_trace_link_fraction
        ),
        "missing_topology_edges": int(not topology_rows),
        "replicas_below_assignment_minimum": sum(
            replica_counts[replica] < config.minimum_replica_assignments_per_replica
            for replica in ("a", "b")
        ),
        "malformed_health_rows_or_ticks": malformed_health,
        "missing_test_health_ticks": int(not test_health_rows),
        "malformed_test_health_rows_or_ticks": malformed_test_health,
        "denied_learner_fields": len(denied_fields),
        "privileged_files_copied_to_learner": sum(
            (learner / name).exists() for name in config.privileged_source_files
        ),
    }
    source_hashes = {
        name: file_sha256(source / name)
        for name in (*config.allowed_source_files, *config.privileged_source_files)
        if (source / name).is_file()
    }
    failures = {name: value for name, value in quality.items() if value}
    boundary_audit = {
        "schema_version": 1,
        "kind": "learner_evaluator_boundary_audit",
        "diagnostic_only": True,
        **identity,
        "learner_period": config.learner_period,
        "evaluation_period": "test",
        "allowed_source_files": list(config.allowed_source_files),
        "privileged_source_files": list(config.privileged_source_files),
        "privileged_files_parsed_for_learner": [],
        "denied_learner_fields": denied_fields,
        "source_sha256": source_hashes,
        "quality": quality,
        "usable": not failures,
    }
    (audit_directory / "boundary.json").write_text(
        json.dumps(boundary_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        **identity,
        "calibration_requests": len(learner_rows),
        "calibration_semantic_successes": semantic_successes,
        "calibration_traces_present": present,
        "calibration_traces_parsed": parsed_linked,
        "calibration_trace_link_fraction": linked_fraction,
        "calibration_health_ticks": len(health_rows),
        "topology_edges": len(topology_rows),
        "replica_a_trace_assignments": replica_counts["a"],
        "replica_b_trace_assignments": replica_counts["b"],
        "test_requests_sequestered": len(evaluation_rows),
        "test_health_ticks_sequestered": len(test_health_rows),
        "quality_failures": sum(quality.values()),
        "usable": not failures,
    }
    (output / "cell-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def qualify_evidence_boundary(
    config: EvidenceBoundaryConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    manifest_paths = sorted(root.rglob("pilot-manifest.json"))
    summaries: list[dict[str, Any]] = []
    identities: list[tuple[str, str, str, int]] = []
    source_run_ids: set[str] = set()
    source_commits: set[str] = set()
    cell_errors: dict[str, str] = {}
    for manifest_path in manifest_paths:
        source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source_environment = source_manifest.get("environment", {})
        source_github = source_environment.get("github", {})
        source_git = source_environment.get("git", {})
        source_run_ids.add(str(source_github.get("GITHUB_RUN_ID", "")))
        source_commits.add(str(source_git.get("commit", "")))
        identity = (
            str(source_manifest.get("profile", "")),
            str(source_manifest.get("placement", "")),
            str(source_manifest.get("failure_law", "")),
            int(source_manifest.get("repetition", -1)),
        )
        identities.append(identity)
        profile, placement, law, repetition = identity
        cell_output = output / "cells" / profile / placement / law / f"r{repetition}"
        try:
            summary = qualify_evidence_cell(config, manifest_path.parent, cell_output)
        except Exception as error:  # noqa: BLE001 - retain all cell diagnostics
            cell_errors[":".join(map(str, identity))] = (
                f"{type(error).__name__}: {error}"
            )
            continue
        summaries.append(summary)

    summaries.sort(
        key=lambda row: (
            row["profile"],
            row["placement"],
            row["failure_law"],
            row["repetition"],
        )
    )
    _write_csv(output / "cells.csv", CELL_SUMMARY_FIELDS, summaries)
    identity_set = set(identities)
    declared_source_run = os.environ.get("M7D_SOURCE_RUN_ID", "")
    quality = {
        "source_cell_count_mismatches": int(
            len(manifest_paths) != config.expected_source_cells
        ),
        "duplicate_source_cells": len(identities) - len(identity_set),
        "cell_processing_errors": len(cell_errors),
        "unusable_cells": sum(not bool(row["usable"]) for row in summaries),
        "learner_test_request_overlap": 0,
        "source_workflow_run_count_mismatches": int(len(source_run_ids - {""}) != 1),
        "source_commit_count_mismatches": int(len(source_commits - {""}) != 1),
        "declared_source_run_mismatches": int(
            bool(declared_source_run) and source_run_ids - {""} != {declared_source_run}
        ),
    }
    for path in output.rglob("boundary.json"):
        audit = json.loads(path.read_text(encoding="utf-8"))
        quality["learner_test_request_overlap"] += int(
            audit["quality"]["learner_test_request_overlap"]
        )
    failures = {name: value for name, value in quality.items() if value}
    aggregate = {
        "schema_version": 1,
        "kind": "learner_evidence_boundary_qualification",
        "experiment_id": config.id,
        "diagnostic_only": True,
        "source_experiment_id": config.source_experiment_id,
        "source_workflow_run_ids": sorted(source_run_ids - {""}),
        "source_commits": sorted(source_commits - {""}),
        "source_cells": len(manifest_paths),
        "qualified_cells": len(summaries),
        "quality": quality,
        "cell_errors": cell_errors,
        "row_counts": {
            "calibration_requests": sum(
                int(row["calibration_requests"]) for row in summaries
            ),
            "calibration_health_ticks": sum(
                int(row["calibration_health_ticks"]) for row in summaries
            ),
            "topology_edges": sum(int(row["topology_edges"]) for row in summaries),
            "sequestered_test_requests": sum(
                int(row["test_requests_sequestered"]) for row in summaries
            ),
            "sequestered_test_health_ticks": sum(
                int(row["test_health_ticks_sequestered"]) for row in summaries
            ),
        },
        "files": {"cells_sha256": file_sha256(output / "cells.csv")},
        "environment": environment_manifest(),
        "usable": not failures,
    }
    (output / "manifest.json").write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise EvidenceBoundaryError(
            f"M7D evidence-boundary acceptance failures: {failures}"
        )
    return aggregate
