from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree

from .provenance import environment_manifest


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MODEL_SUFFIXES = {
    ".allocation",
    ".repository",
    ".resourceenvironment",
    ".system",
    ".usagemodel",
}
_SEMANTIC_DIMENSIONS = {
    "trace_ingestion",
    "architecture_operation_flow",
    "software_operation_failure",
    "host_lifecycle",
    "communication_failure",
    "replication",
    "common_failure_domains",
    "external_client_success",
}


@dataclass(frozen=True)
class PMXPerformabilityConfig:
    path: Path
    raw: Mapping[str, Any]
    id: str
    job_timeout_minutes: int
    internal_timeout_seconds: int
    repeat_count: int


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _sequence(value: object, label: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def _string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _positive_integer(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}.{key} must be a positive integer")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _commit(value: object, label: str) -> str:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a full lowercase commit")
    return value


def _git_blob(value: object, label: str) -> str:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a full lowercase Git blob id")
    return value


def _relative_path(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{label} must remain below its declared root")
    return path.as_posix()


def _string_list(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    sequence = _sequence(value, label)
    if (not allow_empty and not sequence) or any(
        not isinstance(item, str) or not item for item in sequence
    ):
        raise ValueError(f"{label} must contain non-empty strings")
    result = list(sequence)
    if len(set(result)) != len(result):
        raise ValueError(f"{label} must not contain duplicates")
    return result


def _load_json(path: Path, label: str) -> Any:
    with path.open(encoding="utf-8") as source:
        try:
            return json.load(source)
        except json.JSONDecodeError as error:
            raise ValueError(f"{label} is not valid JSON") from error


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(
    path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _audit_regular_file(path: Path, record: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label}: missing file {path}")
    actual_bytes = path.stat().st_size
    actual_sha256 = file_sha256(path)
    expected_bytes = _positive_integer(record, "bytes", label)
    expected_sha256 = _sha256(record.get("sha256"), f"{label}.sha256")
    matches = actual_bytes == expected_bytes and actual_sha256 == expected_sha256
    if not matches:
        raise ValueError(f"{label}: byte identity differs")
    return {
        "path": str(record.get("path", path.name)),
        "expected_bytes": expected_bytes,
        "actual_bytes": actual_bytes,
        "expected_sha256": expected_sha256,
        "actual_sha256": actual_sha256,
        "matches": True,
    }


def load_pmx_performability_config(path: Path) -> PMXPerformabilityConfig:
    root = _mapping(_load_json(path, "M9F config"), "root")
    if root.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    if root.get("status") != "frozen_before_first_remote_pmx_execution":
        raise ValueError("M9F status must remain frozen before PMX execution")
    if root.get("diagnostic_only") is not True:
        raise ValueError("M9F must remain diagnostic_only")
    if root.get("accuracy_scoring") != "forbidden":
        raise ValueError("M9F must forbid accuracy scoring")
    if root.get("new_live_collection") != "forbidden":
        raise ValueError("M9F must forbid new live collection")

    priority = _mapping(root.get("scientific_priority"), "scientific_priority")
    if priority.get("method") != "PMX_performability_extension":
        raise ValueError("M9F must prioritize the PMX performability extension")
    if priority.get("persists_if_application_cost_is_high") is not True:
        raise ValueError("application cost must not cancel PMX scientific priority")
    if priority.get("retriever_result_generalizes_to_ecosystem") is not False:
        raise ValueError("Retriever result must not generalize to the ecosystem")
    if priority.get("m7_interpretation_changes") is not False:
        raise ValueError("M9F cannot change M7 interpretation")

    runtime = _mapping(root.get("runtime"), "runtime")
    job_timeout = _positive_integer(runtime, "job_timeout_minutes", "runtime")
    if job_timeout != 360:
        raise ValueError("all M9F job timeouts must be 360 minutes")
    internal_timeout = _positive_integer(
        runtime, "pmx_internal_timeout_seconds", "runtime"
    )
    safety_minutes = _positive_integer(
        runtime, "headless_job_safety_minutes", "runtime"
    )
    repeat_count = _positive_integer(runtime, "repeat_count_per_condition", "runtime")
    if repeat_count != 2:
        raise ValueError("M9F must retain two runs per condition")
    frozen_run_count = 2 * repeat_count
    available_execution_seconds = (job_timeout - safety_minutes) * 60
    if available_execution_seconds <= 0:
        raise ValueError("M9F headless-job safety margin consumes the job timeout")
    if internal_timeout * frozen_run_count > available_execution_seconds:
        raise ValueError(
            "M9F internal timeouts must leave the frozen headless-job safety margin"
        )
    if runtime.get("remote_only_full_execution") is not True:
        raise ValueError("full PMX execution must remain remote-only")
    if _string_list(runtime.get("invocation"), "runtime.invocation") != [
        "java",
        "-jar",
        "main.jar",
        "-of",
        "Options.txt",
    ]:
        raise ValueError("M9F invocation differs from the frozen options-file route")

    paper = _mapping(root.get("paper"), "paper")
    _string(paper, "url", "paper")
    _positive_integer(paper, "bytes", "paper")
    _sha256(paper.get("sha256"), "paper.sha256")

    repository_locks = _sequence(root.get("repository_locks"), "repository_locks")
    if len(repository_locks) < 2:
        raise ValueError("M9F must lock its protocol and scope correction")
    for index, value in enumerate(repository_locks):
        label = f"repository_locks[{index}]"
        record = _mapping(value, label)
        _relative_path(record.get("path"), f"{label}.path")
        _positive_integer(record, "bytes", label)
        _sha256(record.get("sha256"), f"{label}.sha256")

    manual = _mapping(root.get("manual_actions_log"), "manual_actions_log")
    _relative_path(manual.get("path"), "manual_actions_log.path")
    _positive_integer(manual, "initial_size_in_bytes", "manual_actions_log")
    _sha256(manual.get("initial_sha256"), "manual_actions_log.initial_sha256")
    if manual.get("append_only_after_preregistration") is not True:
        raise ValueError("M9F manual log must be append-only")

    historical_ids: set[str] = set()
    for index, value in enumerate(_sequence(root.get("historical_sources"), "historical_sources")):
        label = f"historical_sources[{index}]"
        source = _mapping(value, label)
        source_id = _string(source, "id", label)
        historical_ids.add(source_id)
        _string(source, "repository", label)
        _commit(source.get("commit"), f"{label}.commit")
        locks = _sequence(source.get("locks"), f"{label}.locks")
        if not locks:
            raise ValueError(f"{label}.locks must not be empty")
        for lock_index, lock_value in enumerate(locks):
            lock_label = f"{label}.locks[{lock_index}]"
            lock = _mapping(lock_value, lock_label)
            _relative_path(lock.get("path"), f"{lock_label}.path")
            _git_blob(lock.get("git_blob"), f"{lock_label}.git_blob")
            _positive_integer(lock, "bytes", lock_label)
            _string_list(lock.get("markers"), f"{lock_label}.markers")
    if historical_ids != {"pmx_opentracing_refactor", "pmx_pcm_companion"}:
        raise ValueError("unexpected historical PMX source set")

    demonstration = _mapping(root.get("demonstration"), "demonstration")
    _positive_integer(demonstration, "project_id", "demonstration")
    _positive_integer(demonstration, "historical_pipeline_id", "demonstration")
    _commit(demonstration.get("commit"), "demonstration.commit")
    demo_paths: set[str] = set()
    for index, value in enumerate(_sequence(demonstration.get("files"), "demonstration.files")):
        label = f"demonstration.files[{index}]"
        record = _mapping(value, label)
        relative = _relative_path(record.get("path"), f"{label}.path")
        demo_paths.add(relative)
        _git_blob(record.get("git_blob"), f"{label}.git_blob")
        _positive_integer(record, "bytes", label)
        _sha256(record.get("sha256"), f"{label}.sha256")
    required_demo = {
        ".gitlab-ci.yml",
        "Options.txt",
        "README.md",
        "main.jar",
        "traces/jaegerapi.json",
        "traces/jaegercustomers.json",
        "traces/jaegervets.json",
        "traces/jaegervisits.json",
    }
    if demo_paths != required_demo:
        raise ValueError("demonstration file set differs from the frozen set")
    if len(_string_list(demonstration.get("published_plugins"), "demonstration.published_plugins")) != 6:
        raise ValueError("M9F must retain all six published plugins")
    containers = _sequence(demonstration.get("containers"), "demonstration.containers")
    if {str(_mapping(item, "container").get("stage")) for item in containers} != {
        "extract",
        "simulate",
        "plot",
    }:
        raise ValueError("M9F must audit all three published container stages")

    jar = _mapping(root.get("jar_audit"), "jar_audit")
    if jar.get("main_class") != "aQute.launcher.pre.EmbeddedLauncher":
        raise ValueError("unexpected frozen PMX Main-Class")
    _string_list(jar.get("required_entries"), "jar_audit.required_entries")
    for index, value in enumerate(_sequence(jar.get("embedded_bundles"), "jar_audit.embedded_bundles")):
        label = f"jar_audit.embedded_bundles[{index}]"
        record = _mapping(value, label)
        _relative_path(record.get("path"), f"{label}.path")
        _positive_integer(record, "bytes", label)
        _sha256(record.get("sha256"), f"{label}.sha256")
    source_check_ids: set[str] = set()
    for index, value in enumerate(_sequence(jar.get("embedded_source_checks"), "jar_audit.embedded_source_checks")):
        label = f"jar_audit.embedded_source_checks[{index}]"
        record = _mapping(value, label)
        source_check_ids.add(_string(record, "id", label))
        _relative_path(record.get("bundle_path"), f"{label}.bundle_path")
        _relative_path(record.get("source_path"), f"{label}.source_path")
        _string_list(record.get("markers"), f"{label}.markers")
    if len(source_check_ids) != 7:
        raise ValueError("M9F must retain all seven embedded-source checks")

    conditions = _sequence(root.get("conditions"), "conditions")
    condition_ids = {str(_mapping(item, "condition").get("id")) for item in conditions}
    if condition_ids != {"published_original", "single_error_control"}:
        raise ValueError("unexpected M9F conditions")
    control = next(
        _mapping(item, "single_error_control")
        for item in conditions
        if _mapping(item, "condition").get("id") == "single_error_control"
    )
    if control.get("expected_failure_probability") != 0.1:
        raise ValueError("single-error control must retain the 1/10 oracle")
    if control.get("eligible_operation_occurrences") != 10:
        raise ValueError("single-error control occurrence count must remain ten")

    suffixes = set(_string_list(root.get("required_core_model_suffixes"), "required_core_model_suffixes"))
    if suffixes != _MODEL_SUFFIXES:
        raise ValueError("required PCM model suffix set differs")
    dimensions = {
        str(_mapping(item, "semantic dimension").get("id"))
        for item in _sequence(root.get("semantic_dimensions"), "semantic_dimensions")
    }
    if dimensions != _SEMANTIC_DIMENSIONS:
        raise ValueError("semantic dimension set differs")

    guardrails = _mapping(root.get("interpretation_guardrails"), "interpretation_guardrails")
    expected_guardrails = {
        "missing_support_is_application_cost_not_scientific_disqualification": True,
        "tested_binary_represents_all_pmx": False,
        "tested_binary_represents_all_palladio": False,
        "published_example_is_accuracy_evidence": False,
        "synthetic_error_control_is_accuracy_evidence": False,
        "historical_source_equals_later_binary_source": False,
        "exit_zero_alone_is_success": False,
    }
    if dict(guardrails) != expected_guardrails:
        raise ValueError("M9F interpretation guardrails differ")

    return PMXPerformabilityConfig(
        path=path,
        raw=root,
        id=_string(root, "id", "root"),
        job_timeout_minutes=job_timeout,
        internal_timeout_seconds=internal_timeout,
        repeat_count=repeat_count,
    )


def _git_output(checkout: Path, *arguments: str, text: bool = False) -> bytes | str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            check=True,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"Git audit failed for {checkout}: {' '.join(arguments)}") from error
    return completed.stdout


def _git_head(checkout: Path) -> str:
    return str(_git_output(checkout, "rev-parse", "HEAD", text=True)).strip()


def _git_blob_bytes(checkout: Path, relative: str) -> tuple[str, bytes]:
    blob = str(
        _git_output(checkout, "rev-parse", f"HEAD:{relative}", text=True)
    ).strip()
    content = _git_output(checkout, "cat-file", "blob", blob)
    if not isinstance(content, bytes):
        raise AssertionError("Git blob command unexpectedly returned text")
    return blob, content


def _audit_historical_source(
    source: Mapping[str, Any], checkout: Path
) -> list[dict[str, Any]]:
    expected_commit = _commit(source.get("commit"), "historical source commit")
    if _git_head(checkout) != expected_commit:
        raise ValueError(f"{source['id']}: checkout commit differs")
    rows: list[dict[str, Any]] = []
    for index, value in enumerate(source["locks"]):
        record = _mapping(value, f"{source['id']}.locks[{index}]")
        relative = _relative_path(record.get("path"), "historical lock path")
        blob, content = _git_blob_bytes(checkout, relative)
        markers = _string_list(record.get("markers"), "historical lock markers")
        decoded = content.decode("utf-8")
        missing = [marker for marker in markers if marker not in decoded]
        matches = (
            blob == record["git_blob"]
            and len(content) == record["bytes"]
            and not missing
        )
        if not matches:
            raise ValueError(
                f"{source['id']}: canonical Git blob audit failed for {relative}; "
                f"missing markers={missing}"
            )
        rows.append(
            {
                "source": source["id"],
                "role": source["role"],
                "commit": expected_commit,
                "path": relative,
                "git_blob": blob,
                "bytes": len(content),
                "sha256": _bytes_sha256(content),
                "marker_count": len(markers),
                "matches": True,
            }
        )
    return rows


def audit_pmx_contract(
    config_path: Path,
    repository_root: Path,
    paper_path: Path,
    historical_root: Path,
    demonstration_root: Path,
    project_metadata_path: Path,
    commit_metadata_path: Path,
    pipeline_metadata_path: Path,
    jobs_metadata_path: Path,
    tree_metadata_path: Path,
    registry_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_performability_config(config_path)
    raw = config.raw

    repository_rows: list[dict[str, Any]] = []
    for index, value in enumerate(raw["repository_locks"]):
        record = _mapping(value, f"repository_locks[{index}]")
        relative = _relative_path(record.get("path"), "repository lock path")
        row = _audit_regular_file(
            repository_root / relative, record, f"repository lock {relative}"
        )
        repository_rows.append(row)

    manual = _mapping(raw["manual_actions_log"], "manual_actions_log")
    manual_path = repository_root / str(manual["path"])
    content = manual_path.read_bytes()
    initial_size = int(manual["initial_size_in_bytes"])
    if len(content) < initial_size:
        raise ValueError("M9F manual log is shorter than its frozen prefix")
    prefix_sha = _bytes_sha256(content[:initial_size])
    if prefix_sha != manual["initial_sha256"]:
        raise ValueError("M9F manual log frozen prefix differs")
    with manual_path.open(encoding="utf-8", newline="") as source_file:
        manual_rows = list(csv.DictReader(source_file))
    if not manual_rows:
        raise ValueError("M9F manual log is empty")

    paper_row = _audit_regular_file(paper_path, _mapping(raw["paper"], "paper"), "paper")

    historical_rows: list[dict[str, Any]] = []
    for source_value in raw["historical_sources"]:
        source = _mapping(source_value, "historical source")
        historical_rows.extend(
            _audit_historical_source(source, historical_root / str(source["id"]))
        )

    demonstration = _mapping(raw["demonstration"], "demonstration")
    project = _mapping(_load_json(project_metadata_path, "GitLab project"), "GitLab project")
    if project.get("id") != demonstration["project_id"]:
        raise ValueError("GitLab project id differs")
    if project.get("visibility") != "public":
        raise ValueError("GitLab demonstration is not publicly visible")
    commit = _mapping(_load_json(commit_metadata_path, "GitLab commit"), "GitLab commit")
    if commit.get("id") != demonstration["commit"]:
        raise ValueError("GitLab demonstration commit differs")
    pipeline = _mapping(_load_json(pipeline_metadata_path, "GitLab pipeline"), "GitLab pipeline")
    if pipeline.get("id") != demonstration["historical_pipeline_id"]:
        raise ValueError("GitLab historical pipeline id differs")
    if pipeline.get("sha") != demonstration["commit"]:
        raise ValueError("GitLab historical pipeline commit differs")
    if pipeline.get("status") != demonstration["historical_pipeline_status"]:
        raise ValueError("GitLab historical pipeline status differs")
    jobs = _sequence(_load_json(jobs_metadata_path, "GitLab jobs"), "GitLab jobs")
    job_status = {
        str(_mapping(item, "GitLab job").get("name")): str(
            _mapping(item, "GitLab job").get("status")
        )
        for item in jobs
    }
    if {"pmx", "palladio", "gnuplot"} - set(job_status):
        raise ValueError("historical GitLab pipeline jobs are incomplete")
    if any(job_status[name] != "success" for name in ("pmx", "palladio", "gnuplot")):
        raise ValueError("historical GitLab pipeline jobs did not all succeed")

    tree = _sequence(_load_json(tree_metadata_path, "GitLab tree"), "GitLab tree")
    tree_by_path = {
        str(_mapping(item, "GitLab tree item").get("path")): _mapping(
            item, "GitLab tree item"
        )
        for item in tree
    }
    demonstration_rows: list[dict[str, Any]] = []
    for index, value in enumerate(demonstration["files"]):
        record = _mapping(value, f"demonstration.files[{index}]")
        relative = str(record["path"])
        item = tree_by_path.get(relative)
        if item is None or item.get("type") != "blob":
            raise ValueError(f"GitLab tree is missing {relative}")
        if item.get("id") != record["git_blob"]:
            raise ValueError(f"GitLab blob id differs for {relative}")
        raw_checked = relative != "main.jar"
        if raw_checked:
            _audit_regular_file(
                demonstration_root / relative,
                record,
                f"downloaded demonstration file {relative}",
            )
        demonstration_rows.append(
            {
                "path": relative,
                "git_blob": item["id"],
                "expected_bytes": record["bytes"],
                "expected_sha256": record["sha256"],
                "raw_bytes_checked_in_contract_job": raw_checked,
                "tree_matches": True,
            }
        )

    ci_text = (demonstration_root / ".gitlab-ci.yml").read_text(encoding="utf-8")
    options_text = (demonstration_root / "Options.txt").read_text(encoding="utf-8")
    missing_plugins = [
        plugin for plugin in demonstration["published_plugins"] if plugin not in options_text
    ]
    if missing_plugins:
        raise ValueError(f"published options omit plugins: {missing_plugins}")

    registry_repositories = _sequence(
        _load_json(registry_root / "repositories.json", "registry repositories"),
        "registry repositories",
    )
    repository_ids = {
        int(_mapping(item, "registry repository")["id"])
        for item in registry_repositories
    }
    container_rows: list[dict[str, Any]] = []
    for value in demonstration["containers"]:
        container = _mapping(value, "container")
        repository_id = int(container["registry_repository_id"])
        tags = _sequence(
            _load_json(registry_root / f"tags-{repository_id}.json", "registry tags"),
            "registry tags",
        )
        tag_names = sorted(
            str(_mapping(item, "registry tag").get("name"))
            if isinstance(item, Mapping)
            else str(item)
            for item in tags
        )
        reference = str(container["reference"])
        if reference not in ci_text:
            raise ValueError(f"pipeline no longer contains {reference}")
        container_rows.append(
            {
                "stage": container["stage"],
                "registry_repository_id": repository_id,
                "repository_listed": repository_id in repository_ids,
                "published_reference": reference,
                "mutable_latest": reference.endswith(":latest"),
                "observed_tag_count": len(tag_names),
                "observed_tags": ";".join(tag_names),
                "historical_digest_pinned": False,
            }
        )

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "repository-lock-audit.csv",
        (
            "path",
            "expected_bytes",
            "actual_bytes",
            "expected_sha256",
            "actual_sha256",
            "matches",
        ),
        repository_rows,
    )
    _write_csv(
        out / "historical-source-audit.csv",
        (
            "source",
            "role",
            "commit",
            "path",
            "git_blob",
            "bytes",
            "sha256",
            "marker_count",
            "matches",
        ),
        historical_rows,
    )
    _write_csv(
        out / "demonstration-artifact-audit.csv",
        (
            "path",
            "git_blob",
            "expected_bytes",
            "expected_sha256",
            "raw_bytes_checked_in_contract_job",
            "tree_matches",
        ),
        demonstration_rows,
    )
    _write_csv(
        out / "container-reproducibility.csv",
        (
            "stage",
            "registry_repository_id",
            "repository_listed",
            "published_reference",
            "mutable_latest",
            "observed_tag_count",
            "observed_tags",
            "historical_digest_pinned",
        ),
        container_rows,
    )
    metadata_snapshot = {
        "project": project,
        "commit": commit,
        "pipeline": pipeline,
        "jobs": jobs,
        "registry_repositories": registry_repositories,
    }
    _write_json(out / "upstream-metadata-snapshot.json", metadata_snapshot)

    output_files = (
        "repository-lock-audit.csv",
        "historical-source-audit.csv",
        "demonstration-artifact-audit.csv",
        "container-reproducibility.csv",
        "upstream-metadata-snapshot.json",
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9f_pmx_provenance_contract",
        "status": "provenance_contract_passed",
        "config_sha256": file_sha256(config_path),
        "paper": paper_row,
        "historical_source_files": len(historical_rows),
        "demonstration_files": len(demonstration_rows),
        "historical_pipeline": {
            "id": pipeline["id"],
            "sha": pipeline["sha"],
            "status": pipeline["status"],
            "job_status": job_status,
        },
        "containers": container_rows,
        "exact_historical_container_chain_recoverable": False,
        "exact_historical_container_chain_reason": (
            "published references are mutable latest tags and no historical digest is pinned"
        ),
        "manual_log_rows": len(manual_rows),
        "manual_log_frozen_prefix_sha256": prefix_sha,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {name: file_sha256(out / name) for name in output_files},
        "environment": environment_manifest(),
    }
    _write_json(out / "contract-manifest.json", manifest)
    return manifest


def _demo_file_record(config: PMXPerformabilityConfig, relative: str) -> Mapping[str, Any]:
    for value in config.raw["demonstration"]["files"]:
        record = _mapping(value, "demonstration file")
        if record.get("path") == relative:
            return record
    raise ValueError(f"demonstration file is not frozen: {relative}")


def _eligible_spring_span(span: Mapping[str, Any]) -> bool:
    operation = str(span.get("operationName", ""))
    excluded = (
        "Handler",
        "ChaosMonkeyRestEndpoint",
        "EnvironmentController",
        "BasicErrorController",
    )
    tags = span.get("tags", [])
    if not isinstance(tags, list):
        return False
    spring = any(
        isinstance(tag, Mapping)
        and tag.get("key") == "otel.library.name"
        and "spring-webmvc" in str(tag.get("value", ""))
        for tag in tags
    )
    return spring and not any(marker in operation for marker in excluded)


def create_error_control(
    config_path: Path,
    demonstration_root: Path,
    output_trace: Path,
    output_options: Path,
    manifest_path: Path,
) -> Mapping[str, Any]:
    config = load_pmx_performability_config(config_path)
    control = next(
        _mapping(item, "single_error_control")
        for item in config.raw["conditions"]
        if _mapping(item, "condition").get("id") == "single_error_control"
    )
    source_relative = str(control["source_trace_path"])
    source_path = demonstration_root / source_relative
    _audit_regular_file(
        source_path,
        _demo_file_record(config, source_relative),
        "error-control source trace",
    )
    payload = _mapping(_load_json(source_path, "source trace"), "source trace")
    traces = _sequence(payload.get("data"), "source trace data")

    target_span: Mapping[str, Any] | None = None
    eligible_count = 0
    original_error_tags = 0
    target_operation = str(control["operation"])
    for trace_value in traces:
        trace = _mapping(trace_value, "trace")
        for span_value in _sequence(trace.get("spans"), "trace spans"):
            span = _mapping(span_value, "span")
            tags = _sequence(span.get("tags"), "span tags")
            original_error_tags += sum(
                1
                for tag in tags
                if isinstance(tag, Mapping) and tag.get("key") == "error"
            )
            if _eligible_spring_span(span) and span.get("operationName") == target_operation:
                eligible_count += 1
            if (
                trace.get("traceID") == control["trace_id"]
                and span.get("spanID") == control["span_id"]
            ):
                if target_span is not None:
                    raise ValueError("error-control target span is duplicated")
                target_span = span

    if target_span is None:
        raise ValueError("error-control target span is absent")
    if target_span.get("operationName") != target_operation:
        raise ValueError("error-control target operation differs")
    if not _eligible_spring_span(target_span):
        raise ValueError("error-control target is not an eligible Spring MVC span")
    if eligible_count != control["eligible_operation_occurrences"]:
        raise ValueError("eligible error-control occurrence count differs")
    if original_error_tags != control["original_error_tags"]:
        raise ValueError("original error-tag count differs")

    mutable_tags = target_span.get("tags")
    if not isinstance(mutable_tags, list):
        raise ValueError("target span tags are not mutable JSON list data")
    mutable_tags.append(dict(_mapping(control["tag"], "control tag")))

    output_trace.parent.mkdir(parents=True, exist_ok=True)
    output_trace.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    source_options = demonstration_root / "Options.txt"
    _audit_regular_file(
        source_options,
        _demo_file_record(config, "Options.txt"),
        "published options",
    )
    options_text = source_options.read_text(encoding="utf-8")
    replacement = str(control["trace_path"])
    if options_text.count(source_relative) != 1:
        raise ValueError("published options do not contain exactly one source trace path")
    control_options = options_text.replace(source_relative, replacement)
    output_options.parent.mkdir(parents=True, exist_ok=True)
    output_options.write_text(control_options, encoding="utf-8")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9f_single_error_control",
        "status": "control_generated",
        "config_sha256": file_sha256(config_path),
        "source_trace": source_relative,
        "source_trace_sha256": file_sha256(source_path),
        "output_trace": output_trace.name,
        "output_trace_sha256": file_sha256(output_trace),
        "source_options_sha256": file_sha256(source_options),
        "output_options": output_options.name,
        "output_options_sha256": file_sha256(output_options),
        "trace_id": control["trace_id"],
        "span_id": control["span_id"],
        "operation": target_operation,
        "inserted_tag": control["tag"],
        "eligible_operation_occurrences": eligible_count,
        "original_error_tags": original_error_tags,
        "inserted_error_tags": 1,
        "expected_failure_probability": control["expected_failure_probability"],
    }
    _write_json(manifest_path, manifest)
    return manifest


def _parse_manifest(content: bytes) -> Mapping[str, str]:
    text = content.decode("utf-8", errors="replace").replace("\r\n", "\n")
    unfolded: list[str] = []
    for line in text.split("\n"):
        if line.startswith(" ") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    result: dict[str, str] = {}
    for line in unfolded:
        if ": " in line:
            key, value = line.split(": ", 1)
            result[key] = value
    return result


def audit_pmx_jar(
    config: PMXPerformabilityConfig, jar_path: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Mapping[str, Any]]:
    record = _demo_file_record(config, "main.jar")
    _audit_regular_file(jar_path, record, "PMX main.jar")
    jar_spec = _mapping(config.raw["jar_audit"], "jar_audit")
    with zipfile.ZipFile(jar_path) as outer:
        names = set(outer.namelist())
        missing = sorted(set(jar_spec["required_entries"]) - names)
        if missing:
            raise ValueError(f"PMX JAR is missing required entries: {missing}")
        outer_manifest = _parse_manifest(outer.read("META-INF/MANIFEST.MF"))
        if outer_manifest.get("Main-Class") != jar_spec["main_class"]:
            raise ValueError("PMX JAR Main-Class differs")
        if outer_manifest.get("Bundle-Version") != jar_spec["bundle_version"]:
            raise ValueError("PMX JAR Bundle-Version differs")

        bundle_rows: list[dict[str, Any]] = []
        bundle_content: dict[str, bytes] = {}
        for value in jar_spec["embedded_bundles"]:
            bundle = _mapping(value, "embedded bundle")
            path = str(bundle["path"])
            content = outer.read(path)
            matches = (
                len(content) == bundle["bytes"]
                and _bytes_sha256(content) == bundle["sha256"]
            )
            if not matches:
                raise ValueError(f"embedded bundle identity differs: {path}")
            bundle_content[path] = content
            with zipfile.ZipFile(io.BytesIO(content)) as nested:
                nested_names = nested.namelist()
                source_count = sum(
                    name.startswith("OSGI-OPT/src/") and name.endswith(".java")
                    for name in nested_names
                )
                nested_manifest = _parse_manifest(nested.read("META-INF/MANIFEST.MF"))
            bundle_rows.append(
                {
                    "path": path,
                    "bytes": len(content),
                    "sha256": _bytes_sha256(content),
                    "bundle_symbolic_name": nested_manifest.get("Bundle-SymbolicName", ""),
                    "bundle_version": nested_manifest.get("Bundle-Version", ""),
                    "embedded_java_sources": source_count,
                    "matches": True,
                }
            )

        source_rows: list[dict[str, Any]] = []
        for value in jar_spec["embedded_source_checks"]:
            check = _mapping(value, "embedded source check")
            bundle_path = str(check["bundle_path"])
            source_path = str(check["source_path"])
            content = bundle_content.get(bundle_path)
            if content is None:
                content = outer.read(bundle_path)
            with zipfile.ZipFile(io.BytesIO(content)) as nested:
                if source_path not in nested.namelist():
                    raise ValueError(f"embedded source is missing: {source_path}")
                source_bytes = nested.read(source_path)
            source_text = source_bytes.decode("utf-8")
            markers = _string_list(check["markers"], "embedded source markers")
            missing_markers = [marker for marker in markers if marker not in source_text]
            if missing_markers:
                raise ValueError(
                    f"embedded source markers differ for {check['id']}: {missing_markers}"
                )
            source_rows.append(
                {
                    "id": check["id"],
                    "bundle_path": bundle_path,
                    "source_path": source_path,
                    "bytes": len(source_bytes),
                    "sha256": _bytes_sha256(source_bytes),
                    "marker_count": len(markers),
                    "matches": True,
                }
            )

        lower_names = [name.lower() for name in names]
        top_level_build = sorted(
            name
            for name in names
            if "/" not in name.rstrip("/")
            and name.lower() in {"pom.xml", "build.gradle", "build.gradle.kts", "bnd.bnd"}
        )
        license_entries = sorted(
            name
            for name, lower in zip(names, lower_names)
            if re.search(r"(^|/)(license|notice|copying)(\.|$)", lower)
        )
        inventory = {
            "path": jar_path.name,
            "bytes": jar_path.stat().st_size,
            "sha256": file_sha256(jar_path),
            "git_blob": record["git_blob"],
            "entry_count": len(names),
            "main_class": outer_manifest.get("Main-Class"),
            "bundle_version": outer_manifest.get("Bundle-Version"),
            "pcm_bundle": jar_spec["pcm_bundle"],
            "embedded_source_checks_passed": len(source_rows),
            "top_level_build_descriptors": top_level_build,
            "license_entries": license_entries,
            "standalone_later_source_build_complete": bool(top_level_build),
        }
    return bundle_rows, source_rows, inventory


def record_pmx_probe(
    config_path: Path,
    demonstration_root: Path,
    execution_root: Path,
    control_manifest_path: Path,
    java_version_path: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_performability_config(config_path)
    out.mkdir(parents=True, exist_ok=True)
    jar_path = demonstration_root / "main.jar"

    input_rows: list[dict[str, Any]] = []
    for value in config.raw["demonstration"]["files"]:
        record = _mapping(value, "demonstration file")
        relative = str(record["path"])
        input_rows.append(
            _audit_regular_file(
                demonstration_root / relative,
                record,
                f"probe input {relative}",
            )
        )

    bundle_rows, source_rows, jar_inventory = audit_pmx_jar(config, jar_path)
    control_manifest = _mapping(
        _load_json(control_manifest_path, "control manifest"), "control manifest"
    )
    if control_manifest.get("config_sha256") != file_sha256(config_path):
        raise ValueError("control manifest config hash differs")
    if control_manifest.get("expected_failure_probability") != 0.1:
        raise ValueError("control manifest oracle differs")

    execution_rows: list[dict[str, Any]] = []
    run_records: list[dict[str, Any]] = []
    for condition_value in config.raw["conditions"]:
        condition = _mapping(condition_value, "condition")
        condition_id = str(condition["id"])
        for repeat in range(1, config.repeat_count + 1):
            run_id = f"{condition_id}/repeat-{repeat}"
            run_root = execution_root / condition_id / f"repeat-{repeat}"
            exit_path = run_root / "exit-code.txt"
            stdout_path = run_root / "stdout.log"
            resource_path = run_root / "resource-usage.txt"
            results_root = run_root / "results"
            for required in (exit_path, stdout_path, resource_path):
                if not required.is_file():
                    raise ValueError(f"{run_id}: missing {required.name}")
            if not results_root.is_dir():
                raise ValueError(f"{run_id}: missing results directory")
            try:
                exit_code = int(exit_path.read_text(encoding="utf-8").strip())
            except ValueError as error:
                raise ValueError(f"{run_id}: invalid exit code") from error
            result_files = sorted(path for path in results_root.rglob("*") if path.is_file())
            core_suffixes = sorted(
                {path.suffix.lower() for path in result_files if path.suffix.lower() in _MODEL_SUFFIXES}
            )
            for path in sorted(path for path in run_root.rglob("*") if path.is_file()):
                relative = path.relative_to(execution_root).as_posix()
                execution_rows.append(
                    {
                        "condition": condition_id,
                        "repeat": repeat,
                        "path": relative,
                        "bytes": path.stat().st_size,
                        "sha256": file_sha256(path),
                        "suffix": path.suffix.lower(),
                        "is_result": results_root in path.parents,
                    }
                )
            stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
            tool_log = results_root / "log.txt"
            tool_text = (
                tool_log.read_text(encoding="utf-8", errors="replace")
                if tool_log.is_file()
                else ""
            )
            run_records.append(
                {
                    "condition": condition_id,
                    "repeat": repeat,
                    "run_id": run_id,
                    "exit_code": exit_code,
                    "result_files": len(result_files),
                    "core_model_suffixes": core_suffixes,
                    "stdout_sha256": file_sha256(stdout_path),
                    "resource_usage_sha256": file_sha256(resource_path),
                    "tool_log_present": tool_log.is_file(),
                    "major_error_mentions": len(
                        re.findall(r"major[_ ]error|MAJOR_ERROR", stdout_text + tool_text, re.I)
                    ),
                    "exception_mentions": len(
                        re.findall(r"exception|error while", stdout_text + tool_text, re.I)
                    ),
                }
            )

    _write_csv(
        out / "downloaded-input-audit.csv",
        (
            "path",
            "expected_bytes",
            "actual_bytes",
            "expected_sha256",
            "actual_sha256",
            "matches",
        ),
        input_rows,
    )
    _write_csv(
        out / "embedded-bundle-audit.csv",
        (
            "path",
            "bytes",
            "sha256",
            "bundle_symbolic_name",
            "bundle_version",
            "embedded_java_sources",
            "matches",
        ),
        bundle_rows,
    )
    _write_csv(
        out / "embedded-source-audit.csv",
        (
            "id",
            "bundle_path",
            "source_path",
            "bytes",
            "sha256",
            "marker_count",
            "matches",
        ),
        source_rows,
    )
    _write_csv(
        out / "execution-files.csv",
        ("condition", "repeat", "path", "bytes", "sha256", "suffix", "is_result"),
        execution_rows,
    )
    _write_json(out / "jar-inventory.json", dict(jar_inventory))
    _write_json(out / "run-records.json", {"runs": run_records})
    copied_control = out / "control-manifest.json"
    _write_json(copied_control, dict(control_manifest))
    copied_java = out / "java-version.txt"
    copied_java.write_bytes(java_version_path.read_bytes())

    derived_files = (
        "downloaded-input-audit.csv",
        "embedded-bundle-audit.csv",
        "embedded-source-audit.csv",
        "execution-files.csv",
        "jar-inventory.json",
        "run-records.json",
        "control-manifest.json",
        "java-version.txt",
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9f_pmx_headless_probe",
        "status": "headless_probe_recorded",
        "config_sha256": file_sha256(config_path),
        "jar": jar_inventory,
        "embedded_bundles": len(bundle_rows),
        "embedded_source_checks": len(source_rows),
        "runs": run_records,
        "run_count": len(run_records),
        "expected_run_count": len(config.raw["conditions"]) * config.repeat_count,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "files": {name: file_sha256(out / name) for name in derived_files},
        "environment": environment_manifest(),
    }
    _write_json(out / "probe-manifest.json", manifest)
    return manifest


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def summarize_pcm_results(results_root: Path) -> Mapping[str, Any]:
    files = sorted(path for path in results_root.rglob("*") if path.is_file())
    model_files = [path for path in files if path.suffix.lower() in _MODEL_SUFFIXES]
    suffixes = sorted({path.suffix.lower() for path in model_files})
    tag_counts: Counter[str] = Counter()
    entity_names: set[str] = set()
    failure_rows: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    text_by_suffix: dict[str, str] = {}

    for path in model_files:
        suffix = path.suffix.lower()
        text = path.read_text(encoding="utf-8", errors="replace")
        text_by_suffix[suffix] = text_by_suffix.get(suffix, "") + "\n" + text
        try:
            tree = ElementTree.parse(path)
        except ElementTree.ParseError:
            parse_errors.append(path.name)
            continue
        for element in tree.iter():
            tag_counts[_local_name(element.tag)] += 1
            for attribute, value in element.attrib.items():
                local_attribute = _local_name(attribute)
                if local_attribute == "entityName":
                    entity_names.add(value)
                if local_attribute.lower() == "failureprobability":
                    try:
                        numeric = float(value)
                    except ValueError:
                        numeric = math.nan
                    failure_rows.append(
                        {
                            "path": path.name,
                            "suffix": suffix,
                            "value": value,
                            "numeric_value": numeric,
                            "nonzero": math.isfinite(numeric) and numeric > 0.0,
                        }
                    )

    combined = "\n".join(text_by_suffix.values())
    token_markers = {
        "resource_demanding_seff": "ResourceDemandingSEFF",
        "external_call_action": "ExternalCallAction",
        "internal_action": "InternalAction",
        "entry_level_system_call": "EntryLevelSystemCall",
        "internal_failure_occurrence": "InternalFailureOccurrenceDescription",
        "software_induced_failure_type": "SoftwareInducedFailureType",
        "allocation_context": "AllocationContext",
        "linking_resource": "LinkingResource",
        "mttf": "MTTF",
        "mttr": "MTTR",
    }
    token_counts = {
        key: len(re.findall(re.escape(marker), combined, re.I))
        for key, marker in token_markers.items()
    }
    nonzero_repository = sorted(
        float(row["numeric_value"])
        for row in failure_rows
        if row["suffix"] == ".repository" and row["nonzero"]
    )
    nonzero_links = sorted(
        float(row["numeric_value"])
        for row in failure_rows
        if row["suffix"] == ".resourceenvironment" and row["nonzero"]
    )
    signature_payload = {
        "suffixes": suffixes,
        "parse_errors": sorted(parse_errors),
        "tag_counts": dict(sorted(tag_counts.items())),
        "entity_names": sorted(entity_names),
        "failure_values": sorted(
            (str(row["suffix"]), str(row["value"])) for row in failure_rows
        ),
        "token_counts": token_counts,
    }
    signature = _bytes_sha256(
        json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode()
    )
    return {
        "result_files": len(files),
        "model_files": len(model_files),
        "core_suffixes": suffixes,
        "missing_core_suffixes": sorted(_MODEL_SUFFIXES - set(suffixes)),
        "parse_errors": sorted(parse_errors),
        "tag_counts": dict(sorted(tag_counts.items())),
        "entity_names": sorted(entity_names),
        "failure_rows": failure_rows,
        "nonzero_repository_failure_probabilities": nonzero_repository,
        "nonzero_link_failure_probabilities": nonzero_links,
        "token_counts": token_counts,
        "semantic_signature": signature,
    }


def _verify_probe_files(probe_root: Path, manifest: Mapping[str, Any]) -> None:
    files = _mapping(manifest.get("files"), "probe manifest files")
    for name, expected in files.items():
        path = probe_root / str(name)
        if not path.is_file() or file_sha256(path) != expected:
            raise ValueError(f"probe derived file differs: {name}")
    inventory_path = probe_root / "execution-files.csv"
    with inventory_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        relative = _relative_path(row["path"], "execution inventory path")
        path = probe_root / "raw" / relative
        if not path.is_file():
            raise ValueError(f"recorded execution file is missing: {relative}")
        if path.stat().st_size != int(row["bytes"]) or file_sha256(path) != row["sha256"]:
            raise ValueError(f"recorded execution file differs: {relative}")


def audit_pmx_probe(
    config_path: Path,
    contract_manifest_path: Path,
    probe_root: Path,
    out: Path,
) -> Mapping[str, Any]:
    config = load_pmx_performability_config(config_path)
    config_sha = file_sha256(config_path)
    contract = _mapping(
        _load_json(contract_manifest_path, "contract manifest"), "contract manifest"
    )
    if contract.get("status") != "provenance_contract_passed":
        raise ValueError("M9F provenance contract did not pass")
    if contract.get("config_sha256") != config_sha:
        raise ValueError("contract config hash differs")
    probe_manifest_path = probe_root / "probe-manifest.json"
    probe = _mapping(_load_json(probe_manifest_path, "probe manifest"), "probe manifest")
    if probe.get("status") != "headless_probe_recorded":
        raise ValueError("M9F headless probe is incomplete")
    if probe.get("config_sha256") != config_sha:
        raise ValueError("probe config hash differs")
    expected_runs = len(config.raw["conditions"]) * config.repeat_count
    if probe.get("run_count") != expected_runs:
        raise ValueError("probe run count differs")
    _verify_probe_files(probe_root, probe)

    records_payload = _mapping(_load_json(probe_root / "run-records.json", "run records"), "run records")
    records = _sequence(records_payload.get("runs"), "run records.runs")
    record_by_id = {
        str(_mapping(record, "run record")["run_id"]): _mapping(record, "run record")
        for record in records
    }
    summaries: dict[str, Mapping[str, Any]] = {}
    run_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    for condition_value in config.raw["conditions"]:
        condition = _mapping(condition_value, "condition")
        condition_id = str(condition["id"])
        for repeat in range(1, config.repeat_count + 1):
            run_id = f"{condition_id}/repeat-{repeat}"
            record = record_by_id.get(run_id)
            if record is None:
                raise ValueError(f"missing run record: {run_id}")
            results_root = probe_root / "raw" / condition_id / f"repeat-{repeat}" / "results"
            summary = summarize_pcm_results(results_root)
            summaries[run_id] = summary
            required_present = not summary["missing_core_suffixes"]
            parseable = not summary["parse_errors"]
            run_rows.append(
                {
                    "condition": condition_id,
                    "repeat": repeat,
                    "exit_code": record["exit_code"],
                    "result_files": summary["result_files"],
                    "model_files": summary["model_files"],
                    "required_core_files_present": required_present,
                    "xml_parseable": parseable,
                    "nonzero_repository_failure_count": len(
                        summary["nonzero_repository_failure_probabilities"]
                    ),
                    "nonzero_link_failure_count": len(
                        summary["nonzero_link_failure_probabilities"]
                    ),
                    "semantic_signature": summary["semantic_signature"],
                    "major_error_mentions": record["major_error_mentions"],
                    "exception_mentions": record["exception_mentions"],
                }
            )
            for failure in summary["failure_rows"]:
                failure_rows.append(
                    {
                        "condition": condition_id,
                        "repeat": repeat,
                        **failure,
                    }
                )

    consistency_rows: list[dict[str, Any]] = []
    condition_consistency: dict[str, bool] = {}
    for condition_value in config.raw["conditions"]:
        condition_id = str(_mapping(condition_value, "condition")["id"])
        condition_summaries = [
            summaries[f"{condition_id}/repeat-{repeat}"]
            for repeat in range(1, config.repeat_count + 1)
        ]
        signatures = [str(summary["semantic_signature"]) for summary in condition_summaries]
        consistent = len(set(signatures)) == 1
        condition_consistency[condition_id] = consistent
        consistency_rows.append(
            {
                "condition": condition_id,
                "repeats": config.repeat_count,
                "semantic_signatures": ";".join(signatures),
                "semantic_repeat_consistent": consistent,
            }
        )

    original_runs = [
        row for row in run_rows if row["condition"] == "published_original"
    ]
    control_runs = [
        row for row in run_rows if row["condition"] == "single_error_control"
    ]
    published_binary_reproduced = all(
        row["exit_code"] == 0
        and row["required_core_files_present"]
        and row["xml_parseable"]
        and row["major_error_mentions"] == 0
        for row in original_runs
    ) and condition_consistency["published_original"]

    control_spec = next(
        _mapping(item, "control")
        for item in config.raw["conditions"]
        if _mapping(item, "condition").get("id") == "single_error_control"
    )
    expected_probability = float(control_spec["expected_failure_probability"])
    tolerance = float(control_spec["absolute_tolerance"])
    control_probability_passes: list[bool] = []
    control_structure_passes: list[bool] = []
    for repeat in range(1, config.repeat_count + 1):
        summary = summaries[f"single_error_control/repeat-{repeat}"]
        probabilities = summary["nonzero_repository_failure_probabilities"]
        control_probability_passes.append(
            any(abs(float(value) - expected_probability) <= tolerance for value in probabilities)
        )
        token_counts = _mapping(summary["token_counts"], "token counts")
        control_structure_passes.append(
            int(token_counts["internal_failure_occurrence"]) > 0
            and int(token_counts["software_induced_failure_type"]) > 0
        )
    operation_failure_mechanism_reproduced = (
        published_binary_reproduced
        and all(
            row["exit_code"] == 0
            and row["required_core_files_present"]
            and row["xml_parseable"]
            and row["major_error_mentions"] == 0
            for row in control_runs
        )
        and condition_consistency["single_error_control"]
        and all(control_probability_passes)
        and all(control_structure_passes)
    )

    first_original = summaries["published_original/repeat-1"]
    original_tokens = _mapping(first_original["token_counts"], "original tokens")
    architecture_demonstrated = published_binary_reproduced and (
        int(original_tokens["resource_demanding_seff"]) > 0
        and int(original_tokens["internal_action"]) > 0
        and int(original_tokens["entry_level_system_call"]) > 0
    )
    any_mttf_mttr = any(
        int(_mapping(summary["token_counts"], "token counts")["mttf"]) > 0
        and int(_mapping(summary["token_counts"], "token counts")["mttr"]) > 0
        for summary in summaries.values()
    )
    any_nonzero_link = any(
        bool(summary["nonzero_link_failure_probabilities"])
        for summary in summaries.values()
    )

    dimension_specs = {
        str(_mapping(item, "semantic dimension")["id"]): _mapping(
            item, "semantic dimension"
        )
        for item in config.raw["semantic_dimensions"]
    }
    dimension_status = {
        "trace_ingestion": (
            "demonstrated_on_authors_jaeger_shaped_example_adapter_required_for_m7"
            if published_binary_reproduced
            else "not_demonstrated_by_remote_execution"
        ),
        "architecture_operation_flow": (
            "demonstrated_on_authors_spring_example_application_adapter_required"
            if architecture_demonstrated
            else "not_demonstrated_by_generated_pcm"
        ),
        "software_operation_failure": (
            "one_in_ten_error_tag_mechanism_reproduced"
            if operation_failure_mechanism_reproduced
            else "mechanism_not_reproduced"
        ),
        "host_lifecycle": (
            "values_present_not_attributed_to_extraction"
            if any_mttf_mttr
            else "not_demonstrated"
        ),
        "communication_failure": (
            "nonzero_value_present_requires_provenance_audit"
            if any_nonzero_link
            else "not_demonstrated_zero_default_in_embedded_source"
        ),
        "replication": "not_demonstrated_component_multiplicity_is_not_redundancy",
        "common_failure_domains": "not_demonstrated",
        "external_client_success": "not_demonstrated_span_error_is_not_full_client_contract",
    }
    semantic_rows: list[dict[str, Any]] = []
    required_work_rows: list[dict[str, Any]] = []
    for dimension in sorted(_SEMANTIC_DIMENSIONS):
        status = dimension_status[dimension]
        spec = dimension_specs[dimension]
        demonstrated = status.startswith("demonstrated") or status.startswith("one_in_ten")
        semantic_rows.append(
            {
                "dimension": dimension,
                "status": status,
                "demonstrated_on_authors_example_or_control": demonstrated,
                "ready_for_m7_without_adapter": False,
                "absence_demotes_scientific_priority": False,
            }
        )
        required_work_rows.append(
            {
                "dimension": dimension,
                "status": status,
                "required_work": spec["required_work_if_absent"],
                "cost_classification": "application_or_integration_cost",
                "scientific_priority_retained": True,
            }
        )

    jar_inventory = _mapping(
        _load_json(probe_root / "jar-inventory.json", "jar inventory"),
        "jar inventory",
    )
    embedded_source_snapshot = probe.get("embedded_source_checks") == 7
    standalone_source_build = bool(jar_inventory["standalone_later_source_build_complete"])
    container_chain = bool(contract["exact_historical_container_chain_recoverable"])
    reproducibility_rows = [
        {"stage": "paper", "reproduced": True, "classification": "byte_pinned"},
        {
            "stage": "historical_source_lineage",
            "reproduced": contract.get("historical_source_files") == 8,
            "classification": "two_commits_and_canonical_blobs_audited",
        },
        {
            "stage": "later_embedded_source_snapshot",
            "reproduced": embedded_source_snapshot,
            "classification": "embedded_osgi_opt_source_markers_audited",
        },
        {
            "stage": "later_standalone_source_build",
            "reproduced": standalone_source_build,
            "classification": (
                "build_descriptor_present"
                if standalone_source_build
                else "embedded_source_without_standalone_build_descriptor"
            ),
        },
        {
            "stage": "headless_binary_extraction",
            "reproduced": published_binary_reproduced,
            "classification": "authors_example_two_run_semantic_check",
        },
        {
            "stage": "operation_failure_mechanism",
            "reproduced": operation_failure_mechanism_reproduced,
            "classification": "predeclared_one_in_ten_error_tag_control",
        },
        {
            "stage": "historical_full_container_chain",
            "reproduced": container_chain,
            "classification": (
                "exact_digest_chain_available"
                if container_chain
                else "mutable_latest_without_historical_digest"
            ),
        },
    ]

    if published_binary_reproduced and operation_failure_mechanism_reproduced:
        status = "pmx_binary_and_failure_mechanism_reproduced_application_adapter_audit_required"
        next_milestone = "m9g_pmx_application_adapter_and_information_cost"
    elif published_binary_reproduced:
        status = "pmx_binary_reproduced_failure_mechanism_not_demonstrated"
        next_milestone = "m9g_pmx_failure_mechanism_and_application_adapter"
    else:
        status = "pmx_public_binary_execution_not_reproduced"
        next_milestone = "m9g_pmx_recovery_and_application_adapter_dual_track"

    out.mkdir(parents=True, exist_ok=True)
    _write_csv(
        out / "run-summary.csv",
        (
            "condition",
            "repeat",
            "exit_code",
            "result_files",
            "model_files",
            "required_core_files_present",
            "xml_parseable",
            "nonzero_repository_failure_count",
            "nonzero_link_failure_count",
            "semantic_signature",
            "major_error_mentions",
            "exception_mentions",
        ),
        run_rows,
    )
    _write_csv(
        out / "failure-probabilities.csv",
        (
            "condition",
            "repeat",
            "path",
            "suffix",
            "value",
            "numeric_value",
            "nonzero",
        ),
        failure_rows,
    )
    _write_csv(
        out / "repeat-consistency.csv",
        (
            "condition",
            "repeats",
            "semantic_signatures",
            "semantic_repeat_consistent",
        ),
        consistency_rows,
    )
    _write_csv(
        out / "semantic-fit.csv",
        (
            "dimension",
            "status",
            "demonstrated_on_authors_example_or_control",
            "ready_for_m7_without_adapter",
            "absence_demotes_scientific_priority",
        ),
        semantic_rows,
    )
    _write_csv(
        out / "required-work.csv",
        (
            "dimension",
            "status",
            "required_work",
            "cost_classification",
            "scientific_priority_retained",
        ),
        required_work_rows,
    )
    _write_csv(
        out / "reproducibility.csv",
        ("stage", "reproduced", "classification"),
        reproducibility_rows,
    )
    details = {
        "summaries": summaries,
        "control_probability_passes": control_probability_passes,
        "control_structure_passes": control_structure_passes,
    }
    _write_json(out / "semantic-details.json", details)

    output_files = (
        "run-summary.csv",
        "failure-probabilities.csv",
        "repeat-consistency.csv",
        "semantic-fit.csv",
        "required-work.csv",
        "reproducibility.csv",
        "semantic-details.json",
    )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "m9f_pmx_performability_decision",
        "status": status,
        "technical_evidence_accepted": True,
        "config_sha256": config_sha,
        "contract_manifest_sha256": file_sha256(contract_manifest_path),
        "probe_manifest_sha256": file_sha256(probe_manifest_path),
        "published_binary_extraction_reproduced": published_binary_reproduced,
        "operation_failure_mechanism_reproduced": operation_failure_mechanism_reproduced,
        "expected_control_failure_probability": expected_probability,
        "control_probability_passes": control_probability_passes,
        "repeat_consistency": condition_consistency,
        "embedded_source_snapshot_audited": embedded_source_snapshot,
        "later_standalone_source_build_reproduced": standalone_source_build,
        "exact_historical_container_chain_reproduced": container_chain,
        "semantic_dimensions": semantic_rows,
        "next_milestone": next_milestone,
        "pmx_scientific_priority_retained": True,
        "missing_support_classified_as_application_cost": True,
        "tested_binary_represents_all_pmx": False,
        "tested_binary_represents_all_palladio": False,
        "accuracy_scoring_started": False,
        "new_live_collection_authorized": False,
        "m7_interpretation_changed": False,
        "files": {name: file_sha256(out / name) for name in output_files},
        "environment": environment_manifest(),
    }
    _write_json(out / "decision-manifest.json", manifest)
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pmx-performability")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("--config", required=True, type=Path)

    contract = commands.add_parser("audit-contract")
    contract.add_argument("--config", required=True, type=Path)
    contract.add_argument("--repository-root", required=True, type=Path)
    contract.add_argument("--paper", required=True, type=Path)
    contract.add_argument("--historical-root", required=True, type=Path)
    contract.add_argument("--demonstration-root", required=True, type=Path)
    contract.add_argument("--project-metadata", required=True, type=Path)
    contract.add_argument("--commit-metadata", required=True, type=Path)
    contract.add_argument("--pipeline-metadata", required=True, type=Path)
    contract.add_argument("--jobs-metadata", required=True, type=Path)
    contract.add_argument("--tree-metadata", required=True, type=Path)
    contract.add_argument("--registry-root", required=True, type=Path)
    contract.add_argument("--out", required=True, type=Path)

    control = commands.add_parser("make-error-control")
    control.add_argument("--config", required=True, type=Path)
    control.add_argument("--demonstration-root", required=True, type=Path)
    control.add_argument("--output-trace", required=True, type=Path)
    control.add_argument("--output-options", required=True, type=Path)
    control.add_argument("--manifest", required=True, type=Path)

    record = commands.add_parser("record-probe")
    record.add_argument("--config", required=True, type=Path)
    record.add_argument("--demonstration-root", required=True, type=Path)
    record.add_argument("--execution-root", required=True, type=Path)
    record.add_argument("--control-manifest", required=True, type=Path)
    record.add_argument("--java-version", required=True, type=Path)
    record.add_argument("--out", required=True, type=Path)

    audit = commands.add_parser("audit-probe")
    audit.add_argument("--config", required=True, type=Path)
    audit.add_argument("--contract-manifest", required=True, type=Path)
    audit.add_argument("--probe-root", required=True, type=Path)
    audit.add_argument("--out", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "validate":
        config = load_pmx_performability_config(args.config)
        result: Mapping[str, Any] = {
            "status": "valid",
            "experiment_id": config.id,
            "role": "pmx_performability_reproducibility_and_semantic_fit",
            "job_timeout_minutes": config.job_timeout_minutes,
            "pmx_internal_timeout_seconds": config.internal_timeout_seconds,
            "repeat_count_per_condition": config.repeat_count,
            "accuracy_scoring": "forbidden",
            "new_live_collection": "forbidden",
            "pmx_scientific_priority_retained": True,
        }
    elif args.command == "audit-contract":
        result = audit_pmx_contract(
            args.config,
            args.repository_root,
            args.paper,
            args.historical_root,
            args.demonstration_root,
            args.project_metadata,
            args.commit_metadata,
            args.pipeline_metadata,
            args.jobs_metadata,
            args.tree_metadata,
            args.registry_root,
            args.out,
        )
    elif args.command == "make-error-control":
        result = create_error_control(
            args.config,
            args.demonstration_root,
            args.output_trace,
            args.output_options,
            args.manifest,
        )
    elif args.command == "record-probe":
        result = record_pmx_probe(
            args.config,
            args.demonstration_root,
            args.execution_root,
            args.control_manifest,
            args.java_version,
            args.out,
        )
    elif args.command == "audit-probe":
        result = audit_pmx_probe(
            args.config,
            args.contract_manifest,
            args.probe_root,
            args.out,
        )
    else:
        raise AssertionError(f"unhandled command {args.command}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
