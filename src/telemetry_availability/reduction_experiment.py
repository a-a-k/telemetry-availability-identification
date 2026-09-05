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

from .compiler import (
    CompiledObservationModel,
    IdentificationStatus,
    compile_observation_model,
)
from .config import ExperimentConfig
from .diagnostics import diagnose_identifiability
from .likelihood import (
    ExactLikelihoodFit,
    compress_observed_patterns,
    exact_target_probability,
    fit_exact_observed_likelihood,
    negative_log_likelihood,
)
from .likelihood_reference import _pattern_rows
from .moments import canonical_moment_estimates, estimate_moments, moment_matrix
from .observation import ObservationPolicy, simulate_batch
from .provenance import environment_manifest, file_sha256
from .runner import _selected, _write_csv, stable_seed


EXPERIMENT_ID = "m2_structure_preserving_likelihood_reduction"
METHOD_REFERENCE = "b3_exact_likelihood"
METHOD_PROPOSED = "proposed_reduced_likelihood"

COMPILER_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "compile_seconds",
    "original_parameter_count",
    "reduced_parameter_count",
    "inactive_factor_count",
    "inactive_factors",
    "factor_groups_json",
    "original_state_count",
    "reduced_state_count",
    "state_space_reduction",
    "original_rank",
    "reduced_rank",
    "parameter_status_json",
    "target_status_json",
)

WITNESS_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "object_kind",
    "object_id",
    "status",
    "first_probabilities_json",
    "second_probabilities_json",
    "first_quantity",
    "second_quantity",
    "quantity_difference",
    "max_observable_moment_difference",
)

FIT_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "parameter_dimension",
    "state_count",
    "empirical_rank",
    "status",
    "converged",
    "runtime_seconds",
    "negative_log_likelihood",
    "truth_negative_log_likelihood",
    "iterations",
    "gradient_infinity_norm",
    "boundary_parameter_count",
    "successful_starts",
    "attempted_starts",
    "near_optimal_parameter_spread",
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
    "members",
    "role",
    "truth",
    "identification_status",
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

PAIRED_FIT_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "b3_negative_log_likelihood",
    "proposed_negative_log_likelihood",
    "nll_delta_proposed_minus_b3",
    "absolute_nll_difference",
    "objective_equivalent",
    "b3_runtime_seconds",
    "proposed_runtime_seconds",
    "speedup_b3_over_proposed",
    "b3_state_count",
    "proposed_state_count",
)

SUMMARY_FIELDS = (
    "family",
    "observation_mode",
    "sample_size",
    "method",
    "datasets",
    "parameter_dimension",
    "state_count",
    "convergence_rate",
    "boundary_fit_rate",
    "nonunique_fit_rate",
    "mean_runtime_seconds",
    "median_runtime_seconds",
    "individual_estimate_rate",
    "individual_mae",
    "combination_estimate_rate",
    "combination_mae",
    "target_estimate_rate",
    "target_mae",
    "false_confident_estimate_rate",
)

