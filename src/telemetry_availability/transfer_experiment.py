from __future__ import annotations

import csv
import json
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .likelihood import compress_observed_patterns, fit_exact_observed_likelihood
from .likelihood_reference import _pattern_rows
from .observation import ObservationPolicy, simulate_batch
from .provenance import environment_manifest, file_sha256
from .runner import _selected, _write_csv, stable_seed
from .transfer import (
    TARGET_ADD,
    TARGET_CURRENT,
    TARGET_IDS,
    TARGET_SPLIT,
    direct_current_rate,
    empirical_joint_current_rate,
    fit_available_domain_moments,
    health_marginals,
    independent_predictions,
    transfer_probabilities,
)
from .transfer_config import TransferExperimentConfig
from .transfer_identifiability import (
    PROVED_IDENTIFIABLE,
    ambiguity_witnesses,
    diagnose_transfer_targets,
)


METHOD_B0 = "b0_endpoint_persistence"
METHOD_B1 = "b1_independent_marginals"
METHOD_B2 = "b2_available_domain_moments"
METHOD_B3 = "b3_exact_likelihood"
METHOD_PROPOSED = "proposed_identification_aware_likelihood"
METHOD_B4 = "b4_empirical_joint"
METHODS = (METHOD_B0, METHOD_B1, METHOD_B2, METHOD_B3, METHOD_PROPOSED, METHOD_B4)

FIT_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "status",
    "converged",
    "parameter_identifiability_status",
    "transfer_identifiable",
    "estimation_source",
    "runtime_seconds",
    "negative_log_likelihood",
    "iterations",
    "boundary_parameter_count",
    "near_optimal_parameter_spread",
    "shared_fit_with",
)

PARAMETER_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "factor",
    "role",
    "identifiability_status",
    "truth",
    "estimate",
    "signed_error",
    "absolute_error",
)

PREDICTION_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "target",
    "is_transfer_target",
    "directly_observed_in_calibration",
    "prediction_rule",
    "identifiability_status",
    "truth",
    "estimate",
    "signed_error",
    "absolute_error",
)

DECISION_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "transfer_identifiability_status",
    "true_best",
    "selected",
    "decision_available",
    "correct",
    "unsupported_decision",
    "regret",
    "predicted_split",
    "predicted_add",
    "true_split",
    "true_add",
)

VALIDATION_FIELDS = (
    "experiment_id",
    "scenario",
    "repetition",
    "target",
    "truth",
    "validation_episodes",
    "successes",
    "validation_rate",
    "validation_signed_error",
    "validation_absolute_error",
)

PATTERN_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "pattern_id",
    "observed_ids",
    "observed_values",
    "count",
)

IDENTIFICATION_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "target",
    "status",
    "certificate",
)

WITNESS_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "target",
    "first_parameters",
    "second_parameters",
    "first_target",
    "second_target",
    "absolute_target_change",
    "max_supported_observable_difference",
)

CHANGE_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "target",
    "identifiability_status",
    "truth_current",
    "truth_target",
    "truth_change",
    "estimated_current",
    "estimated_target",
    "estimated_change",
    "signed_error",
    "absolute_error",
)

PREDICTION_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "method",
    "target",
    "identifiability_status",
    "datasets",
    "prediction_rate",
    "mae",
    "signed_bias",
)

DECISION_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "method",
    "datasets",
    "decision_coverage",
    "unsupported_decision_rate",
    "accuracy_when_decided",
    "mean_regret_when_decided",
    "split_selection_rate_when_decided",
)

PARAMETER_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "method",
    "identifiability_status",
    "datasets",
    "parameter_estimate_rate",
    "parameter_mae",
    "parameter_signed_bias",
)

CHANGE_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "method",
    "target",
    "identifiability_status",
    "datasets",
    "prediction_rate",
    "change_mae",
    "change_signed_bias",
)

CONTRAST_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "target",
    "baseline",
    "campaign_pairs",
    "mean_absolute_error_delta_proposed_minus_baseline",
    "median_absolute_error_delta_proposed_minus_baseline",
    "mean_delta_ci95_low",
    "mean_delta_ci95_high",
    "proposed_win_rate",
)

