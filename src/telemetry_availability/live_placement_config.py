from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence
from .live_pilot_config import RuntimePilotConfig, load_runtime_pilot_config

EXPECTED_PLACEMENTS = {
    "colocated": {"a": "domain_a", "b": "domain_a"},
    "split": {"a": "domain_a", "b": "domain_b"},
}
EXPECTED_EVENT_MECHANISMS = (
    "individual_a",
    "individual_b",
    "common_domain",
    "communication",
)


@dataclass(frozen=True)
class PlacementPilotEvent:
    id: str
    mechanism: str
    offset_seconds: float


@dataclass(frozen=True)
class PlacementPilotProfile:
    id: str
    target_service: str
    target_port: int
    proxy_mode: str
    routing_probe_operation: str

    @property
    def replica_services(self) -> dict[str, str]:
        return {
            replica: f"{self.target_service}-replica-{replica}"
            for replica in ("a", "b")
        }


@dataclass(frozen=True)
class PlacementPilotConfig:
    id: str
    pilot_only: bool
    runtime: RuntimePilotConfig
    runtime_config_path: Path
    proxy_image: str
    proxy_manifest_digest: str
    proxy_stats_port: int
    routing_probe_requests: int
    routing_probe_workers: int
    fault_period_seconds: int
    request_rate_per_second: int
    request_timeout_seconds: int
    request_workers: int
    fault_duration_seconds: int
    health_poll_seconds: float
    trace_flush_seconds: int
    recovery_seconds: int
    minimum_routing_semantic_success_fraction: float
    minimum_linked_success_fraction: float
    minimum_health_samples_per_service: int
    minimum_backend_sessions_per_replica: int
    base_seed: int
    events: tuple[PlacementPilotEvent, ...]
    placements: dict[str, dict[str, str]]
    profiles: tuple[PlacementPilotProfile, ...]
    path: Path

    @property
    def requests_per_fault_period(self) -> int:
        return self.fault_period_seconds * self.request_rate_per_second

    @property
    def proxy_locked_image(self) -> str:
        base = self.proxy_image.split("@", 1)[0]
        return f"{base}@{self.proxy_manifest_digest}"


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


def _fraction(value: Any, label: str) -> float:
    result = float(value)
    if not 0 < result <= 1:
        raise ConfigError(f"{label} must lie in (0, 1]")
    return result


