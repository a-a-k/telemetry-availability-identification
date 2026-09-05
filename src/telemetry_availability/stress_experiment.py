from __future__ import annotations

import csv
import json
import math
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.stats import norm

from .likelihood import compress_observed_patterns, fit_exact_observed_likelihood
from .observation import EpisodeBatch, ObservationPolicy
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv, stable_seed
from .stress import (
    DiagnosticResult,
    block_bootstrap_binary_interval,
    block_bootstrap_ranges,
    branch_target_interval,
    cross_domain_diagnostic,
    direct_binary_interval,
    exporter_loss_batch,
    exporter_mask_diagnostic,
    fit_selection_aware_likelihood,
    full_batch,
    iid_latent_states,
    lag_one_diagnostic,
    markov_latent_states,
    matched_two_domain_model,
    readiness_batch,
    readiness_implication_diagnostic,
    readiness_quantity_values,
    shared_domain_model,
    shared_domain_quantity_values,
    support_diagnostic,
)
from .stress_config import StressExperimentConfig, StressSeries, StressVariant
from .transfer import TARGET_ADD, TARGET_CURRENT, TARGET_SPLIT
from .uncertainty import (
    CHOICE_DIFFERENCE,
    DELTA_ADD,
    DELTA_SPLIT,
    QUANTITIES,
    IntervalEstimate,
    extract_simultaneous_evidence,
    likelihood_wald_ranges,
    quantity_values,
    simultaneous_target_ranges,
)


METHOD_PROPOSED_RAW = "proposed_raw"
METHOD_PROPOSED_GUARDED = "proposed_guarded"
METHOD_B3 = "b3_assumed_model"
METHOD_AWARE = "mechanism_aware_reference"
METHOD_B0 = "b0_endpoint_persistence"
METHODS = (
    METHOD_PROPOSED_RAW,
    METHOD_PROPOSED_GUARDED,
    METHOD_B3,
    METHOD_AWARE,
    METHOD_B0,
)
BRANCH_QUANTITY = "target_mixture_availability"

ESTIMATE_FIELDS = (
    "experiment_id",
    "series",
    "variant",
    "is_stress",
    "repetition",
    "sample_size",
    "method",
    "quantity",
    "truth",
    "point",
    "prediction_available",
    "signed_error",
    "absolute_error",
    "lower",
    "upper",
    "interval_available",
    "covers_truth",
    "width",
    "status",
    "diagnostic_flagged",
)

DIAGNOSTIC_FIELDS = (
    "experiment_id",
    "series",
    "variant",
    "is_stress",
    "repetition",
    "sample_size",
    "diagnostic",
    "statistic",
    "p_value",
    "threshold",
    "evidence_count",
    "flagged",
    "expected_flag",
    "status",
)

DECISION_FIELDS = (
    "experiment_id",
    "series",
    "variant",
    "is_stress",
    "repetition",
    "sample_size",
    "method",
    "decision_rule",
    "true_best",
    "selected",
    "decision_available",
    "correct",
    "regret",
    "diagnostic_flagged",
)

CAMPAIGN_FIELDS = (
    "experiment_id",
    "series",
    "variant",
    "is_stress",
    "repetition",
    "sample_size",
    "assumed_fit_status",
    "aware_fit_status",
    "proposed_set_status",
    "proposed_truncated",
    "trace_retention",
    "branch_a_count",
    "branch_b_count",
    "runtime_seconds",
)

SUMMARY_FIELDS = (
    "series",
    "variant",
    "is_stress",
    "sample_size",
    "method",
    "quantity",
    "datasets",
    "prediction_rate",
    "mae",
    "signed_bias",
    "interval_rate",
    "coverage_when_available",
    "coverage_ci95_low",
    "coverage_ci95_high",
    "mean_width",
    "median_width",
)

DIAGNOSTIC_SUMMARY_FIELDS = (
    "series",
    "variant",
    "is_stress",
    "sample_size",
    "diagnostic",
    "datasets",
    "available_rate",
    "flag_rate",
    "flag_ci95_low",
    "flag_ci95_high",
    "expected_flag",
)

DECISION_SUMMARY_FIELDS = (
    "series",
    "variant",
    "is_stress",
    "sample_size",
    "method",
    "datasets",
    "decision_coverage",
    "accuracy_when_decided",
    "accuracy_ci95_low",
    "accuracy_ci95_high",
    "wrong_decision_rate",
    "mean_regret_when_decided",
)

