from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from scipy.stats import chi2, t

from .config import ConfigError, _mapping, _sequence
from .live_stochastic_config import (
    StochasticPilotConfig,
    load_stochastic_pilot_config,
)
from .live_stochastic_pilot import (
    StochasticPilotError,
    aggregate_stochastic_freeze_pilots,
)
from .provenance import environment_manifest, file_sha256


class BudgetRecoveryError(RuntimeError):
    """Raised when the predeclared post-stopping resource rule cannot freeze M7."""


@dataclass(frozen=True)
class MacroBudgetRecoveryConfig:
    id: str
    pilot_only: bool
    stochastic: StochasticPilotConfig
    stochastic_config_path: Path
    source_pilot_run_id: str
    source_pilot_commit: str
    original_recommendation_sha256: str
    original_estimand: str
    revised_estimand: str
    cell_specific_precision_claim: bool
    expected_strata: int
    expected_pilot_pairs_per_stratum: int
    candidate_main_repetitions: tuple[int, ...]
    target_macro_half_width: float
    paired_confidence_level: float
    variance_upper_confidence_level: float
    path: Path


def _positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be an integer") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _open_fraction(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be numeric") from error
    if not 0 < result < 1:
        raise ConfigError(f"{label} must lie in (0, 1)")
    return result


def _positive_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be numeric") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _sha(value: Any, length: int, label: str) -> str:
    result = str(value)
    if len(result) != length or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise ConfigError(f"{label} must be a lowercase hexadecimal digest")
    return result


def _sibling(config_path: Path, value: Any) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts or not relative.name:
        raise ConfigError("stochastic_pilot_config must be a safe relative path")
    resolved = (config_path.parent / relative).resolve()
    if resolved.parent != config_path.parent:
        raise ConfigError("stochastic_pilot_config must remain beside recovery config")
    return resolved


def load_macro_budget_recovery_config(
    path: str | Path,
) -> MacroBudgetRecoveryConfig:
    config_path = Path(path).resolve()
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "macro precision recovery configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("macro recovery schema_version must equal 1")
    if root.get("pilot_only") is not True:
        raise ConfigError("macro recovery must remain pilot_only")
    if root.get("cell_specific_precision_claim") is not False:
        raise ConfigError("recovery must explicitly drop cell-specific precision")
    stochastic_path = _sibling(config_path, root.get("stochastic_pilot_config"))
    stochastic = load_stochastic_pilot_config(stochastic_path)
    candidates = tuple(
        _positive_int(value, "candidate_main_repetitions")
        for value in _sequence(
            root.get("candidate_main_repetitions"),
            "candidate_main_repetitions",
        )
    )
    if tuple(sorted(set(candidates))) != candidates:
        raise ConfigError("candidate_main_repetitions must increase uniquely")
    if candidates != stochastic.design_selection.candidate_main_repetitions:
        raise ConfigError(
            "recovery candidates must preserve the original resource grid"
        )
    source_run = str(root.get("source_pilot_run_id", ""))
    if not source_run.isdigit():
        raise ConfigError("source_pilot_run_id must be numeric")
    config = MacroBudgetRecoveryConfig(
        id=str(root.get("id", "")),
        pilot_only=True,
        stochastic=stochastic,
        stochastic_config_path=stochastic_path,
        source_pilot_run_id=source_run,
        source_pilot_commit=_sha(
            root.get("source_pilot_commit"), 40, "source_pilot_commit"
        ),
        original_recommendation_sha256=_sha(
            root.get("original_recommendation_sha256"),
            64,
            "original_recommendation_sha256",
        ),
        original_estimand=str(root.get("original_estimand", "")),
        revised_estimand=str(root.get("revised_estimand", "")),
        cell_specific_precision_claim=False,
        expected_strata=_positive_int(root.get("expected_strata"), "expected_strata"),
        expected_pilot_pairs_per_stratum=_positive_int(
            root.get("expected_pilot_pairs_per_stratum"),
            "expected_pilot_pairs_per_stratum",
        ),
        candidate_main_repetitions=candidates,
        target_macro_half_width=_positive_float(
            root.get("target_macro_half_width"), "target_macro_half_width"
        ),
        paired_confidence_level=_open_fraction(
            root.get("paired_confidence_level"), "paired_confidence_level"
        ),
        variance_upper_confidence_level=_open_fraction(
            root.get("variance_upper_confidence_level"),
            "variance_upper_confidence_level",
        ),
        path=config_path,
    )
    if not config.id or not config.original_estimand or not config.revised_estimand:
        raise ConfigError("recovery ids and estimands must be nonempty")
    expected_strata = (
        len(stochastic.placement.profiles)
        * len(stochastic.placement.placements)
        * len(stochastic.laws)
    )
    if config.expected_strata != expected_strata:
        raise ConfigError("expected_strata does not match the frozen matrix")
    if (
        config.target_macro_half_width
        != stochastic.design_selection.target_paired_half_width
    ):
        raise ConfigError("macro target must preserve the original 0.015 threshold")
    return config


