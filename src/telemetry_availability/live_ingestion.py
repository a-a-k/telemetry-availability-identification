from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .live_config import BenchmarkProfile, LiveContractConfig
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class LiveContractError(ValueError):
    """Raised when a live telemetry bundle violates its versioned contract."""


@dataclass(frozen=True)
class Period:
    id: str
    start: datetime
    end: datetime
    workload_seed: int
    failure_seed: int
    sampling_seed: int


@dataclass(frozen=True)
class IngestedLiveBundle:
    manifest: dict[str, Any]
    periods: dict[str, Period]
    operations: dict[str, dict[str, Any]]
    requests: tuple[dict[str, Any], ...]
    spans: tuple[dict[str, Any], ...]
    deployments: tuple[dict[str, Any], ...]
    health: tuple[dict[str, Any], ...]
    mesh: tuple[dict[str, Any], ...]
    injections: tuple[dict[str, Any], ...]
    audit: dict[str, Any]


REQUEST_FIELDS = (
    "request_id",
    "trace_id",
    "started_at",
    "completed_at",
    "period",
    "operation_class",
    "branch_class",
    "outcome",
    "success",
    "timed_out",
)

SPAN_FIELDS = (
    "trace_id",
    "span_id",
    "parent_span_id",
    "service",
    "instance_id",
    "operation",
    "started_at",
    "completed_at",
    "status",
    "kind",
    "attributes_json",
)

DEPLOYMENT_FIELDS = (
    "instance_id",
    "service",
    "version",
    "valid_from",
    "valid_to",
    "domain_id",
    "routing_policy",
)

HEALTH_FIELDS = (
    "timestamp",
    "instance_id",
    "signal",
    "state",
    "source",
)

MESH_FIELDS = (
    "timestamp",
    "request_id",
    "source_instance",
    "target_service",
    "logical_call_id",
    "attempt",
    "outcome",
)

INJECTION_FIELDS = (
    "incident_id",
    "intent_at",
    "applied_at",
    "verified_start",
    "verified_end",
    "scope",
    "mechanism",
    "confirmed",
)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LiveContractError(f"{label} must be a mapping")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise LiveContractError(f"{label} must be a sequence")
    return value


