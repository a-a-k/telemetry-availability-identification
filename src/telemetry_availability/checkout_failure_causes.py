from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .checkout_localization import (
    _audit_selected_files,
    _selected_directories,
)
from .live_validation_analysis import (
    _bool,
    _near_transition,
    _nearest_tick,
    _timestamp,
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


class CheckoutFailureCauseError(ValueError):
    pass


CALIBRATION_CLASSES = (
    "completion_health_unresolved",
    "aggregate_union_lost_during_request",
    "trace_target_unresolved_union_continuous",
    "target_path_down_at_start_union_continuous",
    "target_path_lost_during_request_union_continuous",
    "target_paths_continuously_up",
)

TEST_CLASSES = (
    "completion_health_unresolved",
    "aggregate_union_lost_during_request",
    "aggregate_union_continuous",
)

CANDIDATES = (
    "aggregate_interval_loss",
    "observed_replica_path_loss",
    "observed_paths_continuously_up",
    "evidence_unresolved",
)


@dataclass(frozen=True)
class CheckoutFailureCauseConfig:
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
    tolerance: float
    resamples: int
    seed: int
    confidence_level: float
    minimum_positive_cells: int
    job_timeout_minutes: int


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CheckoutFailureCauseError(f"required CSV is missing: {path}")
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise CheckoutFailureCauseError(f"{label} must be numeric") from error
    if not math.isfinite(result):
        raise CheckoutFailureCauseError(f"{label} must be finite")
    return result


def _artifact_spec(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "id": record["artifact_id"],
        "name": record["artifact_name"],
        "size_in_bytes": record["size_in_bytes"],
        "sha256": record["sha256"],
    }


def _validate_artifact_record(
    evidence: Mapping[str, Any],
    role: str,
    run_id: int,
    head_sha: str,
    artifact_id: int,
) -> Mapping[str, Any]:
    record = _object(evidence.get(role), f"evidence.{role}")
    if (
        record.get("run_id") != run_id
        or _commit(record.get("head_sha"), f"{role}.head_sha") != head_sha
        or record.get("artifact_id") != artifact_id
    ):
        raise CheckoutFailureCauseError(f"M9L {role} anchor differs")
    _string(record.get("artifact_name"), f"{role}.artifact_name")
    _positive(record.get("size_in_bytes"), f"{role}.size")
    _sha256(record.get("sha256"), f"{role}.sha256")
    _string(record.get("expires_at"), f"{role}.expires_at")
    return record


def load_checkout_failure_cause_config(
    path: str | Path,
) -> CheckoutFailureCauseConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9L config"), "root")
    expected = {
        "schema_version": 1,
        "id": "m9l_checkout_route_up_failure_cause_discrimination",
        "status": "frozen_before_first_m9l_remote_discrimination",
        "diagnostic_only": True,
        "changes_m7_predictions_or_scores": False,
        "new_live_collection": "forbidden",
        "pmx_invocation": "forbidden",
    }
    for key, value in expected.items():
        if root.get(key) != value:
            raise CheckoutFailureCauseError(f"M9L {key} differs from frozen value")

    article = _object(root.get("article_position"), "article position")
    if dict(article) != {
        "direction_remains_substantive": True,
        "claimed_advantage_demonstrated": False,
        "specified_model_calculation_supported": True,
        "better_predictive_accuracy_demonstrated": False,
        "lower_end_to_end_automation_cost_than_pmx_demonstrated": False,
        "overall_success_or_failure_decided": False,
    }:
        raise CheckoutFailureCauseError("M9L article-position guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    if (
        evidence.get("m7_source_run_id") != 33990678586
        or _commit(evidence.get("m7_source_commit"), "M7 source commit")
        != "b1925736f314da610debd23a586d7b7d00cae7ca"
    ):
        raise CheckoutFailureCauseError("M9L M7 source anchor differs")
    artifact_records = {
        "m8a_preserved": (
            34016153918,
            "7a9744f6bf2db69424efc2ae0197714ebee42505",
            9983956440,
        ),
        "m8a_audit": (
            34016153918,
            "7a9744f6bf2db69424efc2ae0197714ebee42505",
            9983956747,
        ),
        "m9k_localization": (
            34055967110,
            "9b69491a1e0ca76e6a656aae977c1c5c2b8e3d88",
            9995975814,
        ),
        "m9k_decision": (
            34055967110,
            "9b69491a1e0ca76e6a656aae977c1c5c2b8e3d88",
            9995981451,
        ),
    }
    for role, values in artifact_records.items():
        _validate_artifact_record(evidence, role, *values)
    for role in ("m8a_audit", "m9k_localization", "m9k_decision"):
        files = _object(
            _object(evidence[role], role).get("files"), f"{role}.files"
        )
        if not files:
            raise CheckoutFailureCauseError(f"M9L {role} file locks are empty")
        for name, value in files.items():
            _relative(name, f"{role} file")
            record = _object(value, f"{role}.{name}")
            _positive(record.get("bytes"), f"{role}.{name}.bytes")
            _sha256(record.get("sha256"), f"{role}.{name}.sha256")
    decision_evidence = _object(evidence["m9k_decision"], "M9K decision")
    if (
        decision_evidence.get("machine_status")
        != "checkout_overprediction_localized_to_fault_period_route_up_residual_mismatch"
        or decision_evidence.get("classification") != "route_up_residual"
        or decision_evidence.get("next_experiment")
        != "m9l_checkout_route_up_failure_cause_discrimination"
    ):
        raise CheckoutFailureCauseError("M9K decision anchor differs")

    cohort = _object(root.get("cohort"), "cohort")
    placements = tuple(str(value) for value in _list(cohort.get("placements"), "placements"))
    laws = tuple(str(value) for value in _list(cohort.get("failure_laws"), "laws"))
    repetitions = tuple(
        int(value) for value in _list(cohort.get("repetitions"), "repetitions")
    )
    if (
        cohort.get("profile") != "opentelemetry_demo"
        or cohort.get("operation") != "checkout"
        or placements != ("colocated", "split")
        or laws != ("N", "ND")
        or repetitions != tuple(range(10))
        or cohort.get("expected_cells") != 40
        or cohort.get("expected_qualified_files_per_cell") != 9
        or cohort.get("expected_selected_files") != 360
        or cohort.get("primary_period") != "calibration"
        or cohort.get("test_role")
        != "aggregate_interval_corroboration_without_trace_graph"
        or cohort.get("start_population")
        != "original_M9K_stable_route_up_requests"
        or cohort.get("additional_full_trace_role")
        != "posthoc_physical_cause_diagnostic_not_forecast_input"
        or cohort.get("test_trace_graph_access") != "forbidden"
    ):
        raise CheckoutFailureCauseError("M9L cohort differs")

    classification = _object(root.get("classification"), "classification")
    precedence = tuple(
        str(value) for value in _list(classification.get("precedence"), "precedence")
    )
    candidate_components = _object(
        classification.get("candidate_components"), "candidate components"
    )
    expected_components = {
        "aggregate_interval_loss": ["aggregate_union_lost_during_request"],
        "observed_replica_path_loss": [
            "target_path_down_at_start_union_continuous",
            "target_path_lost_during_request_union_continuous",
        ],
        "observed_paths_continuously_up": ["target_paths_continuously_up"],
        "evidence_unresolved": [
            "completion_health_unresolved",
            "trace_target_unresolved_union_continuous",
        ],
    }
    bootstrap = _object(classification.get("bootstrap"), "bootstrap")
    alignment = _finite(
        classification.get("start_alignment_tolerance_seconds"),
        "start alignment tolerance",
    )
    completion_alignment = _finite(
        classification.get("completion_alignment_tolerance_seconds"),
        "completion alignment tolerance",
    )
    transition_guard = _positive(
        classification.get("transition_guard_seconds_each_side"),
        "transition guard",
    )
    tolerance = _finite(classification.get("tolerance"), "tolerance")
    resamples = _positive(bootstrap.get("resamples"), "bootstrap resamples")
    seed = _positive(bootstrap.get("seed"), "bootstrap seed")
    confidence = _finite(bootstrap.get("confidence_level"), "confidence level")
    minimum_positive = _positive(
        classification.get("minimum_positive_cells_for_dominance"),
        "minimum positive cells",
    )
    if (
        precedence != CALIBRATION_CLASSES
        or dict(candidate_components) != expected_components
        or alignment != 1.25
        or completion_alignment != 1.25
        or transition_guard != 1
        or classification.get("interval_rule")
        != "inclusive_tick_indices_from_nearest_start_through_nearest_completion"
        or classification.get("aggregate_route_signal")
        != "max(replica_a_path,replica_b_path)"
        or classification.get("trace_usable_rule")
        != "trace_present_and_positive_span_count_and_nonempty_subset_of_a_b_matching_target_replica_count"
        or classification.get("calibration_identity")
        != "sum_class_of_(failures-(1-q)*requests)/all_stable_requests_equals_M9K_route_up_residual_invariance"
        or classification.get("test_identity")
        != "aggregate_interval_plus_continuous_plus_completion_unresolved_equals_M9K_route_up_residual_invariance"
        or tolerance != 1e-12
        or classification.get("minimum_completion_alignment_fraction") != 0.995
        or classification.get("minimum_route_up_stable_requests_per_cell") != 500
        or classification.get("minimum_mean_resolved_target_trace_fraction") != 0.60
        or classification.get("trace_resolution_equivalence_margin") != 0.10
        or minimum_positive != 32
        or bootstrap.get("unit")
        != "campaign_within_placement_by_failure_law_stratum"
        or resamples != 10000
        or seed != 20260907
        or confidence != 0.95
        or classification.get("aggregate_interval_requires_test_corroboration")
        is not True
        or classification.get(
            "replica_or_continuously_up_requires_trace_adequacy"
        )
        is not True
        or classification.get("timeout_is_descriptive_not_a_cause_assignment")
        is not True
    ):
        raise CheckoutFailureCauseError("M9L classification contract differs")

    decision = _object(root.get("decision"), "decision")
    if dict(decision) != {
        "aggregate_interval_loss": "checkout_residual_localized_to_within_request_aggregate_path_loss",
        "observed_replica_path_loss": "checkout_residual_localized_to_observed_replica_path_loss",
        "observed_paths_continuously_up": "checkout_residual_persists_with_observed_target_paths_continuously_up",
        "evidence_unresolved": "checkout_route_up_failure_cause_unresolved_by_retained_evidence",
        "integrity_fail": "m9l_evidence_or_reconstruction_integrity_failed",
        "next_aggregate_interval_loss": "m9m_checkout_request_duration_state_model_test",
        "next_observed_replica_path_loss": "m9m_checkout_request_level_routing_model_test",
        "next_observed_paths_continuously_up": "m9m_checkout_dependency_and_timeout_semantics",
        "next_evidence_unresolved": "m9m_checkout_minimal_discriminating_instrumentation",
    }:
        raise CheckoutFailureCauseError("M9L decision routing differs")
    workflow = _object(root.get("workflow"), "workflow")
    if dict(workflow) != {
        "jobs": 3,
        "job_timeout_minutes": 360,
        "heavy_analysis_only_in_github_actions": True,
        "artifact_retention_days": 90,
    }:
        raise CheckoutFailureCauseError("M9L workflow contract differs")
    guards = _object(root.get("interpretation_guardrails"), "guardrails")
    if any(value is not False for value in guards.values()):
        raise CheckoutFailureCauseError("all M9L interpretation guards must be false")

    return CheckoutFailureCauseConfig(
        path=config_path,
        raw=root,
        profile="opentelemetry_demo",
        operation="checkout",
        placements=placements,
        failure_laws=laws,
        repetitions=repetitions,
        expected_cells=40,
        alignment_tolerance=alignment,
        transition_guard=transition_guard,
        tolerance=tolerance,
        resamples=resamples,
        seed=seed,
        confidence_level=confidence,
        minimum_positive_cells=minimum_positive,
        job_timeout_minutes=360,
    )


def validate_repository(config_path: str | Path) -> Mapping[str, Any]:
    config = load_checkout_failure_cause_config(config_path)
    root = config.path.resolve().parents[1]
    locks = []
    for value in _list(config.raw.get("repository_locks"), "repository locks"):
        record = _object(value, "repository lock")
        relative = _relative(record.get("path"), "repository lock path")
        locks.append(_audit_file(root / relative, record, str(relative)))
    manual = root / _relative(config.raw.get("manual_actions_log"), "manual log")
    if not manual.is_file() or manual.stat().st_size <= 100:
        raise CheckoutFailureCauseError("M9L manual-actions log is missing or empty")
    return {
        "schema_version": 1,
        "kind": "m9l_repository_validation",
        "status": "m9l_repository_contract_valid",
        "config_sha256": file_sha256(config.path),
        "repository_locks": locks,
        "expected_cells": config.expected_cells,
        "job_timeout_minutes": config.job_timeout_minutes,
        "pmx_invocations": 0,
        "new_live_collections": 0,
    }


def _audit_metadata(
    config: CheckoutFailureCauseConfig,
    role: str,
    metadata_path: Path,
) -> Mapping[str, Any]:
    record = _object(config.raw["evidence"][role], f"evidence.{role}")
    return _audit_artifact_metadata(
        metadata_path,
        _artifact_spec(record),
        role,
        int(record["run_id"]),
        str(record["head_sha"]),
    )


def _audit_locked_files(
    root: Path, records: Mapping[str, Any], label: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, value in records.items():
        record = _object(value, f"{label}.{name}")
        audit = _audit_file(
            root / _relative(name, f"{label} path"), record, f"{label} {name}"
        )
        rows.append({"role": label, "path": name, **audit})
    return rows


def build_contract(
    config_path: str | Path,
    m8a_preserved_metadata: Path,
    m8a_audit_metadata: Path,
    m9k_localization_metadata: Path,
    m9k_decision_metadata: Path,
    m8a_audit_root: Path,
    m9k_localization_root: Path,
    m9k_decision_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_checkout_failure_cause_config(config_path)
    metadata = {
        role: _audit_metadata(config, role, path)
        for role, path in (
            ("m8a_preserved", m8a_preserved_metadata),
            ("m8a_audit", m8a_audit_metadata),
            ("m9k_localization", m9k_localization_metadata),
            ("m9k_decision", m9k_decision_metadata),
        )
    }
    evidence = config.raw["evidence"]
    audits: list[dict[str, Any]] = []
    for role, root in (
        ("m8a_audit", m8a_audit_root),
        ("m9k_localization", m9k_localization_root),
        ("m9k_decision", m9k_decision_root),
    ):
        audits.extend(
            _audit_locked_files(
                root,
                _object(evidence[role]["files"], f"{role}.files"),
                role,
            )
        )

    m8a = _object(
        _load_json(m8a_audit_root / "manifest.json", "M8A manifest"),
        "M8A manifest",
    )
    quality = _object(m8a.get("quality"), "M8A quality")
    if (
        m8a.get("source_run_id") != "33990678586"
        or m8a.get("artifact_counts", {}).get("qualified_cell") != 160
        or m8a.get("row_counts", {}).get("identities") != 160
        or any(int(value) != 0 for value in quality.values())
    ):
        raise CheckoutFailureCauseError("accepted M8A contract differs")

    localization = _object(
        _load_json(
            m9k_localization_root / "localization-manifest.json",
            "M9K localization",
        ),
        "M9K localization",
    )
    dominance = _object(localization.get("dominance"), "M9K dominance")
    if (
        localization.get("status")
        != evidence["m9k_decision"]["machine_status"]
        or localization.get("integrity_passed") is not True
        or localization.get("cell_count") != config.expected_cells
        or localization.get("decomposition_rows") != 80
        or dominance.get("classification") != "route_up_residual"
        or dominance.get("route_up_residual_dominant") is not True
        or dominance.get("calibration_corroborated") is not True
        or localization.get("pmx_invocations") != 0
        or localization.get("new_live_collections") != 0
    ):
        raise CheckoutFailureCauseError("accepted M9K localization differs")
    decision = _object(
        _load_json(m9k_decision_root / "decision-manifest.json", "M9K decision"),
        "M9K decision",
    )
    if (
        decision.get("status") != evidence["m9k_decision"]["machine_status"]
        or decision.get("technical_evidence_accepted") is not True
        or decision.get("classification") != "route_up_residual"
        or decision.get("next_experiment")
        != "m9l_checkout_route_up_failure_cause_discrimination"
        or decision.get("overall_article_verdict_changed") is not False
    ):
        raise CheckoutFailureCauseError("accepted M9K decision differs")

    period_rows = _rows(m9k_localization_root / "period-state.csv")
    decomposition_rows = _rows(m9k_localization_root / "cell-decomposition.csv")
    expected_period = config.expected_cells * 4
    if len(period_rows) != expected_period or len(decomposition_rows) != 80:
        raise CheckoutFailureCauseError("M9K retained row census differs")

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "artifact-file-audit.csv",
        ["role", "path", "bytes", "sha256", "matches"],
        audits,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9l_checkout_failure_cause_contract",
        "status": "m9k_route_up_residual_and_retained_evidence_verified",
        "config_sha256": file_sha256(config.path),
        "artifact_metadata": metadata,
        "artifact_file_audits": len(audits),
        "target": {"profile": config.profile, "operation": config.operation},
        "selected_cells": config.expected_cells,
        "m9k_status": localization["status"],
        "m9k_classification": dominance["classification"],
        "m9k_machine_decision_rewritten": False,
        "full_retained_trace_credited_as_forecast_input": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "files": {
            "artifact-file-audit.csv": file_sha256(
                out / "artifact-file-audit.csv"
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "contract-manifest.json", manifest)
    return manifest


def _expected_identities(
    config: CheckoutFailureCauseConfig,
) -> set[tuple[str, str, str, int]]:
    return {
        (config.profile, placement, law, repetition)
        for placement in config.placements
        for law in config.failure_laws
        for repetition in config.repetitions
    }


def _path_value(tick: Any, replica: str) -> int:
    if replica == "a":
        return int(tick.signals[2])
    if replica == "b":
        return int(tick.signals[3])
    raise CheckoutFailureCauseError(f"unknown target replica {replica!r}")


def _request_facts(
    row: Mapping[str, str],
    ticks: Sequence[Any],
    alignment_tolerance: float,
    transition_guard: int,
    *,
    allow_trace: bool,
) -> dict[str, Any]:
    tick_tuple = tuple(ticks)
    start = _timestamp(row["started_at"])
    completion = _timestamp(row["completed_at"])
    start_index, start_distance = _nearest_tick(start, tick_tuple)
    transitions = _transition_times(tick_tuple)
    start_aligned = start_distance <= alignment_tolerance
    stable = start_aligned and not _near_transition(
        start, transitions, transition_guard
    )
    route_up_at_start = bool(
        start_aligned
        and (tick_tuple[start_index].signals[2] or tick_tuple[start_index].signals[3])
    )
    selected = stable and route_up_at_start

    replicas = tuple(
        sorted(
            set(
                value
                for value in str(row.get("target_replicas", "")).split(";")
                if value
            )
        )
    )
    try:
        target_replica_count = int(row.get("target_replica_count", "0") or 0)
        span_count = int(row.get("span_count", "0") or 0)
    except (TypeError, ValueError) as error:
        raise CheckoutFailureCauseError("invalid retained trace counts") from error
    trace_present = bool(_bool(row.get("trace_present", "false"))) if allow_trace else False
    trace_usable = bool(
        allow_trace
        and trace_present
        and span_count > 0
        and replicas
        and set(replicas).issubset({"a", "b"})
        and target_replica_count == len(replicas)
    )

    result: dict[str, Any] = {
        "request_id": row["request_id"],
        "period": row["period"],
        "operation": row["operation"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "duration_seconds": completion - start,
        "success": int(_bool(row["semantic_success"])),
        "timed_out": int(_bool(row.get("timed_out", "false"))),
        "start_tick_index": start_index,
        "start_alignment_seconds": start_distance,
        "start_aligned": start_aligned,
        "stable_at_start": stable,
        "route_up_at_start": route_up_at_start,
        "selected_route_up": selected,
        "trace_present": trace_present if allow_trace else "",
        "span_count": span_count if allow_trace else "",
        "target_replicas": ";".join(replicas) if allow_trace else "",
        "target_replica_count": target_replica_count if allow_trace else "",
        "trace_target_usable": trace_usable if allow_trace else "",
        "completion_tick_index": "",
        "completion_alignment_seconds": "",
        "completion_aligned": "",
        "interval_tick_count": "",
        "aggregate_union_continuous": "",
        "target_paths_up_at_start": "",
        "target_paths_continuous": "",
        "class": "",
    }
    if not selected:
        return result

    completion_index, completion_distance = _nearest_tick(completion, tick_tuple)
    completion_aligned = bool(
        completion_distance <= alignment_tolerance
        and completion >= start
        and completion_index >= start_index
    )
    result.update(
        {
            "completion_tick_index": completion_index,
            "completion_alignment_seconds": completion_distance,
            "completion_aligned": completion_aligned,
        }
    )
    if not completion_aligned:
        result["class"] = "completion_health_unresolved"
        return result

    interval = tick_tuple[start_index : completion_index + 1]
    union_continuous = all(tick.signals[2] or tick.signals[3] for tick in interval)
    result["interval_tick_count"] = len(interval)
    result["aggregate_union_continuous"] = union_continuous
    if not union_continuous:
        result["class"] = "aggregate_union_lost_during_request"
        return result
    if not allow_trace:
        result["class"] = "aggregate_union_continuous"
        return result
    if not trace_usable:
        result["class"] = "trace_target_unresolved_union_continuous"
        return result

    paths_up_at_start = all(
        _path_value(tick_tuple[start_index], replica) for replica in replicas
    )
    paths_continuous = all(
        _path_value(tick, replica) for tick in interval for replica in replicas
    )
    result["target_paths_up_at_start"] = paths_up_at_start
    result["target_paths_continuous"] = paths_continuous
    if not paths_up_at_start:
        result["class"] = "target_path_down_at_start_union_continuous"
    elif not paths_continuous:
        result["class"] = "target_path_lost_during_request_union_continuous"
    else:
        result["class"] = "target_paths_continuously_up"
    return result


def _m9k_period_key(row: Mapping[str, str]) -> tuple[str, str, str, int, str]:
    return (
        str(row["profile"]),
        str(row["placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
        str(row["period"]),
    )


def _m9k_period_rows(
    config: CheckoutFailureCauseConfig, rows: Sequence[Mapping[str, str]]
) -> dict[tuple[str, str, str, int, str], Mapping[str, str]]:
    selected = [
        row
        for row in rows
        if row.get("profile") == config.profile
        and row.get("view") == "stable"
        and row.get("period") in {"calibration", "test"}
        and row.get("placement") in config.placements
        and row.get("failure_law") in config.failure_laws
        and int(row.get("repetition", -1)) in config.repetitions
    ]
    result = {_m9k_period_key(row): row for row in selected}
    expected = {
        (*identity, period)
        for identity in _expected_identities(config)
        for period in ("calibration", "test")
    }
    if len(selected) != 80 or len(result) != 80 or set(result) != expected:
        raise CheckoutFailureCauseError("M9K stable period matrix differs")
    return result


def _m9k_decomposition_rows(
    config: CheckoutFailureCauseConfig, rows: Sequence[Mapping[str, str]]
) -> dict[tuple[str, str, str, int, str], Mapping[str, str]]:
    selected = [
        row
        for row in rows
        if row.get("profile") == config.profile
        and row.get("period") in {"calibration", "test"}
        and row.get("placement") in config.placements
        and row.get("failure_law") in config.failure_laws
        and int(row.get("repetition", -1)) in config.repetitions
    ]
    result = {_m9k_period_key(row): row for row in selected}
    if len(selected) != 80 or len(result) != 80:
        raise CheckoutFailureCauseError("M9K decomposition matrix differs")
    return result


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise CheckoutFailureCauseError("cannot average an empty sequence")
    return math.fsum(values) / len(values)


def _summary_for_class(
    identity: tuple[str, str, str, int],
    period: str,
    class_name: str,
    facts: Sequence[Mapping[str, Any]],
    q: float,
    stable_requests: int,
) -> dict[str, Any]:
    selected = [row for row in facts if row["class"] == class_name]
    requests = len(selected)
    successes = sum(int(row["success"]) for row in selected)
    failures = requests - successes
    timeouts = sum(int(row["timed_out"]) for row in selected)
    contribution = (failures - (1.0 - q) * requests) / stable_requests
    return {
        "profile": identity[0],
        "placement": identity[1],
        "failure_law": identity[2],
        "repetition": identity[3],
        "period": period,
        "class": class_name,
        "requests": requests,
        "successes": successes,
        "failures": failures,
        "timeouts": timeouts,
        "failure_rate": failures / requests if requests else "",
        "excess_residual_contribution": contribution,
    }


def _bootstrap_summary(
    rows: Sequence[Mapping[str, Any]],
    resamples: int,
    seed: int,
    confidence_level: float,
) -> dict[str, dict[str, float]]:
    base_metrics = [
        *CANDIDATES,
        "calibration_residual",
        "resolved_target_trace_fraction",
        "resolution_failure_minus_success",
        "test_aggregate_interval_loss",
        "test_aggregate_union_continuous",
        "test_completion_unresolved",
        "test_residual",
    ]
    pair_metrics = [
        f"{left}__minus__{right}"
        for left in CANDIDATES
        for right in CANDIDATES
        if left != right
    ]
    test_pairs = [
        "test_aggregate_interval_loss__minus__test_aggregate_union_continuous",
        "test_aggregate_interval_loss__minus__test_completion_unresolved",
    ]
    metrics = [*base_metrics, *pair_metrics, *test_pairs]

    def metric_value(row: Mapping[str, Any], metric: str) -> float:
        if "__minus__" in metric:
            left, right = metric.split("__minus__", maxsplit=1)
            return float(row[left]) - float(row[right])
        return float(row[metric])

    strata: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(str(row["placement"]), str(row["failure_law"]))].append(row)
    if sorted(len(values) for values in strata.values()) != [10, 10, 10, 10]:
        raise CheckoutFailureCauseError(
            "bootstrap strata must each contain ten campaigns"
        )
    generator = np.random.default_rng(seed)
    draws = {metric: np.empty(resamples, dtype=float) for metric in metrics}
    ordered = [strata[key] for key in sorted(strata)]
    for iteration in range(resamples):
        sample: list[Mapping[str, Any]] = []
        for values in ordered:
            indexes = generator.integers(0, len(values), size=len(values))
            sample.extend(values[int(index)] for index in indexes)
        for metric in metrics:
            draws[metric][iteration] = _mean(
                [metric_value(row, metric) for row in sample]
            )
    alpha = (1.0 - confidence_level) / 2.0
    result: dict[str, dict[str, float]] = {}
    for metric in metrics:
        result[metric] = {
            "estimate": _mean([metric_value(row, metric) for row in rows]),
            "lower": float(np.quantile(draws[metric], alpha)),
            "upper": float(np.quantile(draws[metric], 1.0 - alpha)),
        }
    return result


def _classify_dominance(
    rows: Sequence[Mapping[str, Any]],
    bootstrap: Mapping[str, Mapping[str, float]],
    minimum_positive_cells: int,
    minimum_trace_fraction: float,
    resolution_margin: float,
) -> Mapping[str, Any]:
    positive_cells = {
        candidate: sum(float(row[candidate]) > 0 for row in rows)
        for candidate in CANDIDATES
    }
    dominant: dict[str, bool] = {}
    for candidate in CANDIDATES:
        dominant[candidate] = bool(
            bootstrap[candidate]["lower"] > 0
            and positive_cells[candidate] >= minimum_positive_cells
            and all(
                bootstrap[f"{candidate}__minus__{other}"]["lower"] > 0
                for other in CANDIDATES
                if other != candidate
            )
        )
    winners = [candidate for candidate, passed in dominant.items() if passed]
    if len(winners) > 1:
        raise CheckoutFailureCauseError("multiple mutually exclusive candidates won")
    raw_dominant = winners[0] if winners else "none"

    resolution = bootstrap["resolution_failure_minus_success"]
    trace_adequacy = bool(
        bootstrap["resolved_target_trace_fraction"]["lower"]
        >= minimum_trace_fraction
        and resolution["lower"] > -resolution_margin
        and resolution["upper"] < resolution_margin
    )
    test_positive = sum(
        float(row["test_aggregate_interval_loss"]) > 0 for row in rows
    )
    test_corroboration = bool(
        bootstrap["test_aggregate_interval_loss"]["lower"] > 0
        and bootstrap[
            "test_aggregate_interval_loss__minus__test_aggregate_union_continuous"
        ]["lower"]
        > 0
        and bootstrap[
            "test_aggregate_interval_loss__minus__test_completion_unresolved"
        ]["lower"]
        > 0
        and test_positive >= minimum_positive_cells
    )

    if raw_dominant == "aggregate_interval_loss" and test_corroboration:
        classification = raw_dominant
    elif raw_dominant in {
        "observed_replica_path_loss",
        "observed_paths_continuously_up",
    } and trace_adequacy:
        classification = raw_dominant
    elif raw_dominant == "evidence_unresolved":
        classification = "evidence_unresolved"
    else:
        classification = "evidence_unresolved"
    return {
        "classification": classification,
        "raw_dominant_candidate": raw_dominant,
        "candidate_dominance": dominant,
        "candidate_positive_cells": positive_cells,
        "trace_adequacy_passed": trace_adequacy,
        "trace_coverage_lower": bootstrap["resolved_target_trace_fraction"][
            "lower"
        ],
        "resolution_difference_interval": {
            "lower": resolution["lower"],
            "upper": resolution["upper"],
        },
        "test_aggregate_interval_corroborated": test_corroboration,
        "test_aggregate_interval_positive_cells": test_positive,
    }


def run_discrimination(
    config_path: str | Path,
    contract_manifest_path: Path,
    qualified_root: Path,
    m8a_audit_root: Path,
    m9k_localization_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutFailureCauseError(
            "full M9L discrimination may run only in GitHub Actions"
        )
    config = load_checkout_failure_cause_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9L contract"), "contract")
    if (
        contract.get("status")
        != "m9k_route_up_residual_and_retained_evidence_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or contract.get("selected_cells") != config.expected_cells
    ):
        raise CheckoutFailureCauseError("M9L contract manifest differs")

    evidence = config.raw["evidence"]
    _audit_locked_files(
        m8a_audit_root,
        _object(evidence["m8a_audit"]["files"], "M8A files"),
        "m8a_audit",
    )
    _audit_locked_files(
        m9k_localization_root,
        _object(evidence["m9k_localization"]["files"], "M9K files"),
        "m9k_localization",
    )

    directories, census = _selected_directories(config, qualified_root)  # type: ignore[arg-type]
    file_rows = _audit_selected_files(  # type: ignore[arg-type]
        config,
        qualified_root,
        directories,
        m8a_audit_root / "file-inventory.csv",
    )
    m9k_period = _m9k_period_rows(
        config, _rows(m9k_localization_root / "period-state.csv")
    )
    m9k_decomposition = _m9k_decomposition_rows(
        config, _rows(m9k_localization_root / "cell-decomposition.csv")
    )

    request_rows: list[dict[str, Any]] = []
    class_rows: list[dict[str, Any]] = []
    cell_rows: list[dict[str, Any]] = []
    m9k_count_mismatches = 0
    reconstruction_errors: list[float] = []
    completion_alignment_fractions: list[float] = []
    route_up_counts: list[int] = []

    for directory in directories:
        cell = load_qualified_cell(directory)
        identity = cell.identity
        if identity not in _expected_identities(config):
            raise CheckoutFailureCauseError(f"unexpected selected identity: {identity}")
        raw_learner = [
            row
            for row in _rows(directory / "learner" / "requests.csv")
            if row.get("period") == "calibration"
            and row.get("operation") == config.operation
        ]
        raw_test = [
            row
            for row in _rows(directory / "evaluator" / "test-requests.csv")
            if row.get("period") == "test" and row.get("operation") == config.operation
        ]
        facts_by_period: dict[str, list[dict[str, Any]]] = {}
        for period, raw, ticks, allow_trace in (
            ("calibration", raw_learner, cell.health, True),
            ("test", raw_test, cell.test_health, False),
        ):
            facts = [
                _request_facts(
                    row,
                    ticks,
                    config.alignment_tolerance,
                    config.transition_guard,
                    allow_trace=allow_trace,
                )
                for row in raw
            ]
            facts_by_period[period] = facts
            for fact in facts:
                request_rows.append(
                    {
                        "profile": identity[0],
                        "placement": identity[1],
                        "failure_law": identity[2],
                        "repetition": identity[3],
                        **fact,
                    }
                )

        per_period_summaries: dict[str, list[dict[str, Any]]] = {}
        per_period_contributions: dict[str, dict[str, float]] = {}
        per_period_selected: dict[str, list[dict[str, Any]]] = {}
        for period, classes in (
            ("calibration", CALIBRATION_CLASSES),
            ("test", TEST_CLASSES),
        ):
            facts = facts_by_period[period]
            stable = [row for row in facts if row["stable_at_start"]]
            selected = [row for row in facts if row["selected_route_up"]]
            per_period_selected[period] = selected
            expected = m9k_period[(*identity, period)]
            stable_requests = len(stable)
            stable_successes = sum(int(row["success"]) for row in stable)
            route_up_successes = sum(int(row["success"]) for row in selected)
            comparisons = (
                (len(facts), int(expected["operation_requests"])),
                (stable_requests, int(expected["view_requests"])),
                (stable_successes, int(expected["view_successes"])),
                (len(selected), int(expected["route_up_requests"])),
                (route_up_successes, int(expected["route_up_successes"])),
            )
            m9k_count_mismatches += sum(left != right for left, right in comparisons)
            route_up_counts.append(len(selected))
            completion_alignment_fractions.append(
                sum(bool(row["completion_aligned"]) for row in selected)
                / len(selected)
            )
            q = _finite(
                m9k_decomposition[(*identity, period)]["clean_residual_q"],
                "M9K q",
            )
            summaries = [
                _summary_for_class(
                    identity, period, class_name, selected, q, stable_requests
                )
                for class_name in classes
            ]
            class_rows.extend(summaries)
            per_period_summaries[period] = summaries
            per_period_contributions[period] = {
                row["class"]: float(row["excess_residual_contribution"])
                for row in summaries
            }
            observed_classes = [str(row["class"]) for row in selected]
            if any(class_name not in classes for class_name in observed_classes):
                raise CheckoutFailureCauseError(
                    f"non-exhaustive {period} class at {identity}"
                )

        calibration = per_period_contributions["calibration"]
        test = per_period_contributions["test"]
        candidate_map = config.raw["classification"]["candidate_components"]
        candidate_values = {
            candidate: math.fsum(calibration[class_name] for class_name in classes)
            for candidate, classes in candidate_map.items()
        }
        calibration_residual = _finite(
            m9k_decomposition[(*identity, "calibration")][
                "route_up_residual_invariance"
            ],
            "M9K calibration residual",
        )
        test_residual = _finite(
            m9k_decomposition[(*identity, "test")][
                "route_up_residual_invariance"
            ],
            "M9K test residual",
        )
        calibration_error = math.fsum(candidate_values.values()) - calibration_residual
        test_values = {
            "test_completion_unresolved": test["completion_health_unresolved"],
            "test_aggregate_interval_loss": test[
                "aggregate_union_lost_during_request"
            ],
            "test_aggregate_union_continuous": test["aggregate_union_continuous"],
        }
        test_error = math.fsum(test_values.values()) - test_residual
        reconstruction_errors.extend((calibration_error, test_error))

        calibration_selected = per_period_selected["calibration"]
        resolved = [row for row in calibration_selected if row["trace_target_usable"]]
        failures = [row for row in calibration_selected if not row["success"]]
        successes = [row for row in calibration_selected if row["success"]]
        if not failures or not successes:
            raise CheckoutFailureCauseError(
                f"trace adequacy requires failures and successes: {identity}"
            )
        resolved_fraction = len(resolved) / len(calibration_selected)
        resolution_failure = (
            sum(bool(row["trace_target_usable"]) for row in failures) / len(failures)
        )
        resolution_success = (
            sum(bool(row["trace_target_usable"]) for row in successes) / len(successes)
        )
        cell_rows.append(
            {
                "profile": identity[0],
                "placement": identity[1],
                "failure_law": identity[2],
                "repetition": identity[3],
                "calibration_stable_requests": int(
                    m9k_period[(*identity, "calibration")]["view_requests"]
                ),
                "calibration_route_up_requests": len(calibration_selected),
                "calibration_route_up_failures": len(failures),
                "calibration_residual": calibration_residual,
                **candidate_values,
                "resolved_target_trace_fraction": resolved_fraction,
                "resolved_target_trace_fraction_failures": resolution_failure,
                "resolved_target_trace_fraction_successes": resolution_success,
                "resolution_failure_minus_success": (
                    resolution_failure - resolution_success
                ),
                "calibration_completion_alignment_fraction": (
                    sum(bool(row["completion_aligned"]) for row in calibration_selected)
                    / len(calibration_selected)
                ),
                "calibration_timeout_failures": sum(
                    int(row["timed_out"]) for row in failures
                ),
                "test_route_up_requests": len(per_period_selected["test"]),
                "test_residual": test_residual,
                **test_values,
                "test_completion_alignment_fraction": (
                    sum(
                        bool(row["completion_aligned"])
                        for row in per_period_selected["test"]
                    )
                    / len(per_period_selected["test"])
                ),
                "calibration_reconstruction_error": calibration_error,
                "test_reconstruction_error": test_error,
            }
        )

    bootstrap = _bootstrap_summary(
        cell_rows, config.resamples, config.seed, config.confidence_level
    )
    classification_config = config.raw["classification"]
    discrimination = _classify_dominance(
        cell_rows,
        bootstrap,
        config.minimum_positive_cells,
        float(classification_config["minimum_mean_resolved_target_trace_fraction"]),
        float(classification_config["trace_resolution_equivalence_margin"]),
    )
    max_reconstruction = max(abs(value) for value in reconstruction_errors)
    minimum_completion_alignment = min(completion_alignment_fractions)
    minimum_route_up = min(route_up_counts)
    quality = {
        "qualified_manifest_census": census,
        "selected_cells": len(directories),
        "selected_files_audited": len(file_rows),
        "selected_file_mismatches": 0,
        "m9k_request_count_mismatches": m9k_count_mismatches,
        "minimum_route_up_stable_requests": minimum_route_up,
        "minimum_completion_alignment_fraction": minimum_completion_alignment,
        "maximum_residual_reconstruction_error": max_reconstruction,
        "calibration_class_rows": sum(
            row["period"] == "calibration" for row in class_rows
        ),
        "test_class_rows": sum(row["period"] == "test" for row in class_rows),
    }
    integrity_pass = bool(
        census == 160
        and len(directories) == config.expected_cells
        and len(file_rows) == int(config.raw["cohort"]["expected_selected_files"])
        and m9k_count_mismatches == 0
        and minimum_route_up
        >= int(classification_config["minimum_route_up_stable_requests_per_cell"])
        and minimum_completion_alignment
        >= float(classification_config["minimum_completion_alignment_fraction"])
        and max_reconstruction <= config.tolerance
        and quality["calibration_class_rows"] == 240
        and quality["test_class_rows"] == 120
    )
    decision = _object(config.raw["decision"], "decision")
    status = (
        str(decision[str(discrimination["classification"])])
        if integrity_pass
        else str(decision["integrity_fail"])
    )

    out.mkdir(parents=True, exist_ok=True)
    request_fields = [
        "profile",
        "placement",
        "failure_law",
        "repetition",
        "request_id",
        "period",
        "operation",
        "started_at",
        "completed_at",
        "duration_seconds",
        "success",
        "timed_out",
        "start_tick_index",
        "start_alignment_seconds",
        "start_aligned",
        "stable_at_start",
        "route_up_at_start",
        "selected_route_up",
        "trace_present",
        "span_count",
        "target_replicas",
        "target_replica_count",
        "trace_target_usable",
        "completion_tick_index",
        "completion_alignment_seconds",
        "completion_aligned",
        "interval_tick_count",
        "aggregate_union_continuous",
        "target_paths_up_at_start",
        "target_paths_continuous",
        "class",
    ]
    _write_csv(out / "request-classification.csv", request_fields, request_rows)
    _write_csv(
        out / "class-summary.csv",
        [
            "profile",
            "placement",
            "failure_law",
            "repetition",
            "period",
            "class",
            "requests",
            "successes",
            "failures",
            "timeouts",
            "failure_rate",
            "excess_residual_contribution",
        ],
        class_rows,
    )
    cell_fields = [
        "profile",
        "placement",
        "failure_law",
        "repetition",
        "calibration_stable_requests",
        "calibration_route_up_requests",
        "calibration_route_up_failures",
        "calibration_residual",
        *CANDIDATES,
        "resolved_target_trace_fraction",
        "resolved_target_trace_fraction_failures",
        "resolved_target_trace_fraction_successes",
        "resolution_failure_minus_success",
        "calibration_completion_alignment_fraction",
        "calibration_timeout_failures",
        "test_route_up_requests",
        "test_residual",
        "test_aggregate_interval_loss",
        "test_aggregate_union_continuous",
        "test_completion_unresolved",
        "test_completion_alignment_fraction",
        "calibration_reconstruction_error",
        "test_reconstruction_error",
    ]
    _write_csv(out / "cell-candidates.csv", cell_fields, cell_rows)
    bootstrap_rows = [
        {"metric": metric, **values} for metric, values in bootstrap.items()
    ]
    _write_csv(
        out / "bootstrap-summary.csv",
        ["metric", "estimate", "lower", "upper"],
        bootstrap_rows,
    )
    _write_csv(
        out / "selected-file-audit.csv",
        ["path", "bytes", "sha256", "matches_m8a_inventory"],
        file_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9l_checkout_route_up_failure_cause_discrimination",
        "status": status,
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "integrity_passed": integrity_pass,
        "quality": quality,
        "target": {"profile": config.profile, "operation": config.operation},
        "cell_count": len(cell_rows),
        "request_rows": len(request_rows),
        "class_rows": len(class_rows),
        "bootstrap": bootstrap,
        "discrimination": discrimination,
        "full_retained_trace_credited_as_forecast_input": False,
        "trace_replica_set_claimed_as_exact_call_time_choice": False,
        "test_trace_graph_accessed": False,
        "changes_m7_predictions_or_scores": False,
        "posthoc_classification_is_confirmatory_accuracy_evidence": False,
        "single_operation_generalization_authorized": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "request-classification.csv",
                "class-summary.csv",
                "cell-candidates.csv",
                "bootstrap-summary.csv",
                "selected-file-audit.csv",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "discrimination-manifest.json", manifest)
    return manifest


def decide(
    config_path: str | Path,
    contract_manifest_path: Path,
    discrimination_manifest_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_checkout_failure_cause_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9L contract"), "contract")
    discrimination = _object(
        _load_json(discrimination_manifest_path, "M9L discrimination"),
        "discrimination",
    )
    config_hash = file_sha256(config.path)
    contract_pass = bool(
        contract.get("config_sha256") == config_hash
        and contract.get("status")
        == "m9k_route_up_residual_and_retained_evidence_verified"
        and contract.get("selected_cells") == config.expected_cells
        and contract.get("pmx_invocations") == 0
        and contract.get("new_live_collections") == 0
    )
    discrimination_pass = bool(
        discrimination.get("config_sha256") == config_hash
        and discrimination.get("contract_manifest_sha256")
        == file_sha256(contract_manifest_path)
        and discrimination.get("integrity_passed") is True
        and discrimination.get("cell_count") == config.expected_cells
        and discrimination.get("test_trace_graph_accessed") is False
        and discrimination.get("pmx_invocations") == 0
        and discrimination.get("new_live_collections") == 0
    )
    result = _object(discrimination.get("discrimination"), "discrimination result")
    classification = str(result.get("classification", "evidence_unresolved"))
    if classification not in CANDIDATES:
        discrimination_pass = False
        classification = "evidence_unresolved"
    rules = _object(config.raw["decision"], "decision")
    expected_status = str(rules[classification])
    status_matches = discrimination.get("status") == expected_status
    if contract_pass and discrimination_pass and status_matches:
        status = expected_status
        next_experiment = str(rules[f"next_{classification}"])
        accepted = True
    else:
        status = str(rules["integrity_fail"])
        next_experiment = str(rules["next_evidence_unresolved"])
        accepted = False

    matrix = [
        {
            "question": "m9k_and_retained_evidence_contract_passed",
            "value": contract_pass,
            "interpretation": "accepted M9K branch and exact retained identities",
        },
        {
            "question": "request_taxonomy_and_residual_reconstruction_passed",
            "value": discrimination_pass,
            "interpretation": "exhaustive calibration/test classes reproduce M9K",
        },
        {
            "question": "raw_dominant_candidate",
            "value": result.get("raw_dominant_candidate", "none"),
            "interpretation": "frozen four-way campaign-bootstrap rule before adequacy",
        },
        {
            "question": "trace_adequacy_passed",
            "value": result.get("trace_adequacy_passed") is True,
            "interpretation": "coverage plus failure/success resolution equivalence",
        },
        {
            "question": "test_aggregate_interval_corroborated",
            "value": result.get("test_aggregate_interval_corroborated") is True,
            "interpretation": "held-out aggregate interval check without test traces",
        },
        {
            "question": "selected_classification",
            "value": classification,
            "interpretation": "frozen branch after applicable evidence gates",
        },
        {
            "question": "m7_prediction_or_article_verdict_changed",
            "value": False,
            "interpretation": "post-result one-operation diagnostic only",
        },
    ]
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "decision-matrix.csv",
        ["question", "value", "interpretation"],
        matrix,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9l_checkout_failure_cause_decision",
        "status": status,
        "config_sha256": config_hash,
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "discrimination_manifest_sha256": file_sha256(
            discrimination_manifest_path
        ),
        "technical_evidence_accepted": accepted,
        "contract_passed": contract_pass,
        "discrimination_integrity_passed": discrimination_pass,
        "classification": classification,
        "discrimination": dict(result),
        "next_experiment": next_experiment,
        "physical_cause_uniquely_identified": False,
        "full_retained_trace_credited_as_forecast_input": False,
        "test_trace_graph_accessed": False,
        "additional_pmx_repair_authorized": False,
        "changes_m7_predictions_or_scores": False,
        "new_live_collection_authorized": False,
        "single_operation_generalization_authorized": False,
        "better_predictive_accuracy_demonstrated": False,
        "lower_end_to_end_automation_cost_than_pmx_demonstrated": False,
        "overall_article_verdict_changed": False,
        "files": {"decision-matrix.csv": file_sha256(out / "decision-matrix.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="M9L checkout route-up failure-cause discrimination"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--config", type=Path, required=True)
    contract = subparsers.add_parser("build-contract")
    contract.add_argument("--config", type=Path, required=True)
    contract.add_argument("--m8a-preserved-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-metadata", type=Path, required=True)
    contract.add_argument("--m9k-localization-metadata", type=Path, required=True)
    contract.add_argument("--m9k-decision-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-root", type=Path, required=True)
    contract.add_argument("--m9k-localization-root", type=Path, required=True)
    contract.add_argument("--m9k-decision-root", type=Path, required=True)
    contract.add_argument("--out", type=Path, required=True)
    discriminate = subparsers.add_parser("discriminate")
    discriminate.add_argument("--config", type=Path, required=True)
    discriminate.add_argument("--contract-manifest", type=Path, required=True)
    discriminate.add_argument("--qualified-root", type=Path, required=True)
    discriminate.add_argument("--m8a-audit-root", type=Path, required=True)
    discriminate.add_argument("--m9k-localization-root", type=Path, required=True)
    discriminate.add_argument("--out", type=Path, required=True)
    decision = subparsers.add_parser("decide")
    decision.add_argument("--config", type=Path, required=True)
    decision.add_argument("--contract-manifest", type=Path, required=True)
    decision.add_argument("--discrimination-manifest", type=Path, required=True)
    decision.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        payload = validate_repository(args.config)
    elif args.command == "build-contract":
        payload = build_contract(
            args.config,
            args.m8a_preserved_metadata,
            args.m8a_audit_metadata,
            args.m9k_localization_metadata,
            args.m9k_decision_metadata,
            args.m8a_audit_root,
            args.m9k_localization_root,
            args.m9k_decision_root,
            args.out,
        )
    elif args.command == "discriminate":
        payload = run_discrimination(
            args.config,
            args.contract_manifest,
            args.qualified_root,
            args.m8a_audit_root,
            args.m9k_localization_root,
            args.out,
        )
    else:
        payload = decide(
            args.config,
            args.contract_manifest,
            args.discrimination_manifest,
            args.out,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
