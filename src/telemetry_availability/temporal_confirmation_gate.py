"""Remote provenance, retention and readiness gates for M9P."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from . import temporal_confirmation_live as live
from .provenance import file_sha256

REPOSITORY = "a-a-k/telemetry-availability-identification"
ACCEPTANCE = live.ROOT / "configs/m9p_preflight_acceptance.json"


def api(path):
    process = subprocess.run(["gh", "api", "--hostname", "github.com", f"repos/{REPOSITORY}/{path}"], check=True, capture_output=True, text=True)
    return json.loads(process.stdout)


def artifacts(run_id):
    result = []
    page = 1
    while True:
        response = api(f"actions/runs/{int(run_id)}/artifacts?per_page=100&page={page}")
        result.extend(response["artifacts"])
        if len(result) >= response["total_count"]:
            return result
        page += 1


def retained(record, days):
    created = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
    return (not record["expired"] and record["size_in_bytes"] > 0
            and expires > datetime.now(timezone.utc)
            and (expires - created).total_seconds() >= (days - 1) * 86400)


def verify_lock(record, lock):
    for field in ("id", "name", "size_in_bytes", "digest"):
        if record.get(field) != lock[field]:
            raise ValueError(f"accepted artifact {field} differs")
    if not retained(record, 90):
        raise ValueError("accepted artifact expired or retention differs")


def readiness(out):
    live.remote_only()
    live.validate()
    acceptance = live.read_json(ACCEPTANCE)
    for name, digest in acceptance["implementation_sha256"].items():
        if file_sha256(live.ROOT / name) != digest:
            raise ValueError(f"main implementation changed after readiness audit: {name}")
    run_id = acceptance["run_id"]
    run = api(f"actions/runs/{run_id}")
    if (run["status"] != "completed" or run["conclusion"] != "success"
            or run["head_sha"] != acceptance["head_sha"] or run["path"] != ".github/workflows/m9p-temporal-preflight.yml"):
        raise ValueError("accepted no-fit preflight run differs or failed")
    records = artifacts(run_id)
    by_id = {record["id"]: record for record in records}
    lock = acceptance["audit_artifact"]
    verify_lock(by_id[lock["id"]], lock)
    expected = {f"m9p-preflight-{role}-{placement}-{law}-{run_id}-a1"
                for role in ("learner", "evaluator", "audit") for placement in ("colocated", "split") for law in ("N", "ND")}
    compact = [record for record in records if record["name"] in expected]
    if {r["name"] for r in compact} != expected or any(not retained(r, 90) for r in compact):
        raise ValueError("preflight compact artifact coverage or retention differs")
    out = Path(out)
    downloaded = out / "accepted-preflight"
    subprocess.run(["gh", "run", "download", str(run_id), "--repo", REPOSITORY, "--name", lock["name"], "--dir", str(downloaded)], check=True)
    audit_path = downloaded / "preflight-audit.json"
    if file_sha256(audit_path) != acceptance["audit_file_sha256"]:
        raise ValueError("accepted preflight audit bytes differ")
    audit = live.read_json(audit_path)
    if (audit["status"] != "no_fit_preflight_passed" or audit["model_fits"] or audit["comparison_scores"]
            or audit["main_effectiveness_observations"] or audit["cells"] != 4
            or audit["config_sha256"] != file_sha256(live.CONFIG)
            or audit["acquisition_implementation_sha256"] != file_sha256(Path(live.__file__))):
        raise ValueError("accepted no-fit scientific boundary differs")
    result = {"status": "main_acquisition_ready", "preflight_run_id": run_id,
              "preflight_head_sha": run["head_sha"], "audit_artifact": by_id[lock["id"]],
              "compact_artifact_count": len(compact), "retention_days": 90,
              "main_cells": 120, "source_run_id": os.environ["GITHUB_RUN_ID"],
              "source_commit": os.environ["GITHUB_SHA"], "acceptance_sha256": file_sha256(ACCEPTANCE),
              "implementation_sha256": acceptance["implementation_sha256"]}
    live.write_json(out / "readiness.json", result)
    return {"status": result["status"], "main_cells": 120, "preflight_run_id": run_id}


def before_evaluator(candidate_artifact_id, out):
    live.remote_only()
    artifact = api(f"actions/artifacts/{int(candidate_artifact_id)}")
    if artifact["workflow_run"]["id"] != int(os.environ["GITHUB_RUN_ID"]) or artifact["workflow_run"]["head_sha"] != os.environ["GITHUB_SHA"]:
        raise ValueError("candidate artifact belongs to another execution")
    expected_name = f"m9p-candidates-{os.environ['GITHUB_RUN_ID']}-a{os.environ['GITHUB_RUN_ATTEMPT']}"
    if artifact["name"] != expected_name or not retained(artifact, 90):
        raise ValueError("candidate artifact name or retention differs")
    now = datetime.now(timezone.utc)
    created = datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00"))
    if created > now:
        raise ValueError("candidate upload does not precede evaluator access")
    live.write_json(Path(out) / "evaluator-access.json", {"status": "candidate_upload_precedes_evaluator_download",
                    "checked_at_utc": now.isoformat(), "candidate_artifact": artifact,
                    "evaluator_download_started": False})
    return {"status": "candidate_upload_precedes_evaluator_download"}


def audit_main(input_root, out):
    live.remote_only()
    run_id = int(os.environ["GITHUB_RUN_ID"])
    attempt = os.environ["GITHUB_RUN_ATTEMPT"]
    all_artifacts = artifacts(run_id)
    expected = {f"m9p-main-{role}-{p}-{law}-r{r}-{run_id}-a{attempt}"
                for role in ("learner", "evaluator", "audit") for p in ("colocated", "split") for law in ("N", "ND") for r in range(30)}
    selected = [r for r in all_artifacts if r["name"] in expected]
    if {r["name"] for r in selected} != expected or any(not retained(r, 90) for r in selected):
        raise ValueError("main artifact coverage or 90-day retention differs")
    raw_names = {f"m9p-main-raw-{p}-{law}-r{r}-{run_id}-a{attempt}"
                 for p in ("colocated", "split") for law in ("N", "ND") for r in range(30)}
    raw_artifacts = [r for r in all_artifacts if r["name"] in raw_names]
    if {r["name"] for r in raw_artifacts} != raw_names or any(not retained(r, 90) for r in raw_artifacts):
        raise ValueError("complete native source retention differs")
    summaries = [live.read_json(p) for p in Path(input_root).rglob("acquisition-audit.json")]
    if len(summaries) != 120 or {live.identity(r) for r in summaries} != live.expected_identities("full"):
        raise ValueError("main acquisition audit census differs")
    for record in summaries:
        if record["scope"] != "full" or record["status"] != "fresh_source_and_separation_passed" or record["source_run_id"] != str(run_id):
            raise ValueError("main acquisition source differs")
    costs = []
    for record in summaries:
        source_cost = record["cost"]
        costs.append({**{key: record[key] for key in live.IDENTITY},
                      "qualification_seconds": source_cost["qualification_seconds"],
                      "raw_telemetry_bytes": source_cost["source_file_bytes"].get("raw-telemetry.log", 0),
                      "raw_request_bytes": source_cost["source_file_bytes"]["requests.csv"],
                      "raw_health_bytes": source_cost["source_file_bytes"]["health.csv"],
                      "all_source_bytes": sum(source_cost["source_file_bytes"].values()),
                      "learner_request_rows": source_cost["learner_request_rows"],
                      "health_ticks": source_cost["health_ticks"]})
    jobs, page = [], 1
    while True:
        response = api(f"actions/runs/{run_id}/jobs?per_page=100&page={page}")
        jobs.extend(response["jobs"])
        if len(jobs) >= response["total_count"]:
            break
        page += 1
    runner_rows = []
    for job in jobs:
        if job["status"] != "completed":
            continue
        start = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
        runner_rows.append({"job_id": job["id"], "name": job["name"], "conclusion": job["conclusion"],
                            "started_at": job["started_at"], "completed_at": job["completed_at"],
                            "runner_seconds": (end - start).total_seconds()})
    out = Path(out)
    live.write_csv(out / "acquisition-costs.csv", costs)
    live.write_csv(out / "completed-job-costs.csv", runner_rows)
    live.write_json(out / "artifact-inventory.json", all_artifacts)
    result = {"status": "main_retention_and_acquisition_audit_passed", "source_run_id": run_id,
              "cells": 120, "compact_artifacts": len(selected), "completed_job_runner_hours": sum(r["runner_seconds"] for r in runner_rows) / 3600,
              "raw_source_artifacts": len(raw_artifacts), "compressed_raw_source_bytes": sum(r["size_in_bytes"] for r in raw_artifacts),
              "excludes_current_final_audit_job": True, "nominal_acquisition_runner_hours": 62,
              "source_trace_bytes": sum(r["raw_telemetry_bytes"] for r in costs),
              "qualification_seconds": sum(r["qualification_seconds"] for r in costs)}
    live.write_json(out / "main-audit.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("readiness", "before-evaluator", "audit-main"):
        child = sub.add_parser(name)
        child.add_argument("--out", required=True)
        if name == "before-evaluator":
            child.add_argument("--candidate-artifact-id", required=True)
        if name == "audit-main":
            child.add_argument("--input-root", required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    result = {"readiness": readiness, "before-evaluator": before_evaluator, "audit-main": audit_main}[command](**args)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