PAIRED_SUMMARY_FIELDS = (
    "family",
    "observation_mode",
    "sample_size",
    "objective_pairs",
    "objective_equivalence_rate",
    "maximum_absolute_nll_difference",
    "median_speedup_b3_over_proposed",
    "individual_campaign_pairs",
    "individual_mean_mae_delta_proposed_minus_b3",
    "combination_campaign_pairs",
    "combination_mean_mae_delta_proposed_minus_b3",
    "target_campaign_pairs",
    "target_mean_mae_delta_proposed_minus_b3",
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


def _no_observation_fit() -> ExactLikelihoodFit:
    return ExactLikelihoodFit(
        status="no_observations",
        converged=False,
        probabilities=None,
        negative_log_likelihood=None,
        iterations=0,
        gradient_infinity_norm=None,
        boundary_parameter_count=0,
        successful_starts=0,
        attempted_starts=0,
        near_optimal_parameter_spread=None,
        objective_spread=None,
        message="no supported observable values",
    )


def _empirical_report(model: Any, batch: Any):
    rows = canonical_moment_estimates(
        estimate_moments(
            model,
            batch,
            max_order=len(model.observables),
            min_observations=1,
        )
    )
    return diagnose_identifiability(model, moment_matrix(rows, len(model.factors)))


def _compilation_row(
    family: Any,
    policy: ObservationPolicy,
    compiled: CompiledObservationModel,
    compile_seconds: float,
) -> dict[str, Any]:
    reduced_count = 0 if compiled.reduced_model is None else len(compiled.reduced_model.factors)
    return {
        "experiment_id": EXPERIMENT_ID,
        "family": family.id,
        "observation_mode": policy.id,
        "compile_seconds": compile_seconds,
        "original_parameter_count": len(family.factors),
        "reduced_parameter_count": reduced_count,
        "inactive_factor_count": len(compiled.inactive_factors),
        "inactive_factors": "&".join(compiled.inactive_factors),
        "factor_groups_json": json.dumps(
            {group.id: list(group.members) for group in compiled.factor_groups},
            sort_keys=True,
        ),
        "original_state_count": compiled.original_state_count,
        "reduced_state_count": compiled.reduced_state_count,
        "state_space_reduction": (
            None
            if compiled.reduced_state_count == 0
            else compiled.original_state_count / compiled.reduced_state_count
        ),
        "original_rank": compiled.original_report.rank,
        "reduced_rank": None if compiled.reduced_report is None else compiled.reduced_report.rank,
        "parameter_status_json": json.dumps(
            {name: str(status) for name, status in compiled.parameter_status.items()},
            sort_keys=True,
        ),
        "target_status_json": json.dumps(
            {name: str(status) for name, status in compiled.target_status.items()},
            sort_keys=True,
        ),
    }


def _witness_rows(compiled: CompiledObservationModel) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    factor_ids = compiled.original_model.factor_ids
    for object_kind, witnesses in (
        ("parameter", compiled.parameter_witnesses),
        ("target", compiled.target_witnesses),
    ):
        statuses = (
            compiled.parameter_status if object_kind == "parameter" else compiled.target_status
        )
        for object_id, witness in witnesses.items():
            result.append(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "family": compiled.original_model.id,
                    "observation_mode": compiled.policy.id,
                    "object_kind": object_kind,
                    "object_id": object_id,
                    "status": str(statuses[object_id]),
                    "first_probabilities_json": json.dumps(
                        dict(zip(factor_ids, witness.first_probabilities, strict=True)),
                        sort_keys=True,
                    ),
                    "second_probabilities_json": json.dumps(
                        dict(zip(factor_ids, witness.second_probabilities, strict=True)),
                        sort_keys=True,
                    ),
                    "first_quantity": witness.first_quantity,
                    "second_quantity": witness.second_quantity,
                    "quantity_difference": witness.second_quantity - witness.first_quantity,
                    "max_observable_moment_difference": witness.max_observable_moment_difference,
                }
            )
    return result


def _fit_row(
    base: dict[str, Any],
    method: str,
    fit: ExactLikelihoodFit,
    runtime_seconds: float,
    dimension: int,
    state_count: int,
    empirical_rank: int,
    truth_nll: float | None,
) -> dict[str, Any]:
    return {
        **base,
        "method": method,
        "parameter_dimension": dimension,
        "state_count": state_count,
        "empirical_rank": empirical_rank,
        "status": fit.status,
        "converged": fit.converged,
        "runtime_seconds": runtime_seconds,
        "negative_log_likelihood": fit.negative_log_likelihood,
        "truth_negative_log_likelihood": truth_nll,
        "iterations": fit.iterations,
        "gradient_infinity_norm": fit.gradient_infinity_norm,
        "boundary_parameter_count": fit.boundary_parameter_count,
        "successful_starts": fit.successful_starts,
        "attempted_starts": fit.attempted_starts,
        "near_optimal_parameter_spread": fit.near_optimal_parameter_spread,
    }