CHANGE_CONTRAST_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "target",
    "baseline",
    "campaign_pairs",
    "mean_absolute_error_delta_proposed_minus_baseline",
    "median_absolute_error_delta_proposed_minus_baseline",
    "mean_delta_ci95_low",
    "mean_delta_ci95_high",
    "proposed_win_rate",
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _mean(values: Iterable[float | None]) -> float | None:
    materialized = [float(value) for value in values if value is not None]
    return float(statistics.fmean(materialized)) if materialized else None


def _median(values: Iterable[float | None]) -> float | None:
    materialized = [float(value) for value in values if value is not None]
    return float(statistics.median(materialized)) if materialized else None


def _bootstrap_mean_interval(
    values: list[float],
    *seed_parts: object,
    replicates: int = 2_000,
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    vector = np.asarray(values, dtype=float)
    if len(vector) == 1:
        return float(vector[0]), float(vector[0])
    rng = np.random.default_rng(stable_seed(260905, "m3_evaluation_bootstrap", *seed_parts))
    indices = rng.integers(0, len(vector), size=(replicates, len(vector)))
    means = np.mean(vector[indices], axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return float(low), float(high)


def _has_trace(policy: ObservationPolicy) -> bool:
    return policy.includes_kind("trace") and policy.sampling_by_kind.get("trace", 1.0) > 0.0


def _fit_row(
    base: dict[str, Any],
    method: str,
    status: str,
    converged: bool,
    parameter_identifiability_status: str,
    transfer_identifiable: bool,
    runtime_seconds: float,
    estimation_source: str = "",
    negative_log_likelihood: float | None = None,
    iterations: int = 0,
    boundary_parameter_count: int = 0,
    near_optimal_parameter_spread: float | None = None,
    shared_fit_with: str = "",
) -> dict[str, Any]:
    return {
        **base,
        "method": method,
        "status": status,
        "converged": converged,
        "parameter_identifiability_status": parameter_identifiability_status,
        "transfer_identifiable": transfer_identifiable,
        "estimation_source": estimation_source,
        "runtime_seconds": runtime_seconds,
        "negative_log_likelihood": negative_log_likelihood,
        "iterations": iterations,
        "boundary_parameter_count": boundary_parameter_count,
        "near_optimal_parameter_spread": near_optimal_parameter_spread,
        "shared_fit_with": shared_fit_with,
    }


def _append_parameters(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    method: str,
    model: Any,
    estimates: dict[str, float] | None,
    identifiability_status: str,
) -> None:
    for factor in model.factors:
        estimate = None if estimates is None else estimates[factor.id]
        error = None if estimate is None else estimate - factor.probability
        rows.append(
            {
                **base,
                "method": method,
                "factor": factor.id,
                "role": factor.role,
                "identifiability_status": identifiability_status,
                "truth": factor.probability,
                "estimate": estimate,
                "signed_error": error,
                "absolute_error": None if error is None else abs(error),
            }
        )


def _append_predictions(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    method: str,
    truths: dict[str, float],
    estimates: dict[str, float | None],
    rule: str,
    trace_observed: bool,
    identification: dict[str, Any],
) -> None:
    for target in TARGET_IDS:
        estimate = estimates.get(target)
        error = None if estimate is None else estimate - truths[target]
        rows.append(
            {
                **base,
                "method": method,
                "target": target,
                "is_transfer_target": target != TARGET_CURRENT,
                "directly_observed_in_calibration": (
                    target == TARGET_CURRENT and trace_observed
                ),
                "prediction_rule": rule,
                "identifiability_status": identification[target].status,
                "truth": truths[target],
                "estimate": estimate,
                "signed_error": error,
                "absolute_error": None if error is None else abs(error),
            }
        )


def _decision_row(
    base: dict[str, Any],
    method: str,
    truths: dict[str, float],
    estimates: dict[str, float | None],
    transfer_identifiability_status: str,
) -> dict[str, Any]:
    true_best = TARGET_SPLIT if truths[TARGET_SPLIT] > truths[TARGET_ADD] else TARGET_ADD
    split = estimates.get(TARGET_SPLIT)
    add = estimates.get(TARGET_ADD)
    selected: str | None = None
    if split is not None and add is not None and abs(split - add) > 1e-12:
        selected = TARGET_SPLIT if split > add else TARGET_ADD
    correct = None if selected is None else selected == true_best
    regret = (
        None
        if selected is None
        else max(truths[TARGET_SPLIT], truths[TARGET_ADD]) - truths[selected]
    )
    return {
        **base,
        "method": method,
        "transfer_identifiability_status": transfer_identifiability_status,
        "true_best": true_best,
        "selected": selected,
        "decision_available": selected is not None,
        "correct": correct,
        "unsupported_decision": (
            selected is not None
            and transfer_identifiability_status != PROVED_IDENTIFIABLE
        ),
        "regret": regret,
        "predicted_split": split,
        "predicted_add": add,
        "true_split": truths[TARGET_SPLIT],
        "true_add": truths[TARGET_ADD],
    }


def summarize_predictions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["scenario"]),
            str(row["observation_mode"]),
            int(row["sample_size"]),
            str(row["method"]),
            str(row["target"]),
            str(row["identifiability_status"]),
        )
        grouped[key].append(row)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        available = [row for row in group if _optional_float(row["estimate"]) is not None]
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "method": key[3],
                "target": key[4],
                "identifiability_status": key[5],
                "datasets": len(group),
                "prediction_rate": len(available) / len(group),
                "mae": _mean(_optional_float(row["absolute_error"]) for row in available),
                "signed_bias": _mean(_optional_float(row["signed_error"]) for row in available),
            }
        )
    return result


