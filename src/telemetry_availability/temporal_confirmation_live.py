"""Prospective M9P acquisition and no-fit evidence boundary.

The historical acquisition code is reused unchanged. This module never fits a
model or computes a comparison; its outputs gate the separate analysis jobs.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time

from .live_evidence import qualify_evidence_cell
from .live_evidence_config import load_evidence_boundary_config
from .live_stochastic_pilot import (
    StochasticCellPurpose, _run_stochastic_cell, _stable_seed,
    factor_definitions, renewal_schedule_seed,
)
from .live_validation_config import load_frozen_live_validation_config
from .provenance import environment_manifest, file_sha256

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/m9p_temporal_confirmation.json"
PROFILE = "opentelemetry_demo"
IDENTITY = ("profile", "placement", "failure_law", "repetition")
LEARNER_FILES = {
    "learner/requests.csv", "learner/health.csv", "learner/manifest.json",
    "learner/deployment.json", "audit/boundary.json",
}
EVALUATOR_FILES = {"evaluator/test-requests.csv", "evaluator/test-health.csv"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def rows(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not values:
        raise ValueError("cannot publish an empty CSV")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def remote_only():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("M9P collection and data analysis run only in GitHub Actions")


def identity(value):
    return (value["profile"], value["placement"], value["failure_law"], int(value["repetition"]))


def expected_identities(scope):
    if scope not in {"preflight", "full"}:
        raise ValueError("unknown M9P scope")
    return {(PROFILE, placement, law, rep)
            for placement in ("colocated", "split") for law in ("N", "ND")
            for rep in range(1 if scope == "preflight" else 30)}


def validate():
    config = read_json(CONFIG)
    for name, lock in config["repository_locks"].items():
        path = ROOT / name
        if path.stat().st_size != lock["bytes"] or file_sha256(path) != lock["sha256"]:
            raise ValueError(f"M9P repository lock differs: {name}")
    design = read_json(ROOT / config["design_file"])
    if design["selected_campaigns"] != 120 or design["selected_per_stratum"] != 30:
        raise ValueError("M9O campaign design differs")
    prospective = rows(ROOT / config["matrix_file"])
    if len(prospective) != 120 or {identity(row) for row in prospective} != expected_identities("full"):
        raise ValueError("M9O identity matrix differs")
    confirmation = read_json(ROOT / "configs/m9o_temporal_confirmation.json")["confirmation"]
    if config["confirmation"] != confirmation:
        raise ValueError("M9P changed the M9O confirmation protocol")
    if config["preflight_request_namespace"] != "m9p-temporal-preflight-v1":
        raise ValueError("preflight namespace differs")
    return config


def stochastic_config(scope):
    config = validate()
    old = load_frozen_live_validation_config(ROOT / "configs/m7_frozen_live.yaml").stochastic
    profiles = tuple(p for p in old.placement.profiles if p.id == PROFILE)
    runtime = replace(old.placement.runtime, profiles=tuple(p for p in old.placement.runtime.profiles if p.id == PROFILE))
    placement = replace(old.placement, profiles=profiles, runtime=runtime)
    confirmation = config["confirmation"]
    seed = confirmation["preflight_base_seed" if scope == "preflight" else "base_seed"]
    return replace(old, id="m9p_independent_temporal_confirmation", pilot_only=scope == "preflight",
                   placement=placement, pilot_repetitions=1 if scope == "preflight" else 30,
                   baseline_seconds=60, period_seconds=900, request_rate_per_second=4,
                   pilot_base_seed=seed, main_base_seed=seed,
                   laws={law: old.laws[law] for law in ("N", "ND")})


def namespace(scope, run_id, attempt):
    config = validate()
    base = config["preflight_request_namespace"] if scope == "preflight" else config["confirmation"]["request_namespace"]
    return f"{base}-run{int(run_id)}-a{int(attempt)}"


def role_labels(scope):
    config = validate()
    return {
        "pilot_only": scope == "preflight", "main_effectiveness": scope == "full",
        "preflight_only": scope == "preflight", "campaign_scope": scope,
        "analysis_frozen": True, "selected_design_sha256": file_sha256(ROOT / config["design_file"]),
        "live_config_sha256": file_sha256(CONFIG),
    }


def run_cell(scope, placement, law, repetition, checkout, compose, image_audit, out):
    remote_only()
    if (PROFILE, placement, law, repetition) not in expected_identities(scope):
        raise ValueError("cell outside frozen prospective matrix")
    config = stochastic_config(scope)
    purpose = StochasticCellPurpose(
        kind="independent_temporal_confirmation_campaign", manifest_filename="campaign-manifest.json",
        role_fields=role_labels(scope), usability_field="usable_for_temporal_confirmation",
        repetition_count=config.pilot_repetitions, base_seed=config.main_base_seed,
        request_namespace=namespace(scope, os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"]),
        failure_label="M9P " + scope,
    )
    return _run_stochastic_cell(config, PROFILE, placement, law, repetition, checkout, compose, image_audit, out, purpose)


def check_fresh_source(source, scope):
    """Validate identities, seeds and actual timestamps without reading success fields."""
    config = stochastic_config(scope)
    manifest = read_json(source / "campaign-manifest.json")
    cell_id = identity(manifest)
    if cell_id not in expected_identities(scope):
        raise ValueError("unexpected source identity")
    github = manifest["environment"]["github"]
    if any(github.get(key) != os.environ[key] for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA")):
        raise ValueError("source is not this fresh acquisition execution")
    if any(manifest.get(key) != value for key, value in role_labels(scope).items()):
        raise ValueError("source role or protocol lock differs")
    if manifest["observed_checkout_commit"] != validate()["confirmation"]["benchmark_commit"]:
        raise ValueError("benchmark revision differs")
    if not manifest.get("usable_for_temporal_confirmation") or any(manifest["quality"].values()):
        raise ValueError("source acquisition quality failed")
    schedule = read_json(source / "planned-schedule.json")
    profile = config.placement.profiles[0]
    _, placement, law, rep = cell_id
    expected_seeds = {period: {factor.factor_id: renewal_schedule_seed(config, profile, placement, law, rep, period, factor.factor_id, base_seed=config.main_base_seed)
                              for factor in factor_definitions(config, profile, placement, law)}
                      for period in ("calibration", "test")}
    if schedule["factor_schedule_seeds"] != expected_seeds:
        raise ValueError("factor-specific renewal seeds differ")
    all_requests = rows(source / "requests.csv")
    request_ids = [r["request_id"] for r in all_requests]
    prefix = namespace(scope, github["GITHUB_RUN_ID"], github["GITHUB_RUN_ATTEMPT"]) + "-"
    if len(request_ids) != 7440 or len(set(request_ids)) != 7440 or not all(v.startswith(prefix) for v in request_ids):
        raise ValueError("new request census or namespace differs")
    prior_end = None
    for period, duration in (("baseline", 60), ("calibration", 900), ("test", 900)):
        metadata = manifest["periods"][period]
        begin = datetime.fromisoformat(metadata["started_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(metadata["completed_at"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if begin < datetime(2026, 9, 7, tzinfo=timezone.utc) or end > now or (now - begin).total_seconds() > 6 * 3600:
            raise ValueError("source timestamps are not fresh")
        if metadata["duration_seconds"] != duration or (end - begin).total_seconds() < duration - 1 or (prior_end and begin < prior_end):
            raise ValueError("period timing differs")
        prior_end = end
        if metadata["workload_seed"] != _stable_seed(config.main_base_seed, *cell_id, period, "workload"):
            raise ValueError("workload seed differs")
        selected = [r for r in all_requests if r["period"] == period]
        if len(selected) != duration * 4 or any(not (metadata["started_at"] <= r["started_at"] <= metadata["completed_at"]) for r in selected):
            raise ValueError("request period membership differs")
    return manifest, expected_seeds


def seal(directory, metadata):
    files = {p.relative_to(directory).as_posix(): {"bytes": p.stat().st_size, "sha256": file_sha256(p)}
             for p in sorted(directory.rglob("*")) if p.is_file()}
    write_json(directory / "seal.json", {**metadata, "files": files})


def verify_seal(directory, allowed=None):
    record = read_json(directory / "seal.json")
    files = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    if files != set(record["files"]) | {"seal.json"} or (allowed is not None and set(record["files"]) != allowed):
        raise ValueError("sealed file allowlist differs")
    if allowed == LEARNER_FILES and any(p.name == "evaluator" for p in directory.rglob("*")):
        raise ValueError("evaluator directory present in learner input")
    for name, lock in record["files"].items():
        path = directory / name
        if path.stat().st_size != lock["bytes"] or file_sha256(path) != lock["sha256"]:
            raise ValueError(f"sealed bytes differ: {name}")
    return record


def qualify(source, out, scope):
    remote_only()
    started = time.perf_counter()
    source, out = Path(source), Path(out)
    manifest, seeds = check_fresh_source(source, scope)
    old = load_evidence_boundary_config(ROOT / "configs/m7_evidence_boundary.yaml")
    config = replace(old, id="m9p_evidence_boundary", diagnostic_only=scope == "preflight", main_effectiveness=scope == "full",
                     source_experiment_id="m9p_independent_temporal_confirmation",
                     source_usable_field="usable_for_temporal_confirmation", required_source_labels=role_labels(scope),
                     expected_source_cells=len(expected_identities(scope)), profiles=tuple(p for p in old.profiles if p.id == PROFILE))
    qualified = out / "qualified"
    summary = qualify_evidence_cell(config, source, qualified)
    if not summary["usable"]:
        raise ValueError("native evidence qualification failed")
    cell = {key: manifest[key] for key in IDENTITY}
    metadata = {**cell, "scope": scope, "source_run_id": os.environ["GITHUB_RUN_ID"],
                "source_attempt": os.environ["GITHUB_RUN_ATTEMPT"], "source_commit": os.environ["GITHUB_SHA"],
                "config_sha256": file_sha256(CONFIG)}
    learner = out / "learner-bundle"
    for name in ("learner/health.csv", "learner/deployment.json"):
        target = learner / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(qualified / name, target)
    # Existing record loader accepts these inert fields; no trace graph is staged.
    request_rows = rows(qualified / "learner/requests.csv")
    for row in request_rows:
        for name in ("trace_id", "services", "target_replicas"):
            row[name] = ""
        for name in ("span_count", "target_replica_count"):
            row[name] = "0"
        row["trace_present"] = "False"
    write_csv(learner / "learner/requests.csv", request_rows)
    write_json(learner / "learner/manifest.json", {**cell, "source_experiment_id": config.source_experiment_id})
    write_json(learner / "audit/boundary.json", {**cell, "usable": True, "learner_only": True})
    seal(learner, metadata)
    evaluator = out / "evaluator-bundle"
    for name in EVALUATOR_FILES:
        target = evaluator / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(qualified / name, target)
    seal(evaluator, metadata)
    audit = out / "audit-bundle"
    audit.mkdir(parents=True, exist_ok=True)
    for name in ("campaign-manifest.json", "planned-schedule.json", "image-lock-audit.json", "runtime-containers.json", "runner.txt"):
        shutil.copyfile(source / name, audit / name)
    shutil.copyfile(qualified / "audit/boundary.json", audit / "boundary.json")
    cost = {"source_file_bytes": {p.name: p.stat().st_size for p in source.iterdir() if p.is_file()},
            "qualification_seconds": time.perf_counter() - started,
            "learner_request_rows": len(request_rows), "health_ticks": summary["calibration_health_ticks"],
            "source_trace_required_by_qualification": True, "source_trace_required_by_temporal_fit": False}
    write_json(audit / "acquisition-audit.json", {**metadata, "status": "fresh_source_and_separation_passed",
               "factor_schedule_seeds": seeds, "namespace": namespace(scope, metadata["source_run_id"], metadata["source_attempt"]),
               "learner_seal_sha256": file_sha256(learner / "seal.json"), "evaluator_seal_sha256": file_sha256(evaluator / "seal.json"),
               "cost": cost, "model_fits": 0, "comparison_scores": 0,
               "acquisition_implementation_sha256": file_sha256(Path(__file__))})
    return {"status": "fresh_source_and_separation_passed", **cell, "scope": scope}


def audit_preflight(input_root, out):
    remote_only()
    config = validate()
    records = [read_json(p) for p in Path(input_root).rglob("acquisition-audit.json")]
    if len(records) != 4 or {identity(r) for r in records} != expected_identities("preflight"):
        raise ValueError("preflight does not contain exactly four prescribed cells")
    for record in records:
        if record["scope"] != "preflight" or record["status"] != "fresh_source_and_separation_passed" or record["model_fits"] or record["comparison_scores"]:
            raise ValueError("preflight scope or no-fit boundary failed")
        if record["config_sha256"] != file_sha256(CONFIG) or record["acquisition_implementation_sha256"] != file_sha256(Path(__file__)):
            raise ValueError("preflight implementation lock differs")
        if record["source_run_id"] != os.environ["GITHUB_RUN_ID"] or record["source_commit"] != os.environ["GITHUB_SHA"]:
            raise ValueError("mixed or historical preflight sources")
    result = {"status": "no_fit_preflight_passed", "cells": 4, "model_fits": 0, "comparison_scores": 0,
              "main_effectiveness_observations": 0, "config_sha256": file_sha256(CONFIG),
              "acquisition_implementation_sha256": file_sha256(Path(__file__)),
              "source_run_id": os.environ["GITHUB_RUN_ID"], "source_commit": os.environ["GITHUB_SHA"],
              "environment": environment_manifest(), "artifact_retention_days": config["artifact_retention_days"],
              "cells_audit": records}
    write_json(Path(out) / "preflight-audit.json", result)
    return {key: result[key] for key in ("status", "cells", "model_fits", "comparison_scores")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    run = sub.add_parser("run-cell")
    for key in ("scope", "placement", "law", "checkout", "compose", "image-audit", "out"):
        run.add_argument("--" + key, required=True)
    run.add_argument("--repetition", type=int, required=True)
    boundary = sub.add_parser("qualify")
    for key in ("source", "out", "scope"):
        boundary.add_argument("--" + key, required=True)
    audit = sub.add_parser("audit-preflight")
    audit.add_argument("--input-root", required=True)
    audit.add_argument("--out", required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    if command == "validate":
        validate()
        result = {"status": "m9p_acquisition_contract_valid", "main_cells": 120, "preflight_cells": 4}
    else:
        result = {"run-cell": run_cell, "qualify": qualify, "audit-preflight": audit_preflight}[command](**args)
    if command != "run-cell":
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