def _append_estimate(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    method: str,
    object_kind: str,
    object_id: str,
    members: tuple[str, ...],
    role: str,
    truth: float,
    status: IdentificationStatus,
    empirically_identifiable: bool,
    estimate: float | None,
) -> None:
    signed_error = None if estimate is None else estimate - truth
    rows.append(
        {
            **base,
            "method": method,
            "object_kind": object_kind,
            "object_id": object_id,
            "members": "&".join(members),
            "role": role,
            "truth": truth,
            "identification_status": str(status),
            "empirically_identifiable": empirically_identifiable,
            "estimate": estimate,
            "signed_error": signed_error,
            "absolute_error": None if signed_error is None else abs(signed_error),
            "false_confident_estimate": (
                estimate is not None and status != IdentificationStatus.PROVED_IDENTIFIABLE
            ),
        }
    )


def _add_estimates(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    compiled: CompiledObservationModel,
    original_report: Any,
    reduced_report: Any,
    reference_fit: ExactLikelihoodFit,
    proposed_fit: ExactLikelihoodFit,
) -> None:
    family = compiled.original_model
    factor_index = {factor_id: index for index, factor_id in enumerate(family.factor_ids)}
    group_index = (
        {}
        if compiled.reduced_model is None
        else {
            factor_id: index
            for index, factor_id in enumerate(compiled.reduced_model.factor_ids)
        }
    )

    for method, fit in (
        (METHOD_REFERENCE, reference_fit),
        (METHOD_PROPOSED, proposed_fit),
    ):
        for factor in family.factors:
            if method == METHOD_REFERENCE:
                empirical = original_report.parameter_identifiable[factor.id]
                estimate = (
                    float(fit.probabilities[factor_index[factor.id]])
                    if fit.converged and fit.probabilities is not None and empirical
                    else None
                )
            else:
                group = next(
                    (item for item in compiled.factor_groups if factor.id in item.members),
                    None,
                )
                empirical = bool(
                    group is not None
                    and len(group.members) == 1
                    and reduced_report is not None
                    and reduced_report.parameter_identifiable[group.id]
                )
                estimate = (
                    float(fit.probabilities[group_index[group.id]])
                    if fit.converged
                    and fit.probabilities is not None
                    and group is not None
                    and empirical
                    else None
                )
            _append_estimate(
                rows,
                base,
                method,
                "individual",
                factor.id,
                (factor.id,),
                factor.role,
                factor.probability,
                compiled.parameter_status[factor.id],
                empirical,
                estimate,
            )

        for group in compiled.factor_groups:
            if len(group.members) == 1:
                continue
            status = (
                IdentificationStatus.PROVED_IDENTIFIABLE
                if compiled.reduced_report is not None
                and compiled.reduced_report.parameter_identifiable[group.id]
                else IdentificationStatus.PROVED_AMBIGUOUS
            )
            empirical = bool(
                reduced_report is not None
                and reduced_report.parameter_identifiable[group.id]
            )
            if method == METHOD_REFERENCE:
                estimate = (
                    float(
                        np.prod(
                            [
                                fit.probabilities[factor_index[member]]
                                for member in group.members
                            ]
                        )
                    )
                    if fit.converged and fit.probabilities is not None and empirical
                    else None
                )
            else:
                estimate = (
                    float(fit.probabilities[group_index[group.id]])
                    if fit.converged and fit.probabilities is not None and empirical
                    else None
                )
            _append_estimate(
                rows,
                base,
                method,
                "combination",
                group.id,
                group.members,
                "identified_product",
                group.probability,
                status,
                empirical,
                estimate,
            )

        for target in family.targets:
            status = compiled.target_status[target.id]
            if method == METHOD_REFERENCE:
                empirical = original_report.target_identifiable[target.id]
                estimate = (
                    float(
                        np.prod(
                            [
                                fit.probabilities[factor_index[member]]
                                for member in target.factors
                            ]
                        )
                    )
                    if fit.converged and fit.probabilities is not None and empirical
                    else None
                )
            else:
                mapped = compiled.target_reduced_factors[target.id]
                empirical = bool(
                    mapped is not None
                    and reduced_report is not None
                    and reduced_report.target_identifiable.get(target.id, False)
                )
                estimate = (
                    float(
                        np.prod(
                            [fit.probabilities[group_index[group_id]] for group_id in mapped]
                        )
                    )
                    if fit.converged
                    and fit.probabilities is not None
                    and mapped is not None
                    and empirical
                    else None
                )
            _append_estimate(
                rows,
                base,
                method,
                "target",
                target.id,
                target.factors,
                "availability_target",
                exact_target_probability(family, target.factors),
                status,
                empirical,
                estimate,
            )


