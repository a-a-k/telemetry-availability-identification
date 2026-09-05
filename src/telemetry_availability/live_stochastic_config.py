from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence
from .live_fault_config import EXPECTED_LAWS
from .live_placement_config import (
    PlacementPilotConfig,
    load_placement_pilot_config,
)


@dataclass(frozen=True)
class RenewalProcess:
    mechanism: str
    minimum_up_seconds: float
    mean_up_seconds: float
    minimum_down_seconds: float
    maximum_down_seconds: float


@dataclass(frozen=True)
class DesignSelection:
    candidate_period_seconds: tuple[int, ...]
    minimum_events_per_factor_period: int
    minimum_schedule_fraction: float
    minimum_effective_blocks_per_period: int
    acf_absolute_threshold: float
    acf_consecutive_lags: int
    acf_max_lag_seconds: int
    transition_guard_candidates_seconds: tuple[int, ...]
    transition_lag_quantile: float
    candidate_main_repetitions: tuple[int, ...]
    target_paired_half_width: float
    paired_confidence_level: float
    sd_upper_confidence_level: float
    planning_sd_floor: float


@dataclass(frozen=True)
class StochasticPilotConfig:
    id: str
    pilot_only: bool
    placement: PlacementPilotConfig
    placement_config_path: Path
    pilot_repetitions: int
    baseline_seconds: int
    period_seconds: int
    request_rate_per_second: int
    request_timeout_seconds: int
    request_workers: int
    inter_period_recovery_seconds: int
    health_poll_seconds: float
    trace_flush_seconds: int
    minimum_baseline_semantic_success_fraction: float
    minimum_linked_success_fraction: float
    minimum_health_observation_fraction: float
    minimum_backend_sessions_per_replica: int
    pilot_base_seed: int
    main_base_seed: int
    laws: dict[str, tuple[str, ...]]
    renewal_processes: dict[str, RenewalProcess]
    design_selection: DesignSelection
    path: Path

    @property
    def requests_per_period(self) -> int:
        return self.period_seconds * self.request_rate_per_second

    @property
    def baseline_requests(self) -> int:
        return self.baseline_seconds * self.request_rate_per_second

    @property
    def expected_cells(self) -> int:
        return (
            len(self.placement.profiles)
            * len(self.placement.placements)
            * len(self.laws)
            * self.pilot_repetitions
        )


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


def _open_fraction(value: Any, label: str) -> float:
    result = float(value)
    if not 0 < result < 1:
        raise ConfigError(f"{label} must lie in (0, 1)")
    return result


def _closed_fraction(value: Any, label: str) -> float:
    result = float(value)
    if not 0 < result <= 1:
        raise ConfigError(f"{label} must lie in (0, 1]")
    return result


def _increasing_positive_ints(value: Any, label: str) -> tuple[int, ...]:
    result = tuple(_positive_int(item, label) for item in _sequence(value, label))
    if tuple(sorted(set(result))) != result:
        raise ConfigError(f"{label} must be strictly increasing and unique")
    return result


def _relative_sibling(config_path: Path, value: Any, label: str) -> Path:
    name = str(value)
    relative = Path(name)
    if not name or relative.is_absolute() or ".." in relative.parts:
        raise ConfigError(f"{label} must be a safe relative path")
    resolved = (config_path.parent / relative).resolve()
    if resolved.parent != config_path.parent:
        raise ConfigError(f"{label} must remain in the configuration directory")
    return resolved