PAIRED_FIELDS = (
    "series",
    "control_variant",
    "stress_variant",
    "sample_size",
    "method",
    "quantity",
    "prediction_pairs",
    "mean_absolute_error_delta_stress_minus_control",
    "mean_error_delta_ci95_low",
    "mean_error_delta_ci95_high",
    "interval_pairs",
    "mean_width_delta_stress_minus_control",
    "diagnostic_pairs",
    "mean_flag_delta_stress_minus_control",
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


def _wilson(successes: int, trials: int) -> tuple[float | None, float | None]:
    if trials <= 0:
        return None, None
    critical = float(norm.ppf(0.975))
    estimate = successes / trials
    denominator = 1.0 + critical**2 / trials
    center = (estimate + critical**2 / (2.0 * trials)) / denominator
    half = critical / denominator * math.sqrt(
        estimate * (1.0 - estimate) / trials + critical**2 / (4.0 * trials**2)
    )
    return max(0.0, center - half), min(1.0, center + half)


def _unavailable(
    quantities: Iterable[str],
    status: str,
) -> dict[str, IntervalEstimate]:
    return {
        quantity: IntervalEstimate(None, None, None, status)
        for quantity in quantities
    }


def _with_points(
    intervals: dict[str, IntervalEstimate],
    points: dict[str, float | None],
) -> dict[str, IntervalEstimate]:
    return {
        quantity: IntervalEstimate(
            estimate.lower,
            estimate.upper,
            points.get(quantity),
            estimate.status,
        )
        for quantity, estimate in intervals.items()
    }


def _point_only(
    quantities: Iterable[str],
    points: dict[str, float | None],
    status: str,
) -> dict[str, IntervalEstimate]:
    return {
        quantity: IntervalEstimate(None, None, points.get(quantity), status)
        for quantity in quantities
    }


def _append_estimates(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    methods: dict[str, dict[str, IntervalEstimate]],
    truths: dict[str, float],
    diagnostic_flagged: bool,
) -> None:
    for method in METHODS:
        estimates = methods[method]
        for quantity, truth in truths.items():
            estimate = estimates[quantity]
            point = estimate.point
            interval_available = estimate.lower is not None and estimate.upper is not None
            rows.append(
                {
                    **base,
                    "method": method,
                    "quantity": quantity,
                    "truth": truth,
                    "point": point,
                    "prediction_available": point is not None,
                    "signed_error": None if point is None else point - truth,
                    "absolute_error": None if point is None else abs(point - truth),
                    "lower": estimate.lower,
                    "upper": estimate.upper,
                    "interval_available": interval_available,
                    "covers_truth": (
                        None
                        if not interval_available
                        else estimate.lower <= truth <= estimate.upper
                    ),
                    "width": None if not interval_available else estimate.upper - estimate.lower,
                    "status": estimate.status,
                    "diagnostic_flagged": diagnostic_flagged,
                }
            )


def _append_decisions(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    methods: dict[str, dict[str, IntervalEstimate]],
    truths: dict[str, float],
    diagnostic_flagged: bool,
) -> None:
    if CHOICE_DIFFERENCE not in truths:
        return
    truth = truths[CHOICE_DIFFERENCE]
    true_best = TARGET_SPLIT if truth > 0.0 else TARGET_ADD if truth < 0.0 else "tie"
    for method in METHODS:
        estimate = methods[method][CHOICE_DIFFERENCE]
        selected: str | None = None
        rule = "interval_sign"
        if method in {METHOD_B3, METHOD_AWARE, METHOD_B0}:
            rule = "point_sign"
            if estimate.point is not None:
                selected = (
                    TARGET_SPLIT
                    if estimate.point > 0.0
                    else TARGET_ADD
                    if estimate.point < 0.0
                    else None
                )
        elif estimate.lower is not None and estimate.upper is not None:
            if estimate.lower > 0.0:
                selected = TARGET_SPLIT
            elif estimate.upper < 0.0:
                selected = TARGET_ADD
        available = selected is not None
        correct = None if not available else selected == true_best
        rows.append(
            {
                **base,
                "method": method,
                "decision_rule": rule,
                "true_best": true_best,
                "selected": selected,
                "decision_available": available,
                "correct": correct,
                "regret": (
                    None if not available else 0.0 if correct else abs(truth)
                ),
                "diagnostic_flagged": diagnostic_flagged,
            }
        )


def _append_diagnostic(
    rows: list[dict[str, Any]],
    base: dict[str, Any],
    diagnostic: DiagnosticResult,
    expected_flag: bool,
) -> None:
    rows.append(
        {
            **base,
            "diagnostic": diagnostic.id,
            "statistic": diagnostic.statistic,
            "p_value": diagnostic.p_value,
            "threshold": diagnostic.threshold,
            "evidence_count": diagnostic.evidence_count,
            "flagged": diagnostic.flagged,
            "expected_flag": expected_flag,
            "status": diagnostic.status,
        }
    )


def _direct_from_batch(
    model: Any,
    batch: EpisodeBatch,
    confidence_level: float,
) -> IntervalEstimate:
    position = next(
        index for index, item in enumerate(model.observables) if item.id == "current_success"
    )
    selected = batch.observed[:, position]
    if not np.any(selected):
        return IntervalEstimate(None, None, None, "direct_endpoint_unavailable")
    return direct_binary_interval(batch.values[selected, position], confidence_level)


def _b0_transfer_estimates(
    direct: IntervalEstimate,
) -> dict[str, IntervalEstimate]:
    points: dict[str, float | None] = {
        TARGET_CURRENT: direct.point,
        TARGET_SPLIT: direct.point,
        TARGET_ADD: direct.point,
        DELTA_SPLIT: 0.0 if direct.point is not None else None,
        DELTA_ADD: 0.0 if direct.point is not None else None,
        CHOICE_DIFFERENCE: 0.0 if direct.point is not None else None,
    }
    result = _point_only(QUANTITIES, points, "endpoint_persistence_point")
    result[TARGET_CURRENT] = direct
    return result


def _assumed_transfer_methods(
    config: StressExperimentConfig,
    model: Any,
    policy: ObservationPolicy,
    batch: EpisodeBatch,
    diagnostic: DiagnosticResult,
) -> tuple[
    dict[str, dict[str, IntervalEstimate]],
    Any,
    str,
    bool,
]:
    table = None
    fit = None
    fit_status = "not_attempted"
    try:
        table = compress_observed_patterns(model, batch)
        fit = fit_exact_observed_likelihood(model, table)
        fit_status = fit.status
    except ValueError as error:
        fit_status = f"impossible_pattern:{error}"
    points = {quantity: None for quantity in QUANTITIES}
    if fit is not None and fit.converged and fit.probabilities is not None:
        points = quantity_values(
            model,
            dict(zip(model.factor_ids, fit.probabilities, strict=True)),
        )

    tolerance = max(
        config.branch_minimum_tolerance,
        min(config.branch_tolerance, config.branch_tolerance_scale / math.sqrt(len(batch.values))),
    )
    proposed_status = "range_failed"
    truncated = False
    try:
        domain_a, domain_b, _ = extract_simultaneous_evidence(
            model,
            batch,
            config.confidence_level,
        )
        proposed = simultaneous_target_ranges(
            model,
            policy,
            domain_a,
            domain_b,
            tolerance,
            config.branch_max_nodes_per_domain,
        )
        raw = _with_points(proposed.intervals, points)
        proposed_status = next(iter(proposed.intervals.values())).status
        truncated = proposed.domain_a.truncated or proposed.domain_b.truncated
    except (ValueError, ZeroDivisionError, FloatingPointError) as error:
        raw = _point_only(QUANTITIES, points, f"range_failed:{error}")
        proposed_status = f"range_failed:{error}"
    guarded = (
        _unavailable(QUANTITIES, "diagnostic_rejection")
        if diagnostic.flagged
        else raw
    )
    wald = (
        likelihood_wald_ranges(model, table, fit, config.confidence_level, simultaneous=False)
        if table is not None and fit is not None
        else _unavailable(QUANTITIES, "wald_unavailable")
    )
    b3 = _with_points(wald, points)
    direct = _direct_from_batch(model, batch, config.confidence_level)
    methods = {
        METHOD_PROPOSED_RAW: raw,
        METHOD_PROPOSED_GUARDED: guarded,
        METHOD_B3: b3,
        METHOD_AWARE: _unavailable(QUANTITIES, "aware_reference_not_supplied"),
        METHOD_B0: _b0_transfer_estimates(direct),
    }
    return methods, fit, proposed_status, truncated


def _base_row(
    config: StressExperimentConfig,
    series: StressSeries,
    variant: StressVariant,
    repetition: int,
    sample_size: int,
) -> dict[str, Any]:
    return {
        "experiment_id": config.id,
        "series": series.id,
        "variant": variant.id,
        "is_stress": variant.is_stress,
        "repetition": repetition,
        "sample_size": sample_size,
    }


def _policy(config: StressExperimentConfig, series: StressSeries) -> ObservationPolicy:
    requested = str(series.settings["observation_mode"])
    return next(item for item in config.transfer.observation_modes if item.id == requested)


def _run_exporter(
    config: StressExperimentConfig,
    series: StressSeries,
    model: Any,
    repetitions: int,
    sample_sizes: tuple[int, ...],
    estimates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
) -> None:
    maximum = max(sample_sizes)
    policy = _policy(config, series)
    truths = quantity_values(model)
    for variant in series.variants:
        up = float(variant.parameters["retention_when_domain_up"])
        down = float(variant.parameters["retention_when_domain_down"])
        for repetition in range(repetitions):
            latent = iid_latent_states(
                model,
                maximum,
                np.random.default_rng(stable_seed(config.seed, series.id, repetition, "values")),
            )
            batch = exporter_loss_batch(
                model,
                latent,
                up,
                down,
                np.random.default_rng(stable_seed(config.seed, series.id, repetition, "health_mask")),
                np.random.default_rng(stable_seed(config.seed, series.id, repetition, "trace_mask")),
            )
            aware_warm = None
            for sample_size in sample_sizes:
                started = time.perf_counter()
                prefix = batch.prefix(sample_size)
                base = _base_row(config, series, variant, repetition, sample_size)
                diagnostic = exporter_mask_diagnostic(model, prefix, config.diagnostic_alpha)
                _append_diagnostic(diagnostics, base, diagnostic, variant.is_stress)
                methods, fit, set_status, truncated = _assumed_transfer_methods(
                    config, model, policy, prefix, diagnostic
                )
                aware = fit_selection_aware_likelihood(
                    model,
                    prefix,
                    up,
                    down,
                    initial_probabilities=aware_warm,
                )
                aware_status = aware.status
                if aware.converged and aware.probabilities is not None:
                    aware_warm = aware.probabilities
                    aware_points = quantity_values(
                        model,
                        dict(zip(model.factor_ids, aware.probabilities, strict=True)),
                    )
                else:
                    aware_points = {quantity: None for quantity in QUANTITIES}
                methods[METHOD_AWARE] = _point_only(
                    QUANTITIES,
                    aware_points,
                    "selection_aware_likelihood",
                )
                _append_estimates(estimates, base, methods, truths, diagnostic.flagged)
                _append_decisions(decisions, base, methods, truths, diagnostic.flagged)
                trace_position = next(
                    index
                    for index, item in enumerate(model.observables)
                    if item.id == "current_success"
                )
                campaigns.append(
                    {
                        **base,
                        "assumed_fit_status": "unavailable" if fit is None else fit.status,
                        "aware_fit_status": aware_status,
                        "proposed_set_status": set_status,
                        "proposed_truncated": truncated,
                        "trace_retention": float(np.mean(prefix.observed[:, trace_position])),
                        "branch_a_count": None,
                        "branch_b_count": None,
                        "runtime_seconds": time.perf_counter() - started,
                    }
                )


def _run_temporal(
    config: StressExperimentConfig,
    series: StressSeries,
    model: Any,
    repetitions: int,
    sample_sizes: tuple[int, ...],
    bootstrap_replicates: int,
    estimates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
) -> None:
    maximum = max(sample_sizes)
    policy = _policy(config, series)
    truths = quantity_values(model)
    current_position = next(
        index for index, item in enumerate(model.observables) if item.id == "current_success"
    )
    for variant in series.variants:
        correlation = float(variant.parameters["lag1_autocorrelation"])
        for repetition in range(repetitions):
            latent = markov_latent_states(
                model,
                maximum,
                correlation,
                np.random.default_rng(stable_seed(config.seed, series.id, variant.id, repetition, "states")),
            )
            batch = full_batch(model, latent)
            for sample_size in sample_sizes:
                started = time.perf_counter()
                prefix = batch.prefix(sample_size)
                base = _base_row(config, series, variant, repetition, sample_size)
                diagnostic = lag_one_diagnostic(
                    prefix.values[:, current_position],
                    config.diagnostic_alpha,
                )
                _append_diagnostic(diagnostics, base, diagnostic, variant.is_stress)
                methods, fit, set_status, truncated = _assumed_transfer_methods(
                    config, model, policy, prefix, diagnostic
                )
                if fit is not None and fit.converged and fit.probabilities is not None:
                    points = quantity_values(
                        model,
                        dict(zip(model.factor_ids, fit.probabilities, strict=True)),
                    )
                    selected_quantities = (TARGET_SPLIT, CHOICE_DIFFERENCE)
                    bootstrap = block_bootstrap_ranges(
                        model,
                        prefix,
                        fit.probabilities,
                        selected_quantities,
                        config.confidence_level,
                        bootstrap_replicates,
                        config.block_length,
                        np.random.default_rng(
                            stable_seed(config.seed, series.id, variant.id, repetition, sample_size, "bootstrap")
                        ),
                        lambda fitted_model, table: fit_exact_observed_likelihood(
                            fitted_model,
                            table,
                            initial_probabilities=fit.probabilities,
                        ),
                    )
                    aware_intervals = _point_only(
                        QUANTITIES,
                        points,
                        "same_likelihood_point",
                    )
                    for quantity, interval in bootstrap.items():
                        aware_intervals[quantity] = interval
                    aware_status = "moving_block_bootstrap"
                else:
                    aware_intervals = _unavailable(QUANTITIES, "block_bootstrap_unavailable")
                    aware_status = "fit_unavailable"
                methods[METHOD_AWARE] = aware_intervals
                _append_estimates(estimates, base, methods, truths, diagnostic.flagged)
                _append_decisions(decisions, base, methods, truths, diagnostic.flagged)
                campaigns.append(
                    {
                        **base,
                        "assumed_fit_status": "unavailable" if fit is None else fit.status,
                        "aware_fit_status": aware_status,
                        "proposed_set_status": set_status,
                        "proposed_truncated": truncated,
                        "trace_retention": 1.0,
                        "branch_a_count": None,
                        "branch_b_count": None,
                        "runtime_seconds": time.perf_counter() - started,
                    }
                )


def _run_wrong_domain(
    config: StressExperimentConfig,
    series: StressSeries,
    base_model: Any,
    repetitions: int,
    sample_sizes: tuple[int, ...],
    estimates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
) -> None:
    maximum = max(sample_sizes)
    assumed_model = matched_two_domain_model(
        base_model,
        float(series.settings["shared_domain_probability"]),
    )
    merged_model = shared_domain_model(assumed_model)
    policy = _policy(config, series)
    for variant in series.variants:
        merged = bool(variant.parameters["merge_declared_domains"])
        generator_model = merged_model if merged else assumed_model
        truths = (
            shared_domain_quantity_values(merged_model)
            if merged
            else quantity_values(assumed_model)
        )
        for repetition in range(repetitions):
            latent = iid_latent_states(
                generator_model,
                maximum,
                np.random.default_rng(stable_seed(config.seed, series.id, variant.id, repetition, "states")),
            )
            batch = full_batch(generator_model, latent)
            aware_warm = None
            for sample_size in sample_sizes:
                started = time.perf_counter()
                prefix = batch.prefix(sample_size)
                base = _base_row(config, series, variant, repetition, sample_size)
                diagnostic = cross_domain_diagnostic(assumed_model, prefix, config.diagnostic_alpha)
                _append_diagnostic(diagnostics, base, diagnostic, variant.is_stress)
                methods, fit, set_status, truncated = _assumed_transfer_methods(
                    config, assumed_model, policy, prefix, diagnostic
                )
                aware_model = merged_model if merged else assumed_model
                try:
                    aware_table = compress_observed_patterns(aware_model, prefix)
                    aware_fit = fit_exact_observed_likelihood(
                        aware_model,
                        aware_table,
                        initial_probabilities=aware_warm,
                    )
                except ValueError:
                    aware_fit = None
                if aware_fit is not None and aware_fit.converged and aware_fit.probabilities is not None:
                    aware_warm = aware_fit.probabilities
                    aware_map = dict(zip(aware_model.factor_ids, aware_fit.probabilities, strict=True))
                    aware_points = (
                        shared_domain_quantity_values(aware_model, aware_map)
                        if merged
                        else quantity_values(aware_model, aware_map)
                    )
                    aware_intervals = _point_only(
                        QUANTITIES,
                        aware_points,
                        "topology_aware_likelihood",
                    )
                    if merged:
                        direct = _direct_from_batch(aware_model, prefix, config.confidence_level)
                        aware_intervals[TARGET_CURRENT] = direct
                        aware_intervals[TARGET_SPLIT] = IntervalEstimate(
                            direct.lower,
                            direct.upper,
                            aware_points[TARGET_SPLIT],
                            "shared_domain_direct_exact",
                        )
                        aware_intervals[DELTA_SPLIT] = IntervalEstimate(
                            0.0,
                            0.0,
                            0.0,
                            "shared_domain_structural_identity",
                        )
                    aware_status = aware_fit.status
                else:
                    aware_intervals = _unavailable(QUANTITIES, "topology_aware_fit_unavailable")
                    aware_status = "unavailable" if aware_fit is None else aware_fit.status
                methods[METHOD_AWARE] = aware_intervals
                _append_estimates(estimates, base, methods, truths, diagnostic.flagged)
                _append_decisions(decisions, base, methods, truths, diagnostic.flagged)
                campaigns.append(
                    {
                        **base,
                        "assumed_fit_status": "unavailable" if fit is None else fit.status,
                        "aware_fit_status": aware_status,
                        "proposed_set_status": set_status,
                        "proposed_truncated": truncated,
                        "trace_retention": 1.0,
                        "branch_a_count": None,
                        "branch_b_count": None,
                        "runtime_seconds": time.perf_counter() - started,
                    }
                )


def _branch_wald(
    branch: np.ndarray,
    success: np.ndarray,
    target_share: float,
    confidence_level: float,
) -> IntervalEstimate:
    counts = (int(np.count_nonzero(~branch)), int(np.count_nonzero(branch)))
    if min(counts) == 0:
        return IntervalEstimate(None, None, None, "branch_likelihood_unidentified")
    rates = (
        float(np.mean(success[~branch])),
        float(np.mean(success[branch])),
    )
    point = (1.0 - target_share) * rates[0] + target_share * rates[1]
    variance = (
        (1.0 - target_share) ** 2 * rates[0] * (1.0 - rates[0]) / counts[0]
        + target_share**2 * rates[1] * (1.0 - rates[1]) / counts[1]
    )
    critical = float(norm.ppf(0.5 + confidence_level / 2.0))
    half = critical * math.sqrt(max(0.0, variance))
    return IntervalEstimate(
        max(0.0, point - half),
        min(1.0, point + half),
        point,
        "saturated_branch_wald",
    )


def _run_rare_branch(
    config: StressExperimentConfig,
    series: StressSeries,
    repetitions: int,
    sample_sizes: tuple[int, ...],
    estimates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
) -> None:
    del decisions
    maximum = max(sample_sizes)
    success_a = float(series.settings["branch_a_success"])
    success_b = float(series.settings["branch_b_success"])
    target_share = float(series.settings["target_branch_b_share"])
    truth = (1.0 - target_share) * success_a + target_share * success_b
    truths = {BRANCH_QUANTITY: truth}
    for variant in series.variants:
        calibration_share = float(variant.parameters["calibration_branch_b_share"])
        for repetition in range(repetitions):
            route_uniform = np.random.default_rng(
                stable_seed(config.seed, series.id, repetition, "route")
            ).random(maximum)
            potential_a = np.random.default_rng(
                stable_seed(config.seed, series.id, repetition, "success_a")
            ).random(maximum) < success_a
            potential_b = np.random.default_rng(
                stable_seed(config.seed, series.id, repetition, "success_b")
            ).random(maximum) < success_b
            branch = route_uniform < calibration_share
            success = np.where(branch, potential_b, potential_a)
            for sample_size in sample_sizes:
                started = time.perf_counter()
                prefix_branch = branch[:sample_size]
                prefix_success = success[:sample_size]
                base = _base_row(config, series, variant, repetition, sample_size)
                proposed, counts = branch_target_interval(
                    prefix_branch,
                    prefix_success,
                    target_share,
                    config.confidence_level,
                    config.minimum_branch_observations,
                )
                diagnostic = support_diagnostic(counts, config.minimum_branch_observations)
                _append_diagnostic(diagnostics, base, diagnostic, variant.is_stress)
                guarded = (
                    IntervalEstimate(None, None, None, "diagnostic_rejection")
                    if diagnostic.flagged
                    else proposed
                )
                b3 = _branch_wald(
                    prefix_branch,
                    prefix_success,
                    target_share,
                    config.confidence_level,
                )
                direct = direct_binary_interval(prefix_success, config.confidence_level)
                methods = {
                    METHOD_PROPOSED_RAW: {BRANCH_QUANTITY: proposed},
                    METHOD_PROPOSED_GUARDED: {BRANCH_QUANTITY: guarded},
                    METHOD_B3: {BRANCH_QUANTITY: b3},
                    METHOD_AWARE: {
                        BRANCH_QUANTITY: IntervalEstimate(
                            proposed.lower,
                            proposed.upper,
                            b3.point,
                            "branch_aware_exact_reference",
                        )
                    },
                    METHOD_B0: {
                        BRANCH_QUANTITY: IntervalEstimate(
                            direct.lower,
                            direct.upper,
                            direct.point,
                            "endpoint_persistence_wrong_mixture",
                        )
                    },
                }
                _append_estimates(estimates, base, methods, truths, diagnostic.flagged)
                campaigns.append(
                    {
                        **base,
                        "assumed_fit_status": "saturated_branch_likelihood",
                        "aware_fit_status": "branch_aware_exact",
                        "proposed_set_status": proposed.status,
                        "proposed_truncated": False,
                        "trace_retention": 1.0,
                        "branch_a_count": counts[0],
                        "branch_b_count": counts[1],
                        "runtime_seconds": time.perf_counter() - started,
                    }
                )


def _run_readiness(
    config: StressExperimentConfig,
    series: StressSeries,
    model: Any,
    repetitions: int,
    sample_sizes: tuple[int, ...],
    bootstrap_replicates: int,
    estimates: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    campaigns: list[dict[str, Any]],
) -> None:
    maximum = max(sample_sizes)
    policy = _policy(config, series)
    recovery = float(series.settings["recovery_probability"])
    current_position = next(
        index for index, item in enumerate(model.observables) if item.id == "current_success"
    )
    for variant in series.variants:
        lag = int(variant.parameters["lag_episodes"])
        truths = readiness_quantity_values(model, recovery, lag)
        for repetition in range(repetitions):
            batch = readiness_batch(
                model,
                maximum,
                recovery,
                lag,
                np.random.default_rng(stable_seed(config.seed, series.id, repetition, "domain")),
                np.random.default_rng(stable_seed(config.seed, series.id, repetition, "residuals")),
            )
            for sample_size in sample_sizes:
                started = time.perf_counter()
                prefix = batch.prefix(sample_size)
                base = _base_row(config, series, variant, repetition, sample_size)
                diagnostic = readiness_implication_diagnostic(model, prefix)
                _append_diagnostic(diagnostics, base, diagnostic, variant.is_stress)
                methods, fit, set_status, truncated = _assumed_transfer_methods(
                    config, model, policy, prefix, diagnostic
                )
                block = block_bootstrap_binary_interval(
                    prefix.values[:, current_position],
                    config.confidence_level,
                    bootstrap_replicates,
                    config.block_length,
                    np.random.default_rng(
                        stable_seed(config.seed, series.id, variant.id, repetition, sample_size, "bootstrap")
                    ),
                )
                aware = _unavailable(QUANTITIES, "dynamic_transfer_not_identified")
                aware[TARGET_CURRENT] = block
                methods[METHOD_AWARE] = aware
                _append_estimates(estimates, base, methods, truths, diagnostic.flagged)
                _append_decisions(decisions, base, methods, truths, diagnostic.flagged)
                campaigns.append(
                    {
                        **base,
                        "assumed_fit_status": "unavailable" if fit is None else fit.status,
                        "aware_fit_status": "moving_block_endpoint_only",
                        "proposed_set_status": set_status,
                        "proposed_truncated": truncated,
                        "trace_retention": 1.0,
                        "branch_a_count": None,
                        "branch_b_count": None,
                        "runtime_seconds": time.perf_counter() - started,
                    }
                )


def summarize_estimates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, bool, int, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["series"]),
            str(row["variant"]),
            _as_bool(row["is_stress"]),
            int(row["sample_size"]),
            str(row["method"]),
            str(row["quantity"]),
        )
        groups[key].append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(groups):
        selected = groups[key]
        points = [_optional_float(row["point"]) for row in selected]
        errors = [_optional_float(row["absolute_error"]) for row in selected]
        signed = [_optional_float(row["signed_error"]) for row in selected]
        interval_rows = [row for row in selected if _as_bool(row["interval_available"])]
        coverage = sum(_as_bool(row["covers_truth"]) for row in interval_rows)
        low, high = _wilson(coverage, len(interval_rows))
        result.append(
            {
                "series": key[0],
                "variant": key[1],
                "is_stress": key[2],
                "sample_size": key[3],
                "method": key[4],
                "quantity": key[5],
                "datasets": len(selected),
                "prediction_rate": sum(value is not None for value in points) / len(selected),
                "mae": _mean(errors),
                "signed_bias": _mean(signed),
                "interval_rate": len(interval_rows) / len(selected),
                "coverage_when_available": (
                    coverage / len(interval_rows) if interval_rows else None
                ),
                "coverage_ci95_low": low,
                "coverage_ci95_high": high,
                "mean_width": _mean(_optional_float(row["width"]) for row in interval_rows),
                "median_width": _median(_optional_float(row["width"]) for row in interval_rows),
            }
        )
    return result


