from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .pmx_performability import _MODEL_SUFFIXES, file_sha256, summarize_pcm_results
from .provenance import environment_manifest


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class PMXEntrypointError(ValueError):
    pass


@dataclass(frozen=True)
class PMXEntrypointConfig:
    path: Path
    raw: Mapping[str, Any]
    command: str
    startup_seconds: int
    timeout_seconds: int
    confirmation_repeats: int
    job_timeout_minutes: int


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PMXEntrypointError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PMXEntrypointError(f"{label} must be a list")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PMXEntrypointError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PMXEntrypointError(f"{label} must be an integer")
    return value


def _positive(value: object, label: str) -> int:
    result = _integer(value, label)
    if result <= 0:
        raise PMXEntrypointError(f"{label} must be positive")
    return result


def _sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if not _SHA256_RE.fullmatch(result):
        raise PMXEntrypointError(f"{label} must be a lowercase SHA-256")
    return result


def _commit(value: object, label: str) -> str:
    result = _string(value, label)
    if not _COMMIT_RE.fullmatch(result):
        raise PMXEntrypointError(f"{label} must be a full lowercase commit")
    return result


def _relative(value: object, label: str) -> Path:
    path = Path(_string(value, label))
    if path.is_absolute() or ".." in path.parts:
        raise PMXEntrypointError(f"{label} must remain below its declared root")
    return path


