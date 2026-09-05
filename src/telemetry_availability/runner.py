from __future__ import annotations

import csv
import hashlib
import json
import os
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .config import ExperimentConfig
from .diagnostics import diagnose_identifiability
from .estimators import fit_log_moments
from .moments import (
    canonical_moment_estimates,
    estimate_moments,
    moment_matrix,
    structural_moment_rows,
)
from .observation import ObservationPolicy, simulate_batch
from .provenance import environment_manifest, file_sha256


RUN_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "structural_rank",
    "empirical_rank",
    "estimation_rank",
    "parameter_count",
    "structural_full_rank",
    "empirical_full_rank",
    "structural_condition_number",
    "empirical_condition_number",
    "moment_count",
    "distinct_moment_count",
    "usable_moment_count",
    "minimum_moment_observations",
    "fit_status",
    "full_rank_diagnosis_correct",
    "target_diagnosis_correct",
)

PARAMETER_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "factor",
    "role",
    "truth",
    "structurally_identifiable",
    "empirically_identifiable",
    "estimate",
    "signed_error",
    "absolute_error",
    "false_confident_estimate",
)

TARGET_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "target",
    "truth",
    "structurally_identifiable",
    "empirically_identifiable",
    "estimate",
    "signed_error",
    "absolute_error",
)

MOMENT_FIELDS = (
    "experiment_id",
    "family",
    "observation_mode",
    "repetition",
    "sample_size",
    "observable_ids",
    "factor_ids",
    "order",
    "observation_count",
    "estimate",
    "truth",
    "signed_error",
    "absolute_error",
)

SUMMARY_FIELDS = (
    "family",
    "observation_mode",
    "sample_size",
    "datasets",
    "structural_rank",
    "parameter_count",
    "structural_full_rank",
    "full_rank_diagnosis_accuracy",
    "target_diagnosis_accuracy",
    "fit_completion_rate",
    "mean_empirical_rank",
    "mean_moment_count",
    "mean_distinct_moment_count",
    "parameter_estimate_rate",
    "parameter_mae",
    "parameter_signed_bias",
    "false_confident_parameter_rate",
    "target_estimate_rate",
    "target_mae",
    "target_signed_bias",
)


def stable_seed(base_seed: int, *parts: object) -> int:
    payload = ":".join((str(base_seed), *(str(part) for part in parts))).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], byteorder="big", signed=False)


def _selected(items: Iterable[Any], names: tuple[str, ...] | None, label: str) -> tuple[Any, ...]:
    materialized = tuple(items)
    if not names:
        return materialized
    lookup = {item.id: item for item in materialized}
    unknown = set(names) - set(lookup)
    if unknown:
        raise ValueError(f"unknown {label}: {sorted(unknown)}")
    return tuple(lookup[name] for name in names)


def _serialize(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialize(row.get(field)) for field in fields})


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _as_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _mean(values: Iterable[float | None]) -> float | None:
    available = [float(value) for value in values if value is not None]
    return float(statistics.fmean(available)) if available else None