def summarize_diagnostics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, bool, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["series"]),
            str(row["variant"]),
            _as_bool(row["is_stress"]),
            int(row["sample_size"]),
            str(row["diagnostic"]),
        )
        groups[key].append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(groups):
        selected = groups[key]
        available = [row for row in selected if row["p_value"] not in {None, ""} or row["status"] == "complete"]
        flags = sum(_as_bool(row["flagged"]) for row in selected)
        low, high = _wilson(flags, len(selected))
        result.append(
            {
                "series": key[0],
                "variant": key[1],
                "is_stress": key[2],
                "sample_size": key[3],
                "diagnostic": key[4],
                "datasets": len(selected),
                "available_rate": len(available) / len(selected),
                "flag_rate": flags / len(selected),
                "flag_ci95_low": low,
                "flag_ci95_high": high,
                "expected_flag": _as_bool(selected[0]["expected_flag"]),
            }
        )
    return result


def summarize_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, bool, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["series"]),
            str(row["variant"]),
            _as_bool(row["is_stress"]),
            int(row["sample_size"]),
            str(row["method"]),
        )
        groups[key].append(row)
    result: list[dict[str, Any]] = []
    for key in sorted(groups):
        selected = groups[key]
        decided = [row for row in selected if _as_bool(row["decision_available"])]
        correct = sum(_as_bool(row["correct"]) for row in decided)
        low, high = _wilson(correct, len(decided))
        result.append(
            {
                "series": key[0],
                "variant": key[1],
                "is_stress": key[2],
                "sample_size": key[3],
                "method": key[4],
                "datasets": len(selected),
                "decision_coverage": len(decided) / len(selected),
                "accuracy_when_decided": correct / len(decided) if decided else None,
                "accuracy_ci95_low": low,
                "accuracy_ci95_high": high,
                "wrong_decision_rate": (len(decided) - correct) / len(selected),
                "mean_regret_when_decided": _mean(
                    _optional_float(row["regret"]) for row in decided
                ),
            }
        )
    return result


