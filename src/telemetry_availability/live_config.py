from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
import re

import yaml

from .config import ConfigError, _mapping, _sequence


@dataclass(frozen=True)
class LiveContractConfig:
    id: str
    version: int
    require_file_digests: bool
    require_disjoint_periods: bool
    require_external_request_census: bool
    maximum_health_age_seconds: float


@dataclass(frozen=True)
class OperationEvidence:
    id: str
    workload_path: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkProfile:
    id: str
    repository: str
    commit: str
    checkout_subtree: str
    required_paths: tuple[str, ...]
    required_services: tuple[str, ...]
    trace_format: str
    fixture_bundle: Path
    operations: tuple[OperationEvidence, ...]

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.operations)


@dataclass(frozen=True)
class LiveHarnessConfig:
    contract: LiveContractConfig
    benchmarks: tuple[BenchmarkProfile, ...]
    path: Path


def _relative_posix(value: Any, label: str, allow_dot: bool = False) -> str:
    raw = str(value)
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or (raw == "." and not allow_dot):
        raise ConfigError(f"{label} must be a safe relative POSIX path")
    return raw


def _strict_boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{label} must be a YAML boolean")
    return value


def load_live_harness_config(path: str | Path) -> LiveHarnessConfig:
    config_path = Path(path)
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "live harness configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("live harness schema_version must equal 1")
    raw_contract = _mapping(root.get("contract"), "live contract")
    contract = LiveContractConfig(
        id=str(raw_contract["id"]),
        version=int(raw_contract["version"]),
        require_file_digests=_strict_boolean(
            raw_contract["require_file_digests"],
            "require_file_digests",
        ),
        require_disjoint_periods=_strict_boolean(
            raw_contract["require_disjoint_periods"],
            "require_disjoint_periods",
        ),
        require_external_request_census=_strict_boolean(
            raw_contract["require_external_request_census"],
            "require_external_request_census",
        ),
        maximum_health_age_seconds=float(
            raw_contract["maximum_health_age_seconds"]
        ),
    )
    if not contract.id or contract.version <= 0 or contract.maximum_health_age_seconds <= 0:
        raise ConfigError("live contract identity, version, and health age are invalid")

    benchmarks: list[BenchmarkProfile] = []
    for raw_value in _sequence(root.get("benchmarks"), "live benchmark profiles"):
        data = _mapping(raw_value, "live benchmark profile")
        repository = str(data["repository"])
        if not repository.startswith("https://github.com/") or not repository.endswith(".git"):
            raise ConfigError("benchmark repository must be an HTTPS GitHub clone URL")
        commit = str(data["commit"])
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise ConfigError("benchmark commit must be a full lowercase SHA-1")
        trace_format = str(data["trace_format"])
        if trace_format not in {"otlp_json_v1", "jaeger_json_v1"}:
            raise ConfigError(f"unsupported trace adapter {trace_format!r}")
        fixture = config_path.parent.parent / _relative_posix(
            data["fixture_bundle"],
            "fixture bundle",
        )
        required_paths = tuple(
            _relative_posix(value, "required benchmark path")
            for value in _sequence(data.get("required_paths"), "required_paths")
        )
        operations: list[OperationEvidence] = []
        for raw_operation in _sequence(
            data.get("operations"),
            "benchmark operations",
        ):
            operation = _mapping(raw_operation, "benchmark operation")
            evidence = OperationEvidence(
                id=str(operation["id"]),
                workload_path=_relative_posix(
                    operation["workload_path"],
                    "operation workload path",
                ),
                markers=tuple(
                    str(value)
                    for value in _sequence(
                        operation.get("markers"),
                        "operation markers",
                    )
                ),
            )
            if not evidence.id or not evidence.markers or any(
                not marker for marker in evidence.markers
            ):
                raise ConfigError("operation evidence must have an id and markers")
            operations.append(evidence)
        profile = BenchmarkProfile(
            id=str(data["id"]),
            repository=repository,
            commit=commit,
            checkout_subtree=_relative_posix(
                data["checkout_subtree"],
                "checkout subtree",
                allow_dot=True,
            ),
            required_paths=required_paths,
            required_services=tuple(
                str(value)
                for value in _sequence(data.get("required_services"), "required_services")
            ),
            trace_format=trace_format,
            fixture_bundle=fixture,
            operations=tuple(operations),
        )
        if not all(
            (
                profile.id,
                profile.required_paths,
                profile.required_services,
                profile.operations,
            )
        ):
            raise ConfigError("benchmark profile fields must not be empty")
        if len(set(profile.operation_ids)) != len(profile.operations):
            raise ConfigError("benchmark operation ids must be unique")
        if (
            len(set(profile.required_paths)) != len(profile.required_paths)
            or len(set(profile.required_services)) != len(profile.required_services)
            or any(not value for value in profile.required_services)
        ):
            raise ConfigError("required paths and services must be nonempty and unique")
        required_path_set = set(profile.required_paths)
        if any(
            operation.workload_path not in required_path_set
            for operation in profile.operations
        ):
            raise ConfigError("every operation workload path must be a required path")
        subtree = PurePosixPath(profile.checkout_subtree)
        if profile.checkout_subtree != "." and any(
            not PurePosixPath(path).is_relative_to(subtree)
            for path in profile.required_paths
        ):
            raise ConfigError("required paths must lie within checkout_subtree")
        benchmarks.append(profile)
    if not benchmarks or len({item.id for item in benchmarks}) != len(benchmarks):
        raise ConfigError("live harness needs uniquely named benchmark profiles")
    if {item.trace_format for item in benchmarks} != {"otlp_json_v1", "jaeger_json_v1"}:
        raise ConfigError("live harness must exercise both trace adapters")
    return LiveHarnessConfig(contract, tuple(benchmarks), config_path)
