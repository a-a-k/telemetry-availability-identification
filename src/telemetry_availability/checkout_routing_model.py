from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from .checkout_localization import _audit_selected_files, _period_metrics
from .live_validation_analysis import (
    QualifiedCell,
    RequestRecord,
    _bool,
    _health_ticks,
    _latent_template,
    _parameter_names,
    _stable_uniform,
    _state_probabilities,
    _target_operations,
    _timestamp,
    fit_exact_model,
    load_qualified_cell,
    predict_cell,
    prepare_mode,
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


class CheckoutRoutingModelError(ValueError):
    pass


ROUTE_MODELS = (
    "m7_single_demand_or",
    "source_strict_round_robin_and",
    "source_three_call_independent",
    "source_two_client_affinity",
    "learner_trace_requirement_mixture",
)
REFERENCE_MODEL = "m7_b2_marginal_reference"
ALL_METHODS = (*ROUTE_MODELS, REFERENCE_MODEL)
PRIMARY_MODEL = "learner_trace_requirement_mixture"
LEARNER_FILES = (
    "audit/boundary.json",
    "learner/deployment.json",
    "learner/health.csv",
    "learner/manifest.json",
    "learner/requests.csv",
    "learner/topology-edges.csv",
)


@dataclass(frozen=True)
class CheckoutRoutingModelConfig:
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
    minimum_footprints: int
    minimum_resolution: float
    minimum_both: float
    fit_range_tolerance: float
    probability_tolerance: float
    closure_margin: float
    minimum_bracketed: int
    resamples: int
    seed: int
    confidence_level: float
    job_timeout_minutes: int


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise CheckoutRoutingModelError(f"required CSV is missing: {path}")
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _finite(value: object, label: str) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise CheckoutRoutingModelError(f"{label} must be numeric") from error
    if not math.isfinite(result):
        raise CheckoutRoutingModelError(f"{label} must be finite")
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
        raise CheckoutRoutingModelError(f"M9M {role} anchor differs")
    _string(record.get("artifact_name"), f"{role}.artifact_name")
    _positive(record.get("size_in_bytes"), f"{role}.size")
    _sha256(record.get("sha256"), f"{role}.sha256")
    _string(record.get("expires_at"), f"{role}.expires_at")
    return record


def _validate_file_locks(record: Mapping[str, Any], role: str) -> None:
    files = _object(record.get("files"), f"{role}.files")
    if not files:
        raise CheckoutRoutingModelError(f"M9M {role} file locks are empty")
    for name, value in files.items():
        _relative(name, f"{role} file")
        item = _object(value, f"{role}.{name}")
        _positive(item.get("bytes"), f"{role}.{name}.bytes")
        _sha256(item.get("sha256"), f"{role}.{name}.sha256")


def load_checkout_routing_model_config(
    path: str | Path,
) -> CheckoutRoutingModelConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9M config"), "root")
    expected = {
        "schema_version": 1,
        "id": "m9m_checkout_request_level_routing_model_test",
        "status": "frozen_before_first_m9m_remote_candidate_generation_or_evaluator_access",
        "diagnostic_only": True,
        "posthoc_to_m7_and_m9l": True,
        "changes_m7_predictions_or_scores": False,
        "new_live_collection": "forbidden",
        "pmx_invocation": "forbidden",
    }
    for key, value in expected.items():
        if root.get(key) != value:
            raise CheckoutRoutingModelError(f"M9M {key} differs from frozen value")

    article = _object(root.get("article_position"), "article position")
    if dict(article) != {
        "direction_remains_substantive": True,
        "claimed_advantage_demonstrated": False,
        "specified_model_calculation_supported": True,
        "better_predictive_accuracy_demonstrated": False,
        "lower_end_to_end_automation_cost_than_pmx_demonstrated": False,
        "overall_success_or_failure_decided": False,
    }:
        raise CheckoutRoutingModelError("M9M article-position guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    if (
        evidence.get("m7_source_run_id") != 33990678586
        or _commit(evidence.get("m7_source_commit"), "M7 source commit")
        != "b1925736f314da610debd23a586d7b7d00cae7ca"
    ):
        raise CheckoutRoutingModelError("M9M M7 source anchor differs")
    anchors = {
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
        "m9l_contract": (
            34085244404,
            "3dbf8b104faae562b789f5c86966b359f8bd08f2",
            10004980006,
        ),
        "m9l_discrimination": (
            34085244404,
            "3dbf8b104faae562b789f5c86966b359f8bd08f2",
            10005005030,
        ),
        "m9l_decision": (
            34085244404,
            "3dbf8b104faae562b789f5c86966b359f8bd08f2",
            10005011688,
        ),
    }
    artifact_records: dict[str, Mapping[str, Any]] = {}
    for role, anchor in anchors.items():
        artifact_records[role] = _validate_artifact_record(
            evidence, role, *anchor
        )
    for role in ("m8a_audit", "m9l_contract", "m9l_discrimination", "m9l_decision"):
        _validate_file_locks(artifact_records[role], role)
    decision_anchor = artifact_records["m9l_decision"]
    if (
        decision_anchor.get("machine_status")
        != "checkout_residual_localized_to_observed_replica_path_loss"
        or decision_anchor.get("classification") != "observed_replica_path_loss"
        or decision_anchor.get("next_experiment")
        != "m9m_checkout_request_level_routing_model_test"
    ):
        raise CheckoutRoutingModelError("M9L selected branch differs")
    frozen = _object(evidence.get("frozen_analysis"), "frozen analysis")
    if set(frozen) != {"predictions.csv"}:
        raise CheckoutRoutingModelError("M9M frozen analysis inventory differs")
    _validate_file_locks({"files": frozen}, "frozen_analysis")

    source = _object(root.get("source_contract"), "source contract")
    if (
        source.get("logical_request")
        != "frozen_driver_checkout_with_one_new_cart_item"
        or source.get("successful_request_target_call_sites") != 3
        or source.get("call_sites")
        != [
            "driver_product_prerequisite_before_cart_add",
            "checkout_service_product_lookup_for_the_single_cart_item",
            "frontend_product_lookup_when_rendering_the_successful_order_response",
        ]
        or source.get("routing_policy")
        != "haproxy_roundrobin_with_500ms_fall1_rise1_health_checks"
        or source.get("literal_per_call_assignment_observed") is not False
    ):
        raise CheckoutRoutingModelError("M9M source call contract differs")
    local_files = _list(source.get("local_files"), "local source files")
    if len(local_files) != 2:
        raise CheckoutRoutingModelError("M9M requires two local source files")
    for value in local_files:
        item = _object(value, "local source file")
        _relative(item.get("path"), "local source path")
        _positive(item.get("bytes"), "local source bytes")
        _sha256(item.get("sha256"), "local source SHA-256")
        markers = _list(item.get("markers"), "local source markers")
        if not markers or not all(isinstance(marker, str) and marker for marker in markers):
            raise CheckoutRoutingModelError("M9M local source markers differ")
    upstream = _object(source.get("upstream"), "upstream source")
    if (
        upstream.get("repository")
        != "https://github.com/open-telemetry/opentelemetry-demo.git"
        or _commit(upstream.get("commit"), "upstream commit")
        != "8c47d47c9ac27710d2b2a153bcd53e483bffe66d"
    ):
        raise CheckoutRoutingModelError("M9M upstream anchor differs")
    upstream_files = _list(upstream.get("files"), "upstream files")
    if len(upstream_files) != 3:
        raise CheckoutRoutingModelError("M9M requires three upstream sources")
    for value in upstream_files:
        item = _object(value, "upstream file")
        _relative(item.get("path"), "upstream path")
        _positive(item.get("bytes"), "upstream bytes")
        _commit(item.get("git_blob"), "upstream Git blob")
        _sha256(item.get("sha256"), "upstream SHA-256")
        markers = _list(item.get("markers"), "upstream markers")
        if not markers or not all(isinstance(marker, str) and marker for marker in markers):
            raise CheckoutRoutingModelError("M9M upstream markers differ")

    cohort = _object(root.get("cohort"), "cohort")
    placements = tuple(str(value) for value in _list(cohort.get("placements"), "placements"))
    laws = tuple(str(value) for value in _list(cohort.get("failure_laws"), "laws"))
    repetitions = tuple(int(value) for value in _list(cohort.get("repetitions"), "repetitions"))
    alignment = _finite(cohort.get("alignment_tolerance_seconds"), "alignment")
    transition_guard = _positive(
        cohort.get("transition_guard_seconds_each_side"), "transition guard"
    )
    minimum_stable = _positive(
        cohort.get("minimum_stable_test_requests_per_cell"), "minimum stable test"
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
        or cohort.get("mode") != "sampled_mixed"
        or cohort.get("scope") != "current"
        or cohort.get("view") != "stable"
        or alignment != 1.25
        or transition_guard != 1
        or minimum_stable != 500
    ):
        raise CheckoutRoutingModelError("M9M cohort differs")

    boundary = _object(root.get("learner_information_boundary"), "information boundary")
    minimum_footprints = _positive(
        boundary.get("minimum_retained_baseline_checkout_traces_per_cell"),
        "minimum footprints",
    )
    minimum_resolution = _finite(
        boundary.get("minimum_resolved_footprint_fraction_per_cell"),
        "minimum footprint resolution",
    )
    minimum_both = _finite(
        boundary.get("minimum_both_replica_footprint_fraction_per_cell"),
        "minimum both footprint",
    )
    if (
        boundary.get("candidate_job_input")
        != "selected_learner_and_boundary_files_only"
        or boundary.get("evaluator_files_parsed_or_copied") is not False
        or boundary.get("test_outcomes_accessed") is not False
        or boundary.get("footprint_period") != "baseline"
        or boundary.get("footprint_outcomes_read") is not False
        or boundary.get("trace_sampling_mode") != "sampled_mixed"
        or boundary.get("trace_sampling_probability") != 0.7
        or boundary.get("valid_footprints") != ["a", "b", "a;b"]
        or minimum_footprints != 20
        or minimum_resolution != 0.95
        or minimum_both != 0.90
        or boundary.get("additional_input_cost_must_be_reported") is not True
    ):
        raise CheckoutRoutingModelError("M9M information boundary differs")

    models = _object(root.get("models"), "models")
    formulas = _object(models.get("route_state_formulas"), "route formulas")
    expected_formulas = {
        "m7_single_demand_or": "max(pa,pb)",
        "source_strict_round_robin_and": "pa*pb",
        "source_three_call_independent": "((pa+pb)/2)^3",
        "source_two_client_affinity": "((pa+pb)/2)^2",
        "learner_trace_requirement_mixture": "w_a*pa+w_b*pb+w_ab*pa*pb",
        "m7_b2_marginal_reference": "frozen_M7_B2_prediction",
    }
    fit_range = _finite(
        models.get("maximum_equivalent_multistart_prediction_range"),
        "fit range tolerance",
    )
    probability_tolerance = _finite(
        models.get("probability_tolerance"), "probability tolerance"
    )
    if (
        models.get("primary") != PRIMARY_MODEL
        or tuple(models.get("candidate_order", [])) != ALL_METHODS
        or dict(formulas) != expected_formulas
        or models.get("noncheckout_target_operation_route") != "max(pa,pb)"
        or models.get("candidate_specific_refit") is not True
        or models.get("m7_or_must_reproduce_frozen_prediction") is not True
        or models.get("candidate_selection_after_test") is not False
        or models.get("sensitivity_candidates_are_not_promoted_by_best_test_score")
        is not True
        or fit_range != 0.0001
        or probability_tolerance != 1e-10
    ):
        raise CheckoutRoutingModelError("M9M model contract differs")

    evaluation = _object(root.get("evaluation"), "evaluation")
    bootstrap = _object(evaluation.get("bootstrap"), "bootstrap")
    closure = _finite(
        evaluation.get("closure_margin_absolute_probability"), "closure margin"
    )
    minimum_bracketed = _positive(
        evaluation.get("minimum_cells_bracketed_by_strict_and_and_or"),
        "minimum bracketed",
    )
    resamples = _positive(bootstrap.get("resamples"), "bootstrap resamples")
    seed = _positive(bootstrap.get("seed"), "bootstrap seed")
    confidence = _finite(bootstrap.get("confidence_level"), "confidence level")
    if (
        evaluation.get("primary_metric") != "bernoulli_brier_score"
        or evaluation.get("secondary_metrics")
        != ["signed_prediction_error", "absolute_prediction_error"]
        or closure != 0.03
        or minimum_bracketed != 32
        or bootstrap.get("unit")
        != "campaign_within_placement_by_failure_law_stratum"
        or resamples != 10000
        or seed != 20260908
        or confidence != 0.95
        or evaluation.get("intermediate_closure_is_mechanism_bracketing_not_model_selection")
        is not True
    ):
        raise CheckoutRoutingModelError("M9M evaluation contract differs")

    decision = _object(root.get("decision"), "decision")
    if set(decision) != {
        "primary_supported",
        "bracketed_routing_law_unresolved",
        "primary_overshoots",
        "gap_persists",
        "inconclusive",
        "integrity_fail",
        "next_primary_supported",
        "next_bracketed_routing_law_unresolved",
        "next_primary_overshoots",
        "next_gap_persists",
        "next_inconclusive",
    }:
        raise CheckoutRoutingModelError("M9M decision branches differ")
    workflow = _object(root.get("workflow"), "workflow")
    if dict(workflow) != {
        "jobs": 3,
        "job_timeout_minutes": 360,
        "heavy_analysis_only_in_github_actions": True,
        "artifact_retention_days": 90,
    }:
        raise CheckoutRoutingModelError("M9M workflow contract differs")
    guards = _object(root.get("interpretation_guardrails"), "guardrails")
    if len(guards) != 9 or any(value is not False for value in guards.values()):
        raise CheckoutRoutingModelError("all M9M interpretation guards must be false")

    return CheckoutRoutingModelConfig(
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
        minimum_stable_test=minimum_stable,
        minimum_footprints=minimum_footprints,
        minimum_resolution=minimum_resolution,
        minimum_both=minimum_both,
        fit_range_tolerance=fit_range,
        probability_tolerance=probability_tolerance,
        closure_margin=closure,
        minimum_bracketed=minimum_bracketed,
        resamples=resamples,
        seed=seed,
        confidence_level=confidence,
        job_timeout_minutes=360,
    )


def validate_repository(config_path: str | Path) -> Mapping[str, Any]:
    config = load_checkout_routing_model_config(config_path)
    root = config.path.resolve().parents[1]
    locks = []
    for value in _list(config.raw.get("repository_locks"), "repository locks"):
        record = _object(value, "repository lock")
        relative = _relative(record.get("path"), "repository lock path")
        locks.append(_audit_file(root / relative, record, str(relative)))
    manual = root / _relative(config.raw.get("manual_actions_log"), "manual log")
    if not manual.is_file() or manual.stat().st_size <= 100:
        raise CheckoutRoutingModelError("M9M manual-actions log is missing or empty")
    return {
        "schema_version": 1,
        "kind": "m9m_repository_validation",
        "status": "m9m_repository_contract_valid",
        "config_sha256": file_sha256(config.path),
        "repository_locks": locks,
        "expected_cells": config.expected_cells,
        "models": list(ALL_METHODS),
        "job_timeout_minutes": config.job_timeout_minutes,
        "pmx_invocations": 0,
        "new_live_collections": 0,
    }


def _audit_metadata(
    config: CheckoutRoutingModelConfig, role: str, metadata_path: Path
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


def _git(checkout: Path, *arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(checkout), *arguments], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise CheckoutRoutingModelError("cannot audit upstream Git checkout") from error


def _audit_upstream_sources(
    config: CheckoutRoutingModelConfig, upstream_root: Path
) -> list[dict[str, Any]]:
    upstream = _object(config.raw["source_contract"]["upstream"], "upstream")
    expected_head = str(upstream["commit"])
    if _git(upstream_root, "rev-parse", "HEAD") != expected_head:
        raise CheckoutRoutingModelError("upstream checkout commit differs")
    rows: list[dict[str, Any]] = []
    for value in _list(upstream["files"], "upstream files"):
        record = _object(value, "upstream file")
        relative = _relative(record["path"], "upstream path")
        path = upstream_root / relative
        audit = _audit_file(path, record, f"upstream {relative.as_posix()}")
        blob = _git(upstream_root, "rev-parse", f"HEAD:{relative.as_posix()}")
        if blob != record["git_blob"]:
            raise CheckoutRoutingModelError(f"upstream Git blob differs: {relative}")
        text = path.read_text(encoding="utf-8")
        markers = [str(marker) for marker in record["markers"]]
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise CheckoutRoutingModelError(f"upstream markers missing: {relative}")
        rows.append(
            {
                "path": relative.as_posix(),
                "bytes": audit["bytes"],
                "sha256": audit["sha256"],
                "git_blob": blob,
                "marker_count": len(markers),
                "matches": True,
            }
        )
    return rows


def _audit_local_sources(config: CheckoutRoutingModelConfig) -> list[dict[str, Any]]:
    repository = config.path.resolve().parents[1]
    source = _object(config.raw["source_contract"], "source contract")
    rows: list[dict[str, Any]] = []
    for value in _list(source["local_files"], "local source files"):
        record = _object(value, "local source file")
        relative = _relative(record["path"], "local source path")
        path = repository / relative
        audit = _audit_file(path, record, f"local source {relative.as_posix()}")
        text = path.read_text(encoding="utf-8")
        markers = [str(marker) for marker in record["markers"]]
        if any(marker not in text for marker in markers):
            raise CheckoutRoutingModelError(f"local source markers missing: {relative}")
        rows.append(
            {
                "path": relative.as_posix(),
                "bytes": audit["bytes"],
                "sha256": audit["sha256"],
                "marker_count": len(markers),
                "matches": True,
            }
        )
    return rows


def build_contract(
    config_path: str | Path,
    m8a_preserved_metadata: Path,
    m8a_audit_metadata: Path,
    m9l_contract_metadata: Path,
    m9l_discrimination_metadata: Path,
    m9l_decision_metadata: Path,
    m8a_audit_root: Path,
    m9l_contract_root: Path,
    m9l_discrimination_root: Path,
    m9l_decision_root: Path,
    upstream_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_checkout_routing_model_config(config_path)
    metadata = {
        role: _audit_metadata(config, role, path)
        for role, path in (
            ("m8a_preserved", m8a_preserved_metadata),
            ("m8a_audit", m8a_audit_metadata),
            ("m9l_contract", m9l_contract_metadata),
            ("m9l_discrimination", m9l_discrimination_metadata),
            ("m9l_decision", m9l_decision_metadata),
        )
    }
    evidence = config.raw["evidence"]
    audits: list[dict[str, Any]] = []
    for role, root in (
        ("m8a_audit", m8a_audit_root),
        ("m9l_contract", m9l_contract_root),
        ("m9l_discrimination", m9l_discrimination_root),
        ("m9l_decision", m9l_decision_root),
    ):
        audits.extend(
            _audit_locked_files(
                root, _object(evidence[role]["files"], f"{role}.files"), role
            )
        )

    m8a = _object(_load_json(m8a_audit_root / "manifest.json", "M8A manifest"), "M8A")
    if (
        m8a.get("source_run_id") != "33990678586"
        or m8a.get("artifact_counts", {}).get("qualified_cell") != 160
        or m8a.get("row_counts", {}).get("identities") != 160
        or any(int(value) != 0 for value in _object(m8a.get("quality"), "M8A quality").values())
    ):
        raise CheckoutRoutingModelError("accepted M8A contract differs")
    m9l_contract = _object(
        _load_json(m9l_contract_root / "contract-manifest.json", "M9L contract"),
        "M9L contract",
    )
    m9l = _object(
        _load_json(
            m9l_discrimination_root / "discrimination-manifest.json",
            "M9L discrimination",
        ),
        "M9L discrimination",
    )
    m9l_decision = _object(
        _load_json(m9l_decision_root / "decision-manifest.json", "M9L decision"),
        "M9L decision",
    )
    expected_status = "checkout_residual_localized_to_observed_replica_path_loss"
    if (
        m9l_contract.get("status")
        != "m9k_route_up_residual_and_retained_evidence_verified"
        or m9l.get("status") != expected_status
        or m9l.get("integrity_passed") is not True
        or m9l.get("cell_count") != config.expected_cells
        or m9l.get("discrimination", {}).get("classification")
        != "observed_replica_path_loss"
        or m9l_decision.get("status") != expected_status
        or m9l_decision.get("technical_evidence_accepted") is not True
        or m9l_decision.get("next_experiment")
        != "m9m_checkout_request_level_routing_model_test"
        or m9l_decision.get("overall_article_verdict_changed") is not False
    ):
        raise CheckoutRoutingModelError("accepted M9L branch differs")

    upstream_rows = _audit_upstream_sources(config, upstream_root)
    local_rows = _audit_local_sources(config)
    repository = validate_repository(config.path)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "artifact-file-audit.csv",
        ["role", "path", "bytes", "sha256", "matches"],
        audits,
    )
    _write_csv(
        out / "upstream-source-audit.csv",
        ["path", "bytes", "sha256", "git_blob", "marker_count", "matches"],
        upstream_rows,
    )
    _write_csv(
        out / "local-source-audit.csv",
        ["path", "bytes", "sha256", "marker_count", "matches"],
        local_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9m_checkout_routing_contract",
        "status": "m9l_branch_source_and_information_boundary_verified",
        "config_sha256": file_sha256(config.path),
        "artifact_metadata": metadata,
        "artifact_file_audits": len(audits),
        "upstream_source_files": len(upstream_rows),
        "local_source_files": len(local_rows),
        "repository_locks": len(repository["repository_locks"]),
        "target": {"profile": config.profile, "operation": config.operation},
        "selected_cells": config.expected_cells,
        "successful_request_target_call_sites": 3,
        "candidate_generation_may_access_evaluator": False,
        "candidate_selection_after_test": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "files": {
            "artifact-file-audit.csv": file_sha256(out / "artifact-file-audit.csv"),
            "upstream-source-audit.csv": file_sha256(out / "upstream-source-audit.csv"),
            "local-source-audit.csv": file_sha256(out / "local-source-audit.csv"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "contract-manifest.json", manifest)
    return manifest


def _expected_identities(
    config: CheckoutRoutingModelConfig,
) -> set[tuple[str, str, str, int]]:
    return {
        (config.profile, placement, law, repetition)
        for placement in config.placements
        for law in config.failure_laws
        for repetition in config.repetitions
    }


def _manifest_identity(path: Path) -> tuple[str, str, str, int]:
    value = _object(_load_json(path, "learner manifest"), "learner manifest")
    return (
        str(value.get("profile")),
        str(value.get("placement")),
        str(value.get("failure_law")),
        int(value.get("repetition", -1)),
    )


def _selected_source_directories(
    config: CheckoutRoutingModelConfig, qualified_root: Path
) -> tuple[list[tuple[tuple[str, str, str, int], Path]], int]:
    manifests = sorted(qualified_root.rglob("learner/manifest.json"))
    selected = [
        (_manifest_identity(path), path.parents[1])
        for path in manifests
        if _manifest_identity(path) in _expected_identities(config)
    ]
    identities = [identity for identity, _ in selected]
    if len(manifests) != 160:
        raise CheckoutRoutingModelError(f"qualified manifest census differs: {len(manifests)}")
    if (
        set(identities) != _expected_identities(config)
        or len(identities) != len(set(identities))
    ):
        raise CheckoutRoutingModelError("selected M9M identity matrix differs")
    return sorted(selected), len(manifests)


def stage_learner_inputs(
    config_path: str | Path,
    contract_manifest_path: Path,
    qualified_root: Path,
    m8a_audit_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutRoutingModelError("full M9M staging may run only in GitHub Actions")
    config = load_checkout_routing_model_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9M contract"), "contract")
    if (
        contract.get("status") != "m9l_branch_source_and_information_boundary_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or contract.get("candidate_generation_may_access_evaluator") is not False
    ):
        raise CheckoutRoutingModelError("M9M contract differs at staging")
    evidence = config.raw["evidence"]
    _audit_locked_files(
        m8a_audit_root,
        _object(evidence["m8a_audit"]["files"], "M8A files"),
        "m8a_audit",
    )
    inventory_rows = _rows(m8a_audit_root / "file-inventory.csv")
    inventory = {
        str(row["relative_path"]).replace("\\", "/"): row
        for row in inventory_rows
        if row.get("evidence_group") == "qualified"
    }
    selected, census = _selected_source_directories(config, qualified_root)
    file_rows: list[dict[str, Any]] = []
    for identity, directory in selected:
        destination = out / directory.name
        for relative_text in LEARNER_FILES:
            relative = Path(relative_text)
            source = directory / relative
            source_relative = source.relative_to(qualified_root).as_posix()
            expected = inventory.get(source_relative)
            if expected is None or not source.is_file():
                raise CheckoutRoutingModelError(f"learner source missing: {source_relative}")
            observed_bytes = source.stat().st_size
            observed_hash = file_sha256(source)
            if (
                observed_bytes != int(expected["size_in_bytes"])
                or observed_hash != expected["sha256"]
            ):
                raise CheckoutRoutingModelError(f"learner source differs: {source_relative}")
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
        raise CheckoutRoutingModelError("M9M learner staging file count differs")
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
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9m_learner_only_stage",
        "status": "learner_only_inputs_staged",
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "qualified_manifest_census": census,
        "selected_cells": config.expected_cells,
        "staged_files": len(file_rows),
        "evaluator_files_parsed": 0,
        "evaluator_files_copied": 0,
        "test_outcomes_accessed": False,
        "files": {"learner-file-audit.csv": file_sha256(out / "learner-file-audit.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "stage-manifest.json", manifest)
    return manifest


def _load_learner_cell(directory: Path) -> QualifiedCell:
    learner = _object(
        _load_json(directory / "learner" / "manifest.json", "learner manifest"),
        "learner manifest",
    )
    boundary = _object(
        _load_json(directory / "audit" / "boundary.json", "boundary"), "boundary"
    )
    if boundary.get("usable") is not True:
        raise CheckoutRoutingModelError(f"learner boundary is unusable: {directory}")
    deployment = _object(
        _load_json(directory / "learner" / "deployment.json", "deployment"),
        "deployment",
    )
    raw_rows = _rows(directory / "learner" / "requests.csv")
    requests = tuple(
        RequestRecord(
            period=row["period"],
            request_id=row["request_id"],
            operation=row["operation"],
            at=_timestamp(row["started_at"]),
            success=int(_bool(row["semantic_success"])),
            trace_present=_bool(row["trace_present"]),
            span_count=int(row["span_count"]),
            services=frozenset(filter(None, row["services"].split(";"))),
            target_replicas=frozenset(
                filter(None, row["target_replicas"].split(";"))
            ),
        )
        for row in raw_rows
    )
    return QualifiedCell(
        profile=str(learner["profile"]),
        placement=str(learner["placement"]),
        failure_law=str(learner["failure_law"]),
        repetition=int(learner["repetition"]),
        target_service=str(deployment["target_service"]),
        learner_requests=requests,
        health=_health_ticks(directory / "learner" / "health.csv"),
        test_requests=(),
        test_health=(),
        boundary=dict(boundary),
        directory=directory,
    )


def _footprint_weights(
    cell: QualifiedCell, mode: Any, analysis: Any, operation: str
) -> dict[str, Any]:
    sampled = 0
    counts: Counter[str] = Counter()
    invalid = 0
    for request in cell.learner_requests:
        if request.period != "baseline" or request.operation != operation:
            continue
        keep = _stable_uniform(
            analysis.seed,
            *cell.identity,
            mode.id,
            "trace",
            request.request_id,
        ) < mode.trace_keep_probability
        if not keep:
            continue
        sampled += 1
        replicas = ";".join(sorted(request.target_replicas))
        usable = bool(
            request.trace_present
            and request.span_count > 0
            and cell.target_service in request.services
            and replicas in {"a", "b", "a;b"}
        )
        if usable:
            counts[replicas] += 1
        else:
            invalid += 1
    resolved = sum(counts.values())
    if sampled <= 0 or resolved <= 0:
        raise CheckoutRoutingModelError(f"no baseline routing footprints: {cell.identity}")
    return {
        "sampled_baseline_checkout_requests": sampled,
        "resolved_footprints": resolved,
        "unresolved_footprints": invalid,
        "resolution_fraction": resolved / sampled,
        "footprint_a": counts["a"],
        "footprint_b": counts["b"],
        "footprint_a_b": counts["a;b"],
        "weight_a": counts["a"] / resolved,
        "weight_b": counts["b"] / resolved,
        "weight_a_b": counts["a;b"] / resolved,
        "both_replica_fraction": counts["a;b"] / resolved,
        "outcomes_read_for_footprint": False,
    }


def route_state_vector(
    placement: str,
    method: str,
    weights: Mapping[str, float] | None = None,
) -> np.ndarray:
    template = _latent_template(placement)
    pa = template.signals[:, 2].astype(float)
    pb = template.signals[:, 3].astype(float)
    if method == "m7_single_demand_or":
        return np.maximum(pa, pb)
    if method == "source_strict_round_robin_and":
        return pa * pb
    if method == "source_three_call_independent":
        return ((pa + pb) / 2.0) ** 3
    if method == "source_two_client_affinity":
        return ((pa + pb) / 2.0) ** 2
    if method == "learner_trace_requirement_mixture":
        if weights is None:
            raise CheckoutRoutingModelError("trace-mixture weights are required")
        wa = _finite(weights.get("weight_a"), "weight_a")
        wb = _finite(weights.get("weight_b"), "weight_b")
        wab = _finite(weights.get("weight_a_b"), "weight_a_b")
        if not math.isclose(wa + wb + wab, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise CheckoutRoutingModelError("trace-mixture weights do not sum to one")
        return wa * pa + wb * pb + wab * pa * pb
    raise CheckoutRoutingModelError(f"unknown route model: {method}")


@dataclass(frozen=True)
class CandidateLikelihoodData:
    template: Any
    consistency: np.ndarray
    class_masks: np.ndarray
    log_outcomes: np.ndarray
    multiplicities: np.ndarray
    probability_floor: float


def _candidate_likelihood_data(
    prepared: Any,
    placement: str,
    method: str,
    weights: Mapping[str, float],
    floor: float,
) -> CandidateLikelihoodData:
    operations = _target_operations(prepared)
    if prepared.mode.id != "sampled_mixed" or not operations:
        raise CheckoutRoutingModelError("candidate likelihood target operations differ")
    compressed = Counter((tick.observed, tick.outcomes) for tick in prepared.ticks)
    records = list(compressed)
    template = _latent_template(placement)
    consistency = np.ones((len(records), len(template.bits)), dtype=bool)
    or_route = route_state_vector(placement, "m7_single_demand_or")
    checkout_route = route_state_vector(placement, method, weights)
    signatures = sorted(
        {(float(or_route[index]), float(checkout_route[index])) for index in range(len(template.bits))}
    )
    class_masks = np.asarray(
        [
            [
                float(or_route[index]) == signature[0]
                and float(checkout_route[index]) == signature[1]
                for index in range(len(template.bits))
            ]
            for signature in signatures
        ],
        dtype=float,
    )
    log_outcomes = np.zeros((len(records), len(signatures)), dtype=float)
    for row_index, (observed, outcomes) in enumerate(records):
        for signal_index, value in enumerate(observed):
            if value is not None:
                consistency[row_index] &= template.signals[:, signal_index] == value
        for class_index, signature in enumerate(signatures):
            for operation, (attempts, successes) in zip(operations, outcomes, strict=True):
                if not attempts:
                    continue
                route = signature[1] if operation == "checkout" else signature[0]
                probability = min(
                    max(float(prepared.q_by_operation[operation]) * route, floor),
                    1.0 - floor,
                )
                log_outcomes[row_index, class_index] += successes * math.log(probability)
                log_outcomes[row_index, class_index] += (
                    attempts - successes
                ) * math.log1p(-probability)
    return CandidateLikelihoodData(
        template=template,
        consistency=consistency,
        class_masks=class_masks,
        log_outcomes=log_outcomes,
        multiplicities=np.asarray([compressed[record] for record in records], dtype=float),
        probability_floor=floor,
    )


def _candidate_objective(
    values: np.ndarray,
    names: tuple[str, ...],
    data: CandidateLikelihoodData,
) -> float:
    parameters = {
        name: float(value) for name, value in zip(names, values, strict=True)
    }
    if not all(math.isfinite(value) for value in parameters.values()):
        return 1e100
    try:
        probabilities = _state_probabilities(data.template, parameters)
    except (ValueError, FloatingPointError, RuntimeError):
        return 1e100
    consistent_mass = data.consistency.astype(float) * probabilities[np.newaxis, :]
    class_masses = consistent_mass @ data.class_masks.T
    log_terms = np.log(np.maximum(class_masses, data.probability_floor)) + data.log_outcomes
    record_logs = logsumexp(log_terms, axis=1)
    if not np.all(np.isfinite(record_logs)):
        return 1e100
    result = -float(data.multiplicities @ record_logs)
    return result if math.isfinite(result) else 1e100


def _fit_structural_candidate(
    cell: QualifiedCell,
    prepared: Any,
    analysis: Any,
    method: str,
    weights: Mapping[str, float],
) -> dict[str, Any]:
    names = _parameter_names(cell.failure_law)
    data = _candidate_likelihood_data(
        prepared,
        cell.placement,
        method,
        weights,
        analysis.numerical_probability_floor,
    )
    epsilon = analysis.parameter_epsilon
    bounds = [(epsilon, 1.0 - epsilon)] * len(names)
    start_seed = int(
        _stable_uniform(analysis.seed, *cell.identity, prepared.mode.id, "optimizer")
        * (2**63 - 1)
    )
    generator = np.random.default_rng(start_seed)
    starts = [np.full(len(names), 0.9, dtype=float)]
    starts.extend(
        generator.uniform(0.55, 0.99, size=len(names))
        for _ in range(analysis.optimizer_starts - 1)
    )
    results: list[dict[str, Any]] = []
    route = route_state_vector(cell.placement, method, weights)
    for start in starts:
        fit = minimize(
            _candidate_objective,
            start,
            args=(names, data),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": analysis.optimizer_max_iterations, "ftol": 1e-12},
        )
        if not math.isfinite(float(fit.fun)):
            continue
        parameters = {
            name: float(value)
            for name, value in zip(names, np.asarray(fit.x, dtype=float), strict=True)
        }
        state_probabilities = _state_probabilities(data.template, parameters)
        results.append(
            {
                "parameters": parameters,
                "nll": float(fit.fun),
                "converged": bool(fit.success),
                "message": str(fit.message),
                "route_probability": float(state_probabilities @ route),
            }
        )
    if not results:
        raise CheckoutRoutingModelError(
            f"all {method} fits were nonfinite: {cell.identity}"
        )
    results.sort(key=lambda item: float(item["nll"]))
    best = results[0]
    equivalent = [
        item
        for item in results
        if float(item["nll"]) - float(best["nll"])
        <= 1e-6 * max(1.0, abs(float(best["nll"])))
    ]
    prediction_range = max(float(item["route_probability"]) for item in equivalent) - min(
        float(item["route_probability"]) for item in equivalent
    )
    boundary = any(
        value <= epsilon * 1.01 or value >= 1.0 - epsilon * 1.01
        for value in best["parameters"].values()
    )
    return {
        "route_probability": float(best["route_probability"]),
        "fit_nll": float(best["nll"]),
        "fit_status": (
            "boundary" if boundary and best["converged"] else
            "boundary_nonconvergence" if boundary else
            "regular" if best["converged"] else
            "finite_nonconvergence"
        ),
        "finite_starts": len(results),
        "converged_starts": sum(bool(item["converged"]) for item in results),
        "equivalent_prediction_range": prediction_range,
        "parameters": best["parameters"],
    }


def _find_m7_prediction(
    rows: Sequence[Mapping[str, Any]], method: str, operation: str
) -> Mapping[str, Any]:
    selected = [
        row
        for row in rows
        if row.get("method") == method and row.get("operation") == operation
    ]
    if len(selected) != 1:
        raise CheckoutRoutingModelError(f"M7 {method} checkout row differs")
    return selected[0]


def generate_candidates(
    config_path: str | Path,
    contract_manifest_path: Path,
    learner_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutRoutingModelError(
            "full M9M candidate generation may run only in GitHub Actions"
        )
    config = load_checkout_routing_model_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9M contract"), "contract")
    stage = _object(_load_json(learner_root / "stage-manifest.json", "M9M stage"), "stage")
    if (
        contract.get("status") != "m9l_branch_source_and_information_boundary_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or stage.get("status") != "learner_only_inputs_staged"
        or stage.get("config_sha256") != file_sha256(config.path)
        or stage.get("contract_manifest_sha256") != file_sha256(contract_manifest_path)
        or stage.get("selected_cells") != config.expected_cells
        or stage.get("evaluator_files_parsed") != 0
        or stage.get("evaluator_files_copied") != 0
        or stage.get("test_outcomes_accessed") is not False
        or file_sha256(learner_root / "learner-file-audit.csv")
        != stage.get("files", {}).get("learner-file-audit.csv")
    ):
        raise CheckoutRoutingModelError("M9M learner stage contract differs")

    m7_path = config.path.resolve().parent / "m7_frozen_live.yaml"
    frozen = load_frozen_live_validation_config(m7_path)
    analysis = frozen.analysis
    modes = [mode for mode in analysis.modes if mode.id == "sampled_mixed"]
    if (
        len(modes) != 1
        or modes[0].trace_keep_probability != 0.7
        or analysis.primary_mode != "sampled_mixed"
        or analysis.health_alignment_tolerance_seconds != config.alignment_tolerance
        or analysis.transition_guard_seconds_each_side != config.transition_guard
    ):
        raise CheckoutRoutingModelError("frozen M7 analysis constants differ")
    mode = modes[0]
    manifests = sorted(learner_root.glob("*/learner/manifest.json"))
    if len(manifests) != config.expected_cells:
        raise CheckoutRoutingModelError("staged learner cell count differs")

    candidate_rows: list[dict[str, Any]] = []
    footprint_rows: list[dict[str, Any]] = []
    fit_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for manifest_path in manifests:
        cell = _load_learner_cell(manifest_path.parents[1])
        if cell.identity not in _expected_identities(config) or cell.identity in seen:
            raise CheckoutRoutingModelError(f"staged cell identity differs: {cell.identity}")
        seen.add(cell.identity)
        footprint = _footprint_weights(cell, mode, analysis, config.operation)
        footprint_rows.append(
            {
                "profile": cell.profile,
                "placement": cell.placement,
                "failure_law": cell.failure_law,
                "repetition": cell.repetition,
                **footprint,
            }
        )
        prepared = prepare_mode(cell, mode, analysis)
        exact = fit_exact_model(cell, prepared, analysis)
        if exact.best is None:
            raise CheckoutRoutingModelError(f"M7 OR fit missing: {cell.identity}")
        m7_rows = predict_cell(cell, prepared, exact, analysis, scope="current")
        proposed = _find_m7_prediction(m7_rows, "proposed", config.operation)
        b2 = _find_m7_prediction(m7_rows, "B2", config.operation)
        q = _finite(proposed["residual_success_probability"], "checkout q")
        base = {
            "profile": cell.profile,
            "placement": cell.placement,
            "failure_law": cell.failure_law,
            "repetition": cell.repetition,
            "mode": mode.id,
            "scope": "current",
            "operation": config.operation,
        }
        candidate_rows.append(
            {
                **base,
                "method": "m7_single_demand_or",
                "prediction": _finite(proposed["prediction"], "M7 OR prediction"),
                "route_prediction": _finite(proposed["route_prediction"], "M7 OR route"),
                "residual_success_probability": q,
                "fit_nll": exact.best.nll,
                "fit_status": exact.status,
                "finite_starts": len(exact.candidates),
                "converged_starts": sum(item.converged for item in exact.candidates),
                "equivalent_prediction_range": exact.current_prediction_range,
                "candidate_frozen_before_test": True,
            }
        )
        fit_rows.append(
            {
                **base,
                "method": "m7_single_demand_or",
                "parameters_json": json.dumps(exact.best.parameters, sort_keys=True),
                "fit_nll": exact.best.nll,
                "fit_status": exact.status,
                "route_prediction": exact.best.current_route,
                "equivalent_prediction_range": exact.current_prediction_range,
            }
        )
        weights = {
            "weight_a": float(footprint["weight_a"]),
            "weight_b": float(footprint["weight_b"]),
            "weight_a_b": float(footprint["weight_a_b"]),
        }
        for method in ROUTE_MODELS[1:]:
            fit = _fit_structural_candidate(cell, prepared, analysis, method, weights)
            route = float(fit["route_probability"])
            candidate_rows.append(
                {
                    **base,
                    "method": method,
                    "prediction": q * route,
                    "route_prediction": route,
                    "residual_success_probability": q,
                    "fit_nll": fit["fit_nll"],
                    "fit_status": fit["fit_status"],
                    "finite_starts": fit["finite_starts"],
                    "converged_starts": fit["converged_starts"],
                    "equivalent_prediction_range": fit["equivalent_prediction_range"],
                    "candidate_frozen_before_test": True,
                }
            )
            fit_rows.append(
                {
                    **base,
                    "method": method,
                    "parameters_json": json.dumps(fit["parameters"], sort_keys=True),
                    "fit_nll": fit["fit_nll"],
                    "fit_status": fit["fit_status"],
                    "route_prediction": route,
                    "equivalent_prediction_range": fit["equivalent_prediction_range"],
                }
            )
        candidate_rows.append(
            {
                **base,
                "method": REFERENCE_MODEL,
                "prediction": _finite(b2["prediction"], "M7 B2 prediction"),
                "route_prediction": _finite(b2["route_prediction"], "M7 B2 route"),
                "residual_success_probability": _finite(
                    b2["residual_success_probability"], "M7 B2 q"
                ),
                "fit_nll": exact.best.nll,
                "fit_status": str(b2["status"]),
                "finite_starts": len(exact.candidates),
                "converged_starts": sum(item.converged for item in exact.candidates),
                "equivalent_prediction_range": "",
                "candidate_frozen_before_test": True,
            }
        )

    if seen != _expected_identities(config) or len(candidate_rows) != 240 or len(fit_rows) != 200:
        raise CheckoutRoutingModelError("M9M frozen candidate matrix differs")
    trace_gates = all(
        int(row["resolved_footprints"]) >= config.minimum_footprints
        and float(row["resolution_fraction"]) >= config.minimum_resolution
        and float(row["both_replica_fraction"]) >= config.minimum_both
        for row in footprint_rows
    )
    fit_ranges = [
        float(row["equivalent_prediction_range"])
        for row in candidate_rows
        if row["method"] != REFERENCE_MODEL
    ]
    fit_integrity = all(
        int(row["finite_starts"]) == analysis.optimizer_starts
        and int(row["converged_starts"]) >= 1
        and float(row["equivalent_prediction_range"]) <= config.fit_range_tolerance
        for row in candidate_rows
        if row["method"] != REFERENCE_MODEL
    )
    out.mkdir(parents=True, exist_ok=True)
    candidate_fields = [
        "profile", "placement", "failure_law", "repetition", "mode", "scope",
        "operation", "method", "prediction", "route_prediction",
        "residual_success_probability", "fit_nll", "fit_status", "finite_starts",
        "converged_starts", "equivalent_prediction_range", "candidate_frozen_before_test",
    ]
    _write_csv(out / "candidate-predictions.csv", candidate_fields, candidate_rows)
    _write_csv(
        out / "footprint-audit.csv",
        [
            "profile", "placement", "failure_law", "repetition",
            "sampled_baseline_checkout_requests", "resolved_footprints",
            "unresolved_footprints", "resolution_fraction", "footprint_a",
            "footprint_b", "footprint_a_b", "weight_a", "weight_b", "weight_a_b",
            "both_replica_fraction", "outcomes_read_for_footprint",
        ],
        footprint_rows,
    )
    _write_csv(
        out / "fit-audit.csv",
        [
            "profile", "placement", "failure_law", "repetition", "mode", "scope",
            "operation", "method", "parameters_json", "fit_nll", "fit_status",
            "route_prediction", "equivalent_prediction_range",
        ],
        fit_rows,
    )
    shutil.copy2(learner_root / "learner-file-audit.csv", out / "learner-file-audit.csv")
    shutil.copy2(learner_root / "stage-manifest.json", out / "stage-manifest.json")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9m_checkout_candidate_freeze",
        "status": "candidate_predictions_frozen_before_evaluator_access",
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "selected_cells": config.expected_cells,
        "candidate_rows": len(candidate_rows),
        "fit_rows": len(fit_rows),
        "footprint_rows": len(footprint_rows),
        "trace_gates_passed": trace_gates,
        "fit_integrity_passed": fit_integrity,
        "quality": {
            "minimum_resolved_footprints": min(int(row["resolved_footprints"]) for row in footprint_rows),
            "minimum_resolution_fraction": min(float(row["resolution_fraction"]) for row in footprint_rows),
            "minimum_both_replica_fraction": min(float(row["both_replica_fraction"]) for row in footprint_rows),
            "maximum_equivalent_prediction_range": max(fit_ranges),
        },
        "candidate_job_received_learner_only_stage": True,
        "evaluator_files_present_during_model_fit": False,
        "evaluator_files_parsed": 0,
        "test_outcomes_accessed": False,
        "footprint_outcomes_read": False,
        "candidate_selection_after_test": False,
        "additional_trace_structure_is_free_input": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "candidate-predictions.csv",
                "footprint-audit.csv",
                "fit-audit.csv",
                "learner-file-audit.csv",
                "stage-manifest.json",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "candidate-manifest.json", manifest)
    return manifest


def _candidate_key(row: Mapping[str, Any]) -> tuple[str, str, str, int, str]:
    return (
        str(row["profile"]),
        str(row["placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
        str(row["method"]),
    )


def _frozen_prediction_key(
    row: Mapping[str, Any],
) -> tuple[str, str, str, int, str]:
    method = {
        "proposed": "m7_single_demand_or",
        "B2": REFERENCE_MODEL,
    }[str(row["method"])]
    return (
        str(row["profile"]),
        str(row["source_placement"]),
        str(row["failure_law"]),
        int(row["repetition"]),
        method,
    )


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise CheckoutRoutingModelError("cannot average an empty sequence")
    return math.fsum(values) / len(values)


def _bootstrap_evaluation(
    rows: Sequence[Mapping[str, Any]],
    resamples: int,
    seed: int,
    confidence_level: float,
) -> dict[str, dict[str, float]]:
    by_identity: dict[tuple[str, str, str, int], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        identity = (
            str(row["profile"]),
            str(row["placement"]),
            str(row["failure_law"]),
            int(row["repetition"]),
        )
        method = str(row["method"])
        if method in by_identity[identity]:
            raise CheckoutRoutingModelError("duplicate evaluation method within a cell")
        by_identity[identity][method] = row
    if len(by_identity) != 40 or any(set(value) != set(ALL_METHODS) for value in by_identity.values()):
        raise CheckoutRoutingModelError("evaluation method matrix differs")
    strata: dict[tuple[str, str], list[tuple[str, str, str, int]]] = defaultdict(list)
    for identity in by_identity:
        strata[(identity[1], identity[2])].append(identity)
    if sorted(len(values) for values in strata.values()) != [10, 10, 10, 10]:
        raise CheckoutRoutingModelError("evaluation bootstrap strata differ")

    metric_names: list[str] = []
    for method in ALL_METHODS:
        metric_names.extend(
            f"{method}.{metric}"
            for metric in ("prediction", "signed_error", "absolute_error", "brier_score")
        )
        if method != "m7_single_demand_or":
            metric_names.extend(
                (
                    f"{method}.delta_absolute_error_vs_or",
                    f"{method}.delta_brier_vs_or",
                )
            )

    def metric(identity: tuple[str, str, str, int], name: str) -> float:
        method, field = name.split(".", maxsplit=1)
        row = by_identity[identity][method]
        if field == "prediction":
            return float(row["prediction"])
        if field == "signed_error":
            return float(row["signed_prediction_error"])
        if field == "absolute_error":
            return float(row["absolute_prediction_error"])
        if field == "brier_score":
            return float(row["brier_score"])
        reference = by_identity[identity]["m7_single_demand_or"]
        if field == "delta_absolute_error_vs_or":
            return float(row["absolute_prediction_error"]) - float(
                reference["absolute_prediction_error"]
            )
        if field == "delta_brier_vs_or":
            return float(row["brier_score"]) - float(reference["brier_score"])
        raise CheckoutRoutingModelError(f"unknown bootstrap metric: {name}")

    identities = sorted(by_identity)
    observed = {
        name: _mean([metric(identity, name) for identity in identities])
        for name in metric_names
    }
    generator = np.random.default_rng(seed)
    draws = {name: np.empty(resamples, dtype=float) for name in metric_names}
    ordered_strata = [sorted(strata[key]) for key in sorted(strata)]
    for iteration in range(resamples):
        sample: list[tuple[str, str, str, int]] = []
        for values in ordered_strata:
            indexes = generator.integers(0, len(values), size=len(values))
            sample.extend(values[int(index)] for index in indexes)
        for name in metric_names:
            draws[name][iteration] = _mean([metric(identity, name) for identity in sample])
    alpha = (1.0 - confidence_level) / 2.0
    return {
        name: {
            "estimate": observed[name],
            "lower": float(np.quantile(draws[name], alpha)),
            "upper": float(np.quantile(draws[name], 1.0 - alpha)),
        }
        for name in metric_names
    }


def _method_closes(
    bootstrap: Mapping[str, Mapping[str, float]], method: str, margin: float
) -> bool:
    signed = bootstrap[f"{method}.signed_error"]
    return bool(
        abs(float(signed["estimate"])) <= margin
        and float(signed["lower"]) <= 0.0 <= float(signed["upper"])
    )


def classify_evaluation(
    bootstrap: Mapping[str, Mapping[str, float]],
    *,
    integrity_passed: bool,
    trace_gates_passed: bool,
    bracketed_cells: int,
    closure_margin: float,
    minimum_bracketed: int,
) -> dict[str, Any]:
    closures = {
        method: _method_closes(bootstrap, method, closure_margin)
        for method in ALL_METHODS
    }
    primary_brier = bootstrap[f"{PRIMARY_MODEL}.delta_brier_vs_or"]
    primary_absolute = bootstrap[f"{PRIMARY_MODEL}.delta_absolute_error_vs_or"]
    primary_supported = bool(
        integrity_passed
        and trace_gates_passed
        and closures[PRIMARY_MODEL]
        and float(primary_brier["upper"]) < 0.0
        and float(primary_absolute["upper"]) < 0.0
    )
    intermediate = [
        method
        for method in (
            "source_three_call_independent",
            "source_two_client_affinity",
        )
        if closures[method]
    ]
    bracketed = bool(
        integrity_passed
        and bracketed_cells >= minimum_bracketed
        and intermediate
    )
    primary_signed = bootstrap[f"{PRIMARY_MODEL}.signed_error"]
    primary_overshoots = bool(
        integrity_passed
        and float(primary_signed["upper"]) < -closure_margin
    )
    request_candidates = ROUTE_MODELS[1:]
    gap_persists = bool(
        integrity_passed
        and all(
            float(bootstrap[f"{method}.signed_error"]["lower"]) > closure_margin
            for method in request_candidates
        )
    )
    if not integrity_passed or not trace_gates_passed:
        branch = "integrity_fail"
    elif primary_supported:
        branch = "primary_supported"
    elif bracketed:
        branch = "bracketed_routing_law_unresolved"
    elif primary_overshoots:
        branch = "primary_overshoots"
    elif gap_persists:
        branch = "gap_persists"
    else:
        branch = "inconclusive"
    return {
        "branch": branch,
        "method_closure": closures,
        "primary_supported": primary_supported,
        "intermediate_closing_models": intermediate,
        "bracketed_routing_law_unresolved": bracketed,
        "primary_overshoots": primary_overshoots,
        "gap_persists": gap_persists,
        "bracketed_cells": bracketed_cells,
    }


def evaluate_candidates(
    config_path: str | Path,
    contract_manifest_path: Path,
    candidate_root: Path,
    qualified_root: Path,
    analysis_root: Path,
    m8a_audit_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise CheckoutRoutingModelError(
            "full M9M held-out evaluation may run only in GitHub Actions"
        )
    config = load_checkout_routing_model_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "M9M contract"), "contract")
    candidate_manifest_path = candidate_root / "candidate-manifest.json"
    candidate_manifest = _object(
        _load_json(candidate_manifest_path, "M9M candidates"), "candidates"
    )
    if (
        contract.get("status") != "m9l_branch_source_and_information_boundary_verified"
        or contract.get("config_sha256") != file_sha256(config.path)
        or candidate_manifest.get("status")
        != "candidate_predictions_frozen_before_evaluator_access"
        or candidate_manifest.get("config_sha256") != file_sha256(config.path)
        or candidate_manifest.get("contract_manifest_sha256")
        != file_sha256(contract_manifest_path)
        or candidate_manifest.get("selected_cells") != config.expected_cells
        or candidate_manifest.get("candidate_rows") != 240
        or candidate_manifest.get("test_outcomes_accessed") is not False
        or candidate_manifest.get("candidate_selection_after_test") is not False
    ):
        raise CheckoutRoutingModelError("M9M frozen candidate contract differs")
    for name, digest in _object(candidate_manifest.get("files"), "candidate files").items():
        path = candidate_root / _relative(name, "candidate file")
        if not path.is_file() or file_sha256(path) != digest:
            raise CheckoutRoutingModelError(f"frozen candidate file differs: {name}")

    evidence = config.raw["evidence"]
    _audit_locked_files(
        m8a_audit_root,
        _object(evidence["m8a_audit"]["files"], "M8A files"),
        "m8a_audit",
    )
    frozen_prediction = _object(
        evidence["frozen_analysis"]["predictions.csv"], "frozen predictions"
    )
    _audit_file(
        analysis_root / "predictions.csv", frozen_prediction, "frozen predictions.csv"
    )
    selected, census = _selected_source_directories(config, qualified_root)
    directories = [path for _, path in selected]
    selected_file_rows = _audit_selected_files(
        config, qualified_root, directories, m8a_audit_root / "file-inventory.csv"
    )

    candidate_rows = _rows(candidate_root / "candidate-predictions.csv")
    candidate_by_key = {_candidate_key(row): row for row in candidate_rows}
    expected_keys = {
        (*identity, method)
        for identity in _expected_identities(config)
        for method in ALL_METHODS
    }
    if len(candidate_rows) != 240 or set(candidate_by_key) != expected_keys:
        raise CheckoutRoutingModelError("frozen candidate row matrix differs")
    frozen_rows = [
        row
        for row in _rows(analysis_root / "predictions.csv")
        if row.get("profile") == config.profile
        and row.get("operation") == config.operation
        and row.get("source_placement") in config.placements
        and row.get("target_placement") == row.get("source_placement")
        and row.get("failure_law") in config.failure_laws
        and int(row.get("repetition", -1)) in config.repetitions
        and row.get("method") in {"proposed", "B2"}
        and row.get("mode") == "sampled_mixed"
        and row.get("scope") == "current"
    ]
    frozen_by_key = {_frozen_prediction_key(row): row for row in frozen_rows}
    if len(frozen_rows) != 80 or set(frozen_by_key) != {
        key for key in expected_keys if key[-1] in {"m7_single_demand_or", REFERENCE_MODEL}
    }:
        raise CheckoutRoutingModelError("frozen M7 reference matrix differs")
    frozen_mismatches = 0
    for key, frozen_row in frozen_by_key.items():
        candidate = candidate_by_key[key]
        for field in ("prediction", "route_prediction", "residual_success_probability"):
            frozen_mismatches += int(
                not math.isclose(
                    _finite(candidate[field], f"candidate {field}"),
                    _finite(frozen_row[field], f"frozen {field}"),
                    rel_tol=0.0,
                    abs_tol=config.probability_tolerance,
                )
            )
    if frozen_mismatches:
        raise CheckoutRoutingModelError("M9M OR/B2 predictions do not reproduce M7")

    score_rows: list[dict[str, Any]] = []
    stable_counts: list[int] = []
    bracketed_cells = 0
    for identity, directory in selected:
        cell = load_qualified_cell(directory)
        metrics = next(
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
        attempts = int(metrics["view_requests"])
        successes = int(round(float(metrics["empirical_success_rate"]) * attempts))
        # Use the count from the rate only after checking exact integer recovery.
        if attempts <= 0 or not math.isclose(
            successes / attempts,
            float(metrics["empirical_success_rate"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise CheckoutRoutingModelError(f"stable test count differs: {identity}")
        stable_counts.append(attempts)
        test_rate = successes / attempts
        cell_predictions: dict[str, float] = {}
        for method in ALL_METHODS:
            candidate = candidate_by_key[(*identity, method)]
            prediction = _finite(candidate["prediction"], "candidate prediction")
            if not 0.0 <= prediction <= 1.0:
                raise CheckoutRoutingModelError("candidate probability lies outside [0,1]")
            brier = (
                successes * (prediction - 1.0) ** 2
                + (attempts - successes) * prediction**2
            ) / attempts
            cell_predictions[method] = prediction
            score_rows.append(
                {
                    "profile": identity[0],
                    "placement": identity[1],
                    "failure_law": identity[2],
                    "repetition": identity[3],
                    "method": method,
                    "prediction": prediction,
                    "test_requests": attempts,
                    "test_successes": successes,
                    "test_success_rate": test_rate,
                    "signed_prediction_error": prediction - test_rate,
                    "absolute_prediction_error": abs(prediction - test_rate),
                    "brier_score": brier,
                }
            )
        lower = min(
            cell_predictions["source_strict_round_robin_and"],
            cell_predictions["m7_single_demand_or"],
        )
        upper = max(
            cell_predictions["source_strict_round_robin_and"],
            cell_predictions["m7_single_demand_or"],
        )
        bracketed_cells += int(lower <= test_rate <= upper)
    if len(score_rows) != 240:
        raise CheckoutRoutingModelError("M9M score matrix differs")

    bootstrap = _bootstrap_evaluation(
        score_rows, config.resamples, config.seed, config.confidence_level
    )
    candidate_integrity = bool(candidate_manifest.get("fit_integrity_passed"))
    trace_gates = bool(candidate_manifest.get("trace_gates_passed"))
    integrity = bool(
        candidate_integrity
        and frozen_mismatches == 0
        and census == 160
        and len(selected_file_rows) == 360
        and min(stable_counts) >= config.minimum_stable_test
    )
    classification = classify_evaluation(
        bootstrap,
        integrity_passed=integrity,
        trace_gates_passed=trace_gates,
        bracketed_cells=bracketed_cells,
        closure_margin=config.closure_margin,
        minimum_bracketed=config.minimum_bracketed,
    )
    branch = str(classification["branch"])
    decision = _object(config.raw["decision"], "decision")
    status = str(decision[branch])
    next_experiment = (
        "m9m_repair_information_boundary_or_fit_integrity"
        if branch == "integrity_fail"
        else str(decision[f"next_{branch}"])
    )
    mean_brier = {
        method: float(bootstrap[f"{method}.brier_score"]["estimate"])
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
        out / "heldout-scores.csv",
        [
            "profile", "placement", "failure_law", "repetition", "method",
            "prediction", "test_requests", "test_successes", "test_success_rate",
            "signed_prediction_error", "absolute_prediction_error", "brier_score",
        ],
        score_rows,
    )
    bootstrap_rows = [
        {"metric": name, **values} for name, values in sorted(bootstrap.items())
    ]
    _write_csv(
        out / "bootstrap-summary.csv",
        ["metric", "estimate", "lower", "upper"],
        bootstrap_rows,
    )
    decision_rows = []
    for method in ALL_METHODS:
        decision_rows.append(
            {
                "method": method,
                "primary": method == PRIMARY_MODEL,
                "mean_prediction": bootstrap[f"{method}.prediction"]["estimate"],
                "mean_signed_error": bootstrap[f"{method}.signed_error"]["estimate"],
                "signed_error_lower": bootstrap[f"{method}.signed_error"]["lower"],
                "signed_error_upper": bootstrap[f"{method}.signed_error"]["upper"],
                "mean_absolute_error": bootstrap[f"{method}.absolute_error"]["estimate"],
                "mean_brier_score": bootstrap[f"{method}.brier_score"]["estimate"],
                "closes_signed_gap": classification["method_closure"][method],
                "selected_from_test": False,
            }
        )
    _write_csv(
        out / "decision-matrix.csv",
        [
            "method", "primary", "mean_prediction", "mean_signed_error",
            "signed_error_lower", "signed_error_upper", "mean_absolute_error",
            "mean_brier_score", "closes_signed_gap", "selected_from_test",
        ],
        decision_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9m_checkout_routing_heldout_evaluation",
        "status": status,
        "config_sha256": file_sha256(config.path),
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "candidate_manifest_sha256": file_sha256(candidate_manifest_path),
        "candidate_artifact_preceded_evaluator_access": True,
        "selected_cells": config.expected_cells,
        "score_rows": len(score_rows),
        "bootstrap": bootstrap,
        "classification": classification,
        "next_experiment": next_experiment,
        "descriptive_minimum_brier_method": descriptive_minimum,
        "descriptive_minimum_promoted": False,
        "integrity_passed": integrity,
        "technical_evidence_accepted": integrity and trace_gates,
        "quality": {
            "qualified_manifest_census": census,
            "selected_files_audited": len(selected_file_rows),
            "frozen_M7_prediction_mismatches": frozen_mismatches,
            "minimum_stable_test_requests": min(stable_counts),
            "bracketed_cells": bracketed_cells,
        },
        "reused_test_is_independent_confirmation": False,
        "single_operation_generalization_authorized": False,
        "changes_m7_predictions_or_scores": False,
        "better_overall_accuracy_demonstrated": False,
        "lower_end_to_end_cost_than_pmx_demonstrated": False,
        "pmx_scientific_priority_reduced": False,
        "overall_article_verdict_changed": False,
        "pmx_invocations": 0,
        "new_live_collections": 0,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "selected-file-audit.csv",
                "heldout-scores.csv",
                "bootstrap-summary.csv",
                "decision-matrix.csv",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "evaluation-manifest.json", manifest)
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M9M checkout routing-model test")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("--config", type=Path, required=True)

    contract = commands.add_parser("build-contract")
    contract.add_argument("--config", type=Path, required=True)
    contract.add_argument("--m8a-preserved-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-metadata", type=Path, required=True)
    contract.add_argument("--m9l-contract-metadata", type=Path, required=True)
    contract.add_argument("--m9l-discrimination-metadata", type=Path, required=True)
    contract.add_argument("--m9l-decision-metadata", type=Path, required=True)
    contract.add_argument("--m8a-audit-root", type=Path, required=True)
    contract.add_argument("--m9l-contract-root", type=Path, required=True)
    contract.add_argument("--m9l-discrimination-root", type=Path, required=True)
    contract.add_argument("--m9l-decision-root", type=Path, required=True)
    contract.add_argument("--upstream-root", type=Path, required=True)
    contract.add_argument("--out", type=Path, required=True)

    stage = commands.add_parser("stage-learner")
    stage.add_argument("--config", type=Path, required=True)
    stage.add_argument("--contract-manifest", type=Path, required=True)
    stage.add_argument("--qualified-root", type=Path, required=True)
    stage.add_argument("--m8a-audit-root", type=Path, required=True)
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
    evaluate.add_argument("--analysis-root", type=Path, required=True)
    evaluate.add_argument("--m8a-audit-root", type=Path, required=True)
    evaluate.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "validate":
        result = validate_repository(args.config)
    elif args.command == "build-contract":
        result = build_contract(
            args.config,
            args.m8a_preserved_metadata,
            args.m8a_audit_metadata,
            args.m9l_contract_metadata,
            args.m9l_discrimination_metadata,
            args.m9l_decision_metadata,
            args.m8a_audit_root,
            args.m9l_contract_root,
            args.m9l_discrimination_root,
            args.m9l_decision_root,
            args.upstream_root,
            args.out,
        )
    elif args.command == "stage-learner":
        result = stage_learner_inputs(
            args.config,
            args.contract_manifest,
            args.qualified_root,
            args.m8a_audit_root,
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
            args.analysis_root,
            args.m8a_audit_root,
            args.out,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
