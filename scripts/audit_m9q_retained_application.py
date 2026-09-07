"""Describe retained M9Q application mismatches; never refit or alter the gate."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from zipfile import ZipFile


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("retained application audit runs remotely")
    config_path = Path("configs/m9q_retained_application_audit.json")
    config = read(config_path)
    for row in config["repository_locks"]:
        assert digest(Path(row["path"])) == row["sha256"]
    out = Path("workflow-results/m9q-retained-application")
    evidence = Path("workflow-input/m9q-retained-application")
    repo = os.environ["GITHUB_REPOSITORY"]
    metadata = []
    for lock in config["artifacts"]:
        endpoint = f"repos/{repo}/actions/artifacts/{lock['id']}"
        actual = json.loads(subprocess.check_output(["gh", "api", endpoint]))
        for field in ("id", "name", "size_in_bytes", "digest"):
            assert actual[field] == lock[field], (field, lock["id"])
        assert not actual["expired"]
        assert actual["workflow_run"]["id"] == config["source_run_id"]
        assert actual["workflow_run"]["head_sha"] == config["source_head_sha"]
        archive = subprocess.check_output(["gh", "api", endpoint + "/zip"])
        assert len(archive) == lock["size_in_bytes"]
        assert "sha256:" + sha256(archive).hexdigest() == lock["digest"]
        with ZipFile(io.BytesIO(archive)) as stream:
            for name in stream.namelist():
                relative = PurePosixPath(name)
                assert not relative.is_absolute() and ".." not in relative.parts
            stream.extractall(evidence / lock["role"])
        metadata.append({key: actual[key] for key in
                         ("id", "name", "size_in_bytes", "digest", "expired", "created_at", "expires_at", "workflow_run")})
    census = read(evidence / "census/application-census.json")
    assert census["head_sha"] == config["source_head_sha"]
    assert census["run_id"] == str(config["source_run_id"])
    assert census["completed_samples"] == 4 and census["projection_fidelity_passed_samples"] == 0
    summaries = []
    for original in census["sample_results"]:
        key = original["sample"]["key"]
        learner = evidence / "learners/learners" / key
        result = evidence / key
        contract = read(learner / "learner-contract.json")
        assert read(result / "learner-contract.json") == contract
        assert read(result / "application-fidelity.json") == original
        for name, expected_digest in contract["files"].items():
            assert digest(learner / name) == expected_digest
        row = {"sample": key, "original_status": original["status"],
               "original_projection_fidelity_passed": original["projection_fidelity_passed"],
               "selection_audit": read(learner / "adapter/selection_audit.json"),
               "contract_files_verified": len(contract["files"]),
               "coverage": original["coverage"]}
        if not original["dynamic_invocations"]:
            summaries.append(row)
            continue
        actual = read(result / "resolved-pcm.json")
        for name, expected_digest in actual["model_files"].items():
            assert digest(result / "raw/results" / name) == expected_digest
        expected = read(learner / "expected-observed-projection.json")
        mapping = read(learner / "adapter/mapping.json")
        names = {r["pmx_operation"]: {"service": r["service"], "operation": r["operation"],
                                     "instance_key": r["instance_key"], "instance_value": r["instance_value"]}
                 for r in mapping}
        oracle = read(learner / "adapter/operation_oracle.json")
        root_counts = Counter(r["pmx_operation"] for r in mapping if not r["pmx_parent_span_id"])
        envelope = read(learner / "traces/observed.json")
        earliest_counts = Counter()
        early_descendants = []
        equal_start_trees = 0
        for trace in envelope["data"]:
            root = next(s for s in trace["spans"] if not s["references"])
            earliest_time = min(s["startTime"] for s in trace["spans"])
            earliest = [s for s in trace["spans"] if s["startTime"] == earliest_time]
            equal_start_trees += len(earliest) > 1
            # Stable order is descriptive only; tied reconstruction order is not inferred.
            earliest_counts[earliest[0]["operationName"]] += 1
            if earliest_time < root["startTime"]:
                early_descendants.append({"root": root["operationName"],
                                          "earliest": earliest[0]["operationName"],
                                          "offset_us": root["startTime"] - earliest_time})
        row["operation_rows"] = [{**names[r["operation"]], "pmx_operation": r["operation"],
                                  "invocations": r["invocations"], "errors": r["errors"],
                                  "error_probability": r["error_probability"],
                                  "projected_root_observations": root_counts[r["operation"]],
                                  "earliest_span_observations": earliest_counts[r["operation"]],
                                  "expected_usage_entries": expected["entry_operation_counts"].get(r["operation"], 0),
                                  "actual_usage_entries": actual["entry_operation_counts"].get(r["operation"], 0)}
                                 for r in oracle]
        row["trees_with_descendant_before_root"] = len(early_descendants)
        row["early_descendant_operation_pairs"] = [{"root": a, "earliest": b, "count": n}
                                                   for (a, b), n in sorted(Counter((r["root"], r["earliest"]) for r in early_descendants).items())]
        row["trees_with_multiple_earliest_spans"] = equal_start_trees
        row["max_descendant_lead_us"] = max((r["offset_us"] for r in early_descendants), default=0)
        log = (result / "raw/stdout.log").read_text()
        row["usage_log_lines"] = [line for line in log.splitlines()
                                  if re.search(r"NUMCALLS |==>|=== (?:message chain|durartion) ===", line)]
        row["pmx_resource_usage"] = (result / "raw/resource-usage.txt").read_text()
        row["execution"] = original["execution"]
        summaries.append(row)
    report = {"kind": "m9q_retained_application_description", "run_id": os.environ["GITHUB_RUN_ID"],
              "head_sha": os.environ["GITHUB_SHA"], "source_run_id": config["source_run_id"],
              "source_head_sha": config["source_head_sha"], "config_sha256": digest(config_path),
              "completed_at": datetime.now(timezone.utc).isoformat(), "artifact_metadata": metadata,
              "original_census_sha256": digest(evidence / "census/application-census.json"),
              "original_qualified_samples": 0, "original_pmx_invocations": 2,
              "new_pmx_invocations": 0, "availability_forecasts": 0, "evaluator_rows_read": 0,
              "gate_amended": False, "samples": summaries,
              "shared_preparation_resource_usage": (evidence / "learners/preparation-resource-usage.txt").read_text()}
    write(out / "retained-application-description.json", report)
    print(json.dumps({"samples": len(summaries), "new_pmx_invocations": 0, "gate_amended": False}))


if __name__ == "__main__":
    main()
