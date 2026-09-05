from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence
from .live_pilot_config import RuntimePilotConfig, load_runtime_pilot_config


ALLOWED_MECHANISMS = {"individual", "communication", "common_domain"}
EXPECTED_LAWS = {
    "N": ("individual",),
    "NC": ("individual", "communication"),
    "ND": ("individual", "common_domain"),
    "NCD": ("individual", "communication", "common_domain"),
}


@dataclass(frozen=True)
class LiveFaultProfile:
    id: str
    individual_service: str
    communication_service: str
    common_domain_services: tuple[str, ...]
    health_services: tuple[str, ...]


@dataclass(frozen=True)
class LiveFaultConfig:
    id: str
    diagnostic_only: bool
    runtime: RuntimePilotConfig
    runtime_config_path: Path
    period_seconds: int
    request_rate_per_second: int
    request_timeout_seconds: int
    request_workers: int
    inter_period_gap_seconds: int
    fault_duration_seconds: int
    first_fault_offset_seconds: int
    fault_gap_seconds: int
    fault_jitter_seconds: float
    health_poll_seconds: float
    trace_flush_seconds: int
    minimum_linked_success_fraction: float
    minimum_health_samples_per_service_period: int
    base_seed: int
    repetitions: int
    laws: dict[str, tuple[str, ...]]
    profiles: tuple[LiveFaultProfile, ...]
    path: Path

    @property
    def requests_per_period(self) -> int:
        return self.period_seconds * self.request_rate_per_second


def _positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be an integer") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _positive_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be numeric") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def load_live_fault_config(path: str | Path) -> LiveFaultConfig:
    config_path = Path(path).resolve()
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "live fault diagnostic configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("live fault diagnostic schema_version must equal 1")
    if root.get("diagnostic_only") is not True:
        raise ConfigError("live fault acquisition must be explicitly diagnostic_only")

    runtime_name = str(root["runtime_config"])
    if not runtime_name or Path(runtime_name).is_absolute() or ".." in Path(runtime_name).parts:
        raise ConfigError("runtime_config must be a safe relative path")
    runtime_path = (config_path.parent / runtime_name).resolve()
    if runtime_path.parent != config_path.parent:
        raise ConfigError("runtime_config must remain in the configuration directory")
    runtime = load_runtime_pilot_config(runtime_path)

    laws = {
        str(name): tuple(str(item) for item in _sequence(value, f"law {name}"))
        for name, value in _mapping(root.get("failure_laws"), "failure laws").items()
    }
    if laws != EXPECTED_LAWS:
        raise ConfigError(f"failure_laws must equal the frozen mapping {EXPECTED_LAWS}")
    if any(
        mechanism not in ALLOWED_MECHANISMS
        for values in laws.values()
        for mechanism in values
    ):
        raise ConfigError("failure_laws contain an unsupported mechanism")

    profiles: list[LiveFaultProfile] = []
    for raw in _sequence(root.get("profiles"), "live fault profiles"):
        data = _mapping(raw, "live fault profile")
        common = tuple(
            str(value)
            for value in _sequence(
                data.get("common_domain_services"),
                "common-domain services",
            )
        )
        health = tuple(
            str(value)
            for value in _sequence(data.get("health_services"), "health services")
        )
        profile = LiveFaultProfile(
            id=str(data["id"]),
            individual_service=str(data["individual_service"]),
            communication_service=str(data["communication_service"]),
            common_domain_services=common,
            health_services=health,
        )
        named = {
            profile.individual_service,
            profile.communication_service,
            *profile.common_domain_services,
        }
        if (
            re.fullmatch(r"[a-z0-9_]+", profile.id) is None
            or any(not service for service in named)
            or len(common) < 2
            or len(set(common)) != len(common)
            or not health
            or len(set(health)) != len(health)
            or not named.issubset(set(health))
        ):
            raise ConfigError("live fault profile service declarations are invalid")
        profiles.append(profile)

    runtime_ids = {profile.id for profile in runtime.profiles}
    profile_ids = {profile.id for profile in profiles}
    if profile_ids != runtime_ids or len(profiles) != len(profile_ids):
        raise ConfigError(
            "live fault profiles must match the unique runtime-pilot profiles"
        )

    minimum_linked = float(root["minimum_linked_success_fraction"])
    if not 0 < minimum_linked <= 1:
        raise ConfigError("minimum_linked_success_fraction must lie in (0, 1]")
    jitter = float(root["fault_jitter_seconds"])
    if jitter < 0:
        raise ConfigError("fault_jitter_seconds must be nonnegative")

    config = LiveFaultConfig(
        id=str(root["id"]),
        diagnostic_only=True,
        runtime=runtime,
        runtime_config_path=runtime_path,
        period_seconds=_positive_int(root["period_seconds"], "period_seconds"),
        request_rate_per_second=_positive_int(
            root["request_rate_per_second"],
            "request_rate_per_second",
        ),
        request_timeout_seconds=_positive_int(
            root["request_timeout_seconds"],
            "request_timeout_seconds",
        ),
        request_workers=_positive_int(root["request_workers"], "request_workers"),
        inter_period_gap_seconds=_positive_int(
            root["inter_period_gap_seconds"],
            "inter_period_gap_seconds",
        ),
        fault_duration_seconds=_positive_int(
            root["fault_duration_seconds"],
            "fault_duration_seconds",
        ),
        first_fault_offset_seconds=_positive_int(
            root["first_fault_offset_seconds"],
            "first_fault_offset_seconds",
        ),
        fault_gap_seconds=_positive_int(root["fault_gap_seconds"], "fault_gap_seconds"),
        fault_jitter_seconds=jitter,
        health_poll_seconds=_positive_float(
            root["health_poll_seconds"],
            "health_poll_seconds",
        ),
        trace_flush_seconds=_positive_int(
            root["trace_flush_seconds"],
            "trace_flush_seconds",
        ),
        minimum_linked_success_fraction=minimum_linked,
        minimum_health_samples_per_service_period=_positive_int(
            root["minimum_health_samples_per_service_period"],
            "minimum_health_samples_per_service_period",
        ),
        base_seed=_positive_int(root["base_seed"], "base_seed"),
        repetitions=_positive_int(root["repetitions"], "repetitions"),
        laws=laws,
        profiles=tuple(profiles),
        path=config_path,
    )
    latest_fault_end = (
        config.first_fault_offset_seconds
        + 2 * config.fault_gap_seconds
        + config.fault_jitter_seconds
        + config.fault_duration_seconds
    )
    if latest_fault_end >= config.period_seconds:
        raise ConfigError(
            "diagnostic period must fit at least one complete event of every NCD mechanism"
        )
    if config.request_workers < config.request_rate_per_second:
        raise ConfigError("request_workers must be at least request_rate_per_second")
    return config


def select_live_fault_profile(
    config: LiveFaultConfig,
    profile_id: str,
) -> LiveFaultProfile:
    matches = [profile for profile in config.profiles if profile.id == profile_id]
    if len(matches) != 1:
        raise ConfigError(
            f"unknown live fault profile {profile_id!r}; "
            f"expected {[profile.id for profile in config.profiles]}"
        )
    return matches[0]
