from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .pmx_performability import (
    _MODEL_SUFFIXES,
    _eligible_spring_span,
    _parse_manifest,
    file_sha256,
    summarize_pcm_results,
)
from .provenance import environment_manifest


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_EXPECTED_CANDIDATES = [
    (1, "gogo_unscoped_pmx", "pmx -of Options.txt"),
    (2, "gogo_scoped_execute", "pmx:execute -of Options.txt"),
    (3, "gogo_scoped_main", "pmx:main -of Options.txt"),
    (4, "gogo_scoped_pmx", "pmx:pmx -of Options.txt"),
]
_EXPECTED_LOG_MARKERS = (
    "Executing reader org.palladiosimulator.pmx.reader.otlp.ReaderOpenTelemetry",
    "Executing transformer org.palladiosimulator.pmx.transformer.tracetointernaltrace.otlp.TransformerTraceToInternalTraceBasic",
    "Executing transformer org.palladiosimulator.pmx.transformer.internaltracetosystem.otlp.TransformerInternalTraceToSystemBasic",
    "Executing transformer org.palladiosimulator.pmx.transformer.systemtopcm.TransformerSystemToPCMBasic",
    "Executing transformer org.palladiosimulator.pmx.transformer.systemtopcm.failureprobabilities.TransformerSystemToPCMFailureDependencies",
    "Executing writer org.palladiosimulator.pmx.writer.basic.PCMWriter",
)


class PMXRecoveryError(ValueError):
    pass


