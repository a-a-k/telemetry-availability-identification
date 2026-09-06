from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import shutil
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from importlib.metadata import version as distribution_version
from pathlib import Path
from statistics import fmean, variance
from typing import Any, Iterable, Mapping, Sequence

from scipy.stats import t

from .live_validation_analysis import (
    QualifiedCell,
    RequestRecord,
    _bool,
    _health_ticks,
    _rows,
    _timestamp,
    discover_qualified_cells,
    fit_exact_model,
    predict_cell,
    prepare_mode,
)
from .live_validation_config import load_frozen_live_validation_config
from .m7_diagnostic_analysis import outcome_counts
from .palladio_mapping import (
    ApplicationModel,
    PalladioMappingConfig,
    _audit_one_application_model,
    _model_payloads,
    load_palladio_mapping_config,
)
from .provenance import environment_manifest, file_sha256


class PalladioAlignedError(RuntimeError):
    """Raised when the frozen M9D aligned-input contract is violated."""


_SHA256 = set("0123456789abcdef")
_METHODS = ("B0", "B2", "B3", "proposed")
_MODEL_FILES = (
    "default.allocation",
    "default.repository",
    "default.resourceenvironment",
    "default.system",
    "default.usagemodel",
)


@dataclass(frozen=True)
class ArtifactLock:
    key: str
    run_id: int
    head_sha: str
    artifact_id: int
    artifact_name: str
    size_in_bytes: int
    sha256: str
    manifest_sha256: str | None = None


@dataclass(frozen=True)
class PalladioAlignedConfig:
    path: Path
    raw: Mapping[str, Any]
    id: str
    source_run_id: int
    source_commit: str
    observation_mode: str
    operations: Mapping[str, str]
    failure_laws: tuple[str, ...]
    repetitions: int
    probability_tolerance: float
    technical_repetitions: int
    expected_models: int
    expected_raw_runs: int
    expected_opportunities: Mapping[str, int]
    expected_emitted: Mapping[str, int]
    expected_missing: Mapping[str, int]
    expected_fit_statuses: Mapping[str, int]
    expected_state_models: Mapping[int, int]
    analyzer_commit: str
    pcm_commit: str
    artifact_locks: Mapping[str, ArtifactLock]


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PalladioAlignedError(f"{label} must be an object")
    return value


def _integer(value: object, label: str, *, positive: bool = True) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PalladioAlignedError(f"{label} must be an integer")
    if positive and value <= 0:
        raise PalladioAlignedError(f"{label} must be positive")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PalladioAlignedError(f"{label} must be a non-empty string")
    return value


def _digest(value: object, label: str, length: int = 64) -> str:
    result = _string(value, label)
    if len(result) != length or any(character not in _SHA256 for character in result):
        raise PalladioAlignedError(f"{label} must be a lowercase hexadecimal digest")
    return result


