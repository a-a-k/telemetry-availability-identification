"""Gated M9Q historical learner census and observed-operation fidelity audit."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from xml.etree import ElementTree as ET

from .pmx_adapter_conformance import JAR_SHA, OPTIONS_SHA, compare_pcm, inspect_pcm, validate_config
from .pmx_observed_operations import AdapterError, _id, convert, file_sha256, read_native, write_conversion
from .pmx_usage_contract_audit import _metadata, aggregated_entry_counts, reconstructed_inventory, usage_details


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _remote() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise AdapterError("application_census_is_remote_only")


def validate(path: Path) -> dict[str, Any]:
    config = _read(path)
    validate_config(Path("configs/m9q_pmx_observed_operations.json"))
    acceptance = _read(Path("configs/m9q_application_acceptance.json"))
    for row in config["repository_locks"] + acceptance["repository_locks"]:
        source = Path(row["path"])
        if source.stat().st_size != row["bytes"] or file_sha256(source) != row["sha256"]:
            raise AdapterError(f"application_source_lock_differs:{source}")
    if len(config["samples"]) != 4 or config["internal_watchdog_seconds"] != 1800:
        raise AdapterError("application_census_design_differs")
    return config


def check_gate(config_path: Path, review: Path, metadata: Path) -> dict[str, Any]:
    _remote()
    validate(config_path)
    acceptance = _read(Path("configs/m9q_application_acceptance.json"))
    lock = acceptance["review"]
    _metadata(metadata, lock)
    if review.stat().st_size != lock["file_bytes"] or file_sha256(review) != lock["file_sha256"]:
        raise AdapterError("accepted_review_file_differs")
    result = _read(review)
    if result["original_conformance_qualified"] or not result["qualified_after_oracle_repair"] or len(result["rows"]) != 6:
        raise AdapterError("application_acceptance_not_satisfied")
    return {"status": "accepted_after_explicit_oracle_repair", "review_run_id": lock["run_id"],
            "review_file_sha256": lock["file_sha256"], "checked_at": datetime.now(timezone.utc).isoformat()}


def historical_learner_ids(path: Path) -> tuple[set[str], dict[str, Any]]:
    """The M7 join includes declared semantic sentinels before the three periods."""
    selected, excluded = set(), set()
    periods: Counter[str] = Counter()
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"period", "trace_id"}.issubset(reader.fieldnames or []):
            raise AdapterError("missing_historical_membership_columns")
        for row in reader:
            period = row["period"]
            if period not in {"baseline", "calibration", "test", "sentinel"}:
                raise AdapterError("unknown_historical_period")
            periods[period] += 1
            if not row["trace_id"]:
                continue
            trace_id = _id(row["trace_id"])
            (selected if period in {"baseline", "calibration"} else excluded).add(trace_id)
    if selected & excluded:
        raise AdapterError("historical_learner_excluded_overlap")
    return selected, {"period_rows": dict(periods), "selected_trace_ids": len(selected),
                      "excluded_test_or_sentinel_trace_ids": len(excluded), "outcome_columns_used": False}


def prepare(config_path: Path, source_root: Path, audit_root: Path, metadata_root: Path,
            review: Path, options: Path, out: Path) -> dict[str, Any]:
    _remote()
    config = validate(config_path)
    gate = check_gate(config_path, review, metadata_root / "review.json")
    _metadata(metadata_root / "preserved.json", config["artifacts"]["preserved"])
    _metadata(metadata_root / "inventory.json", config["artifacts"]["inventory"])
    inventory_path = audit_root / "file-inventory.csv"
    if file_sha256(inventory_path) != config["inventory_file_sha256"]:
        raise AdapterError("historical_file_inventory_differs")
    if file_sha256(options) != OPTIONS_SHA:
        raise AdapterError("author_options_differs")
    with inventory_path.open(encoding="utf-8-sig", newline="") as stream:
        inventory = {row["relative_path"].replace("\\", "/"): row for row in csv.DictReader(stream)
                     if row["evidence_group"] == "raw_audit_sample"}
    raw_root = source_root / "raw-audit-samples"
    actual_names = {p.name for p in raw_root.glob("m7-raw-audit-sample-*") if p.is_dir()}
    if actual_names != {s["artifact_directory"] for s in config["samples"]}:
        raise AdapterError("historical_raw_sample_census_differs")
    original_options = options.read_text(encoding="utf-8")
    if original_options.count("traces/jaegercustomers.json") != 1:
        raise AdapterError("author_input_path_differs")
    sample_rows = []
    for sample in config["samples"]:
        directory = raw_root / sample["artifact_directory"]
        files = ("campaign-manifest.json", "trace-join.csv", sample["native_file"])
        file_rows = []
        for name in files:
            p = directory / name
            key = p.relative_to(raw_root).as_posix()
            record = inventory.get(key)
            if record is None or p.stat().st_size != int(record["size_in_bytes"]) or file_sha256(p) != record["sha256"]:
                raise AdapterError(f"historical_raw_file_differs:{key}")
            file_rows.append({"source_path": key, "bytes": p.stat().st_size, "sha256": record["sha256"]})
        campaign = _read(directory / "campaign-manifest.json")
        identity = {key: campaign.get(key) for key in ("profile", "placement", "failure_law", "repetition")}
        expected_identity = {"profile": sample["profile"], "placement": sample["placement"], "failure_law": "NCD", "repetition": 0}
        if identity != expected_identity:
            raise AdapterError("historical_campaign_identity_differs")
        started = time.perf_counter()
        selected, selection_audit = historical_learner_ids(directory / "trace-join.csv")
        if len(selected) != 3840:
            raise AdapterError("historical_learner_selection_count_differs")
        grouped, parse_audit = read_native(directory / sample["native_file"], selected, sample["native_format"])
        result = convert(grouped, selected, sample["declared_host"], parse_audit["invalid_traces"])
        elapsed = time.perf_counter() - started
        target = out / sample["key"]
        write_conversion(result, target / "adapter")
        _write(target / "adapter/parse_audit.json", parse_audit)
        _write(target / "adapter/selection_audit.json", selection_audit)
        _write(target / "traces/observed.json", result["envelope"])
        (target / "Options.txt").write_text(original_options.replace("traces/jaegercustomers.json", "traces/observed.json"), encoding="utf-8")
        roots = [span for trace in result["envelope"]["data"] for span in trace["spans"] if not span["references"]]
        counts = dict(Counter(span["operationName"] for span in roots))
        first_times: dict[str, int] = {}
        for span in roots:
            operation = span["operationName"]
            first_times[operation] = min(first_times.get(operation, span["startTime"]), span["startTime"])
        expected = {"operations": {row["operation"]: row["error_probability"] for row in result["operation_oracle"]},
                    "operation_components": {row["operation"]: row["component"] for row in result["operation_oracle"]},
                    "component_hosts": {row["pmx_component"]: sample["declared_host"].upper() + "-SRV" for row in result["mapping"]},
                    "edges": sorted([[row["caller"], row["callee"]] for row in result["edge_oracle"]]),
                    "entry_operation_counts": aggregated_entry_counts(counts) if counts else {},
                    "leaf_operation_seconds": {}}
        _write(target / "expected-observed-projection.json", expected)
        census = result["census"]
        coverage = {"requested_trace_ids": len(selected), "status_counts": result["summary"]["status_counts"],
                    "native_spans_in_valid_traces": sum(row.get("unique_native_spans", 0) for row in census),
                    "selected_server_spans": len(result["mapping"]), "observed_trees": len(result["envelope"]["data"]),
                    "missing_parent_roots": sum(row.get("missing_parent_roots", 0) for row in census),
                    "multiple_tree_traces": sum(row.get("observed_trees", 0) > 1 for row in census),
                    "unresolved_instance_spans": sum(row.get("unresolved_instance_spans", 0) for row in census),
                    "discarded_nonserver_errors": sum(row.get("nonserver_errors", 0) for row in census),
                    "malformed_json_records": parse_audit["malformed_json_records"],
                    "root_operation_first_timestamp_collisions": len(first_times) - len(set(first_times.values())),
                    "full_external_request_mapping_established": False}
        manifest = {"kind": "m9q_historical_learner_projection", "sample": sample, "source_identity": identity,
                    "config_sha256": file_sha256(config_path), "gate": gate, "source_files": file_rows,
                    "coverage": coverage, "parse_projection_seconds": elapsed,
                    "native_input_bytes": (directory / sample["native_file"]).stat().st_size,
                    "learner_operations": len(expected["operations"]), "learner_call_edges": len(expected["edges"]),
                    "evaluator_rows_read": 0, "availability_forecasts": 0,
                    "run_id": os.environ.get("GITHUB_RUN_ID"), "head_sha": os.environ.get("GITHUB_SHA"),
                    "files": {p.relative_to(target).as_posix(): file_sha256(p) for p in sorted(target.rglob("*")) if p.is_file()}}
        _write(target / "learner-contract.json", manifest)
        sample_rows.append({key: value for key, value in manifest.items() if key != "files"})
    summary = {"kind": "m9q_four_sample_preparation", "samples": sample_rows, "sample_count": len(sample_rows), "evaluator_rows_read": 0}
    _write(out / "preparation-summary.json", summary)
    return summary


def execute(config_path: Path, contract: Path, jar: Path, out: Path) -> dict[str, Any]:
    _remote()
    config = validate(config_path)
    manifest = _read(contract / "learner-contract.json")
    if manifest["config_sha256"] != file_sha256(config_path) or manifest["run_id"] != os.environ.get("GITHUB_RUN_ID"):
        raise AdapterError("application_contract_source_differs")
    for name, digest in manifest["files"].items():
        if file_sha256(contract / name) != digest:
            raise AdapterError("frozen_application_projection_changed")
    if file_sha256(jar) != JAR_SHA:
        raise AdapterError("pmx_binary_differs")
    out.mkdir(parents=True, exist_ok=False)
    _write(out / "learner-contract.json", manifest)
    expected = _read(contract / "expected-observed-projection.json")
    result = {"kind": "m9q_historical_projection_fidelity", "sample": manifest["sample"],
              "coverage": manifest["coverage"], "parse_projection_seconds": manifest["parse_projection_seconds"],
              "native_input_bytes": manifest["native_input_bytes"], "learner_operations": manifest["learner_operations"],
              "learner_call_edges": manifest["learner_call_edges"], "config_sha256": file_sha256(config_path),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "head_sha": os.environ.get("GITHUB_SHA"),
              "projection_fidelity_passed": False, "evaluator_rows_read": 0, "availability_forecasts": 0,
              "dynamic_invocations": 0}
    if not expected["operations"]:
        result["status"] = "no_observed_server_input"
        _write(out / "application-fidelity.json", result)
        return result
    root = out / "raw"
    (root / "results").mkdir(parents=True)
    shutil.copyfile(contract / "Options.txt", root / "Options.txt")
    shutil.copytree(contract / "traces", root / "traces")
    commands = "main:main -of Options.txt\nexit 0\n"
    (root / "stdin.txt").write_text(commands)
    started, started_utc = time.perf_counter(), datetime.now(timezone.utc).isoformat()
    limit = config["internal_watchdog_seconds"]
    with (root / "stdout.log").open("wb") as stdout:
        process = subprocess.Popen(["/usr/bin/time", "-v", "-o", "resource-usage.txt", "timeout",
                                    "--signal=TERM", "--kill-after=10s", f"{limit}s", "java",
                                    "-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector",
                                    "-jar", str(jar.resolve())], cwd=root, stdin=subprocess.PIPE, stdout=stdout, stderr=subprocess.STDOUT)
        time.sleep(20)
        command_utc = datetime.now(timezone.utc).isoformat()
        process.communicate(commands.encode(), timeout=limit + 30)
    execution = {"started_at": started_utc, "command_sent_at": command_utc, "finished_at": datetime.now(timezone.utc).isoformat(),
                 "elapsed_seconds": time.perf_counter() - started, "exit_code": process.returncode,
                 "internal_watchdog_seconds": limit, "startup_seconds": 20}
    _write(root / "execution.json", execution)
    result.update(dynamic_invocations=1, execution=execution, status="projection_fidelity_unresolved")
    try:
        actual = inspect_pcm(root / "results")
        _write(out / "resolved-pcm.json", actual)
        comparison = compare_pcm(actual, expected)
        envelope = _read(contract / "traces/observed.json")
        inventory = reconstructed_inventory((root / "stdout.log").read_text(), envelope)
        usage = usage_details(root / "results")
        passed = (process.returncode == 0 and comparison["qualified"]
                  and all(value for value in inventory.values() if isinstance(value, bool))
                  and manifest["coverage"]["root_operation_first_timestamp_collisions"] == 0
                  and usage == {"closed_workload_populations": [10], "think_time_literals": ["0"]})
        result.update(comparison=comparison, inventory=inventory, usage=usage, projection_fidelity_passed=passed,
                      status="observed_projection_fidelity_passed" if passed else "observed_projection_mismatch")
    except (AdapterError, ET.ParseError, KeyError, ValueError, StopIteration) as exc:
        result["model_error"] = f"{type(exc).__name__}: {exc}"
    _write(out / "application-fidelity.json", result)
    return result


def summarize(config_path: Path, inputs: Path, out: Path) -> dict[str, Any]:
    _remote()
    config = validate(config_path)
    rows = [_read(p) for p in sorted(inputs.rglob("application-fidelity.json"))]
    wanted = {s["key"] for s in config["samples"]}
    names = [r["sample"]["key"] for r in rows]
    if len(names) != len(set(names)) or not set(names).issubset(wanted):
        raise AdapterError("unexpected_application_output_census")
    for row in rows:
        if row["config_sha256"] != file_sha256(config_path) or row["run_id"] != os.environ.get("GITHUB_RUN_ID") or row["head_sha"] != os.environ.get("GITHUB_SHA"):
            raise AdapterError("application_output_provenance_differs")
    result = {"kind": "m9q_four_sample_application_census", "run_id": os.environ.get("GITHUB_RUN_ID"),
              "head_sha": os.environ.get("GITHUB_SHA"), "config_sha256": file_sha256(config_path),
              "expected_samples": 4, "completed_samples": len(rows), "missing_samples": sorted(wanted - set(names)),
              "sample_results": rows, "projection_fidelity_passed_samples": sum(row["projection_fidelity_passed"] for row in rows),
              "dynamic_invocations": sum(row["dynamic_invocations"] for row in rows),
              "full_external_request_mapping_established": False, "evaluator_rows_read": 0, "availability_forecasts": 0}
    _write(out / "application-census.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "gate", "prepare", "execute", "summarize"))
    parser.add_argument("--config", type=Path, default=Path("configs/m9q_application_census.json"))
    for arg in ("source-root", "audit-root", "metadata-root", "review", "options", "contract", "jar", "inputs", "out"):
        parser.add_argument("--" + arg, type=Path)
    args = parser.parse_args(argv)
    if args.action == "validate":
        validate(args.config)
    elif args.action == "gate":
        check_gate(args.config, args.review, args.metadata_root / "review.json")
    elif args.action == "prepare":
        prepare(args.config, args.source_root, args.audit_root, args.metadata_root, args.review, args.options, args.out)
    elif args.action == "execute":
        execute(args.config, args.contract, args.jar, args.out)
    else:
        summarize(args.config, args.inputs, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