def _load_json(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise PMXEntrypointError(f"cannot read {label}: {path}") from error


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(path: Path, fields: Sequence[str], rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _audit_file(path: Path, record: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PMXEntrypointError(f"{label} is missing: {path}")
    expected_bytes = _positive(record.get("bytes"), f"{label}.bytes")
    expected_sha = _sha256(record.get("sha256"), f"{label}.sha256")
    actual_bytes = path.stat().st_size
    actual_sha = file_sha256(path)
    if actual_bytes != expected_bytes or actual_sha != expected_sha:
        raise PMXEntrypointError(f"{label} byte identity differs")
    return {
        "path": str(path),
        "bytes": actual_bytes,
        "sha256": actual_sha,
        "matches": True,
    }


def load_pmx_entrypoint_config(path: str | Path) -> PMXEntrypointConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9H config"), "root")
    expected_scalars = {
        "schema_version": 1,
        "id": "m9h_pmx_source_declared_entrypoint",
        "status": "frozen_before_first_remote_entrypoint_invocation",
        "diagnostic_only": True,
        "accuracy_scoring": "forbidden",
        "m7_evidence_access": "forbidden",
        "new_live_collection": "forbidden",
    }
    for key, expected in expected_scalars.items():
        if root.get(key) != expected:
            raise PMXEntrypointError(f"M9H {key} differs from the frozen value")

    priority = _object(root.get("scientific_priority"), "scientific_priority")
    expected_priority = {
        "method": "PMX_performability_extension",
        "persists_if_application_cost_is_high": True,
        "m9g_negative_generalizes_to_source_declared_command": False,
        "tested_artifacts_represent_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "m7_interpretation_changes": False,
    }
    if dict(priority) != expected_priority:
        raise PMXEntrypointError("M9H scientific-priority guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    m9g = _object(evidence.get("m9g"), "evidence.m9g")
    if (
        m9g.get("run_id") != 34049195927
        or _commit(m9g.get("head_sha"), "m9g.head_sha")
        != "a69881a3fb6ab48b3ee0980d9c1470d260de3e5b"
        or m9g.get("conclusion") != "success"
        or m9g.get("decision_status")
        != "historical_output_recovered_launcher_unresolved"
        or m9g.get("next_milestone")
        != "m9h_pmx_source_entrypoint_recovery_and_manual_pcm_parallel"
    ):
        raise PMXEntrypointError("accepted M9G anchor differs")
    artifacts = _object(m9g.get("artifacts"), "m9g.artifacts")
    if set(artifacts) != {"recovery", "application", "decision"}:
        raise PMXEntrypointError("M9H requires exactly three M9G artifacts")
    for role, value in artifacts.items():
        record = _object(value, f"m9g.artifacts.{role}")
        _positive(record.get("id"), f"{role}.id")
        _positive(record.get("size_in_bytes"), f"{role}.size")
        _sha256(record.get("sha256"), f"{role}.sha256")
        _relative(record.get("manifest_path"), f"{role}.manifest_path")
        _positive(record.get("manifest_bytes"), f"{role}.manifest_bytes")
        _sha256(record.get("manifest_sha256"), f"{role}.manifest_sha256")
    recovery = _object(artifacts["recovery"], "recovery artifact")
    _relative(recovery.get("launcher_manifest_path"), "launcher manifest path")
    _positive(recovery.get("launcher_manifest_bytes"), "launcher manifest bytes")
    _sha256(recovery.get("launcher_manifest_sha256"), "launcher manifest sha")

    demo = _object(evidence.get("demonstration"), "demonstration")
    if _commit(demo.get("commit"), "demonstration.commit") != (
        "9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2"
    ):
        raise PMXEntrypointError("demonstration commit differs")
    jar = _object(demo.get("jar"), "demonstration.jar")
    if jar.get("bytes") != 65729095 or _sha256(
        jar.get("sha256"), "jar.sha256"
    ) != "befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013":
        raise PMXEntrypointError("PMX JAR lock differs")
    _sha256(demo.get("historical_semantic_signature"), "historical signature")
    control = _object(evidence.get("m9f_control"), "m9f_control")
    if control.get("expected_failure_probability") != 0.1:
        raise PMXEntrypointError("M9H control probability differs")
    if control.get("absolute_tolerance") != 1e-12:
        raise PMXEntrypointError("M9H control tolerance differs")

    source = _object(root.get("source_contract"), "source_contract")
    command = _string(source.get("gogo_command"), "source command")
    if (
        command != "main:main -of Options.txt"
        or source.get("scope") != "main"
        or source.get("function") != "main"
        or source.get("candidate_search_allowed") is not False
        or source.get("m9g_guessed_candidates_repeated") is not False
    ):
        raise PMXEntrypointError("exact source-declared command contract differs")
    required_markers = _list(source.get("required_markers"), "required_markers")
    if len(required_markers) != 5 or "System.exit(0)" not in required_markers:
        raise PMXEntrypointError("source evidence markers differ")

    execution = _object(root.get("execution"), "execution")
    startup = _positive(
        execution.get("startup_stabilization_seconds"), "startup stabilization"
    )
    timeout = _positive(execution.get("internal_timeout_seconds"), "timeout")
    repeats = _positive(execution.get("confirmation_repeats"), "repeats")
    if startup != 20 or timeout != 180 or repeats != 2:
        raise PMXEntrypointError("M9H execution bounds differ")
    if execution.get("stdin_lines") != [command, "exit 0"]:
        raise PMXEntrypointError("M9H stdin contract differs")
    if execution.get("screen_repeats") != 1:
        raise PMXEntrypointError("M9H must have one source-command screen")
    if set(execution.get("required_core_suffixes", [])) != _MODEL_SUFFIXES:
        raise PMXEntrypointError("M9H required PCM model types differ")
    if len(execution.get("required_log_markers", [])) != 6:
        raise PMXEntrypointError("M9H log sequence differs")

    manual_pcm = _object(root.get("manual_pcm_parallel"), "manual_pcm_parallel")
    if dict(manual_pcm) != {
        "status": "retained_as_separately_labelled_contingency",
        "credited_as_pmx_automation": False,
        "executed_or_scored_in_m9h": False,
        "reference": "docs/milestones/M9D_PALLADIO_ALIGNED_COMPARISON.md",
    }:
        raise PMXEntrypointError("manual PCM separation guard differs")

    runtime = _object(root.get("runtime"), "runtime")
    job_timeout = _positive(runtime.get("job_timeout_minutes"), "job timeout")
    if job_timeout != 360 or runtime.get("workflow_jobs") != 3:
        raise PMXEntrypointError("M9H requires exactly three 360-minute jobs")
    if runtime.get("remote_only_full_execution") is not True:
        raise PMXEntrypointError("full M9H execution must remain remote-only")

    repository_root = config_path.resolve().parents[1]
    for value in _list(root.get("repository_locks"), "repository_locks"):
        record = _object(value, "repository lock")
        target = repository_root / _relative(record.get("path"), "lock path")
        _audit_file(target, record, f"repository lock {target.name}")
    manual = _object(root.get("manual_actions_log"), "manual_actions_log")
    manual_path = repository_root / _relative(manual.get("path"), "manual log path")
    content = manual_path.read_bytes()
    prefix_bytes = _positive(manual.get("initial_size_in_bytes"), "manual prefix bytes")
    if len(content) < prefix_bytes:
        raise PMXEntrypointError("M9H manual log lost its frozen prefix")
    if hashlib.sha256(content[:prefix_bytes]).hexdigest() != _sha256(
        manual.get("initial_sha256"), "manual prefix sha256"
    ):
        raise PMXEntrypointError("M9H manual log frozen prefix differs")

    return PMXEntrypointConfig(
        path=config_path,
        raw=root,
        command=command,
        startup_seconds=startup,
        timeout_seconds=timeout,
        confirmation_repeats=repeats,
        job_timeout_minutes=job_timeout,
    )


def _audit_artifact_metadata(
    metadata_path: Path, record: Mapping[str, Any], role: str
) -> Mapping[str, Any]:
    metadata = _object(_load_json(metadata_path, f"{role} metadata"), "metadata")
    digest = str(metadata.get("digest", "")).removeprefix("sha256:")
    checks = {
        "id": metadata.get("id") == record.get("id"),
        "name": metadata.get("name") == record.get("name"),
        "size": metadata.get("size_in_bytes") == record.get("size_in_bytes"),
        "digest": digest == record.get("sha256"),
        "not_expired": metadata.get("expired") is False,
    }
    if not all(checks.values()):
        raise PMXEntrypointError(f"{role} M9G artifact metadata differs: {checks}")
    return {"checks": checks, "metadata": metadata}


def _manifest_record(record: Mapping[str, Any], prefix: str = "") -> Mapping[str, Any]:
    return {
        "bytes": record[f"{prefix}manifest_bytes"],
        "sha256": record[f"{prefix}manifest_sha256"],
    }


def audit_source_contract(
    config_path: Path,
    recovery_metadata: Path,
    application_metadata: Path,
    decision_metadata: Path,
    recovery_root: Path,
    application_root: Path,
    decision_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_entrypoint_config(config_path)
    artifacts = config.raw["evidence"]["m9g"]["artifacts"]
    metadata_audits = {
        "recovery": _audit_artifact_metadata(
            recovery_metadata, artifacts["recovery"], "recovery"
        ),
        "application": _audit_artifact_metadata(
            application_metadata, artifacts["application"], "application"
        ),
        "decision": _audit_artifact_metadata(
            decision_metadata, artifacts["decision"], "decision"
        ),
    }
    roots = {
        "recovery": recovery_root,
        "application": application_root,
        "decision": decision_root,
    }
    manifests: dict[str, Mapping[str, Any]] = {}
    manifest_audits: dict[str, Mapping[str, Any]] = {}
    for role in ("recovery", "application", "decision"):
        record = artifacts[role]
        path = roots[role] / _relative(record["manifest_path"], f"{role} manifest")
        manifest_audits[role] = _audit_file(
            path, _manifest_record(record), f"{role} manifest"
        )
        manifests[role] = _object(_load_json(path, f"{role} manifest"), role)

    recovery_record = artifacts["recovery"]
    launcher_path = recovery_root / _relative(
        recovery_record["launcher_manifest_path"], "launcher manifest"
    )
    launcher_audit = _audit_file(
        launcher_path,
        _manifest_record(recovery_record, "launcher_"),
        "M9G launcher manifest",
    )
    launcher = _object(_load_json(launcher_path, "M9G launcher manifest"), "launcher")

    expected_signature = config.raw["evidence"]["demonstration"][
        "historical_semantic_signature"
    ]
    if (
        manifests["recovery"].get("status")
        != "historical_output_and_launcher_contract_audited"
        or manifests["recovery"].get("historical_pcm_semantic_signature")
        != expected_signature
        or launcher.get("status") != "pmx_launcher_recovery_not_reproduced"
        or launcher.get("selection") is not None
        or manifests["application"].get("status")
        != "application_information_delta_audited"
        or manifests["decision"].get("status")
        != "historical_output_recovered_launcher_unresolved"
        or manifests["decision"].get("next_milestone")
        != "m9h_pmx_source_entrypoint_recovery_and_manual_pcm_parallel"
    ):
        raise PMXEntrypointError("accepted M9G decision chain differs")

    source = config.raw["source_contract"]
    descriptor_path = recovery_root / _relative(
        source["descriptor_path"], "descriptor path"
    )
    java_path = recovery_root / _relative(source["java_source_path"], "Java path")
    if file_sha256(descriptor_path) != source["descriptor_sha256"]:
        raise PMXEntrypointError("M9G descriptor evidence hash differs")
    if file_sha256(java_path) != source["java_source_sha256"]:
        raise PMXEntrypointError("M9G core source evidence hash differs")
    with descriptor_path.open(encoding="utf-8", newline="") as source_file:
        descriptor_rows = list(csv.DictReader(source_file))
    descriptor_text = "\n".join(str(row.get("text", "")) for row in descriptor_rows)
    java_text = java_path.read_text(encoding="utf-8")
    combined = descriptor_text + "\n" + java_text
    marker_rows = [
        {
            "marker": marker,
            "in_descriptor": marker in descriptor_text,
            "in_java_source": marker in java_text,
            "present": marker in combined,
        }
        for marker in source["required_markers"]
    ]
    if not all(row["present"] for row in marker_rows):
        raise PMXEntrypointError("source-declared entrypoint marker is absent")
    if not (
        "osgi.command.scope" in descriptor_text
        and 'value="main"' in descriptor_text
        and "osgi.command.function" in descriptor_text
        and descriptor_text.count('value="main"') >= 2
        and "osgi.command.scope=main" in java_text
        and "osgi.command.function=main" in java_text
    ):
        raise PMXEntrypointError("scope/function declarations do not independently agree")

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "source-command-evidence.csv",
        ("marker", "in_descriptor", "in_java_source", "present"),
        marker_rows,
    )
    manifest = {
        "schema_version": 1,
        "kind": "m9h_source_entrypoint_contract",
        "status": "exact_source_declared_command_audited",
        "config_sha256": file_sha256(config_path),
        "m9g_artifact_metadata": metadata_audits,
        "m9g_manifest_audits": manifest_audits,
        "m9g_launcher_manifest_audit": launcher_audit,
        "source_command": config.command,
        "scope_function_agree_in_descriptor_and_source": True,
        "candidate_search_allowed": False,
        "m9g_candidates_repeated": False,
        "manual_pcm_credited_as_pmx": False,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {
            "source-command-evidence.csv": file_sha256(
                out / "source-command-evidence.csv"
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "source-contract-manifest.json", manifest)
    return manifest


def _read_entrypoint_run(
    config: PMXEntrypointConfig, run_root: Path, label: str
) -> dict[str, Any]:
    required = (
        "exit-code.txt",
        "elapsed-seconds.txt",
        "started-at-utc.txt",
        "command-sent-at-utc.txt",
        "finished-at-utc.txt",
        "stdin.txt",
        "stdout.log",
        "resource-usage.txt",
    )
    missing = [name for name in required if not (run_root / name).is_file()]
    if missing or not (run_root / "results").is_dir():
        raise PMXEntrypointError(f"{label} lacks execution evidence: {missing}")
    try:
        exit_code = int((run_root / "exit-code.txt").read_text().strip())
        elapsed = int((run_root / "elapsed-seconds.txt").read_text().strip())
    except ValueError as error:
        raise PMXEntrypointError(f"{label} has invalid execution metadata") from error
    summary = dict(summarize_pcm_results(run_root / "results"))
    log_path = run_root / "results" / "log.txt"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    stdout_text = (run_root / "stdout.log").read_text(
        encoding="utf-8", errors="replace"
    )
    markers = config.raw["execution"]["required_log_markers"]
    marker_count = sum(marker in log_text for marker in markers)
    complete_models = not summary["missing_core_suffixes"] and not summary["parse_errors"]
    expected_signature = config.raw["evidence"]["demonstration"][
        "historical_semantic_signature"
    ]
    command_not_found = bool(
        re.search(r"Command not found:\s*main:main(?:\s|$)", stdout_text)
    )
    major_error = bool(re.search(r"major[_ ]error|MAJOR_ERROR", log_text + stdout_text, re.I))
    output_eligible = (
        complete_models
        and marker_count == len(markers)
        and not major_error
        and summary["semantic_signature"] == expected_signature
    )
    return {
        "label": label,
        "exit_code": exit_code,
        "timed_out": exit_code in {124, 137},
        "elapsed_seconds": elapsed,
        "started_at_utc": (run_root / "started-at-utc.txt").read_text().strip(),
        "command_sent_at_utc": (run_root / "command-sent-at-utc.txt").read_text().strip(),
        "finished_at_utc": (run_root / "finished-at-utc.txt").read_text().strip(),
        "stdin_sha256": file_sha256(run_root / "stdin.txt"),
        "stdout_sha256": file_sha256(run_root / "stdout.log"),
        "stdout_bytes": (run_root / "stdout.log").stat().st_size,
        "source_command_rejected": command_not_found,
        "source_command_entered": not command_not_found
        and bool(log_path.is_file() or summary["result_files"]),
        "result_files": summary["result_files"],
        "model_files": summary["model_files"],
        "required_core_files_present": not summary["missing_core_suffixes"],
        "xml_parseable": not summary["parse_errors"],
        "log_markers": marker_count,
        "log_sequence_complete": marker_count == len(markers),
        "major_error_mentions": len(
            re.findall(r"major[_ ]error|MAJOR_ERROR", log_text + stdout_text, re.I)
        ),
        "exception_mentions": len(
            re.findall(r"exception|error while", log_text + stdout_text, re.I)
        ),
        "semantic_signature": summary["semantic_signature"],
        "matches_historical_signature": summary["semantic_signature"]
        == expected_signature,
        "output_eligible_as_original": output_eligible,
        "nonzero_repository_failure_probabilities": summary[
            "nonzero_repository_failure_probabilities"
        ],
        "internal_failure_occurrence_count": summary["token_counts"][
            "internal_failure_occurrence"
        ],
        "software_failure_type_count": summary["token_counts"][
            "software_induced_failure_type"
        ],
    }


def classify_screen(
    config_path: Path, run_root: Path, out_path: Path
) -> Mapping[str, Any]:
    config = load_pmx_entrypoint_config(config_path)
    run = _read_entrypoint_run(config, run_root, "screen/published_original")
    payload = {
        "schema_version": 1,
        "kind": "m9h_source_entrypoint_screen",
        "config_sha256": file_sha256(config_path),
        "command": config.command,
        "output_eligible": run["output_eligible_as_original"],
        "run": run,
        "accuracy_outcomes_used": False,
    }
    _write_json(out_path, payload)
    return payload


def record_entrypoint_probe(
    config_path: Path,
    source_contract_path: Path,
    screen_path: Path,
    execution_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_entrypoint_config(config_path)
    source_contract = _object(
        _load_json(source_contract_path, "source contract"), "source contract"
    )
    if (
        source_contract.get("status") != "exact_source_declared_command_audited"
        or source_contract.get("config_sha256") != file_sha256(config_path)
        or source_contract.get("source_command") != config.command
    ):
        raise PMXEntrypointError("M9H source contract is incomplete")
    screen = _object(_load_json(screen_path, "entrypoint screen"), "screen")
    if (
        screen.get("config_sha256") != file_sha256(config_path)
        or screen.get("command") != config.command
    ):
        raise PMXEntrypointError("M9H screen contract differs")
    screen_run = _read_entrypoint_run(
        config, execution_root / "screen" / "published_original", "screen"
    )
    if screen.get("output_eligible") is not screen_run["output_eligible_as_original"]:
        raise PMXEntrypointError("recorded screen eligibility differs")

    confirmation_rows: list[dict[str, Any]] = []
    if screen_run["output_eligible_as_original"]:
        for condition in ("published_original", "single_error_control"):
            for repeat in range(1, config.confirmation_repeats + 1):
                confirmation_rows.append(
                    {
                        "phase": "confirmation",
                        "condition": condition,
                        "repeat": repeat,
                        **_read_entrypoint_run(
                            config,
                            execution_root
                            / "confirmation"
                            / condition
                            / f"repeat-{repeat}",
                            f"confirmation/{condition}/repeat-{repeat}",
                        ),
                    }
                )
    elif (execution_root / "confirmation").exists():
        unexpected = list((execution_root / "confirmation").rglob("exit-code.txt"))
        if unexpected:
            raise PMXEntrypointError("confirmation ran after an ineligible screen")

    rows = [
        {
            "phase": "screen",
            "condition": "published_original",
            "repeat": 1,
            **screen_run,
        },
        *confirmation_rows,
    ]
    originals = [
        row
        for row in confirmation_rows
        if row["condition"] == "published_original"
    ]
    controls = [
        row
        for row in confirmation_rows
        if row["condition"] == "single_error_control"
    ]
    original_confirmed = len(originals) == config.confirmation_repeats and all(
        row["output_eligible_as_original"] for row in originals
    )
    expected_probability = float(
        config.raw["evidence"]["m9f_control"]["expected_failure_probability"]
    )
    tolerance = float(config.raw["evidence"]["m9f_control"]["absolute_tolerance"])
    control_passes = [
        (
            row["required_core_files_present"]
            and row["xml_parseable"]
            and row["log_sequence_complete"]
            and row["major_error_mentions"] == 0
            and row["internal_failure_occurrence_count"] > 0
            and row["software_failure_type_count"] > 0
            and any(
                abs(float(value) - expected_probability) <= tolerance
                for value in row["nonzero_repository_failure_probabilities"]
            )
        )
        for row in controls
    ]
    mechanism = (
        original_confirmed
        and len(control_passes) == config.confirmation_repeats
        and all(control_passes)
    )
    clean = (
        screen_run["exit_code"] == 0
        and original_confirmed
        and len(controls) == config.confirmation_repeats
        and all(row["exit_code"] == 0 for row in originals + controls)
    )
    repeat_consistency = {
        condition: (
            len(
                {
                    row["semantic_signature"]
                    for row in confirmation_rows
                    if row["condition"] == condition
                }
            )
            == 1
        )
        for condition in ("published_original", "single_error_control")
    }
    if mechanism and clean:
        status = "pmx_source_entrypoint_and_failure_mechanism_reproduced"
    elif mechanism:
        status = "pmx_source_entrypoint_mechanism_reproduced_nonclean_exit"
    elif original_confirmed:
        status = "pmx_source_entrypoint_reproduced_failure_control_unresolved"
    elif screen_run["source_command_rejected"]:
        status = "pmx_source_declared_command_not_active_in_public_jar"
    else:
        status = "pmx_source_entrypoint_invoked_output_not_reproduced"

    out.mkdir(parents=True, exist_ok=True)
    fields = (
        "phase",
        "condition",
        "repeat",
        "exit_code",
        "timed_out",
        "elapsed_seconds",
        "stdout_bytes",
        "source_command_rejected",
        "source_command_entered",
        "result_files",
        "model_files",
        "required_core_files_present",
        "xml_parseable",
        "log_markers",
        "log_sequence_complete",
        "major_error_mentions",
        "exception_mentions",
        "semantic_signature",
        "matches_historical_signature",
        "output_eligible_as_original",
        "nonzero_repository_failure_probabilities",
        "internal_failure_occurrence_count",
        "software_failure_type_count",
    )
    flat_rows = [
        {
            key: (
                ";".join(str(item) for item in value)
                if isinstance(value, list)
                else value
            )
            for key, value in row.items()
            if key in fields
        }
        for row in rows
    ]
    _write_csv(out / "entrypoint-runs.csv", fields, flat_rows)
    _write_json(out / "entrypoint-screen.json", dict(screen))
    manifest = {
        "schema_version": 1,
        "kind": "m9h_source_entrypoint_probe",
        "status": status,
        "config_sha256": file_sha256(config_path),
        "source_contract_sha256": file_sha256(source_contract_path),
        "command": config.command,
        "startup_stabilization_seconds": config.startup_seconds,
        "internal_timeout_seconds": config.timeout_seconds,
        "source_command_rejected": screen_run["source_command_rejected"],
        "source_command_entered": screen_run["source_command_entered"],
        "screen_output_eligible": screen_run["output_eligible_as_original"],
        "confirmation_runs": len(confirmation_rows),
        "original_output_confirmed": original_confirmed,
        "launcher_terminates_cleanly": clean,
        "operation_failure_mechanism_reproduced": mechanism,
        "control_probability_passes": control_passes,
        "repeat_consistency": repeat_consistency,
        "manual_pcm_credited_as_pmx": False,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {
            "entrypoint-runs.csv": file_sha256(out / "entrypoint-runs.csv"),
            "entrypoint-screen.json": file_sha256(out / "entrypoint-screen.json"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "entrypoint-probe-manifest.json", manifest)
    return manifest


def decide(
    config_path: Path,
    source_contract_path: Path,
    probe_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_entrypoint_config(config_path)
    expected_config = file_sha256(config_path)
    contract = _object(_load_json(source_contract_path, "source contract"), "contract")
    probe = _object(_load_json(probe_path, "entrypoint probe"), "probe")
    if (
        contract.get("config_sha256") != expected_config
        or probe.get("config_sha256") != expected_config
        or contract.get("status") != "exact_source_declared_command_audited"
    ):
        raise PMXEntrypointError("M9H decision input chain differs")
    command_entered = probe.get("source_command_entered") is True
    output = probe.get("original_output_confirmed") is True
    clean = probe.get("launcher_terminates_cleanly") is True
    mechanism = probe.get("operation_failure_mechanism_reproduced") is True
    if mechanism:
        status = "pmx_source_entrypoint_and_failure_mechanism_reproduced"
        next_milestone = "m9i_learner_only_pmx_adapter_prototype"
    elif output:
        status = "pmx_source_entrypoint_reproduced_failure_semantics_unresolved"
        next_milestone = "m9i_pmx_failure_semantics_diagnostic"
    elif command_entered:
        status = "pmx_source_entrypoint_entered_output_not_reproduced"
        next_milestone = "m9i_pmx_source_runtime_diagnostic_and_manual_pcm_parallel"
    else:
        status = "pmx_source_declared_entrypoint_not_active"
        next_milestone = "m9i_pmx_container_reconstruction_and_manual_pcm_parallel"
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "question": "source_contract_agrees",
            "value": True,
            "interpretation": "descriptor and Java source independently declare main:main",
        },
        {
            "question": "source_command_entered",
            "value": command_entered,
            "interpretation": "not rejected and transformation evidence started",
        },
        {
            "question": "original_output_confirmed",
            "value": output,
            "interpretation": "two confirmations match historical semantics",
        },
        {
            "question": "launcher_terminates_cleanly",
            "value": clean,
            "interpretation": "output validity and process integration are separate",
        },
        {
            "question": "failure_mechanism_reproduced",
            "value": mechanism,
            "interpretation": "one-in-ten synthetic mechanism control; not accuracy",
        },
        {
            "question": "manual_pcm_credited_as_pmx",
            "value": False,
            "interpretation": "manual route remains a labelled contingency",
        },
    ]
    _write_csv(out / "decision-matrix.csv", ("question", "value", "interpretation"), rows)
    manifest = {
        "schema_version": 1,
        "kind": "m9h_source_entrypoint_decision",
        "status": status,
        "technical_evidence_accepted": True,
        "config_sha256": expected_config,
        "source_contract_sha256": file_sha256(source_contract_path),
        "probe_sha256": file_sha256(probe_path),
        "source_contract_agrees": True,
        "source_command_entered": command_entered,
        "original_output_confirmed": output,
        "launcher_terminates_cleanly": clean,
        "operation_failure_mechanism_reproduced": mechanism,
        "next_milestone": next_milestone,
        "pmx_scientific_priority_retained": True,
        "manual_pcm_parallel_retained": True,
        "manual_pcm_credited_as_pmx": False,
        "tested_artifacts_represent_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "accuracy_scoring_started": False,
        "m7_evidence_accessed": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {"decision-matrix.csv": file_sha256(out / "decision-matrix.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pmx-source-entrypoint")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--config", required=True, type=Path)
    contract = commands.add_parser("audit-source-contract")
    contract.add_argument("--config", required=True, type=Path)
    contract.add_argument("--recovery-metadata", required=True, type=Path)
    contract.add_argument("--application-metadata", required=True, type=Path)
    contract.add_argument("--decision-metadata", required=True, type=Path)
    contract.add_argument("--recovery-root", required=True, type=Path)
    contract.add_argument("--application-root", required=True, type=Path)
    contract.add_argument("--decision-root", required=True, type=Path)
    contract.add_argument("--out", required=True, type=Path)
    screen = commands.add_parser("classify-screen")
    screen.add_argument("--config", required=True, type=Path)
    screen.add_argument("--run-root", required=True, type=Path)
    screen.add_argument("--out", required=True, type=Path)
    probe = commands.add_parser("record-probe")
    probe.add_argument("--config", required=True, type=Path)
    probe.add_argument("--source-contract", required=True, type=Path)
    probe.add_argument("--screen", required=True, type=Path)
    probe.add_argument("--execution-root", required=True, type=Path)
    probe.add_argument("--out", required=True, type=Path)
    decision = commands.add_parser("decide")
    decision.add_argument("--config", required=True, type=Path)
    decision.add_argument("--source-contract", required=True, type=Path)
    decision.add_argument("--probe", required=True, type=Path)
    decision.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        config = load_pmx_entrypoint_config(args.config)
        payload: Mapping[str, Any] = {
            "status": "valid",
            "id": config.raw["id"],
            "command": config.command,
            "startup_stabilization_seconds": config.startup_seconds,
            "internal_timeout_seconds": config.timeout_seconds,
            "confirmation_repeats": config.confirmation_repeats,
            "job_timeout_minutes": config.job_timeout_minutes,
            "accuracy_scoring": "forbidden",
            "m7_evidence_access": "forbidden",
        }
    elif args.command == "audit-source-contract":
        payload = audit_source_contract(
            args.config,
            args.recovery_metadata,
            args.application_metadata,
            args.decision_metadata,
            args.recovery_root,
            args.application_root,
            args.decision_root,
            args.out,
        )
    elif args.command == "classify-screen":
        payload = classify_screen(args.config, args.run_root, args.out)
    elif args.command == "record-probe":
        payload = record_entrypoint_probe(
            args.config,
            args.source_contract,
            args.screen,
            args.execution_root,
            args.out,
        )
    else:
        payload = decide(args.config, args.source_contract, args.probe, args.out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