def macro_repetition_recommendation(
    config: MacroBudgetRecoveryConfig,
    cell_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    strata = len(cell_rows)
    variances = [float(row["sample_sd"]) ** 2 for row in cell_rows]
    degrees = [int(row["pilot_pairs"]) - 1 for row in cell_rows]
    if strata != config.expected_strata or any(
        value != config.expected_pilot_pairs_per_stratum - 1 for value in degrees
    ):
        return {
            "selection_status": "invalid_pilot_matrix",
            "selected_repetitions": None,
        }
    weights = [1.0 / strata] * strata
    macro_variance = sum(
        weight**2 * variance
        for weight, variance in zip(weights, variances, strict=True)
    )
    variance_of_variance = sum(
        (weight**2 * variance) ** 2 / degree
        for weight, variance, degree in zip(weights, variances, degrees, strict=True)
    )
    satterthwaite_df = (
        macro_variance**2 / variance_of_variance
        if variance_of_variance > 0
        else math.inf
    )
    alpha = 1.0 - config.variance_upper_confidence_level
    if math.isfinite(satterthwaite_df) and macro_variance > 0:
        upper_macro_sd = math.sqrt(
            macro_variance * satterthwaite_df / float(chi2.ppf(alpha, satterthwaite_df))
        )
    else:
        upper_macro_sd = 0.0
    candidates = []
    for repetitions in config.candidate_main_repetitions:
        main_df = strata * (repetitions - 1)
        critical = float(t.ppf(0.5 + config.paired_confidence_level / 2.0, main_df))
        half_width = critical * upper_macro_sd / math.sqrt(repetitions)
        candidates.append(
            {
                "repetitions_per_stratum": repetitions,
                "independent_pairs_total": repetitions * strata,
                "projected_macro_half_width": half_width,
                "passed": half_width <= config.target_macro_half_width,
            }
        )
    selected = next((row for row in candidates if row["passed"]), None)
    return {
        "selection_status": "selected" if selected else "no_candidate_met",
        "selected_repetitions": (
            None if selected is None else selected["repetitions_per_stratum"]
        ),
        "estimand": config.revised_estimand,
        "cell_specific_precision_claim": False,
        "strata": strata,
        "pilot_pairs_per_stratum": config.expected_pilot_pairs_per_stratum,
        "estimated_macro_sd_per_balanced_repetition": math.sqrt(macro_variance),
        "satterthwaite_degrees_of_freedom": satterthwaite_df,
        "one_sided_upper_macro_sd": upper_macro_sd,
        "variance_upper_confidence_level": config.variance_upper_confidence_level,
        "paired_confidence_level": config.paired_confidence_level,
        "target_macro_half_width": config.target_macro_half_width,
        "candidates": candidates,
        "planning_quantity": (
            "equal-weight macro-average of calibration-to-test semantic "
            "endpoint-rate differences; a resource proxy, not a method contrast"
        ),
    }


def recover_macro_budget(
    config: MacroBudgetRecoveryConfig,
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    output = Path(output_directory)
    original_output = output / "original-analysis"
    output.mkdir(parents=True, exist_ok=True)
    try:
        original_manifest = aggregate_stochastic_freeze_pilots(
            config.stochastic, input_root, original_output
        )
    except StochasticPilotError:
        manifest_path = original_output / "manifest.json"
        if not manifest_path.is_file():
            raise
        original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    original_recommendation_path = original_output / "recommendation.json"
    original = json.loads(original_recommendation_path.read_text(encoding="utf-8"))
    technical_failures = {
        name: value
        for name, value in original_manifest["quality"].items()
        if name != "design_selection_failures" and value
    }
    repetition = macro_repetition_recommendation(
        config, list(original.get("repetitions", {}).get("cells", []))
    )
    source_manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in Path(input_root).rglob("pilot-manifest.json")
    ]
    source_runs = {
        str(item.get("environment", {}).get("github", {}).get("GITHUB_RUN_ID", ""))
        for item in source_manifests
    } - {""}
    source_commits = {
        str(item.get("environment", {}).get("git", {}).get("commit", ""))
        for item in source_manifests
    } - {""}
    quality = {
        "original_technical_failures": sum(
            int(value) for value in technical_failures.values()
        ),
        "original_stopping_condition_mismatches": int(
            original_manifest["quality"].get("design_selection_failures") != 1
            or original.get("repetitions", {}).get("selection_status")
            != "no_candidate_met"
        ),
        "original_recommendation_hash_mismatches": int(
            file_sha256(original_recommendation_path)
            != config.original_recommendation_sha256
        ),
        "source_run_mismatches": int(source_runs != {config.source_pilot_run_id}),
        "source_commit_mismatches": int(source_commits != {config.source_pilot_commit}),
        "duration_not_selected": int(
            original.get("duration", {}).get("selection_status") != "selected"
        ),
        "transition_guard_not_selected": int(
            original.get("transition_guard", {}).get("selection_status") != "selected"
        ),
        "macro_repetition_not_selected": int(
            repetition.get("selection_status") != "selected"
        ),
    }
    selected_design = dict(original.get("selected_design", {}))
    selected_design["repetitions"] = repetition.get("selected_repetitions")
    canonical = json.dumps(selected_design, sort_keys=True, separators=(",", ":"))
    selected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    recommendation = {
        "schema_version": 1,
        "kind": "m7_macro_precision_resource_recovery",
        "pilot_only": True,
        "freeze_ready": not any(quality.values()),
        "source_pilot_run_id": config.source_pilot_run_id,
        "source_pilot_commit": config.source_pilot_commit,
        "original_recommendation_sha256": config.original_recommendation_sha256,
        "original_stopping_condition": original.get("repetitions"),
        "claim_change": {
            "original_estimand": config.original_estimand,
            "revised_estimand": config.revised_estimand,
            "cell_specific_precision_claim": False,
            "cell_specific_outputs": "descriptive estimates with intervals only",
        },
        "duration": original.get("duration"),
        "transition_guard": original.get("transition_guard"),
        "repetitions": repetition,
        "selected_design": selected_design,
        "selected_design_sha256": selected_hash,
        "inference_boundary": (
            "M7C/M7C-R data select engineering resources only; all pilot "
            "requests remain excluded from M7 fitting and method comparisons"
        ),
    }
    (output / "recommendation.json").write_text(
        json.dumps(recommendation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "kind": "m7_macro_precision_resource_recovery_aggregate",
        "experiment_id": config.id,
        "pilot_only": True,
        "quality": quality,
        "recommendation": recommendation,
        "files": {
            "recommendation_sha256": file_sha256(output / "recommendation.json"),
            "original_manifest_sha256": file_sha256(original_output / "manifest.json"),
            "original_recommendation_sha256": file_sha256(original_recommendation_path),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise BudgetRecoveryError(f"M7C-R acceptance failures: {failures}")
    return manifest
