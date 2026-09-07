"""Frozen M9O inference applied to new M9P learner/evaluator artifacts."""
from __future__ import annotations

import argparse
import csv
from dataclasses import replace
import io
import json
import math
import os
from pathlib import Path
import time

import numpy as np

from . import checkout_temporal_failover as temporal
from .checkout_routing_model import _load_learner_cell
from .live_validation_analysis import EvaluationRequest, _bool, _health_ticks, _timestamp
from .provenance import environment_manifest, file_sha256
from . import temporal_confirmation_live as live

PRIMARY = "temporal_logit_midpoint"
STATE = "learner_state_only"
LOGITS = (STATE, "temporal_logit_lower", PRIMARY, "temporal_logit_upper")
ENDPOINTS = ("matched_stable_endpoint", "all_calibration_endpoint")
METHODS = (*LOGITS, "source_500ms_failover", *ENDPOINTS)
METRICS = ("conditional_temporal_minus_state_brier", "marginal_temporal_minus_state_brier", "marginal_temporal_signed_error")


def analysis_config():
    confirmation = live.validate()["confirmation"]
    historical = temporal.load_temporal_config(live.ROOT / "configs/m9n_checkout_temporal_failover.json")
    return replace(historical, repetitions=tuple(range(30)), expected_cells=120,
                   seed=confirmation["analysis_seed"], resamples=confirmation["bootstrap_resamples"],
                   confidence_level=1 - 0.05 / 3)


def discover_bundles(root, allowed):
    root = Path(root)
    if allowed == live.LEARNER_FILES and any(p.name == "evaluator" for p in root.rglob("*")):
        raise ValueError("held-out evaluator directory present before fit")
    bundles = {}
    for path in sorted(root.glob("*/seal.json")):
        record = live.verify_seal(path.parent, allowed)
        key = live.identity(record)
        if key in bundles or key not in live.expected_identities("full") or record["scope"] != "full":
            raise ValueError("unexpected or duplicate main campaign")
        if record["source_run_id"] != os.environ["GITHUB_RUN_ID"] or record["source_commit"] != os.environ["GITHUB_SHA"]:
            raise ValueError("historical or mixed acquisition source")
        if record["source_attempt"] != os.environ["GITHUB_RUN_ATTEMPT"]:
            raise ValueError("mixed acquisition attempts require an explicit recovery audit")
        if record["config_sha256"] != file_sha256(live.CONFIG):
            raise ValueError("acquisition protocol differs")
        bundles[key] = (path.parent, record)
    if set(bundles) != live.expected_identities("full"):
        raise ValueError(f"incomplete confirmation: {len(bundles)}/120 campaigns; no subset inference")
    expected_files = {p for directory, _ in bundles.values() for p in directory.rglob("*") if p.is_file()}
    if {p for p in root.rglob("*") if p.is_file()} != expected_files:
        raise ValueError("unexpected file outside sealed campaign bundles")
    return bundles


def endpoint_probability(successes, attempts):
    if not 0 <= successes <= attempts or attempts < 1:
        raise ValueError("endpoint requires a nonempty valid count")
    return (successes + 0.5) / (attempts + 1.0)


def bernoulli_brier(probability, observed):
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (probability, observed)):
        raise ValueError("invalid Bernoulli score input")
    return probability * probability + observed * (1 - 2 * probability)


def adequacy_passed(audit, config, *, test=False):
    enough = audit["stable_aligned_requests"] >= (config.minimum_stable_test if test else config.minimum_stable_calibration)
    enough &= audit["maximum_age_interval_width"] <= config.interval_width_limit
    if not test:
        enough &= (audit["one_path_up_requests"] >= config.minimum_one_path
                   and audit["one_path_up_episodes"] >= config.minimum_episodes
                   and audit["early_one_path_requests"] >= config.minimum_early
                   and audit["late_one_path_requests"] >= config.minimum_late)
    return bool(enough)


def optimizer_passed(fit, config):
    return (fit["finite_starts"] == 8 and fit["converged_starts"] >= 1
            and fit["equivalent_prediction_range"] <= config.fit_range_tolerance)


