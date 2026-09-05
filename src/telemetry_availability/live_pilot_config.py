from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence


@dataclass(frozen=True)
class RuntimePilotProfile:
    id: str
    repository: str
    commit: str
    compose_file: str
    base_url: str
    readiness_path: str
    telemetry_kind: str
    telemetry_source: str
    operations: tuple[str, ...]
    images: dict[str, str]


@dataclass(frozen=True)
class RuntimePilotConfig:
    id: str
    pilot_only: bool
    requests_per_operation_per_period: int
    minimum_success_fraction: float
    minimum_exported_traces: int
    readiness_timeout_seconds: int
    trace_flush_seconds: int
    inter_period_gap_seconds: int
    profiles: tuple[RuntimePilotProfile, ...]
    path: Path


def _positive_integer(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be an integer") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _safe_posix_path(value: Any, label: str) -> str:
    raw = str(value)
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ConfigError(f"{label} must be a safe relative POSIX path")
    return raw


def load_runtime_pilot_config(path: str | Path) -> RuntimePilotConfig:
    config_path = Path(path)
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "runtime pilot configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("runtime pilot schema_version must equal 1")
    if root.get("pilot_only") is not True:
        raise ConfigError("runtime pilot must be explicitly marked pilot_only")
    minimum_success_fraction = float(root["minimum_success_fraction"])
    if not 0 < minimum_success_fraction <= 1:
        raise ConfigError("minimum_success_fraction must lie in (0, 1]")

    profiles: list[RuntimePilotProfile] = []
    for raw_profile in _sequence(root.get("profiles"), "runtime pilot profiles"):
        data = _mapping(raw_profile, "runtime pilot profile")
        repository = str(data["repository"])
        commit = str(data["commit"])
        if not repository.startswith("https://github.com/") or not repository.endswith(
            ".git"
        ):
            raise ConfigError("runtime pilot repository must be an HTTPS GitHub URL")
        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise ConfigError("runtime pilot commit must be a full lowercase SHA-1")
        images = {
            str(image): str(digest)
            for image, digest in _mapping(
                data.get("images"),
                "runtime image locks",
            ).items()
        }
        if not images or any(
            re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
            for digest in images.values()
        ):
            raise ConfigError("every runtime image must have a SHA-256 manifest digest")
        operations = tuple(
            str(value)
            for value in _sequence(data.get("operations"), "pilot operations")
        )
        profile = RuntimePilotProfile(
            id=str(data["id"]),
            repository=repository,
            commit=commit,
            compose_file=_safe_posix_path(data["compose_file"], "pilot compose file"),
            base_url=str(data["base_url"]).rstrip("/"),
            readiness_path=str(data["readiness_path"]),
            telemetry_kind=str(data["telemetry_kind"]),
            telemetry_source=str(data["telemetry_source"]),
            operations=operations,
            images=images,
        )
        if (
            not profile.id
            or not profile.base_url.startswith("http://127.0.0.1:")
            or not profile.readiness_path.startswith("/")
            or profile.telemetry_kind not in {"jaeger_api", "docker_logs"}
            or not profile.telemetry_source
            or not operations
            or len(set(operations)) != len(operations)
        ):
            raise ConfigError("runtime pilot profile fields are invalid")
        profiles.append(profile)
    if len(profiles) != 2 or len({item.id for item in profiles}) != 2:
        raise ConfigError("runtime pilot requires exactly two unique profiles")
    return RuntimePilotConfig(
        id=str(root["id"]),
        pilot_only=True,
        requests_per_operation_per_period=_positive_integer(
            root["requests_per_operation_per_period"],
            "requests_per_operation_per_period",
        ),
        minimum_success_fraction=minimum_success_fraction,
        minimum_exported_traces=_positive_integer(
            root["minimum_exported_traces"],
            "minimum_exported_traces",
        ),
        readiness_timeout_seconds=_positive_integer(
            root["readiness_timeout_seconds"],
            "readiness_timeout_seconds",
        ),
        trace_flush_seconds=_positive_integer(
            root["trace_flush_seconds"],
            "trace_flush_seconds",
        ),
        inter_period_gap_seconds=_positive_integer(
            root["inter_period_gap_seconds"],
            "inter_period_gap_seconds",
        ),
        profiles=tuple(profiles),
        path=config_path,
    )


def select_runtime_pilot_profile(
    config: RuntimePilotConfig,
    profile_id: str,
) -> RuntimePilotProfile:
    matches = [profile for profile in config.profiles if profile.id == profile_id]
    if len(matches) != 1:
        raise ConfigError(
            f"unknown runtime pilot profile {profile_id!r}; "
            f"expected {[profile.id for profile in config.profiles]}"
        )
    return matches[0]
