from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence
from .transfer_config import TransferExperimentConfig, load_transfer_config


@dataclass(frozen=True)
class StressVariant:
    id: str
    is_stress: bool
    parameters: dict[str, Any]


@dataclass(frozen=True)
class StressSeries:
    id: str
    settings: dict[str, Any]
    variants: tuple[StressVariant, ...]


@dataclass(frozen=True)
class StressExperimentConfig:
    id: str
    seed: int
    repetitions: int
    sample_sizes: tuple[int, ...]
    confidence_level: float
    diagnostic_alpha: float
    local_smoke_max_dataset_fits: int
    branch_tolerance: float
    branch_tolerance_scale: float
    branch_minimum_tolerance: float
    branch_max_nodes_per_domain: int
    block_bootstrap_replicates: int
    block_length: int
    minimum_branch_observations: int
    transfer_config_path: Path
    transfer: TransferExperimentConfig
    base_scenario: str
    series: tuple[StressSeries, ...]


REQUIRED_SERIES = (
    "exporter_loss",
    "temporal_bursts",
    "wrong_domain_map",
    "rare_branch",
    "readiness_lag",
)


def load_stress_config(path: str | Path) -> StressExperimentConfig:
    config_path = Path(path)
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    root = _mapping(document, "stress configuration")
    if root.get("schema_version") != 1:
        raise ConfigError("stress schema_version must equal 1")
    experiment = _mapping(root.get("experiment"), "stress experiment")
    transfer_path = config_path.parent / str(experiment["transfer_config"])
    transfer = load_transfer_config(transfer_path)
    sample_sizes = tuple(
        int(value) for value in _sequence(experiment.get("sample_sizes"), "sample_sizes")
    )
    if not sample_sizes or tuple(sorted(set(sample_sizes))) != sample_sizes:
        raise ConfigError("stress sample_sizes must be strictly increasing")

    raw_series = _mapping(root.get("series"), "stress series")
    parsed: list[StressSeries] = []
    for series_id, raw_value in raw_series.items():
        data = _mapping(raw_value, f"stress series {series_id}")
        variants = tuple(
            StressVariant(
                id=str(variant["id"]),
                is_stress=bool(variant["is_stress"]),
                parameters={
                    str(key): value
                    for key, value in variant.items()
                    if key not in {"id", "is_stress"}
                },
            )
            for variant in (
                _mapping(value, f"variant in {series_id}")
                for value in _sequence(data.get("variants"), f"variants in {series_id}")
            )
        )
        if len({variant.id for variant in variants}) != len(variants):
            raise ConfigError(f"duplicate variant id in {series_id}")
        if not variants or not any(not variant.is_stress for variant in variants):
            raise ConfigError(f"{series_id} needs at least one neutral control")
        parsed.append(
            StressSeries(
                id=str(series_id),
                settings={
                    str(key): value
                    for key, value in data.items()
                    if key != "variants"
                },
                variants=variants,
            )
        )

    series_ids = tuple(item.id for item in parsed)
    if set(series_ids) != set(REQUIRED_SERIES) or len(series_ids) != len(REQUIRED_SERIES):
        raise ConfigError(
            f"stress series must be exactly {list(REQUIRED_SERIES)}; got {list(series_ids)}"
        )
    result = StressExperimentConfig(
        id=str(experiment["id"]),
        seed=int(experiment["seed"]),
        repetitions=int(experiment["repetitions"]),
        sample_sizes=sample_sizes,
        confidence_level=float(experiment["confidence_level"]),
        diagnostic_alpha=float(experiment["diagnostic_alpha"]),
        local_smoke_max_dataset_fits=int(experiment["local_smoke_max_dataset_fits"]),
        branch_tolerance=float(experiment["branch_tolerance"]),
        branch_tolerance_scale=float(experiment["branch_tolerance_scale"]),
        branch_minimum_tolerance=float(experiment["branch_minimum_tolerance"]),
        branch_max_nodes_per_domain=int(experiment["branch_max_nodes_per_domain"]),
        block_bootstrap_replicates=int(experiment["block_bootstrap_replicates"]),
        block_length=int(experiment["block_length"]),
        minimum_branch_observations=int(experiment["minimum_branch_observations"]),
        transfer_config_path=transfer_path,
        transfer=transfer,
        base_scenario=str(experiment["base_scenario"]),
        series=tuple(parsed),
    )
    if not 0.0 < result.confidence_level < 1.0:
        raise ConfigError("stress confidence_level must lie in (0, 1)")
    if not 0.0 < result.diagnostic_alpha < 1.0:
        raise ConfigError("stress diagnostic_alpha must lie in (0, 1)")
    positive_counts = (
        result.repetitions,
        result.local_smoke_max_dataset_fits,
        result.branch_max_nodes_per_domain,
        result.block_bootstrap_replicates,
        result.block_length,
        result.minimum_branch_observations,
    )
    if any(value <= 0 for value in positive_counts):
        raise ConfigError("stress counts must be positive")
    if not (
        0.0 < result.branch_minimum_tolerance <= result.branch_tolerance < 1.0
        and result.branch_tolerance_scale > 0.0
    ):
        raise ConfigError("stress branch tolerances are invalid")
    if result.base_scenario not in {scenario.id for scenario in transfer.scenarios}:
        raise ConfigError(f"unknown base stress scenario {result.base_scenario!r}")

    exporter = next(item for item in result.series if item.id == "exporter_loss")
    gamma = next(
        factor.probability
        for scenario in transfer.scenarios
        if scenario.id == result.base_scenario
        for factor in scenario.model.factors
        if factor.id == "domain_a"
    )
    target = float(exporter.settings["target_trace_retention"])
    for variant in exporter.variants:
        up = float(variant.parameters["retention_when_domain_up"])
        down = float(variant.parameters["retention_when_domain_down"])
        if not 0.0 <= up <= 1.0 or not 0.0 <= down <= 1.0:
            raise ConfigError("exporter retention probabilities must lie in [0, 1]")
        marginal = gamma * up + (1.0 - gamma) * down
        if abs(marginal - target) > 1e-12:
            raise ConfigError(
                f"exporter variant {variant.id!r} does not preserve retention: {marginal}"
            )
    return result
