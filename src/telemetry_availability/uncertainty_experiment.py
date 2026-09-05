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
from scipy.stats import norm

from .likelihood import compress_observed_patterns, fit_exact_observed_likelihood
from .observation import ObservationPolicy, simulate_batch
from .provenance import environment_manifest, file_sha256
from .runner import _selected, _write_csv, stable_seed
from .transfer import TARGET_ADD, TARGET_CURRENT, TARGET_SPLIT
from .transfer_identifiability import PROVED_IDENTIFIABLE, diagnose_transfer_targets
from .uncertainty import (
    CHOICE_DIFFERENCE,
    DELTA_ADD,
    DELTA_SPLIT,
    QUANTITIES,
    IntervalEstimate,
    clopper_pearson_interval,
    extract_simultaneous_evidence,
    likelihood_wald_ranges,
    quantity_values,
    simultaneous_target_ranges,
    simulation_only_ranges,
)
from .uncertainty_config import UncertaintyExperimentConfig


METHOD_PROPOSED = "proposed_simultaneous_observation_set"
METHOD_WALD = "b3_marginal_wald"
METHOD_WALD_SIMULTANEOUS = "b3_bonferroni_wald"
METHOD_B0 = "b0_direct_endpoint_clopper_pearson"
METHOD_A5 = "a5_fixed_input_simulation_only"
METHODS = (
    METHOD_PROPOSED,
    METHOD_WALD,
    METHOD_WALD_SIMULTANEOUS,
    METHOD_B0,
    METHOD_A5,
)

INTERVAL_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "quantity",
    "identifiability_status",
    "interval_status",
    "simultaneous_claim",
    "truth",
    "point",
    "lower",
    "upper",
    "width",
    "available",
    "covers_truth",
)

SET_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "constraint_count",
    "observable_set_covers_truth",
    "target_set_covers_all_truth",
    "transfer_identifiability_status",
    "domain_a_status",
    "domain_a_boxes",
    "domain_a_visited_nodes",
    "domain_a_truncated",
    "domain_b_status",
    "domain_b_boxes",
    "domain_b_visited_nodes",
    "domain_b_truncated",
    "runtime_seconds",
    "likelihood_status",
)

CONSTRAINT_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "domain",
    "statistic",
    "observable_ids",
    "successes",
    "trials",
    "estimate",
    "lower",
    "upper",
    "truth",
    "covers_truth",
)

DECISION_FIELDS = (
    "experiment_id",
    "scenario",
    "observation_mode",
    "repetition",
    "sample_size",
    "method",
    "true_best",
    "selected",
    "decision_available",
    "correct",
    "regret",
    "difference_truth",
    "difference_lower",
    "difference_upper",
    "difference_covers_truth",
)

INTERVAL_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "method",
    "quantity",
    "identifiability_status",
    "datasets",
    "interval_rate",
    "coverage_when_available",
    "coverage_ci95_low",
    "coverage_ci95_high",
    "mean_width",
    "median_width",
)

SET_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
    "sample_size",
    "datasets",
    "observable_simultaneous_coverage",
    "observable_coverage_ci95_low",
    "observable_coverage_ci95_high",
    "target_simultaneous_coverage",
    "target_coverage_ci95_low",
    "target_coverage_ci95_high",
    "mean_constraint_count",
    "mean_runtime_seconds",
    "truncation_rate",
    "empty_set_rate",
)

