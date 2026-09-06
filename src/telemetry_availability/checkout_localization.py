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

from .live_validation_analysis import (
    _near_transition,
    _nearest_tick,
    _transition_times,
    load_qualified_cell,
)
from .live_validation_config import load_frozen_live_validation_config
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


class CheckoutLocalizationError(ValueError):
    pass


@dataclass(frozen=True)
class CheckoutLocalizationConfig:
    path: Path
    raw: Mapping[str, Any]
    profile: str
    operation: str
    placements: tuple[str, ...]
    failure_laws: tuple[str, ...]
    repetitions: tuple[int, ...]
    expected_cells: int
    tolerance: float
    alignment_tolerance: float
    transition_guard: int
    bootstrap_resamples: int
    bootstrap_seed: int
    confidence_level: float
    job_timeout_minutes: int


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CheckoutLocalizationError(f"required CSV is missing: {path}")
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise CheckoutLocalizationError(f"{label} must be numeric") from error
    if not math.isfinite(result):
        raise CheckoutLocalizationError(f"{label} must be finite")
    return result


def _artifact_spec(record: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "id": record["artifact_id"],
        "name": record["artifact_name"],
        "size_in_bytes": record["size_in_bytes"],
        "sha256": record["sha256"],
    }


def load_checkout_localization_config(
    path: str | Path,
) -> CheckoutLocalizationConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9K config"), "root")
    expected = {
        "schema_version": 1,
        "id": "m9k_single_operation_overestimation_localization",
        "status": "frozen_before_first_m9k_remote_localization",
        "diagnostic_only": True,
        "changes_m7_predictions_or_scores": False,
        "new_live_collection": "forbidden",
        "pmx_invocation": "forbidden",
    }
    for key, value in expected.items():
        if root.get(key) != value:
            raise CheckoutLocalizationError(f"M9K {key} differs from frozen value")

    article = _object(root.get("article_position"), "article position")
    if dict(article) != {
        "direction_remains_substantive": True,
        "claimed_advantage_demonstrated": False,
        "specified_model_calculation_supported": True,
        "better_predictive_accuracy_demonstrated": False,
        "lower_end_to_end_automation_cost_than_pmx_demonstrated": False,
        "overall_success_or_failure_decided": False,
    }:
        raise CheckoutLocalizationError("M9K article-position guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    if (
        evidence.get("m7_source_run_id") != 33990678586
        or _commit(evidence.get("m7_source_commit"), "M7 source commit")
        != "b1925736f314da610debd23a586d7b7d00cae7ca"
    ):
        raise CheckoutLocalizationError("M9K M7 source anchor differs")
    expected_artifacts = {
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
        "m8b": (
            34017401101,
            "a8737e9519da2fcfafb7cedd999c4c1867653d5b",
            9984348911,
        ),
        "m9j_decision": (
            34054064325,
            "6ad7679941f7303af81b569736deb5b8fe8b1933",
            9995457506,
        ),
    }
    for role, (run_id, head_sha, artifact_id) in expected_artifacts.items():
        record = _object(evidence.get(role), f"evidence.{role}")
        if (
            record.get("run_id") != run_id
            or _commit(record.get("head_sha"), f"{role}.head_sha") != head_sha
            or record.get("artifact_id") != artifact_id
        ):
            raise CheckoutLocalizationError(f"M9K {role} anchor differs")
        _string(record.get("artifact_name"), f"{role}.artifact_name")
        _positive(record.get("size_in_bytes"), f"{role}.size")
        _sha256(record.get("sha256"), f"{role}.sha256")
        _string(record.get("expires_at"), f"{role}.expires_at")

    for role in ("m8a_audit", "m8b"):
        files = _object(_object(evidence[role], role).get("files"), f"{role}.files")
        if not files:
            raise CheckoutLocalizationError(f"M9K {role} file locks are empty")
        for name, value in files.items():
            _relative(name, f"{role} file")
            record = _object(value, f"{role}.{name}")
            _positive(record.get("bytes"), f"{role}.{name}.bytes")
            _sha256(record.get("sha256"), f"{role}.{name}.sha256")
    m9j = _object(evidence["m9j_decision"], "m9j decision")
    m9j_manifest = _object(m9j.get("manifest"), "m9j manifest")
    _relative(m9j_manifest.get("path"), "m9j manifest path")
    _positive(m9j_manifest.get("bytes"), "m9j manifest bytes")
    _sha256(m9j_manifest.get("sha256"), "m9j manifest sha256")
    if (
        m9j.get("machine_status") != "pmx_carrier_negative_pass_positive_unresolved"
        or m9j.get("external_tool_diagnostic_closed") is not True
        or m9j.get("additional_pmx_repair_run_authorized") is not False
    ):
        raise CheckoutLocalizationError("M9J scope boundary differs")

    frozen_analysis = _object(evidence.get("frozen_analysis"), "frozen analysis")
    if set(frozen_analysis) != {"manifest.json", "predictions.csv"}:
        raise CheckoutLocalizationError("M9K frozen analysis file set differs")
    for name, value in frozen_analysis.items():
        _sha256(_object(value, name).get("sha256"), f"{name}.sha256")

    selection = _object(root.get("target_selection"), "target selection")
    if (
        selection.get("source") != "accepted_M8B_bias_detail_before_M9K"
        or selection.get("metric")
        != "unweighted_mean_prediction_minus_test_stable_over_emitted_proposed_rows"
        or selection.get("profile") != "opentelemetry_demo"
        or selection.get("operation") != "checkout"
        or selection.get("selected_emitted_rows") != 55
        or not math.isclose(
            _finite(selection.get("selected_mean"), "selected mean"),
            0.17806941533026183,
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        raise CheckoutLocalizationError("M9K target selection differs")
    ranking = _list(selection.get("ranking"), "target ranking")
    if len(ranking) != 6:
        raise CheckoutLocalizationError("M9K target ranking must contain six operations")
    ranking_means = [
        _finite(_object(value, "ranking row").get("mean"), "ranking mean")
        for value in ranking
    ]
    if ranking_means != sorted(ranking_means, reverse=True):
        raise CheckoutLocalizationError("M9K target ranking is not descending")

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
        or cohort.get("excluded_failure_laws") != ["NC", "NCD"]
        or repetitions != tuple(range(10))
        or cohort.get("expected_cells") != 40
        or cohort.get("expected_qualified_files_per_cell") != 9
        or cohort.get("expected_selected_files") != 360
        or cohort.get("method") != "proposed"
        or cohort.get("mode") != "sampled_mixed"
        or cohort.get("scope") != "current"
        or cohort.get("view") != "stable"
        or cohort.get("prediction_status") != "identified_exact_likelihood"
        or cohort.get("requires_target_group") is not True
    ):
        raise CheckoutLocalizationError("M9K checkout cohort differs")
    summary = _object(cohort.get("m8b_known_summary"), "known summary")
    expected_summary = {
        "rows": 40,
        "mean_prediction": 0.9470192674169405,
        "mean_test_stable_rate": 0.773958749559624,
        "mean_signed_error": 0.17306051785731663,
        "mean_clean_residual": 0.9938271604938272,
        "mean_route_prediction": 0.9529013746679779,
    }
    for key, value in expected_summary.items():
        observed = summary.get(key)
        if key == "rows":
            matches = observed == value
        else:
            matches = math.isclose(
                _finite(observed, f"known summary {key}"),
                value,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        if not matches:
            raise CheckoutLocalizationError(f"M9K known summary {key} differs")

    localization = _object(root.get("localization"), "localization")
    bootstrap = _object(localization.get("bootstrap"), "bootstrap")
    tolerance = _finite(localization.get("tolerance"), "tolerance")
    alignment = _finite(
        localization.get("alignment_tolerance_seconds"), "alignment tolerance"
    )
    transition_guard = _positive(
        localization.get("transition_guard_seconds_each_side"), "transition guard"
    )
    resamples = _positive(bootstrap.get("resamples"), "bootstrap resamples")
    seed = _positive(bootstrap.get("seed"), "bootstrap seed")
    confidence = _finite(bootstrap.get("confidence_level"), "confidence level")
    if (
        localization.get("health_route_signal")
        != "max(replica_a_path,replica_b_path)"
        or alignment != 1.25
        or transition_guard != 1
        or localization.get("periods") != ["calibration", "test"]
        or localization.get("views") != ["all_sequence", "stable"]
        or localization.get("decomposition_view") != "stable"
        or localization.get("components")
        != [
            "route_state_exposure",
            "route_up_residual_invariance",
            "route_down_success_offset",
        ]
        or localization.get("counterfactuals_are_diagnostic_not_revised_predictions")
        is not True
        or localization.get("test_outcomes_may_select_target_or_threshold") is not False
        or tolerance != 1e-12
        or localization.get("minimum_alignment_fraction") != 0.995
        or localization.get("minimum_stable_requests_per_cell_period") != 500
        or localization.get("minimum_positive_cells_for_dominance") != 32
        or localization.get("minimum_known_mean_gap") != 0.10
        or bootstrap.get("unit")
        != "campaign_within_placement_by_failure_law_stratum"
        or resamples != 10000
        or seed != 20260906
        or confidence != 0.95
        or localization.get("calibration_corroboration_required") is not True
    ):
        raise CheckoutLocalizationError("M9K localization contract differs")

    decision = _object(root.get("decision"), "decision")
    if dict(decision) != {
        "route_up_residual": "checkout_overprediction_localized_to_fault_period_route_up_residual_mismatch",
        "route_state_exposure": "checkout_overprediction_localized_to_route_state_exposure_mismatch",
        "unresolved": "checkout_overprediction_decomposed_but_not_uniquely_localized",
        "integrity_fail": "m9k_evidence_or_reconstruction_integrity_failed",
        "next_route_up_residual": "m9l_checkout_route_up_failure_cause_discrimination",
        "next_route_state_exposure": "m9l_checkout_exposure_conditioned_route_model_test",
        "next_unresolved": "m9l_checkout_minimal_discriminating_instrumentation",
    }:
        raise CheckoutLocalizationError("M9K decision routing differs")

    workflow = _object(root.get("workflow"), "workflow")
    if dict(workflow) != {
        "jobs": 3,
        "job_timeout_minutes": 360,
        "heavy_analysis_only_in_github_actions": True,
        "artifact_retention_days": 90,
    }:
        raise CheckoutLocalizationError("M9K workflow contract differs")
    guards = _object(root.get("interpretation_guardrails"), "guardrails")
    if any(value is not False for value in guards.values()):
        raise CheckoutLocalizationError("all M9K interpretation guards must be false")

    return CheckoutLocalizationConfig(
        path=config_path,
        raw=root,
        profile="opentelemetry_demo",
        operation="checkout",
        placements=placements,
        failure_laws=laws,
        repetitions=repetitions,
        expected_cells=40,
        tolerance=tolerance,
        alignment_tolerance=alignment,
        transition_guard=transition_guard,
        bootstrap_resamples=resamples,
        bootstrap_seed=seed,
        confidence_level=confidence,
        job_timeout_minutes=360,
    )


def validate_repository(config_path: str | Path) -> Mapping[str, Any]:
    config = load_checkout_localization_config(config_path)
    root = config.path.resolve().parents[1]
    locks: list[dict[str, Any]] = []
    for value in _list(config.raw.get("repository_locks"), "repository locks"):
        record = _object(value, "repository lock")
        relative = _relative(record.get("path"), "repository lock path")
        locks.append(_audit_file(root / relative, record, str(relative)))
    manual = root / _relative(config.raw.get("manual_actions_log"), "manual log")
    if not manual.is_file() or manual.stat().st_size <= 100:
        raise CheckoutLocalizationError("M9K manual-actions log is missing or empty")
    return {
        "schema_version": 1,
        "kind": "m9k_repository_validation",
        "status": "m9k_repository_contract_valid",
        "config_sha256": file_sha256(config.path),
        "repository_locks": locks,
        "expected_cells": config.expected_cells,
        "job_timeout_minutes": config.job_timeout_minutes,
        "pmx_invocations": 0,
        "new_live_collections": 0,
    }


def _audit_metadata(
    config: CheckoutLocalizationConfig,
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


def _audit_locked_files(root: Path, records: Mapping[str, Any], label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, value in records.items():
        record = _object(value, f"{label}.{name}")
        audit = _audit_file(root / _relative(name, f"{label} path"), record, f"{label} {name}")
        rows.append({"role": label, "path": name, **audit})
    return rows


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise CheckoutLocalizationError("cannot average an empty sequence")
    return math.fsum(values) / len(values)


def _m8b_ranking(rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        if row.get("method") != "proposed" or row.get("prediction", "") == "":
            continue
        grouped[(str(row["profile"]), str(row["operation"]))].append(
            _finite(row["prediction_minus_test_stable"], "M8B signed error")
        )
    result = [
        {
            "profile": key[0],
            "operation": key[1],
            "emitted_rows": len(values),
            "mean": _mean(values),
        }
        for key, values in grouped.items()
    ]
    return sorted(result, key=lambda row: (-float(row["mean"]), str(row["profile"]), str(row["operation"])))


def _cohort_m8b_rows(
    config: CheckoutLocalizationConfig,
    rows: Sequence[Mapping[str, str]],
) -> list[Mapping[str, str]]:
    return [
        row
        for row in rows
        if row.get("profile") == config.profile
        and row.get("operation") == config.operation
        and row.get("placement") in config.placements
        and row.get("failure_law") in config.failure_laws
        and int(row.get("repetition", -1)) in config.repetitions
        and row.get("method") == "proposed"
        and row.get("prediction", "") != ""
    ]


def build_contract(
    config_path: str | Path,
    m8a_preserved_metadata: Path,
    m8a_audit_metadata: Path,
    m8b_metadata: Path,
    m9j_metadata: Path,
    m8a_audit_root: Path,
    m8b_root: Path,
    m9j_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_checkout_localization_config(config_path)
    metadata = {
        "m8a_preserved": _audit_metadata(config, "m8a_preserved", m8a_preserved_metadata),
        "m8a_audit": _audit_metadata(config, "m8a_audit", m8a_audit_metadata),
        "m8b": _audit_metadata(config, "m8b", m8b_metadata),
        "m9j_decision": _audit_metadata(config, "m9j_decision", m9j_metadata),
    }
    audits: list[dict[str, Any]] = []
    audits.extend(
        _audit_locked_files(
            m8a_audit_root,
            _object(config.raw["evidence"]["m8a_audit"]["files"], "M8A files"),
            "m8a_audit",
        )
    )
    audits.extend(
        _audit_locked_files(
            m8b_root,
            _object(config.raw["evidence"]["m8b"]["files"], "M8B files"),
            "m8b",
        )
    )
    m9j_record = _object(config.raw["evidence"]["m9j_decision"]["manifest"], "M9J manifest")
    m9j_manifest_path = m9j_root / _relative(m9j_record["path"], "M9J manifest path")
    audits.append(
        {
            "role": "m9j_decision",
            "path": m9j_record["path"],
            **_audit_file(m9j_manifest_path, m9j_record, "M9J decision manifest"),
        }
    )

    m8a_manifest = _object(
        _load_json(m8a_audit_root / "manifest.json", "M8A audit manifest"),
        "M8A audit manifest",
    )
    quality = _object(m8a_manifest.get("quality"), "M8A quality")
    if (
        m8a_manifest.get("source_run_id") != "33990678586"
        or m8a_manifest.get("artifact_counts", {}).get("qualified_cell") != 160
        or m8a_manifest.get("row_counts", {}).get("identities") != 160
        or m8a_manifest.get("row_counts", {}).get("inventoried_files") != 1538
        or any(int(value) != 0 for value in quality.values())
    ):
        raise CheckoutLocalizationError("accepted M8A audit contract differs")
    m8b_manifest = _object(
        _load_json(m8b_root / "manifest.json", "M8B manifest"), "M8B manifest"
    )
    if (
        m8b_manifest.get("diagnostic_only") is not True
        or m8b_manifest.get("changes_m7_predictions_or_scores") is not False
        or m8b_manifest.get("row_counts", {}).get("qualified_cells") != 160
        or m8b_manifest.get("row_counts", {}).get("bias_detail") != 1440
    ):
        raise CheckoutLocalizationError("accepted M8B manifest contract differs")
    m9j_manifest = _object(_load_json(m9j_manifest_path, "M9J decision"), "M9J decision")
    if (
        m9j_manifest.get("status")
        != config.raw["evidence"]["m9j_decision"]["machine_status"]
        or m9j_manifest.get("execution_integrity_passed") is not True
        or m9j_manifest.get("carrier_false_oracle_passed") is not True
        or m9j_manifest.get("carrier_true_oracle_passed") is not False
        or m9j_manifest.get("next_milestone")
        != "m9k_single_operation_overestimation_localization"
    ):
        raise CheckoutLocalizationError("accepted M9J decision contract differs")

    bias_rows = _rows(m8b_root / "bias-detail.csv")
    observed_ranking = _m8b_ranking(bias_rows)
    expected_ranking = [dict(_object(value, "ranking row")) for value in config.raw["target_selection"]["ranking"]]
    if len(observed_ranking) != len(expected_ranking):
        raise CheckoutLocalizationError("M8B operation ranking length differs")
    for observed, expected in zip(observed_ranking, expected_ranking, strict=True):
        if (
            observed["profile"] != expected["profile"]
            or observed["operation"] != expected["operation"]
            or observed["emitted_rows"] != expected["emitted_rows"]
            or not math.isclose(
                float(observed["mean"]),
                float(expected["mean"]),
                rel_tol=0.0,
                abs_tol=config.tolerance,
            )
        ):
            raise CheckoutLocalizationError("accepted M8B operation ranking differs")

    cohort_rows = _cohort_m8b_rows(config, bias_rows)
    if len(cohort_rows) != config.expected_cells:
        raise CheckoutLocalizationError("M8B checkout cohort count differs")
    known = _object(config.raw["cohort"]["m8b_known_summary"], "known summary")
    checks = {
        "mean_prediction": _mean([_finite(row["prediction"], "prediction") for row in cohort_rows]),
        "mean_test_stable_rate": _mean(
            [_finite(row["test_stable_rate"], "test stable rate") for row in cohort_rows]
        ),
        "mean_signed_error": _mean(
            [_finite(row["prediction_minus_test_stable"], "signed error") for row in cohort_rows]
        ),
        "mean_clean_residual": _mean(
            [_finite(row["residual_success_probability"], "clean residual") for row in cohort_rows]
        ),
        "mean_route_prediction": _mean(
            [_finite(row["route_prediction"], "route prediction") for row in cohort_rows]
        ),
    }
    if any(
        not math.isclose(value, float(known[key]), rel_tol=0.0, abs_tol=config.tolerance)
        for key, value in checks.items()
    ):
        raise CheckoutLocalizationError("M8B known checkout summary differs")

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "artifact-file-audit.csv",
        ["role", "path", "bytes", "sha256", "matches"],
        audits,
    )
    _write_csv(
        out / "target-selection.csv",
        ["profile", "operation", "emitted_rows", "mean"],
        observed_ranking,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9k_checkout_localization_contract",
        "status": "checkout_target_and_retained_evidence_verified",
        "config_sha256": file_sha256(config.path),
        "artifact_metadata": metadata,
        "artifact_file_audits": len(audits),
        "target": {"profile": config.profile, "operation": config.operation},
        "selected_cells": config.expected_cells,
        "m8b_known_summary": checks,
        "m9j_machine_status": m9j_manifest["status"],
        "m9j_machine_gate_rewritten": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "changes_m7_predictions_or_scores": False,
        "files": {
            "artifact-file-audit.csv": file_sha256(out / "artifact-file-audit.csv"),
            "target-selection.csv": file_sha256(out / "target-selection.csv"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "contract-manifest.json", manifest)
    return manifest


def _expected_identities(config: CheckoutLocalizationConfig) -> set[tuple[str, str, str, int]]:
    return {
        (config.profile, placement, law, repetition)
        for placement in config.placements
        for law in config.failure_laws
        for repetition in config.repetitions
    }


def _selected_directories(
    config: CheckoutLocalizationConfig, qualified_root: Path
) -> tuple[list[Path], int]:
    manifests = sorted(qualified_root.rglob("learner/manifest.json"))
    selected: list[tuple[tuple[str, str, str, int], Path]] = []
    for path in manifests:
        payload = _object(_load_json(path, "qualified learner manifest"), "learner manifest")
        identity = (
            str(payload.get("profile")),
            str(payload.get("placement")),
            str(payload.get("failure_law")),
            int(payload.get("repetition", -1)),
        )
        if identity in _expected_identities(config):
            selected.append((identity, path.parents[1]))
    identities = [identity for identity, _ in selected]
    if len(manifests) != 160:
        raise CheckoutLocalizationError(
            f"qualified manifest census differs: {len(manifests)}"
        )
    if set(identities) != _expected_identities(config) or len(identities) != len(set(identities)):
        raise CheckoutLocalizationError("selected checkout identity matrix differs")
    return [path for _, path in sorted(selected)], len(manifests)


def _audit_selected_files(
    config: CheckoutLocalizationConfig,
    qualified_root: Path,
    directories: Sequence[Path],
    inventory_path: Path,
) -> list[dict[str, Any]]:
    inventory_rows = _rows(inventory_path)
    inventory: dict[str, Mapping[str, str]] = {}
    for row in inventory_rows:
        if row.get("evidence_group") == "qualified":
            relative = str(row["relative_path"]).replace("\\", "/")
            if relative in inventory:
                raise CheckoutLocalizationError("duplicate M8A inventory path")
            inventory[relative] = row
    result: list[dict[str, Any]] = []
    for directory in directories:
        files = sorted(path for path in directory.rglob("*") if path.is_file())
        if len(files) != int(config.raw["cohort"]["expected_qualified_files_per_cell"]):
            raise CheckoutLocalizationError(f"selected cell file count differs: {directory}")
        for path in files:
            relative = path.relative_to(qualified_root).as_posix()
            expected = inventory.get(relative)
            if expected is None:
                raise CheckoutLocalizationError(f"selected file absent from M8A inventory: {relative}")
            observed_bytes = path.stat().st_size
            observed_hash = file_sha256(path)
            matches = (
                observed_bytes == int(expected["size_in_bytes"])
                and observed_hash == expected["sha256"]
            )
            if not matches:
                raise CheckoutLocalizationError(f"selected M8A file differs: {relative}")
            result.append(
                {
                    "path": relative,
                    "bytes": observed_bytes,
                    "sha256": observed_hash,
                    "matches_m8a_inventory": True,
                }
            )
    if len(result) != int(config.raw["cohort"]["expected_selected_files"]):
        raise CheckoutLocalizationError("selected file audit count differs")
    return result


def _prediction_key(row: Mapping[str, str]) -> tuple[str, str, str, int]:
    return (
        str(row["profile"]),
        str(row["source_placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
    )


def _m8b_key(row: Mapping[str, str]) -> tuple[str, str, str, int]:
    return (
        str(row["profile"]),
        str(row["placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
    )


def _selected_predictions(
    config: CheckoutLocalizationConfig, rows: Sequence[Mapping[str, str]]
) -> dict[tuple[str, str, str, int], Mapping[str, str]]:
    cohort = config.raw["cohort"]
    selected = [
        row
        for row in rows
        if row.get("profile") == config.profile
        and row.get("operation") == config.operation
        and row.get("source_placement") in config.placements
        and row.get("target_placement") == row.get("source_placement")
        and row.get("failure_law") in config.failure_laws
        and int(row.get("repetition", -1)) in config.repetitions
        and row.get("method") == cohort["method"]
        and row.get("mode") == cohort["mode"]
        and row.get("scope") == cohort["scope"]
    ]
    result = {_prediction_key(row): row for row in selected}
    if (
        len(selected) != config.expected_cells
        or len(result) != config.expected_cells
        or set(result) != _expected_identities(config)
        or any(row.get("status") != cohort["prediction_status"] for row in selected)
    ):
        raise CheckoutLocalizationError("frozen checkout prediction matrix differs")
    return result


def _period_metrics(
    operation: str,
    requests: Sequence[Any],
    ticks: Sequence[Any],
    alignment_tolerance: float,
    transition_guard: int,
) -> list[dict[str, Any]]:
    selected_requests = [request for request in requests if request.operation == operation]
    transitions = _transition_times(tuple(ticks))
    aligned: list[tuple[int, int, bool]] = []
    unaligned = 0
    for request in selected_requests:
        index, distance = _nearest_tick(request.at, tuple(ticks))
        if distance > alignment_tolerance:
            unaligned += 1
            continue
        route_up = int(bool(ticks[index].signals[2] or ticks[index].signals[3]))
        stable = not _near_transition(request.at, transitions, transition_guard)
        aligned.append((int(request.success), route_up, stable))
    result: list[dict[str, Any]] = []
    for view in ("all_sequence", "stable"):
        records = aligned if view == "all_sequence" else [row for row in aligned if row[2]]
        attempts = len(records)
        successes = sum(row[0] for row in records)
        up = [row for row in records if row[1] == 1]
        down = [row for row in records if row[1] == 0]
        result.append(
            {
                "view": view,
                "operation_requests": len(selected_requests),
                "aligned_requests": len(aligned),
                "unaligned_requests": unaligned,
                "transition_excluded": len(aligned) - len([row for row in aligned if row[2]]),
                "view_requests": attempts,
                "view_successes": successes,
                "empirical_success_rate": successes / attempts if attempts else math.nan,
                "route_up_requests": len(up),
                "route_up_successes": sum(row[0] for row in up),
                "route_up_fraction": len(up) / attempts if attempts else math.nan,
                "route_up_success_rate": (
                    sum(row[0] for row in up) / len(up) if up else math.nan
                ),
                "route_down_requests": len(down),
                "route_down_successes": sum(row[0] for row in down),
                "route_down_success_rate": (
                    sum(row[0] for row in down) / len(down) if down else math.nan
                ),
            }
        )
    return result


def _decompose(q: float, route_model: float, metrics: Mapping[str, Any]) -> dict[str, float]:
    attempts = int(metrics["view_requests"])
    up_attempts = int(metrics["route_up_requests"])
    if attempts <= 0 or up_attempts <= 0:
        raise CheckoutLocalizationError("decomposition requires route-up stable requests")
    up_successes = int(metrics["route_up_successes"])
    down_successes = int(metrics["route_down_successes"])
    route_observed = up_attempts / attempts
    empirical = (up_successes + down_successes) / attempts
    model_prediction = q * route_model
    state = q * (route_model - route_observed)
    residual = q * route_observed - up_successes / attempts
    down_offset = -down_successes / attempts
    reconstructed = state + residual + down_offset
    return {
        "clean_residual_q": q,
        "model_route_probability": route_model,
        "model_prediction": model_prediction,
        "observed_route_up_fraction": route_observed,
        "observed_success_rate": empirical,
        "model_minus_observed": model_prediction - empirical,
        "route_state_exposure": state,
        "route_up_residual_invariance": residual,
        "route_down_success_offset": down_offset,
        "component_sum": reconstructed,
        "reconstruction_error": reconstructed - (model_prediction - empirical),
    }


def _bootstrap_summary(
    rows: Sequence[Mapping[str, Any]],
    resamples: int,
    seed: int,
    confidence_level: float,
) -> dict[str, dict[str, float]]:
    metrics = (
        "model_minus_observed",
        "route_state_exposure",
        "route_up_residual_invariance",
        "route_down_success_offset",
        "residual_minus_state",
        "state_minus_residual",
    )
    strata: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[(str(row["placement"]), str(row["failure_law"]))].append(row)
    if sorted(len(values) for values in strata.values()) != [10, 10, 10, 10]:
        raise CheckoutLocalizationError("bootstrap strata must each contain ten campaigns")
    generator = np.random.default_rng(seed)
    draws = {metric: np.empty(resamples, dtype=float) for metric in metrics}
    ordered = [strata[key] for key in sorted(strata)]
    for iteration in range(resamples):
        sample: list[Mapping[str, Any]] = []
        for values in ordered:
            indexes = generator.integers(0, len(values), size=len(values))
            sample.extend(values[int(index)] for index in indexes)
        for metric in metrics:
            if metric == "residual_minus_state":
                values = [
                    float(row["route_up_residual_invariance"])
                    - float(row["route_state_exposure"])
                    for row in sample
                ]
            elif metric == "state_minus_residual":
                values = [
                    float(row["route_state_exposure"])
                    - float(row["route_up_residual_invariance"])
                    for row in sample
                ]
            else:
                values = [float(row[metric]) for row in sample]
            draws[metric][iteration] = _mean(values)
    alpha = (1.0 - confidence_level) / 2.0
    result: dict[str, dict[str, float]] = {}
    for metric in metrics:
        if metric == "residual_minus_state":
            observed_values = [
                float(row["route_up_residual_invariance"])
                - float(row["route_state_exposure"])
                for row in rows
            ]
        elif metric == "state_minus_residual":
            observed_values = [
                float(row["route_state_exposure"])
                - float(row["route_up_residual_invariance"])
                for row in rows
            ]
        else:
            observed_values = [float(row[metric]) for row in rows]
        result[metric] = {
            "estimate": _mean(observed_values),
            "lower": float(np.quantile(draws[metric], alpha)),
            "upper": float(np.quantile(draws[metric], 1.0 - alpha)),
        }
    return result


def _classify_localization(
    test_rows: Sequence[Mapping[str, Any]],
    calibration_rows: Sequence[Mapping[str, Any]],
    test_bootstrap: Mapping[str, Mapping[str, float]],
    calibration_bootstrap: Mapping[str, Mapping[str, float]],
    minimum_positive_cells: int,
) -> Mapping[str, Any]:
    residual_positive = sum(
        float(row["route_up_residual_invariance"]) > 0 for row in test_rows
    )
    state_positive = sum(float(row["route_state_exposure"]) > 0 for row in test_rows)
    calibration_residual_positive = sum(
        float(row["route_up_residual_invariance"]) > 0 for row in calibration_rows
    )
    residual_dominant = (
        test_bootstrap["residual_minus_state"]["lower"] > 0
        and test_bootstrap["route_up_residual_invariance"]["lower"] > 0
        and residual_positive >= minimum_positive_cells
        and calibration_bootstrap["route_up_residual_invariance"]["lower"] > 0
        and calibration_residual_positive >= minimum_positive_cells
    )
    state_dominant = (
        test_bootstrap["state_minus_residual"]["lower"] > 0
        and test_bootstrap["route_state_exposure"]["lower"] > 0
        and state_positive >= minimum_positive_cells
    )
    if residual_dominant and state_dominant:
        raise CheckoutLocalizationError("mutually exclusive dominance rules both passed")
    classification = (
        "route_up_residual"
        if residual_dominant
        else "route_state_exposure"
        if state_dominant
        else "unresolved"
    )
    return {
        "classification": classification,
        "route_up_residual_dominant": residual_dominant,
        "route_state_exposure_dominant": state_dominant,
        "test_residual_positive_cells": residual_positive,
        "test_state_positive_cells": state_positive,
        "calibration_residual_positive_cells": calibration_residual_positive,
        "calibration_corroborated": (
            calibration_bootstrap["route_up_residual_invariance"]["lower"] > 0
            and calibration_residual_positive >= minimum_positive_cells
        ),
    }


def run_localization(
    config_path: str | Path,
    contract_manifest_path: Path,
    qualified_root: Path,
    analysis_root: Path,
    m8a_audit_root: Path,
    m8b_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutLocalizationError("full M9K localization may run only in GitHub Actions")
    config = load_checkout_localization_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9K contract"), "contract")
    if (
        contract.get("status") != "checkout_target_and_retained_evidence_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or contract.get("selected_cells") != config.expected_cells
    ):
        raise CheckoutLocalizationError("M9K contract manifest differs")

    evidence = config.raw["evidence"]
    _audit_locked_files(
        m8a_audit_root,
        _object(evidence["m8a_audit"]["files"], "M8A files"),
        "m8a_audit",
    )
    _audit_locked_files(
        m8b_root,
        _object(evidence["m8b"]["files"], "M8B files"),
        "m8b",
    )
    for name, value in _object(evidence["frozen_analysis"], "frozen analysis").items():
        expected = _object(value, f"frozen analysis {name}")
        path = analysis_root / _relative(name, "analysis path")
        if not path.is_file() or file_sha256(path) != expected["sha256"]:
            raise CheckoutLocalizationError(f"frozen analysis file differs: {name}")

    directories, census = _selected_directories(config, qualified_root)
    file_rows = _audit_selected_files(
        config,
        qualified_root,
        directories,
        m8a_audit_root / "file-inventory.csv",
    )
    predictions = _selected_predictions(config, _rows(analysis_root / "predictions.csv"))
    m8b_rows = {
        _m8b_key(row): row
        for row in _cohort_m8b_rows(config, _rows(m8b_root / "bias-detail.csv"))
    }
    if set(m8b_rows) != _expected_identities(config):
        raise CheckoutLocalizationError("M8B selected-row identities differ")

    m7_config_path = config.path.resolve().parents[1] / "configs" / "m7_frozen_live.yaml"
    frozen_config = load_frozen_live_validation_config(m7_config_path)
    analysis = frozen_config.analysis
    if (
        analysis.health_alignment_tolerance_seconds != config.alignment_tolerance
        or analysis.transition_guard_seconds_each_side != config.transition_guard
        or analysis.primary_mode != config.raw["cohort"]["mode"]
        or analysis.primary_view != config.raw["cohort"]["view"]
    ):
        raise CheckoutLocalizationError("current frozen M7 analysis constants differ")

    period_rows: list[dict[str, Any]] = []
    decomposition_rows: list[dict[str, Any]] = []
    m8b_mismatches = 0
    baseline_mismatches = 0
    for directory in directories:
        cell = load_qualified_cell(directory)
        key = cell.identity
        prediction = predictions[key]
        m8b = m8b_rows[key]
        baseline = [
            row.success
            for row in cell.learner_requests
            if row.period == "baseline" and row.operation == config.operation
        ]
        if not baseline:
            raise CheckoutLocalizationError(f"checkout baseline missing: {key}")
        q_recomputed = (
            sum(baseline) + analysis.baseline_beta_prior_alpha
        ) / (
            len(baseline)
            + analysis.baseline_beta_prior_alpha
            + analysis.baseline_beta_prior_beta
        )
        q = _finite(prediction["residual_success_probability"], "frozen q")
        route_model = _finite(prediction["route_prediction"], "frozen route")
        model_prediction = _finite(prediction["prediction"], "frozen prediction")
        baseline_mismatches += int(
            not math.isclose(q, q_recomputed, rel_tol=0.0, abs_tol=config.tolerance)
        )
        if not math.isclose(q * route_model, model_prediction, rel_tol=0.0, abs_tol=config.tolerance):
            raise CheckoutLocalizationError(f"frozen prediction product differs: {key}")

        period_inputs = {
            "calibration": (
                [row for row in cell.learner_requests if row.period == "calibration"],
                cell.health,
            ),
            "test": (cell.test_requests, cell.test_health),
        }
        stable_by_period: dict[str, Mapping[str, Any]] = {}
        for period, (requests, ticks) in period_inputs.items():
            metrics_rows = _period_metrics(
                config.operation,
                requests,
                ticks,
                config.alignment_tolerance,
                config.transition_guard,
            )
            for metrics in metrics_rows:
                row = {
                    "profile": key[0],
                    "placement": key[1],
                    "failure_law": key[2],
                    "repetition": key[3],
                    "period": period,
                    **metrics,
                }
                period_rows.append(row)
                if metrics["view"] == "stable":
                    stable_by_period[period] = row

        test_stable = stable_by_period["test"]
        calibration_all = next(
            row
            for row in period_rows
            if row["profile"] == key[0]
            and row["placement"] == key[1]
            and row["failure_law"] == key[2]
            and row["repetition"] == key[3]
            and row["period"] == "calibration"
            and row["view"] == "all_sequence"
        )
        comparisons = (
            (model_prediction, _finite(m8b["prediction"], "M8B prediction")),
            (q, _finite(m8b["residual_success_probability"], "M8B q")),
            (route_model, _finite(m8b["route_prediction"], "M8B route")),
            (
                float(test_stable["view_requests"]),
                _finite(m8b["test_stable_requests"], "M8B stable requests"),
            ),
            (
                float(test_stable["empirical_success_rate"]),
                _finite(m8b["test_stable_rate"], "M8B stable rate"),
            ),
            (float(len(baseline)), _finite(m8b["baseline_requests"], "M8B baseline n")),
            (
                sum(baseline) / len(baseline),
                _finite(m8b["baseline_rate"], "M8B baseline rate"),
            ),
            (
                float(calibration_all["operation_requests"]),
                _finite(m8b["calibration_requests"], "M8B calibration n"),
            ),
            (
                sum(
                    row.success
                    for row in cell.learner_requests
                    if row.period == "calibration" and row.operation == config.operation
                )
                / int(calibration_all["operation_requests"]),
                _finite(m8b["calibration_rate"], "M8B calibration rate"),
            ),
        )
        m8b_mismatches += sum(
            not math.isclose(left, right, rel_tol=0.0, abs_tol=config.tolerance)
            for left, right in comparisons
        )

        for period in ("calibration", "test"):
            metrics = stable_by_period[period]
            decomposition_rows.append(
                {
                    "profile": key[0],
                    "placement": key[1],
                    "failure_law": key[2],
                    "repetition": key[3],
                    "period": period,
                    "stable_requests": metrics["view_requests"],
                    "route_up_requests": metrics["route_up_requests"],
                    "route_down_requests": metrics["route_down_requests"],
                    "route_up_success_rate": metrics["route_up_success_rate"],
                    "route_down_success_rate": metrics["route_down_success_rate"],
                    **_decompose(q, route_model, metrics),
                }
            )

    minimum_stable = int(config.raw["localization"]["minimum_stable_requests_per_cell_period"])
    minimum_alignment = float(config.raw["localization"]["minimum_alignment_fraction"])
    alignment_fractions = [
        int(row["aligned_requests"]) / int(row["operation_requests"])
        for row in period_rows
        if row["view"] == "all_sequence"
    ]
    max_reconstruction = max(abs(float(row["reconstruction_error"])) for row in decomposition_rows)
    test_rows = [row for row in decomposition_rows if row["period"] == "test"]
    calibration_rows = [row for row in decomposition_rows if row["period"] == "calibration"]
    test_bootstrap = _bootstrap_summary(
        test_rows,
        config.bootstrap_resamples,
        config.bootstrap_seed,
        config.confidence_level,
    )
    calibration_bootstrap = _bootstrap_summary(
        calibration_rows,
        config.bootstrap_resamples,
        config.bootstrap_seed + 1,
        config.confidence_level,
    )
    dominance = _classify_localization(
        test_rows,
        calibration_rows,
        test_bootstrap,
        calibration_bootstrap,
        int(config.raw["localization"]["minimum_positive_cells_for_dominance"]),
    )
    known_gap_pass = test_bootstrap["model_minus_observed"]["estimate"] >= float(
        config.raw["localization"]["minimum_known_mean_gap"]
    )
    quality = {
        "qualified_manifest_census": census,
        "selected_cells": len(directories),
        "selected_files_audited": len(file_rows),
        "selected_file_mismatches": 0,
        "baseline_q_mismatches": baseline_mismatches,
        "m8b_reproduction_mismatches": m8b_mismatches,
        "minimum_alignment_fraction": min(alignment_fractions),
        "minimum_stable_requests": min(
            int(row["view_requests"])
            for row in period_rows
            if row["view"] == "stable"
        ),
        "maximum_decomposition_reconstruction_error": max_reconstruction,
        "known_mean_gap_gate_passed": known_gap_pass,
    }
    integrity_pass = (
        census == 160
        and len(directories) == config.expected_cells
        and len(file_rows) == int(config.raw["cohort"]["expected_selected_files"])
        and baseline_mismatches == 0
        and m8b_mismatches == 0
        and min(alignment_fractions) >= minimum_alignment
        and quality["minimum_stable_requests"] >= minimum_stable
        and max_reconstruction <= config.tolerance
        and known_gap_pass
    )
    rules = _object(config.raw["decision"], "decision")
    status = (
        str(rules[str(dominance["classification"])])
        if integrity_pass
        else str(rules["integrity_fail"])
    )

    out.mkdir(parents=True, exist_ok=True)
    period_fields = [
        "profile",
        "placement",
        "failure_law",
        "repetition",
        "period",
        "view",
        "operation_requests",
        "aligned_requests",
        "unaligned_requests",
        "transition_excluded",
        "view_requests",
        "view_successes",
        "empirical_success_rate",
        "route_up_requests",
        "route_up_successes",
        "route_up_fraction",
        "route_up_success_rate",
        "route_down_requests",
        "route_down_successes",
        "route_down_success_rate",
    ]
    decomposition_fields = [
        "profile",
        "placement",
        "failure_law",
        "repetition",
        "period",
        "stable_requests",
        "route_up_requests",
        "route_down_requests",
        "route_up_success_rate",
        "route_down_success_rate",
        "clean_residual_q",
        "model_route_probability",
        "model_prediction",
        "observed_route_up_fraction",
        "observed_success_rate",
        "model_minus_observed",
        "route_state_exposure",
        "route_up_residual_invariance",
        "route_down_success_offset",
        "component_sum",
        "reconstruction_error",
    ]
    _write_csv(out / "period-state.csv", period_fields, period_rows)
    _write_csv(out / "cell-decomposition.csv", decomposition_fields, decomposition_rows)
    _write_csv(
        out / "selected-file-audit.csv",
        ["path", "bytes", "sha256", "matches_m8a_inventory"],
        file_rows,
    )
    bootstrap_rows = []
    for period, summaries in (
        ("calibration", calibration_bootstrap),
        ("test", test_bootstrap),
    ):
        for metric, values in summaries.items():
            bootstrap_rows.append({"period": period, "metric": metric, **values})
    _write_csv(
        out / "bootstrap-summary.csv",
        ["period", "metric", "estimate", "lower", "upper"],
        bootstrap_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9k_checkout_overprediction_localization",
        "status": status,
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "integrity_passed": integrity_pass,
        "quality": quality,
        "target": {"profile": config.profile, "operation": config.operation},
        "cell_count": len(directories),
        "period_state_rows": len(period_rows),
        "decomposition_rows": len(decomposition_rows),
        "test_bootstrap": test_bootstrap,
        "calibration_bootstrap": calibration_bootstrap,
        "dominance": dominance,
        "counterfactuals_are_revised_predictions": False,
        "changes_m7_predictions_or_scores": False,
        "posthoc_localization_is_confirmatory_accuracy_evidence": False,
        "single_operation_generalization_authorized": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "files": {
            "period-state.csv": file_sha256(out / "period-state.csv"),
            "cell-decomposition.csv": file_sha256(out / "cell-decomposition.csv"),
            "selected-file-audit.csv": file_sha256(out / "selected-file-audit.csv"),
            "bootstrap-summary.csv": file_sha256(out / "bootstrap-summary.csv"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "localization-manifest.json", manifest)
    return manifest


def decide(
    config_path: str | Path,
    contract_manifest_path: Path,
    localization_manifest_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_checkout_localization_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9K contract"), "contract")
    localization = _object(
        _load_json(localization_manifest_path, "M9K localization"), "localization"
    )
    config_hash = file_sha256(config.path)
    contract_pass = (
        contract.get("config_sha256") == config_hash
        and contract.get("status") == "checkout_target_and_retained_evidence_verified"
        and contract.get("selected_cells") == config.expected_cells
        and contract.get("pmx_invocations") == 0
        and contract.get("new_live_collections") == 0
    )
    localization_pass = (
        localization.get("config_sha256") == config_hash
        and localization.get("contract_manifest_sha256")
        == file_sha256(contract_manifest_path)
        and localization.get("integrity_passed") is True
        and localization.get("cell_count") == config.expected_cells
        and localization.get("decomposition_rows") == 80
        and localization.get("pmx_invocations") == 0
        and localization.get("new_live_collections") == 0
    )
    dominance = _object(localization.get("dominance"), "dominance")
    classification = str(dominance.get("classification", "unresolved"))
    rules = _object(config.raw["decision"], "decision")
    expected_status = str(rules.get(classification, rules["integrity_fail"]))
    status_matches = localization.get("status") == expected_status
    if not contract_pass or not localization_pass or not status_matches:
        status = str(rules["integrity_fail"])
        next_experiment = str(rules["next_unresolved"])
        accepted = False
    else:
        status = expected_status
        next_experiment = str(rules[f"next_{classification}"])
        accepted = True

    rows = [
        {
            "question": "retained_evidence_and_target_contract_passed",
            "value": contract_pass,
            "interpretation": "accepted M8A/M8B/M9J identities and pre-M9K checkout selection",
        },
        {
            "question": "forty_cell_reconstruction_integrity_passed",
            "value": localization_pass,
            "interpretation": "all selected files and exact decomposition identity",
        },
        {
            "question": "route_up_residual_dominant",
            "value": dominance.get("route_up_residual_dominant") is True,
            "interpretation": "clean residual versus fault-period route-up boundary",
        },
        {
            "question": "route_state_exposure_dominant",
            "value": dominance.get("route_state_exposure_dominant") is True,
            "interpretation": "stationary route probability versus request exposure",
        },
        {
            "question": "calibration_corroborated",
            "value": dominance.get("calibration_corroborated") is True,
            "interpretation": "distinction already present in learner calibration evidence",
        },
        {
            "question": "m7_or_article_verdict_changed",
            "value": False,
            "interpretation": "post-result single-operation diagnostic only",
        },
    ]
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "decision-matrix.csv",
        ["question", "value", "interpretation"],
        rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9k_checkout_localization_decision",
        "status": status,
        "config_sha256": config_hash,
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "localization_manifest_sha256": file_sha256(localization_manifest_path),
        "technical_evidence_accepted": accepted,
        "contract_passed": contract_pass,
        "localization_integrity_passed": localization_pass,
        "classification": classification,
        "dominance": dict(dominance),
        "next_experiment": next_experiment,
        "m9j_machine_gate_rewritten": False,
        "additional_pmx_repair_authorized": False,
        "changes_m7_predictions_or_scores": False,
        "new_live_collection_authorized": False,
        "single_operation_generalization_authorized": False,
        "physical_root_cause_claimed": False,
        "better_predictive_accuracy_demonstrated": False,
        "lower_end_to_end_automation_cost_than_pmx_demonstrated": False,
        "overall_article_verdict_changed": False,
        "files": {"decision-matrix.csv": file_sha256(out / "decision-matrix.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M9K checkout overprediction localization")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--config", type=Path, required=True)
    contract = subparsers.add_parser("build-contract")
    contract.add_argument("--config", type=Path, required=True)
    contract.add_argument("--m8a-preserved-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-metadata", type=Path, required=True)
    contract.add_argument("--m8b-metadata", type=Path, required=True)
    contract.add_argument("--m9j-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-root", type=Path, required=True)
    contract.add_argument("--m8b-root", type=Path, required=True)
    contract.add_argument("--m9j-root", type=Path, required=True)
    contract.add_argument("--out", type=Path, required=True)
    localize = subparsers.add_parser("localize")
    localize.add_argument("--config", type=Path, required=True)
    localize.add_argument("--contract-manifest", type=Path, required=True)
    localize.add_argument("--qualified-root", type=Path, required=True)
    localize.add_argument("--analysis-root", type=Path, required=True)
    localize.add_argument("--m8a-audit-root", type=Path, required=True)
    localize.add_argument("--m8b-root", type=Path, required=True)
    localize.add_argument("--out", type=Path, required=True)
    decision = subparsers.add_parser("decide")
    decision.add_argument("--config", type=Path, required=True)
    decision.add_argument("--contract-manifest", type=Path, required=True)
    decision.add_argument("--localization-manifest", type=Path, required=True)
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
            args.m8b_metadata,
            args.m9j_metadata,
            args.m8a_audit_root,
            args.m8b_root,
            args.m9j_root,
            args.out,
        )
    elif args.command == "localize":
        payload = run_localization(
            args.config,
            args.contract_manifest,
            args.qualified_root,
            args.analysis_root,
            args.m8a_audit_root,
            args.m8b_root,
            args.out,
        )
    else:
        payload = decide(
            args.config,
            args.contract_manifest,
            args.localization_manifest,
            args.out,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