@dataclass(frozen=True)
class PMXRecoveryConfig:
    path: Path
    raw: Mapping[str, Any]
    id: str
    timeout_seconds: int
    confirmation_repeats: int
    job_timeout_minutes: int


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PMXRecoveryError(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PMXRecoveryError(f"{label} must be a list")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PMXRecoveryError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PMXRecoveryError(f"{label} must be an integer")
    return value


def _positive(value: object, label: str) -> int:
    result = _integer(value, label)
    if result <= 0:
        raise PMXRecoveryError(f"{label} must be positive")
    return result


def _sha256(value: object, label: str) -> str:
    result = _string(value, label)
    if not _SHA256_RE.fullmatch(result):
        raise PMXRecoveryError(f"{label} must be a lowercase SHA-256")
    return result


def _commit(value: object, label: str) -> str:
    result = _string(value, label)
    if not _COMMIT_RE.fullmatch(result):
        raise PMXRecoveryError(f"{label} must be a full lowercase commit")
    return result


def _load_json(path: Path, label: str) -> Any:
    try:
        with path.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise PMXRecoveryError(f"cannot read {label}: {path}") from error


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(
    path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _relative(value: object, label: str) -> Path:
    text = _string(value, label)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise PMXRecoveryError(f"{label} must stay below its declared root")
    return path


def _audit_file(path: Path, record: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not path.is_file():
        raise PMXRecoveryError(f"{label} is missing: {path}")
    expected_bytes = _positive(record.get("bytes"), f"{label}.bytes")
    expected_sha = _sha256(record.get("sha256"), f"{label}.sha256")
    actual_bytes = path.stat().st_size
    actual_sha = file_sha256(path)
    if actual_bytes != expected_bytes or actual_sha != expected_sha:
        raise PMXRecoveryError(f"{label} byte identity differs")
    return {
        "path": str(record.get("path", path.name)),
        "expected_bytes": expected_bytes,
        "actual_bytes": actual_bytes,
        "expected_sha256": expected_sha,
        "actual_sha256": actual_sha,
        "matches": True,
    }


def load_pmx_recovery_config(path: str | Path) -> PMXRecoveryConfig:
    config_path = Path(path)
    root = _object(_load_json(config_path, "M9G config"), "root")
    if root.get("schema_version") != 1:
        raise PMXRecoveryError("M9G schema_version must equal 1")
    if root.get("id") != "m9g_pmx_recovery_and_application_delta":
        raise PMXRecoveryError("M9G id differs")
    if root.get("status") != "frozen_before_first_remote_launcher_probe_or_application_audit":
        raise PMXRecoveryError("M9G status must remain frozen before remote evidence")
    if root.get("diagnostic_only") is not True:
        raise PMXRecoveryError("M9G must remain diagnostic")
    if root.get("accuracy_scoring") != "forbidden":
        raise PMXRecoveryError("M9G must forbid accuracy scoring")
    if root.get("new_live_collection") != "forbidden":
        raise PMXRecoveryError("M9G must forbid new live collection")

    priority = _object(root.get("scientific_priority"), "scientific_priority")
    expected_priority = {
        "method": "PMX_performability_extension",
        "persists_if_application_cost_is_high": True,
        "historical_output_is_not_launcher_reproduction": True,
        "tested_artifacts_represent_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "m7_interpretation_changes": False,
    }
    if dict(priority) != expected_priority:
        raise PMXRecoveryError("M9G scientific-priority guard differs")

    evidence = _object(root.get("evidence"), "evidence")
    m9f = _object(evidence.get("m9f"), "evidence.m9f")
    if (
        m9f.get("run_id") != 34041926658
        or _commit(m9f.get("head_sha"), "m9f.head_sha")
        != "e3bfdfb5415d79007cce874181b274a10d62b433"
        or m9f.get("decision_status") != "pmx_public_binary_execution_not_reproduced"
    ):
        raise PMXRecoveryError("accepted M9F anchor differs")
    artifacts = _list(m9f.get("artifacts"), "m9f.artifacts")
    if len(artifacts) != 3:
        raise PMXRecoveryError("M9G requires all three accepted M9F artifacts")
    for index, value in enumerate(artifacts):
        item = _object(value, f"m9f.artifacts[{index}]")
        _positive(item.get("id"), f"m9f.artifacts[{index}].id")
        _positive(item.get("size_in_bytes"), f"m9f.artifacts[{index}].size")
        _sha256(item.get("sha256"), f"m9f.artifacts[{index}].sha256")

    demo = _object(evidence.get("demonstration"), "evidence.demonstration")
    if (
        demo.get("gitlab_project_id") != 50
        or _commit(demo.get("commit"), "demonstration.commit")
        != "9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2"
        or demo.get("pipeline_id") != 1120
        or demo.get("pmx_job_id") != 1984
    ):
        raise PMXRecoveryError("historical demonstration anchor differs")
    jar = _object(demo.get("jar"), "demonstration.jar")
    if (
        jar.get("bytes") != 65729095
        or _sha256(jar.get("sha256"), "demonstration.jar.sha256")
        != "befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013"
    ):
        raise PMXRecoveryError("PMX JAR lock differs")
    archive = _object(
        demo.get("historical_job_artifact"), "historical_job_artifact"
    )
    if archive.get("bytes") != 13676:
        raise PMXRecoveryError("historical PMX artifact size differs")
    _sha256(archive.get("sha256"), "historical_job_artifact.sha256")
    _sha256(archive.get("semantic_signature"), "historical semantic signature")
    files = _list(archive.get("files"), "historical_job_artifact.files")
    if len(files) != 14:
        raise PMXRecoveryError("historical PMX artifact must contain 14 pinned files")
    for index, value in enumerate(files):
        item = _object(value, f"historical file {index}")
        _relative(item.get("path"), f"historical file {index}.path")
        _positive(item.get("bytes"), f"historical file {index}.bytes")
        _sha256(item.get("sha256"), f"historical file {index}.sha256")
    if tuple(demo.get("historical_log_markers", [])) != _EXPECTED_LOG_MARKERS:
        raise PMXRecoveryError("historical PMX log markers differ")

    m8 = _object(evidence.get("m8a_preserved_m7"), "m8a_preserved_m7")
    if (
        m8.get("artifact_id") != 9983956440
        or m8.get("artifact_name")
        != "m8-preserved-m7-evidence-33990678586-34016153918"
        or m8.get("source_run_id") != 33990678586
    ):
        raise PMXRecoveryError("preserved M7 artifact anchor differs")
    _sha256(m8.get("sha256"), "m8a_preserved_m7.sha256")

    launcher = _object(root.get("launcher"), "launcher")
    timeout = _positive(launcher.get("screen_timeout_seconds"), "launcher timeout")
    if timeout != 120:
        raise PMXRecoveryError("M9G launcher screens must remain bounded at 120 seconds")
    repeats = _positive(launcher.get("confirmation_repeats"), "confirmation repeats")
    if repeats != 2:
        raise PMXRecoveryError("M9G confirmation repeat count differs")
    candidates = _list(launcher.get("candidate_order"), "candidate_order")
    observed_candidates = [
        (
            _integer(_object(item, "candidate").get("rank"), "candidate.rank"),
            _string(_object(item, "candidate").get("id"), "candidate.id"),
            _string(_object(item, "candidate").get("command"), "candidate.command"),
        )
        for item in candidates
    ]
    if observed_candidates != _EXPECTED_CANDIDATES:
        raise PMXRecoveryError("M9G frozen launcher candidate order differs")
    if launcher.get("selection_uses_accuracy_outcomes") is not False:
        raise PMXRecoveryError("launcher selection cannot use accuracy outcomes")
    if launcher.get("m9f_direct_argument_candidate_repeated") is not False:
        raise PMXRecoveryError("M9F failed direct invocation must not be repeated")
    if set(launcher.get("required_core_suffixes", [])) != _MODEL_SUFFIXES:
        raise PMXRecoveryError("required PCM suffix set differs")

    application = _object(root.get("application_audit"), "application_audit")
    if application.get("expected_qualified_bundles") != 160:
        raise PMXRecoveryError("M9G must audit the full 160-bundle learner population")
    if len(application.get("expected_raw_audit_samples", [])) != 4:
        raise PMXRecoveryError("M9G must keep the four raw samples separate")
    if application.get("raw_subset_is_accuracy_population") is not False:
        raise PMXRecoveryError("four raw samples cannot become an accuracy population")
    if application.get("evaluator_files_may_be_read") is not False:
        raise PMXRecoveryError("M9G application audit must forbid evaluator reads")

    runtime = _object(root.get("runtime"), "runtime")
    job_timeout = _positive(runtime.get("job_timeout_minutes"), "runtime timeout")
    if job_timeout != 360 or runtime.get("workflow_jobs") != 3:
        raise PMXRecoveryError("M9G requires exactly three 360-minute jobs")
    if runtime.get("remote_only_full_execution") is not True:
        raise PMXRecoveryError("full M9G execution must remain remote-only")

    repository_root = config_path.resolve().parents[1]
    for value in _list(root.get("repository_locks"), "repository_locks"):
        record = _object(value, "repository lock")
        target = repository_root / _relative(record.get("path"), "repository lock path")
        _audit_file(target, record, f"repository lock {target.name}")
    manual = _object(root.get("manual_actions_log"), "manual_actions_log")
    manual_path = repository_root / _relative(manual.get("path"), "manual log path")
    content = manual_path.read_bytes()
    prefix_size = _positive(manual.get("initial_size_in_bytes"), "manual prefix size")
    if len(content) < prefix_size:
        raise PMXRecoveryError("M9G manual log lost its frozen prefix")
    if hashlib.sha256(content[:prefix_size]).hexdigest() != _sha256(
        manual.get("initial_sha256"), "manual prefix sha256"
    ):
        raise PMXRecoveryError("M9G manual log frozen prefix differs")

    return PMXRecoveryConfig(
        path=config_path,
        raw=root,
        id=str(root["id"]),
        timeout_seconds=timeout,
        confirmation_repeats=repeats,
        job_timeout_minutes=job_timeout,
    )


def _manifest_text(values: Mapping[str, str]) -> str:
    return "\n".join(f"{key}: {value}" for key, value in sorted(values.items())) + "\n"


def audit_recovery_evidence(
    config_path: Path,
    demonstration_root: Path,
    historical_archive: Path,
    historical_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_recovery_config(config_path)
    demo = _object(config.raw["evidence"]["demonstration"], "demonstration")
    jar_record = _object(demo["jar"], "jar")
    jar_path = demonstration_root / str(jar_record["path"])
    jar_audit = _audit_file(jar_path, jar_record, "PMX JAR")
    archive_record = _object(demo["historical_job_artifact"], "historical archive")
    archive_audit = _audit_file(historical_archive, archive_record, "historical job artifact")

    historical_rows: list[dict[str, Any]] = []
    expected_paths: set[str] = set()
    for value in archive_record["files"]:
        record = _object(value, "historical file")
        relative = _relative(record["path"], "historical file path")
        expected_paths.add(relative.as_posix())
        historical_rows.append(
            _audit_file(historical_root / relative, record, f"historical {relative}")
        )
    actual_paths = {
        path.relative_to(historical_root).as_posix()
        for path in historical_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise PMXRecoveryError(
            f"historical artifact member set differs: {sorted(actual_paths ^ expected_paths)}"
        )
    with zipfile.ZipFile(historical_archive) as archive:
        zip_paths = {name.rstrip("/") for name in archive.namelist() if not name.endswith("/")}
    if zip_paths != expected_paths:
        raise PMXRecoveryError("historical ZIP central-directory member set differs")

    historical_results = historical_root / "results"
    historical_summary = dict(summarize_pcm_results(historical_results))
    if historical_summary["semantic_signature"] != archive_record["semantic_signature"]:
        raise PMXRecoveryError("historical PCM semantic signature differs")
    if historical_summary["missing_core_suffixes"] or historical_summary["parse_errors"]:
        raise PMXRecoveryError("historical PMX core model set is incomplete")
    historical_log = (historical_results / "log.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    missing_log_markers = [
        marker for marker in demo["historical_log_markers"] if marker not in historical_log
    ]
    if missing_log_markers:
        raise PMXRecoveryError(f"historical PMX log sequence differs: {missing_log_markers}")

    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(jar_path) as outer:
        names = sorted(outer.namelist())
        required = {"META-INF/MANIFEST.MF", "launcher.properties", "jar/org.palladiosimulator.pmx.core.jar"}
        if not required.issubset(names):
            raise PMXRecoveryError("PMX JAR lacks launcher audit entries")
        outer_manifest_bytes = outer.read("META-INF/MANIFEST.MF")
        launcher_bytes = outer.read("launcher.properties")
        core_bytes = outer.read("jar/org.palladiosimulator.pmx.core.jar")
        start_like = [
            name
            for name in names
            if Path(name.rstrip("/")).name.lower()
            in {"start", "start.sh", "entrypoint.sh", "run", "run.sh"}
        ]
        small_start_entries: dict[str, str] = {}
        for name in start_like:
            payload = outer.read(name)
            if len(payload) <= 1024 * 1024:
                small_start_entries[name] = payload.decode("utf-8", errors="replace")

    outer_manifest = _parse_manifest(outer_manifest_bytes)
    launcher_text = launcher_bytes.decode("utf-8", errors="replace")
    (out / "outer-manifest.txt").write_text(
        outer_manifest_bytes.decode("utf-8", errors="replace"), encoding="utf-8"
    )
    (out / "launcher.properties.txt").write_text(launcher_text, encoding="utf-8")
    for index, (name, text) in enumerate(sorted(small_start_entries.items()), start=1):
        (out / f"embedded-start-{index}.txt").write_text(
            f"source-entry: {name}\n{text}", encoding="utf-8"
        )

    core_source_path = "OSGI-OPT/src/org/palladiosimulator/pmx/core/Main.java"
    command_evidence: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(core_bytes)) as core:
        core_names = sorted(core.namelist())
        if core_source_path not in core_names:
            raise PMXRecoveryError("embedded PMX core Main.java is missing")
        main_source = core.read(core_source_path).decode("utf-8", errors="replace")
        core_manifest_bytes = core.read("META-INF/MANIFEST.MF")
        candidate_entries = [
            name
            for name in core_names
            if (
                name == core_source_path
                or name.startswith("OSGI-INF/")
                or name.lower().endswith((".properties", ".bnd"))
            )
            and not name.endswith("/")
        ]
        for name in candidate_entries:
            payload = core.read(name)
            if len(payload) > 1024 * 1024:
                continue
            text = payload.decode("utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if re.search(
                    r"osgi\.command|@Descriptor|options-file|System\.exit|public\s+\w+\s*\(",
                    line,
                    re.I,
                ):
                    command_evidence.append(
                        {"entry": name, "line": line_number, "text": line.strip()}
                    )
    (out / "core-main.java.txt").write_text(main_source, encoding="utf-8")
    (out / "core-manifest.txt").write_text(
        core_manifest_bytes.decode("utf-8", errors="replace"), encoding="utf-8"
    )
    _write_csv(
        out / "command-registration-evidence.csv",
        ("entry", "line", "text"),
        command_evidence,
    )
    _write_csv(
        out / "historical-file-audit.csv",
        (
            "path",
            "expected_bytes",
            "actual_bytes",
            "expected_sha256",
            "actual_sha256",
            "matches",
        ),
        historical_rows,
    )
    _write_json(out / "historical-pcm-summary.json", historical_summary)
    launcher_audit = {
        "outer_entry_count": len(names),
        "outer_manifest": outer_manifest,
        "launcher_properties_bytes": len(launcher_bytes),
        "launcher_properties_sha256": hashlib.sha256(launcher_bytes).hexdigest(),
        "embedded_start_like_entries": start_like,
        "core_entry_count": len(core_names),
        "core_manifest": _parse_manifest(core_manifest_bytes),
        "core_main_sha256": hashlib.sha256(main_source.encode()).hexdigest(),
        "command_evidence_rows": len(command_evidence),
        "historical_ci_uses_container_entrypoint": "/entrypoint.sh"
        in (demonstration_root / ".gitlab-ci.yml").read_text(encoding="utf-8"),
        "historical_ci_publishes_entrypoint": (demonstration_root / "entrypoint.sh").is_file(),
    }
    _write_json(out / "jar-launcher-audit.json", launcher_audit)

    output_files = [
        "outer-manifest.txt",
        "launcher.properties.txt",
        "core-main.java.txt",
        "core-manifest.txt",
        "command-registration-evidence.csv",
        "historical-file-audit.csv",
        "historical-pcm-summary.json",
        "jar-launcher-audit.json",
    ] + [f"embedded-start-{index}.txt" for index in range(1, len(small_start_entries) + 1)]
    manifest = {
        "schema_version": 1,
        "kind": "m9g_pmx_recovery_contract",
        "status": "historical_output_and_launcher_contract_audited",
        "config_sha256": file_sha256(config_path),
        "jar": jar_audit,
        "historical_archive": archive_audit,
        "historical_files": len(historical_rows),
        "historical_pcm_semantic_signature": historical_summary["semantic_signature"],
        "historical_pcm_model_files": historical_summary["model_files"],
        "historical_pcm_result_files": historical_summary["result_files"],
        "historical_failure_probability_count": len(historical_summary["failure_rows"]),
        "historical_log_sequence_complete": True,
        "launcher": launcher_audit,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {name: file_sha256(out / name) for name in output_files},
        "environment": environment_manifest(),
    }
    _write_json(out / "recovery-contract-manifest.json", manifest)
    return manifest


def _read_run(config: PMXRecoveryConfig, run_root: Path, label: str) -> dict[str, Any]:
    required = (
        "exit-code.txt",
        "elapsed-seconds.txt",
        "started-at-utc.txt",
        "finished-at-utc.txt",
        "stdin.txt",
        "stdout.log",
        "resource-usage.txt",
    )
    missing = [name for name in required if not (run_root / name).is_file()]
    if missing or not (run_root / "results").is_dir():
        raise PMXRecoveryError(f"{label} lacks execution evidence: {missing}")
    try:
        exit_code = int((run_root / "exit-code.txt").read_text().strip())
        elapsed = int((run_root / "elapsed-seconds.txt").read_text().strip())
    except ValueError as error:
        raise PMXRecoveryError(f"{label} has invalid execution metadata") from error
    summary = dict(summarize_pcm_results(run_root / "results"))
    log_path = run_root / "results" / "log.txt"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    stdout_text = (run_root / "stdout.log").read_text(encoding="utf-8", errors="replace")
    marker_count = sum(marker in log_text for marker in _EXPECTED_LOG_MARKERS)
    complete_models = not summary["missing_core_suffixes"] and not summary["parse_errors"]
    historical_signature = config.raw["launcher"]["expected_original_semantic_signature"]
    return {
        "label": label,
        "exit_code": exit_code,
        "timed_out": exit_code in {124, 137},
        "elapsed_seconds": elapsed,
        "started_at_utc": (run_root / "started-at-utc.txt").read_text().strip(),
        "finished_at_utc": (run_root / "finished-at-utc.txt").read_text().strip(),
        "stdin_sha256": file_sha256(run_root / "stdin.txt"),
        "stdout_sha256": file_sha256(run_root / "stdout.log"),
        "stdout_bytes": (run_root / "stdout.log").stat().st_size,
        "result_files": summary["result_files"],
        "model_files": summary["model_files"],
        "required_core_files_present": not summary["missing_core_suffixes"],
        "xml_parseable": not summary["parse_errors"],
        "log_markers": marker_count,
        "log_sequence_complete": marker_count == len(_EXPECTED_LOG_MARKERS),
        "major_error_mentions": len(re.findall(r"major[_ ]error|MAJOR_ERROR", log_text + stdout_text, re.I)),
        "exception_mentions": len(re.findall(r"exception|error while", log_text + stdout_text, re.I)),
        "semantic_signature": summary["semantic_signature"],
        "matches_historical_signature": summary["semantic_signature"] == historical_signature,
        "output_eligible_as_original": (
            complete_models
            and marker_count == len(_EXPECTED_LOG_MARKERS)
            and not re.search(r"major[_ ]error|MAJOR_ERROR", log_text + stdout_text, re.I)
            and summary["semantic_signature"] == historical_signature
        ),
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


def select_launcher(
    config_path: Path, candidate_root: Path, out_path: Path
) -> Mapping[str, Any]:
    config = load_pmx_recovery_config(config_path)
    rows: list[dict[str, Any]] = []
    selected: Mapping[str, Any] | None = None
    for candidate in config.raw["launcher"]["candidate_order"]:
        run = _read_run(config, candidate_root / str(candidate["id"]), str(candidate["id"]))
        row = {
            "rank": candidate["rank"],
            "id": candidate["id"],
            "command": candidate["command"],
            **run,
        }
        rows.append(row)
        if selected is None and run["output_eligible_as_original"]:
            selected = {
                "rank": candidate["rank"],
                "id": candidate["id"],
                "command": candidate["command"],
                "screen_exit_code": run["exit_code"],
                "screen_timed_out": run["timed_out"],
            }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9g_launcher_selection",
        "config_sha256": file_sha256(config_path),
        "selection_rule": "first_output_eligible_candidate_in_frozen_order",
        "selected": selected,
        "candidates": rows,
        "accuracy_outcomes_used": False,
    }
    _write_json(out_path, payload)
    return payload


def record_launcher_probes(
    config_path: Path,
    recovery_contract_path: Path,
    selection_path: Path,
    execution_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_recovery_config(config_path)
    contract = _object(_load_json(recovery_contract_path, "recovery contract"), "contract")
    if contract.get("status") != "historical_output_and_launcher_contract_audited":
        raise PMXRecoveryError("M9G recovery contract is incomplete")
    selection = _object(_load_json(selection_path, "launcher selection"), "selection")
    if selection.get("config_sha256") != file_sha256(config_path):
        raise PMXRecoveryError("launcher selection config hash differs")

    screen_rows = [
        {
            "phase": "screen",
            "condition": "published_original",
            "repeat": 1,
            "candidate_id": candidate["id"],
            "candidate_rank": candidate["rank"],
            "command": candidate["command"],
            **_read_run(
                config,
                execution_root / "screen" / str(candidate["id"]),
                f"screen/{candidate['id']}",
            ),
        }
        for candidate in config.raw["launcher"]["candidate_order"]
    ]
    selected = selection.get("selected")
    confirmation_rows: list[dict[str, Any]] = []
    if selected is not None:
        selected_record = _object(selected, "selected launcher")
        expected = next(
            candidate
            for candidate in config.raw["launcher"]["candidate_order"]
            if candidate["id"] == selected_record.get("id")
        )
        if selected_record.get("command") != expected["command"]:
            raise PMXRecoveryError("selected launcher command differs from frozen candidate")
        for condition in ("published_original", "single_error_control"):
            for repeat in range(1, config.confirmation_repeats + 1):
                confirmation_rows.append(
                    {
                        "phase": "confirmation",
                        "condition": condition,
                        "repeat": repeat,
                        "candidate_id": selected_record["id"],
                        "candidate_rank": selected_record["rank"],
                        "command": selected_record["command"],
                        **_read_run(
                            config,
                            execution_root
                            / "confirmation"
                            / condition
                            / f"repeat-{repeat}",
                            f"confirmation/{condition}/repeat-{repeat}",
                        ),
                    }
                )

    originals = [row for row in confirmation_rows if row["condition"] == "published_original"]
    controls = [row for row in confirmation_rows if row["condition"] == "single_error_control"]
    output_recovered = len(originals) == config.confirmation_repeats and all(
        row["output_eligible_as_original"] for row in originals
    )
    clean_termination = bool(originals) and all(row["exit_code"] == 0 for row in originals)
    expected_probability = float(config.raw["launcher"]["control_expected_failure_probability"])
    tolerance = float(config.raw["launcher"]["control_absolute_tolerance"])
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
    mechanism_reproduced = (
        output_recovered
        and len(control_passes) == config.confirmation_repeats
        and all(control_passes)
    )
    repeat_consistent = {
        condition: (
            len({row["semantic_signature"] for row in confirmation_rows if row["condition"] == condition})
            == 1
        )
        for condition in ("published_original", "single_error_control")
    }
    if mechanism_reproduced and clean_termination:
        status = "pmx_gogo_launcher_and_failure_mechanism_reproduced"
    elif mechanism_reproduced:
        status = "pmx_output_and_failure_mechanism_reproduced_launcher_nonterminal"
    elif output_recovered:
        status = "pmx_output_reproduced_failure_mechanism_not_reproduced"
    else:
        status = "pmx_launcher_recovery_not_reproduced"

    out.mkdir(parents=True, exist_ok=True)
    rows = screen_rows + confirmation_rows
    flat_rows = []
    for row in rows:
        flat_rows.append(
            {
                key: (
                    ";".join(str(item) for item in value)
                    if isinstance(value, list)
                    else value
                )
                for key, value in row.items()
                if key
                in {
                    "phase",
                    "condition",
                    "repeat",
                    "candidate_id",
                    "candidate_rank",
                    "command",
                    "exit_code",
                    "timed_out",
                    "elapsed_seconds",
                    "stdout_bytes",
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
                }
            }
        )
    fields = (
        "phase",
        "condition",
        "repeat",
        "candidate_id",
        "candidate_rank",
        "command",
        "exit_code",
        "timed_out",
        "elapsed_seconds",
        "stdout_bytes",
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
    _write_csv(out / "launcher-runs.csv", fields, flat_rows)
    _write_json(out / "launcher-selection.json", dict(selection))
    manifest = {
        "schema_version": 1,
        "kind": "m9g_launcher_recovery_probe",
        "status": status,
        "config_sha256": file_sha256(config_path),
        "recovery_contract_sha256": file_sha256(recovery_contract_path),
        "selection": selected,
        "screen_candidates": len(screen_rows),
        "confirmation_runs": len(confirmation_rows),
        "byte_pinned_gogo_output_recovered": output_recovered,
        "launcher_terminates_cleanly": clean_termination,
        "operation_failure_mechanism_reproduced": mechanism_reproduced,
        "control_probability_passes": control_passes,
        "repeat_consistency": repeat_consistent,
        "historical_output_is_not_launcher_reproduction": True,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {
            "launcher-runs.csv": file_sha256(out / "launcher-runs.csv"),
            "launcher-selection.json": file_sha256(out / "launcher-selection.json"),
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "launcher-probe-manifest.json", manifest)
    return manifest


def _csv_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return next(csv.reader(source), [])


def _attribute_value(value: object) -> Any:
    data = value if isinstance(value, Mapping) else {}
    for key in ("stringValue", "boolValue", "intValue", "doubleValue", "bytesValue"):
        if key in data:
            return data[key]
    if "arrayValue" in data:
        array = data["arrayValue"] if isinstance(data["arrayValue"], Mapping) else {}
        return [_attribute_value(item) for item in array.get("values", [])]
    if "kvlistValue" in data:
        nested = data["kvlistValue"] if isinstance(data["kvlistValue"], Mapping) else {}
        return _attributes(nested.get("values", []))
    return None


def _attributes(values: object) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if not isinstance(values, list):
        return result
    for item in values:
        if isinstance(item, Mapping) and "key" in item:
            result[str(item["key"])] = _attribute_value(item.get("value"))
    return result


def _learner_trace_ids(
    trace_join: Path, learner_periods: set[str], forbidden: set[str]
) -> tuple[set[str], set[str]]:
    selected: set[str] = set()
    forbidden_ids: set[str] = set()
    with trace_join.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"period", "trace_id"}.issubset(reader.fieldnames or []):
            raise PMXRecoveryError(f"{trace_join} lacks trace selection columns")
        for row in reader:
            trace_id = str(row.get("trace_id", "")).lower()
            period = str(row.get("period", ""))
            if not trace_id:
                continue
            if period in learner_periods:
                selected.add(trace_id)
            if period in forbidden:
                forbidden_ids.add(trace_id)
    if selected & forbidden_ids:
        raise PMXRecoveryError("learner and forbidden trace IDs overlap")
    return selected, forbidden_ids


def _audit_jaeger_raw(path: Path, selected: set[str], forbidden: set[str]) -> dict[str, Any]:
    payload = _object(_load_json(path, "Jaeger raw telemetry"), "Jaeger envelope")
    traces = _list(payload.get("data"), "Jaeger data")
    seen_spans: set[tuple[str, str]] = set()
    selected_traces: set[str] = set()
    services: set[str] = set()
    spring = errors = http_status = missing_required = forbidden_seen = 0
    host_values: set[str] = set()
    instance_values: set[str] = set()
    for trace_value in traces:
        trace = _object(trace_value, "Jaeger trace")
        trace_id = str(trace.get("traceID", "")).lower()
        if trace_id not in selected:
            continue
        selected_traces.add(trace_id)
        forbidden_seen += int(trace_id in forbidden)
        processes = trace.get("processes", {})
        process_map = processes if isinstance(processes, Mapping) else {}
        for process in process_map.values():
            if not isinstance(process, Mapping):
                continue
            service = str(process.get("serviceName", ""))
            if service:
                services.add(service)
            tags = {str(t.get("key")): t.get("value") for t in process.get("tags", []) if isinstance(t, Mapping)}
            if tags.get("host.name"):
                host_values.add(str(tags["host.name"]))
            for key in ("service.instance.id", "container.id", "container.name"):
                if tags.get(key):
                    instance_values.add(str(tags[key]))
        for span_value in trace.get("spans", []):
            if not isinstance(span_value, Mapping):
                continue
            span_id = str(span_value.get("spanID", "")).lower()
            key = (trace_id, span_id)
            if key in seen_spans:
                continue
            seen_spans.add(key)
            missing_required += int(
                not span_id
                or not span_value.get("operationName")
                or span_value.get("startTime") is None
                or span_value.get("duration") is None
            )
            tags = {str(t.get("key")): t.get("value") for t in span_value.get("tags", []) if isinstance(t, Mapping)}
            spring += int(_eligible_spring_span(span_value))
            errors += int(str(tags.get("error", "")).lower() == "true")
            http_status += int("http.status_code" in tags)
    return {
        "native_format": "jaeger_json_v1",
        "direct_jaeger_envelope": True,
        "schema_adapter_required": False,
        "selected_trace_ids": len(selected),
        "selected_traces_present": len(selected_traces),
        "selected_unique_spans": len(seen_spans),
        "missing_required_span_fields": missing_required,
        "services": len(services),
        "host_identifiers": len(host_values),
        "instance_identifiers": len(instance_values),
        "spring_webmvc_spans": spring,
        "direct_error_true_spans": errors,
        "otlp_error_status_spans": 0,
        "http_status_spans": http_status,
        "forbidden_trace_spans_selected": forbidden_seen,
        "malformed_jsonl_records": 0,
    }


def _audit_otlp_raw(path: Path, selected: set[str], forbidden: set[str]) -> dict[str, Any]:
    seen_spans: set[tuple[str, str]] = set()
    selected_traces: set[str] = set()
    services: set[str] = set()
    spring = direct_errors = status_errors = http_status = missing_required = malformed = 0
    host_values: set[str] = set()
    instance_values: set[str] = set()
    forbidden_seen = 0
    with path.open(encoding="utf-8", errors="replace") as source:
        for raw in source:
            if not raw.strip():
                continue
            try:
                document = json.loads(raw)
            except json.JSONDecodeError:
                malformed += 1
                continue
            for resource_group in document.get("resourceSpans", []):
                if not isinstance(resource_group, Mapping):
                    malformed += 1
                    continue
                resource = resource_group.get("resource", {})
                resource_attrs = _attributes(
                    resource.get("attributes", []) if isinstance(resource, Mapping) else []
                )
                service = str(resource_attrs.get("service.name", ""))
                resource_selected = False
                for scope_group in resource_group.get("scopeSpans", []):
                    if not isinstance(scope_group, Mapping):
                        malformed += 1
                        continue
                    scope = scope_group.get("scope", {})
                    scope_name = str(scope.get("name", "")) if isinstance(scope, Mapping) else ""
                    for span in scope_group.get("spans", []):
                        if not isinstance(span, Mapping):
                            malformed += 1
                            continue
                        trace_id = str(span.get("traceId", "")).lower()
                        if trace_id not in selected:
                            continue
                        span_id = str(span.get("spanId", "")).lower()
                        key = (trace_id, span_id)
                        if key in seen_spans:
                            continue
                        seen_spans.add(key)
                        resource_selected = True
                        selected_traces.add(trace_id)
                        forbidden_seen += int(trace_id in forbidden)
                        missing_required += int(
                            not span_id
                            or not span.get("name")
                            or span.get("startTimeUnixNano") is None
                            or span.get("endTimeUnixNano") is None
                            or not service
                        )
                        attrs = _attributes(span.get("attributes", []))
                        library = str(attrs.get("otel.library.name", scope_name))
                        spring += int("spring-webmvc" in library)
                        direct_errors += int(str(attrs.get("error", "")).lower() == "true")
                        status = span.get("status", {})
                        status_code = status.get("code") if isinstance(status, Mapping) else None
                        status_errors += int(status_code in {2, "2", "STATUS_CODE_ERROR"})
                        http_status += int(
                            "http.status_code" in attrs
                            or "http.response.status_code" in attrs
                        )
                if resource_selected:
                    if service:
                        services.add(service)
                    if resource_attrs.get("host.name"):
                        host_values.add(str(resource_attrs["host.name"]))
                    for key in (
                        "service.instance.id",
                        "k8s.pod.name",
                        "container.id",
                        "container.name",
                    ):
                        if resource_attrs.get(key):
                            instance_values.add(str(resource_attrs[key]))
    return {
        "native_format": "otlp_jsonl_v1",
        "direct_jaeger_envelope": False,
        "schema_adapter_required": True,
        "selected_trace_ids": len(selected),
        "selected_traces_present": len(selected_traces),
        "selected_unique_spans": len(seen_spans),
        "missing_required_span_fields": missing_required,
        "services": len(services),
        "host_identifiers": len(host_values),
        "instance_identifiers": len(instance_values),
        "spring_webmvc_spans": spring,
        "direct_error_true_spans": direct_errors,
        "otlp_error_status_spans": status_errors,
        "http_status_spans": http_status,
        "forbidden_trace_spans_selected": forbidden_seen,
        "malformed_jsonl_records": malformed,
    }


def _artifact_metadata(path: Path, lock: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = _object(_load_json(path, "M8 artifact metadata"), "artifact metadata")
    digest = str(metadata.get("digest", "")).removeprefix("sha256:")
    checks = {
        "id": metadata.get("id") == lock.get("artifact_id"),
        "name": metadata.get("name") == lock.get("artifact_name"),
        "size": metadata.get("size_in_bytes") == lock.get("size_in_bytes"),
        "digest": digest == lock.get("sha256"),
        "not_expired": metadata.get("expired") is False,
    }
    if not all(checks.values()):
        raise PMXRecoveryError(f"M8 preserved artifact metadata differs: {checks}")
    return {"metadata": metadata, "checks": checks}


def audit_application_delta(
    config_path: Path,
    artifact_metadata_path: Path,
    preserved_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_recovery_config(config_path)
    spec = _object(config.raw["application_audit"], "application_audit")
    lock = _object(config.raw["evidence"]["m8a_preserved_m7"], "M8 lock")
    artifact_audit = _artifact_metadata(artifact_metadata_path, lock)
    qualified_root = preserved_root / "qualified"
    raw_root = preserved_root / "raw-audit-samples"
    manifests = sorted(qualified_root.rglob("learner/manifest.json"))
    if len(manifests) != spec["expected_qualified_bundles"]:
        raise PMXRecoveryError(
            f"expected 160 learner manifests, found {len(manifests)} below {qualified_root}"
        )

    qualified_rows: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str, int]] = set()
    raw_qualified = 0
    required_files = list(spec["required_learner_files"])
    for manifest_path in manifests:
        learner = manifest_path.parent
        manifest = _object(_load_json(manifest_path, "learner manifest"), "learner manifest")
        identity = (
            str(manifest.get("profile")),
            str(manifest.get("placement")),
            str(manifest.get("failure_law")),
            int(manifest.get("repetition")),
        )
        if identity in identities:
            raise PMXRecoveryError(f"duplicate M7 learner identity: {identity}")
        identities.add(identity)
        missing = [name for name in required_files if not (learner / name).is_file()]
        if missing:
            raise PMXRecoveryError(f"{identity} lacks learner files {missing}")
        raw_files = sorted(learner.glob("raw-telemetry.*"))
        raw_qualified += int(bool(raw_files))
        requests_header = set(_csv_header(learner / "requests.csv"))
        health_header = set(_csv_header(learner / "health.csv"))
        topology_header = set(_csv_header(learner / "topology-edges.csv"))
        deployment = _object(_load_json(learner / "deployment.json", "deployment"), "deployment")
        qualified_rows.append(
            {
                "profile": identity[0],
                "placement": identity[1],
                "failure_law": identity[2],
                "repetition": identity[3],
                "raw_trace_stream_in_learner": bool(raw_files),
                "direct_pmx_reader_input": False,
                "derived_trace_id": "trace_id" in requests_header,
                "derived_operation": "operation" in requests_header,
                "derived_service_set": "services" in requests_header,
                "derived_span_count": "span_count" in requests_header,
                "raw_span_parent_and_timing": False,
                "derived_topology": {"source_service", "target_service"}.issubset(topology_header),
                "deployment_replica_metadata": bool(deployment.get("replica_services")),
                "deployment_domain_metadata": bool(deployment.get("domain_assignments")),
                "lifecycle_health_observations": "observed_at" in health_header,
                "communication_health_observations": any(
                    name.endswith("_network_count") for name in health_header
                ),
                "external_semantic_success": "semantic_success" in requests_header,
                "evaluator_files_read": False,
            }
        )
    expected_identities = {
        (profile, placement, law, repetition)
        for profile in spec["profiles"]
        for placement in spec["placements"]
        for law in spec["failure_laws"]
        for repetition in range(spec["repetitions"])
    }
    if identities != expected_identities:
        raise PMXRecoveryError("qualified M7 learner identity matrix differs")
    if raw_qualified != spec["expected_raw_files_in_qualified_bundles"]:
        raise PMXRecoveryError("unexpected raw telemetry appeared in qualified learner bundles")

    expected_samples = set(spec["expected_raw_audit_samples"])
    sample_dirs = {
        path.name: path
        for path in raw_root.rglob("m7-raw-audit-sample-*")
        if path.is_dir() and (path / "campaign-manifest.json").is_file()
    }
    if set(sample_dirs) != expected_samples:
        raise PMXRecoveryError(
            f"raw audit sample set differs: {sorted(set(sample_dirs) ^ expected_samples)}"
        )
    learner_periods = set(spec["learner_periods"])
    forbidden_periods = set(spec["forbidden_periods"])
    raw_rows: list[dict[str, Any]] = []
    for name in sorted(sample_dirs):
        sample = sample_dirs[name]
        campaign = _object(
            _load_json(sample / "campaign-manifest.json", "campaign manifest"),
            "campaign manifest",
        )
        profile = str(campaign.get("profile"))
        expected_format = spec["raw_formats"][profile]
        selected, forbidden = _learner_trace_ids(
            sample / "trace-join.csv", learner_periods, forbidden_periods
        )
        if expected_format == "jaeger_json_v1":
            raw_result = _audit_jaeger_raw(
                sample / "raw-telemetry.json", selected, forbidden
            )
        elif expected_format == "otlp_jsonl_v1":
            raw_result = _audit_otlp_raw(
                sample / "raw-telemetry.log", selected, forbidden
            )
        else:
            raise PMXRecoveryError(f"unsupported frozen raw format {expected_format}")
        if raw_result["native_format"] != expected_format:
            raise PMXRecoveryError(f"raw format differs for {name}")
        raw_rows.append(
            {
                "sample": name,
                "profile": profile,
                "placement": campaign.get("placement"),
                "failure_law": campaign.get("failure_law"),
                "repetition": campaign.get("repetition"),
                **raw_result,
                "schema_adaptable_without_evaluator": (
                    raw_result["selected_traces_present"] > 0
                    and raw_result["selected_unique_spans"] > 0
                    and raw_result["missing_required_span_fields"] == 0
                    and raw_result["forbidden_trace_spans_selected"] == 0
                ),
                "direct_pmx_instrumentation_semantics": raw_result[
                    "spring_webmvc_spans"
                ]
                > 0,
                "evaluator_files_read": False,
                "request_success_used": False,
            }
        )

    out.mkdir(parents=True, exist_ok=True)
    qualified_fields = tuple(qualified_rows[0].keys())
    raw_fields = tuple(raw_rows[0].keys())
    _write_csv(out / "qualified-input-coverage.csv", qualified_fields, qualified_rows)
    _write_csv(out / "raw-schema-compatibility.csv", raw_fields, raw_rows)
    dimension_rows = [
        {
            "dimension": "raw_trace_ingestion",
            "qualified_population_direct": raw_qualified == len(qualified_rows),
            "raw_subset_support": all(row["schema_adaptable_without_evaluator"] for row in raw_rows),
            "required_work": "preserve or recollect learner-period raw spans for the accuracy population and implement OTLP-to-reader conversion where needed",
        },
        {
            "dimension": "instrumentation_semantics",
            "qualified_population_direct": False,
            "raw_subset_support": all(row["direct_pmx_instrumentation_semantics"] for row in raw_rows),
            "required_work": "map each application's instrumentation to the audited Spring-WebMVC operation/error contract and validate rather than assume equivalence",
        },
        {
            "dimension": "architecture_and_replication",
            "qualified_population_direct": False,
            "raw_subset_support": all(row["services"] > 0 for row in raw_rows),
            "required_work": "join derived topology with declared replica/domain metadata and keep inferred redundancy explicit",
        },
        {
            "dimension": "lifecycle_and_communication",
            "qualified_population_direct": False,
            "raw_subset_support": False,
            "required_work": "map independent learner health/network observations to PCM lifecycle and communication semantics outside the trace-only PMX transform",
        },
        {
            "dimension": "external_client_success",
            "qualified_population_direct": False,
            "raw_subset_support": False,
            "required_work": "retain the external semantic-success contract as a separate learner input; span error is not automatically equivalent",
        },
    ]
    _write_csv(
        out / "application-dimensions.csv",
        ("dimension", "qualified_population_direct", "raw_subset_support", "required_work"),
        dimension_rows,
    )
    manifest = {
        "schema_version": 1,
        "kind": "m9g_application_information_delta",
        "status": "application_information_delta_audited",
        "config_sha256": file_sha256(config_path),
        "artifact_metadata": artifact_audit,
        "qualified_bundles": len(qualified_rows),
        "qualified_raw_streams": raw_qualified,
        "all_160_direct_raw_input_coverage": raw_qualified == len(qualified_rows),
        "raw_audit_samples": len(raw_rows),
        "raw_subset_schema_adaptable": all(
            row["schema_adaptable_without_evaluator"] for row in raw_rows
        ),
        "raw_subset_direct_instrumentation_semantics": all(
            row["direct_pmx_instrumentation_semantics"] for row in raw_rows
        ),
        "additional_deployment_lifecycle_communication_mapping_required": True,
        "raw_subset_is_accuracy_population": False,
        "evaluator_files_read": False,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {
            name: file_sha256(out / name)
            for name in (
                "qualified-input-coverage.csv",
                "raw-schema-compatibility.csv",
                "application-dimensions.csv",
            )
        },
        "environment": environment_manifest(),
    }
    _write_json(out / "application-audit-manifest.json", manifest)
    return manifest


def decide(
    config_path: Path,
    recovery_contract_path: Path,
    launcher_probe_path: Path,
    application_audit_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_recovery_config(config_path)
    expected_config_sha = file_sha256(config_path)
    contract = _object(_load_json(recovery_contract_path, "recovery contract"), "contract")
    launcher = _object(_load_json(launcher_probe_path, "launcher probe"), "launcher")
    application = _object(_load_json(application_audit_path, "application audit"), "application")
    for label, manifest in (
        ("contract", contract),
        ("launcher", launcher),
        ("application", application),
    ):
        if manifest.get("config_sha256") != expected_config_sha:
            raise PMXRecoveryError(f"{label} config hash differs")
    historical = contract.get("status") == "historical_output_and_launcher_contract_audited"
    output_recovered = launcher.get("byte_pinned_gogo_output_recovered") is True
    clean = launcher.get("launcher_terminates_cleanly") is True
    mechanism = launcher.get("operation_failure_mechanism_reproduced") is True
    direct_160 = application.get("all_160_direct_raw_input_coverage") is True
    raw_adaptable = application.get("raw_subset_schema_adaptable") is True
    instrumentation = application.get("raw_subset_direct_instrumentation_semantics") is True
    extra_mapping = (
        application.get("additional_deployment_lifecycle_communication_mapping_required")
        is True
    )
    if mechanism:
        status = "pmx_launcher_mechanism_recovered_application_adapter_required"
        next_milestone = "m9h_learner_only_pmx_application_adapter"
    elif output_recovered:
        status = "pmx_output_recovered_mechanism_or_application_semantics_incomplete"
        next_milestone = "m9h_pmx_failure_semantics_and_application_adapter"
    else:
        status = "historical_output_recovered_launcher_unresolved"
        next_milestone = "m9h_pmx_source_entrypoint_recovery_and_manual_pcm_parallel"
    if not direct_160:
        next_collection_status = "future_preregistered_collection_required_for_full_pmx_accuracy_population"
    else:
        next_collection_status = "existing_learner_population_has_direct_raw_input"

    rows = [
        {"question": "historical_output_recovered", "value": historical, "interpretation": "public job artifact audited independently of mutable image"},
        {"question": "byte_pinned_gogo_output_recovered", "value": output_recovered, "interpretation": "authors example confirmed twice if true"},
        {"question": "launcher_terminates_cleanly", "value": clean, "interpretation": "runtime integration cost; separate from output validity"},
        {"question": "one_in_ten_failure_mechanism_reproduced", "value": mechanism, "interpretation": "synthetic mechanism control; not accuracy"},
        {"question": "all_160_direct_raw_input_coverage", "value": direct_160, "interpretation": "qualified M7 learner population only"},
        {"question": "four_sample_schema_adaptable", "value": raw_adaptable, "interpretation": "schema subset; not accuracy population"},
        {"question": "direct_instrumentation_semantics", "value": instrumentation, "interpretation": "audited PMX Spring-WebMVC contract"},
        {"question": "additional_mapping_required", "value": extra_mapping, "interpretation": "deployment lifecycle communication and external success"},
    ]
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "decision-matrix.csv", ("question", "value", "interpretation"), rows)
    manifest = {
        "schema_version": 1,
        "kind": "m9g_joint_decision",
        "status": status,
        "technical_evidence_accepted": True,
        "config_sha256": expected_config_sha,
        "recovery_contract_sha256": file_sha256(recovery_contract_path),
        "launcher_probe_sha256": file_sha256(launcher_probe_path),
        "application_audit_sha256": file_sha256(application_audit_path),
        "historical_output_recovered": historical,
        "byte_pinned_gogo_output_recovered": output_recovered,
        "launcher_terminates_cleanly": clean,
        "operation_failure_mechanism_reproduced": mechanism,
        "all_160_direct_raw_input_coverage": direct_160,
        "raw_subset_schema_adaptable": raw_adaptable,
        "raw_subset_direct_instrumentation_semantics": instrumentation,
        "additional_mapping_required": extra_mapping,
        "raw_subset_is_accuracy_population": False,
        "next_collection_status": next_collection_status,
        "next_milestone": next_milestone,
        "pmx_scientific_priority_retained": True,
        "tested_artifacts_represent_all_pmx_or_palladio": False,
        "retriever_result_generalizes_to_ecosystem": False,
        "missing_support_classified_as_application_cost": True,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {"decision-matrix.csv": file_sha256(out / "decision-matrix.csv")},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pmx-recovery")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--config", required=True, type=Path)
    recovery = commands.add_parser("audit-recovery-evidence")
    recovery.add_argument("--config", required=True, type=Path)
    recovery.add_argument("--demonstration-root", required=True, type=Path)
    recovery.add_argument("--historical-archive", required=True, type=Path)
    recovery.add_argument("--historical-root", required=True, type=Path)
    recovery.add_argument("--out", required=True, type=Path)
    selection = commands.add_parser("select-launcher")
    selection.add_argument("--config", required=True, type=Path)
    selection.add_argument("--candidate-root", required=True, type=Path)
    selection.add_argument("--out", required=True, type=Path)
    probe = commands.add_parser("record-launcher-probes")
    probe.add_argument("--config", required=True, type=Path)
    probe.add_argument("--recovery-contract", required=True, type=Path)
    probe.add_argument("--selection", required=True, type=Path)
    probe.add_argument("--execution-root", required=True, type=Path)
    probe.add_argument("--out", required=True, type=Path)
    application = commands.add_parser("audit-application-delta")
    application.add_argument("--config", required=True, type=Path)
    application.add_argument("--artifact-metadata", required=True, type=Path)
    application.add_argument("--preserved-root", required=True, type=Path)
    application.add_argument("--out", required=True, type=Path)
    decision = commands.add_parser("decide")
    decision.add_argument("--config", required=True, type=Path)
    decision.add_argument("--recovery-contract", required=True, type=Path)
    decision.add_argument("--launcher-probe", required=True, type=Path)
    decision.add_argument("--application-audit", required=True, type=Path)
    decision.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        config = load_pmx_recovery_config(args.config)
        payload: Mapping[str, Any] = {
            "status": "valid",
            "id": config.id,
            "job_timeout_minutes": config.job_timeout_minutes,
            "screen_timeout_seconds": config.timeout_seconds,
            "confirmation_repeats": config.confirmation_repeats,
            "accuracy_scoring": "forbidden",
            "new_live_collection": "forbidden",
        }
    elif args.command == "audit-recovery-evidence":
        payload = audit_recovery_evidence(
            args.config,
            args.demonstration_root,
            args.historical_archive,
            args.historical_root,
            args.out,
        )
    elif args.command == "select-launcher":
        payload = select_launcher(args.config, args.candidate_root, args.out)
    elif args.command == "record-launcher-probes":
        payload = record_launcher_probes(
            args.config,
            args.recovery_contract,
            args.selection,
            args.execution_root,
            args.out,
        )
    elif args.command == "audit-application-delta":
        payload = audit_application_delta(
            args.config,
            args.artifact_metadata,
            args.preserved_root,
            args.out,
        )
    else:
        payload = decide(
            args.config,
            args.recovery_contract,
            args.launcher_probe,
            args.application_audit,
            args.out,
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
