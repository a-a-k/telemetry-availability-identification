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

from .config import ExperimentConfig
from .diagnostics import diagnose_identifiability
from .estimators import fit_log_moments
from .likelihood import (
    ObservedPatternTable,
    compress_observed_patterns,
    exact_target_probability,
    fit_exact_observed_likelihood,
    negative_log_likelihood,
)
from .moments import (
    canonical_moment_estimates,
    estimate_moments,
    moment_matrix,
    structural_moment_rows,
)
from .observation import ObservationPolicy, simulate_batch
from .provenance import environment_manifest, file_sha256
from .runner import _selected, _write_csv, stable_seed


REFERENCE_EXPERIMENT_ID = "rq1_exact_observed_likelihood_reference"
METHOD_MOMENT = "b2_log_moment"
METHOD_LIKELIHOOD = "b3_exact_likelihood"

FIT_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "structural_rank",
    "empirical_rank",
    "parameter_count",
    "status",
    "converged",
    "runtime_seconds",
    "negative_log_likelihood",
    "truth_negative_log_likelihood",
    "nll_gap_to_truth",
    "iterations",
    "gradient_infinity_norm",
    "boundary_parameter_count",
    "successful_starts",
    "attempted_starts",
    "near_optimal_parameter_spread",
    "objective_spread",
    "optimizer_message",
)

ESTIMATE_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "object_kind",
    "object_id",
    "role",
    "truth",
    "structurally_identifiable",
    "empirically_identifiable",
    "estimate",
    "signed_error",
    "absolute_error",
    "false_confident_estimate",
)

PATTERN_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "pattern_id",
    "observed_ids",
    "observed_values",
    "count",
)

SUMMARY_FIELDS = (
    "family",
    "observation_mode",
    "sample_size",
    "method",
    "datasets",
    "structural_rank",
    "parameter_count",
    "convergence_rate",
    "nonunique_fit_rate",
    "boundary_fit_rate",
    "mean_runtime_seconds",
    "median_runtime_seconds",
    "parameter_estimate_rate",
    "parameter_mae",
    "parameter_signed_bias",
    "false_confident_parameter_rate",
    "target_estimate_rate",
    "target_mae",
    "target_signed_bias",
    "mean_nll_gap_to_truth",
)

