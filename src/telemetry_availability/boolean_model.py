from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable

import numpy as np

from .model import Factor, ModelValidationError


@dataclass(frozen=True)
class BooleanObservable:
    """A binary observable represented as OR over conjunctive clauses."""

    id: str
    clauses: tuple[tuple[str, ...], ...]
    kind: str

    def __post_init__(self) -> None:
        if not self.id or not self.kind:
            raise ModelValidationError("Boolean observable id and kind must not be empty")
        if not self.clauses or any(not clause for clause in self.clauses):
            raise ModelValidationError(f"Boolean observable {self.id!r} needs nonempty clauses")
        if any(len(set(clause)) != len(clause) for clause in self.clauses):
            raise ModelValidationError(f"Boolean observable {self.id!r} repeats a factor")


@dataclass(frozen=True)
class BooleanTarget:
    id: str
    clauses: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ModelValidationError("Boolean target id must not be empty")
        if not self.clauses or any(not clause for clause in self.clauses):
            raise ModelValidationError(f"Boolean target {self.id!r} needs nonempty clauses")
        if any(len(set(clause)) != len(clause) for clause in self.clauses):
            raise ModelValidationError(f"Boolean target {self.id!r} repeats a factor")


@dataclass(frozen=True)
class BooleanFactorModel:
    id: str
    factors: tuple[Factor, ...]
    observables: tuple[BooleanObservable, ...]
    targets: tuple[BooleanTarget, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.factors or not self.observables:
            raise ModelValidationError("Boolean model needs an id, factors, and observables")
        self._require_unique("factor", (item.id for item in self.factors))
        self._require_unique("observable", (item.id for item in self.observables))
        self._require_unique("target", (item.id for item in self.targets))
        known = set(self.factor_ids)
        for item in (*self.observables, *self.targets):
            referenced = {factor for clause in item.clauses for factor in clause}
            unknown = referenced - known
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
    def factor_probabilities(self) -> np.ndarray:
        return np.asarray([item.probability for item in self.factors], dtype=float)

    @property
    def observable_ids(self) -> tuple[str, ...]:
        return tuple(item.id for item in self.observables)

    def exact_probability(self, clauses: tuple[tuple[str, ...], ...]) -> float:
        index = {factor_id: position for position, factor_id in enumerate(self.factor_ids)}
        total = 0.0
        probabilities = self.factor_probabilities
        for raw_state in product((False, True), repeat=len(self.factors)):
            state = np.asarray(raw_state, dtype=bool)
            satisfied = any(
                all(state[index[factor_id]] for factor_id in clause)
                for clause in clauses
            )
            if not satisfied:
                continue
            weight = float(
                np.prod(np.where(state, probabilities, 1.0 - probabilities))
            )
            total += weight
        return total


def clauses_for(item: object) -> tuple[tuple[str, ...], ...]:
    clauses = getattr(item, "clauses", None)
    if clauses is not None:
        return tuple(tuple(str(factor) for factor in clause) for clause in clauses)
    factors = getattr(item, "factors")
    return (tuple(str(factor) for factor in factors),)
