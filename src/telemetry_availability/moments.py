from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import ConjunctiveModel
from .observation import EpisodeBatch, ObservationPolicy, candidate_observable_subsets


@dataclass(frozen=True)
class MomentEstimate:
    observable_ids: tuple[str, ...]
    factor_vector: np.ndarray
    value: float
    observation_count: int


def structural_moment_rows(
    model: ConjunctiveModel,
    policy: ObservationPolicy,
    max_order: int,
) -> np.ndarray:
    rows: dict[tuple[int, ...], np.ndarray] = {}
    for positions in candidate_observable_subsets(model, max_order, policy):
        observable_ids = tuple(model.observables[position].id for position in positions)
        factors = model.factors_for_observables(observable_ids)
        row = model.factor_vector(factors)
        rows[tuple(int(value) for value in row)] = row
    if not rows:
        return np.zeros((0, len(model.factors)), dtype=float)
    return np.vstack([rows[key] for key in sorted(rows)])


def estimate_moments(
    model: ConjunctiveModel,
    batch: EpisodeBatch,
    max_order: int,
    min_observations: int,
) -> tuple[MomentEstimate, ...]:
    if min_observations <= 0:
        raise ValueError("min_observations must be positive")
    estimates: list[MomentEstimate] = []
    for positions in candidate_observable_subsets(model, max_order):
        joint_mask = np.all(batch.observed[:, positions], axis=1)
        count = int(np.count_nonzero(joint_mask))
        if count < min_observations:
            continue
        successes = np.all(batch.values[joint_mask][:, positions], axis=1)
        value = float(np.mean(successes))
        observable_ids = tuple(model.observables[position].id for position in positions)
        factors = model.factors_for_observables(observable_ids)
        estimates.append(
            MomentEstimate(
                observable_ids=observable_ids,
                factor_vector=model.factor_vector(factors),
                value=value,
                observation_count=count,
            )
        )
    return tuple(estimates)


def moment_matrix(estimates: tuple[MomentEstimate, ...], parameter_count: int) -> np.ndarray:
    if not estimates:
        return np.zeros((0, parameter_count), dtype=float)
    return np.vstack([item.factor_vector for item in estimates])


def canonical_moment_estimates(
    estimates: tuple[MomentEstimate, ...],
) -> tuple[MomentEstimate, ...]:
    """Select one highest-exposure estimate for every distinct factor union.

    Several observable subsets can imply the same primitive conjunction. Treating
    those algebraically duplicate rows as independent equations would silently
    double-count episodes. The initial baseline therefore keeps one deterministic
    representative and preserves all raw estimates separately for audit.
    """

    selected: dict[tuple[int, ...], MomentEstimate] = {}
    ordered = sorted(
        estimates,
        key=lambda item: (-item.observation_count, item.observable_ids),
    )
    for item in ordered:
        key = tuple(int(value) for value in item.factor_vector)
        selected.setdefault(key, item)
    return tuple(selected[key] for key in sorted(selected))