def summarize_rows(
    runs: list[dict[str, Any]],
    parameters: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped_runs: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    grouped_parameters: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    grouped_targets: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)

    def key(row: dict[str, Any]) -> tuple[str, str, int]:
        return (str(row["family"]), str(row["observation_mode"]), int(row["sample_size"]))

    for row in runs:
        grouped_runs[key(row)].append(row)
    for row in parameters:
        grouped_parameters[key(row)].append(row)
    for row in targets:
        grouped_targets[key(row)].append(row)

    summary: list[dict[str, Any]] = []
    for group_key in sorted(grouped_runs):
        run_group = grouped_runs[group_key]
        parameter_group = grouped_parameters[group_key]
        target_group = grouped_targets[group_key]
        identifiable_parameters = [
            row for row in parameter_group if _as_bool(row["structurally_identifiable"])
        ]
        unidentifiable_parameters = [
            row for row in parameter_group if not _as_bool(row["structurally_identifiable"])
        ]
        parameter_estimates = [
            row for row in identifiable_parameters if _as_optional_float(row["estimate"]) is not None
        ]
        target_estimates = [
            row for row in target_group if _as_optional_float(row["estimate"]) is not None
        ]
        false_confident = sum(
            _as_bool(row["false_confident_estimate"]) for row in unidentifiable_parameters
        )

        summary.append(
            {
                "family": group_key[0],
                "observation_mode": group_key[1],
                "sample_size": group_key[2],
                "datasets": len(run_group),
                "structural_rank": int(run_group[0]["structural_rank"]),
                "parameter_count": int(run_group[0]["parameter_count"]),
                "structural_full_rank": _as_bool(run_group[0]["structural_full_rank"]),
                "full_rank_diagnosis_accuracy": _mean(
                    float(_as_bool(row["full_rank_diagnosis_correct"])) for row in run_group
                ),
                "target_diagnosis_accuracy": _mean(
                    float(_as_bool(row["target_diagnosis_correct"])) for row in run_group
                ),
                "fit_completion_rate": _mean(
                    float(str(row["fit_status"]) != "no_positive_moments") for row in run_group
                ),
                "mean_empirical_rank": _mean(float(row["empirical_rank"]) for row in run_group),
                "mean_moment_count": _mean(float(row["moment_count"]) for row in run_group),
                "mean_distinct_moment_count": _mean(
                    float(row["distinct_moment_count"]) for row in run_group
                ),
                "parameter_estimate_rate": (
                    len(parameter_estimates) / len(identifiable_parameters)
                    if identifiable_parameters
                    else None
                ),
                "parameter_mae": _mean(
                    _as_optional_float(row["absolute_error"]) for row in parameter_estimates
                ),
                "parameter_signed_bias": _mean(
                    _as_optional_float(row["signed_error"]) for row in parameter_estimates
                ),
                "false_confident_parameter_rate": (
                    false_confident / len(unidentifiable_parameters)
                    if unidentifiable_parameters
                    else 0.0
                ),
                "target_estimate_rate": (
                    len(target_estimates) / len(target_group) if target_group else None
                ),
                "target_mae": _mean(
                    _as_optional_float(row["absolute_error"]) for row in target_estimates
                ),
                "target_signed_bias": _mean(
                    _as_optional_float(row["signed_error"]) for row in target_estimates
                ),
            }
        )
    return summary


