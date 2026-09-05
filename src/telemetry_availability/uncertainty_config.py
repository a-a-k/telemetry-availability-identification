from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping
from .transfer_config import TransferExperimentConfig, load_transfer_config


@dataclass(frozen=True)
class UncertaintyExperimentConfig:
    id: str
    confidence_level: float
    branch_tolerance: float
    branch_tolerance_scale: float
    branch_minimum_tolerance: float
    branch_max_nodes_per_domain: int
    simulation_episodes: int
    local_smoke_max_dataset_fits: int
    transfer_config_path: Path
    transfer: TransferExperimentConfig


def load_uncertainty_config(path: str | Path) -> UncertaintyExperimentConfig:
    config_path = Path(path)
    document: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    root = _mapping(document, "uncertainty configuration")
    if root.get("schema_version") != 1:
        raise ConfigError("uncertainty schema_version must equal 1")
    experiment = _mapping(root.get("experiment"), "uncertainty experiment")
    transfer_path = config_path.parent / str(experiment["transfer_config"])
    result = UncertaintyExperimentConfig(
        id=str(experiment["id"]),
        confidence_level=float(experiment["confidence_level"]),
        branch_tolerance=float(experiment["branch_tolerance"]),
        branch_tolerance_scale=float(experiment["branch_tolerance_scale"]),
        branch_minimum_tolerance=float(experiment["branch_minimum_tolerance"]),
        branch_max_nodes_per_domain=int(experiment["branch_max_nodes_per_domain"]),
        simulation_episodes=int(experiment["simulation_episodes"]),
        local_smoke_max_dataset_fits=int(experiment["local_smoke_max_dataset_fits"]),
        transfer_config_path=transfer_path,
        transfer=load_transfer_config(transfer_path),
    )
    if not 0.0 < result.confidence_level < 1.0:
        raise ConfigError("confidence_level must lie in (0, 1)")
    if not (
        0.0
        < result.branch_minimum_tolerance
        <= result.branch_tolerance
        < 1.0
        and result.branch_tolerance_scale > 0.0
    ):
        raise ConfigError("branch tolerances and scale are invalid")
    if (
        result.branch_max_nodes_per_domain <= 0
        or result.simulation_episodes <= 0
        or result.local_smoke_max_dataset_fits <= 0
    ):
        raise ConfigError("uncertainty experiment counts must be positive")
    return result
