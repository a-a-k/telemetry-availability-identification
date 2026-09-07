"""Explicit observed-server projection for the pinned PMX performability reader.

This adapter does not estimate external-request availability. Full native-data
conversion and PMX execution belong to remote workflows; tests use tiny inputs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from .pmx_recovery import _attributes


class AdapterError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def _true(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.lower() == "true")


def _id(value: Any) -> str:
    result = str(value or "").lower()
    if not result or any(x not in "0123456789abcdef" for x in result):
        raise AdapterError("missing_or_invalid_identifier")
    return result


@dataclass(frozen=True)
class NativeSpan:
    trace_id: str
    span_id: str
    parent_id: str
    service: str
    operation: str
    server: bool
    start_us: int
    duration_us: int
    start_remainder_ns: int
    duration_remainder_ns: int
    attributes: dict[str, Any]
    resource_attributes: dict[str, Any]
    error_tag: bool
    error_status: bool
    native_kind: str
    native_links: list[Any]

    @property
    def error(self) -> bool:
        return self.error_tag or self.error_status


def _timing(start: Any, duration: Any, divisor: int) -> tuple[int, int, int, int]:
    # Do not silently truncate floating native timestamps before unit conversion.
    if isinstance(start, bool) or isinstance(duration, bool):
        raise AdapterError("invalid_duration_or_timestamp")
    if isinstance(start, float) or isinstance(duration, float):
        raise AdapterError("noninteger_native_time")
    try:
        start_value, duration_value = int(start), int(duration)
    except (ValueError, TypeError) as exc:
        raise AdapterError("invalid_duration_or_timestamp") from exc
    start_us, start_rem = divmod(start_value, divisor)
    duration_us, duration_rem = divmod(duration_value, divisor)
    if start_value < 0 or duration_us <= 0 or max(start_us, duration_us) * 1000 > 2**63 - 1:
        raise AdapterError("invalid_duration_or_timestamp")
    return start_us, duration_us, start_rem, duration_rem


def from_jaeger(trace: Mapping[str, Any], span: Mapping[str, Any]) -> NativeSpan:
    trace_id = _id(trace.get("traceID"))
    if _id(span.get("traceID", trace_id)) != trace_id:
        raise AdapterError("conflicting_trace_identity")
    parents = [r for r in span.get("references", []) if r.get("refType") == "CHILD_OF"]
    if len(parents) > 1:
        raise AdapterError("ambiguous_parent")
    if parents and _id(parents[0].get("traceID", trace_id)) != trace_id:
        raise AdapterError("cross_trace_parent")
    process = trace.get("processes", {}).get(span.get("processID"), {})
    resource = {str(t["key"]): t.get("value") for t in process.get("tags", [])}
    attrs = {str(t["key"]): t.get("value") for t in span.get("tags", [])}
    kind = str(attrs.get("span.kind", "")).lower()
    service, operation = str(process.get("serviceName", "")), str(span.get("operationName", ""))
    if not service or not operation:
        raise AdapterError("missing_operation_identity")
    return NativeSpan(trace_id, _id(span.get("spanID")), _id(parents[0].get("spanID")) if parents else "",
                      service, operation, kind == "server", *_timing(span.get("startTime"), span.get("duration"), 1),
                      attrs, resource, _true(attrs.get("error")), False, kind,
                      [dict(r) for r in span.get("references", []) if r.get("refType") != "CHILD_OF"])


def from_otlp(resource_group: Mapping[str, Any], scope_group: Mapping[str, Any],
              span: Mapping[str, Any]) -> NativeSpan:
    resource = _attributes(resource_group.get("resource", {}).get("attributes", []))
    attrs = _attributes(span.get("attributes", []))
    scope = scope_group.get("scope", scope_group.get("instrumentationLibrary", {}))
    attrs = {**attrs, "adapter.original.scope": scope}
    service, operation = str(resource.get("service.name", "")), str(span.get("name", ""))
    if not service or not operation:
        raise AdapterError("missing_operation_identity")
    kind = str(span.get("kind", ""))
    start, end = span.get("startTimeUnixNano"), span.get("endTimeUnixNano")
    if isinstance(start, (float, bool)) or isinstance(end, (float, bool)):
        raise AdapterError("noninteger_native_time")
    try:
        duration = int(end) - int(start)
    except (ValueError, TypeError) as exc:
        raise AdapterError("invalid_duration_or_timestamp") from exc
    return NativeSpan(_id(span.get("traceId")), _id(span.get("spanId")),
                      _id(span["parentSpanId"]) if span.get("parentSpanId") else "", service, operation,
                      kind in {"2", "SPAN_KIND_SERVER"}, *_timing(start, duration, 1000),
                      attrs, resource, _true(attrs.get("error")),
                      str(span.get("status", {}).get("code", "")) in {"2", "STATUS_CODE_ERROR"},
                      kind, list(span.get("links", [])))


def read_native(path: Path, selected: set[str], native_format: str) -> tuple[dict[str, list[NativeSpan]], dict[str, Any]]:
    """Selection occurs before span normalization; invalid traces stay in census."""
    grouped: dict[str, list[NativeSpan]] = defaultdict(list)
    invalid: dict[str, list[str]] = defaultdict(list)
    metadata: dict[str, Any] = {"malformed_json_records": 0, "invalid_traces": invalid}

    def append(trace_id: str, factory: Any, *args: Any) -> None:
        if trace_id not in selected:
            return
        try:
            grouped[trace_id].append(factory(*args))
        except (AdapterError, TypeError, KeyError, AttributeError) as exc:
            invalid[trace_id].append(str(exc))

    if native_format == "jaeger_json_v1":
        data = json.loads(path.read_text(encoding="utf-8"))
        for trace in data["data"]:
            trace_id = str(trace.get("traceID", "")).lower()
            if trace_id in selected:
                for span in trace.get("spans", []):
                    append(trace_id, from_jaeger, trace, span)
    elif native_format == "otlp_jsonl_v1":
        with path.open(encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    metadata["malformed_json_records"] += 1
                    continue
                for resource in data.get("resourceSpans", []):
                    for scope in resource.get("scopeSpans", resource.get("instrumentationLibrarySpans", [])):
                        for span in scope.get("spans", []):
                            append(str(span.get("traceId", "")).lower(), from_otlp, resource, scope, span)
    else:
        raise AdapterError("unsupported_native_format")
    return dict(grouped), metadata


def select_learner_ids(path: Path) -> set[str]:
    selected, forbidden = set(), set()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"period", "trace_id"}.issubset(reader.fieldnames or []):
            raise AdapterError("missing_trace_selection_columns")
        for row in reader:
            trace_id = str(row["trace_id"]).lower()
            if not trace_id:
                continue
            if row["period"] in {"baseline", "calibration"}:
                selected.add(_id(trace_id))
            elif row["period"] == "test":
                forbidden.add(_id(trace_id))
            else:
                raise AdapterError("unknown_period")
    if selected & forbidden:
        raise AdapterError("learner_test_overlap")
    return selected


def _identity(span: NativeSpan) -> tuple[str, str, str, str, str]:
    for key in ("service.instance.id", "container.id", "container.name", "k8s.pod.name", "host.name"):
        value = span.resource_attributes.get(key)
        if value is not None and str(value):
            break
    else:
        key, value = "unresolved", "unresolved"
    component = "component_" + _digest([span.service, key, str(value)])[:24]
    operation = "operation_" + _digest([span.service, key, str(value), span.operation])[:24]
    return component, operation, key, str(value), "process_" + _digest([component])[:24]


def _tag(key: str, value: str) -> dict[str, str]:
    return {"key": key, "type": "string", "value": value}


def project_trace(spans: Iterable[NativeSpan], host: str | Mapping[str, str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not host:
        raise AdapterError("missing_declared_host")
    by_id: dict[str, NativeSpan] = {}
    duplicates = 0
    for span in spans:
        if span.span_id in by_id:
            if span != by_id[span.span_id]:
                raise AdapterError("conflicting_duplicate")
            duplicates += 1
        by_id[span.span_id] = span
    if len({s.trace_id for s in by_id.values()}) > 1:
        raise AdapterError("mixed_trace_identity")
    for span_id in by_id:
        seen: set[str] = set()
        cursor = span_id
        while cursor in by_id:
            if cursor in seen:
                raise AdapterError("parent_cycle")
            seen.add(cursor)
            cursor = by_id[cursor].parent_id
    servers = {key: span for key, span in by_id.items() if span.server}
    parents, roots, missing = {}, {}, {}
    for span_id, span in servers.items():
        cursor, contracted = span.parent_id, 0
        while cursor in by_id and cursor not in servers:
            contracted += 1
            cursor = by_id[cursor].parent_id
        parents[span_id] = cursor if cursor in servers else ""
        missing[span_id] = cursor if cursor and cursor not in by_id else ""
        roots[span_id] = contracted
    tree_groups: dict[str, list[str]] = defaultdict(list)
    for span_id in servers:
        root = span_id
        while parents[root]:
            root = parents[root]
        tree_groups[root].append(span_id)
    traces, mapping = [], []
    for root, member_ids in sorted(tree_groups.items()):
        trace_id = _digest(["m9q-observed-tree-v1", servers[root].trace_id, root])[:32]
        processes, output_spans = {}, []
        for span_id in sorted(member_ids, key=lambda x: (servers[x].start_us, x)):
            span = servers[span_id]
            component, operation, instance_key, instance_value, process = _identity(span)
            declared_host = host if isinstance(host, str) else host.get(component, "")
            if not declared_host:
                raise AdapterError("missing_declared_host")
            processes[process] = {"id": process, "serviceName": component,
                                  "tags": [_tag("host.name", declared_host)]}
            parent = parents[span_id]
            output_spans.append({"traceID": trace_id, "spanID": span_id, "flags": 1,
                                 "operationName": operation, "processID": process,
                                 "startTime": span.start_us, "duration": span.duration_us,
                                 "references": [{"refType": "CHILD_OF", "traceID": trace_id, "spanID": parent}] if parent else [],
                                 "tags": [_tag("otel.library.name", "adapter.spring-webmvc.m9q"),
                                          _tag("error", "true" if span.error else "false")], "logs": []})
            mapping.append({**asdict(span), "pmx_trace_id": trace_id, "pmx_component": component,
                            "pmx_operation": operation, "pmx_parent_span_id": parent,
                            "instance_key": instance_key, "instance_value": instance_value,
                            "declared_host": declared_host, "missing_parent_id": missing[span_id],
                            "contracted_intermediate_spans": roots[span_id]})
        traces.append({"traceID": trace_id, "startTime": servers[root].start_us,
                       "processes": processes, "spans": output_spans})
    audit = {"unique_native_spans": len(by_id), "identical_duplicates": duplicates,
             "server_spans": len(servers), "observed_trees": len(traces),
             "missing_parent_roots": sum(bool(v) for v in missing.values()),
             "nonserver_errors": sum(s.error for s in by_id.values() if not s.server),
             "native_kinds": dict(Counter(s.native_kind for s in by_id.values())),
             "unresolved_instance_spans": sum(m["instance_key"] == "unresolved" for m in mapping),
             "complete_single_observed_tree": len(traces) == 1 and not any(missing.values()),
             "external_request_completeness_established": False}
    return traces, mapping, audit


def convert(grouped: Mapping[str, list[NativeSpan]], selected: set[str], host: str | Mapping[str, str],
            invalid: Mapping[str, list[str]] | None = None) -> dict[str, Any]:
    invalid = invalid or {}
    traces, mapping, census = [], [], []
    for trace_id in sorted(selected):
        row: dict[str, Any] = {"original_trace_id": trace_id, "status": "pending"}
        if trace_id in invalid:
            row.update(status="invalid_native_trace", reasons=invalid[trace_id])
        elif not grouped.get(trace_id):
            row["status"] = "absent_from_raw"
        else:
            try:
                output, span_mapping, audit = project_trace(grouped[trace_id], host)
                row.update(audit, status="adapted" if output else "no_server_spans")
                traces.extend(output)
                mapping.extend(span_mapping)
            except AdapterError as exc:
                row.update(status="invalid_native_trace", reasons=[str(exc)])
        census.append(row)
    counts: dict[str, dict[str, Any]] = {}
    edges: Counter[tuple[str, str]] = Counter()
    for trace in traces:
        by_id = {s["spanID"]: s for s in trace["spans"]}
        for span in trace["spans"]:
            name = span["operationName"]
            row = counts.setdefault(name, {"operation": name, "component": trace["processes"][span["processID"]]["serviceName"],
                                            "invocations": 0, "errors": 0})
            row["invocations"] += 1
            row["errors"] += int(any(t["key"] == "error" and t["value"] == "true" for t in span["tags"]))
            for ref in span["references"]:
                edges[(by_id[ref["spanID"]]["operationName"], name)] += 1
    for row in counts.values():
        row["error_probability"] = row["errors"] / row["invocations"]
    return {"envelope": {"data": traces}, "mapping": mapping, "census": census,
            "operation_oracle": sorted(counts.values(), key=lambda x: x["operation"]),
            "edge_oracle": [{"caller": a, "callee": b, "observed_calls": n} for (a, b), n in sorted(edges.items())],
            "summary": {"selected_traces": len(selected), "status_counts": dict(Counter(r["status"] for r in census)),
                        "adapted_server_spans": len(mapping), "observed_trees": len(traces),
                        "operations": len(counts), "distinct_edges": len(edges),
                        "external_request_forecasts": 0, "evaluator_rows_read": 0}}


def write_conversion(result: dict[str, Any], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for key, value in result.items():
        (out / f"{key}.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", required=True, type=Path)
    parser.add_argument("--format", choices=("jaeger_json_v1", "otlp_jsonl_v1"), required=True)
    parser.add_argument("--trace-join", required=True, type=Path)
    parser.add_argument("--declared-host", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise AdapterError("full_native_conversion_is_remote_only")
    selected = select_learner_ids(args.trace_join)
    grouped, parse_audit = read_native(args.native, selected, args.format)
    result = convert(grouped, selected, args.declared_host, parse_audit["invalid_traces"])
    result["parse_audit"] = parse_audit
    result["source"] = {"native_sha256": file_sha256(args.native),
                        "selection_sha256": file_sha256(args.trace_join),
                        "format": args.format, "declared_host": args.declared_host,
                        "run_id": os.environ.get("GITHUB_RUN_ID"), "head_sha": os.environ.get("GITHUB_SHA")}
    write_conversion(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