def run_experiment(
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
            "experiment exceeds the local smoke budget "
            f"({dataset_fits} > {config.local_smoke_max_dataset_fits} dataset fits); "
            "run it through the GitHub Actions experiment workflow"
        )

    run_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    moment_rows: list[dict[str, Any]] = []
    max_size = max(actual_sizes)

    for family in families:
        for policy in policies:
            structural_matrix = structural_moment_rows(
                family,
                policy,
                config.max_moment_order,
            )
            structural_report = diagnose_identifiability(family, structural_matrix)
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
                for sample_size in actual_sizes:
                    estimates = estimate_moments(
                        model=family,
                        batch=batch.prefix(sample_size),
                        max_order=config.max_moment_order,
                        min_observations=config.min_joint_observations,
                    )
                    distinct_estimates = canonical_moment_estimates(estimates)
                    empirical_matrix = moment_matrix(distinct_estimates, len(family.factors))
                    empirical_report = diagnose_identifiability(family, empirical_matrix)
                    positive_estimates = tuple(
                        item for item in distinct_estimates if item.value > 0.0
                    )
                    estimation_matrix = moment_matrix(positive_estimates, len(family.factors))
                    estimation_report = diagnose_identifiability(family, estimation_matrix)
                    fit = fit_log_moments(family, distinct_estimates, estimation_report)

                    target_diagnosis_correct = all(
                        empirical_report.target_identifiable[target.id]
                        == structural_report.target_identifiable[target.id]
                        for target in family.targets
                    )
                    counts = [item.observation_count for item in estimates]
                    base = {
                        "experiment_id": config.id,
                        "family": family.id,
                        "observation_mode": policy.id,
                        "repetition": repetition,
                        "sample_size": sample_size,
                    }
                    run_rows.append(
                        {
                            **base,
                            "structural_rank": structural_report.rank,
                            "empirical_rank": empirical_report.rank,
                            "estimation_rank": estimation_report.rank,
                            "parameter_count": len(family.factors),
                            "structural_full_rank": structural_report.full_rank,
                            "empirical_full_rank": empirical_report.full_rank,
                            "structural_condition_number": structural_report.condition_number,
                            "empirical_condition_number": empirical_report.condition_number,
                            "moment_count": len(estimates),
                            "distinct_moment_count": len(distinct_estimates),
                            "usable_moment_count": fit.usable_moment_count,
                            "minimum_moment_observations": min(counts) if counts else None,
                            "fit_status": fit.status,
                            "full_rank_diagnosis_correct": (
                                empirical_report.full_rank == structural_report.full_rank
                            ),
                            "target_diagnosis_correct": target_diagnosis_correct,
                        }
                    )

                    for moment in estimates:
                        truth = family.exact_moment(moment.observable_ids)
                        signed_error = moment.value - truth
                        factor_ids = tuple(
                            factor_id
                            for factor_id, present in zip(
                                family.factor_ids,
                                moment.factor_vector,
                                strict=True,
                            )
                            if present
                        )
                        moment_rows.append(
                            {
                                **base,
                                "observable_ids": "&".join(moment.observable_ids),
                                "factor_ids": "&".join(factor_ids),
                                "order": len(moment.observable_ids),
                                "observation_count": moment.observation_count,
                                "estimate": moment.value,
                                "truth": truth,
                                "signed_error": signed_error,
                                "absolute_error": abs(signed_error),
                            }
                        )

                    for factor in family.factors:
                        estimate = fit.parameter_estimates[factor.id]
                        signed_error = None if estimate is None else estimate - factor.probability
                        parameter_rows.append(
                            {
                                **base,
                                "factor": factor.id,
                                "role": factor.role,
                                "truth": factor.probability,
                                "structurally_identifiable": structural_report.parameter_identifiable[factor.id],
                                "empirically_identifiable": estimation_report.parameter_identifiable[factor.id],
                                "estimate": estimate,
                                "signed_error": signed_error,
                                "absolute_error": None if signed_error is None else abs(signed_error),
                                "false_confident_estimate": (
                                    estimate is not None
                                    and not structural_report.parameter_identifiable[factor.id]
                                ),
                            }
                        )

                    for target in family.targets:
                        estimate = fit.target_estimates[target.id]
                        truth = family.exact_target(target.id)
                        signed_error = None if estimate is None else estimate - truth
                        target_rows.append(
                            {
                                **base,
                                "target": target.id,
                                "truth": truth,
                                "structurally_identifiable": structural_report.target_identifiable[target.id],
                                "empirically_identifiable": estimation_report.target_identifiable[target.id],
                                "estimate": estimate,
                                "signed_error": signed_error,
                                "absolute_error": None if signed_error is None else abs(signed_error),
                            }
                        )

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    summary_rows = summarize_rows(run_rows, parameter_rows, target_rows)
    _write_csv(output / "runs.csv", RUN_FIELDS, run_rows)
    _write_csv(output / "parameters.csv", PARAMETER_FIELDS, parameter_rows)
    _write_csv(output / "targets.csv", TARGET_FIELDS, target_rows)
    _write_csv(output / "moments.csv", MOMENT_FIELDS, moment_rows)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary_rows)

    manifest = {
        "schema_version": 1,
        "kind": "experiment_shard",
        "experiment_id": config.id,
        "config_sha256": file_sha256(config_path),
        "seed": config.seed,
        "families": [item.id for item in families],
        "observation_modes": [item.id for item in policies],
        "repetitions": actual_repetitions,
        "sample_sizes": list(actual_sizes),
        "max_moment_order": config.max_moment_order,
        "min_joint_observations": config.min_joint_observations,
        "local_smoke_max_dataset_fits": config.local_smoke_max_dataset_fits,
        "row_counts": {
            "runs": len(run_rows),
            "parameters": len(parameter_rows),
            "targets": len(target_rows),
            "moments": len(moment_rows),
            "summary": len(summary_rows),
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


def aggregate_results(input_root: str | Path, output_directory: str | Path) -> dict[str, Any]:
    root = Path(input_root)
    run_paths = sorted(root.rglob("runs.csv"))
    parameter_paths = sorted(root.rglob("parameters.csv"))
    target_paths = sorted(root.rglob("targets.csv"))
    moment_paths = sorted(root.rglob("moments.csv"))
    if not run_paths or not parameter_paths or not target_paths or not moment_paths:
        raise ValueError("input root does not contain complete experiment shards")

    runs = _read_csvs(run_paths)
    parameters = _read_csvs(parameter_paths)
    targets = _read_csvs(target_paths)
    moments = _read_csvs(moment_paths)
    summary = summarize_rows(runs, parameters, targets)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "runs.csv", RUN_FIELDS, runs)
    _write_csv(output / "parameters.csv", PARAMETER_FIELDS, parameters)
    _write_csv(output / "targets.csv", TARGET_FIELDS, targets)
    _write_csv(output / "moments.csv", MOMENT_FIELDS, moments)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary)

    manifest = {
        "schema_version": 1,
        "kind": "aggregate",
        "source_shards": len(run_paths),
        "row_counts": {
            "runs": len(runs),
            "parameters": len(parameters),
            "targets": len(targets),
            "moments": len(moments),
            "summary": len(summary),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
