"""Bounded remote qualification of the M9Q PMX observed-operation adapter."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from xml.etree import ElementTree as ET

from .pmx_observed_operations import (
    AdapterError, _digest, _identity, convert, file_sha256,
    from_otlp, write_conversion,
)

CASES = ("nested_errors", "colliding_instances", "contracted_forest")
JAR_SHA = "befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013"
OPTIONS_SHA = "7cd828213521e1a608938b05a8c2899556652d093624bde1afbaf9e5dacc597d"


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["cases"] != list(CASES) or config["technical_repetitions"] != 2:
        raise AdapterError("unexpected_conformance_design")
    if config["pmx_jar_sha256"] != JAR_SHA or config["options_sha256"] != OPTIONS_SHA:
        raise AdapterError("unexpected_upstream_binary_or_options")
    for record in config["repository_locks"]:
        source = Path(record["path"])
        if source.stat().st_size != record["bytes"] or file_sha256(source) != record["sha256"]:
            raise AdapterError(f"repository_lock_differs: {source}")
    return config


def _resource(service: str, instance: str) -> dict[str, Any]:
    return {"resource": {"attributes": [
        {"key": "service.name", "value": {"stringValue": service}},
        {"key": "service.instance.id", "value": {"stringValue": instance}},
    ]}}


def fixture(case: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Thirty server observations; the independent oracle uses explicit counts."""
    if case not in CASES:
        raise AdapterError("unknown_fixture")
    grouped, documents = {}, []
    labels = [("root", "a", "call"), ("child", "b", "call"), ("sibling", "c", "call")]
    if case == "colliding_instances":
        labels = [("shared", "a", "Handler"), ("shared", "b", "Handler"), ("different", "c", "Handler")]
    errors = (2, 1, 0) if case == "nested_errors" else ((0, 1, 0) if case == "contracted_forest" else (0, 0, 0))
    declared_hosts = {}
    for repeat in range(10):
        trace_id = f"{repeat + 1:032x}"
        base = 1800000000000000000 + repeat * 100000000
        spans, resources = [], []
        for index, (service, instance, operation) in enumerate(labels):
            resource = _resource(service, instance)
            scope = {"scope": {"name": "artificial-native-instrumentation"}}
            parent = "" if index == 0 else "0000000000000001"
            if case == "contracted_forest" and index == 1:
                parent = "0000000000000004"
            if case == "contracted_forest" and index == 2:
                parent = "ffffffffffffffff"
            start = base + (0, 2000000, 10000000)[index]
            duration = (30000000, 5000000, 5000000)[index]
            source = {"traceId": trace_id, "spanId": f"{index + 1:016x}", "parentSpanId": parent,
                      "name": operation, "kind": 2, "startTimeUnixNano": str(start),
                      "endTimeUnixNano": str(start + duration),
                      "status": {"code": 2 if repeat < errors[index] else 1}}
            native = from_otlp(resource, scope, source)
            spans.append(native)
            component = _identity(native)[0]
            declared_hosts[component] = f"fixture-{instance}" if case == "colliding_instances" else "fixture-worker"
            resources.append({**resource, "scopeSpans": [{**scope, "spans": [source]}]})
        if case == "contracted_forest":
            resource = _resource("root", "a")
            source = {"traceId": trace_id, "spanId": "0000000000000004", "parentSpanId": "0000000000000001",
                      "name": "client-intermediate", "kind": 3, "startTimeUnixNano": str(base + 1000000),
                      "endTimeUnixNano": str(base + 8000000), "status": {"code": 2 if repeat == 0 else 1}}
            spans.append(from_otlp(resource, {}, source))
            resources.append({**resource, "scopeSpans": [{"spans": [source]}]})
        grouped[trace_id] = spans
        documents.append({"resourceSpans": resources})
    result = convert(grouped, set(grouped), declared_hosts)
    role_to_operation, component_hosts, operation_components = {}, {}, {}
    for index, label in enumerate(labels):
        selected = [m for m in result["mapping"] if (m["service"], m["instance_value"], m["operation"]) == label]
        if len(selected) != 10 or sum(m["error_status"] for m in selected) != errors[index]:
            raise AdapterError("fixture_native_inventory_mismatch")
        if {m["duration_us"] for m in selected} != {30000 if index == 0 else 5000}:
            raise AdapterError("fixture_timing_conversion_mismatch")
        operations = {m["pmx_operation"] for m in selected}
        if len(operations) != 1:
            raise AdapterError("fixture_operation_identity_mismatch")
        role_to_operation[index] = next(iter(operations))
        operation_components[role_to_operation[index]] = selected[0]["pmx_component"]
        for item in selected:
            component_hosts[item["pmx_component"]] = item["declared_host"].upper() + "-SRV"
    expected = {
        "case": case, "operations": {role_to_operation[i]: errors[i] / 10 for i in range(3)},
        "edges": sorted([[role_to_operation[0], role_to_operation[1]]] +
                        ([] if case == "contracted_forest" else [[role_to_operation[0], role_to_operation[2]]])),
        "component_hosts": component_hosts, "server_observations": 30,
        "operation_components": operation_components,
        "entry_operation_counts": {role_to_operation[0]: 10} | ({role_to_operation[2]: 10} if case == "contracted_forest" else {}),
        "observed_trees": 20 if case == "contracted_forest" else 10,
        "adapter_duration_microseconds": {role_to_operation[i]: 30000 if i == 0 else 5000 for i in range(3)},
        "leaf_operation_seconds": {role_to_operation[i]: .005 for i in (1, 2)},
        "oracle_basis": "ten independently specified invocations per role and explicit error counts",
    }
    actual_probabilities = {r["operation"]: r["error_probability"] for r in result["operation_oracle"]}
    actual_edges = sorted([[r["caller"], r["callee"]] for r in result["edge_oracle"]])
    if actual_probabilities != expected["operations"] or actual_edges != expected["edges"]:
        raise AdapterError("fixture_envelope_error_or_edge_mismatch")
    if len(result["mapping"]) != 30 or len(result["envelope"]["data"]) != expected["observed_trees"]:
        raise AdapterError("fixture_server_conservation_mismatch")
    return result, expected, documents