def _timestamp(value: Any, label: str) -> datetime:
    raw = str(value)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise LiveContractError(f"{label} is not an ISO-8601 timestamp: {raw!r}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LiveContractError(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unix_nanos(value: Any, label: str) -> datetime:
    try:
        nanos = int(str(value))
    except ValueError as error:
        raise LiveContractError(f"{label} must be integer nanoseconds") from error
    return datetime.fromtimestamp(nanos / 1_000_000_000, tz=timezone.utc)


def _unix_micros(value: Any, label: str) -> datetime:
    try:
        micros = int(value)
    except (TypeError, ValueError) as error:
        raise LiveContractError(f"{label} must be integer microseconds") from error
    return datetime.fromtimestamp(micros / 1_000_000, tz=timezone.utc)


def _boolean(value: Any, label: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise LiveContractError(f"{label} must be boolean")


def _hex_identifier(value: Any, lengths: set[int], label: str) -> str:
    normalized = str(value).lower()
    if len(normalized) not in lengths or re.fullmatch(r"[0-9a-f]+", normalized) is None:
        raise LiveContractError(
            f"{label} must be hexadecimal with length in {sorted(lengths)}"
        )
    return normalized


def _safe_file(bundle_root: Path, raw_path: Any, label: str) -> Path:
    relative = Path(str(raw_path))
    if relative.is_absolute() or ".." in relative.parts:
        raise LiveContractError(f"{label} must be a safe relative path")
    root = bundle_root.resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise LiveContractError(f"{label} escapes the bundle root")
    if not result.is_file():
        raise LiveContractError(f"{label} does not exist: {relative.as_posix()}")
    return result


def _csv_rows(path: Path, required_fields: Iterable[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = set(required_fields) - set(reader.fieldnames or ())
        if missing:
            raise LiveContractError(f"{path.name} misses columns {sorted(missing)}")
        return [dict(row) for row in reader]


def _unique(rows: Iterable[dict[str, Any]], field: str, label: str) -> None:
    values = [str(row[field]) for row in rows]
    if any(not value for value in values):
        raise LiveContractError(f"{label} has an empty {field}")
    duplicate = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicate:
        raise LiveContractError(f"{label} repeats {field}: {duplicate[:5]}")


def _attribute_value(value: Any) -> Any:
    data = _mapping(value, "OTLP attribute value")
    scalar_keys = (
        "stringValue",
        "boolValue",
        "intValue",
        "doubleValue",
        "bytesValue",
    )
    for key in scalar_keys:
        if key in data:
            return data[key]
    if "arrayValue" in data:
        array = _mapping(data["arrayValue"], "OTLP array value")
        return [_attribute_value(item) for item in _sequence(array.get("values", []), "OTLP array")]
    if "kvlistValue" in data:
        nested = _mapping(data["kvlistValue"], "OTLP kvlist value")
        return _attributes(nested.get("values", []))
    return None


def _attributes(values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in _sequence(values or [], "attribute list"):
        data = _mapping(item, "attribute")
        result[str(data["key"])] = _attribute_value(data["value"])
    return result


def parse_otlp_json(path: Path) -> list[dict[str, Any]]:
    document = _mapping(json.loads(path.read_text(encoding="utf-8")), "OTLP document")
    rows: list[dict[str, Any]] = []
    for resource_spans in _sequence(document.get("resourceSpans", []), "resourceSpans"):
        resource_data = _mapping(resource_spans, "resourceSpans item")
        resource = _mapping(resource_data.get("resource", {}), "OTLP resource")
        resource_attributes = _attributes(resource.get("attributes", []))
        for scope_spans in _sequence(resource_data.get("scopeSpans", []), "scopeSpans"):
            scope_data = _mapping(scope_spans, "scopeSpans item")
            for span in _sequence(scope_data.get("spans", []), "OTLP spans"):
                data = _mapping(span, "OTLP span")
                attributes = {**resource_attributes, **_attributes(data.get("attributes", []))}
                start = _unix_nanos(data["startTimeUnixNano"], "span startTimeUnixNano")
                end = _unix_nanos(data["endTimeUnixNano"], "span endTimeUnixNano")
                if end < start:
                    raise LiveContractError("OTLP span has negative duration")
                status_data = _mapping(data.get("status", {}), "OTLP status")
                rows.append(
                    {
                        "trace_id": _hex_identifier(data["traceId"], {32}, "OTLP traceId"),
                        "span_id": _hex_identifier(data["spanId"], {16}, "OTLP spanId"),
                        "parent_span_id": (
                            _hex_identifier(
                                data["parentSpanId"],
                                {16},
                                "OTLP parentSpanId",
                            )
                            if data.get("parentSpanId")
                            else ""
                        ),
                        "service": str(attributes.get("service.name", "")),
                        "instance_id": str(
                            attributes.get(
                                "service.instance.id",
                                attributes.get("k8s.pod.name", ""),
                            )
                        ),
                        "operation": str(
                            attributes.get(
                                "taid.operation_class",
                                attributes.get("http.route", data.get("name", "")),
                            )
                        ),
                        "started_at": _format_time(start),
                        "completed_at": _format_time(end),
                        "status": str(status_data.get("code", "STATUS_CODE_UNSET")),
                        "kind": str(data.get("kind", "SPAN_KIND_UNSPECIFIED")),
                        "attributes_json": json.dumps(
                            attributes,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                )
    return rows


def _jaeger_tags(values: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in _sequence(values or [], "Jaeger tags"):
        data = _mapping(item, "Jaeger tag")
        result[str(data["key"])] = data.get("value")
    return result


def parse_jaeger_json(path: Path) -> list[dict[str, Any]]:
    document = _mapping(json.loads(path.read_text(encoding="utf-8")), "Jaeger document")
    rows: list[dict[str, Any]] = []
    for trace in _sequence(document.get("data", []), "Jaeger data"):
        trace_data = _mapping(trace, "Jaeger trace")
        processes = _mapping(trace_data.get("processes", {}), "Jaeger processes")
        for span in _sequence(trace_data.get("spans", []), "Jaeger spans"):
            data = _mapping(span, "Jaeger span")
            process = _mapping(processes.get(str(data.get("processID", "")), {}), "Jaeger process")
            attributes = {
                **_jaeger_tags(process.get("tags", [])),
                **_jaeger_tags(data.get("tags", [])),
            }
            start = _unix_micros(data["startTime"], "Jaeger startTime")
            duration = int(data["duration"])
            if duration < 0:
                raise LiveContractError("Jaeger span has negative duration")
            end = datetime.fromtimestamp(
                start.timestamp() + duration / 1_000_000,
                tz=timezone.utc,
            )
            references = [
                _mapping(item, "Jaeger reference")
                for item in _sequence(data.get("references", []), "Jaeger references")
                if _mapping(item, "Jaeger reference").get("refType") == "CHILD_OF"
            ]
            parent = (
                _hex_identifier(
                    references[0].get("spanID", ""),
                    {16},
                    "Jaeger parent spanID",
                )
                if references
                else ""
            )
            error = _boolean(attributes.get("error", False), "Jaeger error tag")
            rows.append(
                {
                    "trace_id": _hex_identifier(
                        data.get("traceID", trace_data.get("traceID", "")),
                        {16, 32},
                        "Jaeger traceID",
                    ),
                    "span_id": _hex_identifier(data["spanID"], {16}, "Jaeger spanID"),
                    "parent_span_id": parent,
                    "service": str(process.get("serviceName", "")),
                    "instance_id": str(
                        attributes.get(
                            "service.instance.id",
                            attributes.get("hostname", ""),
                        )
                    ),
                    "operation": str(
                        attributes.get("taid.operation_class", data.get("operationName", ""))
                    ),
                    "started_at": _format_time(start),
                    "completed_at": _format_time(end),
                    "status": "ERROR" if error else "OK",
                    "kind": str(attributes.get("span.kind", "unspecified")),
                    "attributes_json": json.dumps(
                        attributes,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
    return rows


def _load_periods(raw: Any, require_disjoint: bool) -> dict[str, Period]:
    data = _mapping(raw, "bundle periods")
    if set(data) != {"calibration", "test"}:
        raise LiveContractError("bundle periods must be exactly calibration and test")
    result: dict[str, Period] = {}
    for period_id, value in data.items():
        item = _mapping(value, f"period {period_id}")
        period = Period(
            id=period_id,
            start=_timestamp(item["start"], f"{period_id} start"),
            end=_timestamp(item["end"], f"{period_id} end"),
            workload_seed=int(item["workload_seed"]),
            failure_seed=int(item["failure_seed"]),
            sampling_seed=int(item["sampling_seed"]),
        )
        if period.end <= period.start:
            raise LiveContractError(f"{period_id} period is empty or reversed")
        result[period_id] = period
    calibration = result["calibration"]
    test = result["test"]
    if require_disjoint and not (
        calibration.end <= test.start or test.end <= calibration.start
    ):
        raise LiveContractError("calibration and test periods overlap")
    if (
        calibration.workload_seed,
        calibration.failure_seed,
        calibration.sampling_seed,
    ) == (
        test.workload_seed,
        test.failure_seed,
        test.sampling_seed,
    ):
        raise LiveContractError("calibration and test must not reuse the complete seed tuple")
    return result


def _load_operations(path: Path) -> dict[str, dict[str, Any]]:
    root = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "operation document")
    if root.get("schema_version") != "taid.operations/v1":
        raise LiveContractError("operation schema_version must equal taid.operations/v1")
    result: dict[str, dict[str, Any]] = {}
    for raw in _sequence(root.get("operations"), "operations"):
        item = _mapping(raw, "operation")
        operation_id = str(item["id"])
        if operation_id in result or not operation_id:
            raise LiveContractError(f"duplicate or empty operation id {operation_id!r}")
        semantics = str(item["semantics"])
        if semantics not in {"immediate", "eventual"}:
            raise LiveContractError(f"unsupported operation semantics {semantics!r}")
        accepted = tuple(str(value) for value in _sequence(item.get("accepted_outcomes"), "accepted outcomes"))
        effects = tuple(str(value) for value in _sequence(item.get("required_effects", []), "required effects"))
        branches = tuple(str(value) for value in _sequence(item.get("branch_classes", []), "branch classes"))
        if not str(item["entry_service"]) or not accepted:
            raise LiveContractError(f"operation {operation_id!r} lacks entry service/outcomes")
        result[operation_id] = {
            "id": operation_id,
            "entry_service": str(item["entry_service"]),
            "semantics": semantics,
            "accepted_outcomes": accepted,
            "required_effects": effects,
            "branch_classes": branches,
        }
    if not result:
        raise LiveContractError("operation specification is empty")
    return result


def _load_requests(
    path: Path,
    periods: dict[str, Period],
    operations: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_rows = _csv_rows(path, REQUEST_FIELDS)
    _unique(raw_rows, "request_id", "external requests")
    trace_ids = [row["trace_id"].lower() for row in raw_rows if row["trace_id"]]
    if len(trace_ids) != len(set(trace_ids)):
        raise LiveContractError("external request census repeats a nonempty trace_id")
    result: list[dict[str, Any]] = []
    for row in raw_rows:
        period_id = row["period"]
        if period_id not in periods:
            raise LiveContractError(f"request uses unknown period {period_id!r}")
        operation = row["operation_class"]
        if operation not in operations:
            raise LiveContractError(f"request uses unknown operation {operation!r}")
        start = _timestamp(row["started_at"], "request start")
        end = _timestamp(row["completed_at"], "request completion")
        period = periods[period_id]
        if end < start or not (period.start <= start < period.end) or end > period.end:
            raise LiveContractError(f"request {row['request_id']!r} violates its period")
        success = _boolean(row["success"], "request success")
        timed_out = _boolean(row["timed_out"], "request timed_out")
        if success and timed_out:
            raise LiveContractError("a successful request cannot be timed out")
        if success and row["outcome"] not in operations[operation]["accepted_outcomes"]:
            raise LiveContractError(
                f"successful request outcome {row['outcome']!r} is not accepted for {operation!r}"
            )
        branch = row["branch_class"]
        declared_branches = operations[operation]["branch_classes"]
        if branch and branch not in declared_branches:
            raise LiveContractError(f"request uses undeclared branch class {branch!r}")
        result.append(
            {
                **row,
                "trace_id": row["trace_id"].lower(),
                "started_at": _format_time(start),
                "completed_at": _format_time(end),
                "success": success,
                "timed_out": timed_out,
            }
        )
    return result


def _validate_request_trace_ids(
    requests: list[dict[str, Any]],
    trace_format: str,
) -> None:
    lengths = {32} if trace_format == "otlp_json_v1" else {16, 32}
    for row in requests:
        if row["trace_id"]:
            row["trace_id"] = _hex_identifier(
                row["trace_id"],
                lengths,
                "external request trace_id",
            )


def _load_deployments(path: Path) -> list[dict[str, Any]]:
    raw_rows = _csv_rows(path, DEPLOYMENT_FIELDS)
    result: list[dict[str, Any]] = []
    for row in raw_rows:
        start = _timestamp(row["valid_from"], "deployment valid_from")
        end = _timestamp(row["valid_to"], "deployment valid_to") if row["valid_to"] else None
        if end is not None and end <= start:
            raise LiveContractError("deployment validity interval is empty or reversed")
        if not all(row[field] for field in ("instance_id", "service", "version", "domain_id", "routing_policy")):
            raise LiveContractError("deployment row has an empty required identity field")
        result.append(
            {
                **row,
                "valid_from": _format_time(start),
                "valid_to": "" if end is None else _format_time(end),
            }
        )
    return result


def _load_health(path: Path) -> list[dict[str, Any]]:
    rows = _csv_rows(path, HEALTH_FIELDS)
    for row in rows:
        row["timestamp"] = _format_time(_timestamp(row["timestamp"], "health timestamp"))
        if row["signal"] not in {"liveness", "readiness", "restart"}:
            raise LiveContractError(f"unknown health signal {row['signal']!r}")
        if row["state"] not in {"up", "down", "unknown"}:
            raise LiveContractError(f"unknown health state {row['state']!r}")
    return rows


def _load_mesh(path: Path) -> list[dict[str, Any]]:
    rows = _csv_rows(path, MESH_FIELDS)
    for row in rows:
        row["timestamp"] = _format_time(_timestamp(row["timestamp"], "mesh timestamp"))
        try:
            attempt = int(row["attempt"])
        except ValueError as error:
            raise LiveContractError("mesh attempt must be an integer") from error
        if attempt <= 0:
            raise LiveContractError("mesh attempt must be positive")
        row["attempt"] = attempt
    attempt_keys = [
        (row["request_id"], row["logical_call_id"], row["attempt"])
        for row in rows
    ]
    duplicates = sorted(
        value for value, count in Counter(attempt_keys).items() if count > 1
    )
    if duplicates:
        raise LiveContractError(f"mesh repeats request/call/attempt: {duplicates[:5]}")
    return rows


def _load_injections(path: Path) -> list[dict[str, Any]]:
    rows = _csv_rows(path, INJECTION_FIELDS)
    _unique(rows, "incident_id", "injection audit")
    for row in rows:
        for field in ("intent_at", "applied_at", "verified_start", "verified_end"):
            row[field] = _format_time(_timestamp(row[field], f"injection {field}"))
        if _timestamp(row["verified_end"], "verified_end") <= _timestamp(
            row["verified_start"], "verified_start"
        ):
            raise LiveContractError("injection verified interval is empty or reversed")
        row["confirmed"] = _boolean(row["confirmed"], "injection confirmed")
    return rows


def _validate_span_graph(spans: list[dict[str, Any]]) -> None:
    span_keys = [(row["trace_id"], row["span_id"]) for row in spans]
    duplicate_keys = sorted(
        value for value, count in Counter(span_keys).items() if count > 1
    )
    if duplicate_keys:
        raise LiveContractError(
            f"normalized spans repeat trace/span identity: {duplicate_keys[:5]}"
        )
    by_trace: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in spans:
        if not all(row[field] for field in ("trace_id", "span_id", "service", "instance_id")):
            raise LiveContractError("normalized span lacks trace/span/service/instance identity")
        by_trace[row["trace_id"]].append(row)
    for trace_id, rows in by_trace.items():
        ids = {row["span_id"] for row in rows}
        roots = [row for row in rows if not row["parent_span_id"]]
        if len(roots) != 1:
            raise LiveContractError(f"trace {trace_id!r} must have exactly one exported root")
        if any(row["parent_span_id"] and row["parent_span_id"] not in ids for row in rows):
            raise LiveContractError(f"trace {trace_id!r} has a missing exported parent")
        parent = {row["span_id"]: row["parent_span_id"] for row in rows}
        for span_id in ids:
            visited: set[str] = set()
            cursor = span_id
            while cursor:
                if cursor in visited:
                    raise LiveContractError(f"trace {trace_id!r} contains a parent cycle")
                visited.add(cursor)
                cursor = parent.get(cursor, "")


def _deployment_matches(
    deployment: dict[str, Any],
    instance_id: str,
    service: str,
    timestamp: datetime,
) -> bool:
    start = _timestamp(deployment["valid_from"], "deployment valid_from")
    end = (
        _timestamp(deployment["valid_to"], "deployment valid_to")
        if deployment["valid_to"]
        else None
    )
    return (
        deployment["instance_id"] == instance_id
        and deployment["service"] == service
        and start <= timestamp
        and (end is None or timestamp < end)
    )


def _validate_relations(
    requests: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    deployments: list[dict[str, Any]],
    health: list[dict[str, Any]],
    mesh: list[dict[str, Any]],
    injections: list[dict[str, Any]],
    periods: dict[str, Period],
    operations: dict[str, dict[str, Any]],
) -> None:
    request_ids = {row["request_id"] for row in requests}
    requests_by_trace = {
        row["trace_id"]: row for row in requests if row["trace_id"]
    }
    request_traces = {row["trace_id"] for row in requests if row["trace_id"]}
    span_traces = {row["trace_id"] for row in spans}
    orphan = span_traces - request_traces
    if orphan:
        raise LiveContractError(f"exported traces are absent from request census: {sorted(orphan)[:5]}")
    for row in spans:
        timestamp = _timestamp(row["started_at"], "span start")
        completed = _timestamp(row["completed_at"], "span completion")
        request = requests_by_trace[row["trace_id"]]
        period = periods[request["period"]]
        if completed < timestamp or not (
            period.start <= timestamp < period.end and completed <= period.end
        ):
            raise LiveContractError(
                f"span {row['span_id']!r} violates its request's period"
            )
        matches = [
            deployment
            for deployment in deployments
            if _deployment_matches(
                deployment,
                row["instance_id"],
                row["service"],
                timestamp,
            )
        ]
        if len(matches) != 1:
            raise LiveContractError(
                f"span {row['span_id']!r} maps to {len(matches)} active deployments"
            )
    deployment_instances = {row["instance_id"] for row in deployments}
    for row in health:
        timestamp = _timestamp(row["timestamp"], "health timestamp")
        active = [
            deployment
            for deployment in deployments
            if deployment["instance_id"] == row["instance_id"]
            and _deployment_matches(
                deployment,
                deployment["instance_id"],
                deployment["service"],
                timestamp,
            )
        ]
        if len(active) != 1:
            raise LiveContractError("health row lacks unique active deployment ownership")
    if any(row["request_id"] not in request_ids for row in mesh):
        raise LiveContractError("mesh row references an unknown external request")
    if any(row["source_instance"] not in deployment_instances for row in mesh):
        raise LiveContractError("mesh row references an unknown source instance")
    deployment_services = {row["service"] for row in deployments}
    if any(row["target_service"] not in deployment_services for row in mesh):
        raise LiveContractError("mesh row references an unknown target service")
    requests_by_id = {row["request_id"]: row for row in requests}
    for row in mesh:
        request = requests_by_id[row["request_id"]]
        timestamp = _timestamp(row["timestamp"], "mesh timestamp")
        period = periods[request["period"]]
        if not (period.start <= timestamp < period.end):
            raise LiveContractError("mesh row violates its request's period")
        active_sources = [
            deployment
            for deployment in deployments
            if deployment["instance_id"] == row["source_instance"]
            and _deployment_matches(
                deployment,
                deployment["instance_id"],
                deployment["service"],
                timestamp,
            )
        ]
        active_targets = [
            deployment
            for deployment in deployments
            if deployment["service"] == row["target_service"]
            and _timestamp(deployment["valid_from"], "deployment valid_from") <= timestamp
            and (
                not deployment["valid_to"]
                or timestamp
                < _timestamp(deployment["valid_to"], "deployment valid_to")
            )
        ]
        if len(active_sources) != 1 or not active_targets:
            raise LiveContractError("mesh row lacks active source or target deployment")
    for operation_id, operation in operations.items():
        traced_requests = [
            row
            for row in requests
            if row["operation_class"] == operation_id
            and row["trace_id"] in span_traces
        ]
        for request in traced_requests:
            roots = [
                row
                for row in spans
                if row["trace_id"] == request["trace_id"]
                and not row["parent_span_id"]
            ]
            if (
                len(roots) != 1
                or roots[0]["service"] != operation["entry_service"]
                or roots[0]["operation"] != operation_id
            ):
                raise LiveContractError(
                    f"request {request['request_id']!r} lacks the declared operation root"
                )
    for row in injections:
        intent = _timestamp(row["intent_at"], "intent_at")
        applied = _timestamp(row["applied_at"], "applied_at")
        start = _timestamp(row["verified_start"], "verified_start")
        end = _timestamp(row["verified_end"], "verified_end")
        if not intent <= applied <= start < end:
            raise LiveContractError(
                f"injection {row['incident_id']!r} has inconsistent audit ordering"
            )
        containing_periods = [
            period
            for period in periods.values()
            if period.start <= start < period.end and end <= period.end
        ]
        if len(containing_periods) != 1:
            raise LiveContractError(
                f"injection {row['incident_id']!r} is outside or crosses a declared period"
            )
        known_scopes = {
            value
            for deployment in deployments
            for value in (
                deployment["instance_id"],
                deployment["service"],
                deployment["domain_id"],
            )
        }
        if row["scope"] not in known_scopes:
            raise LiveContractError(
                f"injection {row['incident_id']!r} uses an unknown scope"
            )


def _audit(
    profile: BenchmarkProfile,
    periods: dict[str, Period],
    operations: dict[str, dict[str, Any]],
    requests: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    deployments: list[dict[str, Any]],
    health: list[dict[str, Any]],
    mesh: list[dict[str, Any]],
    injections: list[dict[str, Any]],
    maximum_health_age_seconds: float,
) -> dict[str, Any]:
    span_traces = {row["trace_id"] for row in spans}
    traced_requests = [
        row for row in requests if row["trace_id"] and row["trace_id"] in span_traces
    ]
    missing_trace = [row for row in requests if row not in traced_requests]
    health_counts = Counter((row["signal"], row["state"]) for row in health)
    by_instance: dict[str, list[datetime]] = defaultdict(list)
    for row in health:
        by_instance[row["instance_id"]].append(_timestamp(row["timestamp"], "health timestamp"))
    stale_gaps = 0
    max_gap = 0.0
    for values in by_instance.values():
        ordered = sorted(values)
        for first, second in zip(ordered, ordered[1:]):
            gap = (second - first).total_seconds()
            max_gap = max(max_gap, gap)
            stale_gaps += int(gap > maximum_health_age_seconds)
    request_counts = Counter((row["period"], row["operation_class"]) for row in requests)
    branch_counts = Counter(
        (row["period"], row["operation_class"], row["branch_class"])
        for row in requests
        if row["branch_class"]
    )
    incident_counts = Counter(
        (
            bool(row["intent_at"]),
            bool(row["applied_at"]),
            bool(row["verified_start"]),
            _boolean(row["confirmed"], "confirmed"),
        )
        for row in injections
    )
    return {
        "contract_status": "valid",
        "benchmark_id": profile.id,
        "benchmark_commit": profile.commit,
        "trace_format": profile.trace_format,
        "periods": {
            period_id: {
                "start": _format_time(period.start),
                "end": _format_time(period.end),
                "workload_seed": period.workload_seed,
                "failure_seed": period.failure_seed,
                "sampling_seed": period.sampling_seed,
            }
            for period_id, period in periods.items()
        },
        "counts": {
            "external_requests": len(requests),
            "successful_requests": sum(_boolean(row["success"], "success") for row in requests),
            "failed_requests": sum(not _boolean(row["success"], "success") for row in requests),
            "timed_out_requests": sum(_boolean(row["timed_out"], "timeout") for row in requests),
            "traced_external_requests": len(traced_requests),
            "requests_without_exported_trace": len(missing_trace),
            "untraced_external_failures": sum(
                not _boolean(row["success"], "success") for row in missing_trace
            ),
            "spans": len(spans),
            "traces": len(span_traces),
            "deployments": len(deployments),
            "services": len({row["service"] for row in deployments}),
            "domains": len({row["domain_id"] for row in deployments}),
            "health_records": len(health),
            "unknown_health_records": sum(row["state"] == "unknown" for row in health),
            "stale_health_gaps": stale_gaps,
            "mesh_records": len(mesh),
            "mesh_logical_calls": len({row["logical_call_id"] for row in mesh}),
            "mesh_attempts": len(mesh),
            "injections": len(injections),
            "confirmed_injections": sum(_boolean(row["confirmed"], "confirmed") for row in injections),
            "manual_operations": len(operations),
            "manual_required_effects": sum(len(item["required_effects"]) for item in operations.values()),
            "manual_branch_rules": sum(len(item["branch_classes"]) for item in operations.values()),
        },
        "root_trace_coverage": len(traced_requests) / len(requests) if requests else None,
        "maximum_health_gap_seconds": max_gap,
        "request_support": [
            {"period": key[0], "operation": key[1], "count": count}
            for key, count in sorted(request_counts.items())
        ],
        "branch_support": [
            {
                "period": key[0],
                "operation": key[1],
                "branch": key[2],
                "count": count,
            }
            for key, count in sorted(branch_counts.items())
        ],
        "health_counts": [
            {"signal": key[0], "state": key[1], "count": count}
            for key, count in sorted(health_counts.items())
        ],
        "injection_audit_shapes": [
            {
                "has_intent": key[0],
                "has_applied": key[1],
                "has_verified": key[2],
                "confirmed": key[3],
                "count": count,
            }
            for key, count in sorted(incident_counts.items())
        ],
        "quality": {
            "schema_violations": 0,
            "digest_mismatches": 0,
            "period_violations": 0,
            "identity_violations": 0,
            "parent_graph_violations": 0,
            "deployment_mapping_violations": 0,
            "cross_period_incidents": 0,
        },
    }


def ingest_live_bundle(
    bundle_directory: str | Path,
    contract: LiveContractConfig,
    profile: BenchmarkProfile,
) -> IngestedLiveBundle:
    bundle_root = Path(bundle_directory)
    manifest_path = _safe_file(bundle_root, "manifest.yaml", "bundle manifest")
    manifest = _mapping(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
        "bundle manifest",
    )
    expected_schema = f"{contract.id}/v{contract.version}"
    if manifest.get("schema_version") != expected_schema:
        raise LiveContractError(f"bundle schema_version must equal {expected_schema}")
    benchmark = _mapping(manifest.get("benchmark"), "bundle benchmark")
    if benchmark.get("id") != profile.id or benchmark.get("commit") != profile.commit:
        raise LiveContractError("bundle benchmark identity/commit does not match its profile")
    if manifest.get("trace_format") != profile.trace_format:
        raise LiveContractError("bundle trace format does not match its profile")
    periods = _load_periods(manifest.get("periods"), contract.require_disjoint_periods)
    files = _mapping(manifest.get("files"), "bundle files")
    required_names = {
        "requests",
        "traces",
        "deployments",
        "health",
        "mesh",
        "injections",
        "operations",
    }
    if set(files) != required_names:
        raise LiveContractError(f"bundle files must be exactly {sorted(required_names)}")
    resolved: dict[str, Path] = {}
    for name in sorted(required_names):
        specification = _mapping(files[name], f"file specification {name}")
        path = _safe_file(bundle_root, specification.get("path"), f"bundle file {name}")
        expected_digest = str(specification.get("sha256", ""))
        if contract.require_file_digests:
            if len(expected_digest) != 64 or file_sha256(path) != expected_digest:
                raise LiveContractError(f"bundle file {name!r} digest mismatch")
        resolved[name] = path
    operations = _load_operations(resolved["operations"])
    if set(operations) != set(profile.operation_ids):
        raise LiveContractError("bundle operations do not match the frozen benchmark profile")
    requests = _load_requests(resolved["requests"], periods, operations)
    _validate_request_trace_ids(requests, profile.trace_format)
    if contract.require_external_request_census and not requests:
        raise LiveContractError("external request census must not be empty")
    spans = (
        parse_otlp_json(resolved["traces"])
        if profile.trace_format == "otlp_json_v1"
        else parse_jaeger_json(resolved["traces"])
    )
    _validate_span_graph(spans)
    deployments = _load_deployments(resolved["deployments"])
    health = _load_health(resolved["health"])
    mesh = _load_mesh(resolved["mesh"])
    injections = _load_injections(resolved["injections"])
    _validate_relations(
        requests,
        spans,
        deployments,
        health,
        mesh,
        injections,
        periods,
        operations,
    )
    audit = _audit(
        profile,
        periods,
        operations,
        requests,
        spans,
        deployments,
        health,
        mesh,
        injections,
        contract.maximum_health_age_seconds,
    )
    return IngestedLiveBundle(
        manifest=manifest,
        periods=periods,
        operations=operations,
        requests=tuple(requests),
        spans=tuple(spans),
        deployments=tuple(deployments),
        health=tuple(health),
        mesh=tuple(mesh),
        injections=tuple(injections),
        audit=audit,
    )


def write_ingested_bundle(
    bundle: IngestedLiveBundle,
    output_directory: str | Path,
) -> dict[str, Any]:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "requests.csv", REQUEST_FIELDS, bundle.requests)
    _write_csv(output / "spans.csv", SPAN_FIELDS, bundle.spans)
    _write_csv(output / "deployments.csv", DEPLOYMENT_FIELDS, bundle.deployments)
    _write_csv(output / "health.csv", HEALTH_FIELDS, bundle.health)
    _write_csv(output / "mesh.csv", MESH_FIELDS, bundle.mesh)
    _write_csv(output / "injections.csv", INJECTION_FIELDS, bundle.injections)
    (output / "audit.json").write_text(
        json.dumps(bundle.audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "kind": "normalized_live_bundle",
        "benchmark_id": bundle.audit["benchmark_id"],
        "benchmark_commit": bundle.audit["benchmark_commit"],
        "trace_format": bundle.audit["trace_format"],
        "source_bundle_id": bundle.manifest["bundle_id"],
        "row_counts": {
            "requests": len(bundle.requests),
            "spans": len(bundle.spans),
            "deployments": len(bundle.deployments),
            "health": len(bundle.health),
            "mesh": len(bundle.mesh),
            "injections": len(bundle.injections),
        },
        "quality": bundle.audit["quality"],
        "normalized_sha256": {
            name: file_sha256(output / name)
            for name in (
                "requests.csv",
                "spans.csv",
                "deployments.csv",
                "health.csv",
                "mesh.csv",
                "injections.csv",
                "audit.json",
            )
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
