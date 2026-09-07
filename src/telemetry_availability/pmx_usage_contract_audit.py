"""Post-result repair of the M9Q usage oracle; never invokes PMX."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree as ET

from .pmx_adapter_conformance import CASES, compare_pcm, inspect_pcm, validate_config
from .pmx_observed_operations import AdapterError, file_sha256


def aggregated_entry_counts(counts: dict[str, int]) -> dict[str, int]:
    if not counts or any(n <= 0 for n in counts.values()):
        raise AdapterError("unsupported_root_count")
    smallest = min(counts.values())
    # Positive Java Math.round, using integers to avoid binary tie ambiguity.
    return {operation: (2 * count + smallest) // (2 * smallest) for operation, count in counts.items()}


def reconstructed_inventory(stdout: str, envelope: dict[str, Any]) -> dict[str, Any]:
    normalized = stdout.replace("\r\n", "\n")
    pattern = re.compile(r"^(?:osgi> )?#{42}\n(?P<spans>(?:operation_[0-9a-f]{24} / [0-9a-f]+ / (?:null|[0-9a-f]+)\n)+)#{42}\n(?P<execution>ExecutionTrace [^\n]*)$", re.MULTILINE)
    records, timings, traces = Counter(), {}, Counter()
    for match in pattern.finditer(normalized):
        execution = match["execution"]
        identities = re.findall(r"([0-9a-f]{32})(operation_[0-9a-f]{24}) <NOSESSIONID>", execution)
        trace_ids = {trace for trace, _ in identities}
        if len(trace_ids) != 1 or "invalidExecutions=[]" not in execution:
            raise AdapterError("unresolved_reconstructed_trace")
        trace_id = next(iter(trace_ids))
        traces[trace_id] += 1
        times = re.search(r"minTin=(\d+), maxTout=(\d+)", execution)
        if times is None:
            raise AdapterError("missing_reconstructed_times")
        timings[trace_id] = [int(times[1]), int(times[2])]
        span_rows = [line.split(" / ") for line in match["spans"].splitlines()]
        if Counter(op for _, op in identities) != Counter(row[0] for row in span_rows):
            raise AdapterError("span_tree_execution_inventory_differs")
        for operation, span_id, parent in span_rows:
            records[(trace_id, span_id, operation, "" if parent == "null" else parent)] += 1
    wanted, wanted_timings = Counter(), {}
    for trace in envelope["data"]:
        trace_id = trace["traceID"]
        wanted_timings[trace_id] = [min(s["startTime"] for s in trace["spans"]) * 1000,
                                   max(s["startTime"] + s["duration"] for s in trace["spans"]) * 1000]
        for span in trace["spans"]:
            refs = span["references"]
            wanted[(trace_id, span["spanID"], span["operationName"], refs[0]["spanID"] if refs else "")] += 1
    return {"expected_spans": sum(wanted.values()), "reconstructed_spans": sum(records.values()),
            "exact_trace_span_operation_parent_inventory": records == wanted,
            "each_trace_reconstructed_once": traces == Counter({trace: 1 for trace in wanted_timings}),
            "reconstructed_nanosecond_bounds_match_input_microseconds": timings == wanted_timings}


def usage_details(root: Path) -> dict[str, Any]:
    paths = list(root.glob("*.usagemodel"))
    if len(paths) != 1:
        raise AdapterError("ambiguous_usage_model")
    tree = ET.parse(paths[0])
    closed = [e for e in tree.iter() if e.get("{http://www.w3.org/2001/XMLSchema-instance}type", "").endswith(":ClosedWorkload")]
    return {"closed_workload_populations": [int(e.attrib["population"]) for e in closed],
            "think_time_literals": [c.get("specification") for e in closed for c in e
                                     if c.tag.rsplit("}", 1)[-1] == "thinkTime_ClosedWorkload"]}


def _metadata(path: Path, lock: dict[str, Any]) -> None:
    data = json.loads(path.read_text())
    for key in ("id", "name", "size_in_bytes"):
        if data.get(key) != lock[key]:
            raise AdapterError(f"artifact_metadata_differs:{key}")
    if data.get("digest", "").removeprefix("sha256:") != lock["digest"] or data.get("expired"):
        raise AdapterError("artifact_digest_or_expiry_differs")
    run = data.get("workflow_run", {})
    if run.get("id") != lock["run_id"] or run.get("head_sha") != lock["head_sha"]:
        raise AdapterError("artifact_source_run_differs")


def audit(config_path: Path, retained: Path, source_root: Path, metadata: Path, out: Path) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise AdapterError("full_retained_audit_is_remote_only")
    config = json.loads(config_path.read_text())
    validate_config(Path("configs/m9q_pmx_observed_operations.json"))
    for row in config["repository_locks"]:
        p = Path(row["path"])
        if p.stat().st_size != row["bytes"] or file_sha256(p) != row["sha256"]:
            raise AdapterError("oracle_repair_source_lock_differs")
    for role in ("conformance", "source"):
        _metadata(metadata / f"{role}.json", config["artifacts"][role])
    manifest_path = source_root / "source-manifest.json"
    if file_sha256(manifest_path) != config["source_manifest_sha256"]:
        raise AdapterError("embedded_source_manifest_differs")
    source = json.loads(manifest_path.read_text())
    for row in source["files"]:
        p = source_root / row["path"]
        if p.stat().st_size != row["bytes"] or file_sha256(p) != row["sha256"]:
            raise AdapterError("embedded_source_file_differs")
    original = json.loads((retained / "probe/conformance-decision.json").read_text())
    if (original["qualified"] or original["invocations"] != 6
            or not all(original["repeat_agreement"].values())
            or original["head_sha"] != config["artifacts"]["conformance"]["head_sha"]):
        raise AdapterError("original_failed_decision_differs")
    contract = json.loads((retained / "contract/contract-manifest.json").read_text())
    for name, digest in contract["files"].items():
        if file_sha256(retained / "contract" / name) != digest:
            raise AdapterError("frozen_synthetic_input_differs")
    rows = []
    for case in CASES:
        expected = json.loads((retained / "contract" / case / "expected.json").read_text())
        envelope = json.loads((retained / "contract" / case / "traces/observed.json").read_text())
        roots = [s for trace in envelope["data"] for s in trace["spans"] if not s["references"]]
        counts = dict(Counter(s["operationName"] for s in roots))
        first_times: dict[str, int] = {}
        for span in roots:
            operation = span["operationName"]
            first_times[operation] = min(first_times.get(operation, span["startTime"]), span["startTime"])
        if len(set(first_times.values())) != len(first_times):
            raise AdapterError("root_first_timestamp_collision_is_outside_qualified_synthetic_contract")
        corrected = deepcopy(expected)
        corrected["entry_operation_counts"] = aggregated_entry_counts(counts)
        for repeat in (1, 2):
            root = retained / "probe/raw" / case / f"repeat-{repeat}"
            recorded = json.loads((root / "resolved-pcm.json").read_text())
            for name, digest in recorded["model_files"].items():
                if file_sha256(root / "results" / name) != digest:
                    raise AdapterError("retained_pcm_file_changed")
            actual = inspect_pcm(root / "results")
            inventory = reconstructed_inventory((root / "stdout.log").read_text(), envelope)
            comparison = compare_pcm(actual, corrected)
            workload = usage_details(root / "results")
            original_row = next(r for r in original["results"] if r["case"] == case and r["repeat"] == repeat)
            original_failure_is_isolated = [key for key, value in original_row["checks"].items() if not value] == ["entry_operation_counts"]
            qualified = (original_failure_is_isolated and original_row["execution"]["exit_code"] == 0
                         and comparison["qualified"] and all(value for key, value in inventory.items() if isinstance(value, bool))
                         and workload == {"closed_workload_populations": [10], "think_time_literals": ["0"]})
            rows.append({"case": case, "repeat": repeat, "original_qualified": False,
                         "observed_root_counts": counts, "source_aggregated_entry_counts": corrected["entry_operation_counts"],
                         "inventory": inventory, "comparison": comparison, "usage": workload, "qualified_after_oracle_repair": qualified})
    result = {"kind": "m9q_post_result_usage_oracle_repair", "config_sha256": file_sha256(config_path),
              "run_id": os.environ.get("GITHUB_RUN_ID"), "head_sha": os.environ.get("GITHUB_SHA"),
              "original_conformance_qualified": False, "original_run_id": 34122721945,
              "source_run_id": 34123438744, "source_files_verified": len(source["files"]),
              "rows": rows, "qualified_after_oracle_repair": all(row["qualified_after_oracle_repair"] for row in rows),
              "dynamic_pmx_invocations": 0, "evaluator_rows_read": 0, "availability_forecasts": 0}
    out.mkdir(parents=True, exist_ok=True)
    (out / "retained-contract-audit.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/m9q_usage_oracle_review.json"))
    parser.add_argument("--retained", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit(args.config, args.retained, args.source_root, args.metadata, args.out)
    return 0 if result["qualified_after_oracle_repair"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
