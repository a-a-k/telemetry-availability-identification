from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .boolean_model import BooleanFactorModel
from .observation import EpisodeBatch


TARGET_CURRENT = "current_same_domain"
TARGET_SPLIT = "split_across_domains"
TARGET_ADD = "add_same_type_replica"
TARGET_IDS = (TARGET_CURRENT, TARGET_SPLIT, TARGET_ADD)


@dataclass(frozen=True)
class ParameterEstimate:
    status: str
    probabilities: dict[str, float] | None
    source: str = ""


def transfer_probabilities(
    model: BooleanFactorModel,
    probabilities: dict[str, float] | None = None,
) -> dict[str, float]:
    values = (
        {factor.id: factor.probability for factor in model.factors}
        if probabilities is None
        else probabilities
    )
    gamma_a = values["domain_a"]
    eta_a = values["replica_a"]
    eta_b = values["replica_b"]
    gamma_b = values["domain_b"]
    current = gamma_a * (1.0 - (1.0 - eta_a) * (1.0 - eta_b))
    split = 1.0 - (1.0 - gamma_a * eta_a) * (1.0 - gamma_b * eta_b)
    add = gamma_a * (1.0 - (1.0 - eta_a) * (1.0 - eta_b) ** 2)
    return {
        TARGET_CURRENT: float(current),
        TARGET_SPLIT: float(split),
        TARGET_ADD: float(add),
    }


def _moment(batch: EpisodeBatch, positions: tuple[int, ...], minimum: int) -> float | None:
    observed = np.all(batch.observed[:, positions], axis=1)
    count = int(np.count_nonzero(observed))
    if count < minimum:
        return None
    return float(np.mean(np.all(batch.values[observed][:, positions], axis=1)))


def fit_available_domain_moments(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    minimum: int,
) -> ParameterEstimate:
    positions = {observable.id: index for index, observable in enumerate(model.observables)}
    pairs = (
        (
            "domain_a",
            "replica_a",
            "replica_b",
            "replica_a_health",
            "replica_b_health",
            "current_success",
        ),
        (
            "domain_b",
            "anchor_a",
            "anchor_b",
            "anchor_a_health",
            "anchor_b_health",
            "anchor_success",
        ),
    )
    estimates: dict[str, float] = {}
    sources: list[str] = []
    for (
        domain,
        first_factor,
        second_factor,
        first_observable,
        second_observable,
        union_observable,
    ) in pairs:
        first_position = positions[first_observable]
        second_position = positions[second_observable]
        first = _moment(batch, (first_position,), minimum)
        second = _moment(batch, (second_position,), minimum)
        joint = _moment(batch, (first_position, second_position), minimum)
        union = _moment(batch, (positions[union_observable],), minimum)
        if first is None or second is None:
            return ParameterEstimate("insufficient_health_marginals", None)
        if joint is not None and joint > 0.0:
            overlap = joint
            sources.append("joint_health")
        elif union is not None and first + second - union > 0.0:
            overlap = first + second - union
            sources.append("health_marginals_plus_or_trace")
        else:
            return ParameterEstimate("insufficient_domain_moment", None)
        raw_domain = first * second / overlap
        domain_estimate = float(np.clip(raw_domain, max(first, second, 1e-6), 1.0 - 1e-6))
        estimates[domain] = domain_estimate
        estimates[first_factor] = float(np.clip(first / domain_estimate, 1e-6, 1.0 - 1e-6))
        estimates[second_factor] = float(np.clip(second / domain_estimate, 1e-6, 1.0 - 1e-6))
    return ParameterEstimate("complete", estimates, "+".join(sources))


def health_marginals(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    minimum: int,
) -> dict[str, float] | None:
    positions = {observable.id: index for index, observable in enumerate(model.observables)}
    result: dict[str, float] = {}
    for observable_id in ("replica_a_health", "replica_b_health"):
        value = _moment(batch, (positions[observable_id],), minimum)
        if value is None:
            return None
        result[observable_id] = value
    return result


def direct_current_rate(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    minimum: int,
) -> float | None:
    position = next(
        index
        for index, observable in enumerate(model.observables)
        if observable.id == "current_success"
    )
    return _moment(batch, (position,), minimum)


def empirical_joint_current_rate(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    minimum: int,
) -> float | None:
    positions = {observable.id: index for index, observable in enumerate(model.observables)}
    selected = (
        positions["replica_a_health"],
        positions["replica_b_health"],
    )
    observed = np.all(batch.observed[:, selected], axis=1)
    count = int(np.count_nonzero(observed))
    if count < minimum:
        return None
    values = batch.values[observed][:, selected]
    return float(np.mean(np.any(values, axis=1)))


def independent_predictions(marginals: dict[str, float]) -> dict[str, float]:
    first = marginals["replica_a_health"]
    second = marginals["replica_b_health"]
    return {
        TARGET_CURRENT: 1.0 - (1.0 - first) * (1.0 - second),
        TARGET_SPLIT: 1.0 - (1.0 - first) * (1.0 - second),
        TARGET_ADD: 1.0 - (1.0 - first) * (1.0 - second) ** 2,
    }