def build_contract(config_path: Path, author_options: Path, out: Path) -> dict[str, Any]:
    validate_config(config_path)
    if file_sha256(author_options) != OPTIONS_SHA:
        raise AdapterError("author_options_hash_mismatch")
    original = author_options.read_text(encoding="utf-8")
    if original.count("traces/jaegercustomers.json") != 1:
        raise AdapterError("author_input_path_mismatch")
    for case in CASES:
        result, expected, documents = fixture(case)
        root = out / case
        write_conversion(result, root / "adapter")
        _write(root / "expected.json", expected)
        _write(root / "traces" / "observed.json", result["envelope"])
        (root / "native-otlp.jsonl").write_text("".join(json.dumps(d, sort_keys=True) + "\n" for d in documents), encoding="utf-8")
        # Preserve the author's other options, including CPU defaults. CPU and
        # resource-demand accuracy are not inferred from these reliability controls.
        (root / "Options.txt").write_text(original.replace("traces/jaegercustomers.json", "traces/observed.json"), encoding="utf-8")
    manifest = {"kind": "m9q_synthetic_adapter_contract", "config_sha256": file_sha256(config_path),
                "cases": list(CASES), "technical_repetitions": 2, "dynamic_invocations": 0,
                "files": {p.relative_to(out).as_posix(): file_sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}}
    _write(out / "contract-manifest.json", manifest)
    return manifest


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def inspect_pcm(root: Path) -> dict[str, Any]:
    """Resolve identifiers, never stdout positions or incidental XML order."""
    trees: dict[str, ET.Element] = {}
    index: dict[tuple[str, str], ET.Element] = {}
    for suffix in ("repository", "system", "allocation", "resourceenvironment", "usagemodel"):
        files = list(root.glob(f"*.{suffix}"))
        if len(files) != 1:
            raise AdapterError(f"expected_one_pcm_{suffix}")
        tree = ET.parse(files[0]).getroot()
        trees[files[0].name] = tree
        for node in tree.iter():
            node_id = node.get("id") or node.get("{http://www.omg.org/XMI}id")
            if node_id:
                key = files[0].name, node_id
                if key in index:
                    raise AdapterError("duplicate_pcm_identifier")
                index[key] = node

    def resolve(value: str, current: str) -> tuple[ET.Element, str]:
        if "#" in value:
            filename, identifier = value.rsplit("#", 1)
            filename = filename or current
        else:
            filename, identifier = current, value
        if (filename, identifier) not in index:
            raise AdapterError(f"unresolved_pcm_reference:{filename}#{identifier}")
        return index[filename, identifier], filename

    operations, edges, components, demands = {}, set(), set(), {}
    for filename, tree in trees.items():
        if not filename.endswith(".repository"):
            continue
        for component in tree:
            if _local(component.tag) != "components__Repository":
                continue
            component_name = component.attrib["entityName"]
            components.add(component_name)
            for seff in component:
                if _local(seff.tag) != "serviceEffectSpecifications__BasicComponent":
                    continue
                signature, _ = resolve(seff.attrib["describedService__SEFF"], filename)
                operation = signature.attrib["entityName"]
                if operation in operations:
                    raise AdapterError("duplicate_pcm_operation_seff")
                failures = [float(n.attrib["failureProbability"]) for n in seff.iter() if "failureProbability" in n.attrib]
                if len(failures) > 1 or any(not math.isfinite(p) or not 0 <= p <= 1 for p in failures):
                    raise AdapterError("ambiguous_pcm_operation_failure")
                operations[operation] = {"component": component_name, "failure_probability": failures[0] if failures else 0.0}
                demands[operation] = [n.get("specification", "") for n in seff.iter()
                                      if _local(n.tag) == "specification_ParametericResourceDemand"]
                for node in seff.iter():
                    if "calledService_ExternalService" in node.attrib:
                        callee, _ = resolve(node.attrib["calledService_ExternalService"], filename)
                        edges.add((operation, callee.attrib["entityName"]))
    allocations, entry_counts = [], Counter()
    for filename, tree in trees.items():
        if not filename.endswith(".allocation"):
            continue
        for context in tree:
            if _local(context.tag) != "allocationContexts_Allocation":
                continue
            links = {_local(n.tag): n.attrib["href"] for n in context}
            assembly, assembly_file = resolve(links["assemblyContext_AllocationContext"], filename)
            encapsulated = next(n for n in assembly if _local(n.tag) == "encapsulatedComponent__AssemblyContext")
            component, _ = resolve(encapsulated.attrib["href"], assembly_file)
            resource, _ = resolve(links["resourceContainer_AllocationContext"], filename)
            allocations.append({"component": component.attrib["entityName"], "host": resource.attrib["entityName"]})
    for filename, tree in trees.items():
        if not filename.endswith(".usagemodel"):
            continue
        for node in tree.iter():
            if not any(value.endswith(":EntryLevelSystemCall") for key, value in node.attrib.items() if _local(key) == "type"):
                continue
            operation_link = next(child for child in node if _local(child.tag) == "operationSignature__EntryLevelSystemCall")
            operation, _ = resolve(operation_link.attrib["href"], filename)
            entry_counts[operation.attrib["entityName"]] += 1
    return {"operations": operations, "edges": sorted([list(edge) for edge in edges]),
            "components": sorted(components), "allocations": sorted(allocations, key=lambda x: (x["component"], x["host"])),
            "entry_operation_counts": dict(sorted(entry_counts.items())),
            "resource_demands": demands, "model_files": {name: file_sha256(root / name) for name in trees}}