DECISION_SUMMARY_FIELDS = (
    "scenario",
    "observation_mode",
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
    z = float(norm.ppf(0.975))
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    half = z / denominator * np.sqrt(
        proportion * (1.0 - proportion) / trials
        + z * z / (4.0 * trials * trials)
    )
    return float(center - half), float(center + half)


def _quantity_identification(
    diagnostics: dict[str, Any],
    quantity: str,
) -> str:
    if quantity == TARGET_CURRENT:
        return diagnostics[TARGET_CURRENT].status
    if quantity in {TARGET_ADD, DELTA_ADD}:
        return diagnostics[TARGET_ADD].status
    return diagnostics[TARGET_SPLIT].status


def _unavailable(status: str) -> dict[str, IntervalEstimate]:
    return {
        quantity: IntervalEstimate(None, None, None, status)
        for quantity in QUANTITIES
    }


def _direct_endpoint_interval(
    model: Any,
    batch: Any,
    confidence_level: float,
) -> dict[str, IntervalEstimate]:
    position = next(
        index
        for index, observable in enumerate(model.observables)
        if observable.id == "current_success"
    )
    observed = batch.observed[:, position]
    trials = int(np.count_nonzero(observed))
    if trials == 0:
        return _unavailable("direct_endpoint_unavailable")
    successes = int(np.count_nonzero(observed & batch.values[:, position]))
    lower, upper = clopper_pearson_interval(
        successes,
        trials,
        confidence_level,
    )
    result = _unavailable("direct_endpoint_transfer_unavailable")
    result[TARGET_CURRENT] = IntervalEstimate(
        lower,
        upper,
        successes / trials,
        "direct_endpoint_clopper_pearson",
    )
    return result


def _interval_rows(
    base: dict[str, Any],
    method: str,
    intervals: dict[str, IntervalEstimate],
    truths: dict[str, float],
    diagnostics: dict[str, Any],
    simultaneous_claim: str,
    point_override: dict[str, float | None] | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for quantity in QUANTITIES:
        interval = intervals[quantity]
        available = interval.lower is not None and interval.upper is not None
        point = (
            interval.point
            if point_override is None
            else point_override.get(quantity, interval.point)
        )
        covers = (
            None
            if not available
            else interval.lower <= truths[quantity] <= interval.upper
        )
        rows.append(
            {
                **base,
                "method": method,
                "quantity": quantity,
                "identifiability_status": _quantity_identification(
                    diagnostics,
                    quantity,
                ),
                "interval_status": interval.status,
                "simultaneous_claim": simultaneous_claim,
                "truth": truths[quantity],
                "point": point,
                "lower": interval.lower,
                "upper": interval.upper,
                "width": interval.width,
                "available": available,
                "covers_truth": covers,
            }
        )
    return rows


def _decision_row(
    base: dict[str, Any],
    method: str,
    interval: IntervalEstimate,
    truths: dict[str, float],
) -> dict[str, Any]:
    selected: str | None = None
    if interval.lower is not None and interval.upper is not None:
        if interval.lower > 0.0:
            selected = TARGET_SPLIT
        elif interval.upper < 0.0:
            selected = TARGET_ADD
    true_best = TARGET_SPLIT if truths[CHOICE_DIFFERENCE] > 0.0 else TARGET_ADD
    correct = None if selected is None else selected == true_best
    regret = (
        None
        if selected is None
        else max(truths[TARGET_SPLIT], truths[TARGET_ADD]) - truths[selected]
    )
    covers = (
        None
        if interval.lower is None or interval.upper is None
        else interval.lower
        <= truths[CHOICE_DIFFERENCE]
        <= interval.upper
    )
    return {
        **base,
        "method": method,
        "true_best": true_best,
        "selected": selected,
        "decision_available": selected is not None,
        "correct": correct,
        "regret": regret,
        "difference_truth": truths[CHOICE_DIFFERENCE],
        "difference_lower": interval.lower,
        "difference_upper": interval.upper,
        "difference_covers_truth": covers,
    }


def summarize_intervals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["scenario"]),
            str(row["observation_mode"]),
            int(row["sample_size"]),
            str(row["method"]),
            str(row["quantity"]),
            str(row["identifiability_status"]),
        )
        grouped[key].append(row)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        available = [row for row in group if _as_bool(row["available"])]
        covered = sum(_as_bool(row["covers_truth"]) for row in available)
        low, high = _wilson(covered, len(available))
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "method": key[3],
                "quantity": key[4],
                "identifiability_status": key[5],
                "datasets": len(group),
                "interval_rate": len(available) / len(group),
                "coverage_when_available": (
                    covered / len(available) if available else None
                ),
                "coverage_ci95_low": low,
                "coverage_ci95_high": high,
                "mean_width": _mean(
                    _optional_float(row["width"]) for row in available
                ),
                "median_width": _median(
                    _optional_float(row["width"]) for row in available
                ),
            }
        )
    return result


