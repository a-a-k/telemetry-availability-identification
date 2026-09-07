from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from .checkout_localization import _audit_selected_files, _period_metrics
from .checkout_routing_model import (
    FROZEN_ANALYSIS_FIELDS,
    _audit_locked_files,
    _expected_identities,
    _load_learner_cell,
    _selected_source_directories,
)
from .live_validation_analysis import (
    HealthTick,
    QualifiedCell,
    _near_transition,
    _nearest_tick,
    _stable_uniform,
    _transition_times,
    load_qualified_cell,
)
from .pmx_failure_semantics import (
    _audit_artifact_metadata,
    _audit_file,
    _commit,
    _list,
    _load_json,
    _object,
    _positive,
    _relative,
    _sha256,
    _string,
    _write_csv,
    _write_json,
)
from .pmx_performability import file_sha256
from .provenance import environment_manifest


class CheckoutTemporalFailoverError(ValueError):
    pass


REFERENCE_METHODS = (
    "m7_single_demand_or",
    "m9m_static_and",
    "m9m_trace_requirement",
    "m9m_two_client_affinity",
    "m7_b0_endpoint",
    "m7_b2_marginal_reference",
)
NEW_METHODS = (
    "source_500ms_failover",
    "learner_state_only",
    "temporal_logit_lower",
    "temporal_logit_midpoint",
    "temporal_logit_upper",
    "temporal_monotone_bins",
)
ALL_METHODS = (
    "m7_single_demand_or",
    "m9m_static_and",
    "m9m_trace_requirement",
    "m9m_two_client_affinity",
    *NEW_METHODS,
    "m7_b0_endpoint",
    "m7_b2_marginal_reference",
)
PRIMARY_METHOD = "temporal_logit_midpoint"
LEARNER_FILES = (
    "audit/boundary.json",
    "learner/deployment.json",
    "learner/health.csv",
    "learner/manifest.json",
    "learner/requests.csv",
)
REFERENCE_NAME = "frozen-predictor-references.csv"
REFERENCE_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "method",
    "prediction",
    "route_prediction",
    "residual_success_probability",
)
M9M_REFERENCE_MAP = {
    "m7_single_demand_or": "m7_single_demand_or",
    "source_strict_round_robin_and": "m9m_static_and",
    "learner_trace_requirement_mixture": "m9m_trace_requirement",
    "source_two_client_affinity": "m9m_two_client_affinity",
    "m7_b2_marginal_reference": "m7_b2_marginal_reference",
}
AGE_VIEWS = ("lower", "midpoint", "upper")
CONDITIONAL_METHODS = (
    "conditional_path_or",
    "conditional_path_and",
    "conditional_source_500ms",
    "conditional_state_only",
    "conditional_temporal_lower",
    "conditional_temporal_midpoint",
    "conditional_temporal_upper",
    "conditional_monotone_bins",
    "conditional_b0_constant",
)


@dataclass(frozen=True)
class TemporalConfig:
    path: Path
    raw: Mapping[str, Any]
    profile: str
    operation: str
    placements: tuple[str, ...]
    failure_laws: tuple[str, ...]
    repetitions: tuple[int, ...]
    expected_cells: int
    alignment_tolerance: float
    transition_guard: int
    minimum_stable_test: int
    minimum_stable_calibration: int
    minimum_one_path: int
    minimum_episodes: int
    minimum_early: int
    minimum_late: int
    minimum_positive_cells: int
    interval_width_limit: float
    fit_range_tolerance: float
    probability_floor: float
    closure_margin: float
    interval_prediction_span: float
    resamples: int
    seed: int
    confidence_level: float
    job_timeout_minutes: int


@dataclass(frozen=True)
class TemporalRecord:
    success: int
    path_count: int
    episode_id: int
    lower_age: float
    midpoint_age: float
    upper_age: float


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CheckoutTemporalFailoverError(f"required CSV is missing: {path}")
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise CheckoutTemporalFailoverError(f"{label} must be numeric") from error
    if not math.isfinite(result):
        raise CheckoutTemporalFailoverError(f"{label} must be finite")
    return result


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise CheckoutTemporalFailoverError("cannot average empty values")
    return math.fsum(values) / len(values)