def _load_probability(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PalladioAlignedError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 < result < 1.0:
        raise PalladioAlignedError(f"{label} must lie strictly between zero and one")
    return result


def _artifact_lock(key: str, raw: object) -> ArtifactLock:
    data = _object(raw, f"evidence.{key}")
    return ArtifactLock(
        key=key,
        run_id=_integer(data.get("run_id"), f"evidence.{key}.run_id"),
        head_sha=_digest(data.get("head_sha"), f"evidence.{key}.head_sha", 40),
        artifact_id=_integer(data.get("artifact_id"), f"evidence.{key}.artifact_id"),
        artifact_name=_string(data.get("artifact_name"), f"evidence.{key}.artifact_name"),
        size_in_bytes=_integer(data.get("size_in_bytes"), f"evidence.{key}.size_in_bytes"),
        sha256=_digest(data.get("sha256"), f"evidence.{key}.sha256"),
        manifest_sha256=(
            _digest(data.get("manifest_sha256"), f"evidence.{key}.manifest_sha256")
            if "manifest_sha256" in data
            else None
        ),
    )


def load_palladio_aligned_config(path: str | Path) -> PalladioAlignedConfig:
    config_path = Path(path).resolve()
    root = _object(json.loads(config_path.read_text(encoding="utf-8")), "root")
    if root.get("schema_version") != 1:
        raise PalladioAlignedError("schema_version must equal 1")
    if root.get("status") != "frozen_before_first_remote_parameter_recovery_or_solver_output":
        raise PalladioAlignedError("M9D status must retain the preregistered freeze")
    evidence = _object(root.get("evidence"), "evidence")
    design = _object(root.get("design"), "design")
    mapping = _object(root.get("mapping"), "mapping")
    runtime = _object(root.get("runtime"), "runtime")

    locks = {
        key: _artifact_lock(key, evidence.get(key))
        for key in (
            "m8a_preserved_evidence",
            "m8a_integrity_audit",
            "m9c_contract",
            "m9c_solver",
            "m9c_acceptance",
        )
    }
    source_run_id = _integer(evidence.get("m7_source_run_id"), "evidence.m7_source_run_id")
    source_commit = _digest(evidence.get("m7_source_commit"), "evidence.m7_source_commit", 40)
    if source_run_id != 33990678586 or source_commit != (
        "b1925736f314da610debd23a586d7b7d00cae7ca"
    ):
        raise PalladioAlignedError("frozen M7 source identity differs")
    expected_artifact_anchors = {
        "m8a_preserved_evidence": (
            34016153918,
            "7a9744f6bf2db69424efc2ae0197714ebee42505",
            9983956440,
            "m8-preserved-m7-evidence-33990678586-34016153918",
            78577341,
            "978b380bf54be67ec13b2ebbfaac4464ee5653106ee68176fefcf2db4e85e271",
            None,
        ),
        "m8a_integrity_audit": (
            34016153918,
            "7a9744f6bf2db69424efc2ae0197714ebee42505",
            9983956747,
            "m8a-m7-integrity-arithmetic-34016153918",
            737045,
            "eca453e577ccac02f26716660062664355dde046748456b4695caa7480ba3439",
            "e0c923926006d920207a236e7d74ac440806bb30af8e99c9ae5ff4a8142ace1e",
        ),
        "m9c_contract": (
            34026488176,
            "45539a33f4b150cb961981dbcd27c55427cf3cf4",
            9987214676,
            "m9c-palladio-contract-34026488176",
            1160392,
            "f9e5ab7f5a63696241222b91ba4f7660c7de30bb5fd49b875711988e92cc3ed8",
            None,
        ),
        "m9c_solver": (
            34026488176,
            "45539a33f4b150cb961981dbcd27c55427cf3cf4",
            9987264993,
            "m9c-palladio-application-models-34026488176",
            82562,
            "30e9ce5926f8d826f6ea91b0f84b4ce6841bdc44e1e631abfa48652de6434e6c",
            None,
        ),
        "m9c_acceptance": (
            34026488176,
            "45539a33f4b150cb961981dbcd27c55427cf3cf4",
            9987270345,
            "m9c-palladio-acceptance-34026488176",
            2612,
            "1585d3ed0cc66466b4faf4a0d017cdbb156ec27b7bb1f10c0f5f3255e3c2a227",
            "3bdaf4b785495a4eca8974aed10b50d454b8ddb6b237841ed84b84b9b2ce2175",
        ),
    }
    for key, expected in expected_artifact_anchors.items():
        lock = locks[key]
        observed = (
            lock.run_id,
            lock.head_sha,
            lock.artifact_id,
            lock.artifact_name,
            lock.size_in_bytes,
            lock.sha256,
            lock.manifest_sha256,
        )
        if observed != expected:
            raise PalladioAlignedError(f"frozen artifact anchor differs: {key}")
    frozen = _object(evidence.get("frozen_analysis"), "evidence.frozen_analysis")
    expected_analysis = {
        "manifest.json",
        "predictions.csv",
        "scores.csv",
        "cell-diagnostics.csv",
        "contrasts.csv",
        "summary.csv",
    }
    if set(frozen) != expected_analysis:
        raise PalladioAlignedError("frozen analysis file inventory differs")
    for name, digest in frozen.items():
        _digest(digest, f"evidence.frozen_analysis.{name}")

    repository_locks = evidence.get("repository_locks")
    if not isinstance(repository_locks, list) or not repository_locks:
        raise PalladioAlignedError("evidence.repository_locks must be non-empty")
    seen_paths: set[str] = set()
    for index, raw in enumerate(repository_locks):
        item = _object(raw, f"evidence.repository_locks[{index}]")
        relative = Path(_string(item.get("path"), f"repository_locks[{index}].path"))
        if relative.is_absolute() or ".." in relative.parts:
            raise PalladioAlignedError("repository lock paths must be repository-relative")
        if relative.as_posix() in seen_paths:
            raise PalladioAlignedError("repository lock paths must be unique")
        seen_paths.add(relative.as_posix())
        _digest(item.get("sha256"), f"repository_locks[{index}].sha256")
    required_locks = {
        "configs/m7_frozen_live.yaml",
        "requirements.txt",
        "src/telemetry_availability/live_validation_analysis.py",
        "src/telemetry_availability/live_validation_config.py",
        "src/telemetry_availability/live_validation.py",
        "configs/m9c_palladio_application_mapping.json",
        "src/telemetry_availability/palladio_mapping.py",
        "docs/M9D_PALLADIO_ALIGNED_INPUT_PROTOCOL.md",
    }
    if not required_locks.issubset(seen_paths):
        raise PalladioAlignedError("required M7/M9C/M9D repository locks are missing")
    manual_log = _object(evidence.get("manual_actions_log"), "manual_actions_log")
    if manual_log.get("path") != "docs/M9D_MANUAL_ACTIONS.csv":
        raise PalladioAlignedError("manual action log path differs")
    _digest(manual_log.get("initial_sha256"), "manual_actions_log.initial_sha256")
    _integer(
        manual_log.get("initial_size_in_bytes"),
        "manual_actions_log.initial_size_in_bytes",
    )
    if (
        manual_log.get("initial_sha256")
        != "cd8ecb130debd2910e2569d618670961c97df3425038480cb0b000c9f8dcff3f"
        or manual_log.get("initial_size_in_bytes") != 1571
    ):
        raise PalladioAlignedError("manual action log initial prefix differs")
    for key in (
        "append_only_after_preregistration",
        "planned_rows_are_not_completed_work",
        "final_sha256_recorded_at_acceptance",
    ):
        if manual_log.get(key) is not True:
            raise PalladioAlignedError(f"manual action log rule differs: {key}")

    operations = _object(design.get("operations"), "design.operations")
    expected_operations = {
        "deathstarbench_social_network": "read_user_timeline",
        "opentelemetry_demo": "browse_product",
    }
    if dict(operations) != expected_operations:
        raise PalladioAlignedError("M9D operation population differs from M9C")
    if design.get("observation_mode") != "sampled_mixed":
        raise PalladioAlignedError("M9D must retain sampled_mixed")
    if design.get("accuracy_views") != ["all_sequence", "stable"]:
        raise PalladioAlignedError("M9D accuracy views differ")
    if design.get("retained_score_views") != [
        "all_sequence",
        "stable",
        "stable_block_sensitivity",
    ]:
        raise PalladioAlignedError("M9D retained score views differ")
    labels = _object(design.get("historical_method_labels"), "design.historical_method_labels")
    if tuple(labels) != _METHODS or dict(labels) != {
        "B0": "B0",
        "B2": "B2",
        "B3": "B3-direct",
        "proposed": "proposed-direct",
    }:
        raise PalladioAlignedError("historical method labels differ")
    if design.get("technical_reference_methods") != [
        "B3-direct",
        "PCM-PAR/B3-parameters",
    ]:
        raise PalladioAlignedError("technical reference methods differ")
    if design.get("accuracy_methods") != [
        "B0",
        "B2",
        "proposed-direct",
        "PCM-PAR/admissible",
    ]:
        raise PalladioAlignedError("accuracy methods differ")
    laws = tuple(design.get("failure_laws", ()))
    if laws != ("N", "NC", "ND", "NCD"):
        raise PalladioAlignedError("failure-law inventory differs")
    opportunities = _object(design.get("opportunities"), "design.opportunities")
    expected_emitted = _object(design.get("expected_emitted"), "design.expected_emitted")
    missing = _object(design.get("expected_missing"), "design.expected_missing")
    if {key: int(value) for key, value in opportunities.items()} != {
        "current": 160,
        "transfer": 80,
        "total": 240,
    }:
        raise PalladioAlignedError("opportunity inventory differs")
    if {key: int(value) for key, value in expected_emitted.items()} != {
        "B0": 240,
        "B2": 184,
        "B3": 184,
        "proposed": 184,
        "PCM-PAR/admissible": 184,
    }:
        raise PalladioAlignedError("emitted-prediction inventory differs")
    if {key: int(value) for key, value in missing.items()} != {
        "current": 41,
        "transfer": 15,
        "total": 56,
    }:
        raise PalladioAlignedError("missing-prediction inventory differs")
    if design.get("source_placement") != "colocated" or design.get(
        "target_placement"
    ) != "split":
        raise PalladioAlignedError("M9D placement comparison differs")
    if design.get("expected_unique_fit_replays") != 160 or design.get(
        "expected_transfer_fit_reuses"
    ) != 80:
        raise PalladioAlignedError("fit replay/reuse inventory differs")
    if design.get("expected_missing_reason") != "topology_ambiguous_target_fraction":
        raise PalladioAlignedError("missing-reason taxonomy differs")
    stratum_rows = design.get("expected_emitted_by_stratum")
    if not isinstance(stratum_rows, list) or len(stratum_rows) != 24:
        raise PalladioAlignedError("expected emitted-stratum table must have 24 rows")
    stratum_keys: set[tuple[str, ...]] = set()
    stratum_counts: dict[tuple[str, ...], int] = {}
    stratum_scope_counts: Counter[str] = Counter()
    for index, raw in enumerate(stratum_rows):
        item = _object(raw, f"expected_emitted_by_stratum[{index}]")
        key = tuple(
            _string(item.get(field), f"expected_emitted_by_stratum[{index}].{field}")
            for field in (
                "application",
                "scope",
                "source_placement",
                "target_placement",
                "failure_law",
            )
        )
        if key in stratum_keys:
            raise PalladioAlignedError("expected emitted-stratum identities must be unique")
        stratum_keys.add(key)
        emitted = _integer(
            item.get("emitted"), f"expected_emitted_by_stratum[{index}].emitted"
        )
        if emitted > 10:
            raise PalladioAlignedError("stratum emission cannot exceed repetitions")
        stratum_counts[key] = emitted
        stratum_scope_counts[key[1]] += emitted
    if dict(stratum_scope_counts) != {"current": 119, "transfer": 65}:
        raise PalladioAlignedError("emitted-stratum totals differ")
    by_application_placement = {
        "deathstarbench_social_network": {
            "colocated": {"N": 10, "NC": 8, "ND": 10, "NCD": 7},
            "split": {"N": 10, "NC": 3, "ND": 10, "NCD": 7},
        },
        "opentelemetry_demo": {
            "colocated": {"N": 10, "NC": 6, "ND": 10, "NCD": 4},
            "split": {"N": 10, "NC": 2, "ND": 10, "NCD": 2},
        },
    }
    expected_stratum_counts: dict[tuple[str, ...], int] = {}
    for application, placements in by_application_placement.items():
        for placement, counts_by_law in placements.items():
            for law, emitted in counts_by_law.items():
                expected_stratum_counts[
                    (application, "current", placement, placement, law)
                ] = emitted
        for law, emitted in placements["colocated"].items():
            expected_stratum_counts[
                (application, "transfer", "colocated", "split", law)
            ] = emitted
    if stratum_counts != expected_stratum_counts:
        raise PalladioAlignedError("emitted-stratum cell counts differ")

    boundary = _object(design.get("fit_input_boundary"), "design.fit_input_boundary")
    if boundary.get("allowed_cell_trees") != ["learner/**", "audit/**"]:
        raise PalladioAlignedError("learner-only allowlist differs")
    if boundary.get("forbidden_paths") != [
        "evaluator/**",
        "**/test-requests.csv",
        "**/test-health.csv",
    ]:
        raise PalladioAlignedError("learner-only denylist differs")
    for key in (
        "frozen_predictions_available_only_for_post_fit_reproduction_check",
        "guard_checks_paths_not_audit_file_contents",
    ):
        if boundary.get(key) is not True:
            raise PalladioAlignedError(f"fit-input boundary flag differs: {key}")
    for key in ("scores_available_to_fitter", "evaluator_available_to_fitter"):
        if boundary.get(key) is not False:
            raise PalladioAlignedError(f"fit-input boundary flag differs: {key}")

    if mapping.get("parameter_source") != "deterministic_frozen_B3_optimizer_realization":
        raise PalladioAlignedError("parameter source differs")
    expected_mapping = {
        "inactive_domain_factor": 1.0,
        "inactive_communication_factor": 1.0,
        "communication_link_failure_formula": "1-sqrt(call_success)",
        "resource_ratio_formula": "MTTF=A;MTTR=1-A",
        "colocated_route_formula": "q*g*(ea*ca+(1-ea*ca)*eb*cb)",
        "split_route_formula": "q*(g*ea*ca+(1-g*ea*ca)*g*eb*cb)",
    }
    for key, value in expected_mapping.items():
        if mapping.get(key) != value:
            raise PalladioAlignedError(f"PCM mapping rule differs: {key}")
    if mapping.get("individual_parameters_are_causally_identified") is not False:
        raise PalladioAlignedError("optimizer realization must not be causalized")
    if mapping.get("literal_round_robin_or_retry_claimed") is not False:
        raise PalladioAlignedError("literal router behavior must not be claimed")
    if mapping.get("temporal_disconnect_process_claimed") is not False:
        raise PalladioAlignedError("temporal communication behavior must not be claimed")

    tolerance = _measure_tolerance(runtime.get("probability_tolerance"), "runtime.probability_tolerance")
    if tolerance > 1e-12:
        raise PalladioAlignedError("probability tolerance cannot exceed 1e-12")
    if _integer(runtime.get("job_timeout_minutes"), "runtime.job_timeout_minutes") != 360:
        raise PalladioAlignedError("all M9D jobs must retain 360-minute timeouts")
    if runtime.get("java") != "Temurin 17" or runtime.get("python") != "CPython 3.13.15":
        raise PalladioAlignedError("runtime versions differ from the freeze")
    if dict(_object(runtime.get("dependencies"), "runtime.dependencies")) != {
        "numpy": "2.4.4", "scipy": "1.17.1", "PyYAML": "6.0.2"
    }:
        raise PalladioAlignedError("M7 replay dependency versions differ")
    if runtime.get("warmup_models") != 1 or runtime.get("warmup_selection") != "lexicographically_first_admitted_model_id":
        raise PalladioAlignedError("solver warmup rule differs")
    if runtime.get("solver_time_limit_enabled") is not False:
        raise PalladioAlignedError("solver time limit must remain disabled")
    state_models = {
        int(key): int(value)
        for key, value in _object(
            runtime.get("expected_physical_state_models"),
            "runtime.expected_physical_state_models",
        ).items()
    }
    if state_models != {4: 153, 8: 31}:
        raise PalladioAlignedError("physical-state model inventory differs")

    analysis = _object(root.get("analysis"), "analysis")
    expected_analysis = {
        "confidence_level": 0.95,
        "interval_method": "m7_equal_stratum_welch_satterthwaite",
        "contrast_orientation": "first_minus_second",
        "negative_brier_difference_favors": "first",
        "current_intended_strata": 16,
        "transfer_intended_strata": 8,
        "minimum_pairs_per_represented_stratum": 2,
        "incomplete_intended_support_is_marked_incomplete": True,
        "compute_p_values": False,
    }
    for key, value in expected_analysis.items():
        if analysis.get(key) != value:
            raise PalladioAlignedError(f"analysis rule differs: {key}")
    expected_contrasts = [
        ["PCM-PAR/admissible", "proposed-direct"],
        ["PCM-PAR/B3-parameters", "B3-direct"],
        ["PCM-PAR/admissible", "B2"],
        ["PCM-PAR/admissible", "B0"],
        ["proposed-direct", "B2"],
        ["proposed-direct", "B0"],
        ["B2", "B0"],
    ]
    if analysis.get("pairwise_contrasts") != expected_contrasts:
        raise PalladioAlignedError("pairwise contrast inventory differs")

    reuse = _object(root.get("reuse_endpoints"), "reuse_endpoints")
    if reuse != {
        "expected_template_files_manually_changed_per_cell": 0,
        "record_parameter_only_serialization_time": True,
        "record_automatic_colocated_to_split_transformation_time": True,
        "record_automatically_written_parameter_fields": True,
        "expected_automatically_written_parameter_fields_per_model": 9,
        "record_manual_interventions_per_model": True,
        "separate_initial_integration_from_repeated_update": True,
    }:
        raise PalladioAlignedError("model-reuse endpoint contract differs")

    config = PalladioAlignedConfig(
        path=config_path,
        raw=root,
        id=_string(root.get("id"), "root.id"),
        source_run_id=source_run_id,
        source_commit=source_commit,
        observation_mode="sampled_mixed",
        operations={str(key): str(value) for key, value in operations.items()},
        failure_laws=laws,
        repetitions=_integer(design.get("repetitions"), "design.repetitions"),
        probability_tolerance=tolerance,
        technical_repetitions=_integer(runtime.get("technical_repetitions"), "runtime.technical_repetitions"),
        expected_models=_integer(runtime.get("expected_models"), "runtime.expected_models"),
        expected_raw_runs=_integer(runtime.get("expected_raw_runs"), "runtime.expected_raw_runs"),
        expected_opportunities={str(key): int(value) for key, value in opportunities.items()},
        expected_emitted={str(key): int(value) for key, value in expected_emitted.items()},
        expected_missing={str(key): int(value) for key, value in missing.items()},
        expected_fit_statuses={
            str(key): int(value)
            for key, value in _object(
                design.get("expected_fit_statuses_on_pcm_support"),
                "design.expected_fit_statuses_on_pcm_support",
            ).items()
        },
        expected_state_models=state_models,
        analyzer_commit=_digest(runtime.get("analyzer_commit"), "runtime.analyzer_commit", 40),
        pcm_commit=_digest(runtime.get("pcm_commit"), "runtime.pcm_commit", 40),
        artifact_locks=locks,
    )
    if config.repetitions != 10 or config.technical_repetitions != 2:
        raise PalladioAlignedError("repetition counts differ")
    if config.expected_models != 184 or config.expected_raw_runs != 368:
        raise PalladioAlignedError("model/run counts differ")
    if dict(config.expected_fit_statuses) != {
        "regular": 183,
        "finite_nonconvergence": 1,
    }:
        raise PalladioAlignedError("fit-status inventory differs")
    if config.analyzer_commit != "a694e570afb705dc9e0470dc321e77b7219dcea4":
        raise PalladioAlignedError("analyzer commit differs from accepted M9C")
    if config.pcm_commit != "5fbcc3409e02687881f88ab78b6242d8acd2677c":
        raise PalladioAlignedError("PCM commit differs from accepted M9C")
    return config


def _measure_tolerance(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PalladioAlignedError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise PalladioAlignedError(f"{label} must be positive and finite")
    return result


def _audit_replay_runtime(config: PalladioAlignedConfig) -> Mapping[str, str]:
    observed = {
        "python": f"{platform.python_implementation()} {platform.python_version()}",
        "numpy": distribution_version("numpy"),
        "scipy": distribution_version("scipy"),
        "PyYAML": distribution_version("PyYAML"),
    }
    expected = {
        "python": config.raw["runtime"]["python"],
        **config.raw["runtime"]["dependencies"],
    }
    if observed != expected:
        raise PalladioAlignedError(
            f"M9D replay runtime differs: observed={observed}, expected={expected}"
        )
    return observed


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _file_prefix_sha256(path: Path, size_in_bytes: int) -> str:
    digest = hashlib.sha256()
    remaining = size_in_bytes
    with path.open("rb") as handle:
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    if remaining:
        return ""
    return digest.hexdigest()


def _find_manifest(root: Path, *, kind: str | None = None) -> tuple[Path, Mapping[str, Any]]:
    matches: list[tuple[Path, Mapping[str, Any]]] = []
    for path in root.rglob("manifest.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, Mapping) and (kind is None or value.get("kind") == kind):
            matches.append((path, value))
    if len(matches) != 1:
        raise PalladioAlignedError(
            f"expected one {kind or 'eligible'} manifest below {root}, found {len(matches)}"
        )
    return matches[0]


def _artifact_metadata(path: Path, lock: ArtifactLock) -> Mapping[str, Any]:
    data = _object(json.loads(path.read_text(encoding="utf-8")), f"{lock.key} metadata")
    expected = {
        "id": lock.artifact_id,
        "name": lock.artifact_name,
        "size_in_bytes": lock.size_in_bytes,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            raise PalladioAlignedError(f"{lock.key} artifact metadata differs for {key}")
    if data.get("expired") is True:
        raise PalladioAlignedError(f"{lock.key} artifact is expired")
    digest = str(data.get("digest") or "")
    if digest not in {lock.sha256, f"sha256:{lock.sha256}"}:
        raise PalladioAlignedError(f"{lock.key} artifact digest differs")
    workflow = _object(data.get("workflow_run"), f"{lock.key}.workflow_run")
    if int(workflow.get("id", -1)) != lock.run_id or workflow.get("head_sha") != lock.head_sha:
        raise PalladioAlignedError(f"{lock.key} workflow identity differs")
    return data


def _repository_lock_audit(config: PalladioAlignedConfig, repository_root: Path) -> list[dict[str, Any]]:
    rows = []
    evidence = _object(config.raw["evidence"], "evidence")
    for raw in evidence["repository_locks"]:
        item = _object(raw, "repository lock")
        relative = str(item["path"])
        path = repository_root / relative
        actual = file_sha256(path) if path.is_file() else ""
        rows.append(
            {
                "path": relative,
                "expected_sha256": str(item["sha256"]),
                "actual_sha256": actual,
                "matches": actual == item["sha256"],
            }
        )
    return rows


def _analysis_directory(root: Path) -> Path:
    return _find_manifest(root, kind="frozen_live_validation_analysis")[0].parent


def _count_cell_manifests(root: Path) -> int:
    return sum(1 for _ in root.rglob("learner/manifest.json"))


def _count_raw_samples(root: Path) -> int:
    return sum(
        path.is_dir() and path.name.startswith("m7-raw-audit-sample-")
        for path in root.iterdir()
    )


def _audit_preserved_groups(
    audit_root: Path,
    group_roots: Mapping[str, Path],
) -> list[dict[str, Any]]:
    inventory_candidates = list(audit_root.rglob("file-inventory.csv"))
    if len(inventory_candidates) != 1:
        raise PalladioAlignedError("accepted M8A file inventory is not unique")
    _, audit_manifest = _find_manifest(
        audit_root, kind="m7_posthoc_integrity_and_arithmetic_diagnostic"
    )
    expected_inventory_hash = _object(
        audit_manifest.get("files"), "M8A manifest files"
    ).get("file-inventory.csv")
    if file_sha256(inventory_candidates[0]) != expected_inventory_hash:
        raise PalladioAlignedError("accepted M8A file inventory hash differs")
    expected: dict[tuple[str, str], tuple[int, str]] = {}
    for row in _rows(inventory_candidates[0]):
        group = row["evidence_group"]
        if group not in group_roots:
            continue
        key = (group, row["relative_path"])
        if key in expected:
            raise PalladioAlignedError(f"duplicate M8A file inventory key: {key}")
        expected[key] = (int(row["size_in_bytes"]), row["sha256"])
    actual: dict[tuple[str, str], tuple[int, str]] = {}
    for group, root in group_roots.items():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            key = (group, path.relative_to(root).as_posix())
            actual[key] = (path.stat().st_size, file_sha256(path))
    rows = []
    for key in sorted(set(expected) | set(actual)):
        expected_value = expected.get(key)
        actual_value = actual.get(key)
        rows.append(
            {
                "evidence_group": key[0],
                "relative_path": key[1],
                "expected_size_in_bytes": expected_value[0] if expected_value else "",
                "actual_size_in_bytes": actual_value[0] if actual_value else "",
                "expected_sha256": expected_value[1] if expected_value else "",
                "actual_sha256": actual_value[1] if actual_value else "",
                "matches": expected_value == actual_value,
            }
        )
    return rows


def audit_palladio_aligned_evidence(
    config_path: str | Path,
    m8a_preserved_metadata_path: str | Path,
    m8a_audit_metadata_path: str | Path,
    m9c_contract_metadata_path: str | Path,
    m9c_solver_metadata_path: str | Path,
    m9c_acceptance_metadata_path: str | Path,
    qualified_root: str | Path,
    analysis_root: str | Path,
    raw_root: str | Path,
    audit_root: str | Path,
    m9c_contract_root: str | Path,
    m9c_acceptance_root: str | Path,
    repository_root: str | Path,
    output_root: str | Path,
) -> Mapping[str, Any]:
    """Byte-audit all accepted inputs without performing the expensive M7 replay."""

    config = load_palladio_aligned_config(config_path)
    replay_runtime = _audit_replay_runtime(config)
    metadata_paths = {
        "m8a_preserved_evidence": Path(m8a_preserved_metadata_path),
        "m8a_integrity_audit": Path(m8a_audit_metadata_path),
        "m9c_contract": Path(m9c_contract_metadata_path),
        "m9c_solver": Path(m9c_solver_metadata_path),
        "m9c_acceptance": Path(m9c_acceptance_metadata_path),
    }
    for key, path in metadata_paths.items():
        _artifact_metadata(path, config.artifact_locks[key])

    analysis = _analysis_directory(Path(analysis_root))
    frozen_hashes = _object(config.raw["evidence"]["frozen_analysis"], "frozen analysis")
    analysis_rows = []
    for name, expected in sorted(frozen_hashes.items()):
        path = analysis / name
        actual = file_sha256(path) if path.is_file() else ""
        analysis_rows.append(
            {"path": name, "expected_sha256": expected, "actual_sha256": actual, "matches": actual == expected}
        )

    audit_manifest_path, audit_manifest = _find_manifest(
        Path(audit_root), kind="m7_posthoc_integrity_and_arithmetic_diagnostic"
    )
    audit_lock = config.artifact_locks["m8a_integrity_audit"]
    if audit_lock.manifest_sha256 and file_sha256(audit_manifest_path) != audit_lock.manifest_sha256:
        raise PalladioAlignedError("accepted M8A audit manifest differs")
    if any(int(value) for value in _object(audit_manifest.get("quality"), "M8A quality").values()):
        raise PalladioAlignedError("accepted M8A audit contains a quality mismatch")
    inventory_candidates = list(Path(audit_root).rglob("file-inventory.csv"))
    if len(inventory_candidates) != 1:
        raise PalladioAlignedError("accepted M8A file inventory is not unique")
    inventory_manifest_hash = _object(
        audit_manifest.get("files"), "M8A manifest files"
    ).get("file-inventory.csv")
    if file_sha256(inventory_candidates[0]) != inventory_manifest_hash:
        raise PalladioAlignedError("accepted M8A file inventory hash differs")
    inventory_rows = _rows(inventory_candidates[0])
    group_roots = {
        "analysis": Path(analysis_root),
        "qualified": Path(qualified_root),
        "raw_audit_sample": Path(raw_root),
    }
    expected_inventory: dict[tuple[str, str], tuple[int, str]] = {}
    for row in inventory_rows:
        key = (row["evidence_group"], row["relative_path"])
        if key in expected_inventory or key[0] not in group_roots:
            raise PalladioAlignedError(f"invalid M8A file inventory key: {key}")
        expected_inventory[key] = (int(row["size_in_bytes"]), row["sha256"])
    actual_inventory: dict[tuple[str, str], tuple[int, str]] = {}
    inventory_audit_rows = []
    for group, root_path in group_roots.items():
        for path in sorted(item for item in root_path.rglob("*") if item.is_file()):
            key = (group, path.relative_to(root_path).as_posix())
            actual_inventory[key] = (path.stat().st_size, file_sha256(path))
    for key in sorted(set(expected_inventory) | set(actual_inventory)):
        expected_value = expected_inventory.get(key)
        actual_value = actual_inventory.get(key)
        inventory_audit_rows.append(
            {
                "evidence_group": key[0],
                "relative_path": key[1],
                "expected_size_in_bytes": expected_value[0] if expected_value else "",
                "actual_size_in_bytes": actual_value[0] if actual_value else "",
                "expected_sha256": expected_value[1] if expected_value else "",
                "actual_sha256": actual_value[1] if actual_value else "",
                "matches": expected_value == actual_value,
            }
        )

    contract_root = Path(m9c_contract_root)
    contract_evidence = list(contract_root.rglob("evidence-manifest.json"))
    contract_models = list(contract_root.rglob("model-contract-manifest.json"))
    if len(contract_evidence) != 1 or len(contract_models) != 1:
        raise PalladioAlignedError("accepted M9C contract manifests are not unique")
    m9c_lock = config.artifact_locks["m9c_contract"]
    expected_contract = _object(config.raw["evidence"]["m9c_contract"], "M9C contract lock")
    if file_sha256(contract_evidence[0]) != expected_contract["evidence_manifest_sha256"]:
        raise PalladioAlignedError("accepted M9C evidence manifest differs")
    if file_sha256(contract_models[0]) != expected_contract["model_manifest_sha256"]:
        raise PalladioAlignedError("accepted M9C model manifest differs")
    if m9c_lock.run_id != 34026488176:
        raise PalladioAlignedError("M9C contract run identity differs")

    acceptance_candidates = list(Path(m9c_acceptance_root).rglob("acceptance-manifest.json"))
    if len(acceptance_candidates) != 1:
        raise PalladioAlignedError("accepted M9C acceptance manifest is not unique")
    acceptance_lock = config.artifact_locks["m9c_acceptance"]
    if acceptance_lock.manifest_sha256 and file_sha256(acceptance_candidates[0]) != acceptance_lock.manifest_sha256:
        raise PalladioAlignedError("accepted M9C acceptance manifest differs")
    accepted = _object(json.loads(acceptance_candidates[0].read_text(encoding="utf-8")), "M9C acceptance")
    if accepted.get("status") != "application_mapping_and_models_passed":
        raise PalladioAlignedError("M9C acceptance is not successful")

    repository_rows = _repository_lock_audit(config, Path(repository_root))
    manual_lock = _object(config.raw["evidence"].get("manual_actions_log"), "manual actions log")
    manual_relative = Path(_string(manual_lock.get("path"), "manual_actions_log.path"))
    if manual_relative.is_absolute() or ".." in manual_relative.parts:
        raise PalladioAlignedError("manual action log path must be repository-relative")
    manual_expected = _digest(manual_lock.get("initial_sha256"), "manual_actions_log.initial_sha256")
    manual_initial_size = _integer(
        manual_lock.get("initial_size_in_bytes"),
        "manual_actions_log.initial_size_in_bytes",
    )
    manual_path = Path(repository_root) / manual_relative
    manual_actual = file_sha256(manual_path) if manual_path.is_file() else ""
    manual_initial_actual = (
        _file_prefix_sha256(manual_path, manual_initial_size)
        if manual_path.is_file()
        else ""
    )
    manual_rows = _rows(manual_path) if manual_path.is_file() else []
    manual_statuses = Counter(row.get("status", "") for row in manual_rows)
    if set(manual_statuses) - {"planned", "completed"}:
        raise PalladioAlignedError("manual action log contains an invalid status")
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "repository-lock-audit.csv", ("path", "expected_sha256", "actual_sha256", "matches"), repository_rows)
    _write_csv(output / "analysis-lock-audit.csv", ("path", "expected_sha256", "actual_sha256", "matches"), analysis_rows)
    _write_csv(
        output / "preserved-file-audit.csv",
        ("evidence_group", "relative_path", "expected_size_in_bytes", "actual_size_in_bytes", "expected_sha256", "actual_sha256", "matches"),
        inventory_audit_rows,
    )
    quality = {
        "repository_lock_mismatches": sum(not row["matches"] for row in repository_rows),
        "manual_action_initial_lock_mismatches": int(
            manual_initial_actual != manual_expected
        ),
        "analysis_lock_mismatches": sum(not row["matches"] for row in analysis_rows),
        "qualified_cell_count_mismatches": int(_count_cell_manifests(Path(qualified_root)) != 160),
        "raw_sample_count_mismatches": int(_count_raw_samples(Path(raw_root)) != 4),
        "preserved_file_inventory_count_mismatches": int(len(expected_inventory) != 1538),
        "preserved_file_mismatches": sum(not row["matches"] for row in inventory_audit_rows),
        "m8a_quality_mismatches": 0,
        "m9c_acceptance_mismatches": 0,
    }
    if any(quality.values()):
        raise PalladioAlignedError(f"M9D evidence audit failed: {quality}")
    manifest = {
        "schema_version": 1,
        "kind": "m9d_aligned_evidence_contract",
        "config_sha256": file_sha256(Path(config_path)),
        "source_run_id": config.source_run_id,
        "quality": quality,
        "counts": {"qualified_cells": 160, "raw_samples": 4, "preserved_files": len(inventory_audit_rows)},
        "accepted_m8a_manifest_sha256": file_sha256(audit_manifest_path),
        "accepted_m9c_evidence_manifest_sha256": file_sha256(contract_evidence[0]),
        "accepted_m9c_model_manifest_sha256": file_sha256(contract_models[0]),
        "accepted_m9c_acceptance_manifest_sha256": file_sha256(acceptance_candidates[0]),
        "manual_actions_initial_sha256": manual_initial_actual,
        "manual_actions_current_sha256": manual_actual,
        "manual_actions_current_size_in_bytes": (
            manual_path.stat().st_size if manual_path.is_file() else 0
        ),
        "manual_action_rows": len(manual_rows),
        "manual_action_status_counts": dict(sorted(manual_statuses.items())),
        "optimizer_realization_is_not_causal_parameter_identification": True,
        "replay_runtime": replay_runtime,
        "environment": environment_manifest(),
    }
    _write_json(output / "evidence-manifest.json", manifest)
    return manifest


def _row_identity(row: Mapping[str, Any], *, include_method: bool = False) -> tuple[Any, ...]:
    identity: tuple[Any, ...] = (
        str(row["profile"]),
        str(row["failure_law"]),
        int(row["repetition"]),
        str(row["scope"]),
        str(row["source_placement"]),
        str(row["target_placement"]),
        str(row["operation"]),
    )
    return (*identity, str(row["method"])) if include_method else identity


def _score_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (*_row_identity(row), str(row["view"]), str(row["method"]))


def _score(
    base: Mapping[str, Any], method: str, prediction: float, requests: int, successes: int,
    lower: float, upper: float,
) -> dict[str, Any]:
    rate = successes / requests
    brier = (successes * (prediction - 1.0) ** 2 + (requests - successes) * prediction**2) / requests
    return {
        "profile": base["profile"],
        "failure_law": base["failure_law"],
        "repetition": int(base["repetition"]),
        "mode": base["mode"],
        "scope": base["scope"],
        "source_placement": base["source_placement"],
        "target_placement": base["target_placement"],
        "method": method,
        "view": base["view"],
        "block_length_seconds": int(base["block_length_seconds"]),
        "operation": base["operation"],
        "prediction": prediction,
        "test_requests": requests,
        "test_successes": successes,
        "test_success_fraction": rate,
        "brier_score": brier,
        "signed_prediction_error": prediction - rate,
        "absolute_prediction_error": abs(prediction - rate),
        "test_block_mean_lower": lower,
        "test_block_mean_upper": upper,
        "prediction_in_test_block_interval": lower <= prediction <= upper,
    }


def _paired_interval(values_by_stratum: Mapping[tuple[Any, ...], list[float]], confidence: float) -> Mapping[str, Any]:
    represented = {key: values for key, values in values_by_stratum.items() if values}
    if not represented:
        return {"estimate": "", "standard_error": "", "degrees_of_freedom": "", "confidence_lower": "", "confidence_upper": ""}
    means = [fmean(values) for values in represented.values()]
    estimate = fmean(means)
    terms = [variance(values) / len(values) for values in represented.values() if len(values) > 1]
    if len(terms) != len(represented):
        return {"estimate": estimate, "standard_error": "", "degrees_of_freedom": "", "confidence_lower": "", "confidence_upper": ""}
    k = len(terms)
    se2 = sum(terms) / (k * k)
    se = math.sqrt(se2)
    denominator = sum((term / k**2) ** 2 / (len(values) - 1) for term, values in zip(terms, represented.values(), strict=True))
    df = se2**2 / denominator if denominator > 0.0 else math.inf
    critical = float(t.ppf((1.0 + confidence) / 2.0, df)) if math.isfinite(df) else 0.0
    return {
        "estimate": estimate,
        "standard_error": se,
        "degrees_of_freedom": df,
        "confidence_lower": estimate - critical * se,
        "confidence_upper": estimate + critical * se,
    }


def _contrast_rows(scores: Sequence[Mapping[str, Any]], config: PalladioAlignedConfig) -> list[dict[str, Any]]:
    analysis = _object(config.raw["analysis"], "analysis")
    lookup = {_score_key(row): row for row in scores}
    methods_by_identity: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for row in scores:
        methods_by_identity[(*_row_identity(row), str(row["view"]))].add(str(row["method"]))
    result = []
    for scope in ("current", "transfer"):
        intended_strata = int(analysis[f"{scope}_intended_strata"])
        for view in config.raw["design"]["accuracy_views"]:
            for first, second in analysis["pairwise_contrasts"]:
                paired = [
                    key for key, methods in methods_by_identity.items()
                    if key[3] == scope and key[-1] == view and first in methods and second in methods
                ]
                for metric in ("brier_score", "signed_prediction_error", "absolute_prediction_error"):
                    strata: dict[tuple[Any, ...], list[float]] = defaultdict(list)
                    for key in paired:
                        base_identity = key[:-1]
                        first_row = lookup[(*base_identity, view, first)]
                        second_row = lookup[(*base_identity, view, second)]
                        stratum = (
                            (key[0], key[5], key[1])
                            if scope == "current"
                            else (key[0], key[1])
                        )
                        strata[stratum].append(float(first_row[metric]) - float(second_row[metric]))
                    interval = _paired_interval(strata, float(analysis["confidence_level"]))
                    result.append(
                        {
                            "scope": scope,
                            "view": view,
                            "metric": metric,
                            "first_method": first,
                            "second_method": second,
                            "paired_campaigns": len(paired),
                            "represented_strata": len(strata),
                            "intended_strata": intended_strata,
                            "complete": len(strata) == intended_strata and all(len(values) == config.repetitions for values in strata.values()),
                            **interval,
                        }
                    )
    return result


def _transfer_change_rows(scores: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    lookup = {_score_key(row): row for row in scores}
    rows = []
    for row in scores:
        if row["scope"] != "transfer" or row["view"] not in {"all_sequence", "stable"}:
            continue
        current_key = (
            row["profile"], row["failure_law"], int(row["repetition"]), "current",
            "colocated", "colocated", row["operation"], row["view"], row["method"],
        )
        current = lookup.get(current_key)
        if current is None:
            continue
        predicted_change = float(row["prediction"]) - float(current["prediction"])
        observed_change = float(row["test_success_fraction"]) - float(current["test_success_fraction"])
        rows.append(
            {
                "profile": row["profile"], "failure_law": row["failure_law"], "repetition": row["repetition"],
                "view": row["view"], "method": row["method"], "operation": row["operation"],
                "predicted_split_minus_colocated": predicted_change,
                "observed_split_minus_colocated": observed_change,
                "transfer_change_error": predicted_change - observed_change,
            }
        )
    return rows


def _summary_rows(
    scores: Sequence[Mapping[str, Any]], config: PalladioAlignedConfig
) -> list[dict[str, Any]]:
    methods = tuple(
        dict.fromkeys(
            [
                *config.raw["design"]["accuracy_methods"],
                *config.raw["design"]["technical_reference_methods"],
            ]
        )
    )
    rows = []
    for scope in ("current", "transfer"):
        intended_strata = int(config.raw["analysis"][f"{scope}_intended_strata"])
        for view in config.raw["design"]["retained_score_views"]:
            for method in methods:
                selected = [
                    row
                    for row in scores
                    if row["scope"] == scope
                    and row["view"] == view
                    and row["method"] == method
                ]
                strata: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
                for row in selected:
                    key = (
                        (row["profile"], row["target_placement"], row["failure_law"])
                        if scope == "current"
                        else (row["profile"], row["failure_law"])
                    )
                    strata[key].append(row)
                if not strata:
                    raise PalladioAlignedError(
                        f"summary method has no rows: {scope}/{view}/{method}"
                    )

                def equal_stratum_mean(field: str) -> float:
                    return fmean(
                        fmean(float(row[field]) for row in values)
                        for values in strata.values()
                    )

                rows.append(
                    {
                        "scope": scope,
                        "view": view,
                        "method": method,
                        "campaigns": len(selected),
                        "represented_strata": len(strata),
                        "intended_strata": intended_strata,
                        "complete": len(strata) == intended_strata
                        and all(
                            len(values) == config.repetitions
                            for values in strata.values()
                        ),
                        "mean_brier_score": equal_stratum_mean("brier_score"),
                        "mean_signed_prediction_error": equal_stratum_mean(
                            "signed_prediction_error"
                        ),
                        "mean_absolute_prediction_error": equal_stratum_mean(
                            "absolute_prediction_error"
                        ),
                        "prediction_interval_compatibility_fraction": equal_stratum_mean(
                            "prediction_in_test_block_interval"
                        ),
                    }
                )
    return rows


def audit_palladio_aligned_results(
    config_path: str | Path,
    contract_root: str | Path,
    raw_result_path: str | Path,
    qualified_root: str | Path,
    analysis_root: str | Path,
    audit_root: str | Path,
    m8a_preserved_metadata_path: str | Path,
    m8a_audit_metadata_path: str | Path,
    output_root: str | Path,
) -> Mapping[str, Any]:
    """Audit solver fidelity, then independently score against sequestered outcomes."""

    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise PalladioAlignedError("full M9D result audit may run only in GitHub Actions")
    config = load_palladio_aligned_config(config_path)
    replay_runtime = _audit_replay_runtime(config)
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    _artifact_metadata(Path(m8a_preserved_metadata_path), config.artifact_locks["m8a_preserved_evidence"])
    _artifact_metadata(Path(m8a_audit_metadata_path), config.artifact_locks["m8a_integrity_audit"])
    audit_manifest_path, audit_manifest = _find_manifest(
        Path(audit_root), kind="m7_posthoc_integrity_and_arithmetic_diagnostic"
    )
    audit_lock = config.artifact_locks["m8a_integrity_audit"]
    if audit_lock.manifest_sha256 and file_sha256(audit_manifest_path) != audit_lock.manifest_sha256:
        raise PalladioAlignedError("downstream M8A audit manifest differs")
    if any(int(value) for value in _object(audit_manifest.get("quality"), "M8A quality").values()):
        raise PalladioAlignedError("downstream M8A audit has quality mismatches")
    analysis_dir = _analysis_directory(Path(analysis_root))
    downstream_source_rows = _audit_preserved_groups(
        Path(audit_root),
        {
            "analysis": Path(analysis_root),
            "qualified": Path(qualified_root),
        },
    )
    _write_csv(
        output / "downstream-source-audit.csv",
        (
            "evidence_group",
            "relative_path",
            "expected_size_in_bytes",
            "actual_size_in_bytes",
            "expected_sha256",
            "actual_sha256",
            "matches",
        ),
        downstream_source_rows,
    )
    downstream_source_mismatches = sum(
        not row["matches"] for row in downstream_source_rows
    )
    if len(downstream_source_rows) != 1446 or downstream_source_mismatches:
        raise PalladioAlignedError(
            "downstream preserved analysis/evaluator evidence differs: "
            f"files={len(downstream_source_rows)}, mismatches={downstream_source_mismatches}"
        )
    contract = Path(contract_root)
    evidence_manifests = list(contract.rglob("evidence-manifest.json"))
    model_manifests = list(contract.rglob("model-contract-manifest.json"))
    model_indexes = list(contract.rglob("model-index.csv"))
    model_file_indexes = list(contract.rglob("model-files.csv"))
    opportunity_ledgers = list(contract.rglob("opportunity-ledger.csv"))
    if not all(
        len(items) == 1
        for items in (
            evidence_manifests,
            model_manifests,
            model_indexes,
            model_file_indexes,
            opportunity_ledgers,
        )
    ):
        raise PalladioAlignedError("M9D contract files are not unique")
    evidence_manifest = _object(json.loads(evidence_manifests[0].read_text(encoding="utf-8")), "M9D evidence manifest")
    model_manifest = _object(json.loads(model_manifests[0].read_text(encoding="utf-8")), "M9D model manifest")
    if any(int(value) for value in _object(evidence_manifest["quality"], "evidence quality").values()):
        raise PalladioAlignedError("M9D evidence contract contains mismatches")
    config_digest = file_sha256(Path(config_path))
    if (
        evidence_manifest.get("kind") != "m9d_aligned_evidence_contract"
        or evidence_manifest.get("config_sha256") != config_digest
        or model_manifest.get("kind") != "m9d_aligned_model_contract"
        or model_manifest.get("config_sha256") != config_digest
        or model_manifest.get("evidence_manifest_sha256")
        != file_sha256(evidence_manifests[0])
    ):
        raise PalladioAlignedError("M9D contract provenance chain differs")
    if model_manifest.get("all_replayed_rows_match_frozen") is not True:
        raise PalladioAlignedError("M9D model contract did not reproduce frozen M7")
    models = _rows(model_indexes[0])
    model_lookup = {row["model_id"]: row for row in models}
    if len(models) != config.expected_models or len(model_lookup) != config.expected_models:
        raise PalladioAlignedError("M9D model index count differs")
    model_file_rows = _rows(model_file_indexes[0])
    models_root = model_indexes[0].parent / "models"
    model_file_mismatches = 0
    seen_model_files: set[str] = set()
    for row in model_file_rows:
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise PalladioAlignedError("M9D model-file path is unsafe")
        normalized = relative.as_posix()
        if normalized in seen_model_files:
            raise PalladioAlignedError("M9D model-file index contains duplicates")
        seen_model_files.add(normalized)
        path = models_root / relative
        matches = (
            path.is_file()
            and path.stat().st_size == int(row["bytes"])
            and file_sha256(path) == row["sha256"]
        )
        model_file_mismatches += int(not matches)
    actual_model_files = {
        path.relative_to(models_root).as_posix()
        for path in models_root.rglob("*")
        if path.is_file()
    }
    if (
        len(model_file_rows) != config.expected_models * len(_MODEL_FILES)
        or actual_model_files != seen_model_files
        or model_file_mismatches
    ):
        raise PalladioAlignedError("M9D generated model files differ from their contract")

    raw = _object(json.loads(Path(raw_result_path).read_text(encoding="utf-8")), "raw Palladio result")
    warmup = _object(raw.get("warmup"), "raw Palladio warmup")
    expected_warmup = sorted(model_lookup)[0]
    if (
        warmup.get("model_id") != expected_warmup
        or int(warmup.get("scenario_count", -1)) != 1
        or int(warmup.get("load_solve_elapsed_nanoseconds", 0)) <= 0
    ):
        raise PalladioAlignedError("Palladio warmup record differs from the frozen rule")
    raw_runs = raw.get("runs")
    if not isinstance(raw_runs, list) or len(raw_runs) != config.expected_raw_runs:
        raise PalladioAlignedError("raw Palladio result count differs")
    run_keys: set[tuple[str, int]] = set()
    result_rows = []
    maximum = {"solver_oracle": 0.0, "oracle_frozen_b3": 0.0, "solver_proposed": 0.0, "success_plus_failure": 0.0, "physical_mass": 0.0, "technical_repeat": 0.0}
    success_by_run: dict[tuple[str, int], float] = {}
    for raw_row in raw_runs:
        row = _object(raw_row, "raw run")
        model_id = str(row["model_id"])
        repetition = int(row["repetition"])
        model = model_lookup.get(model_id)
        if model is None or not 0 <= repetition < config.technical_repetitions or (model_id, repetition) in run_keys:
            raise PalladioAlignedError("raw run has invalid model/repetition identity")
        run_keys.add((model_id, repetition))
        success = float(row["success_probability"])
        failure = float(row["failure_probability_sum"])
        mass = float(row["physical_state_probability"])
        if (
            str(row.get("scenario_id")) != model["operation"]
            or any(not math.isfinite(value) for value in (success, failure, mass))
            or not 0.0 <= success <= 1.0
            or not 0.0 <= failure <= 1.0
        ):
            raise PalladioAlignedError(f"raw probability/scenario is invalid for {model_id}")
        oracle = float(model["independent_oracle"])
        b3 = float(model["b3_prediction"])
        proposed = float(model["proposed_prediction"]) if model["proposed_prediction"] else math.nan
        expected_states = int(model["expected_physical_states"])
        maximum["solver_oracle"] = max(maximum["solver_oracle"], abs(success - oracle))
        maximum["oracle_frozen_b3"] = max(maximum["oracle_frozen_b3"], abs(oracle - b3))
        if math.isfinite(proposed):
            maximum["solver_proposed"] = max(maximum["solver_proposed"], abs(success - proposed))
        maximum["success_plus_failure"] = max(maximum["success_plus_failure"], abs(success + failure - 1.0))
        maximum["physical_mass"] = max(maximum["physical_mass"], abs(mass - 1.0))
        success_by_run[(model_id, repetition)] = success
        if int(row["evaluated_physical_states"]) != expected_states or int(row["total_physical_states"]) != expected_states:
            raise PalladioAlignedError(f"physical state count differs for {model_id}")
        elapsed = int(row.get("load_solve_elapsed_nanoseconds", 0))
        if elapsed <= 0:
            raise PalladioAlignedError("raw measured solver timing is missing")
        result_rows.append(
            {**{key: model[key] for key in ("model_id", "profile", "failure_law", "repetition", "scope", "source_placement", "target_placement", "operation", "proposed_admissible", "independent_oracle", "expected_physical_states", "fit_status")},
             "solver_repetition": repetition, "success_probability": success, "failure_probability_sum": failure, "physical_state_probability": mass,
             "load_solve_elapsed_nanoseconds": elapsed}
        )
    for model_id in model_lookup:
        maximum["technical_repeat"] = max(
            maximum["technical_repeat"],
            abs(success_by_run[(model_id, 0)] - success_by_run[(model_id, 1)]),
        )
    if any(value > config.probability_tolerance for value in maximum.values()):
        raise PalladioAlignedError(f"Palladio technical acceptance failed: {maximum}")

    for name, expected_hash in config.raw["evidence"]["frozen_analysis"].items():
        if file_sha256(analysis_dir / name) != expected_hash:
            raise PalladioAlignedError(f"downstream frozen analysis file differs: {name}")
    frozen_scores = [
        row for row in _rows(analysis_dir / "scores.csv")
        if row["mode"] == config.observation_mode
        and row["operation"] == config.operations.get(row["profile"])
        and row["method"] in _METHODS
        and (row["scope"] == "current" or row["source_placement"] == "colocated")
    ]
    cells = discover_qualified_cells(Path(qualified_root))
    if len(cells) != 160:
        raise PalladioAlignedError(
            f"downstream qualified-cell inventory differs: {len(cells)}"
        )
    live_config = load_frozen_live_validation_config(
        _m7_config_path(config, config.path.parents[1])
    )
    counts = outcome_counts(
        cells, live_config.analysis.transition_guard_seconds_each_side
    )
    historical_labels = config.raw["design"]["historical_method_labels"]
    scores: list[dict[str, Any]] = []
    frozen_score_lookup: dict[tuple[Any, ...], Mapping[str, str]] = {}
    for frozen in frozen_scores:
        expected_block_seconds = (
            46 if frozen["view"] == "stable_block_sensitivity" else 23
        )
        if int(frozen["block_length_seconds"]) != expected_block_seconds:
            raise PalladioAlignedError("frozen score block-length view differs")
        key = (
            frozen["profile"], frozen["failure_law"], int(frozen["repetition"]), frozen["scope"], frozen["source_placement"],
            frozen["target_placement"], frozen["operation"], frozen["view"], frozen["method"],
        )
        frozen_score_lookup[key] = frozen
        outcome_key = (frozen["profile"], frozen["target_placement"], frozen["failure_law"], int(frozen["repetition"]), frozen["view"], frozen["operation"])
        requests, successes = counts[outcome_key]
        lower, upper = float(frozen["test_block_mean_lower"]), float(frozen["test_block_mean_upper"])
        scored = _score(frozen, historical_labels[frozen["method"]], float(frozen["prediction"]), requests, successes, lower, upper)
        for field in ("test_requests", "test_successes"):
            if int(scored[field]) != int(frozen[field]):
                raise PalladioAlignedError("frozen score outcome count did not reproduce")
        for field in ("test_success_fraction", "brier_score", "signed_prediction_error", "absolute_prediction_error"):
            if abs(float(scored[field]) - float(frozen[field])) > config.probability_tolerance:
                raise PalladioAlignedError(f"frozen score did not reproduce: {field}")
        scores.append(scored)
    expected_historical_score_rows = sum(
        int(config.expected_emitted[method]) for method in _METHODS
    ) * len(config.raw["design"]["retained_score_views"])
    if (
        len(frozen_scores) != expected_historical_score_rows
        or len(frozen_score_lookup) != expected_historical_score_rows
    ):
        raise PalladioAlignedError("selected frozen score inventory differs")

    solver_first = {row["model_id"]: float(row["success_probability"]) for row in result_rows if int(row["solver_repetition"]) == 0}
    for model in models:
        method_pairs = [("B3", "PCM-PAR/B3-parameters")]
        if str(model["proposed_admissible"]).lower() in {"true", "1"}:
            method_pairs.append(("proposed", "PCM-PAR/admissible"))
        for historical_method, pcm_method in method_pairs:
            for view in config.raw["design"]["retained_score_views"]:
                key = (
                    model["profile"], model["failure_law"], int(model["repetition"]), model["scope"], model["source_placement"],
                    model["target_placement"], model["operation"], view, historical_method,
                )
                frozen = frozen_score_lookup.get(key)
                if frozen is None:
                    raise PalladioAlignedError(f"PCM model has no frozen score target: {key}")
                outcome_key = (model["profile"], model["target_placement"], model["failure_law"], int(model["repetition"]), view, model["operation"])
                requests, successes = counts[outcome_key]
                scores.append(
                    _score(frozen, pcm_method, solver_first[model["model_id"]], requests, successes, float(frozen["test_block_mean_lower"]), float(frozen["test_block_mean_upper"]))
                )

    opportunity_rows = _rows(opportunity_ledgers[0])
    coverage_rows = []
    for scope in ("current", "transfer"):
        denominator = int(config.expected_opportunities[scope])
        for historical, label in (("B0", "B0"), ("B2", "B2"), ("proposed", "proposed-direct")):
            selected = [row for row in opportunity_rows if row["scope"] == scope and row["method"] == historical]
            emitted = sum(row["prediction"] != "" for row in selected)
            reasons = Counter(row["status"] for row in selected if row["prediction"] == "")
            coverage_rows.append({"scope": scope, "method": label, "opportunities": denominator, "emitted": emitted, "coverage": emitted / denominator, "missing_reasons": ";".join(f"{key}:{value}" for key, value in sorted(reasons.items()))})
        admitted = sum(str(row["proposed_admissible"]).lower() in {"true", "1"} and row["scope"] == scope for row in models)
        coverage_rows.append({"scope": scope, "method": "PCM-PAR/admissible", "opportunities": denominator, "emitted": admitted, "coverage": admitted / denominator, "missing_reasons": f"topology_ambiguous_target_fraction:{denominator-admitted}"})

    coverage_stratum_rows = []
    for expected in config.raw["design"]["expected_emitted_by_stratum"]:
        identity = (
            expected["application"],
            expected["scope"],
            expected["source_placement"],
            expected["target_placement"],
            expected["failure_law"],
        )
        for historical, label in (
            ("B0", "B0"),
            ("B2", "B2"),
            ("proposed", "proposed-direct"),
        ):
            selected = [
                row
                for row in opportunity_rows
                if (
                    row["profile"],
                    row["scope"],
                    row["source_placement"],
                    row["target_placement"],
                    row["failure_law"],
                )
                == identity
                and row["method"] == historical
            ]
            if len(selected) != 10:
                raise PalladioAlignedError(
                    f"historical stratum opportunity count differs: {identity}/{historical}"
                )
            emitted = sum(row["prediction"] != "" for row in selected)
            reasons = Counter(
                row["status"] for row in selected if row["prediction"] == ""
            )
            coverage_stratum_rows.append(
                {
                    "profile": identity[0],
                    "scope": identity[1],
                    "source_placement": identity[2],
                    "target_placement": identity[3],
                    "failure_law": identity[4],
                    "method": label,
                    "opportunities": len(selected),
                    "emitted": emitted,
                    "coverage": emitted / len(selected),
                    "missing_reasons": ";".join(
                        f"{key}:{value}" for key, value in sorted(reasons.items())
                    ),
                }
            )
            expected_emitted = 10 if historical == "B0" else int(expected["emitted"])
            if emitted != expected_emitted:
                raise PalladioAlignedError(
                    f"historical stratum coverage differs: {identity}/{historical}"
                )
        pcm_emitted = sum(
            str(row["proposed_admissible"]).lower() in {"true", "1"}
            and (
                row["profile"],
                row["scope"],
                row["source_placement"],
                row["target_placement"],
                row["failure_law"],
            )
            == identity
            for row in models
        )
        coverage_stratum_rows.append(
            {
                "profile": identity[0],
                "scope": identity[1],
                "source_placement": identity[2],
                "target_placement": identity[3],
                "failure_law": identity[4],
                "method": "PCM-PAR/admissible",
                "opportunities": 10,
                "emitted": pcm_emitted,
                "coverage": pcm_emitted / 10,
                "missing_reasons": (
                    f"topology_ambiguous_target_fraction:{10-pcm_emitted}"
                    if pcm_emitted < 10
                    else ""
                ),
            }
        )
        if pcm_emitted != int(expected["emitted"]):
            raise PalladioAlignedError(
                f"PCM stratum coverage differs: {identity}"
            )
    expected_scope_coverage = {
        ("current", "B0"): (160, 160),
        ("current", "B2"): (160, 119),
        ("current", "proposed-direct"): (160, 119),
        ("current", "PCM-PAR/admissible"): (160, 119),
        ("transfer", "B0"): (80, 80),
        ("transfer", "B2"): (80, 65),
        ("transfer", "proposed-direct"): (80, 65),
        ("transfer", "PCM-PAR/admissible"): (80, 65),
    }
    observed_scope_coverage = {
        (row["scope"], row["method"]): (
            int(row["opportunities"]),
            int(row["emitted"]),
        )
        for row in coverage_rows
    }
    if observed_scope_coverage != expected_scope_coverage:
        raise PalladioAlignedError("scope-level coverage differs")

    summaries = _summary_rows(scores, config)
    comparisons = _contrast_rows(scores, config)
    transfer_changes = _transfer_change_rows(scores)
    expected_score_rows = (
        sum(int(config.expected_emitted[method]) for method in _METHODS)
        + config.expected_models
        + int(config.expected_emitted["PCM-PAR/admissible"])
    ) * len(config.raw["design"]["retained_score_views"])
    if len(scores) != expected_score_rows:
        raise PalladioAlignedError(f"downstream score inventory differs: {len(scores)} != {expected_score_rows}")
    if (
        len(coverage_rows) != 8
        or len(coverage_stratum_rows) != 96
        or len(summaries) != 36
        or len(comparisons) != 84
    ):
        raise PalladioAlignedError("coverage/summary/comparison output inventory differs")
    if len(transfer_changes) != 810:
        raise PalladioAlignedError(
            f"transfer-change output inventory differs: {len(transfer_changes)}"
        )
    result_fields = ("model_id", "profile", "failure_law", "repetition", "scope", "source_placement", "target_placement", "operation", "proposed_admissible", "independent_oracle", "expected_physical_states", "fit_status", "solver_repetition", "success_probability", "failure_probability_sum", "physical_state_probability", "load_solve_elapsed_nanoseconds")
    score_fields = ("profile", "failure_law", "repetition", "mode", "scope", "source_placement", "target_placement", "method", "view", "block_length_seconds", "operation", "prediction", "test_requests", "test_successes", "test_success_fraction", "brier_score", "signed_prediction_error", "absolute_prediction_error", "test_block_mean_lower", "test_block_mean_upper", "prediction_in_test_block_interval")
    summary_fields = ("scope", "view", "method", "campaigns", "represented_strata", "intended_strata", "complete", "mean_brier_score", "mean_signed_prediction_error", "mean_absolute_prediction_error", "prediction_interval_compatibility_fraction")
    comparison_fields = ("scope", "view", "metric", "first_method", "second_method", "paired_campaigns", "represented_strata", "intended_strata", "complete", "estimate", "standard_error", "degrees_of_freedom", "confidence_lower", "confidence_upper")
    _write_csv(output / "solver-parity.csv", result_fields, result_rows)
    _write_csv(output / "scores.csv", score_fields, scores)
    _write_csv(output / "coverage.csv", ("scope", "method", "opportunities", "emitted", "coverage", "missing_reasons"), coverage_rows)
    _write_csv(output / "coverage-by-stratum.csv", ("profile", "scope", "source_placement", "target_placement", "failure_law", "method", "opportunities", "emitted", "coverage", "missing_reasons"), coverage_stratum_rows)
    _write_csv(output / "summaries.csv", summary_fields, summaries)
    _write_csv(output / "comparisons.csv", comparison_fields, comparisons)
    _write_csv(output / "transfer-change.csv", ("profile", "failure_law", "repetition", "view", "method", "operation", "predicted_split_minus_colocated", "observed_split_minus_colocated", "transfer_change_error"), transfer_changes)
    resource_files = []
    for root in (contract, Path(raw_result_path).parent):
        for path in root.rglob("*resource*usage*.txt"):
            resource_files.append({"path": str(path), "bytes": path.stat().st_size, "sha256": file_sha256(path)})
    elapsed_by_pass = {
        str(repetition): sum(int(row["load_solve_elapsed_nanoseconds"]) for row in result_rows if int(row["solver_repetition"]) == repetition)
        for repetition in range(config.technical_repetitions)
    }
    _write_json(
        output / "resource-inventory.json",
        {
            "files": resource_files,
            "warmup": dict(warmup),
            "measured_pass_elapsed_nanoseconds": elapsed_by_pass,
            "historical_B0_B2_separate_time": "not_separately_measured",
        },
    )
    manifest = {
        "schema_version": 1,
        "kind": "m9d_aligned_comparison_acceptance",
        "status": "technical_bridge_passed_accuracy_descriptive_only",
        "technical_accepted": True,
        "maximum_errors": maximum,
        "counts": {"raw_runs": len(result_rows), "scores": len(scores), "coverage_rows": len(coverage_rows), "coverage_stratum_rows": len(coverage_stratum_rows), "summaries": len(summaries), "comparisons": len(comparisons), "transfer_changes": len(transfer_changes), "downstream_source_files": len(downstream_source_rows)},
        "quality": {
            "downstream_source_mismatches": downstream_source_mismatches,
            "model_file_mismatches": model_file_mismatches,
        },
        "interpretation": {
            "pcm_is_independent_parameter_estimator": False,
            "pcm_proposed_equality_is_accuracy_evidence": False,
            "m7_interpretation_changed": False,
            "optimizer_realization_is_causal_parameter_identification": False,
        },
        "manual_actions_final_sha256": file_sha256(
            config.path.parents[1] / config.raw["evidence"]["manual_actions_log"]["path"]
        ),
        "files": {name: file_sha256(output / name) for name in ("solver-parity.csv", "scores.csv", "coverage.csv", "coverage-by-stratum.csv", "summaries.csv", "comparisons.csv", "transfer-change.csv", "resource-inventory.json", "downstream-source-audit.csv")},
        "replay_runtime": replay_runtime,
        "environment": environment_manifest(),
    }
    _write_json(output / "acceptance-manifest.json", manifest)
    return manifest


def _learner_identity(cell_root: Path) -> tuple[str, str, str, int]:
    manifest = _object(
        json.loads((cell_root / "learner" / "manifest.json").read_text(encoding="utf-8")),
        "learner manifest",
    )
    return (
        str(manifest["profile"]),
        str(manifest["placement"]),
        str(manifest["failure_law"]),
        int(manifest["repetition"]),
    )


def _forbidden_learner_paths(root: Path) -> list[str]:
    forbidden = []
    for path in root.rglob("*"):
        lowered = path.name.lower()
        if path.is_dir() and lowered == "evaluator":
            forbidden.append(path.relative_to(root).as_posix())
        elif path.is_file() and lowered in {"test-requests.csv", "test-health.csv"}:
            forbidden.append(path.relative_to(root).as_posix())
    return sorted(forbidden)


def stage_palladio_aligned_learner_input(
    config_path: str | Path,
    qualified_root: str | Path,
    output_root: str | Path,
) -> Mapping[str, Any]:
    """Copy only learner/audit evidence into a deterministic 160-cell tree."""

    config = load_palladio_aligned_config(config_path)
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    manifests = sorted(Path(qualified_root).rglob("learner/manifest.json"))
    identities: set[tuple[str, str, str, int]] = set()
    records = []
    for manifest in manifests:
        source_cell = manifest.parents[1]
        identity = _learner_identity(source_cell)
        if identity in identities:
            raise PalladioAlignedError(f"duplicate qualified identity: {identity}")
        identities.add(identity)
        profile, placement, law, repetition = identity
        destination = output / profile / placement / law / f"r{repetition}"
        if destination.exists():
            raise PalladioAlignedError(f"staged learner destination already exists: {destination}")
        if not (source_cell / "audit").is_dir():
            raise PalladioAlignedError(f"qualified cell has no audit directory: {identity}")
        shutil.copytree(source_cell / "learner", destination / "learner", copy_function=shutil.copy2)
        shutil.copytree(source_cell / "audit", destination / "audit", copy_function=shutil.copy2)
        records.append(
            {
                "profile": profile,
                "placement": placement,
                "failure_law": law,
                "repetition": repetition,
                "destination": destination.relative_to(output).as_posix(),
            }
        )
    expected = {
        (profile, placement, law, repetition)
        for profile in config.operations
        for placement in ("colocated", "split")
        for law in config.failure_laws
        for repetition in range(config.repetitions)
    }
    if identities != expected:
        raise PalladioAlignedError(
            f"staged learner identities differ: missing={len(expected-identities)}, extra={len(identities-expected)}"
        )
    forbidden = _forbidden_learner_paths(output)
    if forbidden:
        raise PalladioAlignedError(f"learner-only stage contains evaluator evidence: {forbidden[:5]}")
    file_rows = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        file_rows.append(
            {
                "path": path.relative_to(output).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    _write_csv(output / "stage-cells.csv", ("profile", "placement", "failure_law", "repetition", "destination"), records)
    _write_csv(output / "stage-files.csv", ("path", "bytes", "sha256"), file_rows)
    manifest = {
        "schema_version": 1,
        "kind": "m9d_learner_only_stage",
        "source_run_id": config.source_run_id,
        "cells": len(records),
        "files": len(file_rows),
        "forbidden_paths": forbidden,
        "contains_evaluator_data": False,
        "stage_cells_sha256": file_sha256(output / "stage-cells.csv"),
        "stage_files_sha256": file_sha256(output / "stage-files.csv"),
    }
    _write_json(output / "stage-manifest.json", manifest)
    return manifest


def _load_learner_only_cell(cell_root: Path) -> QualifiedCell:
    """Load only learner/audit files; no evaluator path is constructed or opened."""

    identity = _learner_identity(cell_root)
    learner_manifest = _object(
        json.loads((cell_root / "learner" / "manifest.json").read_text(encoding="utf-8")),
        "learner manifest",
    )
    deployment = _object(
        json.loads((cell_root / "learner" / "deployment.json").read_text(encoding="utf-8")),
        "learner deployment",
    )
    boundary = _object(
        json.loads((cell_root / "audit" / "boundary.json").read_text(encoding="utf-8")),
        "evidence boundary",
    )
    if boundary.get("usable") is not True:
        raise PalladioAlignedError(f"learner-only cell is not usable: {identity}")
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
            target_replicas=frozenset(filter(None, row["target_replicas"].split(";"))),
        )
        for row in _rows(cell_root / "learner" / "requests.csv")
    )
    if str(learner_manifest.get("profile")) != identity[0]:
        raise PalladioAlignedError("learner identity changed during loading")
    return QualifiedCell(
        profile=identity[0],
        placement=identity[1],
        failure_law=identity[2],
        repetition=identity[3],
        target_service=str(deployment["target_service"]),
        learner_requests=requests,
        health=_health_ticks(cell_root / "learner" / "health.csv"),
        test_requests=(),
        test_health=(),
        boundary=dict(boundary),
        directory=cell_root,
    )


def _discover_learner_only_cells(root: Path) -> list[QualifiedCell]:
    forbidden = _forbidden_learner_paths(root)
    if forbidden:
        raise PalladioAlignedError(f"learner input contains evaluator paths: {forbidden[:5]}")
    cells = [_load_learner_only_cell(path.parents[1]) for path in sorted(root.rglob("learner/manifest.json"))]
    identities = [cell.identity for cell in cells]
    if len(identities) != len(set(identities)):
        raise PalladioAlignedError("learner input contains duplicate identities")
    return sorted(cells, key=lambda cell: cell.identity)


def _prediction_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(row["profile"]),
        str(row["failure_law"]),
        int(row["repetition"]),
        str(row["mode"]),
        str(row["scope"]),
        str(row["source_placement"]),
        str(row["target_placement"]),
        str(row["method"]),
        str(row["operation"]),
    )


def _selected_prediction(row: Mapping[str, Any], config: PalladioAlignedConfig) -> bool:
    return (
        str(row.get("mode")) == config.observation_mode
        and str(row.get("operation")) == config.operations.get(str(row.get("profile")))
        and str(row.get("method")) in _METHODS
        and (
            str(row.get("scope")) == "current"
            or (
                str(row.get("scope")) == "transfer"
                and str(row.get("source_placement")) == "colocated"
            )
        )
    )


_REPLAY_NUMERIC_FIELDS = (
    "prediction",
    "route_prediction",
    "residual_success_probability",
    "fit_nll",
    "target_gradient_residual",
    "multistart_prediction_range",
)
_REPLAY_CATEGORICAL_FIELDS = (
    "requires_target_group",
    "status",
    "fit_status",
    "identification_rank",
    "identification_dimension",
)


def _compare_replay(
    replay: Mapping[str, Any], frozen: Mapping[str, Any], tolerance: float
) -> list[str]:
    mismatches = []
    for field in _REPLAY_CATEGORICAL_FIELDS:
        if str(replay.get(field, "")).lower() != str(frozen.get(field, "")).lower():
            mismatches.append(field)
    for field in _REPLAY_NUMERIC_FIELDS:
        left = replay.get(field, "")
        right = frozen.get(field, "")
        if left == "" or right == "":
            if left != "" or right != "":
                mismatches.append(field)
            continue
        if abs(float(left) - float(right)) > tolerance:
            mismatches.append(field)
    return mismatches


def _model_id(row: Mapping[str, Any]) -> str:
    return (
        f"{row['profile']}__{row['source_placement']}__{row['failure_law']}__"
        f"r{int(row['repetition']):02d}__{row['scope']}"
    )


def _canonical_witness(failure_law: str, best_parameters: Mapping[str, float], q: float) -> dict[str, float]:
    witness = {
        "residual_success": q,
        "common_domain_availability": float(best_parameters.get("g", 1.0)) if "D" in failure_law else 1.0,
        "individual_availability_a": float(best_parameters["ea"]),
        "individual_availability_b": float(best_parameters["eb"]),
        "communication_call_success_a": float(best_parameters.get("ca", 1.0)) if "C" in failure_law else 1.0,
        "communication_call_success_b": float(best_parameters.get("cb", 1.0)) if "C" in failure_law else 1.0,
    }
    if any(not math.isfinite(value) or not 0.0 < value <= 1.0 for value in witness.values()):
        raise PalladioAlignedError(f"optimizer realization contains an invalid probability: {witness}")
    return witness


def _oracle(witness: Mapping[str, float], placement: str) -> float:
    q = witness["residual_success"]
    g = witness["common_domain_availability"]
    ea = witness["individual_availability_a"]
    eb = witness["individual_availability_b"]
    ca = witness["communication_call_success_a"]
    cb = witness["communication_call_success_b"]
    if placement == "colocated":
        return q * g * (ea * ca + (1.0 - ea * ca) * eb * cb)
    if placement == "split":
        return q * (g * ea * ca + (1.0 - g * ea * ca) * g * eb * cb)
    raise PalladioAlignedError(f"unsupported target placement: {placement}")


def _state_count(witness: Mapping[str, float], placement: str) -> int:
    if placement == "colocated":
        availabilities = (
            witness["common_domain_availability"],
            witness["individual_availability_a"],
            witness["individual_availability_b"],
        )
    else:
        availabilities = (
            1.0,
            witness["common_domain_availability"] * witness["individual_availability_a"],
            witness["common_domain_availability"] * witness["individual_availability_b"],
        )
    return 2 ** sum(0.0 < value < 1.0 for value in availabilities)


def _m9c_config_path(config: PalladioAlignedConfig, repository_root: Path) -> Path:
    for raw in config.raw["evidence"]["repository_locks"]:
        if str(raw["path"]) == "configs/m9c_palladio_application_mapping.json":
            return repository_root / str(raw["path"])
    raise PalladioAlignedError("M9C configuration repository lock is missing")


def _m7_config_path(config: PalladioAlignedConfig, repository_root: Path) -> Path:
    for raw in config.raw["evidence"]["repository_locks"]:
        if str(raw["path"]) == "configs/m7_frozen_live.yaml":
            return repository_root / str(raw["path"])
    raise PalladioAlignedError("M7 configuration repository lock is missing")


def _fake_mapping_config(
    base: PalladioMappingConfig,
    model: ApplicationModel,
    witness: Mapping[str, float],
    config_path: Path,
) -> PalladioMappingConfig:
    return PalladioMappingConfig(
        path=config_path,
        raw=base.raw,
        id="m9d-aligned-model",
        analyzer_commit=base.analyzer_commit,
        pcm_commit=base.pcm_commit,
        repeat_runs=2,
        probability_tolerance=base.probability_tolerance,
        job_timeout_minutes=360,
        applications=base.applications,
        models=(model,),
        witness=dict(witness),
    )


def prepare_palladio_aligned_models(
    config_path: str | Path,
    learner_root: str | Path,
    analysis_root: str | Path,
    evidence_manifest_path: str | Path,
    models_root: str | Path,
    output_root: str | Path,
) -> Mapping[str, Any]:
    """Replay fixed sampled_mixed fits and generate the admitted application PCMs."""

    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise PalladioAlignedError("full M9D fit replay and model generation may run only in GitHub Actions")
    config = load_palladio_aligned_config(config_path)
    replay_runtime = _audit_replay_runtime(config)
    repository_root = config.path.parents[1]
    evidence_manifest = _object(
        json.loads(Path(evidence_manifest_path).read_text(encoding="utf-8")), "M9D evidence manifest"
    )
    if (
        evidence_manifest.get("kind") != "m9d_aligned_evidence_contract"
        or evidence_manifest.get("config_sha256") != file_sha256(Path(config_path))
        or int(evidence_manifest.get("source_run_id", -1)) != config.source_run_id
        or any(
            int(value)
            for value in _object(
                evidence_manifest.get("quality"), "evidence quality"
            ).values()
        )
    ):
        raise PalladioAlignedError("M9D evidence contract is not accepted")
    cells = _discover_learner_only_cells(Path(learner_root))
    if len(cells) != 160:
        raise PalladioAlignedError(f"expected 160 learner-only cells, found {len(cells)}")
    live_config = load_frozen_live_validation_config(_m7_config_path(config, repository_root))
    mode = next((item for item in live_config.analysis.modes if item.id == config.observation_mode), None)
    if mode is None:
        raise PalladioAlignedError("sampled_mixed is absent from the frozen M7 configuration")
    base_pcm = load_palladio_mapping_config(_m9c_config_path(config, repository_root))
    if (
        base_pcm.analyzer_commit != config.analyzer_commit
        or base_pcm.pcm_commit != config.pcm_commit
    ):
        raise PalladioAlignedError("accepted M9C runtime commits differ from M9D")
    output = Path(output_root)
    models = Path(models_root)
    output.mkdir(parents=True, exist_ok=True)
    models.mkdir(parents=True, exist_ok=True)
    opportunity_rows: list[dict[str, Any]] = []
    fit_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    xmi_audits: list[Mapping[str, Any]] = []
    fit_statuses: Counter[str] = Counter()

    fit_replays = []
    for cell in cells:
        preparation_started = time.perf_counter_ns()
        prepared = prepare_mode(cell, mode, live_config.analysis)
        preparation_elapsed = time.perf_counter_ns() - preparation_started
        fit_started = time.perf_counter_ns()
        fit = fit_exact_model(cell, prepared, live_config.analysis)
        fit_elapsed = time.perf_counter_ns() - fit_started
        fit_operations = [
            spec.id
            for spec in prepared.operations
            if prepared.topology[spec.id].status == "confirmed"
            and prepared.topology[spec.id].inferred_requires_target is True
        ]
        fit_rows.append(
            {
                "profile": cell.profile,
                "source_placement": cell.placement,
                "failure_law": cell.failure_law,
                "repetition": cell.repetition,
                "fit_status": fit.status,
                "fit_parameter_names": ";".join(fit.parameter_names),
                "fit_operations": ";".join(fit_operations),
                "fit_nll": fit.best.nll if fit.best is not None else "",
                "mode_preparation_elapsed_nanoseconds": preparation_elapsed,
                "likelihood_fit_elapsed_nanoseconds": fit_elapsed,
                "optimizer_realization_not_causal_identification": True,
            }
        )
        scopes = ("current", "transfer") if cell.placement == "colocated" else ("current",)
        replay_by_scope = {
            scope: predict_cell(cell, prepared, fit, live_config.analysis, scope)
            for scope in scopes
        }
        fit_replays.append((cell, fit, fit_operations, replay_by_scope))

    analysis_directory = Path(analysis_root)
    visible_analysis_files = {
        path.relative_to(analysis_directory).as_posix()
        for path in analysis_directory.rglob("*")
        if path.is_file()
    }
    if visible_analysis_files != {"manifest.json", "predictions.csv"}:
        raise PalladioAlignedError(
            "fit replay may receive only the frozen prediction manifest and table"
        )
    analysis_dir = _analysis_directory(analysis_directory)
    frozen_rows = [
        row
        for row in _rows(analysis_dir / "predictions.csv")
        if _selected_prediction(row, config)
    ]
    frozen_lookup = {_prediction_key(row): row for row in frozen_rows}
    if len(frozen_rows) != 960 or len(frozen_lookup) != 960:
        raise PalladioAlignedError(
            "frozen selected prediction inventory must contain 240 x 4 rows"
        )

    for cell, fit, fit_operations, replay_by_scope in fit_replays:
        scopes = tuple(replay_by_scope)
        for scope in scopes:
            selected_operation = config.operations[cell.profile]
            selected_rows = [row for row in replay_by_scope[scope] if row["operation"] == selected_operation and row["method"] in _METHODS]
            if len(selected_rows) != 4:
                raise PalladioAlignedError(f"replay did not produce four methods for {cell.identity}/{scope}")
            rows_by_method = {str(row["method"]): row for row in selected_rows}
            for method in _METHODS:
                row = rows_by_method[method]
                key = _prediction_key(row)
                frozen = frozen_lookup.get(key)
                if frozen is None:
                    raise PalladioAlignedError(f"replay row has no frozen match: {key}")
                mismatches = _compare_replay(row, frozen, config.probability_tolerance)
                opportunity_rows.append(
                    {
                        **{name: row[name] for name in ("profile", "failure_law", "repetition", "mode", "scope", "source_placement", "target_placement", "method", "operation")},
                        "prediction": row["prediction"],
                        "route_prediction": row["route_prediction"],
                        "residual_success_probability": row["residual_success_probability"],
                        "status": row["status"],
                        "fit_status": row["fit_status"],
                        "frozen_prediction": frozen["prediction"],
                        "replay_mismatch_fields": ";".join(mismatches),
                        "replay_matches": not mismatches,
                    }
                )
                if mismatches:
                    raise PalladioAlignedError(f"replayed M7 row differs from frozen row {key}: {mismatches}")

            b3 = rows_by_method["B3"]
            proposed = rows_by_method["proposed"]
            if b3["prediction"] == "":
                continue
            if fit.best is None:
                raise PalladioAlignedError("B3 emitted without a fitted optimizer realization")
            mapping_started = time.perf_counter_ns()
            witness = _canonical_witness(cell.failure_law, fit.best.parameters, float(b3["residual_success_probability"]))
            target_placement = str(b3["target_placement"])
            oracle = _oracle(witness, target_placement)
            if abs(oracle - float(b3["prediction"])) > config.probability_tolerance:
                raise PalladioAlignedError("optimizer realization oracle differs from replayed B3")
            model_id = _model_id(b3)
            expected_states = _state_count(witness, target_placement)
            model = ApplicationModel(
                id=model_id,
                application=cell.profile,
                operation=selected_operation,
                placement=target_placement,
                expected_physical_states=expected_states,
                expected_success_probability=oracle,
            )
            fake = _fake_mapping_config(base_pcm, model, witness, config.path)
            mapping_elapsed = time.perf_counter_ns() - mapping_started
            model_root = models / model_id
            if model_root.exists():
                raise PalladioAlignedError(f"duplicate generated model id: {model_id}")
            model_root.mkdir(parents=True)
            serialization_started = time.perf_counter_ns()
            for filename, payload in _model_payloads(fake, model).items():
                path = model_root / filename
                path.write_text(payload, encoding="utf-8")
                file_rows.append(
                    {"model_id": model_id, "path": f"{model_id}/{filename}", "bytes": path.stat().st_size, "sha256": file_sha256(path)}
                )
            serialization_elapsed = time.perf_counter_ns() - serialization_started
            audit_started = time.perf_counter_ns()
            xmi_audits.append(_audit_one_application_model(fake, model, model_root))
            audit_elapsed = time.perf_counter_ns() - audit_started
            fit_statuses[fit.status] += 1
            model_rows.append(
                {
                    "model_id": model_id,
                    "profile": cell.profile,
                    "failure_law": cell.failure_law,
                    "repetition": cell.repetition,
                    "scope": scope,
                    "source_placement": cell.placement,
                    "target_placement": target_placement,
                    "operation": selected_operation,
                    "b3_prediction": b3["prediction"],
                    "proposed_prediction": proposed["prediction"],
                    "proposed_admissible": proposed["prediction"] != "",
                    "independent_oracle": oracle,
                    "expected_physical_states": expected_states,
                    "fit_status": fit.status,
                    "fit_parameter_names": ";".join(fit.parameter_names),
                    "fit_operations": ";".join(fit_operations),
                    "g": witness["common_domain_availability"],
                    "ea": witness["individual_availability_a"],
                    "eb": witness["individual_availability_b"],
                    "ca": witness["communication_call_success_a"],
                    "cb": witness["communication_call_success_b"],
                    "q": witness["residual_success"],
                    "automatic_parameter_mapping_elapsed_nanoseconds": mapping_elapsed,
                    "automatic_colocated_to_split_transformation_elapsed_nanoseconds": (
                        mapping_elapsed if scope == "transfer" else ""
                    ),
                    "parameter_only_serialization_elapsed_nanoseconds": serialization_elapsed,
                    "xmi_audit_elapsed_nanoseconds": audit_elapsed,
                    "automatically_written_parameter_fields": 9,
                    "template_files_manually_changed": 0,
                    "manual_interventions": 0,
                    "optimizer_realization_not_causal_identification": True,
                }
            )

    emitted_counts = Counter(
        str(row["method"])
        for row in opportunity_rows
        if row["prediction"] != ""
    )
    for method in _METHODS:
        if emitted_counts[method] != int(config.expected_emitted[method]):
            raise PalladioAlignedError(f"{method} replay coverage differs: {emitted_counts[method]}")
    if len(opportunity_rows) != 960 or len(model_rows) != config.expected_models:
        raise PalladioAlignedError("M9D opportunity/model inventory differs")
    if dict(fit_statuses) != dict(config.expected_fit_statuses):
        raise PalladioAlignedError(f"admitted fit-status inventory differs: {dict(fit_statuses)}")
    state_counts = Counter(int(row["expected_physical_states"]) for row in model_rows)
    if dict(state_counts) != dict(config.expected_state_models):
        raise PalladioAlignedError(f"model physical-state inventory differs: {dict(state_counts)}")
    admissible_count = sum(bool(row["proposed_admissible"]) for row in model_rows)
    if admissible_count != int(config.expected_emitted["PCM-PAR/admissible"]):
        raise PalladioAlignedError("PCM admissible-support inventory differs")
    missing = [
        row for row in opportunity_rows
        if row["method"] in {"B2", "B3", "proposed"} and row["prediction"] == ""
    ]
    if any(row["status"] != config.raw["design"]["expected_missing_reason"] for row in missing):
        raise PalladioAlignedError("unexpected replay missing-reason category")
    observed_strata = Counter(
        (row["profile"], row["scope"], row["source_placement"], row["target_placement"], row["failure_law"])
        for row in model_rows
    )
    expected_strata = {
        (row["application"], row["scope"], row["source_placement"], row["target_placement"], row["failure_law"]): int(row["emitted"])
        for row in config.raw["design"]["expected_emitted_by_stratum"]
    }
    if dict(observed_strata) != expected_strata:
        raise PalladioAlignedError("admitted model stratum inventory differs")
    if any(
        int(row[field]) <= 0
        for row in fit_rows
        for field in (
            "mode_preparation_elapsed_nanoseconds",
            "likelihood_fit_elapsed_nanoseconds",
        )
    ):
        raise PalladioAlignedError("per-fit timing is missing")
    if any(
        int(row[field]) <= 0
        for row in model_rows
        for field in (
            "automatic_parameter_mapping_elapsed_nanoseconds",
            "parameter_only_serialization_elapsed_nanoseconds",
            "xmi_audit_elapsed_nanoseconds",
        )
    ):
        raise PalladioAlignedError("per-model update timing is missing")
    if any(
        int(row["automatically_written_parameter_fields"]) != 9
        or int(row["template_files_manually_changed"]) != 0
        or int(row["manual_interventions"]) != 0
        or (
            row["scope"] == "transfer"
            and int(
                row[
                    "automatic_colocated_to_split_transformation_elapsed_nanoseconds"
                ]
            )
            <= 0
        )
        or (
            row["scope"] != "transfer"
            and row[
                "automatic_colocated_to_split_transformation_elapsed_nanoseconds"
            ]
            != ""
        )
        for row in model_rows
    ):
        raise PalladioAlignedError("per-model reuse endpoint differs")

    opportunity_fields = (
        "profile", "failure_law", "repetition", "mode", "scope", "source_placement", "target_placement", "method", "operation",
        "prediction", "route_prediction", "residual_success_probability", "status", "fit_status", "frozen_prediction", "replay_mismatch_fields", "replay_matches",
    )
    fit_fields = (
        "profile", "source_placement", "failure_law", "repetition", "fit_status", "fit_parameter_names", "fit_operations", "fit_nll", "mode_preparation_elapsed_nanoseconds", "likelihood_fit_elapsed_nanoseconds", "optimizer_realization_not_causal_identification",
    )
    model_fields = (
        "model_id", "profile", "failure_law", "repetition", "scope", "source_placement", "target_placement", "operation", "b3_prediction", "proposed_prediction", "proposed_admissible", "independent_oracle", "expected_physical_states", "fit_status", "fit_parameter_names", "fit_operations", "g", "ea", "eb", "ca", "cb", "q", "automatic_parameter_mapping_elapsed_nanoseconds", "automatic_colocated_to_split_transformation_elapsed_nanoseconds", "parameter_only_serialization_elapsed_nanoseconds", "xmi_audit_elapsed_nanoseconds", "automatically_written_parameter_fields", "template_files_manually_changed", "manual_interventions", "optimizer_realization_not_causal_identification",
    )
    _write_csv(output / "opportunity-ledger.csv", opportunity_fields, opportunity_rows)
    _write_csv(output / "fit-replay.csv", fit_fields, fit_rows)
    _write_csv(output / "model-index.csv", model_fields, model_rows)
    _write_csv(output / "model-files.csv", ("model_id", "path", "bytes", "sha256"), file_rows)
    _write_json(output / "xmi-audit.json", {"models": xmi_audits})
    manifest = {
        "schema_version": 1,
        "kind": "m9d_aligned_model_contract",
        "config_sha256": file_sha256(Path(config_path)),
        "evidence_manifest_sha256": file_sha256(Path(evidence_manifest_path)),
        "unique_fit_replays": len(fit_rows),
        "transfer_fit_reuses": sum(cell.placement == "colocated" for cell in cells),
        "admitted_transfer_models": sum(row["scope"] == "transfer" for row in model_rows),
        "opportunity_rows": len(opportunity_rows),
        "model_count": len(model_rows),
        "model_file_count": len(file_rows),
        "fit_status_counts": dict(sorted(fit_statuses.items())),
        "physical_state_model_counts": {str(key): value for key, value in sorted(state_counts.items())},
        "timings_nanoseconds": {
            "mode_preparation": sum(
                int(row["mode_preparation_elapsed_nanoseconds"])
                for row in fit_rows
            ),
            "likelihood_fit": sum(
                int(row["likelihood_fit_elapsed_nanoseconds"])
                for row in fit_rows
            ),
            "automatic_parameter_mapping": sum(
                int(row["automatic_parameter_mapping_elapsed_nanoseconds"])
                for row in model_rows
            ),
            "parameter_only_serialization": sum(
                int(row["parameter_only_serialization_elapsed_nanoseconds"])
                for row in model_rows
            ),
            "xmi_audit": sum(
                int(row["xmi_audit_elapsed_nanoseconds"])
                for row in model_rows
            ),
        },
        "reuse_endpoints": {
            "template_files_manually_changed_per_cell": 0,
            "automatically_written_parameter_fields_per_model": 9,
            "manual_interventions_per_model": 0,
            "parameter_only_serialization_elapsed_nanoseconds": sum(
                int(row["parameter_only_serialization_elapsed_nanoseconds"])
                for row in model_rows
            ),
            "automatic_colocated_to_split_transformation_elapsed_nanoseconds": sum(
                int(row["automatic_colocated_to_split_transformation_elapsed_nanoseconds"])
                for row in model_rows
                if row["automatic_colocated_to_split_transformation_elapsed_nanoseconds"] != ""
            ),
            "initial_integration_accounted_separately_in_manual_actions_log": True,
        },
        "all_replayed_rows_match_frozen": True,
        "contains_evaluator_data": False,
        "optimizer_realization_is_not_causal_parameter_identification": True,
        "replay_runtime": replay_runtime,
        "files": {
            name: file_sha256(output / name)
            for name in ("opportunity-ledger.csv", "fit-replay.csv", "model-index.csv", "model-files.csv", "xmi-audit.json")
        },
        "environment": environment_manifest(),
    }
    if manifest["unique_fit_replays"] != 160 or manifest["transfer_fit_reuses"] != 80:
        raise PalladioAlignedError("fit replay/reuse counts differ")
    _write_json(output / "model-contract-manifest.json", manifest)
    return manifest
