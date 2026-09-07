"""M9O: audit retained pilot scores and freeze a prospective design, without collection."""
from __future__ import annotations

import argparse
import math
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import chi2, norm

from .checkout_temporal_failover import _identity, _model_key, _rows
from .pmx_failure_semantics import _audit_artifact_metadata, _audit_file, _load_json, _write_csv, _write_json
from .pmx_performability import file_sha256


def validate(config_path: Path) -> dict[str, Any]:
    config = _load_json(config_path, "M9O config")
    if config["id"] != "m9o_independent_temporal_confirmation_preregistration":
        raise ValueError("M9O identity differs")
    for key in ("new_collection_in_this_workflow", "pmx_invocation", "pilot_is_independent_confirmation"):
        if config.get(key) is not False:
            raise ValueError(f"M9O guard differs: {key}")
    planning = config["planning"]
    expected = {
        "strata": 4, "pilot_campaigns_per_stratum": 10, "family_alpha": 0.05,
        "variance_envelope_alpha": 0.05, "minimum_variance_multiplier": 4.0,
        "repetition_grid": [10, 15, 20, 30, 40],
        "metrics": {"conditional_temporal_minus_state_brier": {"half_width": 0.003},
                    "marginal_temporal_minus_state_brier": {"half_width": 0.002},
                    "marginal_temporal_signed_error": {"half_width": 0.02}},
        "working_normal_approximation_is_a_precision_guarantee": False,
        "effect_size_power_claim": False,
    }
    if planning != expected:
        raise ValueError("M9O precision rule differs")
    confirmation = config["confirmation"]
    seeds = [confirmation[key] for key in ("base_seed", "preflight_base_seed", "analysis_seed")]
    if len(set(seeds)) != 3 or set(seeds) & set(confirmation["main_base_seed_must_differ_from"]):
        raise ValueError("prospective seed roots are not separate")
    if confirmation["job_timeout_minutes"] != 360 or confirmation["candidate_selection_after_test"] is not False:
        raise ValueError("confirmation boundary differs")
    root = config_path.resolve().parents[1]
    for name, spec in config["repository_locks"].items():
        _audit_file(root / name, spec, name)
    return config


def _seal(out: Path, name: str, payload: dict[str, Any], files: list[Path]) -> dict[str, Any]:
    payload["files"] = {path.relative_to(out).as_posix(): file_sha256(path) for path in files}
    _write_json(out / name, payload)
    return payload


def _check_files(root: Path, manifest: dict[str, Any]) -> None:
    for name, digest in manifest["files"].items():
        if file_sha256(root / name) != digest:
            raise ValueError(f"design artifact changed: {name}")


def contract(config_path: Path, source: Path, out: Path) -> dict[str, Any]:
    config = validate(config_path)
    for role, spec in config["artifacts"].items():
        _audit_artifact_metadata(source / f"{role}-metadata.json", spec, role,
                                 config["source_run_id"], config["source_head_sha"])
    for name, spec in config["input_files"].items():
        _audit_file(source / name, spec, name)
    evaluation = _load_json(source / "evaluation/evaluation-manifest.json", "M9N evaluation")
    if evaluation["status"] != config["required_branch"] or evaluation["integrity_passed"] is not True:
        raise ValueError("accepted M9N branch differs")
    files = []
    for name in config["input_files"]:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        files.append(target)
    return _seal(out, "contract.json", {
        "status": "locked_m9n_planning_inputs_verified", "config_sha256": file_sha256(config_path),
        "source_run_id": config["source_run_id"], "pilot_only": True,
        "new_live_collections": 0,
    }, files)


def precision_requirements(variances: dict[str, list[float]], planning: dict[str, Any]) -> dict[str, Any]:
    metrics = planning["metrics"]
    if set(variances) != set(metrics) or any(len(values) != 4 for values in variances.values()):
        raise ValueError("planning variance matrix differs")
    if any(not math.isfinite(value) or value < 0 for values in variances.values() for value in values):
        raise ValueError("invalid planning variance")
    df = planning["pilot_campaigns_per_stratum"] - 1
    z = float(norm.ppf(1 - planning["family_alpha"] / (2 * len(metrics))))
    inflation = max(planning["minimum_variance_multiplier"],
                    df / float(chi2.ppf(planning["variance_envelope_alpha"] / (4 * len(metrics)), df)))
    requirements = {}
    for metric, values in variances.items():
        coefficient = z * z * math.fsum(values) * inflation / 16
        width = metrics[metric]["half_width"]
        requirements[metric] = {
            "pilot_stratum_variances": values, "variance_multiplier": inflation,
            "target_half_width": width, "required_per_stratum": math.ceil(coefficient / (width * width)),
            "grid_half_widths": {str(n): math.sqrt(coefficient / n) for n in planning["repetition_grid"]},
        }
    required = max(item["required_per_stratum"] for item in requirements.values())
    selected = next((n for n in planning["repetition_grid"] if n >= required), None)
    return {"normal_critical_value": z, "requirements": requirements, "selected_per_stratum": selected,
            "status": "precision_plan_ready_for_no_fit_preflight" if selected else "precision_budget_requires_redesign",
            "working_normal_approximation_is_a_precision_guarantee": False}


