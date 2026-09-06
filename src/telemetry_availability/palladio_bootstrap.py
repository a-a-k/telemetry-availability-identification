from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
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
class PalladioProductLock:
    url: str
    expected_bytes: int
    sha256: str | None
    required_feature: str
    required_solver_bundle: str


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
    expected_bytes = product_data.get("expected_bytes")
    if (
        isinstance(expected_bytes, bool)
        or not isinstance(expected_bytes, int)
        or expected_bytes <= 0
    ):
        raise ValueError("product.expected_bytes must be a positive integer")
    product = PalladioProductLock(
        url=_required_string(product_data, "url", "product"),
        expected_bytes=expected_bytes,
        sha256=product_sha,
        required_feature=_required_string(
            product_data, "required_feature", "product"
        ),
        required_solver_bundle=_required_string(
            product_data, "required_solver_bundle", "product"
        ),
    )
    release_path = f"/releases/{analyzer.bundle_version}/"
    if not product.url.startswith(
        "https://updatesite.palladio-simulator.com/palladio-bench-product/"
    ) or release_path not in product.url:
        raise ValueError("product URL must be the versioned official release URL")
    if product.required_feature != (
        f"org.palladiosimulator.reliability.feature_{analyzer.bundle_version}.jar"
    ):
        raise ValueError("required feature version disagrees with analyzer version")
    if product.required_solver_bundle != (
        f"org.palladiosimulator.reliability.solver_{analyzer.bundle_version}.jar"
    ):
        raise ValueError("required solver version disagrees with analyzer version")

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
    feature_matches = list(site.rglob(config.product.required_feature))
    solver_matches = list(site.rglob(config.product.required_solver_bundle))
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

    try:
        with ZipFile(archive) as product_zip:
            files = [name for name in product_zip.namelist() if not name.endswith("/")]
            feature_paths = [
                name
                for name in files
                if Path(name).name == config.product.required_feature
            ]
            solver_paths = [
                name
                for name in files
                if Path(name).name == config.product.required_solver_bundle
            ]
            reliability_paths = sorted(
                name
                for name in files
                if (
                    "/plugins/org.palladiosimulator.reliability" in name
                    or "/features/org.palladiosimulator.reliability" in name
                )
                and name.endswith(".jar")
                and ".source_" not in name
            )
            if len(feature_paths) != 1 or len(solver_paths) != 1:
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
        "required_feature": feature_paths[0],
        "required_solver_bundle": solver_paths[0],
        "reliability_files": reliability_files,
        "status": pin_status,
    }
    _write_json(output, payload)
    return payload


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
    expected = config.official_example.expected_success_probability
    if expected is not None and abs(successes[0] - expected) > (
        config.official_example.probability_tolerance
    ):
        raise ValueError(
            f"official example success is {successes[0]}, expected {expected}"
        )

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