def summarize_sets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["scenario"]),
                str(row["observation_mode"]),
                int(row["sample_size"]),
            )
        ].append(row)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        observable_covered = sum(
            _as_bool(row["observable_set_covers_truth"]) for row in group
        )
        target_covered = sum(
            _as_bool(row["target_set_covers_all_truth"]) for row in group
        )
        observable_ci = _wilson(observable_covered, len(group))
        target_ci = _wilson(target_covered, len(group))
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "datasets": len(group),
                "observable_simultaneous_coverage": observable_covered / len(group),
                "observable_coverage_ci95_low": observable_ci[0],
                "observable_coverage_ci95_high": observable_ci[1],
                "target_simultaneous_coverage": target_covered / len(group),
                "target_coverage_ci95_low": target_ci[0],
                "target_coverage_ci95_high": target_ci[1],
                "mean_constraint_count": _mean(
                    float(row["constraint_count"]) for row in group
                ),
                "mean_runtime_seconds": _mean(
                    _optional_float(row["runtime_seconds"]) for row in group
                ),
                "truncation_rate": _mean(
                    float(
                        _as_bool(row["domain_a_truncated"])
                        or _as_bool(row["domain_b_truncated"])
                    )
                    for row in group
                ),
                "empty_set_rate": _mean(
                    float(
                        str(row["domain_a_status"]) == "empty"
                        or str(row["domain_b_status"]) == "empty"
                    )
                    for row in group
                ),
            }
        )
    return result


def summarize_decisions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row["scenario"]),
                str(row["observation_mode"]),
                int(row["sample_size"]),
                str(row["method"]),
            )
        ].append(row)
    result = []
    for key in sorted(grouped):
        group = grouped[key]
        decided = [row for row in group if _as_bool(row["decision_available"])]
        correct = sum(_as_bool(row["correct"]) for row in decided)
        interval = _wilson(correct, len(decided))
        wrong = len(decided) - correct
        result.append(
            {
                "scenario": key[0],
                "observation_mode": key[1],
                "sample_size": key[2],
                "method": key[3],
                "datasets": len(group),
                "decision_coverage": len(decided) / len(group),
                "accuracy_when_decided": (
                    correct / len(decided) if decided else None
                ),
                "accuracy_ci95_low": interval[0],
                "accuracy_ci95_high": interval[1],
                "wrong_decision_rate": wrong / len(group),
                "mean_regret_when_decided": _mean(
                    _optional_float(row["regret"]) for row in decided
                ),
            }
        )
    return result


def quality_metrics(
    interval_rows: list[dict[str, Any]],
    set_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
) -> dict[str, int]:
    invalid = sum(
        _as_bool(row["available"])
        and (
            _optional_float(row["lower"]) is None
            or _optional_float(row["upper"]) is None
            or float(row["lower"]) > float(row["upper"])
        )
        for row in interval_rows
    )
    enclosure_failures = sum(
        _as_bool(row["observable_set_covers_truth"])
        and not _as_bool(row["target_set_covers_all_truth"])
        for row in set_rows
    )
    unsafe_decisions = sum(
        str(row["method"]) == METHOD_PROPOSED
        and _as_bool(row["difference_covers_truth"])
        and _as_bool(row["decision_available"])
        and not _as_bool(row["correct"])
        for row in decision_rows
    )
    trace_narrowing = sum(
        str(row["method"]) == METHOD_PROPOSED
        and str(row["observation_mode"]) == "trace_only"
        and str(row["quantity"]) in {TARGET_SPLIT, CHOICE_DIFFERENCE}
        and (
            float(row["lower"]) != (-1.0 if row["quantity"] == CHOICE_DIFFERENCE else 0.0)
            or float(row["upper"]) != 1.0
        )
        for row in interval_rows
    )
    return {
        "invalid_intervals": invalid,
        "outer_enclosure_failures_when_observable_truth_covered": enclosure_failures,
        "unsafe_proposed_decisions_when_choice_covered": unsafe_decisions,
        "trace_only_transfer_narrowing_failures": trace_narrowing,
    }