def load_placement_pilot_config(path: str | Path) -> PlacementPilotConfig:
    config_path = Path(path).resolve()
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "placement pilot configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("placement pilot schema_version must equal 1")
    if root.get("pilot_only") is not True:
        raise ConfigError("placement experiment must be explicitly pilot_only")

    runtime_name = str(root["runtime_config"])
    runtime_relative = Path(runtime_name)
    if (
        not runtime_name
        or runtime_relative.is_absolute()
        or ".." in runtime_relative.parts
    ):
        raise ConfigError("runtime_config must be a safe relative path")
    runtime_path = (config_path.parent / runtime_relative).resolve()
    if runtime_path.parent != config_path.parent:
        raise ConfigError("runtime_config must remain in the configuration directory")
    runtime = load_runtime_pilot_config(runtime_path)

    placements = {
        str(name): {
            str(replica): str(domain)
            for replica, domain in _mapping(value, f"placement {name}").items()
        }
        for name, value in _mapping(root.get("placements"), "placements").items()
    }
    if placements != EXPECTED_PLACEMENTS:
        raise ConfigError(
            f"placements must equal the frozen mapping {EXPECTED_PLACEMENTS}"
        )

    events: list[PlacementPilotEvent] = []
    for raw in _sequence(root.get("events"), "placement pilot events"):
        data = _mapping(raw, "placement pilot event")
        events.append(
            PlacementPilotEvent(
                id=str(data["id"]),
                mechanism=str(data["mechanism"]),
                offset_seconds=_positive_float(
                    data["offset_seconds"],
                    "event offset_seconds",
                ),
            )
        )
    if tuple(event.mechanism for event in events) != EXPECTED_EVENT_MECHANISMS:
        raise ConfigError(
            "events must exercise individual_a, individual_b, common_domain, "
            "and communication exactly once in that order"
        )
    if len({event.id for event in events}) != len(events):
        raise ConfigError("placement pilot event ids must be unique")
    if any(
        left.offset_seconds >= right.offset_seconds
        for left, right in zip(events, events[1:])
    ):
        raise ConfigError("placement pilot event offsets must be strictly increasing")

    profiles: list[PlacementPilotProfile] = []
    for raw in _sequence(root.get("profiles"), "placement pilot profiles"):
        data = _mapping(raw, "placement pilot profile")
        profile = PlacementPilotProfile(
            id=str(data["id"]),
            target_service=str(data["target_service"]),
            target_port=_positive_int(data["target_port"], "target_port"),
            proxy_mode=str(data["proxy_mode"]),
            routing_probe_operation=str(data["routing_probe_operation"]),
        )
        if (
            re.fullmatch(r"[a-z0-9_]+", profile.id) is None
            or not profile.target_service
            or profile.proxy_mode not in {"tcp", "grpc_h2"}
            or not profile.routing_probe_operation
        ):
            raise ConfigError("placement pilot profile is invalid")
        profiles.append(profile)
    runtime_by_id = {profile.id: profile for profile in runtime.profiles}
    if {profile.id for profile in profiles} != set(runtime_by_id):
        raise ConfigError("placement profiles must match runtime-pilot profiles")
    if len(profiles) != len({profile.id for profile in profiles}):
        raise ConfigError("placement profile ids must be unique")
    for profile in profiles:
        runtime_profile = runtime_by_id[profile.id]
        if profile.routing_probe_operation not in runtime_profile.operations:
            raise ConfigError(
                f"routing probe operation is absent from {profile.id} operations"
            )

    proxy_image = str(root["proxy_image"])
    proxy_digest = str(root["proxy_manifest_digest"])
    if (
        "@" in proxy_image
        or not proxy_image
        or re.fullmatch(r"sha256:[0-9a-f]{64}", proxy_digest) is None
    ):
        raise ConfigError("proxy image and manifest digest are invalid")

    config = PlacementPilotConfig(
        id=str(root["id"]),
        pilot_only=True,
        runtime=runtime,
        runtime_config_path=runtime_path,
        proxy_image=proxy_image,
        proxy_manifest_digest=proxy_digest,
        proxy_stats_port=_positive_int(root["proxy_stats_port"], "proxy_stats_port"),
        routing_probe_requests=_positive_int(
            root["routing_probe_requests"], "routing_probe_requests"
        ),
        routing_probe_workers=_positive_int(
            root["routing_probe_workers"], "routing_probe_workers"
        ),
        fault_period_seconds=_positive_int(
            root["fault_period_seconds"], "fault_period_seconds"
        ),
        request_rate_per_second=_positive_int(
            root["request_rate_per_second"], "request_rate_per_second"
        ),
        request_timeout_seconds=_positive_int(
            root["request_timeout_seconds"], "request_timeout_seconds"
        ),
        request_workers=_positive_int(root["request_workers"], "request_workers"),
        fault_duration_seconds=_positive_int(
            root["fault_duration_seconds"], "fault_duration_seconds"
        ),
        health_poll_seconds=_positive_float(
            root["health_poll_seconds"], "health_poll_seconds"
        ),
        trace_flush_seconds=_positive_int(
            root["trace_flush_seconds"], "trace_flush_seconds"
        ),
        recovery_seconds=_positive_int(root["recovery_seconds"], "recovery_seconds"),
        minimum_routing_semantic_success_fraction=_fraction(
            root["minimum_routing_semantic_success_fraction"],
            "minimum_routing_semantic_success_fraction",
        ),
        minimum_linked_success_fraction=_fraction(
            root["minimum_linked_success_fraction"],
            "minimum_linked_success_fraction",
        ),
        minimum_health_samples_per_service=_positive_int(
            root["minimum_health_samples_per_service"],
            "minimum_health_samples_per_service",
        ),
        minimum_backend_sessions_per_replica=_positive_int(
            root["minimum_backend_sessions_per_replica"],
            "minimum_backend_sessions_per_replica",
        ),
        base_seed=_positive_int(root["base_seed"], "base_seed"),
        events=tuple(events),
        placements=placements,
        profiles=tuple(profiles),
        path=config_path,
    )
    if config.request_workers < config.request_rate_per_second:
        raise ConfigError("request_workers must be at least request_rate_per_second")
    if config.routing_probe_workers > config.routing_probe_requests:
        raise ConfigError("routing_probe_workers cannot exceed routing_probe_requests")
    latest_end = events[-1].offset_seconds + config.fault_duration_seconds
    if latest_end + config.recovery_seconds >= config.fault_period_seconds:
        raise ConfigError(
            "fault period must include the final event and recovery window"
        )
    return config


def select_placement_pilot_profile(
    config: PlacementPilotConfig,
    profile_id: str,
) -> PlacementPilotProfile:
    matches = [profile for profile in config.profiles if profile.id == profile_id]
    if len(matches) != 1:
        raise ConfigError(
            f"unknown placement pilot profile {profile_id!r}; "
            f"expected {[profile.id for profile in config.profiles]}"
        )
    return matches[0]