def load_stochastic_pilot_config(path: str | Path) -> StochasticPilotConfig:
    config_path = Path(path).resolve()
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "stochastic freeze-pilot configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("stochastic freeze-pilot schema_version must equal 1")
    if root.get("pilot_only") is not True:
        raise ConfigError("stochastic freeze experiment must be explicitly pilot_only")

    placement_path = _relative_sibling(
        config_path,
        root.get("placement_config"),
        "placement_config",
    )
    placement = load_placement_pilot_config(placement_path)

    laws = {
        str(name): tuple(str(item) for item in _sequence(value, f"law {name}"))
        for name, value in _mapping(root.get("failure_laws"), "failure laws").items()
    }
    if laws != EXPECTED_LAWS:
        raise ConfigError(f"failure_laws must equal the frozen mapping {EXPECTED_LAWS}")

    renewal: dict[str, RenewalProcess] = {}
    raw_renewal = _mapping(root.get("renewal_processes"), "renewal processes")
    if set(raw_renewal) != {"individual", "communication", "common_domain"}:
        raise ConfigError("renewal_processes must define the three failure mechanisms")
    for mechanism, raw in raw_renewal.items():
        data = _mapping(raw, f"renewal process {mechanism}")
        process = RenewalProcess(
            mechanism=mechanism,
            minimum_up_seconds=_positive_float(
                data["minimum_up_seconds"], f"{mechanism} minimum_up_seconds"
            ),
            mean_up_seconds=_positive_float(
                data["mean_up_seconds"], f"{mechanism} mean_up_seconds"
            ),
            minimum_down_seconds=_positive_float(
                data["minimum_down_seconds"],
                f"{mechanism} minimum_down_seconds",
            ),
            maximum_down_seconds=_positive_float(
                data["maximum_down_seconds"],
                f"{mechanism} maximum_down_seconds",
            ),
        )
        if process.mean_up_seconds <= process.minimum_up_seconds:
            raise ConfigError(
                f"{mechanism} mean_up_seconds must exceed minimum_up_seconds"
            )
        if process.maximum_down_seconds < process.minimum_down_seconds:
            raise ConfigError(
                f"{mechanism} maximum_down_seconds must be at least the minimum"
            )
        renewal[mechanism] = process

    raw_design = _mapping(root.get("design_selection"), "design selection")
    design = DesignSelection(
        candidate_period_seconds=_increasing_positive_ints(
            raw_design["candidate_period_seconds"], "candidate_period_seconds"
        ),
        minimum_events_per_factor_period=_positive_int(
            raw_design["minimum_events_per_factor_period"],
            "minimum_events_per_factor_period",
        ),
        minimum_schedule_fraction=_closed_fraction(
            raw_design["minimum_schedule_fraction"], "minimum_schedule_fraction"
        ),
        minimum_effective_blocks_per_period=_positive_int(
            raw_design["minimum_effective_blocks_per_period"],
            "minimum_effective_blocks_per_period",
        ),
        acf_absolute_threshold=_open_fraction(
            raw_design["acf_absolute_threshold"], "acf_absolute_threshold"
        ),
        acf_consecutive_lags=_positive_int(
            raw_design["acf_consecutive_lags"], "acf_consecutive_lags"
        ),
        acf_max_lag_seconds=_positive_int(
            raw_design["acf_max_lag_seconds"], "acf_max_lag_seconds"
        ),
        transition_guard_candidates_seconds=_increasing_positive_ints(
            raw_design["transition_guard_candidates_seconds"],
            "transition_guard_candidates_seconds",
        ),
        transition_lag_quantile=_open_fraction(
            raw_design["transition_lag_quantile"], "transition_lag_quantile"
        ),
        candidate_main_repetitions=_increasing_positive_ints(
            raw_design["candidate_main_repetitions"],
            "candidate_main_repetitions",
        ),
        target_paired_half_width=_positive_float(
            raw_design["target_paired_half_width"], "target_paired_half_width"
        ),
        paired_confidence_level=_open_fraction(
            raw_design["paired_confidence_level"], "paired_confidence_level"
        ),
        sd_upper_confidence_level=_open_fraction(
            raw_design["sd_upper_confidence_level"],
            "sd_upper_confidence_level",
        ),
        planning_sd_floor=_positive_float(
            raw_design["planning_sd_floor"], "planning_sd_floor"
        ),
    )

    config = StochasticPilotConfig(
        id=str(root["id"]),
        pilot_only=True,
        placement=placement,
        placement_config_path=placement_path,
        pilot_repetitions=_positive_int(root["pilot_repetitions"], "pilot_repetitions"),
        baseline_seconds=_positive_int(root["baseline_seconds"], "baseline_seconds"),
        period_seconds=_positive_int(root["period_seconds"], "period_seconds"),
        request_rate_per_second=_positive_int(
            root["request_rate_per_second"], "request_rate_per_second"
        ),
        request_timeout_seconds=_positive_int(
            root["request_timeout_seconds"], "request_timeout_seconds"
        ),
        request_workers=_positive_int(root["request_workers"], "request_workers"),
        inter_period_recovery_seconds=_positive_int(
            root["inter_period_recovery_seconds"],
            "inter_period_recovery_seconds",
        ),
        health_poll_seconds=_positive_float(
            root["health_poll_seconds"], "health_poll_seconds"
        ),
        trace_flush_seconds=_positive_int(
            root["trace_flush_seconds"], "trace_flush_seconds"
        ),
        minimum_baseline_semantic_success_fraction=_closed_fraction(
            root["minimum_baseline_semantic_success_fraction"],
            "minimum_baseline_semantic_success_fraction",
        ),
        minimum_linked_success_fraction=_closed_fraction(
            root["minimum_linked_success_fraction"],
            "minimum_linked_success_fraction",
        ),
        minimum_health_observation_fraction=_closed_fraction(
            root["minimum_health_observation_fraction"],
            "minimum_health_observation_fraction",
        ),
        minimum_backend_sessions_per_replica=_positive_int(
            root["minimum_backend_sessions_per_replica"],
            "minimum_backend_sessions_per_replica",
        ),
        pilot_base_seed=_positive_int(root["pilot_base_seed"], "pilot_base_seed"),
        main_base_seed=_positive_int(root["main_base_seed"], "main_base_seed"),
        laws=laws,
        renewal_processes=renewal,
        design_selection=design,
        path=config_path,
    )
    if config.request_workers < config.request_rate_per_second:
        raise ConfigError("request_workers must be at least request_rate_per_second")
    if config.pilot_base_seed == config.main_base_seed:
        raise ConfigError("pilot and main base seeds must differ")
    if config.design_selection.acf_max_lag_seconds >= config.period_seconds:
        raise ConfigError("acf_max_lag_seconds must be shorter than the pilot period")
    if any(
        candidate < config.period_seconds
        for candidate in config.design_selection.candidate_period_seconds
    ):
        raise ConfigError("main period candidates cannot be shorter than the pilot")
    return config