def run_uncertainty_experiment(
    config: UncertaintyExperimentConfig,
    config_path: str | Path,
    output_directory: str | Path,
    scenario_names: tuple[str, ...] | None = None,
    mode_names: tuple[str, ...] | None = None,
    repetitions: int | None = None,
    sample_sizes: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    transfer = config.transfer
    scenarios = _selected(transfer.scenarios, scenario_names, "scenarios")
    policies: tuple[ObservationPolicy, ...] = _selected(
        transfer.observation_modes,
        mode_names,
        "observation modes",
    )
    actual_repetitions = transfer.repetitions if repetitions is None else repetitions
    actual_sizes = transfer.sample_sizes if sample_sizes is None else sample_sizes
    if actual_repetitions <= 0:
        raise ValueError("repetitions must be positive")
    if not actual_sizes or tuple(sorted(set(actual_sizes))) != actual_sizes:
        raise ValueError("sample sizes must be strictly increasing")
    dataset_count = len(scenarios) * len(policies) * actual_repetitions * len(actual_sizes)
    if (
        os.environ.get("GITHUB_ACTIONS", "").lower() != "true"
        and dataset_count > config.local_smoke_max_dataset_fits
    ):
        raise RuntimeError(
            "uncertainty experiment exceeds the local smoke budget "
            f"({dataset_count} > {config.local_smoke_max_dataset_fits}); "
            "run it through GitHub Actions"
        )

    interval_rows: list[dict[str, Any]] = []
    set_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    constraint_rows: list[dict[str, Any]] = []
    max_size = max(actual_sizes)
    for scenario in scenarios:
        model = scenario.model
        truths = quantity_values(model)
        for policy in policies:
            diagnostics = diagnose_transfer_targets(policy)
            transfer_identified = (
                diagnostics[TARGET_SPLIT].status == PROVED_IDENTIFIABLE
                and diagnostics[TARGET_ADD].status == PROVED_IDENTIFIABLE
            )
            for repetition in range(actual_repetitions):
                batch = simulate_batch(
                    model,
                    max_size,
                    policy,
                    np.random.default_rng(
                        stable_seed(transfer.seed, scenario.id, repetition, "values")
                    ),
                    np.random.default_rng(
                        stable_seed(
                            transfer.seed,
                            scenario.id,
                            repetition,
                            policy.id,
                            "mask",
                        )
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
                    fit = fit_exact_observed_likelihood(
                        model,
                        table,
                        initial_probabilities=warm_start,
                    )
                    if fit.converged and fit.probabilities is not None:
                        warm_start = fit.probabilities
                    exact_parameters = (
                        dict(zip(model.factor_ids, fit.probabilities, strict=True))
                        if fit.converged and fit.probabilities is not None
                        else None
                    )
                    exact_points = (
                        quantity_values(model, exact_parameters)
                        if exact_parameters is not None
                        else {quantity: None for quantity in QUANTITIES}
                    )

                    range_start = time.perf_counter()
                    domain_a, domain_b, evidence = extract_simultaneous_evidence(
                        model,
                        prefix,
                        config.confidence_level,
                    )
                    proposed = simultaneous_target_ranges(
                        model,
                        policy,
                        domain_a,
                        domain_b,
                        config.branch_tolerance,
                        config.branch_max_nodes_per_domain,
                    )
                    range_seconds = time.perf_counter() - range_start
                    observable_covered = all(item.covers_truth for item in evidence)
                    target_covered = all(
                        interval.lower is not None
                        and interval.upper is not None
                        and interval.lower <= truths[quantity] <= interval.upper
                        for quantity, interval in proposed.intervals.items()
                    )
                    set_rows.append(
                        {
                            **base,
                            "constraint_count": len(evidence),
                            "observable_set_covers_truth": observable_covered,
                            "target_set_covers_all_truth": target_covered,
                            "transfer_identifiability_status": proposed.identification_status,
                            "domain_a_status": proposed.domain_a.status,
                            "domain_a_boxes": len(proposed.domain_a.boxes),
                            "domain_a_visited_nodes": proposed.domain_a.visited_nodes,
                            "domain_a_truncated": proposed.domain_a.truncated,
                            "domain_b_status": proposed.domain_b.status,
                            "domain_b_boxes": len(proposed.domain_b.boxes),
                            "domain_b_visited_nodes": proposed.domain_b.visited_nodes,
                            "domain_b_truncated": proposed.domain_b.truncated,
                            "runtime_seconds": range_seconds,
                            "likelihood_status": fit.status,
                        }
                    )
                    for item in evidence:
                        constraint_rows.append(
                            {
                                **base,
                                "domain": item.domain,
                                "statistic": item.statistic,
                                "observable_ids": "&".join(item.observable_ids),
                                "successes": item.successes,
                                "trials": item.trials,
                                "estimate": item.estimate,
                                "lower": item.lower,
                                "upper": item.upper,
                                "truth": item.truth,
                                "covers_truth": item.covers_truth,
                            }
                        )

                    proposed_points = {
                        quantity: (
                            exact_points[quantity]
                            if _quantity_identification(diagnostics, quantity)
                            == PROVED_IDENTIFIABLE
                            else None
                        )
                        for quantity in QUANTITIES
                    }
                    wald = (
                        likelihood_wald_ranges(
                            model,
                            table,
                            fit,
                            config.confidence_level,
                            simultaneous=False,
                        )
                        if transfer_identified
                        else _unavailable("structurally_ambiguous")
                    )
                    wald_simultaneous = (
                        likelihood_wald_ranges(
                            model,
                            table,
                            fit,
                            config.confidence_level,
                            simultaneous=True,
                        )
                        if transfer_identified
                        else _unavailable("structurally_ambiguous")
                    )
                    direct = _direct_endpoint_interval(
                        model,
                        prefix,
                        config.confidence_level,
                    )
                    simulation_only = simulation_only_ranges(
                        model,
                        exact_parameters if transfer_identified else None,
                        config.confidence_level,
                        config.simulation_episodes,
                    )
                    method_intervals = {
                        METHOD_PROPOSED: proposed.intervals,
                        METHOD_WALD: wald,
                        METHOD_WALD_SIMULTANEOUS: wald_simultaneous,
                        METHOD_B0: direct,
                        METHOD_A5: simulation_only,
                    }
                    simultaneous_claims = {
                        METHOD_PROPOSED: "finite_sample_familywise",
                        METHOD_WALD: "none_marginal_asymptotic",
                        METHOD_WALD_SIMULTANEOUS: "asymptotic_bonferroni",
                        METHOD_B0: "none_single_endpoint",
                        METHOD_A5: "conditional_mc_only",
                    }
                    for method in METHODS:
                        interval_rows.extend(
                            _interval_rows(
                                base,
                                method,
                                method_intervals[method],
                                truths,
                                diagnostics,
                                simultaneous_claims[method],
                                proposed_points if method == METHOD_PROPOSED else None,
                            )
                        )
                        decision_rows.append(
                            _decision_row(
                                base,
                                method,
                                method_intervals[method][CHOICE_DIFFERENCE],
                                truths,
                            )
                        )

    interval_summary = summarize_intervals(interval_rows)
    set_summary = summarize_sets(set_rows)
    decision_summary = summarize_decisions(decision_rows)
    quality = quality_metrics(interval_rows, set_rows, decision_rows)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "intervals.csv", INTERVAL_FIELDS, interval_rows)
    _write_csv(output / "sets.csv", SET_FIELDS, set_rows)
    _write_csv(output / "constraints.csv", CONSTRAINT_FIELDS, constraint_rows)
    _write_csv(output / "decisions.csv", DECISION_FIELDS, decision_rows)
    _write_csv(
        output / "interval_summary.csv",
        INTERVAL_SUMMARY_FIELDS,
        interval_summary,
    )
    _write_csv(output / "set_summary.csv", SET_SUMMARY_FIELDS, set_summary)
    _write_csv(
        output / "decision_summary.csv",
        DECISION_SUMMARY_FIELDS,
        decision_summary,
    )
    manifest = {
        "schema_version": 1,
        "kind": "uncertainty_experiment_shard",
        "experiment_id": config.id,
        "config_sha256": file_sha256(config_path),
        "transfer_config_sha256": file_sha256(config.transfer_config_path),
        "confidence_level": config.confidence_level,
        "branch_tolerance": config.branch_tolerance,
        "branch_max_nodes_per_domain": config.branch_max_nodes_per_domain,
        "simulation_episodes": config.simulation_episodes,
        "scenarios": [scenario.id for scenario in scenarios],
        "observation_modes": [policy.id for policy in policies],
        "repetitions": actual_repetitions,
        "sample_sizes": list(actual_sizes),
        "methods": list(METHODS),
        "quality": quality,
        "row_counts": {
            "intervals": len(interval_rows),
            "sets": len(set_rows),
            "constraints": len(constraint_rows),
            "decisions": len(decision_rows),
            "interval_summary": len(interval_summary),
            "set_summary": len(set_summary),
            "decision_summary": len(decision_summary),
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


def aggregate_uncertainty_experiment(
    input_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    root = Path(input_root)
    raw_names = ("intervals", "sets", "constraints", "decisions")
    paths = {name: sorted(root.rglob(f"{name}.csv")) for name in raw_names}
    if any(not values for values in paths.values()):
        raise ValueError("input root does not contain complete uncertainty shards")
    tables = {name: _read_csvs(values) for name, values in paths.items()}
    interval_summary = summarize_intervals(tables["intervals"])
    set_summary = summarize_sets(tables["sets"])
    decision_summary = summarize_decisions(tables["decisions"])
    quality = quality_metrics(
        tables["intervals"],
        tables["sets"],
        tables["decisions"],
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    fields = {
        "intervals": INTERVAL_FIELDS,
        "sets": SET_FIELDS,
        "constraints": CONSTRAINT_FIELDS,
        "decisions": DECISION_FIELDS,
    }
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", fields[name], rows)
    _write_csv(
        output / "interval_summary.csv",
        INTERVAL_SUMMARY_FIELDS,
        interval_summary,
    )
    _write_csv(output / "set_summary.csv", SET_SUMMARY_FIELDS, set_summary)
    _write_csv(
        output / "decision_summary.csv",
        DECISION_SUMMARY_FIELDS,
        decision_summary,
    )
    manifest = {
        "schema_version": 1,
        "kind": "uncertainty_experiment_aggregate",
        "experiment_id": tables["sets"][0]["experiment_id"],
        "source_shards": len(paths["sets"]),
        "methods": list(METHODS),
        "quality": quality,
        "row_counts": {
            **{name: len(rows) for name, rows in tables.items()},
            "interval_summary": len(interval_summary),
            "set_summary": len(set_summary),
            "decision_summary": len(decision_summary),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