def summarize_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["scenario"]), str(row["observation_mode"]), int(row["sample_size"]), str(row["method"]))].append(row)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        decided = [row for row in group if _as_bool(row["decision_available"])]
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "method": key[3],
                "datasets": len(group),
                "decision_coverage": len(decided) / len(group),
                "unsupported_decision_rate": _mean(
                    float(_as_bool(row["unsupported_decision"])) for row in group
                ),
                "accuracy_when_decided": _mean(
                    float(_as_bool(row["correct"])) for row in decided
                ),
                "mean_regret_when_decided": _mean(
                    _optional_float(row["regret"]) for row in decided
                ),
                "split_selection_rate_when_decided": _mean(
                    float(row["selected"] == TARGET_SPLIT) for row in decided
                ),
            }
        )
    return result


def summarize_parameters(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["scenario"]),
                str(row["observation_mode"]),
                int(row["sample_size"]),
                str(row["method"]),
                str(row["identifiability_status"]),
            )
        ].append(row)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        available = [row for row in group if _optional_float(row["estimate"]) is not None]
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "method": key[3],
                "identifiability_status": key[4],
                "datasets": len({int(row["repetition"]) for row in group}),
                "parameter_estimate_rate": len(available) / len(group),
                "parameter_mae": _mean(
                    _optional_float(row["absolute_error"]) for row in available
                ),
                "parameter_signed_bias": _mean(
                    _optional_float(row["signed_error"]) for row in available
                ),
            }
        )
    return result


def build_change_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["experiment_id"]),
            str(row["scenario"]),
            str(row["observation_mode"]),
            int(row["repetition"]),
            int(row["sample_size"]),
            str(row["method"]),
        )
        grouped[key].append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(grouped):
        lookup = {str(row["target"]): row for row in grouped[key]}
        current = lookup[TARGET_CURRENT]
        truth_current = float(current["truth"])
        estimated_current = _optional_float(current["estimate"])
        for target in (TARGET_SPLIT, TARGET_ADD):
            target_row = lookup[target]
            truth_target = float(target_row["truth"])
            estimated_target = _optional_float(target_row["estimate"])
            estimated_change = (
                None
                if estimated_current is None or estimated_target is None
                else estimated_target - estimated_current
            )
            truth_change = truth_target - truth_current
            error = (
                None
                if estimated_change is None
                else estimated_change - truth_change
            )
            result.append(
                {
                    "experiment_id": key[0],
                    "scenario": key[1],
                    "observation_mode": key[2],
                    "repetition": key[3],
                    "sample_size": key[4],
                    "method": key[5],
                    "target": target,
                    "identifiability_status": target_row["identifiability_status"],
                    "truth_current": truth_current,
                    "truth_target": truth_target,
                    "truth_change": truth_change,
                    "estimated_current": estimated_current,
                    "estimated_target": estimated_target,
                    "estimated_change": estimated_change,
                    "signed_error": error,
                    "absolute_error": None if error is None else abs(error),
                }
            )
    return result