def _model_key(row: Mapping[str, Any]) -> tuple[str, str, str, int, str]:
    return (
        str(row["profile"]),
        str(row["placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
        str(row["method"]),
    )


def _identity(row: Mapping[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(row["profile"]),
        str(row["placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
    )


def _validate_file_locks(record: Mapping[str, Any], role: str) -> None:
    files = _object(record.get("files"), f"{role}.files")
    if not files:
        raise CheckoutTemporalFailoverError(f"{role} file locks are empty")
    for name, value in files.items():
        _relative(name, f"{role} path")
        item = _object(value, f"{role}.{name}")
        _positive(item.get("bytes"), f"{role}.{name}.bytes")
        _sha256(item.get("sha256"), f"{role}.{name}.sha256")


def load_temporal_config(path: str | Path) -> TemporalConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9N config"), "M9N root")
    expected = {
        "schema_version": 1,
        "id": "m9n_checkout_temporal_failover_model",
        "status": "frozen_before_first_m9n_remote_candidate_generation_or_evaluator_access",
        "diagnostic_only": True,
        "posthoc_to_m7_m9l_and_m9m": True,
        "changes_m7_or_m9m_predictions_or_scores": False,
        "new_live_collection": "forbidden",
        "pmx_invocation": "forbidden",
    }
    for key, value in expected.items():
        if root.get(key) != value:
            raise CheckoutTemporalFailoverError(f"M9N {key} differs")

    article = _object(root.get("article_position"), "article position")
    if any(value is not False for key, value in article.items() if key != "direction_remains_substantive" and key != "specified_model_calculation_supported"):
        raise CheckoutTemporalFailoverError("M9N article-position guard differs")
    if article.get("direction_remains_substantive") is not True or article.get("specified_model_calculation_supported") is not True:
        raise CheckoutTemporalFailoverError("M9N positive article guards differ")

    evidence = _object(root.get("evidence"), "evidence")
    if (
        evidence.get("m7_source_run_id") != 33990678586
        or _commit(evidence.get("m7_source_commit"), "M7 commit")
        != "b1925736f314da610debd23a586d7b7d00cae7ca"
    ):
        raise CheckoutTemporalFailoverError("M7 anchor differs")
    for role in ("m8a_preserved", "m8a_audit"):
        record = _object(evidence.get(role), role)
        _positive(record.get("artifact_id"), f"{role}.artifact_id")
        _positive(record.get("size_in_bytes"), f"{role}.size")
        _sha256(record.get("sha256"), f"{role}.sha256")
        _commit(record.get("head_sha"), f"{role}.head_sha")
    _validate_file_locks(_object(evidence["m8a_audit"], "M8A audit"), "m8a_audit")
    frozen = _object(evidence.get("frozen_analysis"), "frozen analysis")
    if set(frozen) != {"predictions.csv"}:
        raise CheckoutTemporalFailoverError("frozen analysis inventory differs")
    _validate_file_locks({"files": frozen}, "frozen_analysis")
    m9m = _object(evidence.get("m9m"), "M9M evidence")
    if (
        m9m.get("run_id") != 34089829138
        or _commit(m9m.get("head_sha"), "M9M commit")
        != "718bf3b1145be2c918980603039e6c784bf76d96"
        or m9m.get("status") != "checkout_trace_requirement_model_overshoots"
        or m9m.get("next_experiment") != "m9n_checkout_temporal_failover_model"
    ):
        raise CheckoutTemporalFailoverError("accepted M9M branch differs")
    for role in ("contract", "candidates", "evaluation"):
        record = _object(m9m.get(role), f"m9m.{role}")
        _positive(record.get("artifact_id"), f"m9m.{role}.artifact_id")
        _positive(record.get("size_in_bytes"), f"m9m.{role}.size")
        _sha256(record.get("sha256"), f"m9m.{role}.sha256")
        _validate_file_locks(record, f"m9m.{role}")

    source = _object(root.get("source_contract"), "source contract")
    if (
        source.get("operation") != "checkout"
        or source.get("successful_request_target_call_sites") != 3
        or source.get("routing_policy") != "haproxy_roundrobin"
        or source.get("backend_health_check_interval_seconds") != 0.5
        or source.get("backend_health_check_fall") != 1
        or source.get("backend_health_check_rise") != 1
        or source.get("ordinary_health_poll_seconds") != 1.0
        or source.get("literal_per_call_assignment_observed") is not False
        or source.get("persistent_connection_identity_observed") is not False
    ):
        raise CheckoutTemporalFailoverError("source timing contract differs")
    probe = _object(root.get("design_probe"), "design probe")
    if (
        probe.get("cells")
        != [
            ["opentelemetry_demo", "colocated", "N", 0],
            ["opentelemetry_demo", "split", "ND", 0],
        ]
        or probe.get("trees_read") != ["learner"]
        or probe.get("evaluator_files_read") != 0
        or probe.get("full_matrix_computed_locally") is not False
        or probe.get("probe_cells_are_not_independent_confirmation") is not True
    ):
        raise CheckoutTemporalFailoverError("design-probe disclosure differs")

    cohort = _object(root.get("cohort"), "cohort")
    placements = tuple(str(value) for value in _list(cohort.get("placements"), "placements"))
    laws = tuple(str(value) for value in _list(cohort.get("failure_laws"), "failure laws"))
    repetitions = tuple(int(value) for value in _list(cohort.get("repetitions"), "repetitions"))
    if (
        cohort.get("profile") != "opentelemetry_demo"
        or cohort.get("operation") != "checkout"
        or placements != ("colocated", "split")
        or laws != ("N", "ND")
        or repetitions != tuple(range(10))
        or cohort.get("expected_cells") != 40
        or cohort.get("expected_qualified_files_per_cell") != 9
        or cohort.get("expected_selected_files") != 360
        or cohort.get("evaluation_view") != "stable"
        or cohort.get("health_alignment_tolerance_seconds") != 1.25
        or cohort.get("transition_guard_seconds_each_side") != 1
        or cohort.get("minimum_stable_test_requests_per_cell") != 500
    ):
        raise CheckoutTemporalFailoverError("cohort differs")

    boundary = _object(root.get("information_boundary"), "information boundary")
    if (
        boundary.get("candidate_job_input")
        != "five_learner_boundary_files_per_cell_plus_sanitized_frozen_predictors"
        or tuple(boundary.get("learner_files", [])) != LEARNER_FILES
        or boundary.get("test_outcomes_accessed_during_fit") is not False
        or boundary.get("test_health_accessed_during_fit") is not False
        or boundary.get("candidate_artifact_precedes_evaluator_access") is not True
        or boundary.get("full_ordinary_calibration_health_is_additional_input") is not True
        or boundary.get("conditional_test_health_score_is_diagnostic_not_a_forecast") is not True
    ):
        raise CheckoutTemporalFailoverError("information boundary differs")

    temporal = _object(root.get("temporal_representation"), "temporal representation")
    if (
        temporal.get("age_views") != list(AGE_VIEWS)
        or temporal.get("primary_age_view") != "midpoint"
        or temporal.get("near_any_four_signal_transition_excluded_seconds_each_side") != 1
        or temporal.get("source_delay_seconds") != 0.5
        or temporal.get("monotone_bin_edges_seconds") != [0, 1, 2, 4, 8, 23]
        or temporal.get("late_recovery_threshold_seconds") != 4
        or temporal.get("interval_width_limit_seconds") != 1.1
    ):
        raise CheckoutTemporalFailoverError("temporal representation differs")

    models = _object(root.get("models"), "models")
    if (
        models.get("primary") != PRIMARY_METHOD
        or tuple(models.get("candidate_order", [])) != ALL_METHODS
        or models.get("both_paths_up_route") != 1.0
        or models.get("neither_path_up_route") != 0.0
        or models.get("parameter_bounds") != {"beta0": [-12, 12], "beta1": [-12, 12]}
        or models.get("maximum_equivalent_multistart_prediction_range") != 0.0001
        or models.get("numerical_probability_floor") != 1e-12
        or models.get("candidate_selection_after_test") is not False
        or models.get("sensitivity_candidates_are_not_promoted_by_best_test_score") is not True
    ):
        raise CheckoutTemporalFailoverError("model contract differs")

    adequacy = _object(root.get("adequacy"), "adequacy")
    expected_adequacy = {
        "minimum_stable_calibration_checkout_requests_per_cell": 500,
        "minimum_stable_one_path_up_requests_per_cell": 100,
        "minimum_one_path_up_episodes_per_cell": 8,
        "minimum_early_one_path_requests_per_cell": 20,
        "minimum_late_one_path_requests_per_cell": 20,
        "minimum_cells_with_positive_late_minus_early_recovery": 32,
        "calibration_recovery_interval_lower_must_exceed_zero": True,
    }
    if dict(adequacy) != expected_adequacy:
        raise CheckoutTemporalFailoverError("adequacy contract differs")
    evaluation = _object(root.get("evaluation"), "evaluation")
    bootstrap = _object(evaluation.get("bootstrap"), "bootstrap")
    if (
        evaluation.get("strong_accuracy_reference") != "m7_b0_endpoint"
        or evaluation.get("structural_reference") != "m7_single_demand_or"
        or evaluation.get("closure_margin_absolute_probability") != 0.03
        or evaluation.get("interval_sensitivity_maximum_mean_prediction_span") != 0.02
        or bootstrap.get("unit") != "campaign_within_placement_by_failure_law_stratum"
        or bootstrap.get("resamples") != 10000
        or bootstrap.get("seed") != 20260909
        or bootstrap.get("confidence_level") != 0.95
    ):
        raise CheckoutTemporalFailoverError("evaluation contract differs")
    workflow = _object(root.get("workflow"), "workflow")
    if dict(workflow) != {
        "jobs": 3,
        "job_timeout_minutes": 360,
        "heavy_analysis_only_in_github_actions": True,
        "artifact_retention_days": 90,
    }:
        raise CheckoutTemporalFailoverError("workflow contract differs")
    guards = _object(root.get("interpretation_guardrails"), "guardrails")
    if len(guards) != 11 or any(value is not False for value in guards.values()):
        raise CheckoutTemporalFailoverError("interpretation guards differ")

    return TemporalConfig(
        path=config_path,
        raw=root,
        profile="opentelemetry_demo",
        operation="checkout",
        placements=placements,
        failure_laws=laws,
        repetitions=repetitions,
        expected_cells=40,
        alignment_tolerance=1.25,
        transition_guard=1,
        minimum_stable_test=500,
        minimum_stable_calibration=500,
        minimum_one_path=100,
        minimum_episodes=8,
        minimum_early=20,
        minimum_late=20,
        minimum_positive_cells=32,
        interval_width_limit=1.1,
        fit_range_tolerance=0.0001,
        probability_floor=1e-12,
        closure_margin=0.03,
        interval_prediction_span=0.02,
        resamples=10000,
        seed=20260909,
        confidence_level=0.95,
        job_timeout_minutes=360,
    )


def validate_repository(config_path: str | Path) -> Mapping[str, Any]:
    config = load_temporal_config(config_path)
    root = config.path.resolve().parents[1]
    locks = []
    for value in _list(config.raw.get("repository_locks"), "repository locks"):
        record = _object(value, "repository lock")
        relative = _relative(record.get("path"), "repository lock path")
        locks.append(_audit_file(root / relative, record, relative.as_posix()))
    manual = root / _relative(config.raw.get("manual_actions_log"), "manual log")
    if not manual.is_file() or manual.stat().st_size < 100:
        raise CheckoutTemporalFailoverError("manual-actions log missing")
    return {
        "schema_version": 1,
        "kind": "m9n_repository_validation",
        "status": "m9n_repository_contract_valid",
        "config_sha256": file_sha256(config.path),
        "repository_locks": locks,
        "models": list(ALL_METHODS),
        "expected_cells": config.expected_cells,
        "job_timeout_minutes": config.job_timeout_minutes,
        "new_live_collections": 0,
        "pmx_invocations": 0,
    }


def _artifact_record(config: TemporalConfig, role: str) -> tuple[Mapping[str, Any], int, str]:
    evidence = config.raw["evidence"]
    if role in {"m8a_preserved", "m8a_audit"}:
        record = _object(evidence[role], role)
        return record, int(record["run_id"]), str(record["head_sha"])
    m9m = _object(evidence["m9m"], "M9M")
    record = _object(m9m[role.removeprefix("m9m_")], role)
    return record, int(m9m["run_id"]), str(m9m["head_sha"])


def _audit_metadata(config: TemporalConfig, role: str, path: Path) -> Mapping[str, Any]:
    record, run_id, head_sha = _artifact_record(config, role)
    spec = {
        "id": record["artifact_id"],
        "name": record["artifact_name"],
        "size_in_bytes": record["size_in_bytes"],
        "sha256": record["sha256"],
    }
    return _audit_artifact_metadata(path, spec, role, run_id, head_sha)


def build_contract(
    config_path: str | Path,
    metadata_paths: Mapping[str, Path],
    m8a_audit_root: Path,
    m9m_contract_root: Path,
    m9m_candidate_root: Path,
    m9m_evaluation_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_temporal_config(config_path)
    expected_roles = {
        "m8a_preserved",
        "m8a_audit",
        "m9m_contract",
        "m9m_candidates",
        "m9m_evaluation",
    }
    if set(metadata_paths) != expected_roles:
        raise CheckoutTemporalFailoverError("contract metadata roles differ")
    metadata = {
        role: _audit_metadata(config, role, path)
        for role, path in metadata_paths.items()
    }
    evidence = config.raw["evidence"]
    audits: list[dict[str, Any]] = []
    audits.extend(
        _audit_locked_files(
            m8a_audit_root,
            _object(evidence["m8a_audit"]["files"], "M8A files"),
            "m8a_audit",
        )
    )
    for role, root in (
        ("contract", m9m_contract_root),
        ("candidates", m9m_candidate_root),
        ("evaluation", m9m_evaluation_root),
    ):
        audits.extend(
            _audit_locked_files(
                root,
                _object(evidence["m9m"][role]["files"], f"M9M {role} files"),
                f"m9m_{role}",
            )
        )
    m8a = _object(_load_json(m8a_audit_root / "manifest.json", "M8A manifest"), "M8A")
    m9m_contract = _object(
        _load_json(m9m_contract_root / "contract-manifest.json", "M9M contract"),
        "M9M contract",
    )
    m9m_candidate = _object(
        _load_json(m9m_candidate_root / "candidate-manifest.json", "M9M candidate"),
        "M9M candidate",
    )
    m9m_evaluation = _object(
        _load_json(m9m_evaluation_root / "evaluation-manifest.json", "M9M evaluation"),
        "M9M evaluation",
    )
    if (
        m8a.get("artifact_counts", {}).get("qualified_cell") != 160
        or m8a.get("row_counts", {}).get("identities") != 160
        or any(int(value) != 0 for value in _object(m8a.get("quality"), "M8A quality").values())
        or m9m_contract.get("status")
        != "m9l_branch_source_and_information_boundary_verified"
        or m9m_contract.get("successful_request_target_call_sites") != 3
        or m9m_candidate.get("status")
        != "candidate_predictions_frozen_before_evaluator_access"
        or m9m_candidate.get("trace_gates_passed") is not True
        or m9m_candidate.get("fit_integrity_passed") is not True
        or m9m_candidate.get("candidate_rows") != 240
        or m9m_evaluation.get("status")
        != "checkout_trace_requirement_model_overshoots"
        or m9m_evaluation.get("next_experiment")
        != "m9n_checkout_temporal_failover_model"
        or m9m_evaluation.get("technical_evidence_accepted") is not True
        or m9m_evaluation.get("quality", {}).get("frozen_M7_prediction_mismatches") != 0
        or m9m_evaluation.get("overall_article_verdict_changed") is not False
    ):
        raise CheckoutTemporalFailoverError("accepted M8A/M9M contract differs")
    source_path = config.path.resolve().parents[1] / "src/telemetry_availability/live_placement_pilot.py"
    source_text = source_path.read_text(encoding="utf-8")
    markers = (
        "balance roundrobin",
        "default-server inter 500ms fall 1 rise 1",
        "server replica_a",
        "server replica_b",
    )
    if any(marker not in source_text for marker in markers):
        raise CheckoutTemporalFailoverError("HAProxy source timing markers differ")
    repository = validate_repository(config.path)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "artifact-file-audit.csv",
        ["role", "path", "bytes", "sha256", "matches"],
        audits,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9n_temporal_contract",
        "status": "m9m_temporal_branch_and_information_boundary_verified",
        "config_sha256": file_sha256(config.path),
        "artifact_metadata": metadata,
        "artifact_file_audits": len(audits),
        "repository_locks": len(repository["repository_locks"]),
        "selected_cells": config.expected_cells,
        "m9m_branch": m9m_evaluation["status"],
        "backend_health_check_interval_seconds": 0.5,
        "ordinary_health_poll_seconds": 1.0,
        "candidate_generation_may_access_test_health": False,
        "candidate_generation_may_access_test_outcomes": False,
        "new_live_collections": 0,
        "pmx_invocations": 0,
        "files": {
            "artifact-file-audit.csv": file_sha256(out / "artifact-file-audit.csv")
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "contract-manifest.json", manifest)
    return manifest


def stage_learner_inputs(
    config_path: str | Path,
    contract_manifest_path: Path,
    qualified_root: Path,
    analysis_root: Path,
    m8a_audit_root: Path,
    m9m_candidate_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutTemporalFailoverError("full M9N staging may run only in GitHub Actions")
    config = load_temporal_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9N contract"), "contract")
    if (
        contract.get("status") != "m9m_temporal_branch_and_information_boundary_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or contract.get("candidate_generation_may_access_test_health") is not False
        or contract.get("candidate_generation_may_access_test_outcomes") is not False
    ):
        raise CheckoutTemporalFailoverError("M9N staging contract differs")
    evidence = config.raw["evidence"]
    _audit_locked_files(
        m8a_audit_root,
        _object(evidence["m8a_audit"]["files"], "M8A files"),
        "m8a_audit",
    )
    _audit_file(
        analysis_root / "predictions.csv",
        _object(evidence["frozen_analysis"]["predictions.csv"], "frozen predictions"),
        "frozen predictions.csv",
    )
    _audit_locked_files(
        m9m_candidate_root,
        _object(evidence["m9m"]["candidates"]["files"], "M9M candidate files"),
        "m9m_candidates",
    )
    inventory_rows = _rows(m8a_audit_root / "file-inventory.csv")
    inventory = {
        str(row["relative_path"]).replace("\\", "/"): row
        for row in inventory_rows
        if row.get("evidence_group") == "qualified"
    }
    selected, census = _selected_source_directories(config, qualified_root)  # type: ignore[arg-type]
    file_rows: list[dict[str, Any]] = []
    for identity, directory in selected:
        destination = out / directory.name
        for relative_text in LEARNER_FILES:
            relative = Path(relative_text)
            source = directory / relative
            source_relative = source.relative_to(qualified_root).as_posix()
            expected = inventory.get(source_relative)
            if expected is None or not source.is_file():
                raise CheckoutTemporalFailoverError(f"learner source missing: {source_relative}")
            observed_bytes = source.stat().st_size
            observed_hash = file_sha256(source)
            if (
                observed_bytes != int(expected["size_in_bytes"])
                or observed_hash != expected["sha256"]
            ):
                raise CheckoutTemporalFailoverError(f"learner source differs: {source_relative}")
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            file_rows.append(
                {
                    "profile": identity[0],
                    "placement": identity[1],
                    "failure_law": identity[2],
                    "repetition": identity[3],
                    "source_path": source_relative,
                    "staged_path": target.relative_to(out).as_posix(),
                    "bytes": observed_bytes,
                    "sha256": observed_hash,
                    "matches_m8a_inventory": True,
                }
            )
    if len(file_rows) != config.expected_cells * len(LEARNER_FILES):
        raise CheckoutTemporalFailoverError("learner staging file count differs")
    _write_csv(
        out / "learner-file-audit.csv",
        [
            "profile",
            "placement",
            "failure_law",
            "repetition",
            "source_path",
            "staged_path",
            "bytes",
            "sha256",
            "matches_m8a_inventory",
        ],
        file_rows,
    )

    m7_rows = _rows(analysis_root / "predictions.csv")
    if not m7_rows or tuple(m7_rows[0]) != FROZEN_ANALYSIS_FIELDS:
        raise CheckoutTemporalFailoverError("M7 frozen prediction schema differs")
    reference_rows: list[dict[str, Any]] = []
    for row in m7_rows:
        if (
            row["profile"] == config.profile
            and row["operation"] == config.operation
            and row["source_placement"] in config.placements
            and row["target_placement"] == row["source_placement"]
            and row["failure_law"] in config.failure_laws
            and int(row["repetition"]) in config.repetitions
            and row["method"] == "B0"
            and row["mode"] == "sampled_mixed"
            and row["scope"] == "current"
        ):
            reference_rows.append(
                {
                    "profile": row["profile"],
                    "placement": row["source_placement"],
                    "failure_law": row["failure_law"],
                    "repetition": int(row["repetition"]),
                    "method": "m7_b0_endpoint",
                    "prediction": _finite(row["prediction"], "M7 B0 prediction"),
                    "route_prediction": "",
                    "residual_success_probability": _finite(
                        row["residual_success_probability"], "M7 B0 q"
                    ),
                }
            )
    m9m_rows = _rows(m9m_candidate_root / "candidate-predictions.csv")
    for row in m9m_rows:
        mapped = M9M_REFERENCE_MAP.get(row["method"])
        if mapped is not None:
            reference_rows.append(
                {
                    "profile": row["profile"],
                    "placement": row["placement"],
                    "failure_law": row["failure_law"],
                    "repetition": int(row["repetition"]),
                    "method": mapped,
                    "prediction": _finite(row["prediction"], "M9M prediction"),
                    "route_prediction": row["route_prediction"],
                    "residual_success_probability": _finite(
                        row["residual_success_probability"], "M9M q"
                    ),
                }
            )
    reference_by_key = {_model_key(row): row for row in reference_rows}
    expected_reference_keys = {
        (*identity, method)
        for identity in _expected_identities(config)  # type: ignore[arg-type]
        for method in REFERENCE_METHODS
    }
    if (
        len(reference_rows) != config.expected_cells * len(REFERENCE_METHODS)
        or len(reference_by_key) != len(reference_rows)
        or set(reference_by_key) != expected_reference_keys
    ):
        raise CheckoutTemporalFailoverError("frozen predictor reference matrix differs")
    reference_rows.sort(key=_model_key)
    _write_csv(out / REFERENCE_NAME, list(REFERENCE_FIELDS), reference_rows)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9n_learner_temporal_stage",
        "status": "learner_timing_and_frozen_predictors_staged",
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "qualified_manifest_census": census,
        "selected_cells": config.expected_cells,
        "staged_learner_files": len(file_rows),
        "frozen_reference_rows": len(reference_rows),
        "frozen_reference_fields": list(REFERENCE_FIELDS),
        "frozen_reference_contains_test_outcomes": False,
        "evaluator_files_parsed": 0,
        "evaluator_files_copied": 0,
        "test_health_accessed": False,
        "test_outcomes_accessed": False,
        "full_ordinary_calibration_health_is_additional_input": True,
        "files": {
            "learner-file-audit.csv": file_sha256(out / "learner-file-audit.csv"),
            REFERENCE_NAME: file_sha256(out / REFERENCE_NAME),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "stage-manifest.json", manifest)
    return manifest


def _baseline_q(cell: QualifiedCell, operation: str) -> tuple[float, int, int]:
    values = [
        request.success
        for request in cell.learner_requests
        if request.period == "baseline" and request.operation == operation
    ]
    if not values:
        raise CheckoutTemporalFailoverError("baseline checkout rows are absent")
    successes = sum(values)
    return (successes + 0.5) / (len(values) + 1.0), len(values), successes


def _temporal_records(
    requests: Sequence[Any],
    ticks: Sequence[HealthTick],
    operation: str,
    alignment_tolerance: float,
    transition_guard: int,
) -> tuple[list[TemporalRecord], dict[str, Any]]:
    ordered_ticks = tuple(sorted(ticks, key=lambda item: item.at))
    if len(ordered_ticks) < 2:
        raise CheckoutTemporalFailoverError("temporal model requires at least two health ticks")
    path_states = tuple((tick.signals[2], tick.signals[3]) for tick in ordered_ticks)
    episode_ids: list[int] = []
    episode_starts: list[int] = []
    episode_id = 0
    episode_start = 0
    for index, state in enumerate(path_states):
        if index and state != path_states[index - 1]:
            episode_id += 1
            episode_start = index
        episode_ids.append(episode_id)
        episode_starts.append(episode_start)
    all_transitions = _transition_times(ordered_ticks)
    selected = [request for request in requests if request.operation == operation]
    records: list[TemporalRecord] = []
    unaligned = 0
    transition_guarded = 0
    left_censored_one_path = 0
    for request in selected:
        index, distance = _nearest_tick(request.at, ordered_ticks)
        if distance > alignment_tolerance:
            unaligned += 1
            continue
        if _near_transition(request.at, all_transitions, transition_guard):
            transition_guarded += 1
            continue
        path_count = int(path_states[index][0] + path_states[index][1])
        start = episode_starts[index]
        if path_count == 1 and start == 0:
            left_censored_one_path += 1
            continue
        if path_count == 1:
            previous_at = ordered_ticks[start - 1].at
            first_new_at = ordered_ticks[start].at
            lower = max(0.0, request.at - first_new_at)
            upper = max(lower, request.at - previous_at)
            midpoint = (lower + upper) / 2.0
        else:
            lower = midpoint = upper = 0.0
        records.append(
            TemporalRecord(
                success=int(request.success),
                path_count=path_count,
                episode_id=episode_ids[index],
                lower_age=lower,
                midpoint_age=midpoint,
                upper_age=upper,
            )
        )
    one_path = [record for record in records if record.path_count == 1]
    early = [record for record in one_path if record.midpoint_age < 4.0]
    late = [record for record in one_path if record.midpoint_age >= 4.0]
    widths = [record.upper_age - record.lower_age for record in one_path]
    audit = {
        "operation_requests": len(selected),
        "stable_aligned_requests": len(records),
        "unaligned_requests": unaligned,
        "transition_guarded_requests": transition_guarded,
        "left_censored_one_path_requests": left_censored_one_path,
        "both_paths_up_requests": sum(record.path_count == 2 for record in records),
        "one_path_up_requests": len(one_path),
        "neither_path_up_requests": sum(record.path_count == 0 for record in records),
        "one_path_up_episodes": len({record.episode_id for record in one_path}),
        "early_one_path_requests": len(early),
        "early_one_path_successes": sum(record.success for record in early),
        "early_one_path_success_rate": (
            sum(record.success for record in early) / len(early) if early else math.nan
        ),
        "late_one_path_requests": len(late),
        "late_one_path_successes": sum(record.success for record in late),
        "late_one_path_success_rate": (
            sum(record.success for record in late) / len(late) if late else math.nan
        ),
        "late_minus_early_success_rate": (
            sum(record.success for record in late) / len(late)
            - sum(record.success for record in early) / len(early)
            if early and late
            else math.nan
        ),
        "maximum_age_interval_width": max(widths, default=0.0),
    }
    return records, audit


def _age(record: TemporalRecord, view: str) -> float:
    if view not in AGE_VIEWS:
        raise CheckoutTemporalFailoverError(f"unknown age view: {view}")
    return float(getattr(record, f"{view}_age"))


def _route_value(
    record: TemporalRecord,
    method: str,
    parameters: Sequence[float] = (),
    bin_values: Sequence[float] = (),
) -> float:
    if record.path_count == 2:
        return 1.0
    if record.path_count == 0:
        return 0.0
    if method == "source_500ms_failover":
        return min(max(record.midpoint_age / 0.5, 0.0), 1.0)
    if method == "learner_state_only":
        return float(expit(parameters[0]))
    if method.startswith("temporal_logit_"):
        view = method.removeprefix("temporal_logit_")
        return float(expit(parameters[0] + parameters[1] * math.log1p(_age(record, view))))
    if method == "temporal_monotone_bins":
        if len(bin_values) != 6:
            raise CheckoutTemporalFailoverError("monotone temporal bin vector differs")
        return float(bin_values[_age_bin(record.midpoint_age)])
    raise CheckoutTemporalFailoverError(f"unknown temporal route method: {method}")


def _marginal_prediction(
    records: Sequence[TemporalRecord],
    q: float,
    method: str,
    parameters: Sequence[float] = (),
    bin_values: Sequence[float] = (),
) -> float:
    return _mean(
        [q * _route_value(record, method, parameters, bin_values) for record in records]
    )


def _negative_log_likelihood(
    parameters: np.ndarray,
    records: Sequence[TemporalRecord],
    q: float,
    method: str,
    floor: float,
) -> float:
    total = 0.0
    for record in records:
        if record.path_count != 1:
            continue
        route = _route_value(record, method, parameters)
        probability = min(max(q * route, floor), 1.0 - floor)
        total -= (
            record.success * math.log(probability)
            + (1 - record.success) * math.log1p(-probability)
        )
    return total


def _fit_logit(
    records: Sequence[TemporalRecord],
    q: float,
    method: str,
    identity: tuple[str, str, str, int],
    config: TemporalConfig,
) -> dict[str, Any]:
    dimension = 1 if method == "learner_state_only" else 2
    bounds = [(-12.0, 12.0)] * dimension
    start_seed = int(
        _stable_uniform(config.seed, *identity, method, "optimizer") * (2**32 - 1)
    )
    generator = np.random.default_rng(start_seed)
    starts = [np.zeros(dimension, dtype=float)]
    starts.extend(
        generator.uniform(-6.0, 6.0, size=dimension) for _ in range(7)
    )
    results: list[dict[str, Any]] = []
    for start in starts:
        result = minimize(
            _negative_log_likelihood,
            start,
            args=(records, q, method, config.probability_floor),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1000, "ftol": 1e-12},
        )
        if math.isfinite(float(result.fun)) and np.all(np.isfinite(result.x)):
            parameters = tuple(float(value) for value in result.x)
            results.append(
                {
                    "nll": float(result.fun),
                    "parameters": parameters,
                    "converged": bool(result.success),
                    "prediction": _marginal_prediction(
                        records, q, method, parameters
                    ),
                }
            )
    if not results:
        raise CheckoutTemporalFailoverError(f"no finite temporal fit: {identity} {method}")
    best = min(results, key=lambda item: (item["nll"], not item["converged"]))
    equivalent = [item for item in results if item["nll"] <= best["nll"] + 1e-7]
    prediction_range = max(item["prediction"] for item in equivalent) - min(
        item["prediction"] for item in equivalent
    )
    boundary = any(abs(abs(value) - 12.0) <= 1e-5 for value in best["parameters"])
    return {
        **best,
        "finite_starts": len(results),
        "converged_starts": sum(bool(item["converged"]) for item in results),
        "equivalent_prediction_range": prediction_range,
        "status": (
            "boundary" if boundary and best["converged"] else
            "boundary_nonconvergence" if boundary else
            "regular" if best["converged"] else
            "finite_nonconvergence"
        ),
    }


def _age_bin(age: float) -> int:
    edges = (1.0, 2.0, 4.0, 8.0, 23.0)
    for index, upper in enumerate(edges):
        if age < upper:
            return index
    return 5


def _weighted_pava(values: Sequence[float], weights: Sequence[int]) -> list[float]:
    if len(values) != len(weights) or not values or any(weight <= 0 for weight in weights):
        raise CheckoutTemporalFailoverError("PAVA inputs differ")
    blocks: list[dict[str, Any]] = []
    for index, (value, weight) in enumerate(zip(values, weights, strict=True)):
        blocks.append(
            {"start": index, "end": index, "weight": float(weight), "value": float(value)}
        )
        while len(blocks) >= 2 and blocks[-2]["value"] > blocks[-1]["value"]:
            right = blocks.pop()
            left = blocks.pop()
            weight_sum = left["weight"] + right["weight"]
            blocks.append(
                {
                    "start": left["start"],
                    "end": right["end"],
                    "weight": weight_sum,
                    "value": (
                        left["value"] * left["weight"]
                        + right["value"] * right["weight"]
                    )
                    / weight_sum,
                }
            )
    fitted = [0.0] * len(values)
    for block in blocks:
        for index in range(int(block["start"]), int(block["end"]) + 1):
            fitted[index] = float(block["value"])
    return fitted


def _fit_monotone_bins(
    records: Sequence[TemporalRecord], q: float
) -> dict[str, Any]:
    counts = [0] * 6
    successes = [0] * 6
    for record in records:
        if record.path_count == 1:
            index = _age_bin(record.midpoint_age)
            counts[index] += 1
            successes[index] += record.success
    nonempty = [index for index, count in enumerate(counts) if count]
    if not nonempty:
        raise CheckoutTemporalFailoverError("no one-path rows for monotone fit")
    raw = [
        min(max(((successes[index] + 0.5) / (counts[index] + 1.0)) / q, 0.0), 1.0)
        for index in nonempty
    ]
    fitted_nonempty = _weighted_pava(raw, [counts[index] for index in nonempty])
    values: list[float] = []
    for index in range(6):
        if index in nonempty:
            values.append(fitted_nonempty[nonempty.index(index)])
        else:
            nearest = min(nonempty, key=lambda candidate: (abs(candidate - index), candidate))
            values.append(fitted_nonempty[nonempty.index(nearest)])
    return {
        "bin_values": tuple(values),
        "bin_counts": tuple(counts),
        "bin_successes": tuple(successes),
        "prediction": _marginal_prediction(
            records, q, "temporal_monotone_bins", bin_values=values
        ),
        "status": "weighted_pava",
    }


def _stratified_interval(
    rows: Sequence[Mapping[str, Any]],
    value: Callable[[Mapping[str, Any]], float],
    resamples: int,
    seed: int,
    confidence_level: float,
) -> dict[str, float]:
    strata: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(str(row["placement"]), str(row["failure_law"]))].append(row)
    if sorted(len(group) for group in strata.values()) != [10, 10, 10, 10]:
        raise CheckoutTemporalFailoverError("bootstrap strata differ")
    observed = _mean([value(row) for row in rows])
    generator = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=float)
    ordered = [strata[key] for key in sorted(strata)]
    for iteration in range(resamples):
        sample: list[Mapping[str, Any]] = []
        for group in ordered:
            indexes = generator.integers(0, len(group), size=len(group))
            sample.extend(group[int(index)] for index in indexes)
        draws[iteration] = _mean([value(row) for row in sample])
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "estimate": observed,
        "lower": float(np.quantile(draws, alpha)),
        "upper": float(np.quantile(draws, 1.0 - alpha)),
    }


def _verify_staged_learner_files(
    learner_root: Path, stage: Mapping[str, Any], expected_cells: int
) -> None:
    audit_path = learner_root / "learner-file-audit.csv"
    if file_sha256(audit_path) != stage.get("files", {}).get("learner-file-audit.csv"):
        raise CheckoutTemporalFailoverError("learner file audit differs")
    rows = _rows(audit_path)
    expected_paths = {"stage-manifest.json", "learner-file-audit.csv", REFERENCE_NAME}
    cells: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        relative = _relative(row["staged_path"], "staged learner path")
        parts = relative.parts
        if len(parts) != 3 or Path(*parts[1:]).as_posix() not in LEARNER_FILES:
            raise CheckoutTemporalFailoverError("unexpected staged learner path")
        if relative.as_posix() in expected_paths:
            raise CheckoutTemporalFailoverError("duplicate staged learner path")
        expected_paths.add(relative.as_posix())
        cells[parts[0]].add(Path(*parts[1:]).as_posix())
        _audit_file(learner_root / relative, {**row, "bytes": int(row["bytes"])}, relative.as_posix())
    if len(cells) != expected_cells or any(set(LEARNER_FILES) != paths for paths in cells.values()):
        raise CheckoutTemporalFailoverError("staged learner file matrix differs")
    if any(path.name == "evaluator" for path in learner_root.rglob("*")):
        raise CheckoutTemporalFailoverError("evaluator path present in learner input")
    actual_paths = {path.relative_to(learner_root).as_posix() for path in learner_root.rglob("*") if path.is_file()}
    if actual_paths != expected_paths:
        raise CheckoutTemporalFailoverError("unexpected files in learner input")


def _mean_interval_prediction_span(rows: Sequence[Mapping[str, Any]]) -> float:
    values: dict[tuple[str, str, str, int], dict[str, float]] = defaultdict(dict)
    methods = {f"temporal_logit_{view}" for view in AGE_VIEWS}
    for row in rows:
        method = str(row["method"])
        if method in methods:
            cell = values[_identity(row)]
            if method in cell:
                raise CheckoutTemporalFailoverError("duplicate interval sensitivity")
            cell[method] = _finite(row["prediction"], "interval prediction")
    if not values or any(set(cell) != methods for cell in values.values()):
        raise CheckoutTemporalFailoverError("interval sensitivity matrix differs")
    return _mean([max(cell.values()) - min(cell.values()) for cell in values.values()])


def generate_candidates(
    config_path: str | Path,
    contract_manifest_path: Path,
    learner_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutTemporalFailoverError(
            "full M9N candidate generation may run only in GitHub Actions"
        )
    config = load_temporal_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9N contract"), "contract")
    stage_path = learner_root / "stage-manifest.json"
    stage = _object(_load_json(stage_path, "M9N stage"), "stage")
    if (
        contract.get("status") != "m9m_temporal_branch_and_information_boundary_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or stage.get("status") != "learner_timing_and_frozen_predictors_staged"
        or stage.get("config_sha256") != file_sha256(config.path)
        or stage.get("contract_manifest_sha256") != file_sha256(contract_manifest_path)
        or stage.get("selected_cells") != config.expected_cells
        or stage.get("staged_learner_files") != config.expected_cells * len(LEARNER_FILES)
        or stage.get("frozen_reference_rows") != config.expected_cells * len(REFERENCE_METHODS)
        or stage.get("evaluator_files_parsed") != 0
        or stage.get("evaluator_files_copied") != 0
        or stage.get("test_health_accessed") is not False
        or stage.get("test_outcomes_accessed") is not False
        or file_sha256(learner_root / REFERENCE_NAME)
        != stage.get("files", {}).get(REFERENCE_NAME)
    ):
        raise CheckoutTemporalFailoverError("candidate stage contract differs")
    _verify_staged_learner_files(learner_root, stage, config.expected_cells)
    reference_rows = _rows(learner_root / REFERENCE_NAME)
    reference_by_key = {_model_key(row): row for row in reference_rows}
    expected_reference_keys = {
        (*identity, method)
        for identity in _expected_identities(config)  # type: ignore[arg-type]
        for method in REFERENCE_METHODS
    }
    if len(reference_rows) != 240 or set(reference_by_key) != expected_reference_keys or tuple(reference_rows[0]) != REFERENCE_FIELDS:
        raise CheckoutTemporalFailoverError("candidate frozen references differ")
    manifests = sorted(learner_root.glob("*/learner/manifest.json"))
    if len(manifests) != config.expected_cells:
        raise CheckoutTemporalFailoverError("candidate learner cell count differs")

    candidate_rows: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for manifest_path in manifests:
        cell = _load_learner_cell(manifest_path.parents[1])
        if cell.identity in seen or cell.identity not in _expected_identities(config):  # type: ignore[arg-type]
            raise CheckoutTemporalFailoverError(f"candidate cell identity differs: {cell.identity}")
        seen.add(cell.identity)
        q, baseline_requests, baseline_successes = _baseline_q(cell, config.operation)
        if any(abs(q - _finite(reference_by_key[(*cell.identity, method)]["residual_success_probability"], "frozen q")) > 1e-12 for method in REFERENCE_METHODS):
            raise CheckoutTemporalFailoverError("baseline q differs from frozen references")
        calibration_requests = [
            request
            for request in cell.learner_requests
            if request.period == "calibration"
        ]
        records, audit = _temporal_records(
            calibration_requests,
            cell.health,
            config.operation,
            config.alignment_tolerance,
            config.transition_guard,
        )
        fits = {
            "learner_state_only": _fit_logit(
                records, q, "learner_state_only", cell.identity, config
            )
        }
        for view in AGE_VIEWS:
            method = f"temporal_logit_{view}"
            fits[method] = _fit_logit(records, q, method, cell.identity, config)
        monotone = _fit_monotone_bins(records, q)
        base = {
            "profile": cell.profile,
            "placement": cell.placement,
            "failure_law": cell.failure_law,
            "repetition": cell.repetition,
        }
        predictions: dict[str, dict[str, Any]] = {}
        for method in REFERENCE_METHODS:
            reference = reference_by_key[(*cell.identity, method)]
            predictions[method] = {
                "prediction": _finite(reference["prediction"], f"{method} prediction"),
                "source": "frozen_reference",
                "fit_status": "frozen_reference",
                "parameters_json": "",
                "equivalent_prediction_range": "",
            }
        predictions["source_500ms_failover"] = {
            "prediction": _marginal_prediction(
                records, q, "source_500ms_failover"
            ),
            "source": "source_fixed",
            "fit_status": "fixed_500ms",
            "parameters_json": json.dumps({"delay_seconds": 0.5}, sort_keys=True),
            "equivalent_prediction_range": 0.0,
        }
        for method, fit in fits.items():
            predictions[method] = {
                "prediction": fit["prediction"],
                "source": "learner_fit",
                "fit_status": fit["status"],
                "parameters_json": json.dumps(fit["parameters"]),
                "equivalent_prediction_range": fit["equivalent_prediction_range"],
            }
        predictions["temporal_monotone_bins"] = {
            "prediction": monotone["prediction"],
            "source": "learner_fit",
            "fit_status": monotone["status"],
            "parameters_json": json.dumps(
                {
                    "bin_edges": [0, 1, 2, 4, 8, 23, "inf"],
                    "bin_values": monotone["bin_values"],
                },
                sort_keys=True,
            ),
            "equivalent_prediction_range": 0.0,
        }
        if set(predictions) != set(ALL_METHODS):
            raise CheckoutTemporalFailoverError("candidate method matrix differs")
        for method in ALL_METHODS:
            row = predictions[method]
            prediction = _finite(row["prediction"], f"{method} prediction")
            if not 0.0 <= prediction <= 1.0:
                raise CheckoutTemporalFailoverError("candidate prediction outside [0,1]")
            candidate_rows.append(
                {
                    **base,
                    "method": method,
                    "prediction": prediction,
                    "clean_residual_probability": q,
                    "source": row["source"],
                    "fit_status": row["fit_status"],
                    "parameters_json": row["parameters_json"],
                    "equivalent_prediction_range": row["equivalent_prediction_range"],
                    "candidate_frozen_before_evaluator": True,
                }
            )
        for method in ("learner_state_only", *tuple(f"temporal_logit_{view}" for view in AGE_VIEWS)):
            fit = fits[method]
            parameter_rows.append(
                {
                    **base,
                    "method": method,
                    "parameters_json": json.dumps(fit["parameters"]),
                    "nll": fit["nll"],
                    "marginal_prediction": fit["prediction"],
                    "fit_status": fit["status"],
                    "finite_starts": fit["finite_starts"],
                    "converged_starts": fit["converged_starts"],
                    "equivalent_prediction_range": fit["equivalent_prediction_range"],
                }
            )
        parameter_rows.append(
            {
                **base,
                "method": "temporal_monotone_bins",
                "parameters_json": predictions["temporal_monotone_bins"]["parameters_json"],
                "nll": "",
                "marginal_prediction": monotone["prediction"],
                "fit_status": monotone["status"],
                "finite_starts": "",
                "converged_starts": "",
                "equivalent_prediction_range": 0.0,
            }
        )
        interval_span = max(fits[f"temporal_logit_{view}"]["prediction"] for view in AGE_VIEWS) - min(
            fits[f"temporal_logit_{view}"]["prediction"] for view in AGE_VIEWS
        )
        audit_rows.append(
            {
                **base,
                "baseline_checkout_requests": baseline_requests,
                "baseline_checkout_successes": baseline_successes,
                "clean_residual_probability": q,
                **audit,
                "state_only_nll": fits["learner_state_only"]["nll"],
                "temporal_midpoint_nll": fits["temporal_logit_midpoint"]["nll"],
                "state_only_minus_temporal_nll": (
                    fits["learner_state_only"]["nll"]
                    - fits["temporal_logit_midpoint"]["nll"]
                ),
                "midpoint_beta0": fits["temporal_logit_midpoint"]["parameters"][0],
                "midpoint_beta1": fits["temporal_logit_midpoint"]["parameters"][1],
                "interval_prediction_span": interval_span,
            }
        )
    if (
        seen != _expected_identities(config)  # type: ignore[arg-type]
        or len(candidate_rows) != config.expected_cells * len(ALL_METHODS)
        or len(parameter_rows) != config.expected_cells * 5
        or len(audit_rows) != config.expected_cells
    ):
        raise CheckoutTemporalFailoverError("candidate output matrix differs")
    recovery = _stratified_interval(
        audit_rows,
        lambda row: float(row["late_minus_early_success_rate"]),
        config.resamples,
        config.seed,
        config.confidence_level,
    )
    positive_recovery_cells = sum(
        float(row["late_minus_early_success_rate"]) > 0.0 for row in audit_rows
    )
    calibration_signature = bool(
        positive_recovery_cells >= config.minimum_positive_cells
        and recovery["lower"] > 0.0
    )
    adequacy = all(
        int(row["stable_aligned_requests"]) >= config.minimum_stable_calibration
        and int(row["one_path_up_requests"]) >= config.minimum_one_path
        and int(row["one_path_up_episodes"]) >= config.minimum_episodes
        and int(row["early_one_path_requests"]) >= config.minimum_early
        and int(row["late_one_path_requests"]) >= config.minimum_late
        and float(row["maximum_age_interval_width"]) <= config.interval_width_limit
        for row in audit_rows
    )
    optimizer_rows = [
        row for row in parameter_rows if str(row["method"]).startswith("temporal_logit_") or row["method"] == "learner_state_only"
    ]
    fit_integrity = all(
        int(row["finite_starts"]) == 8
        and int(row["converged_starts"]) >= 1
        and float(row["equivalent_prediction_range"]) <= config.fit_range_tolerance
        for row in optimizer_rows
    )
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "candidate-predictions.csv",
        [
            "profile",
            "placement",
            "failure_law",
            "repetition",
            "method",
            "prediction",
            "clean_residual_probability",
            "source",
            "fit_status",
            "parameters_json",
            "equivalent_prediction_range",
            "candidate_frozen_before_evaluator",
        ],
        candidate_rows,
    )
    _write_csv(
        out / "temporal-parameters.csv",
        [
            "profile",
            "placement",
            "failure_law",
            "repetition",
            "method",
            "parameters_json",
            "nll",
            "marginal_prediction",
            "fit_status",
            "finite_starts",
            "converged_starts",
            "equivalent_prediction_range",
        ],
        parameter_rows,
    )
    _write_csv(
        out / "calibration-age-audit.csv",
        list(audit_rows[0]),
        audit_rows,
    )
    _write_csv(
        out / "calibration-bootstrap.csv",
        ["metric", "estimate", "lower", "upper", "positive_cells"],
        [
            {
                "metric": "late_minus_early_one_path_success_rate",
                **recovery,
                "positive_cells": positive_recovery_cells,
            }
        ],
    )
    for name in ("learner-file-audit.csv", REFERENCE_NAME, "stage-manifest.json"):
        shutil.copy2(learner_root / name, out / name)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9n_temporal_candidate_freeze",
        "status": "temporal_candidates_frozen_before_evaluator_access",
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "selected_cells": config.expected_cells,
        "candidate_rows": len(candidate_rows),
        "parameter_rows": len(parameter_rows),
        "calibration_audit_rows": len(audit_rows),
        "candidate_selection_after_test": False,
        "candidate_artifact_precedes_evaluator_access": True,
        "test_health_accessed": False,
        "test_outcomes_accessed": False,
        "evaluator_files_present_during_fit": False,
        "full_ordinary_calibration_health_is_additional_input": True,
        "adequacy_passed": adequacy,
        "fit_integrity_passed": fit_integrity,
        "calibration_temporal_signature_passed": calibration_signature,
        "calibration_recovery": {
            **recovery,
            "positive_cells": positive_recovery_cells,
        },
        "quality": {
            "minimum_stable_calibration_requests": min(
                int(row["stable_aligned_requests"]) for row in audit_rows
            ),
            "minimum_one_path_requests": min(
                int(row["one_path_up_requests"]) for row in audit_rows
            ),
            "minimum_one_path_episodes": min(
                int(row["one_path_up_episodes"]) for row in audit_rows
            ),
            "minimum_early_requests": min(
                int(row["early_one_path_requests"]) for row in audit_rows
            ),
            "minimum_late_requests": min(
                int(row["late_one_path_requests"]) for row in audit_rows
            ),
            "maximum_age_interval_width": max(
                float(row["maximum_age_interval_width"]) for row in audit_rows
            ),
            "maximum_equivalent_prediction_range": max(
                float(row["equivalent_prediction_range"]) for row in optimizer_rows
            ),
            "maximum_cell_interval_prediction_span": max(
                float(row["interval_prediction_span"]) for row in audit_rows
            ),
        },
        "new_live_collections": 0,
        "pmx_invocations": 0,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "candidate-predictions.csv",
                "temporal-parameters.csv",
                "calibration-age-audit.csv",
                "calibration-bootstrap.csv",
                "learner-file-audit.csv",
                REFERENCE_NAME,
                "stage-manifest.json",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "candidate-manifest.json", manifest)
    return manifest


def _bootstrap_matrix(
    rows: Sequence[Mapping[str, Any]],
    methods: Sequence[str],
    metric_fields: Sequence[str],
    references: Mapping[str, str],
    resamples: int,
    seed: int,
    confidence_level: float,
) -> dict[str, dict[str, float]]:
    by_identity: dict[
        tuple[str, str, str, int], dict[str, Mapping[str, Any]]
    ] = defaultdict(dict)
    for row in rows:
        identity = _identity(row)
        method = str(row["method"])
        if method in by_identity[identity]:
            raise CheckoutTemporalFailoverError("duplicate method within bootstrap cell")
        by_identity[identity][method] = row
    if len(by_identity) != 40 or any(
        set(group) != set(methods) for group in by_identity.values()
    ):
        raise CheckoutTemporalFailoverError("bootstrap method matrix differs")
    strata: dict[tuple[str, str], list[tuple[str, str, str, int]]] = defaultdict(list)
    for identity in by_identity:
        strata[(identity[1], identity[2])].append(identity)
    if sorted(len(group) for group in strata.values()) != [10, 10, 10, 10]:
        raise CheckoutTemporalFailoverError("bootstrap cell strata differ")
    metric_names = [
        f"{method}.{field}" for method in methods for field in metric_fields
    ]
    for method in methods:
        for label in references:
            metric_names.extend(
                (
                    f"{method}.delta_brier_vs_{label}",
                    f"{method}.delta_absolute_error_vs_{label}",
                )
            )

    def value(identity: tuple[str, str, str, int], name: str) -> float:
        method, field = name.split(".", maxsplit=1)
        row = by_identity[identity][method]
        if field in metric_fields:
            return float(row[field])
        for label, reference_method in references.items():
            reference = by_identity[identity][reference_method]
            if field == f"delta_brier_vs_{label}":
                return float(row["brier_score"]) - float(reference["brier_score"])
            if field == f"delta_absolute_error_vs_{label}":
                return float(row["absolute_error"]) - float(reference["absolute_error"])
        raise CheckoutTemporalFailoverError(f"unknown bootstrap metric: {name}")

    identities = sorted(by_identity)
    estimates = {
        name: _mean([value(identity, name) for identity in identities])
        for name in metric_names
    }
    generator = np.random.default_rng(seed)
    draws = {name: np.empty(resamples, dtype=float) for name in metric_names}
    ordered_strata = [sorted(strata[key]) for key in sorted(strata)]
    for iteration in range(resamples):
        sample: list[tuple[str, str, str, int]] = []
        for group in ordered_strata:
            indexes = generator.integers(0, len(group), size=len(group))
            sample.extend(group[int(index)] for index in indexes)
        for name in metric_names:
            draws[name][iteration] = _mean(
                [value(identity, name) for identity in sample]
            )
    alpha = (1.0 - confidence_level) / 2.0
    return {
        name: {
            "estimate": estimates[name],
            "lower": float(np.quantile(draws[name], alpha)),
            "upper": float(np.quantile(draws[name], 1.0 - alpha)),
        }
        for name in metric_names
    }


def _closes(
    bootstrap: Mapping[str, Mapping[str, float]], method: str, margin: float
) -> bool:
    signed = bootstrap[f"{method}.signed_error"]
    return bool(
        abs(float(signed["estimate"])) <= margin
        and float(signed["lower"]) <= 0.0 <= float(signed["upper"])
    )


def classify_evaluation(
    marginal: Mapping[str, Mapping[str, float]],
    conditional: Mapping[str, Mapping[str, float]],
    *,
    integrity_passed: bool,
    calibration_signature_passed: bool,
    interval_prediction_span: float,
    closure_margin: float,
    interval_span_limit: float,
) -> dict[str, Any]:
    primary_closes = _closes(marginal, PRIMARY_METHOD, closure_margin)
    improves_or = bool(
        marginal[f"{PRIMARY_METHOD}.delta_brier_vs_or"]["upper"] < 0.0
        and marginal[f"{PRIMARY_METHOD}.delta_absolute_error_vs_or"]["upper"] < 0.0
    )
    beats_b0 = bool(
        marginal[f"{PRIMARY_METHOD}.delta_brier_vs_b0"]["upper"] < 0.0
        and marginal[f"{PRIMARY_METHOD}.delta_absolute_error_vs_b0"]["upper"] < 0.0
    )
    interval_robust = interval_prediction_span <= interval_span_limit
    conditional_improves_state = bool(
        conditional[
            "conditional_temporal_midpoint.delta_brier_vs_state"
        ]["upper"]
        < 0.0
    )
    mechanism_supported = bool(
        integrity_passed
        and calibration_signature_passed
        and primary_closes
        and improves_or
        and interval_robust
        and conditional_improves_state
    )
    conditional_only = bool(
        integrity_passed
        and calibration_signature_passed
        and conditional_improves_state
        and not mechanism_supported
    )
    signed = marginal[f"{PRIMARY_METHOD}.signed_error"]
    underpredicts = float(signed["upper"]) < -closure_margin
    overpredicts = float(signed["lower"]) > closure_margin
    if not integrity_passed:
        branch = "integrity_fail"
    elif not calibration_signature_passed:
        branch = "no_recovery"
    elif mechanism_supported and beats_b0:
        branch = "temporal_with_b0_advantage"
    elif mechanism_supported:
        branch = "temporal_without_b0_advantage"
    elif conditional_only:
        branch = "conditional_only"
    elif underpredicts:
        branch = "underpredicts"
    elif overpredicts:
        branch = "overpredicts"
    else:
        branch = "inconclusive"
    return {
        "branch_key": branch,
        "primary_closes": primary_closes,
        "improves_or": improves_or,
        "beats_b0": beats_b0,
        "interval_robust": interval_robust,
        "interval_prediction_span": interval_prediction_span,
        "conditional_improves_state_only": conditional_improves_state,
        "mechanism_supported": mechanism_supported,
        "conditional_only": conditional_only,
        "underpredicts": underpredicts,
        "overpredicts": overpredicts,
    }


def evaluate_candidates(
    config_path: str | Path,
    contract_manifest_path: Path,
    candidate_root: Path,
    qualified_root: Path,
    m8a_audit_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutTemporalFailoverError(
            "full M9N evaluation may run only in GitHub Actions"
        )
    config = load_temporal_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9N contract"), "contract")
    candidate_manifest_path = candidate_root / "candidate-manifest.json"
    candidate_manifest = _object(
        _load_json(candidate_manifest_path, "M9N candidates"), "candidate manifest"
    )
    if (
        contract.get("status") != "m9m_temporal_branch_and_information_boundary_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or candidate_manifest.get("status")
        != "temporal_candidates_frozen_before_evaluator_access"
        or candidate_manifest.get("config_sha256") != file_sha256(config.path)
        or candidate_manifest.get("contract_manifest_sha256")
        != file_sha256(contract_manifest_path)
        or candidate_manifest.get("selected_cells") != config.expected_cells
        or candidate_manifest.get("candidate_rows") != config.expected_cells * len(ALL_METHODS)
        or candidate_manifest.get("candidate_selection_after_test") is not False
        or candidate_manifest.get("candidate_artifact_precedes_evaluator_access") is not True
        or candidate_manifest.get("test_health_accessed") is not False
        or candidate_manifest.get("test_outcomes_accessed") is not False
    ):
        raise CheckoutTemporalFailoverError("frozen candidate contract differs")
    for name, digest in _object(candidate_manifest.get("files"), "candidate files").items():
        path = candidate_root / _relative(name, "candidate path")
        if not path.is_file() or file_sha256(path) != digest:
            raise CheckoutTemporalFailoverError(f"candidate file differs: {name}")
    evidence = config.raw["evidence"]
    _audit_locked_files(
        m8a_audit_root,
        _object(evidence["m8a_audit"]["files"], "M8A files"),
        "m8a_audit",
    )
    selected, census = _selected_source_directories(config, qualified_root)  # type: ignore[arg-type]
    directories = [path for _, path in selected]
    selected_file_rows = _audit_selected_files(
        config,  # type: ignore[arg-type]
        qualified_root,
        directories,
        m8a_audit_root / "file-inventory.csv",
    )
    candidate_rows = _rows(candidate_root / "candidate-predictions.csv")
    candidate_by_key = {_model_key(row): row for row in candidate_rows}
    expected_candidate_keys = {
        (*identity, method)
        for identity in _expected_identities(config)  # type: ignore[arg-type]
        for method in ALL_METHODS
    }
    if len(candidate_rows) != 480 or set(candidate_by_key) != expected_candidate_keys:
        raise CheckoutTemporalFailoverError("candidate prediction matrix differs")

    marginal_rows: list[dict[str, Any]] = []
    conditional_rows: list[dict[str, Any]] = []
    conditional_audits: list[dict[str, Any]] = []
    for identity, directory in selected:
        cell = load_qualified_cell(directory)
        stable = next(
            row
            for row in _period_metrics(
                config.operation,
                cell.test_requests,
                cell.test_health,
                config.alignment_tolerance,
                config.transition_guard,
            )
            if row["view"] == "stable"
        )
        attempts = int(stable["view_requests"])
        successes = int(stable["view_successes"])
        observed = float(stable["empirical_success_rate"])
        for method in ALL_METHODS:
            candidate = candidate_by_key[(*identity, method)]
            prediction = _finite(candidate["prediction"], f"{method} prediction")
            brier = (
                successes * (prediction - 1.0) ** 2
                + (attempts - successes) * prediction**2
            ) / attempts
            signed = prediction - observed
            marginal_rows.append(
                {
                    "profile": identity[0],
                    "placement": identity[1],
                    "failure_law": identity[2],
                    "repetition": identity[3],
                    "method": method,
                    "prediction": prediction,
                    "test_requests": attempts,
                    "test_successes": successes,
                    "test_success_rate": observed,
                    "signed_error": signed,
                    "absolute_error": abs(signed),
                    "brier_score": brier,
                }
            )

        q = _finite(
            candidate_by_key[(*identity, PRIMARY_METHOD)][
                "clean_residual_probability"
            ],
            "candidate q",
        )
        test_records, conditional_audit = _temporal_records(
            cell.test_requests,
            cell.test_health,
            config.operation,
            config.alignment_tolerance,
            config.transition_guard,
        )
        conditional_audits.append(
            {
                "profile": identity[0],
                "placement": identity[1],
                "failure_law": identity[2],
                "repetition": identity[3],
                **conditional_audit,
            }
        )
        state_parameters = json.loads(
            candidate_by_key[(*identity, "learner_state_only")]["parameters_json"]
        )
        temporal_parameters = {
            view: json.loads(
                candidate_by_key[(*identity, f"temporal_logit_{view}")][
                    "parameters_json"
                ]
            )
            for view in AGE_VIEWS
        }
        monotone_payload = json.loads(
            candidate_by_key[(*identity, "temporal_monotone_bins")][
                "parameters_json"
            ]
        )
        b0 = _finite(
            candidate_by_key[(*identity, "m7_b0_endpoint")]["prediction"],
            "B0 prediction",
        )

        def conditional_probability(record: TemporalRecord, method: str) -> float:
            if method == "conditional_path_or":
                return q * float(record.path_count >= 1)
            if method == "conditional_path_and":
                return q * float(record.path_count == 2)
            if method == "conditional_source_500ms":
                return q * _route_value(record, "source_500ms_failover")
            if method == "conditional_state_only":
                return q * _route_value(
                    record, "learner_state_only", state_parameters
                )
            if method.startswith("conditional_temporal_"):
                view = method.removeprefix("conditional_temporal_")
                return q * _route_value(
                    record, f"temporal_logit_{view}", temporal_parameters[view]
                )
            if method == "conditional_monotone_bins":
                return q * _route_value(
                    record,
                    "temporal_monotone_bins",
                    bin_values=monotone_payload["bin_values"],
                )
            if method == "conditional_b0_constant":
                return b0
            raise CheckoutTemporalFailoverError(f"unknown conditional method: {method}")

        conditional_observed = _mean([float(record.success) for record in test_records])
        for method in CONDITIONAL_METHODS:
            probabilities = [
                conditional_probability(record, method) for record in test_records
            ]
            if any(not 0.0 <= probability <= 1.0 for probability in probabilities):
                raise CheckoutTemporalFailoverError("conditional probability outside [0,1]")
            brier = _mean(
                [
                    (probability - record.success) ** 2
                    for probability, record in zip(
                        probabilities, test_records, strict=True
                    )
                ]
            )
            prediction = _mean(probabilities)
            signed = prediction - conditional_observed
            conditional_rows.append(
                {
                    "profile": identity[0],
                    "placement": identity[1],
                    "failure_law": identity[2],
                    "repetition": identity[3],
                    "method": method,
                    "prediction": prediction,
                    "test_requests": len(test_records),
                    "test_successes": sum(record.success for record in test_records),
                    "test_success_rate": conditional_observed,
                    "signed_error": signed,
                    "absolute_error": abs(signed),
                    "brier_score": brier,
                }
            )
    marginal_bootstrap = _bootstrap_matrix(
        marginal_rows,
        ALL_METHODS,
        ("prediction", "signed_error", "absolute_error", "brier_score"),
        {"or": "m7_single_demand_or", "b0": "m7_b0_endpoint"},
        config.resamples,
        config.seed,
        config.confidence_level,
    )
    conditional_bootstrap = _bootstrap_matrix(
        conditional_rows,
        CONDITIONAL_METHODS,
        ("prediction", "signed_error", "absolute_error", "brier_score"),
        {
            "state": "conditional_state_only",
            "source": "conditional_source_500ms",
            "b0": "conditional_b0_constant",
        },
        config.resamples,
        config.seed + 1,
        config.confidence_level,
    )
    interval_prediction_span = _mean_interval_prediction_span(candidate_rows)
    test_adequacy = all(
        int(row["stable_aligned_requests"]) >= config.minimum_stable_test
        and float(row["maximum_age_interval_width"]) <= config.interval_width_limit
        for row in conditional_audits
    )
    integrity = bool(
        candidate_manifest.get("adequacy_passed") is True
        and candidate_manifest.get("fit_integrity_passed") is True
        and test_adequacy
        and census == 160
        and len(selected_file_rows) == 360
    )
    classification = classify_evaluation(
        marginal_bootstrap,
        conditional_bootstrap,
        integrity_passed=integrity,
        calibration_signature_passed=bool(
            candidate_manifest.get("calibration_temporal_signature_passed")
        ),
        interval_prediction_span=interval_prediction_span,
        closure_margin=config.closure_margin,
        interval_span_limit=config.interval_prediction_span,
    )
    decision = config.raw["decision"]
    status = str(decision[classification["branch_key"]])
    if classification["branch_key"] == "temporal_with_b0_advantage":
        next_experiment = str(decision["next_supported"])
    elif classification["branch_key"] == "temporal_without_b0_advantage":
        next_experiment = str(decision["next_without_b0_advantage"])
    elif classification["branch_key"] == "conditional_only":
        next_experiment = str(decision["next_conditional_only"])
    elif classification["branch_key"] in {"underpredicts", "overpredicts", "inconclusive"}:
        next_experiment = str(decision["next_miss"])
    elif classification["branch_key"] == "no_recovery":
        next_experiment = str(decision["next_no_recovery"])
    else:
        next_experiment = str(decision["next_integrity_fail"])
    mean_brier = {
        method: marginal_bootstrap[f"{method}.brier_score"]["estimate"]
        for method in ALL_METHODS
    }
    descriptive_minimum = min(mean_brier, key=mean_brier.get)  # type: ignore[arg-type]
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "selected-file-audit.csv",
        ["path", "bytes", "sha256", "matches_m8a_inventory"],
        selected_file_rows,
    )
    _write_csv(
        out / "marginal-scores.csv",
        list(marginal_rows[0]),
        marginal_rows,
    )
    _write_csv(
        out / "conditional-cell-scores.csv",
        list(conditional_rows[0]),
        conditional_rows,
    )
    _write_csv(
        out / "conditional-age-audit.csv",
        list(conditional_audits[0]),
        conditional_audits,
    )
    bootstrap_rows = [
        {"family": family, "metric": name, **interval}
        for family, values in (
            ("marginal", marginal_bootstrap),
            ("conditional", conditional_bootstrap),
        )
        for name, interval in values.items()
    ]
    _write_csv(
        out / "bootstrap-summary.csv",
        ["family", "metric", "estimate", "lower", "upper"],
        bootstrap_rows,
    )
    decision_rows = [
        {
            "method": method,
            "primary": method == PRIMARY_METHOD,
            "mean_prediction": marginal_bootstrap[f"{method}.prediction"]["estimate"],
            "mean_signed_error": marginal_bootstrap[f"{method}.signed_error"]["estimate"],
            "signed_error_lower": marginal_bootstrap[f"{method}.signed_error"]["lower"],
            "signed_error_upper": marginal_bootstrap[f"{method}.signed_error"]["upper"],
            "mean_absolute_error": marginal_bootstrap[f"{method}.absolute_error"]["estimate"],
            "mean_brier_score": marginal_bootstrap[f"{method}.brier_score"]["estimate"],
            "closes_signed_gap": _closes(
                marginal_bootstrap, method, config.closure_margin
            ),
            "selected_from_test": False,
        }
        for method in ALL_METHODS
    ]
    _write_csv(
        out / "decision-matrix.csv",
        list(decision_rows[0]),
        decision_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9n_temporal_heldout_evaluation",
        "status": status,
        "next_experiment": next_experiment,
        "classification": classification,
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "candidate_manifest_sha256": file_sha256(candidate_manifest_path),
        "candidate_artifact_preceded_evaluator_access": True,
        "selected_cells": config.expected_cells,
        "marginal_score_rows": len(marginal_rows),
        "conditional_score_rows": len(conditional_rows),
        "integrity_passed": integrity,
        "test_adequacy_passed": test_adequacy,
        "calibration_temporal_signature_passed": candidate_manifest.get(
            "calibration_temporal_signature_passed"
        ),
        "calibration_recovery": candidate_manifest.get("calibration_recovery"),
        "marginal_bootstrap": marginal_bootstrap,
        "conditional_bootstrap": conditional_bootstrap,
        "descriptive_minimum_brier_method": descriptive_minimum,
        "descriptive_minimum_promoted": False,
        "quality": {
            "qualified_manifest_census": census,
            "selected_files_audited": len(selected_file_rows),
            "minimum_stable_marginal_test_requests": min(
                int(row["test_requests"]) for row in marginal_rows
            ),
            "minimum_conditional_test_requests": min(
                int(row["stable_aligned_requests"]) for row in conditional_audits
            ),
            "maximum_test_age_interval_width": max(
                float(row["maximum_age_interval_width"]) for row in conditional_audits
            ),
            "interval_mean_prediction_span": interval_prediction_span,
        },
        "conditional_test_health_score_is_deployable_forecast": False,
        "reused_test_is_independent_confirmation": False,
        "single_operation_generalization_authorized": False,
        "changes_m7_or_m9m_predictions_or_scores": False,
        "better_overall_accuracy_demonstrated": False,
        "lower_end_to_end_cost_than_pmx_demonstrated": False,
        "pmx_scientific_priority_reduced": False,
        "overall_article_verdict_changed": False,
        "new_live_collections": 0,
        "pmx_invocations": 0,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "selected-file-audit.csv",
                "marginal-scores.csv",
                "conditional-cell-scores.csv",
                "conditional-age-audit.csv",
                "bootstrap-summary.csv",
                "decision-matrix.csv",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "evaluation-manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M9N checkout temporal-failover model")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--config", type=Path, required=True)

    contract = commands.add_parser("build-contract")
    contract.add_argument("--config", type=Path, required=True)
    for role in (
        "m8a-preserved",
        "m8a-audit",
        "m9m-contract",
        "m9m-candidates",
        "m9m-evaluation",
    ):
        contract.add_argument(f"--{role}-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-root", type=Path, required=True)
    contract.add_argument("--m9m-contract-root", type=Path, required=True)
    contract.add_argument("--m9m-candidate-root", type=Path, required=True)
    contract.add_argument("--m9m-evaluation-root", type=Path, required=True)
    contract.add_argument("--out", type=Path, required=True)

    stage = commands.add_parser("stage-learner")
    stage.add_argument("--config", type=Path, required=True)
    stage.add_argument("--contract-manifest", type=Path, required=True)
    stage.add_argument("--qualified-root", type=Path, required=True)
    stage.add_argument("--analysis-root", type=Path, required=True)
    stage.add_argument("--m8a-audit-root", type=Path, required=True)
    stage.add_argument("--m9m-candidate-root", type=Path, required=True)
    stage.add_argument("--out", type=Path, required=True)

    freeze = commands.add_parser("freeze-candidates")
    freeze.add_argument("--config", type=Path, required=True)
    freeze.add_argument("--contract-manifest", type=Path, required=True)
    freeze.add_argument("--learner-root", type=Path, required=True)
    freeze.add_argument("--out", type=Path, required=True)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--config", type=Path, required=True)
    evaluate.add_argument("--contract-manifest", type=Path, required=True)
    evaluate.add_argument("--candidate-root", type=Path, required=True)
    evaluate.add_argument("--qualified-root", type=Path, required=True)
    evaluate.add_argument("--m8a-audit-root", type=Path, required=True)
    evaluate.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "validate":
        result = validate_repository(args.config)
    elif args.command == "build-contract":
        result = build_contract(
            args.config,
            {
                "m8a_preserved": args.m8a_preserved_metadata,
                "m8a_audit": args.m8a_audit_metadata,
                "m9m_contract": args.m9m_contract_metadata,
                "m9m_candidates": args.m9m_candidates_metadata,
                "m9m_evaluation": args.m9m_evaluation_metadata,
            },
            args.m8a_audit_root,
            args.m9m_contract_root,
            args.m9m_candidate_root,
            args.m9m_evaluation_root,
            args.out,
        )
    elif args.command == "stage-learner":
        result = stage_learner_inputs(
            args.config,
            args.contract_manifest,
            args.qualified_root,
            args.analysis_root,
            args.m8a_audit_root,
            args.m9m_candidate_root,
            args.out,
        )
    elif args.command == "freeze-candidates":
        result = generate_candidates(
            args.config, args.contract_manifest, args.learner_root, args.out
        )
    else:
        result = evaluate_candidates(
            args.config,
            args.contract_manifest,
            args.candidate_root,
            args.qualified_root,
            args.m8a_audit_root,
            args.out,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
