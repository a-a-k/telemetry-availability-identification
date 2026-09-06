from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pmx_failure_semantics import (
    PMXFailureSemanticsError,
    _audit_artifact_metadata,
    _audit_file,
    _commit,
    _integer,
    _list,
    _load_json,
    _object,
    _positive,
    _relative,
    _sha256,
    _stdout_aggregates,
    _string,
    _write_csv,
    _write_json,
)
from .pmx_performability import file_sha256, summarize_pcm_results
from .provenance import environment_manifest


class PMXCarrierControlError(PMXFailureSemanticsError):
    pass


@dataclass(frozen=True)
class PMXCarrierControlConfig:
    path: Path
    raw: Mapping[str, Any]
    command: str
    startup_seconds: int
    timeout_seconds: int
    repeats: int
    job_timeout_minutes: int


def _tag_values(span: Mapping[str, Any], key: str) -> list[Any]:
    tags = _list(span.get("tags"), "span tags")
    return [
        _object(value, "span tag").get("value")
        for value in tags
        if isinstance(value, Mapping) and value.get("key") == key
    ]


def load_pmx_carrier_control_config(path: str | Path) -> PMXCarrierControlConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9J config"), "root")
    expected = {
        "schema_version": 1,
        "id": "m9j_pmx_source_implied_carrier_controls",
        "status": "frozen_before_first_m9j_remote_pmx_invocation",
        "mechanism_test_only": True,
        "accuracy_scoring": "forbidden",
        "m7_evidence_access": "forbidden",
        "new_live_collection": "forbidden",
    }
    for key, value in expected.items():
        if root.get(key) != value:
            raise PMXCarrierControlError(f"M9J {key} differs from frozen value")
    priority = _object(root.get("scientific_priority"), "scientific_priority")
    if dict(priority) != {
        "method": "PMX_performability_extension",
        "persists_if_application_cost_is_high": True,
        "tested_binary_represents_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "m7_interpretation_changes": False,
    }:
        raise PMXCarrierControlError("M9J scientific-priority guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    m9i = _object(evidence.get("m9i"), "evidence.m9i")
    if (
        m9i.get("run_id") != 34052517285
        or _commit(m9i.get("head_sha"), "m9i.head_sha")
        != "dac1921e86285f1b28db47c7fbc8c49834c69649"
        or m9i.get("conclusion") != "success"
        or m9i.get("decision_status")
        != "pmx_exact_failure_sources_and_collapse_boundary_recovered"
    ):
        raise PMXCarrierControlError("accepted M9I anchor differs")
    artifacts = _object(m9i.get("artifacts"), "m9i.artifacts")
    if set(artifacts) != {"source", "boundary", "decision"}:
        raise PMXCarrierControlError("all three M9I artifacts are required")
    for role, value in artifacts.items():
        record = _object(value, f"artifact.{role}")
        _positive(record.get("id"), f"artifact.{role}.id")
        _positive(record.get("size_in_bytes"), f"artifact.{role}.size")
        _sha256(record.get("sha256"), f"artifact.{role}.sha256")
        _relative(record.get("manifest_path"), f"artifact.{role}.manifest_path")
        _positive(record.get("manifest_bytes"), f"artifact.{role}.manifest_bytes")
        _sha256(record.get("manifest_sha256"), f"artifact.{role}.manifest_sha")

    demonstration = _object(evidence.get("demonstration"), "demonstration")
    if _commit(demonstration.get("commit"), "demonstration.commit") != (
        "9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2"
    ):
        raise PMXCarrierControlError("demonstration commit differs")
    files = _list(demonstration.get("files"), "demonstration.files")
    if {str(_object(value, "demonstration file").get("path")) for value in files} != {
        "Options.txt",
        "traces/jaegercustomers.json",
        "main.jar",
    }:
        raise PMXCarrierControlError("demonstration file set differs")
    for value in files:
        record = _object(value, "demonstration file")
        _relative(record.get("path"), "demonstration file.path")
        _positive(record.get("bytes"), "demonstration file.bytes")
        _sha256(record.get("sha256"), "demonstration file.sha256")

    source_checks = _list(root.get("source_checks"), "source_checks")
    if len(source_checks) != 5:
        raise PMXCarrierControlError("exactly five M9I source checks are required")
    if len({str(_object(value, "source check").get("id")) for value in source_checks}) != 5:
        raise PMXCarrierControlError("source-check IDs must be unique")
    for value in source_checks:
        check = _object(value, "source check")
        _relative(check.get("artifact_path"), "source check.artifact_path")
        _positive(check.get("bytes"), "source check.bytes")
        _sha256(check.get("sha256"), "source check.sha256")
        markers = _list(check.get("markers"), "source check.markers")
        if not markers or not all(isinstance(marker, str) and marker for marker in markers):
            raise PMXCarrierControlError("source-check markers differ")

    target = _object(root.get("target"), "target")
    expected_target = {
        "trace_id": "af0f0df51dfdfc3ca3e2eae9b00b114e",
        "spring_child_span_id": "b2adec3b558fff51",
        "surviving_carrier_span_id": "9e0a042aa79207bc",
        "process_id": "p2",
        "final_operation": "VisitResource.read",
        "child_original_operation": "VisitResource.read",
        "carrier_original_operation": "GET /pets/visits",
        "child_instrumentation_contains": "spring-webmvc",
        "carrier_instrumentation_contains": "tomcat",
        "relationship": "CHILD_OF_same_process",
        "original_error_tags": 0,
    }
    if dict(target) != expected_target:
        raise PMXCarrierControlError("source-derived carrier target differs")

    controls = _list(root.get("controls"), "controls")
    if [str(_object(value, "control").get("id")) for value in controls] != [
        "carrier_error_false",
        "carrier_error_true",
    ]:
        raise PMXCarrierControlError("matched carrier controls differ")
    expected_values = ["false", "true"]
    for index, value in enumerate(controls):
        control = _object(value, "control")
        _relative(control.get("output_trace_path"), "control.output_trace_path")
        if control.get("tag") != {
            "key": "error",
            "type": "bool",
            "value": expected_values[index],
        }:
            raise PMXCarrierControlError("carrier tag contract differs")
        if len(_list(control.get("expected_success_aggregates"), "success oracle")) != 5:
            raise PMXCarrierControlError("success aggregate oracle differs")
        if len(_list(control.get("expected_failure_aggregates"), "failure oracle")) != 5:
            raise PMXCarrierControlError("failure aggregate oracle differs")

    witness = _object(root.get("retained_witness"), "retained_witness")
    if (
        witness.get("condition") != "single_error_control"
        or witness.get("tag_location") != "spring_child_span_id"
        or witness.get("tag_value") != "true"
        or witness.get("repeats") != 2
        or witness.get("accuracy_evidence") is not False
    ):
        raise PMXCarrierControlError("retained merge-loss witness differs")

    execution = _object(root.get("execution"), "execution")
    command = _string(execution.get("command"), "execution.command")
    startup = _positive(
        execution.get("startup_stabilization_seconds"), "startup stabilization"
    )
    timeout = _positive(execution.get("internal_timeout_seconds"), "internal timeout")
    repeats = _positive(execution.get("confirmation_repeats"), "repeats")
    if (
        command != "main:main -of Options.txt"
        or startup != 20
        or timeout != 180
        or repeats != 2
        or execution.get("java_distribution") != "temurin"
        or execution.get("java_version") != "11"
        or execution.get("exit_command") != "exit 0"
        or execution.get("required_core_suffixes")
        != [".allocation", ".repository", ".resourceenvironment", ".system", ".usagemodel"]
        or execution.get("absolute_probability_tolerance") != 1e-12
        or len(_list(execution.get("required_log_markers"), "log markers")) != 6
    ):
        raise PMXCarrierControlError("M9J execution contract differs")

    oracle = _object(root.get("baseline_oracle"), "baseline_oracle")
    if (
        oracle.get("operation_order")
        != [
            "OwnerResource.findOwner",
            "VisitResource.read",
            "OwnerResource.createOwner",
            "PetResource.processCreationForm",
            "OwnerResource.findAll",
        ]
        or oracle.get("target_operation_index") != 1
        or oracle.get("surviving_target_executions") != 10
        or oracle.get("positive_failures") != 1
        or oracle.get("positive_successes") != 9
        or oracle.get("positive_probability") != 0.1
        or oracle.get("derived_before_remote_execution") is not True
    ):
        raise PMXCarrierControlError("independent carrier oracle differs")

    decision = _object(root.get("decision"), "decision")
    if (
        decision.get("both_conditions_pass")
        != "pmx_source_implied_carrier_failure_contract_reproduced"
        or decision.get("false_pass_true_fail")
        != "pmx_carrier_negative_pass_positive_unresolved"
        or decision.get("false_fail")
        != "pmx_carrier_pair_invalid_negative_control_failed"
        or decision.get("execution_integrity_fail")
        != "m9j_execution_or_evidence_integrity_failed"
        or decision.get("next_if_both_pass")
        != "m9k_single_operation_overestimation_localization"
        or decision.get("next_otherwise")
        != "m9k_single_operation_overestimation_localization"
    ):
        raise PMXCarrierControlError("M9J bounded decision routing differs")

    workflow = _object(root.get("workflow"), "workflow")
    if (
        workflow.get("jobs") != 3
        or workflow.get("job_timeout_minutes") != 360
        or workflow.get("dynamic_pmx_runs") != 4
        or workflow.get("heavy_runs_only_in_github_actions") is not True
        or workflow.get("artifact_retention_days") != 90
    ):
        raise PMXCarrierControlError("M9J workflow contract differs")
    guards = _object(root.get("interpretation_guardrails"), "guardrails")
    if any(value is not False for value in guards.values()):
        raise PMXCarrierControlError("all M9J interpretation guards must be false")

    return PMXCarrierControlConfig(
        path=config_path,
        raw=root,
        command=command,
        startup_seconds=startup,
        timeout_seconds=timeout,
        repeats=repeats,
        job_timeout_minutes=360,
    )


def validate_repository(config_path: str | Path) -> Mapping[str, Any]:
    config = load_pmx_carrier_control_config(config_path)
    root = config.path.resolve().parents[1]
    locks: list[dict[str, Any]] = []
    for value in _list(config.raw.get("repository_locks"), "repository_locks"):
        record = _object(value, "repository lock")
        relative = _relative(record.get("path"), "repository lock.path")
        locks.append(_audit_file(root / relative, record, str(relative)))
    manual = root / _relative(config.raw.get("manual_actions_log"), "manual log")
    if not manual.is_file() or manual.stat().st_size <= 100:
        raise PMXCarrierControlError("M9J manual-actions log is missing or empty")
    return {
        "schema_version": 1,
        "kind": "m9j_repository_validation",
        "status": "m9j_repository_contract_valid",
        "config_sha256": file_sha256(config.path),
        "repository_locks": locks,
        "manual_log": str(manual.relative_to(root)),
        "dynamic_pmx_runs": 4,
        "job_timeout_minutes": config.job_timeout_minutes,
    }


def _demonstration_record(config: PMXCarrierControlConfig, relative: str) -> Mapping[str, Any]:
    files = config.raw["evidence"]["demonstration"]["files"]
    for value in files:
        record = _object(value, "demonstration file")
        if record.get("path") == relative:
            return record
    raise PMXCarrierControlError(f"demonstration file is not frozen: {relative}")


def _audit_prior_artifacts(
    config: PMXCarrierControlConfig,
    metadata_paths: Mapping[str, Path],
    roots: Mapping[str, Path],
) -> tuple[dict[str, Any], dict[str, Any]]:
    m9i = _object(config.raw["evidence"]["m9i"], "m9i")
    artifacts = _object(m9i["artifacts"], "m9i.artifacts")
    metadata_audits: dict[str, Any] = {}
    manifest_audits: dict[str, Any] = {}
    for role in ("source", "boundary", "decision"):
        record = _object(artifacts[role], f"artifact.{role}")
        metadata_audits[role] = _audit_artifact_metadata(
            metadata_paths[role],
            record,
            role,
            int(m9i["run_id"]),
            str(m9i["head_sha"]),
        )
        manifest_audits[role] = _audit_file(
            roots[role] / _relative(record["manifest_path"], "manifest path"),
            {"bytes": record["manifest_bytes"], "sha256": record["manifest_sha256"]},
            f"M9I {role} manifest",
        )
    return metadata_audits, manifest_audits


def _find_target_spans(
    payload: Mapping[str, Any], target: Mapping[str, Any]
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    child: Mapping[str, Any] | None = None
    carrier: Mapping[str, Any] | None = None
    all_error_tags = 0
    for trace_value in _list(payload.get("data"), "trace data"):
        trace = _object(trace_value, "trace")
        for span_value in _list(trace.get("spans"), "trace spans"):
            span = _object(span_value, "span")
            all_error_tags += len(_tag_values(span, "error"))
            if trace.get("traceID") != target["trace_id"]:
                continue
            if span.get("spanID") == target["spring_child_span_id"]:
                if child is not None:
                    raise PMXCarrierControlError("target Spring child is duplicated")
                child = span
            if span.get("spanID") == target["surviving_carrier_span_id"]:
                if carrier is not None:
                    raise PMXCarrierControlError("target carrier is duplicated")
                carrier = span
    if child is None or carrier is None:
        raise PMXCarrierControlError("source-derived child/carrier target is missing")
    if all_error_tags != target["original_error_tags"]:
        raise PMXCarrierControlError("original demonstration error-tag count differs")
    if (
        child.get("processID") != target["process_id"]
        or carrier.get("processID") != target["process_id"]
        or child.get("operationName") != target["child_original_operation"]
        or carrier.get("operationName") != target["carrier_original_operation"]
    ):
        raise PMXCarrierControlError("source-derived child/carrier fields differ")
    references = _list(child.get("references"), "target child references")
    if not any(
        isinstance(value, Mapping)
        and value.get("refType") == "CHILD_OF"
        and value.get("spanID") == target["surviving_carrier_span_id"]
        for value in references
    ):
        raise PMXCarrierControlError("source-derived CHILD_OF relationship differs")
    child_libraries = [str(value) for value in _tag_values(child, "otel.library.name")]
    carrier_libraries = [str(value) for value in _tag_values(carrier, "otel.library.name")]
    if not any(target["child_instrumentation_contains"] in value for value in child_libraries):
        raise PMXCarrierControlError("target child instrumentation differs")
    if not any(target["carrier_instrumentation_contains"] in value for value in carrier_libraries):
        raise PMXCarrierControlError("target carrier instrumentation differs")
    return child, carrier


def build_control_contract(
    config_path: str | Path,
    source_metadata: Path,
    boundary_metadata: Path,
    decision_metadata: Path,
    source_root: Path,
    boundary_root: Path,
    decision_root: Path,
    demonstration_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_carrier_control_config(config_path)
    metadata_audits, manifest_audits = _audit_prior_artifacts(
        config,
        {"source": source_metadata, "boundary": boundary_metadata, "decision": decision_metadata},
        {"source": source_root, "boundary": boundary_root, "decision": decision_root},
    )
    source_manifest = _object(
        _load_json(source_root / "source-audit-manifest.json", "M9I source manifest"),
        "M9I source manifest",
    )
    boundary_manifest = _object(
        _load_json(boundary_root / "boundary-audit-manifest.json", "M9I boundary manifest"),
        "M9I boundary manifest",
    )
    decision_manifest = _object(
        _load_json(decision_root / "decision-manifest.json", "M9I decision manifest"),
        "M9I decision manifest",
    )
    if source_manifest.get("status") != "exact_embedded_failure_sources_recovered":
        raise PMXCarrierControlError("accepted M9I source status differs")
    if (
        boundary_manifest.get("status")
        != "exact_retained_failure_collapse_boundary_recovered"
        or boundary_manifest.get("earliest_observed_collapse")
        != "collapse_between_raw_tag_and_internal_operation_failure_aggregate"
        or boundary_manifest.get("raw_mutation_present") is not True
    ):
        raise PMXCarrierControlError("accepted M9I boundary status differs")
    if decision_manifest.get("status") != config.raw["evidence"]["m9i"]["decision_status"]:
        raise PMXCarrierControlError("accepted M9I decision status differs")

    source_rows: list[dict[str, Any]] = []
    for value in config.raw["source_checks"]:
        check = _object(value, "source check")
        path = source_root / _relative(check["artifact_path"], "source artifact path")
        audit = _audit_file(path, check, f"source check {check['id']}")
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in check["markers"] if marker not in text]
        if missing:
            raise PMXCarrierControlError(
                f"source markers differ for {check['id']}: {missing}"
            )
        source_rows.append(
            {
                "id": check["id"],
                "artifact_path": check["artifact_path"],
                "bytes": audit["bytes"],
                "sha256": audit["sha256"],
                "marker_count": len(check["markers"]),
                "matches": True,
            }
        )

    for relative in ("Options.txt", "traces/jaegercustomers.json"):
        _audit_file(
            demonstration_root / _relative(relative, "demonstration path"),
            _demonstration_record(config, relative),
            f"demonstration {relative}",
        )
    original_trace_path = demonstration_root / "traces" / "jaegercustomers.json"
    original_payload = _object(
        _load_json(original_trace_path, "published customer trace"), "trace root"
    )
    target = _object(config.raw["target"], "target")
    _find_target_spans(original_payload, target)

    options_path = demonstration_root / "Options.txt"
    options_text = options_path.read_text(encoding="utf-8")
    source_trace_relative = "traces/jaegercustomers.json"
    if options_text.count(source_trace_relative) != 1:
        raise PMXCarrierControlError("published options trace path is not unique")

    control_rows: list[dict[str, Any]] = []
    control_files: dict[str, dict[str, Any]] = {}
    for value in config.raw["controls"]:
        control = _object(value, "control")
        condition = str(control["id"])
        payload = copy.deepcopy(original_payload)
        _, carrier = _find_target_spans(payload, target)
        mutable_tags = carrier.get("tags")
        if not isinstance(mutable_tags, list):
            raise PMXCarrierControlError("carrier tags are not mutable JSON list data")
        mutable_tags.append(dict(_object(control["tag"], "control tag")))
        condition_root = out / "controls" / condition
        trace_relative = str(control["output_trace_path"])
        trace_path = condition_root / _relative(trace_relative, "control trace path")
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        control_options = options_text.replace(source_trace_relative, trace_relative)
        condition_root.mkdir(parents=True, exist_ok=True)
        (condition_root / "Options.txt").write_text(control_options, encoding="utf-8")
        observed_payload = _object(_load_json(trace_path, "generated control"), "control")
        _, observed_carrier = _find_target_spans(
            {
                **observed_payload,
                "data": copy.deepcopy(observed_payload["data"]),
            },
            {**target, "original_error_tags": 1},
        )
        if [
            value
            for value in _list(observed_carrier.get("tags"), "carrier tags")
            if isinstance(value, Mapping) and value.get("key") == "error"
        ] != [control["tag"]]:
            raise PMXCarrierControlError(f"generated carrier tag differs: {condition}")
        for path in (condition_root / "Options.txt", trace_path):
            relative_path = path.relative_to(out).as_posix()
            control_files[relative_path] = {
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        control_rows.append(
            {
                "condition": condition,
                "trace_path": trace_relative,
                "tag_key": control["tag"]["key"],
                "tag_type": control["tag"]["type"],
                "tag_value": control["tag"]["value"],
                "target_trace_id": target["trace_id"],
                "carrier_span_id": target["surviving_carrier_span_id"],
                "expected_success": "|".join(
                    map(str, control["expected_success_aggregates"])
                ),
                "expected_failure": "|".join(
                    "null" if item is None else str(item)
                    for item in control["expected_failure_aggregates"]
                ),
                "expected_probability": "|".join(
                    map(str, control["expected_nonzero_repository_probabilities"])
                ),
            }
        )

    _write_csv(
        out / "source-contract.csv",
        ["id", "artifact_path", "bytes", "sha256", "marker_count", "matches"],
        source_rows,
    )
    _write_csv(
        out / "control-contract.csv",
        [
            "condition",
            "trace_path",
            "tag_key",
            "tag_type",
            "tag_value",
            "target_trace_id",
            "carrier_span_id",
            "expected_success",
            "expected_failure",
            "expected_probability",
        ],
        control_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9j_source_implied_carrier_control_contract",
        "status": "source_implied_carrier_controls_generated",
        "config_sha256": file_sha256(config.path),
        "m9i_artifact_metadata": metadata_audits,
        "m9i_manifest_audits": manifest_audits,
        "source_checks_passed": len(source_rows),
        "controls_generated": len(control_rows),
        "target": dict(target),
        "baseline_oracle": dict(_object(config.raw["baseline_oracle"], "oracle")),
        "control_files": control_files,
        "dynamic_pmx_invocations": 0,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "files": {
            "source-contract.csv": file_sha256(out / "source-contract.csv"),
            "control-contract.csv": file_sha256(out / "control-contract.csv"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "control-contract-manifest.json", manifest)
    return manifest


def _log_sequence_complete(text: str, markers: Sequence[str]) -> bool:
    position = -1
    for marker in markers:
        next_position = text.find(marker, position + 1)
        if next_position < 0:
            return False
        position = next_position
    return True


def _nonfailure_projection(summary: Mapping[str, Any]) -> Mapping[str, Any]:
    token_counts = _object(summary.get("token_counts"), "summary token counts")
    tag_counts = _object(summary.get("tag_counts"), "summary tag counts")
    stable_tokens = {
        "resource_demanding_seff",
        "external_call_action",
        "entry_level_system_call",
        "allocation_context",
        "linking_resource",
        "mttf",
        "mttr",
    }
    return {
        "core_suffixes": summary.get("core_suffixes"),
        "parse_errors": summary.get("parse_errors"),
        "token_counts": {
            key: value for key, value in token_counts.items() if key in stable_tokens
        },
        "tag_counts": {
            key: value for key, value in tag_counts.items() if "failure" not in key.lower()
        },
    }


def record_probe(
    config_path: str | Path,
    contract_root: Path,
    execution_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_carrier_control_config(config_path)
    contract_path = contract_root / "control-contract-manifest.json"
    contract = _object(_load_json(contract_path, "M9J control contract"), "contract")
    if (
        contract.get("config_sha256") != file_sha256(config.path)
        or contract.get("status") != "source_implied_carrier_controls_generated"
        or contract.get("controls_generated") != 2
    ):
        raise PMXCarrierControlError("M9J control contract differs")
    for relative, value in _object(contract.get("control_files"), "control files").items():
        _audit_file(
            contract_root / _relative(relative, "control file path"),
            _object(value, "control file"),
            f"control file {relative}",
        )

    execution = _object(config.raw["execution"], "execution")
    markers = [str(value) for value in execution["required_log_markers"]]
    tolerance = float(execution["absolute_probability_tolerance"])
    run_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    summaries: dict[tuple[str, int], Mapping[str, Any]] = {}
    expected_by_condition = {
        str(_object(value, "control")["id"]): _object(value, "control")
        for value in config.raw["controls"]
    }

    for condition, control in expected_by_condition.items():
        for repeat in range(1, config.repeats + 1):
            run_root = execution_root / condition / f"repeat-{repeat}"
            required = [
                "Options.txt",
                "stdin.txt",
                "stdout.log",
                "resource-usage.txt",
                "exit-code.txt",
                "elapsed-seconds.txt",
                "started-at-utc.txt",
                "command-sent-at-utc.txt",
                "finished-at-utc.txt",
                "watchdog.log",
            ]
            for name in required:
                if not (run_root / name).is_file():
                    raise PMXCarrierControlError(
                        f"{condition}/{repeat}: missing retained file {name}"
                    )
            results_root = run_root / "results"
            if not results_root.is_dir():
                raise PMXCarrierControlError(f"{condition}/{repeat}: missing results")
            exit_code = int((run_root / "exit-code.txt").read_text().strip())
            elapsed = int((run_root / "elapsed-seconds.txt").read_text().strip())
            stdout_text = (run_root / "stdout.log").read_text(
                encoding="utf-8", errors="replace"
            )
            log_path = results_root / "log.txt"
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.is_file()
                else ""
            )
            summary = summarize_pcm_results(results_root)
            summaries[(condition, repeat)] = summary
            success, failures = _stdout_aggregates(run_root / "stdout.log")
            expected_probabilities = sorted(
                float(value)
                for value in control["expected_nonzero_repository_probabilities"]
            )
            observed_probabilities = sorted(
                float(value)
                for value in summary["nonzero_repository_failure_probabilities"]
            )
            probabilities_pass = len(expected_probabilities) == len(
                observed_probabilities
            ) and all(
                math.isclose(observed, expected, rel_tol=0.0, abs_tol=tolerance)
                for observed, expected in zip(observed_probabilities, expected_probabilities)
            )
            expected_signature = str(control["expected_semantic_signature"])
            signature_pass = (
                summary["semantic_signature"] == expected_signature
                if expected_signature != "different_from_historical"
                else summary["semantic_signature"]
                != "4e2f00daefd89ce4ccde30074cbf09deb65a2d44736d6ccf0cacace8f004f695"
            )
            internal_failures = int(
                summary["token_counts"]["internal_failure_occurrence"]
            )
            software_failures = int(
                summary["token_counts"]["software_induced_failure_type"]
            )
            expected_minimum = int(control["expected_internal_failure_minimum"])
            failure_elements_pass = (
                internal_failures == 0 and software_failures == 0
                if expected_minimum == 0
                else internal_failures >= expected_minimum
                and software_failures >= expected_minimum
            )
            technical_valid = (
                exit_code == 0
                and elapsed > config.startup_seconds
                and elapsed < config.timeout_seconds
                and "CommandNotFoundException" not in stdout_text
                and not summary["missing_core_suffixes"]
                and not summary["parse_errors"]
                and _log_sequence_complete(log_text, markers)
                and "MAJOR_ERROR" not in log_text
            )
            oracle_pass = (
                success == control["expected_success_aggregates"]
                and failures == control["expected_failure_aggregates"]
                and probabilities_pass
                and failure_elements_pass
                and signature_pass
            )
            run_pass = technical_valid and oracle_pass
            for path in sorted(path for path in run_root.rglob("*") if path.is_file()):
                file_rows.append(
                    {
                        "condition": condition,
                        "repeat": repeat,
                        "path": path.relative_to(execution_root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": file_sha256(path),
                    }
                )
            run_rows.append(
                {
                    "condition": condition,
                    "repeat": repeat,
                    "exit_code": exit_code,
                    "elapsed_seconds": elapsed,
                    "result_files": summary["result_files"],
                    "model_files": summary["model_files"],
                    "log_sequence_complete": _log_sequence_complete(log_text, markers),
                    "success_aggregates": "|".join(map(str, success)),
                    "failure_aggregates": "|".join(
                        "null" if value is None else value for value in failures
                    ),
                    "repository_probabilities": "|".join(
                        map(str, observed_probabilities)
                    ),
                    "internal_failure_occurrences": internal_failures,
                    "software_failure_types": software_failures,
                    "semantic_signature": summary["semantic_signature"],
                    "technical_valid": technical_valid,
                    "oracle_pass": oracle_pass,
                    "run_pass": run_pass,
                }
            )

    condition_passes: dict[str, bool] = {}
    repeat_consistency: dict[str, bool] = {}
    for condition in expected_by_condition:
        relevant = [row for row in run_rows if row["condition"] == condition]
        condition_passes[condition] = len(relevant) == config.repeats and all(
            bool(row["run_pass"]) for row in relevant
        )
        repeat_consistency[condition] = (
            len({str(row["semantic_signature"]) for row in relevant}) == 1
            and len({str(row["success_aggregates"]) for row in relevant}) == 1
            and len({str(row["failure_aggregates"]) for row in relevant}) == 1
            and len({str(row["repository_probabilities"]) for row in relevant}) == 1
        )
    all_technical = all(bool(row["technical_valid"]) for row in run_rows)
    projections = {
        json.dumps(_nonfailure_projection(summary), sort_keys=True)
        for summary in summaries.values()
    }
    nonfailure_structure_consistent = len(projections) == 1
    status = (
        "source_implied_carrier_contract_reproduced"
        if all(condition_passes.values())
        and all(repeat_consistency.values())
        and nonfailure_structure_consistent
        else "source_implied_carrier_contract_not_fully_reproduced"
    )
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "carrier-control-runs.csv",
        [
            "condition",
            "repeat",
            "exit_code",
            "elapsed_seconds",
            "result_files",
            "model_files",
            "log_sequence_complete",
            "success_aggregates",
            "failure_aggregates",
            "repository_probabilities",
            "internal_failure_occurrences",
            "software_failure_types",
            "semantic_signature",
            "technical_valid",
            "oracle_pass",
            "run_pass",
        ],
        run_rows,
    )
    _write_csv(
        out / "execution-files.csv",
        ["condition", "repeat", "path", "bytes", "sha256"],
        file_rows,
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9j_pmx_carrier_control_probe",
        "status": status,
        "config_sha256": file_sha256(config.path),
        "control_contract_sha256": file_sha256(contract_path),
        "run_count": len(run_rows),
        "expected_run_count": 4,
        "all_runs_technically_valid": all_technical,
        "condition_passes": condition_passes,
        "repeat_consistency": repeat_consistency,
        "nonfailure_structure_consistent": nonfailure_structure_consistent,
        "dynamic_pmx_invocations": len(run_rows),
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "files": {
            "carrier-control-runs.csv": file_sha256(out / "carrier-control-runs.csv"),
            "execution-files.csv": file_sha256(out / "execution-files.csv"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "carrier-probe-manifest.json", manifest)
    return manifest


def decide(
    config_path: str | Path,
    contract_manifest_path: Path,
    probe_manifest_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_carrier_control_config(config_path)
    contract = _object(_load_json(contract_manifest_path, "control contract"), "contract")
    probe = _object(_load_json(probe_manifest_path, "carrier probe"), "probe")
    config_hash = file_sha256(config.path)
    contract_pass = (
        contract.get("config_sha256") == config_hash
        and contract.get("status") == "source_implied_carrier_controls_generated"
        and contract.get("source_checks_passed") == 5
        and contract.get("controls_generated") == 2
        and contract.get("dynamic_pmx_invocations") == 0
    )
    technical_pass = (
        probe.get("config_sha256") == config_hash
        and probe.get("control_contract_sha256") == file_sha256(contract_manifest_path)
        and probe.get("run_count") == 4
        and probe.get("all_runs_technically_valid") is True
        and probe.get("dynamic_pmx_invocations") == 4
    )
    condition_passes = _object(probe.get("condition_passes"), "condition passes")
    false_pass = condition_passes.get("carrier_error_false") is True
    true_pass = condition_passes.get("carrier_error_true") is True
    consistency = _object(probe.get("repeat_consistency"), "repeat consistency")
    repeated = all(consistency.get(name) is True for name in condition_passes)
    structure = probe.get("nonfailure_structure_consistent") is True
    rules = _object(config.raw["decision"], "decision")
    if not contract_pass or not technical_pass:
        status = str(rules["execution_integrity_fail"])
        next_milestone = str(rules["next_otherwise"])
        accepted = False
    elif false_pass and true_pass and repeated and structure:
        status = str(rules["both_conditions_pass"])
        next_milestone = str(rules["next_if_both_pass"])
        accepted = True
    elif false_pass:
        status = str(rules["false_pass_true_fail"])
        next_milestone = str(rules["next_otherwise"])
        accepted = True
    else:
        status = str(rules["false_fail"])
        next_milestone = str(rules["next_otherwise"])
        accepted = True

    rows = [
        {
            "question": "source_and_control_contract_passed",
            "value": contract_pass,
            "interpretation": "exact M9I evidence and two frozen carrier inputs",
        },
        {
            "question": "all_four_runs_technically_valid",
            "value": technical_pass,
            "interpretation": "execution integrity is separate from mechanism oracle",
        },
        {
            "question": "carrier_false_zero_oracle_passed",
            "value": false_pass,
            "interpretation": "carrier placement alone does not create a failure",
        },
        {
            "question": "carrier_true_point_one_oracle_passed",
            "value": true_pass,
            "interpretation": "source-implied positive operation-failure path",
        },
        {
            "question": "repeat_and_nonfailure_structure_consistent",
            "value": repeated and structure,
            "interpretation": "only the predeclared reliability distinction may change",
        },
        {
            "question": "accuracy_scored",
            "value": False,
            "interpretation": "mechanism control only",
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
        "kind": "m9j_pmx_carrier_control_decision",
        "status": status,
        "config_sha256": config_hash,
        "control_contract_sha256": file_sha256(contract_manifest_path),
        "probe_manifest_sha256": file_sha256(probe_manifest_path),
        "technical_evidence_accepted": accepted,
        "source_contract_passed": contract_pass,
        "execution_integrity_passed": technical_pass,
        "carrier_false_oracle_passed": false_pass,
        "carrier_true_oracle_passed": true_pass,
        "repeat_consistency_passed": repeated,
        "nonfailure_structure_consistent": structure,
        "source_implied_failure_mechanism_reproduced": (
            contract_pass
            and technical_pass
            and false_pass
            and true_pass
            and repeated
            and structure
        ),
        "retained_child_error_witness_reclassified": False,
        "next_milestone": next_milestone,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "pmx_scientific_priority_retained": True,
        "tested_binary_represents_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "manual_pcm_credited_as_pmx": False,
        "m7_interpretation_changed": False,
        "files": {"decision-matrix.csv": file_sha256(out / "decision-matrix.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M9J PMX carrier controls")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--config", type=Path, required=True)

    contract = subparsers.add_parser("build-contract")
    contract.add_argument("--config", type=Path, required=True)
    contract.add_argument("--source-metadata", type=Path, required=True)
    contract.add_argument("--boundary-metadata", type=Path, required=True)
    contract.add_argument("--decision-metadata", type=Path, required=True)
    contract.add_argument("--source-root", type=Path, required=True)
    contract.add_argument("--boundary-root", type=Path, required=True)
    contract.add_argument("--decision-root", type=Path, required=True)
    contract.add_argument("--demonstration-root", type=Path, required=True)
    contract.add_argument("--out", type=Path, required=True)

    probe = subparsers.add_parser("record-probe")
    probe.add_argument("--config", type=Path, required=True)
    probe.add_argument("--contract-root", type=Path, required=True)
    probe.add_argument("--execution-root", type=Path, required=True)
    probe.add_argument("--out", type=Path, required=True)

    decision = subparsers.add_parser("decide")
    decision.add_argument("--config", type=Path, required=True)
    decision.add_argument("--contract-manifest", type=Path, required=True)
    decision.add_argument("--probe-manifest", type=Path, required=True)
    decision.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        payload = validate_repository(args.config)
    elif args.command == "build-contract":
        payload = build_control_contract(
            args.config,
            args.source_metadata,
            args.boundary_metadata,
            args.decision_metadata,
            args.source_root,
            args.boundary_root,
            args.decision_root,
            args.demonstration_root,
            args.out,
        )
    elif args.command == "record-probe":
        payload = record_probe(
            args.config, args.contract_root, args.execution_root, args.out
        )
    else:
        payload = decide(
            args.config, args.contract_manifest, args.probe_manifest, args.out
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