def summarize_changes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["scenario"]),
            str(row["observation_mode"]),
            int(row["sample_size"]),
            str(row["method"]),
            str(row["target"]),
            str(row["identifiability_status"]),
        )
        grouped[key].append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(grouped):
        group = grouped[key]
        available = [row for row in group if _optional_float(row["estimated_change"]) is not None]
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "method": key[3],
                "target": key[4],
                "identifiability_status": key[5],
                "datasets": len(group),
                "prediction_rate": len(available) / len(group),
                "change_mae": _mean(
                    _optional_float(row["absolute_error"]) for row in available
                ),
                "change_signed_bias": _mean(
                    _optional_float(row["signed_error"]) for row in available
                ),
            }
        )
    return result


def paired_contrasts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["scenario"]), str(row["observation_mode"]), int(row["sample_size"]), str(row["target"]))].append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(grouped):
        group = grouped[key]
        for baseline in (METHOD_B0, METHOD_B1, METHOD_B2, METHOD_B3, METHOD_B4):
            deltas = []
            for repetition in sorted({int(row["repetition"]) for row in group}):
                selected = [row for row in group if int(row["repetition"]) == repetition]
                lookup = {str(row["method"]): _optional_float(row["absolute_error"]) for row in selected}
                proposed = lookup.get(METHOD_PROPOSED)
                baseline_error = lookup.get(baseline)
                if proposed is not None and baseline_error is not None:
                    deltas.append(proposed - baseline_error)
            interval_low, interval_high = _bootstrap_mean_interval(
                deltas,
                *key,
                baseline,
            )
            result.append(
                {
                    "scenario": key[0],
                    "observation_mode": key[1],
                    "sample_size": key[2],
                    "target": key[3],
                    "baseline": baseline,
                    "campaign_pairs": len(deltas),
                    "mean_absolute_error_delta_proposed_minus_baseline": _mean(deltas),
                    "median_absolute_error_delta_proposed_minus_baseline": _median(deltas),
                    "mean_delta_ci95_low": interval_low,
                    "mean_delta_ci95_high": interval_high,
                    "proposed_win_rate": (
                        _mean(float(delta < 0.0) for delta in deltas) if deltas else None
                    ),
                }
            )
    return result


def quality_metrics(
    predictions: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    witnesses: list[dict[str, Any]],
) -> dict[str, int]:
    grouped: dict[tuple[str, str, int, int, str], dict[str, float | None]] = defaultdict(dict)
    for row in predictions:
        key = (
            str(row["scenario"]),
            str(row["observation_mode"]),
            int(row["repetition"]),
            int(row["sample_size"]),
            str(row["target"]),
        )
        grouped[key][str(row["method"])] = _optional_float(row["estimate"])
    matched_failures = 0
    for values in grouped.values():
        proposed = values.get(METHOD_PROPOSED)
        reference = values.get(METHOD_B3)
        if proposed is not None and (
            reference is None or abs(proposed - reference) > 1e-12
        ):
            matched_failures += 1
    witness_failures = sum(
        _optional_float(row["max_supported_observable_difference"]) is None
        or float(row["max_supported_observable_difference"]) > 1e-12
        or _optional_float(row["absolute_target_change"]) is None
        or float(row["absolute_target_change"]) <= 1e-6
        for row in witnesses
    )
    proposed_unsupported = sum(
        str(row["method"]) == METHOD_PROPOSED
        and _as_bool(row["unsupported_decision"])
        for row in decisions
    )
    b3_unsupported = sum(
        str(row["method"]) == METHOD_B3
        and _as_bool(row["unsupported_decision"])
        for row in decisions
    )
    return {
        "matched_b3_prediction_failures": matched_failures,
        "ambiguity_witness_failures": witness_failures,
        "proposed_unsupported_decisions": proposed_unsupported,
        "b3_raw_unsupported_decisions": b3_unsupported,
    }


