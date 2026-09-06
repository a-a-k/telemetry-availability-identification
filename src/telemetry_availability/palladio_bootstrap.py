from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


@dataclass(frozen=True)
class PalladioSourceLock:
    repository: str
    release_tag: str
    commit: str
    bundle_version: str


@dataclass(frozen=True)
class PalladioExampleLock:
    repository: str
    commit: str
    project_path: str
    repeat_runs: int
    expected_success_probability: float | None
    probability_tolerance: float


@dataclass(frozen=True)
class PalladioFileLock:
    relative_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class PalladioTargetPlatformLock:
    coordinate: str
    artifact_url: str
    artifact_bytes: int
    original_sha256: str
    mutable_repository_url: str
    pinned_repository_url: str
    patched_sha256: str
    historical_basis: str
    repository_evidence: tuple[PalladioFileLock, ...]


@dataclass(frozen=True)
class PalladioProductLock:
    url: str
    expected_bytes: int
    sha256: str | None
    required_feature_id: str
    required_solver_bundle_id: str


@dataclass(frozen=True)
class PalladioRuntimeLock:
    java_distribution: str
    java_version: int
    job_timeout_minutes: int
    remote_only: bool


@dataclass(frozen=True)
class PalladioBootstrapConfig:
    schema_version: int
    id: str
    diagnostic_only: bool
    analyzer: PalladioSourceLock
    target_platform_lock: PalladioTargetPlatformLock
    official_example: PalladioExampleLock
    product: PalladioProductLock
    runtime: PalladioRuntimeLock

    @property
    def acceptance_ready(self) -> bool:
        return (
            self.product.sha256 is not None
            and self.official_example.expected_success_probability is not None
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _commit(data: Mapping[str, Any], key: str, label: str) -> str:
    value = _required_string(data, key, label)
    if not _COMMIT_RE.fullmatch(value):
        raise ValueError(f"{label}.{key} must be a full lowercase Git commit")
    return value


def _sha256_string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = _required_string(data, key, label)
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{label}.{key} must be a lowercase SHA-256")
    return value


def _positive_integer(data: Mapping[str, Any], key: str, label: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label}.{key} must be a positive integer")
    return value


def load_palladio_bootstrap_config(path: Path) -> PalladioBootstrapConfig:
    with path.open("r", encoding="utf-8") as handle:
        root = _mapping(json.load(handle), "root")

    if root.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    experiment_id = _required_string(root, "id", "root")
    if root.get("diagnostic_only") is not True:
        raise ValueError("M9A must remain diagnostic_only")

    analyzer_data = _mapping(root.get("analyzer"), "analyzer")
    analyzer_version = _required_string(
        analyzer_data, "bundle_version", "analyzer"
    )
    if not _VERSION_RE.fullmatch(analyzer_version):
        raise ValueError("analyzer.bundle_version must be a semantic version")
    analyzer = PalladioSourceLock(
        repository=_required_string(analyzer_data, "repository", "analyzer"),
        release_tag=_required_string(analyzer_data, "release_tag", "analyzer"),
        commit=_commit(analyzer_data, "commit", "analyzer"),
        bundle_version=analyzer_version,
    )
    if analyzer.repository != (
        "https://github.com/PalladioSimulator/"
        "Palladio-Analyzer-Reliability.git"
    ):
        raise ValueError("analyzer.repository must be the official repository")
    if analyzer.release_tag != f"releases/{analyzer.bundle_version}":
        raise ValueError("analyzer release tag and bundle version disagree")

    target_data = _mapping(root.get("target_platform_lock"), "target_platform_lock")
    evidence_data = target_data.get("repository_evidence")
    if not isinstance(evidence_data, list) or not evidence_data:
        raise ValueError("target_platform_lock.repository_evidence must be non-empty")
    repository_evidence: list[PalladioFileLock] = []
    seen_evidence_paths: set[str] = set()
    for index, raw_lock in enumerate(evidence_data):
        label = f"target_platform_lock.repository_evidence[{index}]"
        lock_data = _mapping(raw_lock, label)
        relative_path = _required_string(lock_data, "relative_path", label)
        path_parts = Path(relative_path).parts
        if (
            Path(relative_path).is_absolute()
            or ".." in path_parts
            or relative_path in seen_evidence_paths
        ):
            raise ValueError(f"{label}.relative_path must be unique and relative")
        seen_evidence_paths.add(relative_path)
        repository_evidence.append(
            PalladioFileLock(
                relative_path=relative_path,
                bytes=_positive_integer(lock_data, "bytes", label),
                sha256=_sha256_string(lock_data, "sha256", label),
            )
        )
    target_platform_lock = PalladioTargetPlatformLock(
        coordinate=_required_string(target_data, "coordinate", "target_platform_lock"),
        artifact_url=_required_string(
            target_data, "artifact_url", "target_platform_lock"
        ),
        artifact_bytes=_positive_integer(
            target_data, "artifact_bytes", "target_platform_lock"
        ),
        original_sha256=_sha256_string(
            target_data, "original_sha256", "target_platform_lock"
        ),
        mutable_repository_url=_required_string(
            target_data, "mutable_repository_url", "target_platform_lock"
        ),
        pinned_repository_url=_required_string(
            target_data, "pinned_repository_url", "target_platform_lock"
        ),
        patched_sha256=_sha256_string(
            target_data, "patched_sha256", "target_platform_lock"
        ),
        historical_basis=_required_string(
            target_data, "historical_basis", "target_platform_lock"
        ),
        repository_evidence=tuple(repository_evidence),
    )
    if target_platform_lock.coordinate != (
        "org.palladiosimulator:palladio-target-platforms:"
        "0.1.0:target:palladio-2023-03"
    ):
        raise ValueError("target-platform coordinate must remain the upstream one")
    if target_platform_lock.artifact_url != (
        "https://repo.maven.apache.org/maven2/org/palladiosimulator/"
        "palladio-target-platforms/0.1.0/"
        "palladio-target-platforms-0.1.0-palladio-2023-03.target"
    ):
        raise ValueError("target-platform artifact URL must be the official Maven URL")
    if target_platform_lock.mutable_repository_url != (
        "https://updatesite.mdsd.tools/ecore-workflow/releases/latest/"
    ):
        raise ValueError("unexpected mutable MDSD repository URL")
    if target_platform_lock.pinned_repository_url != (
        "https://updatesite.mdsd.tools/ecore-workflow/releases/1.0.0/"
    ):
        raise ValueError("MDSD Ecore Workflow must be historically pinned to 1.0.0")

    example_data = _mapping(root.get("official_example"), "official_example")
    expected_probability = example_data.get("expected_success_probability")
    if expected_probability is not None:
        if isinstance(expected_probability, bool) or not isinstance(
            expected_probability, (int, float)
        ):
            raise ValueError(
                "official_example.expected_success_probability must be numeric or null"
            )
        expected_probability = float(expected_probability)
        if not 0.0 <= expected_probability <= 1.0:
            raise ValueError(
                "official_example.expected_success_probability must be in [0,1]"
            )
    repeat_runs = example_data.get("repeat_runs")
    if isinstance(repeat_runs, bool) or not isinstance(repeat_runs, int):
        raise ValueError("official_example.repeat_runs must be an integer")
    if repeat_runs < 2:
        raise ValueError("official_example.repeat_runs must be at least two")
    tolerance = example_data.get("probability_tolerance")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise ValueError("official_example.probability_tolerance must be numeric")
    tolerance = float(tolerance)
    if not 0.0 < tolerance <= 1e-6:
        raise ValueError(
            "official_example.probability_tolerance must be in (0, 1e-6]"
        )
    example = PalladioExampleLock(
        repository=_required_string(example_data, "repository", "official_example"),
        commit=_commit(example_data, "commit", "official_example"),
        project_path=_required_string(
            example_data, "project_path", "official_example"
        ),
        repeat_runs=repeat_runs,
        expected_success_probability=expected_probability,
        probability_tolerance=tolerance,
    )
    if example.repository != (
        "https://github.com/PalladioSimulator/Palladio-Example-Models.git"
    ):
        raise ValueError("official_example.repository must be the official repository")

    product_data = _mapping(root.get("product"), "product")
    product_sha = product_data.get("sha256")
    if product_sha is not None and (
        not isinstance(product_sha, str) or not _SHA256_RE.fullmatch(product_sha)
    ):
        raise ValueError("product.sha256 must be a lowercase SHA-256 or null")
    product = PalladioProductLock(
        url=_required_string(product_data, "url", "product"),
        expected_bytes=_positive_integer(product_data, "expected_bytes", "product"),
        sha256=product_sha,
        required_feature_id=_required_string(
            product_data, "required_feature_id", "product"
        ),
        required_solver_bundle_id=_required_string(
            product_data, "required_solver_bundle_id", "product"
        ),
    )
    release_path = f"/releases/{analyzer.bundle_version}/"
    if not product.url.startswith(
        "https://updatesite.palladio-simulator.com/palladio-bench-product/"
    ) or release_path not in product.url:
        raise ValueError("product URL must be the versioned official release URL")
    if product.required_feature_id != "org.palladiosimulator.reliability.feature":
        raise ValueError("unexpected required reliability feature ID")
    if product.required_solver_bundle_id != (
        "org.palladiosimulator.reliability.solver"
    ):
        raise ValueError("unexpected required reliability solver bundle ID")

    runtime_data = _mapping(root.get("runtime"), "runtime")
    runtime = PalladioRuntimeLock(
        java_distribution=_required_string(
            runtime_data, "java_distribution", "runtime"
        ),
        java_version=int(runtime_data.get("java_version", 0)),
        job_timeout_minutes=int(runtime_data.get("job_timeout_minutes", 0)),
        remote_only=runtime_data.get("remote_only") is True,
    )
    if runtime.java_distribution != "temurin" or runtime.java_version != 17:
        raise ValueError("M9A is pinned to Temurin Java 17")
    if runtime.job_timeout_minutes != 360:
        raise ValueError("every M9A job must retain the 360-minute timeout")
    if not runtime.remote_only:
        raise ValueError("Palladio build and execution must remain remote-only")

    return PalladioBootstrapConfig(
        schema_version=1,
        id=experiment_id,
        diagnostic_only=True,
        analyzer=analyzer,
        target_platform_lock=target_platform_lock,
        official_example=example,
        product=product,
        runtime=runtime,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_head(checkout: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def apply_palladio_target_platform_lock(
    config_path: Path,
    target_file: Path,
    repository_evidence_dir: Path,
    output: Path,
) -> dict[str, Any]:
    """Replace one mutable upstream URL in Maven's cached target descriptor.

    The analyzer checkout is deliberately not changed.  The replacement
    reconstructs the external dependency state that existed when Palladio
    5.2.2 was published, and every byte used to justify that replacement is
    checked against the committed lock before the cached descriptor is edited.
    """

    config = load_palladio_bootstrap_config(config_path)
    lock = config.target_platform_lock
    if not target_file.is_file():
        raise ValueError("upstream Palladio target-platform artifact is missing")
    original_bytes = target_file.read_bytes()
    if len(original_bytes) != lock.artifact_bytes:
        raise ValueError(
            f"target-platform artifact has {len(original_bytes)} bytes, "
            f"expected {lock.artifact_bytes}"
        )
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    if original_sha != lock.original_sha256:
        raise ValueError(
            f"target-platform artifact SHA-256 is {original_sha}, expected "
            f"{lock.original_sha256}"
        )
    try:
        original_text = original_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("target-platform artifact is not UTF-8") from error
    replacement_count = original_text.count(lock.mutable_repository_url)
    if replacement_count != 1:
        raise ValueError(
            "target-platform artifact must contain the mutable repository URL once"
        )
    patched_bytes = original_text.replace(
        lock.mutable_repository_url, lock.pinned_repository_url
    ).encode("utf-8")
    patched_sha = hashlib.sha256(patched_bytes).hexdigest()
    if patched_sha != lock.patched_sha256:
        raise ValueError(
            f"patched target-platform SHA-256 is {patched_sha}, expected "
            f"{lock.patched_sha256}"
        )

    evidence: list[dict[str, Any]] = []
    for file_lock in lock.repository_evidence:
        evidence_path = repository_evidence_dir / file_lock.relative_path
        if not evidence_path.is_file():
            raise ValueError(
                f"pinned repository evidence is missing: {file_lock.relative_path}"
            )
        actual_bytes = evidence_path.stat().st_size
        actual_sha = _sha256(evidence_path)
        if actual_bytes != file_lock.bytes or actual_sha != file_lock.sha256:
            raise ValueError(
                "pinned repository evidence disagrees with its lock: "
                f"{file_lock.relative_path}"
            )
        evidence.append(
            {
                "relative_path": file_lock.relative_path,
                "bytes": actual_bytes,
                "sha256": actual_sha,
            }
        )

    target_file.write_bytes(patched_bytes)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "palladio_historical_target_platform_lock",
        "diagnostic_only": True,
        "coordinate": lock.coordinate,
        "artifact_url": lock.artifact_url,
        "original_artifact": {
            "bytes": len(original_bytes),
            "sha256": original_sha,
        },
        "replacement": {
            "from": lock.mutable_repository_url,
            "to": lock.pinned_repository_url,
            "count": replacement_count,
            "patched_sha256": patched_sha,
        },
        "historical_basis": lock.historical_basis,
        "repository_evidence": evidence,
        "analyzer_checkout_modified": False,
        "status": "historical_dependency_lock_applied",
    }
    _write_json(output, payload)
    return payload


def audit_palladio_source(
    config_path: Path, checkout: Path, build_log: Path, output: Path
) -> dict[str, Any]:
    config = load_palladio_bootstrap_config(config_path)
    head = _git_head(checkout)
    if head != config.analyzer.commit:
        raise ValueError(f"analyzer checkout is {head}, expected {config.analyzer.commit}")
    if not build_log.is_file() or build_log.stat().st_size == 0:
        raise ValueError("Palladio source build log is missing or empty")

    site = (
        checkout
        / "releng"
        / "org.palladiosimulator.reliability.updatesite"
        / "target"
        / "repository"
    )
    feature_name = (
        f"{config.product.required_feature_id}_"
        f"{config.analyzer.bundle_version}.jar"
    )
    solver_name = (
        f"{config.product.required_solver_bundle_id}_"
        f"{config.analyzer.bundle_version}.jar"
    )
    feature_matches = list(site.rglob(feature_name))
    solver_matches = list(site.rglob(solver_name))
    if len(feature_matches) != 1 or len(solver_matches) != 1:
        raise ValueError("built update site lacks the pinned feature or solver bundle")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "kind": "palladio_reliability_source_build",
        "diagnostic_only": True,
        "analyzer_repository": config.analyzer.repository,
        "analyzer_release_tag": config.analyzer.release_tag,
        "analyzer_commit": head,
        "bundle_version": config.analyzer.bundle_version,
        "build_log": {
            "bytes": build_log.stat().st_size,
            "sha256": _sha256(build_log),
        },
        "built_feature": {
            "relative_path": feature_matches[0].relative_to(checkout).as_posix(),
            "bytes": feature_matches[0].stat().st_size,
            "sha256": _sha256(feature_matches[0]),
        },
        "built_solver_bundle": {
            "relative_path": solver_matches[0].relative_to(checkout).as_posix(),
            "bytes": solver_matches[0].stat().st_size,
            "sha256": _sha256(solver_matches[0]),
        },
        "status": "source_build_passed",
    }
    _write_json(output, payload)
    return payload


def audit_palladio_product(
    config_path: Path, archive: Path, output: Path
) -> dict[str, Any]:
    config = load_palladio_bootstrap_config(config_path)
    if not archive.is_file():
        raise ValueError("Palladio product archive does not exist")
    actual_bytes = archive.stat().st_size
    actual_sha = _sha256(archive)
    if actual_bytes != config.product.expected_bytes:
        raise ValueError(
            f"product archive has {actual_bytes} bytes, expected "
            f"{config.product.expected_bytes}"
        )
    if config.product.sha256 is not None and actual_sha != config.product.sha256:
        raise ValueError(
            f"product archive SHA-256 is {actual_sha}, expected {config.product.sha256}"
        )

    expected_feature_stem = (
        f"{config.product.required_feature_id}_{config.analyzer.bundle_version}"
    )
    expected_solver_name = (
        f"{config.product.required_solver_bundle_id}_"
        f"{config.analyzer.bundle_version}.jar"
    )
    try:
        with ZipFile(archive) as product_zip:
            files = [name for name in product_zip.namelist() if not name.endswith("/")]
            jar_feature_paths = [
                name
                for name in files
                if Path(name).name == f"{expected_feature_stem}.jar"
            ]
            exploded_feature_paths = [
                name
                for name in files
                if Path(name).name == "feature.xml"
                and Path(name).parent.name == expected_feature_stem
            ]
            solver_paths = [
                name
                for name in files
                if Path(name).name == expected_solver_name
            ]
            feature_paths = jar_feature_paths + exploded_feature_paths
            reliability_paths = sorted(
                name
                for name in files
                if (
                    (
                        "plugins" in Path(name).parts
                        and Path(name).name.startswith(
                            "org.palladiosimulator.reliability"
                        )
                        and name.endswith(".jar")
                        and ".source_" not in name
                    )
                    or (
                        "features" in Path(name).parts
                        and (
                            Path(name).name == f"{expected_feature_stem}.jar"
                            or expected_feature_stem in Path(name).parts
                        )
                    )
                )
            )
            if len(feature_paths) != 1 or len(solver_paths) != 1:
                diagnostic_payload = {
                    "schema_version": 1,
                    "kind": "palladio_bench_product_audit",
                    "diagnostic_only": True,
                    "source_url": config.product.url,
                    "archive": {
                        "bytes": actual_bytes,
                        "sha256": actual_sha,
                        "expected_sha256": config.product.sha256,
                    },
                    "expected_feature_stem": expected_feature_stem,
                    "expected_solver_name": expected_solver_name,
                    "feature_candidates": feature_paths,
                    "solver_candidates": solver_paths,
                    "reliability_archive_candidates": reliability_paths,
                    "status": "bundle_inventory_mismatch",
                }
                _write_json(output, diagnostic_payload)
                raise ValueError(
                    "product archive lacks the exact pinned reliability feature or solver"
                )
            reliability_files = [
                {
                    "relative_path": name,
                    "bytes": product_zip.getinfo(name).file_size,
                    "sha256": hashlib.sha256(product_zip.read(name)).hexdigest(),
                }
                for name in reliability_paths
            ]
    except BadZipFile as error:
        raise ValueError("Palladio product archive is not a valid ZIP") from error

    pin_status = (
        "pinned_match"
        if config.product.sha256 is not None
        else "discovered_not_accepted"
    )
    payload = {
        "schema_version": 1,
        "kind": "palladio_bench_product_audit",
        "diagnostic_only": True,
        "source_url": config.product.url,
        "archive": {
            "bytes": actual_bytes,
            "sha256": actual_sha,
            "expected_sha256": config.product.sha256,
            "pin_status": pin_status,
        },
        "required_feature": {
            "relative_path": feature_paths[0],
            "packaging": "jar" if jar_feature_paths else "exploded",
        },
        "required_solver_bundle": solver_paths[0],
        "reliability_files": reliability_files,
        "status": pin_status,
    }
    _write_json(output, payload)
    return payload


def _derive_official_example_oracle(repository_path: Path) -> dict[str, Any]:
    """Evaluate the hand-checkable failure tree encoded by ReliabilityTest."""

    try:
        root = ET.parse(repository_path).getroot()
    except (ET.ParseError, OSError) as error:
        raise ValueError("official example repository is not valid XML") from error
    component = root.find("components__Repository")
    if component is None:
        raise ValueError("official example must contain one repository component")
    seff = component.find("serviceEffectSpecifications__BasicComponent")
    if seff is None:
        raise ValueError("official example must contain one reliability SEFF")
    xsi_type = "{http://www.w3.org/2001/XMLSchema-instance}type"
    direct_steps = list(seff.findall("steps_Behaviour"))
    direct_internal = [
        step for step in direct_steps if step.get(xsi_type) == "seff:InternalAction"
    ]
    recovery_steps = [
        step
        for step in direct_steps
        if step.get(xsi_type) == "seff_reliability:RecoveryAction"
    ]
    if len(direct_internal) != 1 or len(recovery_steps) != 1:
        raise ValueError(
            "official example oracle expects one initial action and one recovery action"
        )
    initial = direct_internal[0]
    recovery = recovery_steps[0]
    if (
        initial.get("successor_AbstractAction") != recovery.get("id")
        or recovery.get("predecessor_AbstractAction") != initial.get("id")
    ):
        raise ValueError("official example action sequence differs from the oracle")

    behaviours = list(
        recovery.findall("recoveryActionBehaviours__RecoveryAction")
    )
    if len(behaviours) != 2:
        raise ValueError("official example oracle expects two recovery behaviours")
    primary_id = recovery.get("primaryBehaviour__RecoveryAction")
    primary_matches = [item for item in behaviours if item.get("id") == primary_id]
    if len(primary_matches) != 1:
        raise ValueError("official example recovery primary is not unique")
    primary = primary_matches[0]
    alternatives = [item for item in behaviours if item is not primary]
    alternative = alternatives[0]
    alternative_ids = primary.get(
        "failureHandlingAlternatives__RecoveryActionBehaviour", ""
    ).split()
    if alternative_ids != [alternative.get("id")]:
        raise ValueError("official example recovery alternative differs from the oracle")
    if alternative.get(
        "failureHandlingAlternatives__RecoveryActionBehaviour", ""
    ).strip():
        raise ValueError("official example oracle expects exactly one fallback")

    def failure_probability(parent: ET.Element, label: str) -> tuple[float, str]:
        actions = [
            step
            for step in parent.findall("steps_Behaviour")
            if step.get(xsi_type) == "seff:InternalAction"
        ]
        if len(actions) != 1:
            raise ValueError(f"official example {label} must have one internal action")
        failures = list(
            actions[0].findall(
                "internalFailureOccurrenceDescriptions__InternalAction"
            )
        )
        if len(failures) != 1:
            raise ValueError(f"official example {label} must have one failure mode")
        probability = float(failures[0].get("failureProbability", "nan"))
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(f"official example {label} failure probability is invalid")
        failure_type = failures[0].get(
            "softwareInducedFailureType__InternalFailureOccurrenceDescription", ""
        )
        if not failure_type:
            raise ValueError(f"official example {label} failure type is missing")
        return probability, failure_type

    initial_failures = list(
        initial.findall("internalFailureOccurrenceDescriptions__InternalAction")
    )
    if len(initial_failures) != 1:
        raise ValueError("official example initial action must have one failure mode")
    initial_failure = float(initial_failures[0].get("failureProbability", "nan"))
    if not math.isfinite(initial_failure) or not 0.0 <= initial_failure <= 1.0:
        raise ValueError("official example initial failure probability is invalid")
    primary_failure, primary_failure_type = failure_probability(
        primary, "primary recovery"
    )
    alternative_failure, alternative_failure_type = failure_probability(
        alternative, "alternative recovery"
    )
    handled_types = alternative.get(
        "failureTypes_FailureHandlingEntity", ""
    ).split()
    if primary_failure_type not in handled_types:
        raise ValueError("official example fallback does not handle primary failure")
    recovery_success = (1.0 - primary_failure) + (
        primary_failure * (1.0 - alternative_failure)
    )
    success = (1.0 - initial_failure) * recovery_success
    return {
        "formula": (
            "(1-p_initial)*((1-p_primary)+"
            "p_primary*(1-p_alternative))"
        ),
        "initial_failure_probability": initial_failure,
        "primary_recovery_failure_probability": primary_failure,
        "primary_recovery_failure_type": primary_failure_type,
        "alternative_recovery_failure_probability": alternative_failure,
        "alternative_recovery_failure_type": alternative_failure_type,
        "success_probability": success,
    }


def audit_palladio_example(
    config_path: Path,
    result_path: Path,
    analyzer_checkout: Path,
    example_checkout: Path,
    output: Path,
) -> dict[str, Any]:
    config = load_palladio_bootstrap_config(config_path)
    if _git_head(analyzer_checkout) != config.analyzer.commit:
        raise ValueError("example run used an unexpected analyzer commit")
    if _git_head(example_checkout) != config.official_example.commit:
        raise ValueError("example run used an unexpected example-model commit")
    with result_path.open("r", encoding="utf-8") as handle:
        result = _mapping(json.load(handle), "official example result")
    repetitions = result.get("repetitions")
    if not isinstance(repetitions, list) or len(repetitions) != (
        config.official_example.repeat_runs
    ):
        raise ValueError("official example result has the wrong repetition count")

    successes: list[float] = []
    mass_residuals: list[float] = []
    for index, repetition in enumerate(repetitions):
        row = _mapping(repetition, f"repetitions[{index}]")
        success = float(row.get("success_probability"))
        failure = float(row.get("failure_probability_sum"))
        physical_mass = float(row.get("physical_state_probability"))
        if not all(math.isfinite(value) for value in (success, failure, physical_mass)):
            raise ValueError("official example produced a non-finite probability")
        if not 0.0 <= success <= 1.0 or not 0.0 <= failure <= 1.0:
            raise ValueError("official example produced a probability outside [0,1]")
        mass_residual = abs((success + failure) - 1.0)
        if mass_residual > config.official_example.probability_tolerance:
            raise ValueError("official example success and failure mass do not sum to one")
        if abs(physical_mass - 1.0) > config.official_example.probability_tolerance:
            raise ValueError("official example did not enumerate full physical-state mass")
        successes.append(success)
        mass_residuals.append(mass_residual)
    if max(successes) - min(successes) > config.official_example.probability_tolerance:
        raise ValueError("official example is not deterministic across technical repeats")

    model_root = example_checkout / config.official_example.project_path
    model_files = sorted(
        path
        for path in model_root.iterdir()
        if path.is_file()
        and path.suffix
        in {".allocation", ".repository", ".resourceenvironment", ".system", ".usagemodel"}
    )
    if len(model_files) != 5:
        raise ValueError("official ReliabilityTest must contain five PCM model files")
    repositories = [path for path in model_files if path.suffix == ".repository"]
    if len(repositories) != 1:
        raise ValueError("official ReliabilityTest must contain one repository model")
    oracle = _derive_official_example_oracle(repositories[0])
    oracle_success = float(oracle["success_probability"])
    if abs(successes[0] - oracle_success) > (
        config.official_example.probability_tolerance
    ):
        raise ValueError(
            f"Palladio result {successes[0]} disagrees with independent oracle "
            f"{oracle_success}"
        )
    expected = config.official_example.expected_success_probability
    if expected is not None:
        if abs(oracle_success - expected) > (
            config.official_example.probability_tolerance
        ):
            raise ValueError(
                f"independent oracle is {oracle_success}, expected pin is {expected}"
            )
        if abs(successes[0] - expected) > (
            config.official_example.probability_tolerance
        ):
            raise ValueError(
                f"official example success is {successes[0]}, expected {expected}"
            )
    pin_status = "pinned_match" if expected is not None else "discovered_not_accepted"
    payload = {
        "schema_version": 1,
        "kind": "palladio_official_reliability_example",
        "diagnostic_only": True,
        "analyzer_commit": config.analyzer.commit,
        "example_repository": config.official_example.repository,
        "example_commit": config.official_example.commit,
        "example_project": config.official_example.project_path,
        "success_probabilities": successes,
        "failure_mass_residuals": mass_residuals,
        "expected_success_probability": expected,
        "independent_oracle": oracle,
        "model_files": [
            {
                "relative_path": path.relative_to(example_checkout).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in model_files
        ],
        "pin_status": pin_status,
        "status": pin_status,
    }
    _write_json(output, payload)
    return payload