def _bootstrap_mean_ci(values: list[float], *seed_parts: object) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    vector = np.asarray(values, dtype=float)
    rng = np.random.default_rng(stable_seed(260907, "m5_paired", *seed_parts))
    indices = rng.integers(0, len(vector), size=(2_000, len(vector)))
    means = np.mean(vector[indices], axis=1)
    low, high = np.quantile(means, (0.025, 0.975))
    return float(low), float(high)


def paired_effects(
    estimate_rows: list[dict[str, Any]],
    diagnostic_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    controls: dict[str, str] = {}
    for row in estimate_rows:
        if not _as_bool(row["is_stress"]):
            controls.setdefault(str(row["series"]), str(row["variant"]))
    estimate_lookup = {
        (
            str(row["series"]),
            str(row["variant"]),
            int(row["sample_size"]),
            int(row["repetition"]),
            str(row["method"]),
            str(row["quantity"]),
        ): row
        for row in estimate_rows
    }
    diagnostic_lookup = {
        (
            str(row["series"]),
            str(row["variant"]),
            int(row["sample_size"]),
            int(row["repetition"]),
        ): row
        for row in diagnostic_rows
    }
    groups = sorted(
        {
            (
                str(row["series"]),
                str(row["variant"]),
                int(row["sample_size"]),
                str(row["method"]),
                str(row["quantity"]),
            )
            for row in estimate_rows
            if _as_bool(row["is_stress"])
        }
    )
    result: list[dict[str, Any]] = []
    for series, stress_variant, sample_size, method, quantity in groups:
        control = controls[series]
        repetitions = sorted(
            int(row["repetition"])
            for row in estimate_rows
            if str(row["series"]) == series
            and str(row["variant"]) == stress_variant
            and int(row["sample_size"]) == sample_size
            and str(row["method"]) == method
            and str(row["quantity"]) == quantity
        )
        error_deltas: list[float] = []
        width_deltas: list[float] = []
        flag_deltas: list[float] = []
        for repetition in repetitions:
            stress = estimate_lookup[(series, stress_variant, sample_size, repetition, method, quantity)]
            control_row = estimate_lookup.get(
                (series, control, sample_size, repetition, method, quantity)
            )
            if control_row is None:
                continue
            stress_error = _optional_float(stress["absolute_error"])
            control_error = _optional_float(control_row["absolute_error"])
            if stress_error is not None and control_error is not None:
                error_deltas.append(stress_error - control_error)
            stress_width = _optional_float(stress["width"])
            control_width = _optional_float(control_row["width"])
            if stress_width is not None and control_width is not None:
                width_deltas.append(stress_width - control_width)
            stress_diagnostic = diagnostic_lookup.get((series, stress_variant, sample_size, repetition))
            control_diagnostic = diagnostic_lookup.get((series, control, sample_size, repetition))
            if stress_diagnostic is not None and control_diagnostic is not None:
                flag_deltas.append(
                    float(_as_bool(stress_diagnostic["flagged"]))
                    - float(_as_bool(control_diagnostic["flagged"]))
                )
        low, high = _bootstrap_mean_ci(
            error_deltas,
            series,
            stress_variant,
            sample_size,
            method,
            quantity,
        )
        result.append(
            {
                "series": series,
                "control_variant": control,
                "stress_variant": stress_variant,
                "sample_size": sample_size,
                "method": method,
                "quantity": quantity,
                "prediction_pairs": len(error_deltas),
                "mean_absolute_error_delta_stress_minus_control": _mean(error_deltas),
                "mean_error_delta_ci95_low": low,
                "mean_error_delta_ci95_high": high,
                "interval_pairs": len(width_deltas),
                "mean_width_delta_stress_minus_control": _mean(width_deltas),
                "diagnostic_pairs": len(flag_deltas),
                "mean_flag_delta_stress_minus_control": _mean(flag_deltas),
            }
        )
    return result


def quality_metrics(
    estimate_rows: list[dict[str, Any]],
    diagnostic_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
) -> dict[str, int]:
    invalid = sum(
        1
        for row in estimate_rows
        if _as_bool(row["interval_available"])
        and (
            not math.isfinite(float(row["lower"]))
            or not math.isfinite(float(row["upper"]))
            or float(row["lower"]) > float(row["upper"])
        )
    )
    guarded_survival = sum(
        1
        for row in estimate_rows
        if row["method"] == METHOD_PROPOSED_GUARDED
        and _as_bool(row["diagnostic_flagged"])
        and (_as_bool(row["prediction_available"]) or _as_bool(row["interval_available"]))
    )
    lookup = {
        (
            row["series"],
            row["variant"],
            int(row["repetition"]),
            int(row["sample_size"]),
            row["quantity"],
            row["method"],
        ): row
        for row in estimate_rows
    }
    mismatches = 0
    for key, row in lookup.items():
        if key[-1] != METHOD_PROPOSED_RAW:
            continue
        other = lookup.get((*key[:-1], METHOD_B3))
        first = _optional_float(row["point"])
        second = None if other is None else _optional_float(other["point"])
        if first is not None and second is not None and abs(first - second) > 1e-10:
            mismatches += 1
    readiness_control_flags = sum(
        1
        for row in diagnostic_rows
        if row["series"] == "readiness_lag"
        and not _as_bool(row["is_stress"])
        and _as_bool(row["flagged"])
    )
    nonfinite_truths = sum(
        1 for row in estimate_rows if not math.isfinite(float(row["truth"]))
    )
    guarded_decisions = sum(
        1
        for row in decision_rows
        if row["method"] == METHOD_PROPOSED_GUARDED
        and _as_bool(row["diagnostic_flagged"])
        and _as_bool(row["decision_available"])
    )
    controls = {
        str(row["series"]): str(row["variant"])
        for row in estimate_rows
        if not _as_bool(row["is_stress"])
    }
    estimate_keys = {
        (
            str(row["series"]),
            str(row["variant"]),
            int(row["repetition"]),
            int(row["sample_size"]),
            str(row["method"]),
            str(row["quantity"]),
        )
        for row in estimate_rows
    }
    missing_pairs = sum(
        1
        for row in estimate_rows
        if _as_bool(row["is_stress"])
        and (
            str(row["series"]),
            controls[str(row["series"])],
            int(row["repetition"]),
            int(row["sample_size"]),
            str(row["method"]),
            str(row["quantity"]),
        )
        not in estimate_keys
    )
    return {
        "invalid_intervals": invalid,
        "guarded_outputs_after_diagnostic_rejection": guarded_survival,
        "guarded_decisions_after_diagnostic_rejection": guarded_decisions,
        "b3_proposed_point_mismatches": mismatches,
        "readiness_control_implication_failures": readiness_control_flags,
        "missing_paired_control_estimates": missing_pairs,
        "nonfinite_truths": nonfinite_truths,
    }


def _selected_series(
    config: StressExperimentConfig,
    names: tuple[str, ...] | None,
) -> tuple[StressSeries, ...]:
    if names is None:
        return config.series
    lookup = {item.id: item for item in config.series}
    unknown = set(names) - set(lookup)
    if unknown:
        raise ValueError(f"unknown stress series: {sorted(unknown)}")
    return tuple(lookup[name] for name in names)


def run_stress_experiment(
    config: StressExperimentConfig,
    config_path: str | Path,
    output_directory: str | Path,
    series_names: tuple[str, ...] | None = None,
    repetitions: int | None = None,
    sample_sizes: tuple[int, ...] | None = None,
    bootstrap_replicates: int | None = None,
) -> dict[str, Any]:
    series = _selected_series(config, series_names)
    actual_repetitions = config.repetitions if repetitions is None else repetitions
    actual_sizes = config.sample_sizes if sample_sizes is None else sample_sizes
    actual_bootstrap = (
        config.block_bootstrap_replicates
        if bootstrap_replicates is None
        else bootstrap_replicates
    )
    if actual_repetitions <= 0 or actual_bootstrap <= 0:
        raise ValueError("stress repetitions and bootstrap replicates must be positive")
    if not actual_sizes or tuple(sorted(set(actual_sizes))) != actual_sizes:
        raise ValueError("stress sample sizes must be strictly increasing")
    dataset_count = (
        sum(len(item.variants) for item in series)
        * actual_repetitions
        * len(actual_sizes)
    )
    if (
        os.environ.get("GITHUB_ACTIONS", "").lower() != "true"
        and dataset_count > config.local_smoke_max_dataset_fits
    ):
        raise RuntimeError(
            "stress experiment exceeds the local smoke budget "
            f"({dataset_count} > {config.local_smoke_max_dataset_fits}); "
            "run it through GitHub Actions"
        )
    base_scenario = next(
        item for item in config.transfer.scenarios if item.id == config.base_scenario
    )
    model = base_scenario.model
    estimate_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    campaign_rows: list[dict[str, Any]] = []
    for item in series:
        if item.id == "exporter_loss":
            _run_exporter(
                config,
                item,
                model,
                actual_repetitions,
                actual_sizes,
                estimate_rows,
                diagnostic_rows,
                decision_rows,
                campaign_rows,
            )
        elif item.id == "temporal_bursts":
            _run_temporal(
                config,
                item,
                model,
                actual_repetitions,
                actual_sizes,
                actual_bootstrap,
                estimate_rows,
                diagnostic_rows,
                decision_rows,
                campaign_rows,
            )
        elif item.id == "wrong_domain_map":
            _run_wrong_domain(
                config,
                item,
                model,
                actual_repetitions,
                actual_sizes,
                estimate_rows,
                diagnostic_rows,
                decision_rows,
                campaign_rows,
            )
        elif item.id == "rare_branch":
            _run_rare_branch(
                config,
                item,
                actual_repetitions,
                actual_sizes,
                estimate_rows,
                diagnostic_rows,
                decision_rows,
                campaign_rows,
            )
        elif item.id == "readiness_lag":
            _run_readiness(
                config,
                item,
                model,
                actual_repetitions,
                actual_sizes,
                actual_bootstrap,
                estimate_rows,
                diagnostic_rows,
                decision_rows,
                campaign_rows,
            )
        else:
            raise AssertionError(f"unhandled stress series {item.id}")

    summary = summarize_estimates(estimate_rows)
    diagnostic_summary = summarize_diagnostics(diagnostic_rows)
    decision_summary = summarize_decisions(decision_rows)
    paired = paired_effects(estimate_rows, diagnostic_rows)
    quality = quality_metrics(estimate_rows, diagnostic_rows, decision_rows)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "estimates.csv", ESTIMATE_FIELDS, estimate_rows)
    _write_csv(output / "diagnostics.csv", DIAGNOSTIC_FIELDS, diagnostic_rows)
    _write_csv(output / "decisions.csv", DECISION_FIELDS, decision_rows)
    _write_csv(output / "campaigns.csv", CAMPAIGN_FIELDS, campaign_rows)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary)
    _write_csv(
        output / "diagnostic_summary.csv",
        DIAGNOSTIC_SUMMARY_FIELDS,
        diagnostic_summary,
    )
    _write_csv(
        output / "decision_summary.csv",
        DECISION_SUMMARY_FIELDS,
        decision_summary,
    )
    _write_csv(output / "paired_effects.csv", PAIRED_FIELDS, paired)
    manifest = {
        "schema_version": 1,
        "kind": "directed_stress_experiment_shard",
        "experiment_id": config.id,
        "config_sha256": file_sha256(config_path),
        "transfer_config_sha256": file_sha256(config.transfer_config_path),
        "seed": config.seed,
        "series": [item.id for item in series],
        "variants": {
            item.id: [variant.id for variant in item.variants] for item in series
        },
        "repetitions": actual_repetitions,
        "sample_sizes": list(actual_sizes),
        "block_bootstrap_replicates": actual_bootstrap,
        "block_length": config.block_length,
        "methods": list(METHODS),
        "quality": quality,
        "row_counts": {
            "estimates": len(estimate_rows),
            "diagnostics": len(diagnostic_rows),
            "decisions": len(decision_rows),
            "campaigns": len(campaign_rows),
            "summary": len(summary),
            "diagnostic_summary": len(diagnostic_summary),
            "decision_summary": len(decision_summary),
            "paired_effects": len(paired),
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


def aggregate_stress_experiment(
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    raw_names = ("estimates", "diagnostics", "decisions", "campaigns")
    paths = {name: sorted(root.rglob(f"{name}.csv")) for name in raw_names}
    if any(not values for values in paths.values()):
        raise ValueError("input root does not contain complete stress shards")
    tables = {name: _read_csvs(values) for name, values in paths.items()}
    summary = summarize_estimates(tables["estimates"])
    diagnostic_summary = summarize_diagnostics(tables["diagnostics"])
    decision_summary = summarize_decisions(tables["decisions"])
    paired = paired_effects(tables["estimates"], tables["diagnostics"])
    quality = quality_metrics(
        tables["estimates"],
        tables["diagnostics"],
        tables["decisions"],
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    fields = {
        "estimates": ESTIMATE_FIELDS,
        "diagnostics": DIAGNOSTIC_FIELDS,
        "decisions": DECISION_FIELDS,
        "campaigns": CAMPAIGN_FIELDS,
    }
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", fields[name], rows)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary)
    _write_csv(
        output / "diagnostic_summary.csv",
        DIAGNOSTIC_SUMMARY_FIELDS,
        diagnostic_summary,
    )
    _write_csv(
        output / "decision_summary.csv",
        DECISION_SUMMARY_FIELDS,
        decision_summary,
    )
    _write_csv(output / "paired_effects.csv", PAIRED_FIELDS, paired)
    source_manifests = sorted(root.rglob("manifest.json"))
    manifest = {
        "schema_version": 1,
        "kind": "directed_stress_experiment_aggregate",
        "experiment_id": tables["estimates"][0]["experiment_id"],
        "source_shards": len(source_manifests),
        "series": sorted({row["series"] for row in tables["estimates"]}),
        "methods": list(METHODS),
        "quality": quality,
        "row_counts": {
            **{name: len(rows) for name, rows in tables.items()},
            "summary": len(summary),
            "diagnostic_summary": len(diagnostic_summary),
            "decision_summary": len(decision_summary),
            "paired_effects": len(paired),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
