from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .model import ConjunctiveModel, Factor, Observable, Target
from .observation import ObservationPolicy


class ConfigError(ValueError):
    """Raised when the experiment configuration violates its contract."""


@dataclass(frozen=True)
class ExperimentConfig:
    id: str
    seed: int
    repetitions: int
    sample_sizes: tuple[int, ...]
    max_moment_order: int
    min_joint_observations: int
    local_smoke_max_dataset_fits: int
    families: tuple[ConjunctiveModel, ...]
    observation_modes: tuple[ObservationPolicy, ...]


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a mapping")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be a sequence")
    return value


def _unique_ids(items: tuple[Any, ...], label: str) -> None:
    identifiers = [item.id for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise ConfigError(f"duplicate {label} id")


def load_config(path: str | Path) -> ExperimentConfig:
    config_path = Path(path)
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    root = _mapping(document, "configuration")
    if root.get("schema_version") != 1:
        raise ConfigError("schema_version must equal 1")

    experiment = _mapping(root.get("experiment"), "experiment")
    sample_sizes = tuple(int(value) for value in _sequence(experiment.get("sample_sizes"), "sample_sizes"))
    if not sample_sizes or any(value <= 0 for value in sample_sizes):
        raise ConfigError("sample_sizes must contain positive integers")
    if tuple(sorted(set(sample_sizes))) != sample_sizes:
        raise ConfigError("sample_sizes must be strictly increasing")

    families: list[ConjunctiveModel] = []
    for family_data in _sequence(root.get("families"), "families"):
        family = _mapping(family_data, "family")
        factors = tuple(
            Factor(
                id=str(item["id"]),
                probability=float(item["probability"]),
                role=str(item["role"]),
            )
            for item in (_mapping(value, "factor") for value in _sequence(family.get("factors"), "factors"))
        )
        observables = tuple(
            Observable(
                id=str(item["id"]),
                factors=tuple(str(value) for value in _sequence(item.get("factors"), "observable factors")),
                kind=str(item["kind"]),
            )
            for item in (
                _mapping(value, "observable")
                for value in _sequence(family.get("observables"), "observables")
            )
        )
        targets = tuple(
            Target(
                id=str(item["id"]),
                factors=tuple(str(value) for value in _sequence(item.get("factors"), "target factors")),
            )
            for item in (_mapping(value, "target") for value in _sequence(family.get("targets"), "targets"))
        )
        if not targets:
            raise ConfigError(f"family {family.get('id')!r} must define at least one target")
        families.append(
            ConjunctiveModel(
                id=str(family["id"]),
                factors=factors,
                observables=observables,
                targets=targets,
            )
        )

    policies: list[ObservationPolicy] = []
    for policy_data in _sequence(root.get("observation_modes"), "observation_modes"):
        policy = _mapping(policy_data, "observation mode")
        policies.append(
            ObservationPolicy(
                id=str(policy["id"]),
                mode=str(policy["mode"]),
                include_kinds=tuple(str(value) for value in policy.get("include_kinds", [])),
                drop_kinds=tuple(str(value) for value in policy.get("drop_kinds", [])),
                staggered_kinds=tuple(str(value) for value in policy.get("staggered_kinds", [])),
                sampling_by_kind={
                    str(key): float(value)
                    for key, value in _mapping(
                        policy.get("sampling_by_kind", {}),
                        "sampling_by_kind",
                    ).items()
                },
            )
        )

    result = ExperimentConfig(
        id=str(experiment["id"]),
        seed=int(experiment["seed"]),
        repetitions=int(experiment["repetitions"]),
        sample_sizes=sample_sizes,
        max_moment_order=int(experiment["max_moment_order"]),
        min_joint_observations=int(experiment["min_joint_observations"]),
        local_smoke_max_dataset_fits=int(experiment["local_smoke_max_dataset_fits"]),
        families=tuple(families),
        observation_modes=tuple(policies),
    )
    if result.repetitions <= 0:
        raise ConfigError("repetitions must be positive")
    if result.max_moment_order <= 0:
        raise ConfigError("max_moment_order must be positive")
    if result.min_joint_observations <= 0:
        raise ConfigError("min_joint_observations must be positive")
    if result.local_smoke_max_dataset_fits <= 0:
        raise ConfigError("local_smoke_max_dataset_fits must be positive")
    if not result.families:
        raise ConfigError("at least one family is required")
    if not result.observation_modes:
        raise ConfigError("at least one observation mode is required")
    _unique_ids(result.families, "family")
    _unique_ids(result.observation_modes, "observation mode")
    return result
