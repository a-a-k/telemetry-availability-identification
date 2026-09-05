from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .boolean_model import BooleanFactorModel, BooleanObservable, BooleanTarget
from .config import ConfigError, _mapping, _sequence
from .model import Factor
from .observation import ObservationPolicy


@dataclass(frozen=True)
class TransferScenario:
    id: str
    model: BooleanFactorModel


@dataclass(frozen=True)
class TransferExperimentConfig:
    id: str
    seed: int
    repetitions: int
    sample_sizes: tuple[int, ...]
    validation_episodes: int
    min_observations: int
    local_smoke_max_dataset_fits: int
    scenarios: tuple[TransferScenario, ...]
    observation_modes: tuple[ObservationPolicy, ...]


def _residual(marginal: float, domain: float, label: str) -> float:
    if not 0.0 < marginal <= domain < 1.0:
        raise ConfigError(
            f"{label} requires 0 < marginal <= domain < 1; got {marginal}, {domain}"
        )
    result = marginal / domain
    if not 0.0 < result < 1.0:
        raise ConfigError(f"{label} residual probability is outside (0, 1)")
    return result


def _scenario_model(data: dict[str, Any]) -> BooleanFactorModel:
    domain_a = float(data["domain_a_probability"])
    domain_b = float(data["domain_b_probability"])
    factors = (
        Factor("domain_a", domain_a, "domain"),
        Factor(
            "replica_a",
            _residual(float(data["replica_a_marginal"]), domain_a, "replica_a"),
            "instance_residual",
        ),
        Factor(
            "replica_b",
            _residual(float(data["replica_b_marginal"]), domain_a, "replica_b"),
            "instance_residual",
        ),
        Factor("domain_b", domain_b, "domain"),
        Factor(
            "anchor_a",
            _residual(float(data["anchor_a_marginal"]), domain_b, "anchor_a"),
            "instance_residual",
        ),
        Factor(
            "anchor_b",
            _residual(float(data["anchor_b_marginal"]), domain_b, "anchor_b"),
            "instance_residual",
        ),
    )
    observables = (
        BooleanObservable("replica_a_health", (("domain_a", "replica_a"),), "health"),
        BooleanObservable("replica_b_health", (("domain_a", "replica_b"),), "health"),
        BooleanObservable("anchor_a_health", (("domain_b", "anchor_a"),), "health"),
        BooleanObservable("anchor_b_health", (("domain_b", "anchor_b"),), "health"),
        BooleanObservable(
            "current_success",
            (("domain_a", "replica_a"), ("domain_a", "replica_b")),
            "trace",
        ),
        BooleanObservable(
            "anchor_success",
            (("domain_b", "anchor_a"), ("domain_b", "anchor_b")),
            "trace",
        ),
    )
    targets = (
        BooleanTarget(
            "current_same_domain",
            (("domain_a", "replica_a"), ("domain_a", "replica_b")),
        ),
        BooleanTarget(
            "split_across_domains",
            (("domain_a", "replica_a"), ("domain_b", "replica_b")),
        ),
    )
    return BooleanFactorModel(
        id=str(data["id"]),
        factors=factors,
        observables=observables,
        targets=targets,
    )


def load_transfer_config(path: str | Path) -> TransferExperimentConfig:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    root = _mapping(document, "transfer configuration")
    if root.get("schema_version") != 1:
        raise ConfigError("transfer schema_version must equal 1")
    experiment = _mapping(root.get("experiment"), "transfer experiment")
    sample_sizes = tuple(
        int(value) for value in _sequence(experiment.get("sample_sizes"), "sample_sizes")
    )
    if not sample_sizes or tuple(sorted(set(sample_sizes))) != sample_sizes:
        raise ConfigError("transfer sample_sizes must be strictly increasing")

    policies = tuple(
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
        for policy in (
            _mapping(value, "observation mode")
            for value in _sequence(root.get("observation_modes"), "observation_modes")
        )
    )
    scenarios = tuple(
        TransferScenario(id=str(data["id"]), model=_scenario_model(data))
        for data in (
            _mapping(value, "transfer scenario")
            for value in _sequence(root.get("scenarios"), "scenarios")
        )
    )
    result = TransferExperimentConfig(
        id=str(experiment["id"]),
        seed=int(experiment["seed"]),
        repetitions=int(experiment["repetitions"]),
        sample_sizes=sample_sizes,
        validation_episodes=int(experiment["validation_episodes"]),
        min_observations=int(experiment["min_observations"]),
        local_smoke_max_dataset_fits=int(experiment["local_smoke_max_dataset_fits"]),
        scenarios=scenarios,
        observation_modes=policies,
    )
    if (
        result.repetitions <= 0
        or result.validation_episodes <= 0
        or result.min_observations <= 0
        or result.local_smoke_max_dataset_fits <= 0
    ):
        raise ConfigError("transfer experiment counts must be positive")
    if len({scenario.id for scenario in scenarios}) != len(scenarios):
        raise ConfigError("duplicate transfer scenario id")
    if len({policy.id for policy in policies}) != len(policies):
        raise ConfigError("duplicate transfer observation mode id")
    if not scenarios or not policies:
        raise ConfigError("transfer experiment needs scenarios and observation modes")
    return result