def projected_request_bytes(request_rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(request_rows)
    return len(stream.getvalue().encode("utf-8"))


def finite_json(value):
    """Keep missing descriptive rates explicit rather than writing nonstandard NaN."""
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [finite_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def freeze_candidates(input_root, out):
    live.remote_only()
    started = time.perf_counter()
    config = analysis_config()
    bundles = discover_bundles(input_root, live.LEARNER_FILES)
    candidates, audits, costs, input_seals = [], [], [], []
    all_fits_passed = True
    for key, (directory, source) in sorted(bundles.items()):
        parse_started = time.perf_counter()
        cell = _load_learner_cell(directory)
        if cell.identity != key or cell.test_requests or cell.test_health:
            raise ValueError("learner identity or physical boundary differs")
        q, baseline_n, baseline_s = temporal._baseline_q(cell, "checkout")
        calibration = [r for r in cell.learner_requests if r.period == "calibration"]
        parse_seconds = time.perf_counter() - parse_started
        selection_started = time.perf_counter()
        records, audit = temporal._temporal_records(calibration, cell.health, "checkout", config.alignment_tolerance, config.transition_guard)
        selection_seconds = time.perf_counter() - selection_started
        if not records:
            raise ValueError(f"no eligible learner requests: {key}; no subset inference")
        base = dict(zip(live.IDENTITY, key, strict=True))
        method_predictions = {}
        request_rows = live.rows(directory / "learner/requests.csv")
        minimal_endpoint_bytes = projected_request_bytes([r for r in request_rows if r["period"] == "calibration" and r["operation"] == "checkout"], ("period", "operation", "semantic_success"))
        health_bytes = (directory / "learner/health.csv").stat().st_size
        request_bytes = (directory / "learner/requests.csv").stat().st_size
        for method in METHODS:
            fit_started = time.perf_counter()
            fit = None
            parameters = []
            if method in LOGITS:
                fit = temporal._fit_logit(records, q, method, key, config)
                parameters = list(fit["parameters"])
                probability = fit["prediction"]
                all_fits_passed &= optimizer_passed(fit, config)
            elif method == "source_500ms_failover":
                probability = temporal._marginal_prediction(records, q, method)
            else:
                outcomes = ([r.success for r in records] if method == "matched_stable_endpoint"
                            else [r.success for r in calibration if r.operation == "checkout"])
                probability = endpoint_probability(sum(outcomes), len(outcomes))
            fit_seconds = time.perf_counter() - fit_started
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("invalid frozen probability")
            method_predictions[method] = probability
            candidates.append({**base, "method": method, "prediction": probability,
                               "q": q, "parameters_json": json.dumps(parameters),
                               "fit_json": json.dumps(fit, sort_keys=True) if fit else "null"})
            needs_health = method != "all_calibration_endpoint"
            costs.append({**base, "method": method,
                          "actual_shared_learner_request_file_bytes": request_bytes,
                          "actual_health_input_bytes": health_bytes if needs_health else 0,
                          "minimal_endpoint_request_projection_bytes": minimal_endpoint_bytes if not needs_health else "",
                          "learner_request_rows": len(cell.learner_requests) if needs_health else len(outcomes),
                          "health_ticks": len(cell.health) if needs_health else 0,
                          "trace_input_bytes_for_model": 0,
                          "shared_parse_seconds_measured": parse_seconds,
                          "shared_stability_episode_age_construction_seconds": selection_seconds if needs_health else 0,
                          "method_fit_or_estimation_seconds": fit_seconds,
                          "deployment_routing_knowledge_required": method not in ENDPOINTS,
                          "shared_acquisition_cost_recorded_separately": True,
                          "isolated_endpoint_io_time_measured": False})
        span = max(method_predictions[f"temporal_logit_{v}"] for v in temporal.AGE_VIEWS) - min(method_predictions[f"temporal_logit_{v}"] for v in temporal.AGE_VIEWS)
        audits.append({**base, **audit, "baseline_requests": baseline_n, "baseline_successes": baseline_s,
                       "q": q, "interval_prediction_span": span, "adequacy_passed": adequacy_passed(audit, config)})
        input_seals.append({**base, "seal_sha256": file_sha256(directory / "seal.json"),
                            "source_attempt": source["source_attempt"], "files": source["files"]})
        print(f"froze {key[1]}/{key[2]}/r{key[3]} ({len(audits)}/120)", flush=True)
    out = Path(out)
    live.write_csv(out / "candidate-predictions.csv", candidates)
    live.write_csv(out / "calibration-audit.csv", audits)
    live.write_csv(out / "model-input-costs.csv", costs)
    live.write_json(out / "learner-input-seals.json", input_seals)
    manifest = {"status": "all_prospective_candidates_frozen", "cells": len(audits), "methods": list(METHODS),
                "candidate_rows": len(candidates), "source_run_id": os.environ["GITHUB_RUN_ID"],
                "source_commit": os.environ["GITHUB_SHA"], "config_sha256": file_sha256(live.CONFIG),
                "analysis_implementation_sha256": file_sha256(Path(__file__)),
                "learner_adequacy_passed": all(r["adequacy_passed"] for r in audits),
                "fit_integrity_passed": bool(all_fits_passed),
                "mean_within_cell_interval_prediction_span": float(np.mean([r["interval_prediction_span"] for r in audits])),
                "test_outcomes_accessed": False, "test_health_accessed": False,
                "raw_traces_staged": False, "candidate_selection_after_test": False,
                "calibration_diagnostics_are_descriptive": True,
                "total_candidate_seconds": time.perf_counter() - started,
                "environment": environment_manifest()}
    live.write_json(out / "candidate-manifest.json", manifest)
    live.seal(out, {"kind": "m9p_candidates", "source_run_id": os.environ["GITHUB_RUN_ID"]})
    return manifest


def bootstrap_family(campaign_values, *, repetitions=30, resamples=10000, seed=2026090703, family_alpha=0.05):
    """Resample paired campaign vectors within four equally weighted strata."""
    expected = {(live.PROFILE, p, law, r) for p in ("colocated", "split") for law in ("N", "ND") for r in range(repetitions)}
    if set(campaign_values) != expected:
        raise ValueError("incomplete or duplicate inference matrix")
    strata = np.asarray([[campaign_values[(live.PROFILE, p, law, r)] for r in range(repetitions)]
                         for p in ("colocated", "split") for law in ("N", "ND")], dtype=float)
    if strata.shape != (4, repetitions, 3) or not np.isfinite(strata).all():
        raise ValueError("inferential metric vector differs or is nonfinite")
    generator = np.random.default_rng(seed)
    samples = np.zeros((resamples, 3))
    for stratum in strata:
        draws = generator.integers(0, repetitions, size=(resamples, repetitions))
        samples += stratum[draws].mean(axis=1) / 4
    alpha = family_alpha / 3
    estimates = strata.mean(axis=(0, 1))
    lower, upper = np.quantile(samples, (alpha / 2, 1 - alpha / 2), axis=0)
    return {metric: {"estimate": float(estimates[i]), "lower": float(lower[i]), "upper": float(upper[i]),
                     "confidence_level": 1 - alpha, "campaigns": 4 * repetitions, "resamples": resamples}
            for i, metric in enumerate(METRICS)}


def classify(intervals, integrity_passed):
    conditional, marginal, calibration = (intervals[name] for name in METRICS)
    result = {
        "status": "independent_confirmation_complete" if integrity_passed else "independent_confirmation_inadequate",
        "inferential_claims_admissible": bool(integrity_passed),
        "conditional_temporal_information": "replicated" if conditional["upper"] < 0 else "not_confirmed",
        "marginal_increment": (
            "practically_equivalent" if marginal["lower"] >= -0.002 and marginal["upper"] <= 0.002
            else "material_temporal_advantage" if marginal["upper"] < -0.002 else "unresolved"),
        "mean_marginal_calibration": "adequate" if calibration["lower"] >= -0.03 and calibration["upper"] <= 0.03 else "not_confirmed",
        "conditional_score_is_advance_forecast": False, "general_accuracy_or_pmx_claim": False,
    }
    if not integrity_passed:
        for name in ("conditional_temporal_information", "marginal_increment", "mean_marginal_calibration"):
            result[name] = "inadequate_confirmation"
    return result


def evaluate(input_root, candidates, out):
    live.remote_only()
    started = time.perf_counter()
    config = analysis_config()
    candidates, out = Path(candidates), Path(out)
    live.verify_seal(candidates)
    manifest = live.read_json(candidates / "candidate-manifest.json")
    if (manifest["source_run_id"] != os.environ["GITHUB_RUN_ID"] or manifest["source_commit"] != os.environ["GITHUB_SHA"]
            or manifest["analysis_implementation_sha256"] != file_sha256(Path(__file__))
            or manifest["config_sha256"] != file_sha256(live.CONFIG)
            or manifest["test_outcomes_accessed"] or manifest["test_health_accessed"]):
        raise ValueError("candidate provenance or frozen boundary differs")
    candidate_rows = live.rows(candidates / "candidate-predictions.csv")
    indexed = {(live.identity(row), row["method"]): row for row in candidate_rows}
    expected = {(key, method) for key in live.expected_identities("full") for method in METHODS}
    if set(indexed) != expected or len(indexed) != len(candidate_rows):
        raise ValueError("candidate matrix incomplete or duplicated")
    bundles = discover_bundles(input_root, live.EVALUATOR_FILES)
    marginal_rows, conditional_rows, test_audits, evaluation_costs = [], [], [], []
    inference_vectors = {}
    for key, (directory, source) in sorted(bundles.items()):
        base = dict(zip(live.IDENTITY, key, strict=True))
        parse_started = time.perf_counter()
        raw = live.rows(directory / "evaluator/test-requests.csv")
        requests = tuple(EvaluationRequest(operation=r["operation"], at=_timestamp(r["started_at"]), success=int(_bool(r["semantic_success"]))) for r in raw)
        ticks = _health_ticks(directory / "evaluator/test-health.csv")
        records, audit = temporal._temporal_records(requests, ticks, "checkout", config.alignment_tolerance, config.transition_guard)
        parse_seconds = time.perf_counter() - parse_started
        if not records:
            raise ValueError(f"empty held-out eligible subset: {key}; no subset inference")
        test_audits.append({**base, **audit, "adequacy_passed": adequacy_passed(audit, config, test=True),
                            "source_attempt": source["source_attempt"]})
        observed = sum(r.success for r in records) / len(records)
        cell_marginal, cell_conditional = {}, {}
        for method in METHODS:
            score_started = time.perf_counter()
            row = indexed[(key, method)]
            probability = float(row["prediction"])
            q = float(row["q"])
            parameters = json.loads(row["parameters_json"])
            marginal = bernoulli_brier(probability, observed)
            conditional_probabilities = ([probability] * len(records) if method in ENDPOINTS else
                                         [q * temporal._route_value(record, method, parameters) for record in records])
            conditional = sum((p - record.success) ** 2 for p, record in zip(conditional_probabilities, records, strict=True)) / len(records)
            common = {**base, "method": method, "test_requests": len(records), "test_success_rate": observed}
            marginal_rows.append({**common, "prediction": probability, "signed_error": probability - observed,
                                  "absolute_error": abs(probability - observed), "brier_score": marginal})
            conditional_rows.append({**common, "mean_conditional_probability": sum(conditional_probabilities) / len(records),
                                     "brier_score": conditional, "uses_heldout_health": method not in ENDPOINTS})
            evaluation_costs.append({**base, "method": method, "shared_test_parse_selection_seconds": parse_seconds,
                                     "method_scoring_seconds": time.perf_counter() - score_started,
                                     "test_request_bytes": (directory / "evaluator/test-requests.csv").stat().st_size,
                                     "test_health_bytes": (directory / "evaluator/test-health.csv").stat().st_size})
            cell_marginal[method] = marginal
            cell_conditional[method] = conditional
        inference_vectors[key] = (cell_conditional[PRIMARY] - cell_conditional[STATE],
                                  cell_marginal[PRIMARY] - cell_marginal[STATE], float(indexed[(key, PRIMARY)]["prediction"]) - observed)
    intervals = bootstrap_family(inference_vectors, resamples=config.resamples, seed=config.seed)
    gates = {"learner_adequacy": manifest["learner_adequacy_passed"], "fit_integrity": manifest["fit_integrity_passed"],
             "test_adequacy": all(r["adequacy_passed"] for r in test_audits),
             "interval_sensitivity": manifest["mean_within_cell_interval_prediction_span"] <= config.interval_prediction_span,
             "complete_campaign_matrix": len(bundles) == 120}
    decision = classify(intervals, all(gates.values()))
    descriptive = {}
    for method in METHODS:
        selected = [r for r in marginal_rows if r["method"] == method]
        conditional = [r for r in conditional_rows if r["method"] == method]
        descriptive[method] = {name: float(np.mean([r[name] for r in selected])) for name in ("prediction", "test_success_rate", "signed_error", "absolute_error", "brier_score")}
        descriptive[method]["conditional_brier_score"] = float(np.mean([r["brier_score"] for r in conditional]))
    for name, values in (("marginal-scores.csv", marginal_rows), ("conditional-scores.csv", conditional_rows),
                         ("test-adequacy.csv", test_audits), ("evaluation-costs.csv", evaluation_costs)):
        live.write_csv(out / name, values)
    live.write_json(out / "inference.json", intervals)
    result = {**decision, "gates": gates, "intervals": intervals, "descriptive_method_means": descriptive,
              "candidate_seal_sha256": file_sha256(candidates / "seal.json"),
              "source_run_id": os.environ["GITHUB_RUN_ID"], "source_commit": os.environ["GITHUB_SHA"],
              "analysis_implementation_sha256": file_sha256(Path(__file__)), "config_sha256": file_sha256(live.CONFIG),
              "evaluation_seconds": time.perf_counter() - started,
              "environment": environment_manifest()}
    live.write_json(out / "evaluation-manifest.json", finite_json(result))
    live.seal(out, {"kind": "m9p_evaluation", "source_run_id": os.environ["GITHUB_RUN_ID"]})
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    for command in ("freeze-candidates", "evaluate"):
        child = sub.add_parser(command)
        child.add_argument("--input-root", required=True)
        child.add_argument("--out", required=True)
        if command == "evaluate":
            child.add_argument("--candidates", required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    if command == "validate":
        analysis_config()
        result = {"status": "m9p_analysis_config_valid", "cells": 120, "methods": list(METHODS), "inference_metrics": list(METRICS)}
    else:
        result = {"freeze-candidates": freeze_candidates, "evaluate": evaluate}[command](**args)
    print(json.dumps(finite_json(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