def run_transfer_experiment(
    config: TransferExperimentConfig,
    config_path: str | Path,
    output_directory: str | Path,
    scenario_names: tuple[str, ...] | None = None,
    mode_names: tuple[str, ...] | None = None,
    repetitions: int | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    validation_episodes: int | None = None,
) -> dict[str, Any]:
    scenarios = _selected(config.scenarios, scenario_names, "scenarios")
    policies: tuple[ObservationPolicy, ...] = _selected(
        config.observation_modes,
        mode_names,
        "observation modes",
    )
    actual_repetitions = config.repetitions if repetitions is None else repetitions
    actual_sizes = config.sample_sizes if sample_sizes is None else sample_sizes
    actual_validation = (
        config.validation_episodes if validation_episodes is None else validation_episodes
    )
    if actual_repetitions <= 0 or actual_validation <= 0:
        raise ValueError("repetitions and validation episodes must be positive")
    if not actual_sizes or tuple(sorted(set(actual_sizes))) != actual_sizes:
        raise ValueError("sample sizes must be strictly increasing")
    dataset_count = len(scenarios) * len(policies) * actual_repetitions * len(actual_sizes)
    if (
        os.environ.get("GITHUB_ACTIONS", "").lower() != "true"
        and dataset_count > config.local_smoke_max_dataset_fits
    ):
        raise RuntimeError(
            "transfer experiment exceeds the local smoke budget "
            f"({dataset_count} > {config.local_smoke_max_dataset_fits} datasets); "
            "run it through GitHub Actions"
        )

    fit_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    pattern_rows: list[dict[str, Any]] = []
    identification_rows: list[dict[str, Any]] = []
    witness_rows: list[dict[str, Any]] = []
    max_size = max(actual_sizes)

    for scenario in scenarios:
        model = scenario.model
        truths = transfer_probabilities(model)
        for repetition in range(actual_repetitions):
            for target in TARGET_IDS:
                validation_rng = np.random.default_rng(
                    stable_seed(config.seed, scenario.id, repetition, target, "validation")
                )
                successes = int(validation_rng.binomial(actual_validation, truths[target]))
                rate = successes / actual_validation
                validation_rows.append(
                    {
                        "experiment_id": config.id,
                        "scenario": scenario.id,
                        "repetition": repetition,
                        "target": target,
                        "truth": truths[target],
                        "validation_episodes": actual_validation,
                        "successes": successes,
                        "validation_rate": rate,
                        "validation_signed_error": rate - truths[target],
                        "validation_absolute_error": abs(rate - truths[target]),
                    }
                )

        for policy in policies:
            trace_observed = _has_trace(policy)
            identification = diagnose_transfer_targets(policy)
            transfer_statuses = {
                identification[target].status
                for target in (TARGET_SPLIT, TARGET_ADD)
            }
            transfer_status = (
                PROVED_IDENTIFIABLE
                if transfer_statuses == {PROVED_IDENTIFIABLE}
                else sorted(transfer_statuses)[0]
            )
            parameter_status = identification[TARGET_SPLIT].status
            for target in TARGET_IDS:
                diagnostic = identification[target]
                identification_rows.append(
                    {
                        "experiment_id": config.id,
                        "scenario": scenario.id,
                        "observation_mode": policy.id,
                        "target": target,
                        "status": diagnostic.status,
                        "certificate": diagnostic.certificate,
                    }
                )
            for witness in ambiguity_witnesses(model, policy):
                witness_rows.append(
                    {
                        "experiment_id": config.id,
                        "scenario": scenario.id,
                        "observation_mode": policy.id,
                        "target": witness.target,
                        "first_parameters": json.dumps(
                            witness.first_probabilities,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "second_parameters": json.dumps(
                            witness.second_probabilities,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        "first_target": witness.first_target,
                        "second_target": witness.second_target,
                        "absolute_target_change": abs(
                            witness.first_target - witness.second_target
                        ),
                        "max_supported_observable_difference": (
                            witness.max_observable_difference
                        ),
                    }
                )
            for repetition in range(actual_repetitions):
                batch = simulate_batch(
                    model,
                    max_size,
                    policy,
                    np.random.default_rng(stable_seed(config.seed, scenario.id, repetition, "values")),
                    np.random.default_rng(
                        stable_seed(config.seed, scenario.id, repetition, policy.id, "mask")
                    ),
                )
                warm_start: np.ndarray | None = None
                for sample_size in actual_sizes:
                    prefix = batch.prefix(sample_size)
                    base = {
                        "experiment_id": config.id,
                        "scenario": scenario.id,
                        "observation_mode": policy.id,
                        "repetition": repetition,
                        "sample_size": sample_size,
                    }
                    table = compress_observed_patterns(model, prefix)
                    raw_patterns = _pattern_rows(base, model, table)
                    pattern_rows.extend(raw_patterns)

                    exact_start = time.perf_counter()
                    exact_fit = fit_exact_observed_likelihood(
                        model,
                        table,
                        initial_probabilities=warm_start,
                    )
                    exact_seconds = time.perf_counter() - exact_start
                    if exact_fit.converged and exact_fit.probabilities is not None:
                        warm_start = exact_fit.probabilities
                    raw_exact_parameters = (
                        dict(zip(model.factor_ids, exact_fit.probabilities, strict=True))
                        if exact_fit.converged
                        and exact_fit.probabilities is not None
                        else None
                    )

                    b2_start = time.perf_counter()
                    b2_fit = fit_available_domain_moments(
                        model,
                        prefix,
                        config.min_observations,
                    )
                    b2_seconds = time.perf_counter() - b2_start
                    marginals = health_marginals(model, prefix, config.min_observations)
                    direct = direct_current_rate(model, prefix, config.min_observations)
                    empirical = empirical_joint_current_rate(
                        model,
                        prefix,
                        config.min_observations,
                    )

                    method_predictions: dict[str, dict[str, float | None]] = {}
                    method_predictions[METHOD_B0] = {
                        target: direct for target in TARGET_IDS
                    }
                    method_predictions[METHOD_B1] = (
                        {target: None for target in TARGET_IDS}
                        if marginals is None
                        else independent_predictions(marginals)
                    )
                    method_predictions[METHOD_B2] = (
                        {target: None for target in TARGET_IDS}
                        if b2_fit.probabilities is None
                        else transfer_probabilities(model, b2_fit.probabilities)
                    )
                    exact_predictions = (
                        transfer_probabilities(model, raw_exact_parameters)
                        if raw_exact_parameters is not None
                        else {target: None for target in TARGET_IDS}
                    )
                    method_predictions[METHOD_B3] = exact_predictions.copy()
                    method_predictions[METHOD_PROPOSED] = {
                        target: (
                            exact_predictions[target]
                            if identification[target].status == PROVED_IDENTIFIABLE
                            else None
                        )
                        for target in TARGET_IDS
                    }
                    method_predictions[METHOD_B4] = {
                        TARGET_CURRENT: empirical,
                        TARGET_SPLIT: None,
                        TARGET_ADD: None,
                    }

                    fit_rows.extend(
                        (
                            _fit_row(
                                base=base,
                                method=METHOD_B0,
                                status="complete" if direct is not None else "unavailable",
                                converged=direct is not None,
                                parameter_identifiability_status=parameter_status,
                                transfer_identifiable=False,
                                runtime_seconds=0.0,
                                estimation_source="direct_current_trace",
                            ),
                            _fit_row(
                                base=base,
                                method=METHOD_B1,
                                status="complete" if marginals is not None else "unavailable",
                                converged=marginals is not None,
                                parameter_identifiability_status=parameter_status,
                                transfer_identifiable=False,
                                runtime_seconds=0.0,
                                estimation_source="health_marginals_independence_assumption",
                            ),
                            _fit_row(
                                base=base,
                                method=METHOD_B2,
                                status=b2_fit.status,
                                converged=b2_fit.probabilities is not None,
                                parameter_identifiability_status=parameter_status,
                                transfer_identifiable=(
                                    b2_fit.probabilities is not None
                                    and transfer_status == PROVED_IDENTIFIABLE
                                ),
                                runtime_seconds=b2_seconds,
                                estimation_source=b2_fit.source,
                            ),
                            _fit_row(
                                base=base,
                                method=METHOD_B3,
                                status=exact_fit.status,
                                converged=exact_fit.converged,
                                parameter_identifiability_status=parameter_status,
                                transfer_identifiable=(
                                    transfer_status == PROVED_IDENTIFIABLE
                                ),
                                runtime_seconds=exact_seconds,
                                estimation_source="raw_exact_likelihood_point",
                                negative_log_likelihood=exact_fit.negative_log_likelihood,
                                iterations=exact_fit.iterations,
                                boundary_parameter_count=exact_fit.boundary_parameter_count,
                                near_optimal_parameter_spread=exact_fit.near_optimal_parameter_spread,
                                shared_fit_with=METHOD_PROPOSED,
                            ),
                            _fit_row(
                                base=base,
                                method=METHOD_PROPOSED,
                                status=exact_fit.status,
                                converged=exact_fit.converged,
                                parameter_identifiability_status=parameter_status,
                                transfer_identifiable=(
                                    transfer_status == PROVED_IDENTIFIABLE
                                ),
                                runtime_seconds=exact_seconds,
                                estimation_source="exact_likelihood_with_structural_gate",
                                negative_log_likelihood=exact_fit.negative_log_likelihood,
                                iterations=exact_fit.iterations,
                                boundary_parameter_count=exact_fit.boundary_parameter_count,
                                near_optimal_parameter_spread=exact_fit.near_optimal_parameter_spread,
                                shared_fit_with=METHOD_B3,
                            ),
                            _fit_row(
                                base=base,
                                method=METHOD_B4,
                                status="complete" if empirical is not None else "unavailable",
                                converged=empirical is not None,
                                parameter_identifiability_status=parameter_status,
                                transfer_identifiable=False,
                                runtime_seconds=0.0,
                                estimation_source="empirical_joint_health_distribution",
                            ),
                        )
                    )

                    _append_parameters(
                        parameter_rows,
                        base,
                        METHOD_B2,
                        model,
                        b2_fit.probabilities,
                        parameter_status,
                    )
                    _append_parameters(
                        parameter_rows,
                        base,
                        METHOD_B3,
                        model,
                        raw_exact_parameters,
                        parameter_status,
                    )
                    _append_parameters(
                        parameter_rows,
                        base,
                        METHOD_PROPOSED,
                        model,
                        (
                            raw_exact_parameters
                            if parameter_status == PROVED_IDENTIFIABLE
                            else None
                        ),
                        parameter_status,
                    )

                    rules = {
                        METHOD_B0: "carry_forward_current_endpoint_rate",
                        METHOD_B1: "independent_replica_marginals",
                        METHOD_B2: "available_domain_moments",
                        METHOD_B3: "raw_exact_likelihood_point",
                        METHOD_PROPOSED: "exact_likelihood_with_structural_gate",
                        METHOD_B4: "empirical_joint_current_only",
                    }
                    for method in METHODS:
                        _append_predictions(
                            prediction_rows,
                            base,
                            method,
                            truths,
                            method_predictions[method],
                            rules[method],
                            trace_observed,
                            identification,
                        )
                        decision_rows.append(
                            _decision_row(
                                base,
                                method,
                                truths,
                                method_predictions[method],
                                transfer_status,
                            )
                        )

    change_rows = build_change_rows(prediction_rows)
    prediction_summary = summarize_predictions(prediction_rows)
    decision_summary = summarize_decisions(decision_rows)
    parameter_summary = summarize_parameters(parameter_rows)
    change_summary = summarize_changes(change_rows)
    contrasts = paired_contrasts(prediction_rows)
    change_contrasts = paired_contrasts(change_rows)
    quality = quality_metrics(prediction_rows, decision_rows, witness_rows)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "fits.csv", FIT_FIELDS, fit_rows)
    _write_csv(output / "parameters.csv", PARAMETER_FIELDS, parameter_rows)
    _write_csv(output / "predictions.csv", PREDICTION_FIELDS, prediction_rows)
    _write_csv(output / "decisions.csv", DECISION_FIELDS, decision_rows)
    _write_csv(output / "validation.csv", VALIDATION_FIELDS, validation_rows)
    _write_csv(output / "patterns.csv", PATTERN_FIELDS, pattern_rows)
    _write_csv(output / "changes.csv", CHANGE_FIELDS, change_rows)
    _write_csv(
        output / "identification.csv",
        IDENTIFICATION_FIELDS,
        identification_rows,
    )
    _write_csv(output / "witnesses.csv", WITNESS_FIELDS, witness_rows)
    _write_csv(
        output / "prediction_summary.csv",
        PREDICTION_SUMMARY_FIELDS,
        prediction_summary,
    )
    _write_csv(output / "decision_summary.csv", DECISION_SUMMARY_FIELDS, decision_summary)
    _write_csv(
        output / "parameter_summary.csv",
        PARAMETER_SUMMARY_FIELDS,
        parameter_summary,
    )
    _write_csv(output / "contrasts.csv", CONTRAST_FIELDS, contrasts)
    _write_csv(
        output / "change_summary.csv",
        CHANGE_SUMMARY_FIELDS,
        change_summary,
    )
    _write_csv(
        output / "change_contrasts.csv",
        CHANGE_CONTRAST_FIELDS,
        change_contrasts,
    )

    manifest = {
        "schema_version": 1,
        "kind": "transfer_experiment_shard",
        "experiment_id": config.id,
        "config_sha256": file_sha256(config_path),
        "seed": config.seed,
        "scenarios": [scenario.id for scenario in scenarios],
        "observation_modes": [policy.id for policy in policies],
        "repetitions": actual_repetitions,
        "sample_sizes": list(actual_sizes),
        "validation_episodes": actual_validation,
        "methods": list(METHODS),
        "quality": quality,
        "row_counts": {
            "fits": len(fit_rows),
            "parameters": len(parameter_rows),
            "predictions": len(prediction_rows),
            "decisions": len(decision_rows),
            "validation": len(validation_rows),
            "patterns": len(pattern_rows),
            "changes": len(change_rows),
            "identification": len(identification_rows),
            "witnesses": len(witness_rows),
            "prediction_summary": len(prediction_summary),
            "decision_summary": len(decision_summary),
            "parameter_summary": len(parameter_summary),
            "contrasts": len(contrasts),
            "change_summary": len(change_summary),
            "change_contrasts": len(change_contrasts),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _read_csvs(paths: Iterable[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as source:
            rows.extend(csv.DictReader(source))
    return rows


def aggregate_transfer_experiment(
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    raw_names = (
        "fits",
        "parameters",
        "predictions",
        "decisions",
        "validation",
        "patterns",
        "changes",
        "identification",
        "witnesses",
    )
    paths = {name: sorted(root.rglob(f"{name}.csv")) for name in raw_names}
    if any(not values for values in paths.values()):
        raise ValueError("input root does not contain complete transfer shards")
    tables = {name: _read_csvs(values) for name, values in paths.items()}
    prediction_summary = summarize_predictions(tables["predictions"])
    decision_summary = summarize_decisions(tables["decisions"])
    parameter_summary = summarize_parameters(tables["parameters"])
    change_summary = summarize_changes(tables["changes"])
    contrasts = paired_contrasts(tables["predictions"])
    change_contrasts = paired_contrasts(tables["changes"])
    quality = quality_metrics(
        tables["predictions"],
        tables["decisions"],
        tables["witnesses"],
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    fields = {
        "fits": FIT_FIELDS,
        "parameters": PARAMETER_FIELDS,
        "predictions": PREDICTION_FIELDS,
        "decisions": DECISION_FIELDS,
        "validation": VALIDATION_FIELDS,
        "patterns": PATTERN_FIELDS,
        "changes": CHANGE_FIELDS,
        "identification": IDENTIFICATION_FIELDS,
        "witnesses": WITNESS_FIELDS,
    }
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", fields[name], rows)
    _write_csv(
        output / "prediction_summary.csv",
        PREDICTION_SUMMARY_FIELDS,
        prediction_summary,
    )
    _write_csv(output / "decision_summary.csv", DECISION_SUMMARY_FIELDS, decision_summary)
    _write_csv(
        output / "parameter_summary.csv",
        PARAMETER_SUMMARY_FIELDS,
        parameter_summary,
    )
    _write_csv(output / "contrasts.csv", CONTRAST_FIELDS, contrasts)
    _write_csv(
        output / "change_summary.csv",
        CHANGE_SUMMARY_FIELDS,
        change_summary,
    )
    _write_csv(
        output / "change_contrasts.csv",
        CHANGE_CONTRAST_FIELDS,
        change_contrasts,
    )
    manifest = {
        "schema_version": 1,
        "kind": "transfer_experiment_aggregate",
        "experiment_id": tables["fits"][0]["experiment_id"],
        "source_shards": len(paths["fits"]),
        "methods": list(METHODS),
        "quality": quality,
        "row_counts": {
            **{name: len(rows) for name, rows in tables.items()},
            "prediction_summary": len(prediction_summary),
            "decision_summary": len(decision_summary),
            "parameter_summary": len(parameter_summary),
            "contrasts": len(contrasts),
            "change_summary": len(change_summary),
            "change_contrasts": len(change_contrasts),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