def summarize_reduction(
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

    result: list[dict[str, Any]] = []
    for group_key in sorted(fit_groups):
        fit_group = fit_groups[group_key]
        estimate_group = estimate_groups[group_key]

        def object_metrics(kind: str) -> tuple[float | None, float | None]:
            structural = [
                row
                for row in estimate_group
                if row["object_kind"] == kind
                and row["identification_status"] == str(IdentificationStatus.PROVED_IDENTIFIABLE)
            ]
            available = [row for row in structural if _optional_float(row["estimate"]) is not None]
            rate = len(available) / len(structural) if structural else None
            mae = _mean(_optional_float(row["absolute_error"]) for row in available)
            return rate, mae

        individual_rate, individual_mae = object_metrics("individual")
        combination_rate, combination_mae = object_metrics("combination")
        target_rate, target_mae = object_metrics("target")
        unsupported = [
            row
            for row in estimate_group
            if row["identification_status"] != str(IdentificationStatus.PROVED_IDENTIFIABLE)
        ]
        false_confident = sum(_as_bool(row["false_confident_estimate"]) for row in unsupported)
        result.append(
            {
                "family": group_key[0],
                "observation_mode": group_key[1],
                "sample_size": group_key[2],
                "method": group_key[3],
                "datasets": len(fit_group),
                "parameter_dimension": int(fit_group[0]["parameter_dimension"]),
                "state_count": int(fit_group[0]["state_count"]),
                "convergence_rate": _mean(float(_as_bool(row["converged"])) for row in fit_group),
                "boundary_fit_rate": _mean(
                    float(int(row["boundary_parameter_count"] or 0) > 0) for row in fit_group
                ),
                "nonunique_fit_rate": _mean(
                    float(str(row["status"]) == "converged_nonunique") for row in fit_group
                ),
                "mean_runtime_seconds": _mean(float(row["runtime_seconds"]) for row in fit_group),
                "median_runtime_seconds": _median(float(row["runtime_seconds"]) for row in fit_group),
                "individual_estimate_rate": individual_rate,
                "individual_mae": individual_mae,
                "combination_estimate_rate": combination_rate,
                "combination_mae": combination_mae,
                "target_estimate_rate": target_rate,
                "target_mae": target_mae,
                "false_confident_estimate_rate": (
                    false_confident / len(unsupported) if unsupported else 0.0
                ),
            }
        )
    return result


def paired_reduction_summary(
    paired_fits: list[dict[str, Any]],
    estimates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fit_groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    estimate_groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in paired_fits:
        fit_groups[(str(row["family"]), str(row["observation_mode"]), int(row["sample_size"]))].append(row)
    for row in estimates:
        estimate_groups[(str(row["family"]), str(row["observation_mode"]), int(row["sample_size"]))].append(row)

    result: list[dict[str, Any]] = []
    for group_key in sorted(fit_groups):
        fit_group = fit_groups[group_key]
        estimate_group = estimate_groups[group_key]
        kind_deltas: dict[str, list[float]] = {
            "individual": [],
            "combination": [],
            "target": [],
        }
        for repetition in sorted({int(row["repetition"]) for row in estimate_group}):
            repetition_rows = [
                row for row in estimate_group if int(row["repetition"]) == repetition
            ]
            for kind in kind_deltas:
                relevant = [
                    row
                    for row in repetition_rows
                    if row["object_kind"] == kind
                    and row["identification_status"] == str(IdentificationStatus.PROVED_IDENTIFIABLE)
                ]
                object_ids = sorted({str(row["object_id"]) for row in relevant})
                if not object_ids:
                    continue
                errors: dict[str, dict[str, float | None]] = {}
                for method in (METHOD_REFERENCE, METHOD_PROPOSED):
                    errors[method] = {
                        str(row["object_id"]): _optional_float(row["absolute_error"])
                        for row in relevant
                        if row["method"] == method
                    }
                if all(
                    set(errors[method]) == set(object_ids)
                    and all(value is not None for value in errors[method].values())
                    for method in errors
                ):
                    kind_deltas[kind].append(
                        statistics.fmean(float(value) for value in errors[METHOD_PROPOSED].values())
                        - statistics.fmean(float(value) for value in errors[METHOD_REFERENCE].values())
                    )

        objective_pairs = [
            row for row in fit_group if _optional_float(row["absolute_nll_difference"]) is not None
        ]
        result.append(
            {
                "family": group_key[0],
                "observation_mode": group_key[1],
                "sample_size": group_key[2],
                "objective_pairs": len(objective_pairs),
                "objective_equivalence_rate": _mean(
                    float(_as_bool(row["objective_equivalent"])) for row in objective_pairs
                ),
                "maximum_absolute_nll_difference": (
                    max(float(row["absolute_nll_difference"]) for row in objective_pairs)
                    if objective_pairs
                    else None
                ),
                "median_speedup_b3_over_proposed": _median(
                    _optional_float(row["speedup_b3_over_proposed"]) for row in objective_pairs
                ),
                "individual_campaign_pairs": len(kind_deltas["individual"]),
                "individual_mean_mae_delta_proposed_minus_b3": _mean(kind_deltas["individual"]),
                "combination_campaign_pairs": len(kind_deltas["combination"]),
                "combination_mean_mae_delta_proposed_minus_b3": _mean(kind_deltas["combination"]),
                "target_campaign_pairs": len(kind_deltas["target"]),
                "target_mean_mae_delta_proposed_minus_b3": _mean(kind_deltas["target"]),
            }
        )
    return result


def run_reduction_experiment(
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
    dataset_count = len(families) * len(policies) * actual_repetitions * len(actual_sizes)
    if (
        os.environ.get("GITHUB_ACTIONS", "").lower() != "true"
        and dataset_count > config.local_smoke_max_dataset_fits
    ):
        raise RuntimeError(
            "reduction experiment exceeds the local smoke budget "
            f"({dataset_count} > {config.local_smoke_max_dataset_fits} datasets); "
            "run it through GitHub Actions"
        )

    compiler_rows: list[dict[str, Any]] = []
    witness_rows: list[dict[str, Any]] = []
    fit_rows: list[dict[str, Any]] = []
    estimate_rows: list[dict[str, Any]] = []
    pattern_rows: list[dict[str, Any]] = []
    paired_fit_rows: list[dict[str, Any]] = []
    max_size = max(actual_sizes)

    for family in families:
        for policy in policies:
            start = time.perf_counter()
            compiled = compile_observation_model(family, policy)
            compile_seconds = time.perf_counter() - start
            compiler_rows.append(_compilation_row(family, policy, compiled, compile_seconds))
            witness_rows.extend(_witness_rows(compiled))

            for repetition in range(actual_repetitions):
                batch = simulate_batch(
                    family,
                    max_size,
                    policy,
                    np.random.default_rng(stable_seed(config.seed, family.id, repetition, "values")),
                    np.random.default_rng(
                        stable_seed(config.seed, family.id, repetition, policy.id, "mask")
                    ),
                )
                reference_warm: np.ndarray | None = None
                proposed_warm: np.ndarray | None = None
                for sample_size in actual_sizes:
                    prefix = batch.prefix(sample_size)
                    base = {
                        "experiment_id": EXPERIMENT_ID,
                        "family": family.id,
                        "observation_mode": policy.id,
                        "repetition": repetition,
                        "sample_size": sample_size,
                    }
                    reference_table = compress_observed_patterns(family, prefix)
                    pattern_rows.extend(_pattern_rows(base, family, reference_table))
                    reference_report = _empirical_report(family, prefix)
                    reference_truth_nll = negative_log_likelihood(
                        family.factor_probabilities,
                        reference_table,
                    )
                    fit_start = time.perf_counter()
                    reference_fit = fit_exact_observed_likelihood(
                        family,
                        reference_table,
                        initial_probabilities=reference_warm,
                    )
                    reference_seconds = time.perf_counter() - fit_start
                    if reference_fit.converged and reference_fit.probabilities is not None:
                        reference_warm = reference_fit.probabilities
                    fit_rows.append(
                        _fit_row(
                            base,
                            METHOD_REFERENCE,
                            reference_fit,
                            reference_seconds,
                            len(family.factors),
                            compiled.original_state_count,
                            reference_report.rank,
                            reference_truth_nll,
                        )
                    )

                    if compiled.reduced_model is None:
                        proposed_fit = _no_observation_fit()
                        proposed_report = None
                        proposed_truth_nll = None
                        proposed_seconds = 0.0
                    else:
                        reduced_batch = compiled.reduce_batch(prefix)
                        reduced_table = compress_observed_patterns(
                            compiled.reduced_model,
                            reduced_batch,
                        )
                        proposed_report = _empirical_report(compiled.reduced_model, reduced_batch)
                        proposed_truth_nll = negative_log_likelihood(
                            compiled.reduced_model.factor_probabilities,
                            reduced_table,
                        )
                        lower = np.asarray(
                            [(1e-6) ** len(group.members) for group in compiled.factor_groups],
                            dtype=float,
                        )
                        upper = np.asarray(
                            [(1.0 - 1e-6) ** len(group.members) for group in compiled.factor_groups],
                            dtype=float,
                        )
                        fit_start = time.perf_counter()
                        proposed_fit = fit_exact_observed_likelihood(
                            compiled.reduced_model,
                            reduced_table,
                            initial_probabilities=proposed_warm,
                            lower_probabilities=lower,
                            upper_probabilities=upper,
                        )
                        proposed_seconds = time.perf_counter() - fit_start
                        if proposed_fit.converged and proposed_fit.probabilities is not None:
                            proposed_warm = proposed_fit.probabilities
                    reduced_dimension = (
                        0 if compiled.reduced_model is None else len(compiled.reduced_model.factors)
                    )
                    fit_rows.append(
                        _fit_row(
                            base,
                            METHOD_PROPOSED,
                            proposed_fit,
                            proposed_seconds,
                            reduced_dimension,
                            compiled.reduced_state_count,
                            0 if proposed_report is None else proposed_report.rank,
                            proposed_truth_nll,
                        )
                    )
                    _add_estimates(
                        estimate_rows,
                        base,
                        compiled,
                        reference_report,
                        proposed_report,
                        reference_fit,
                        proposed_fit,
                    )

                    if (
                        reference_fit.negative_log_likelihood is not None
                        and proposed_fit.negative_log_likelihood is not None
                    ):
                        delta = (
                            proposed_fit.negative_log_likelihood
                            - reference_fit.negative_log_likelihood
                        )
                        absolute = abs(delta)
                        tolerance = 1e-6 * max(
                            1.0,
                            abs(reference_fit.negative_log_likelihood),
                        )
                        speedup = (
                            reference_seconds / proposed_seconds
                            if proposed_seconds > 0.0
                            else None
                        )
                    else:
                        delta = None
                        absolute = None
                        tolerance = None
                        speedup = None
                    paired_fit_rows.append(
                        {
                            **base,
                            "b3_negative_log_likelihood": reference_fit.negative_log_likelihood,
                            "proposed_negative_log_likelihood": proposed_fit.negative_log_likelihood,
                            "nll_delta_proposed_minus_b3": delta,
                            "absolute_nll_difference": absolute,
                            "objective_equivalent": (
                                None if absolute is None else absolute <= tolerance
                            ),
                            "b3_runtime_seconds": reference_seconds,
                            "proposed_runtime_seconds": proposed_seconds,
                            "speedup_b3_over_proposed": speedup,
                            "b3_state_count": compiled.original_state_count,
                            "proposed_state_count": compiled.reduced_state_count,
                        }
                    )

    summary_rows = summarize_reduction(fit_rows, estimate_rows)
    paired_summary_rows = paired_reduction_summary(paired_fit_rows, estimate_rows)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "compiler.csv", COMPILER_FIELDS, compiler_rows)
    _write_csv(output / "ambiguity_witnesses.csv", WITNESS_FIELDS, witness_rows)
    _write_csv(output / "fits.csv", FIT_FIELDS, fit_rows)
    _write_csv(output / "estimates.csv", ESTIMATE_FIELDS, estimate_rows)
    _write_csv(output / "patterns.csv", PATTERN_FIELDS, pattern_rows)
    _write_csv(output / "paired_fits.csv", PAIRED_FIT_FIELDS, paired_fit_rows)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(output / "paired_summary.csv", PAIRED_SUMMARY_FIELDS, paired_summary_rows)

    equivalence_failures = sum(
        not _as_bool(row["objective_equivalent"])
        for row in paired_fit_rows
        if row["objective_equivalent"] is not None
    )
    manifest = {
        "schema_version": 1,
        "kind": "reduction_experiment_shard",
        "experiment_id": EXPERIMENT_ID,
        "config_sha256": file_sha256(config_path),
        "seed": config.seed,
        "families": [family.id for family in families],
        "observation_modes": [policy.id for policy in policies],
        "repetitions": actual_repetitions,
        "sample_sizes": list(actual_sizes),
        "methods": [METHOD_REFERENCE, METHOD_PROPOSED],
        "objective_equivalence_failures": equivalence_failures,
        "row_counts": {
            "compiler": len(compiler_rows),
            "ambiguity_witnesses": len(witness_rows),
            "fits": len(fit_rows),
            "estimates": len(estimate_rows),
            "patterns": len(pattern_rows),
            "paired_fits": len(paired_fit_rows),
            "summary": len(summary_rows),
            "paired_summary": len(paired_summary_rows),
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


def aggregate_reduction_experiment(
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    named_paths = {
        "compiler": sorted(root.rglob("compiler.csv")),
        "ambiguity_witnesses": sorted(root.rglob("ambiguity_witnesses.csv")),
        "fits": sorted(root.rglob("fits.csv")),
        "estimates": sorted(root.rglob("estimates.csv")),
        "patterns": sorted(root.rglob("patterns.csv")),
        "paired_fits": sorted(root.rglob("paired_fits.csv")),
    }
    if any(not paths for paths in named_paths.values()):
        raise ValueError("input root does not contain complete reduction-experiment shards")
    tables = {name: _read_csvs(paths) for name, paths in named_paths.items()}
    summary_rows = summarize_reduction(tables["fits"], tables["estimates"])
    paired_summary_rows = paired_reduction_summary(
        tables["paired_fits"],
        tables["estimates"],
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    field_map = {
        "compiler": COMPILER_FIELDS,
        "ambiguity_witnesses": WITNESS_FIELDS,
        "fits": FIT_FIELDS,
        "estimates": ESTIMATE_FIELDS,
        "patterns": PATTERN_FIELDS,
        "paired_fits": PAIRED_FIT_FIELDS,
    }
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", field_map[name], rows)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(output / "paired_summary.csv", PAIRED_SUMMARY_FIELDS, paired_summary_rows)
    equivalence_failures = sum(
        not _as_bool(row["objective_equivalent"])
        for row in tables["paired_fits"]
        if row["objective_equivalent"] != ""
    )
    manifest = {
        "schema_version": 1,
        "kind": "reduction_experiment_aggregate",
        "experiment_id": EXPERIMENT_ID,
        "source_shards": len(named_paths["fits"]),
        "methods": [METHOD_REFERENCE, METHOD_PROPOSED],
        "objective_equivalence_failures": equivalence_failures,
        "row_counts": {
            **{name: len(rows) for name, rows in tables.items()},
            "summary": len(summary_rows),
            "paired_summary": len(paired_summary_rows),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
