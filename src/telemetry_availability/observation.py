from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable

import numpy as np

from .model import ConjunctiveModel


@dataclass(frozen=True)
class ObservationPolicy:
    """Known, state-independent observation mechanism for the first experiment."""

    id: str
    mode: str
    include_kinds: tuple[str, ...] = ()
    drop_kinds: tuple[str, ...] = ()
    staggered_kinds: tuple[str, ...] = ()
    sampling_by_kind: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        allowed = {"full", "only_kinds", "drop_kinds", "staggered"}
        if self.mode not in allowed:
            raise ValueError(f"unsupported observation mode {self.mode!r}")
        for kind, probability in self.sampling_by_kind.items():
            if not 0.0 <= probability <= 1.0:
                raise ValueError(
                    f"sampling probability for {kind!r} must be in [0, 1]"
                )

    def includes_kind(self, kind: str) -> bool:
        if self.mode == "only_kinds":
            return kind in self.include_kinds
        if self.mode == "drop_kinds":
            return kind not in self.drop_kinds
        return True

    def supports_joint(self, observable_kinds: Iterable[str]) -> bool:
        kinds = tuple(observable_kinds)
        if any(not self.includes_kind(kind) for kind in kinds):
            return False
        if any(self.sampling_by_kind.get(kind, 1.0) <= 0.0 for kind in kinds):
            return False
        for staggered_kind in self.staggered_kinds:
            if sum(kind == staggered_kind for kind in kinds) > 1:
                return False
        return True


@dataclass(frozen=True)
class EpisodeBatch:
    """Observable values and their availability mask for aligned episodes."""

    values: np.ndarray
    observed: np.ndarray

    def __post_init__(self) -> None:
        if self.values.dtype != np.bool_ or self.observed.dtype != np.bool_:
            raise TypeError("episode arrays must be boolean")
        if self.values.shape != self.observed.shape:
            raise ValueError("values and observed masks must have the same shape")
        if self.values.ndim != 2:
            raise ValueError("episode arrays must be two-dimensional")

    def prefix(self, size: int) -> "EpisodeBatch":
        if size <= 0 or size > self.values.shape[0]:
            raise ValueError("prefix size is outside the generated batch")
        return EpisodeBatch(self.values[:size], self.observed[:size])


def simulate_observable_values(
    model: ConjunctiveModel,
    episode_count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if episode_count <= 0:
        raise ValueError("episode_count must be positive")
    primitive = rng.random((episode_count, len(model.factors))) < model.factor_probabilities
    index = {name: position for position, name in enumerate(model.factor_ids)}
    columns = []
    for observable in model.observables:
        positions = [index[name] for name in observable.factors]
        columns.append(np.all(primitive[:, positions], axis=1))
    return np.column_stack(columns).astype(bool, copy=False)


def generate_observation_mask(
    model: ConjunctiveModel,
    episode_count: int,
    policy: ObservationPolicy,
    rng: np.random.Generator,
) -> np.ndarray:
    mask = np.zeros((episode_count, len(model.observables)), dtype=bool)
    kinds = tuple(item.kind for item in model.observables)

    for kind in sorted(set(kinds)):
        positions = [index for index, value in enumerate(kinds) if value == kind]
        if not policy.includes_kind(kind):
            continue

        keep_probability = policy.sampling_by_kind.get(kind, 1.0)
        group_kept = rng.random(episode_count) < keep_probability
        if kind in policy.staggered_kinds and positions:
            choices = rng.integers(0, len(positions), size=episode_count)
            for local_index, position in enumerate(positions):
                mask[:, position] = group_kept & (choices == local_index)
        else:
            mask[:, positions] = group_kept[:, None]

    return mask


def simulate_batch(
    model: ConjunctiveModel,
    episode_count: int,
    policy: ObservationPolicy,
    value_rng: np.random.Generator,
    mask_rng: np.random.Generator,
) -> EpisodeBatch:
    return EpisodeBatch(
        values=simulate_observable_values(model, episode_count, value_rng),
        observed=generate_observation_mask(model, episode_count, policy, mask_rng),
    )


def candidate_observable_subsets(
    model: ConjunctiveModel,
    max_order: int,
    policy: ObservationPolicy | None = None,
) -> tuple[tuple[int, ...], ...]:
    if max_order <= 0:
        raise ValueError("max_order must be positive")
    upper = min(max_order, len(model.observables))
    result: list[tuple[int, ...]] = []
    for order in range(1, upper + 1):
        for positions in combinations(range(len(model.observables)), order):
            if policy is not None:
                kinds = (model.observables[position].kind for position in positions)
                if not policy.supports_joint(kinds):
                    continue
            result.append(positions)
    return tuple(result)