PAIRED_FIELDS = (
    "family",
    "observation_mode",
    "sample_size",
    "parameter_campaign_pairs",
    "parameter_mean_mae_delta_b3_minus_b2",
    "parameter_median_mae_delta_b3_minus_b2",
    "parameter_b3_win_rate",
    "target_campaign_pairs",
    "target_mean_mae_delta_b3_minus_b2",
    "target_median_mae_delta_b3_minus_b2",
    "target_b3_win_rate",
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
    available = [float(value) for value in values if value is not None]
    return float(statistics.fmean(available)) if available else None


def _median(values: Iterable[float | None]) -> float | None:
    available = [float(value) for value in values if value is not None]
    return float(statistics.median(available)) if available else None


def _target_from_probabilities(
    model: Any,
    factor_ids: tuple[str, ...],
    probabilities: np.ndarray,
) -> float:
    index = {factor_id: position for position, factor_id in enumerate(model.factor_ids)}
    return float(np.prod([probabilities[index[factor_id]] for factor_id in factor_ids]))


def _pattern_rows(
    base: dict[str, Any],
    model: Any,
    table: ObservedPatternTable,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pattern_id, (mask, values, count) in enumerate(
        zip(table.masks, table.values, table.counts, strict=True)
    ):
        observed_ids = [
            observable.id
            for observable, is_observed in zip(model.observables, mask, strict=True)
            if is_observed
        ]
        observed_values = [
            f"{observable.id}={int(value)}"
            for observable, is_observed, value in zip(
                model.observables,
                mask,
                values,
                strict=True,
            )
            if is_observed
        ]
        rows.append(
            {
                **base,
                "pattern_id": pattern_id,
                "observed_ids": "&".join(observed_ids),
                "observed_values": "&".join(observed_values),
                "count": int(count),
            }
        )
    return rows


def summarize_reference(
    fits: list[dict[str, Any]],
    estimates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fit_groups: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    estimate_groups: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)

    def key(row: dict[str, Any]) -> tuple[str, str, int, str]:
        return (
            str(row["family"]),
            str(row["observation_mode"]),
            int(row["sample_size"]),
            str(row["method"]),
        )

    for row in fits:
        fit_groups[key(row)].append(row)
    for row in estimates:
        estimate_groups[key(row)].append(row)

    rows: list[dict[str, Any]] = []
    for group_key in sorted(fit_groups):
        fit_group = fit_groups[group_key]
        estimate_group = estimate_groups[group_key]
        parameters = [row for row in estimate_group if row["object_kind"] == "parameter"]
        targets = [row for row in estimate_group if row["object_kind"] == "target"]
        identifiable_parameters = [
            row for row in parameters if _as_bool(row["structurally_identifiable"])
        ]
        parameter_estimates = [
            row for row in identifiable_parameters if _optional_float(row["estimate"]) is not None
        ]
        target_estimates = [row for row in targets if _optional_float(row["estimate"]) is not None]
        unidentifiable_parameters = [
            row for row in parameters if not _as_bool(row["structurally_identifiable"])
        ]
        false_confident = sum(
            _as_bool(row["false_confident_estimate"]) for row in unidentifiable_parameters
        )
        rows.append(
            {
                "family": group_key[0],
                "observation_mode": group_key[1],
                "sample_size": group_key[2],
                "method": group_key[3],
                "datasets": len(fit_group),
                "structural_rank": int(fit_group[0]["structural_rank"]),
                "parameter_count": int(fit_group[0]["parameter_count"]),
                "convergence_rate": _mean(float(_as_bool(row["converged"])) for row in fit_group),
                "nonunique_fit_rate": _mean(
                    float(str(row["status"]) == "converged_nonunique") for row in fit_group
                ),
                "boundary_fit_rate": _mean(
                    float(int(row["boundary_parameter_count"] or 0) > 0) for row in fit_group
                ),
                "mean_runtime_seconds": _mean(float(row["runtime_seconds"]) for row in fit_group),
                "median_runtime_seconds": _median(float(row["runtime_seconds"]) for row in fit_group),
                "parameter_estimate_rate": (
                    len(parameter_estimates) / len(identifiable_parameters)
                    if identifiable_parameters
                    else None
                ),
                "parameter_mae": _mean(
                    _optional_float(row["absolute_error"]) for row in parameter_estimates
                ),
                "parameter_signed_bias": _mean(
                    _optional_float(row["signed_error"]) for row in parameter_estimates
                ),
                "false_confident_parameter_rate": (
                    false_confident / len(unidentifiable_parameters)
                    if unidentifiable_parameters
                    else 0.0
                ),
                "target_estimate_rate": len(target_estimates) / len(targets) if targets else None,
                "target_mae": _mean(
                    _optional_float(row["absolute_error"]) for row in target_estimates
                ),
                "target_signed_bias": _mean(
                    _optional_float(row["signed_error"]) for row in target_estimates
                ),
                "mean_nll_gap_to_truth": _mean(
                    _optional_float(row["nll_gap_to_truth"]) for row in fit_group
                ),
            }
        )
    return rows


def paired_summary(estimates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in estimates:
        grouped[(str(row["family"]), str(row["observation_mode"]), int(row["sample_size"]))].append(row)

    output: list[dict[str, Any]] = []
    for group_key in sorted(grouped):
        rows = grouped[group_key]
        deltas: dict[str, list[float]] = {"parameter": [], "target": []}
        repetitions = sorted({int(row["repetition"]) for row in rows})
        for repetition in repetitions:
            repetition_rows = [row for row in rows if int(row["repetition"]) == repetition]
            for object_kind in ("parameter", "target"):
                relevant = [
                    row
                    for row in repetition_rows
                    if row["object_kind"] == object_kind
                    and _as_bool(row["structurally_identifiable"])
                ]
                object_ids = sorted({str(row["object_id"]) for row in relevant})
                if not object_ids:
                    continue
                method_errors: dict[str, list[float]] = {}
                for method in (METHOD_MOMENT, METHOD_LIKELIHOOD):
                    by_id = {
                        str(row["object_id"]): _optional_float(row["absolute_error"])
                        for row in relevant
                        if row["method"] == method
                    }
                    if set(by_id) != set(object_ids) or any(value is None for value in by_id.values()):
                        break
                    method_errors[method] = [float(by_id[object_id]) for object_id in object_ids]
                if len(method_errors) == 2:
                    deltas[object_kind].append(
                        statistics.fmean(method_errors[METHOD_LIKELIHOOD])
                        - statistics.fmean(method_errors[METHOD_MOMENT])
                    )

        def win_rate(values: list[float]) -> float | None:
            return statistics.fmean(float(value < 0.0) for value in values) if values else None

        output.append(
            {
                "family": group_key[0],
                "observation_mode": group_key[1],
                "sample_size": group_key[2],
                "parameter_campaign_pairs": len(deltas["parameter"]),
                "parameter_mean_mae_delta_b3_minus_b2": _mean(deltas["parameter"]),
                "parameter_median_mae_delta_b3_minus_b2": _median(deltas["parameter"]),
                "parameter_b3_win_rate": win_rate(deltas["parameter"]),
                "target_campaign_pairs": len(deltas["target"]),
                "target_mean_mae_delta_b3_minus_b2": _mean(deltas["target"]),
                "target_median_mae_delta_b3_minus_b2": _median(deltas["target"]),
                "target_b3_win_rate": win_rate(deltas["target"]),
            }
        )
    return output


def run_likelihood_reference(
    config: ExperimentConfig,
    config_path: str | Path,
    output_directory: str | Path,
    family_names: tuple[str, ...] | None = None,
    mode_names: tuple[str, ...] | None = None,
    repetitions: int | None = None,
    sample_sizes: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    families = _selected(config.families, family_names, "families")
    policies: tuple[ObservationPolicy, ...] = _selected(
        config.observation_modes,
        mode_names,
        "observation modes",
    )
    actual_repetitions = config.repetitions if repetitions is None else repetitions
    actual_sizes = config.sample_sizes if sample_sizes is None else sample_sizes
    if actual_repetitions <= 0:
        raise ValueError("repetitions must be positive")
    if not actual_sizes or any(value <= 0 for value in actual_sizes):
        raise ValueError("sample sizes must be positive")
    if tuple(sorted(set(actual_sizes))) != actual_sizes:
        raise ValueError("sample sizes must be strictly increasing")

    dataset_fits = len(families) * len(policies) * actual_repetitions * len(actual_sizes)
    if (
        os.environ.get("GITHUB_ACTIONS", "").lower() != "true"
        and dataset_fits > config.local_smoke_max_dataset_fits
    ):
        raise RuntimeError(
            "likelihood reference exceeds the local smoke budget "
            f"({dataset_fits} > {config.local_smoke_max_dataset_fits} datasets); "
            "run it through the GitHub Actions experiment workflow"
        )

    fit_rows: list[dict[str, Any]] = []
    estimate_rows: list[dict[str, Any]] = []
    pattern_rows: list[dict[str, Any]] = []
    max_size = max(actual_sizes)

    for family in families:
        for policy in policies:
            structural = diagnose_identifiability(
                family,
                structural_moment_rows(family, policy, config.max_moment_order),
            )
            for repetition in range(actual_repetitions):
                batch = simulate_batch(
                    model=family,
                    episode_count=max_size,
                    policy=policy,
                    value_rng=np.random.default_rng(
                        stable_seed(config.seed, family.id, repetition, "values")
                    ),
                    mask_rng=np.random.default_rng(
                        stable_seed(config.seed, family.id, repetition, policy.id, "mask")
                    ),
                )
                warm_start: np.ndarray | None = None
                for sample_size in actual_sizes:
                    prefix = batch.prefix(sample_size)
                    base = {
                        "experiment_id": REFERENCE_EXPERIMENT_ID,
                        "family": family.id,
                        "observation_mode": policy.id,
                        "repetition": repetition,
                        "sample_size": sample_size,
                    }
                    table = compress_observed_patterns(family, prefix)
                    pattern_rows.extend(_pattern_rows(base, family, table))
                    truth_nll = negative_log_likelihood(family.factor_probabilities, table)

                    moment_start = time.perf_counter()
                    moments = canonical_moment_estimates(
                        estimate_moments(
                            family,
                            prefix,
                            config.max_moment_order,
                            config.min_joint_observations,
                        )
                    )
                    positive = tuple(moment for moment in moments if moment.value > 0.0)
                    moment_report = diagnose_identifiability(
                        family,
                        moment_matrix(positive, len(family.factors)),
                    )
                    moment_fit = fit_log_moments(family, moments, moment_report)
                    moment_runtime = time.perf_counter() - moment_start
                    moment_vector = [moment_fit.parameter_estimates[name] for name in family.factor_ids]
                    moment_nll: float | None = None
                    if all(value is not None for value in moment_vector):
                        clipped = np.clip(np.asarray(moment_vector, dtype=float), 1e-6, 1.0 - 1e-6)
                        moment_nll = negative_log_likelihood(clipped, table)
                    fit_rows.append(
                        {
                            **base,
                            "method": METHOD_MOMENT,
                            "structural_rank": structural.rank,
                            "empirical_rank": moment_report.rank,
                            "parameter_count": len(family.factors),
                            "status": moment_fit.status,
                            "converged": moment_fit.status != "no_positive_moments",
                            "runtime_seconds": moment_runtime,
                            "negative_log_likelihood": moment_nll,
                            "truth_negative_log_likelihood": truth_nll,
                            "nll_gap_to_truth": None if moment_nll is None else moment_nll - truth_nll,
                            "iterations": 0,
                            "gradient_infinity_norm": None,
                            "boundary_parameter_count": sum(value == 1.0 for value in moment_vector),
                            "successful_starts": 0,
                            "attempted_starts": 0,
                            "near_optimal_parameter_spread": None,
                            "objective_spread": None,
                            "optimizer_message": "closed-form weighted least squares in log moments",
                        }
                    )

                    likelihood_support = canonical_moment_estimates(
                        estimate_moments(
                            family,
                            prefix,
                            config.max_moment_order,
                            min_observations=1,
                        )
                    )
                    likelihood_report = diagnose_identifiability(
                        family,
                        moment_matrix(likelihood_support, len(family.factors)),
                    )
                    likelihood_start = time.perf_counter()
                    likelihood_fit = fit_exact_observed_likelihood(
                        family,
                        table,
                        initial_probabilities=warm_start,
                    )
                    likelihood_runtime = time.perf_counter() - likelihood_start
                    if likelihood_fit.converged and likelihood_fit.probabilities is not None:
                        warm_start = likelihood_fit.probabilities
                    fit_rows.append(
                        {
                            **base,
                            "method": METHOD_LIKELIHOOD,
                            "structural_rank": structural.rank,
                            "empirical_rank": likelihood_report.rank,
                            "parameter_count": len(family.factors),
                            "status": likelihood_fit.status,
                            "converged": likelihood_fit.converged,
                            "runtime_seconds": likelihood_runtime,
                            "negative_log_likelihood": likelihood_fit.negative_log_likelihood,
                            "truth_negative_log_likelihood": truth_nll,
                            "nll_gap_to_truth": (
                                None
                                if likelihood_fit.negative_log_likelihood is None
                                else likelihood_fit.negative_log_likelihood - truth_nll
                            ),
                            "iterations": likelihood_fit.iterations,
                            "gradient_infinity_norm": likelihood_fit.gradient_infinity_norm,
                            "boundary_parameter_count": likelihood_fit.boundary_parameter_count,
                            "successful_starts": likelihood_fit.successful_starts,
                            "attempted_starts": likelihood_fit.attempted_starts,
                            "near_optimal_parameter_spread": likelihood_fit.near_optimal_parameter_spread,
                            "objective_spread": likelihood_fit.objective_spread,
                            "optimizer_message": likelihood_fit.message,
                        }
                    )

                    for method, report, probabilities in (
                        (METHOD_MOMENT, moment_report, None),
                        (METHOD_LIKELIHOOD, likelihood_report, likelihood_fit.probabilities),
                    ):
                        for factor_index, factor in enumerate(family.factors):
                            if method == METHOD_MOMENT:
                                estimate = moment_fit.parameter_estimates[factor.id]
                            else:
                                estimate = (
                                    float(probabilities[factor_index])
                                    if likelihood_fit.converged
                                    and probabilities is not None
                                    and report.parameter_identifiable[factor.id]
                                    else None
                                )
                            signed_error = None if estimate is None else estimate - factor.probability
                            estimate_rows.append(
                                {
                                    **base,
                                    "method": method,
                                    "object_kind": "parameter",
                                    "object_id": factor.id,
                                    "role": factor.role,
                                    "truth": factor.probability,
                                    "structurally_identifiable": structural.parameter_identifiable[factor.id],
                                    "empirically_identifiable": report.parameter_identifiable[factor.id],
                                    "estimate": estimate,
                                    "signed_error": signed_error,
                                    "absolute_error": None if signed_error is None else abs(signed_error),
                                    "false_confident_estimate": (
                                        estimate is not None
                                        and not structural.parameter_identifiable[factor.id]
                                    ),
                                }
                            )

                        for target in family.targets:
                            truth = exact_target_probability(family, target.factors)
                            if method == METHOD_MOMENT:
                                estimate = moment_fit.target_estimates[target.id]
                            else:
                                estimate = (
                                    _target_from_probabilities(family, target.factors, probabilities)
                                    if likelihood_fit.converged
                                    and probabilities is not None
                                    and report.target_identifiable[target.id]
                                    else None
                                )
                            signed_error = None if estimate is None else estimate - truth
                            estimate_rows.append(
                                {
                                    **base,
                                    "method": method,
                                    "object_kind": "target",
                                    "object_id": target.id,
                                    "role": "availability_target",
                                    "truth": truth,
                                    "structurally_identifiable": structural.target_identifiable[target.id],
                                    "empirically_identifiable": report.target_identifiable[target.id],
                                    "estimate": estimate,
                                    "signed_error": signed_error,
                                    "absolute_error": None if signed_error is None else abs(signed_error),
                                    "false_confident_estimate": False,
                                }
                            )

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    summary_rows = summarize_reference(fit_rows, estimate_rows)
    paired_rows = paired_summary(estimate_rows)
    _write_csv(output / "reference_fits.csv", FIT_FIELDS, fit_rows)
    _write_csv(output / "reference_estimates.csv", ESTIMATE_FIELDS, estimate_rows)
    _write_csv(output / "patterns.csv", PATTERN_FIELDS, pattern_rows)
    _write_csv(output / "reference_summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(output / "paired_summary.csv", PAIRED_FIELDS, paired_rows)

    manifest = {
        "schema_version": 1,
        "kind": "likelihood_reference_shard",
        "experiment_id": REFERENCE_EXPERIMENT_ID,
        "config_sha256": file_sha256(config_path),
        "seed": config.seed,
        "families": [item.id for item in families],
        "observation_modes": [item.id for item in policies],
        "repetitions": actual_repetitions,
        "sample_sizes": list(actual_sizes),
        "methods": [METHOD_MOMENT, METHOD_LIKELIHOOD],
        "row_counts": {
            "fits": len(fit_rows),
            "estimates": len(estimate_rows),
            "patterns": len(pattern_rows),
            "summary": len(summary_rows),
            "paired_summary": len(paired_rows),
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


def aggregate_likelihood_reference(
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    fit_paths = sorted(root.rglob("reference_fits.csv"))
    estimate_paths = sorted(root.rglob("reference_estimates.csv"))
    pattern_paths = sorted(root.rglob("patterns.csv"))
    if not fit_paths or not estimate_paths or not pattern_paths:
        raise ValueError("input root does not contain complete likelihood-reference shards")

    fits = _read_csvs(fit_paths)
    estimates = _read_csvs(estimate_paths)
    patterns = _read_csvs(pattern_paths)
    summaries = summarize_reference(fits, estimates)
    paired = paired_summary(estimates)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "reference_fits.csv", FIT_FIELDS, fits)
    _write_csv(output / "reference_estimates.csv", ESTIMATE_FIELDS, estimates)
    _write_csv(output / "patterns.csv", PATTERN_FIELDS, patterns)
    _write_csv(output / "reference_summary.csv", SUMMARY_FIELDS, summaries)
    _write_csv(output / "paired_summary.csv", PAIRED_FIELDS, paired)

    manifest = {
        "schema_version": 1,
        "kind": "likelihood_reference_aggregate",
        "experiment_id": REFERENCE_EXPERIMENT_ID,
        "source_shards": len(fit_paths),
        "methods": [METHOD_MOMENT, METHOD_LIKELIHOOD],
        "row_counts": {
            "fits": len(fits),
            "estimates": len(estimates),
            "patterns": len(patterns),
            "summary": len(summaries),
            "paired_summary": len(paired),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