def compare_pcm(actual: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    probabilities = {op: row["failure_probability"] for op, row in actual["operations"].items()}
    operations_match = set(probabilities) == set(expected["operations"])
    probabilities_match = operations_match and all(abs(probabilities[op] - p) <= 1e-12 for op, p in expected["operations"].items())
    wanted_allocations = sorted([{"component": c, "host": h} for c, h in expected["component_hosts"].items()], key=lambda x: (x["component"], x["host"]))
    checks = {"operation_set": operations_match, "operation_error_probabilities": probabilities_match,
              "call_edges": actual["edges"] == expected["edges"],
              "component_set": actual["components"] == sorted(expected["component_hosts"]),
              "operation_ownership": {op: row["component"] for op, row in actual["operations"].items()} == expected["operation_components"],
              "entry_operation_counts": actual["entry_operation_counts"] == expected["entry_operation_counts"],
              "allocation_references": actual["allocations"] == wanted_allocations}
    timing = []
    for operation, seconds in expected["leaf_operation_seconds"].items():
        values = actual["resource_demands"].get(operation, [])
        try:
            numeric = float(values[0]) if len(values) == 1 else None
        except ValueError:
            numeric = None
        timing.append({"operation": operation, "native_leaf_duration_seconds": seconds,
                       "pcm_resource_demand_literal": numeric,
                       "numeric_value_matches_seconds": numeric is not None and abs(numeric - seconds) <= 1e-9,
                       "interpretation": "resolved PCM resource-demand literal; performance calibration and CPU defaults are outside structural/error conformance"})
    return {"checks": checks, "qualified": all(checks.values()), "timing_diagnostic": timing}


def run_pmx(jar: Path, input_root: Path, out: Path) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise AdapterError("pmx_execution_is_remote_only")
    if file_sha256(jar) != JAR_SHA:
        raise AdapterError("pmx_jar_hash_mismatch")
    out.mkdir(parents=True, exist_ok=False)
    (out / "results").mkdir()
    shutil.copyfile(input_root / "Options.txt", out / "Options.txt")
    shutil.copytree(input_root / "traces", out / "traces")
    commands = "main:main -of Options.txt\nexit 0\n"
    (out / "stdin.txt").write_text(commands, encoding="utf-8")
    started, started_utc = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    with (out / "stdout.log").open("wb") as stdout:
        process = subprocess.Popen(["/usr/bin/time", "-v", "-o", "resource-usage.txt", "timeout",
                                    "--signal=TERM", "--kill-after=10s", "180s", "java",
                                    "-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector",
                                    "-jar", str(jar.resolve())], cwd=out, stdin=subprocess.PIPE, stdout=stdout, stderr=subprocess.STDOUT)
        time.sleep(20)
        command_utc = datetime.now(timezone.utc).isoformat()
        process.communicate(commands.encode(), timeout=195)
    record = {"started_at": started_utc, "command_sent_at": command_utc,
              "finished_at": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": time.perf_counter() - started,
              "exit_code": process.returncode, "internal_watchdog_seconds": 180,
              "startup_stabilization_seconds": 20, "jar_sha256": JAR_SHA}
    _write(out / "execution.json", record)
    return record


def execute_contract(config_path: Path, contract: Path, jar: Path, out: Path) -> dict[str, Any]:
    validate_config(config_path)
    manifest = json.loads((contract / "contract-manifest.json").read_text())
    if manifest["config_sha256"] != file_sha256(config_path):
        raise AdapterError("contract_config_mismatch")
    for name, expected_hash in manifest["files"].items():
        if file_sha256(contract / name) != expected_hash:
            raise AdapterError("contract_input_changed")
    rows, semantic = [], {}
    for case in CASES:
        expected = json.loads((contract / case / "expected.json").read_text())
        for repeat in (1, 2):
            root = out / "raw" / case / f"repeat-{repeat}"
            execution = run_pmx(jar, contract / case, root)
            row = {"case": case, "repeat": repeat, "execution": execution, "qualified": False}
            try:
                actual = inspect_pcm(root / "results")
                decision = compare_pcm(actual, expected)
                row.update(decision, qualified=execution["exit_code"] == 0 and decision["qualified"])
                # Volatile XML IDs/hashes are excluded from repeat agreement.
                semantic.setdefault(case, []).append(_digest({k: v for k, v in actual.items() if k != "model_files"}))
                _write(root / "resolved-pcm.json", actual)
            except (AdapterError, ET.ParseError, KeyError, ValueError, StopIteration) as exc:
                row["model_error"] = f"{type(exc).__name__}: {exc}"
            _write(root / "decision.json", row)
            rows.append(row)
    consistent = {case: len(semantic.get(case, [])) == 2 and len(set(semantic[case])) == 1 for case in CASES}
    result = {"kind": "m9q_synthetic_adapter_conformance", "config_sha256": file_sha256(config_path),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "head_sha": os.environ.get("GITHUB_SHA"),
              "results": rows, "repeat_agreement": consistent,
              "qualified": len(rows) == 6 and all(row["qualified"] for row in rows) and all(consistent.values()),
              "invocations": len(rows), "evaluator_rows_read": 0, "availability_forecasts": 0}
    _write(out / "conformance-decision.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "build", "execute"))
    parser.add_argument("--config", type=Path, default=Path("configs/m9q_pmx_observed_operations.json"))
    parser.add_argument("--options", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--jar", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.action == "validate":
        validate_config(args.config)
    elif args.action == "build":
        build_contract(args.config, args.options, args.out)
    else:
        result = execute_contract(args.config, args.contract, args.jar, args.out)
        if not result["qualified"]:
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
