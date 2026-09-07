"""Verify completed M9P summary archives and account for reported costs.

Only five generated summary artifacts are downloaded. Native acquisition,
learner and evaluator bundles are never downloaded or parsed by this script.
There is no fitting, scoring, resampling or result classification.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import zipfile

import render_m9p_confirmation as rendering


REPO = "a-a-k/telemetry-availability-identification"
RUN = rendering.RUN
HEAD = rendering.HEAD
SUMMARY_NAMES = {
    "readiness": f"m9p-readiness-{RUN}-a1",
    "candidates": f"m9p-candidates-{RUN}-a1",
    "evaluation": f"m9p-evaluation-{RUN}-a1",
    "access": f"m9p-evaluator-access-{RUN}-a1",
    "audit": f"m9p-main-final-audit-{RUN}-a1",
}
require = rendering.require


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, record):
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def api(path):
    return json.loads(subprocess.run(
        ["gh", "api", "--hostname", "github.com", f"repos/{REPO}/{path}"],
        check=True, capture_output=True).stdout)


def pages(path, key):
    records, page = [], 1
    while True:
        response = api(f"{path}?per_page=100&page={page}")
        records.extend(response[key])
        if len(records) >= response["total_count"]:
            require(len(records) == response["total_count"], "API pagination count differs")
            return records
        require(response[key], "Unexpected empty API page")
        page += 1


def verify_seal(directory, expected):
    seal = read(directory / "seal.json")
    actual = {path.relative_to(directory).as_posix()
              for path in directory.rglob("*") if path.is_file()}
    require(set(seal["files"]) == expected and actual == expected | {"seal.json"},
            "Summary seal file inventory differs")
    require(str(seal["source_run_id"]) == RUN, "Summary seal source differs")
    for name, lock in seal["files"].items():
        path = directory / name
        require(path.stat().st_size == lock["bytes"] and sha(path) == lock["sha256"],
                "Summary seal byte lock differs: " + name)
    return len(expected)


def fetch_archive(record, root, label):
    archive = root / (label + ".zip")
    if not archive.exists():
        with archive.open("wb") as output:
            subprocess.run(["gh", "api", "--hostname", "github.com",
                f"repos/{REPO}/actions/artifacts/{record['id']}/zip"], check=True, stdout=output)
    require(archive.stat().st_size == record["size_in_bytes"], "Archive byte count differs")
    require("sha256:" + sha(archive) == record["digest"], "Archive digest differs")
    directory = root / label
    directory.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        require(len(names) == len(set(names)), "Duplicate ZIP members")
        for item in bundle.infolist():
            target = (directory / item.filename).resolve()
            require(target.is_relative_to(directory.resolve()), "ZIP member escapes summary directory")
        bundle.extractall(directory)
    return directory


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def key(row):
    return (row["profile"], row["placement"], row["failure_law"], int(row["repetition"]))


def audit(root):
    run = api(f"actions/runs/{RUN}")
    require(run["status"] == "completed" and run["conclusion"] == "success",
            "Main run is not completely successful; do not inspect partial results")
    require(run["head_sha"] == HEAD and run["run_attempt"] == 1,
            "Frozen main execution differs")
    require(run["path"] == ".github/workflows/m9p-temporal-confirmation.yml",
            "Main workflow path differs")
    artifacts = pages(f"actions/runs/{RUN}/artifacts", "artifacts")
    jobs = pages(f"actions/runs/{RUN}/jobs", "jobs")
    expected_source = {
        f"m9p-main-{role}-{placement}-{law}-r{rep}-{RUN}-a1"
        for role in ("raw", "learner", "evaluator", "audit")
        for placement in ("colocated", "split") for law in ("N", "ND") for rep in range(30)}
    by_name = {record["name"]: record for record in artifacts}
    require(len(by_name) == len(artifacts)
            and set(by_name) == expected_source | set(SUMMARY_NAMES.values()),
            "Expected complete source and summary artifact inventory differs")
    now = datetime.now(timezone.utc)
    for record in artifacts:
        require(record["workflow_run"]["id"] == int(RUN)
                and record["workflow_run"]["head_sha"] == HEAD, "Artifact provenance differs")
        require(not record["expired"] and stamp(record["expires_at"]) > now
                and (stamp(record["expires_at"]) - stamp(record["created_at"])).total_seconds()
                >= 89 * 86400 and record["size_in_bytes"] > 0, "Artifact retention differs")
        require(record["digest"].startswith("sha256:") and len(record["digest"]) == 71,
                "Artifact SHA-256 is missing")
    require(len(jobs) == 124 and all(job["status"] == "completed"
            and job["conclusion"] == "success" for job in jobs), "Completed job census differs")
    root.mkdir(parents=True, exist_ok=True)
    write(root / "run-api.json", run)
    write(root / "artifact-api.json", artifacts)
    write(root / "jobs-api.json", jobs)
    directories = {label: fetch_archive(by_name[name], root, label)
                   for label, name in SUMMARY_NAMES.items()}
    candidate_dir, evaluation_dir = directories["candidates"], directories["evaluation"]
    seal_files = verify_seal(candidate_dir, {
        "candidate-predictions.csv", "calibration-audit.csv", "model-input-costs.csv",
        "learner-input-seals.json", "candidate-manifest.json"})
    seal_files += verify_seal(evaluation_dir, {
        "marginal-scores.csv", "conditional-scores.csv", "test-adequacy.csv",
        "evaluation-costs.csv", "inference.json", "evaluation-manifest.json"})
    candidate = read(candidate_dir / "candidate-manifest.json")
    evaluation = read(evaluation_dir / "evaluation-manifest.json")
    final_audit = read(directories["audit"] / "main-audit.json")
    rendering.validate(candidate, evaluation, final_audit)
    require(read(evaluation_dir / "inference.json") == evaluation["intervals"],
            "Duplicated inference summary differs")
    require(evaluation["candidate_seal_sha256"] == sha(candidate_dir / "seal.json"),
            "Evaluator used a different candidate seal")
    access = read(directories["access"] / "evaluator-access.json")
    candidate_artifact = by_name[SUMMARY_NAMES["candidates"]]
    require(access["status"] == "candidate_upload_precedes_evaluator_download"
            and access["evaluator_download_started"] is False, "Evaluator access gate differs")
    require(all(access["candidate_artifact"][field] == candidate_artifact[field]
                for field in ("id", "name", "digest", "size_in_bytes")),
            "Evaluator access names a different candidate artifact")
    require(stamp(candidate_artifact["created_at"]) <= stamp(access["checked_at_utc"])
            <= stamp(by_name[SUMMARY_NAMES["evaluation"]]["created_at"]),
            "Candidate freeze/evaluator access/evaluation publication order differs")
    readiness = read(directories["readiness"] / "readiness.json")
    require(readiness["status"] == "main_acquisition_ready"
            and str(readiness["source_run_id"]) == RUN and readiness["source_commit"] == HEAD,
            "Readiness source differs")
    for name, digest in readiness["implementation_sha256"].items():
        committed = subprocess.run(["git", "show", f"{HEAD}:{name}"],
                                   check=True, capture_output=True).stdout
        require(hashlib.sha256(committed).hexdigest() == digest,
                "Readiness lock differs from frozen Git bytes: " + name)

    expected_cells = {("opentelemetry_demo", placement, law, rep)
                      for placement in ("colocated", "split")
                      for law in ("N", "ND") for rep in range(30)}
    acquisition = rows(directories["audit"] / "acquisition-costs.csv")
    require(len(acquisition) == 120 and {key(row) for row in acquisition} == expected_cells,
            "Acquisition cost matrix differs")
    input_costs = rows(candidate_dir / "model-input-costs.csv")
    require(len(input_costs) == 840, "Model cost row count differs")
    require(set(candidate["methods"]) == {"learner_state_only", "temporal_logit_lower",
            "temporal_logit_midpoint", "temporal_logit_upper", "source_500ms_failover",
            "matched_stable_endpoint", "all_calibration_endpoint"}
            and len(candidate["methods"]) == 7, "Registered method family differs")
    expected_pairs = {(cell, method) for cell in expected_cells for method in candidate["methods"]}
    for directory, name in ((candidate_dir, "candidate-predictions.csv"),
                            (evaluation_dir, "marginal-scores.csv"),
                            (evaluation_dir, "conditional-scores.csv")):
        table = rows(directory / name)
        require(len(table) == 840 and {(key(row), row["method"]) for row in table} == expected_pairs,
                "Reported candidate/score matrix differs: " + name)
    for directory, name in ((candidate_dir, "calibration-audit.csv"),
                            (evaluation_dir, "test-adequacy.csv")):
        table = rows(directory / name)
        require(len(table) == 120 and {key(row) for row in table} == expected_cells,
                "Reported adequacy matrix differs: " + name)
    methods = {}
    for method in candidate["methods"]:
        selected = [row for row in input_costs if row["method"] == method]
        require(len(selected) == 120 and {key(row) for row in selected} == expected_cells,
                "Method input-cost matrix differs")
        fit_times = [float(row["method_fit_or_estimation_seconds"]) for row in selected]
        require(all(math.isfinite(value) and value >= 0 for value in fit_times),
                "Nonfinite or negative reported fitting cost")
        methods[method] = {"fit_or_estimation_seconds_sum": sum(fit_times),
            "fit_or_estimation_seconds_median": statistics.median(fit_times),
            "health_bytes_sum": sum(int(row["actual_health_input_bytes"]) for row in selected),
            "native_trace_model_bytes_sum": sum(int(row["trace_input_bytes_for_model"]) for row in selected),
            "shared_request_file_bytes_sum": sum(int(row["actual_shared_learner_request_file_bytes"]) for row in selected),
            "minimal_endpoint_projection_bytes_sum": sum(int(row["minimal_endpoint_request_projection_bytes"] or 0) for row in selected)}
    runner_seconds = {job["id"]: (stamp(job["completed_at"]) - stamp(job["started_at"])).total_seconds()
                      for job in jobs}
    audit_job = [job for job in jobs if job["name"] == "Audit retained source and information costs"]
    require(len(audit_job) == 1, "Final audit job missing or duplicated")
    before_audit = (sum(runner_seconds.values()) - runner_seconds[audit_job[0]["id"]]) / 3600
    require(math.isclose(before_audit, final_audit["completed_job_runner_hours"], abs_tol=1e-9),
            "Recorded runner-hour sum differs from completed API jobs")
    result = {"status": "completed_summary_provenance_and_cost_audit_passed",
        "source_run_id": RUN, "source_commit": HEAD, "checked_at_utc": now.isoformat(),
        "completed_jobs": len(jobs), "retained_source_artifacts": len(expected_source),
        "retained_summary_artifacts": len(SUMMARY_NAMES), "downloaded_summary_archives": 5,
        "downloaded_native_learner_or_evaluator_bundles": 0,
        "verified_summary_seal_files": seal_files,
        "frozen_implementation_locks": len(readiness["implementation_sha256"]),
        "inferential_claims_admissible": evaluation["inferential_claims_admissible"],
        "estimates_intervals_decisions_recomputed": False,
        "runner_hours_including_final_audit": sum(runner_seconds.values()) / 3600,
        "runner_hours_excluding_final_audit": before_audit,
        "final_audit_runner_seconds": runner_seconds[audit_job[0]["id"]],
        "source_all_file_bytes": sum(int(row["all_source_bytes"]) for row in acquisition),
        "source_trace_bytes": sum(int(row["raw_telemetry_bytes"]) for row in acquisition),
        "source_request_bytes": sum(int(row["raw_request_bytes"]) for row in acquisition),
        "source_health_bytes": sum(int(row["raw_health_bytes"]) for row in acquisition),
        "learner_request_rows": sum(int(row["learner_request_rows"]) for row in acquisition),
        "calibration_health_ticks": sum(int(row["health_ticks"]) for row in acquisition),
        "method_costs": methods,
        "summary_artifacts": {label: {field: by_name[name][field] for field in
            ("id", "name", "size_in_bytes", "digest", "created_at", "expires_at")}
            for label, name in SUMMARY_NAMES.items()},
        "script_sha256": sha(Path(__file__)),
    }
    write(root / "completed-summary-audit.json", result)
    write(root / "artifact-locks.json", [{field: record[field] for field in
        ("id", "name", "size_in_bytes", "digest", "created_at", "expires_at")}
        for record in sorted(artifacts, key=lambda record: record["name"])])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.out), indent=2))


if __name__ == "__main__":
    main()