def plan(config_path: Path, source: Path, out: Path) -> dict[str, Any]:
    config = validate(config_path)
    boundary = _load_json(source / "contract.json", "M9O contract")
    _check_files(source, boundary)
    if boundary["config_sha256"] != file_sha256(config_path):
        raise ValueError("M9O config changed after contract")
    tables = {}
    for name, methods in (("marginal-scores.csv", 12), ("conditional-cell-scores.csv", 9)):
        rows = _rows(source / "evaluation" / name)
        indexed = {_model_key(row): row for row in rows}
        if len(rows) != 40 * methods or len(indexed) != len(rows):
            raise ValueError("pilot score matrix differs")
        tables[name] = indexed
    marginal, conditional = tables["marginal-scores.csv"], tables["conditional-cell-scores.csv"]
    values = {name: {} for name in config["planning"]["metrics"]}
    strata = [(p, law) for p in ("colocated", "split") for law in ("N", "ND")]
    variances = {name: [] for name in values}
    for placement, law in strata:
        stratum_values = {name: [] for name in values}
        for repetition in range(10):
            identity = ("opentelemetry_demo", placement, law, repetition)
            primary = marginal[(*identity, "temporal_logit_midpoint")]
            state = marginal[(*identity, "learner_state_only")]
            stratum_values["marginal_temporal_minus_state_brier"].append(float(primary["brier_score"]) - float(state["brier_score"]))
            stratum_values["marginal_temporal_signed_error"].append(float(primary["signed_error"]))
            stratum_values["conditional_temporal_minus_state_brier"].append(
                float(conditional[(*identity, "conditional_temporal_midpoint")]["brier_score"])
                - float(conditional[(*identity, "conditional_state_only")]["brier_score"]))
        for name in values:
            variances[name].append(float(np.var(stratum_values[name], ddof=1)))
    result = precision_requirements(variances, config["planning"])
    out.mkdir(parents=True, exist_ok=True)
    sizing = [{"metric": name, "repetitions_per_stratum": n, "working_half_width": item["grid_half_widths"][str(n)],
               "target_half_width": item["target_half_width"], "meets_working_target": item["grid_half_widths"][str(n)] <= item["target_half_width"]}
              for name, item in result["requirements"].items() for n in config["planning"]["repetition_grid"]]
    _write_csv(out / "precision-grid.csv", list(sizing[0]), sizing)
    count = result["selected_per_stratum"]
    matrix = [{"profile": config["confirmation"]["profile"], "placement": p, "failure_law": law, "repetition": rep,
               "request_namespace": config["confirmation"]["request_namespace"], "base_seed": config["confirmation"]["base_seed"]}
              for p, law in strata for rep in range(count or 0)]
    _write_csv(out / "prospective-campaigns.csv", ["profile", "placement", "failure_law", "repetition", "request_namespace", "base_seed"], matrix)
    result.update({"config_sha256": file_sha256(config_path), "contract_sha256": file_sha256(source / "contract.json"),
                   "selected_campaigns": len(matrix), "nominal_runner_hours": len(matrix) * 1860 / 3600,
                   "new_independent_observations": 0, "full_live_collection_authorized": False,
                   "next_step": "m9p_separate_no_fit_confirmation_preflight" if count else "precision_design_revision_before_collection",
                   "independently_parameterized_pmx_available": False})
    return _seal(out, "design.json", result, [out / "precision-grid.csv", out / "prospective-campaigns.csv"])


def audit(config_path: Path, source: Path, out: Path) -> dict[str, Any]:
    config = validate(config_path)
    design = _load_json(source / "design.json", "M9O design")
    _check_files(source, design)
    if design["config_sha256"] != file_sha256(config_path):
        raise ValueError("M9O config changed after planning")
    n = design["selected_per_stratum"]
    matrix = _rows(source / "prospective-campaigns.csv")
    expected = {(config["confirmation"]["profile"], p, law, rep) for p in ("colocated", "split") for law in ("N", "ND") for rep in range(n or 0)}
    if len(matrix) != len(expected) or {_identity(row) for row in matrix} != expected:
        raise ValueError("prospective identity matrix differs")
    for row in matrix:
        if row["request_namespace"] != config["confirmation"]["request_namespace"] or int(row["base_seed"]) != config["confirmation"]["base_seed"]:
            raise ValueError("prospective namespace or seed differs")
    z = design["normal_critical_value"]
    for requirement in design["requirements"].values():
        coefficient = z**2 * math.fsum(requirement["pilot_stratum_variances"]) * requirement["variance_multiplier"] / 16
        if requirement["required_per_stratum"] != math.ceil(coefficient / requirement["target_half_width"]**2):
            raise ValueError("precision arithmetic differs")
        if n and math.sqrt(coefficient / n) > requirement["target_half_width"]:
            raise ValueError("selected sample misses working precision")
    if design["new_independent_observations"] != 0 or design["full_live_collection_authorized"] is not False:
        raise ValueError("planning was mislabeled as collection")
    out.mkdir(parents=True, exist_ok=True)
    result = {"status": "prospective_design_audited" if n else "precision_budget_requires_redesign",
              "design_sha256": file_sha256(source / "design.json"), "config_sha256": file_sha256(config_path),
              "selected_per_stratum": n, "selected_campaigns": len(matrix),
              "nominal_runner_hours": design["nominal_runner_hours"], "new_independent_observations": 0,
              "full_live_collection_authorized": False, "next_step": design["next_step"]}
    _write_json(out / "audit.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "contract", "plan", "audit"])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        validate(args.config)
        print("M9O config and repository locks valid")
        return
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("M9O full planning and audit run only in GitHub Actions")
    if args.input is None or args.out is None:
        parser.error("--input and --out are required")
    result = {"contract": contract, "plan": plan, "audit": audit}[args.command](args.config, args.input, args.out)
    import json
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
