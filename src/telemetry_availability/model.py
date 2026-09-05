from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Iterable

import numpy as np


class ModelValidationError(ValueError):
    """Raised when an experiment model is internally inconsistent."""


@dataclass(frozen=True)
class Factor:
    """An independent primitive Bernoulli live factor."""

    id: str
    probability: float
    role: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelValidationError("factor id must not be empty")
        if not 0.0 < self.probability < 1.0:
            raise ModelValidationError(
                f"factor {self.id!r} probability must be strictly between zero and one"
            )
        if not self.role:
            raise ModelValidationError(f"factor {self.id!r} role must not be empty")


@dataclass(frozen=True)
class Observable:
    """A binary observable equal to the conjunction of primitive factors."""

    id: str
    factors: tuple[str, ...]
    kind: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelValidationError("observable id must not be empty")
        if not self.factors:
            raise ModelValidationError(f"observable {self.id!r} needs at least one factor")
        if len(set(self.factors)) != len(self.factors):
            raise ModelValidationError(f"observable {self.id!r} repeats a factor")
        if not self.kind:
            raise ModelValidationError(f"observable {self.id!r} kind must not be empty")


@dataclass(frozen=True)
class Target:
    """A conjunctive availability target covered by the initial T1 submodel."""

    id: str
    factors: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelValidationError("target id must not be empty")
        if not self.factors:
            raise ModelValidationError(f"target {self.id!r} needs at least one factor")
        if len(set(self.factors)) != len(self.factors):
            raise ModelValidationError(f"target {self.id!r} repeats a factor")


@dataclass(frozen=True)
class ConjunctiveModel:
    """Finite primitive-factor model used by the rank-based T1 experiment."""

    id: str
    factors: tuple[Factor, ...]
    observables: tuple[Observable, ...]
    targets: tuple[Target, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelValidationError("model id must not be empty")
        self._require_unique("factor", (item.id for item in self.factors))
        self._require_unique("observable", (item.id for item in self.observables))
        self._require_unique("target", (item.id for item in self.targets))
        if not self.factors:
            raise ModelValidationError(f"model {self.id!r} has no factors")
        if not self.observables:
            raise ModelValidationError(f"model {self.id!r} has no observables")
        if not self.targets:
            raise ModelValidationError(f"model {self.id!r} has no targets")

        known = set(self.factor_ids)
        for item in (*self.observables, *self.targets):
            unknown = set(item.factors) - known
            if unknown:
                raise ModelValidationError(
                    f"{item.id!r} references unknown factors: {sorted(unknown)}"
                )

    @staticmethod
    def _require_unique(label: str, values: Iterable[str]) -> None:
        materialized = tuple(values)
        if len(set(materialized)) != len(materialized):
            raise ModelValidationError(f"duplicate {label} id")

    @property
    def factor_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.factors)

    @property
    def observable_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.observables)

    @property
    def factor_probabilities(self) -> np.ndarray:
        return np.asarray([item.probability for item in self.factors], dtype=float)

    def factor_vector(self, factors: Iterable[str]) -> np.ndarray:
        selected = set(factors)
        return np.asarray([int(name in selected) for name in self.factor_ids], dtype=float)

    def factors_for_observables(self, observable_ids: Iterable[str]) -> tuple[str, ...]:
        requested = set(observable_ids)
        lookup = {item.id: item for item in self.observables}
        unknown = requested - set(lookup)
        if unknown:
            raise KeyError(f"unknown observables: {sorted(unknown)}")
        union: set[str] = set()
        for observable_id in requested:
            union.update(lookup[observable_id].factors)
        return tuple(name for name in self.factor_ids if name in union)

    def exact_factor_conjunction(self, factors: Iterable[str]) -> float:
        lookup = {item.id: item.probability for item in self.factors}
        requested = tuple(factors)
        unknown = set(requested) - set(lookup)
        if unknown:
            raise KeyError(f"unknown factors: {sorted(unknown)}")
        return float(prod(lookup[name] for name in set(requested)))

    def exact_moment(self, observable_ids: Iterable[str]) -> float:
        return self.exact_factor_conjunction(
            self.factors_for_observables(observable_ids)
        )

    def exact_target(self, target_id: str) -> float:
        target = next((item for item in self.targets if item.id == target_id), None)
        if target is None:
            raise KeyError(f"unknown target: {target_id}")
        return self.exact_factor_conjunction(target.factors)
