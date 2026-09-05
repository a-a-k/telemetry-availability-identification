from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import ConjunctiveModel


@dataclass(frozen=True)
class IdentifiabilityReport:
    rank: int
    parameter_count: int
    singular_values: tuple[float, ...]
    condition_number: float | None
    parameter_identifiable: dict[str, bool]
    target_identifiable: dict[str, bool]

    @property
    def full_rank(self) -> bool:
        return self.rank == self.parameter_count


def _row_space_basis(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    if matrix.ndim != 2:
        raise ValueError("incidence matrix must be two-dimensional")
    if matrix.shape[0] == 0:
        return np.zeros((0, matrix.shape[1])), np.asarray([], dtype=float), 0
    _, singular_values, vh = np.linalg.svd(matrix, full_matrices=True)
    threshold = max(matrix.shape) * np.finfo(float).eps * singular_values[0]
    rank = int(np.count_nonzero(singular_values > threshold))
    return vh[:rank], singular_values, rank


def vector_in_row_space(vector: np.ndarray, row_basis: np.ndarray, tolerance: float = 1e-9) -> bool:
    if row_basis.shape[0] == 0:
        return bool(np.linalg.norm(vector) <= tolerance)
    projection = row_basis.T @ (row_basis @ vector)
    return bool(np.linalg.norm(vector - projection) <= tolerance * max(1.0, np.linalg.norm(vector)))


def diagnose_identifiability(
    model: ConjunctiveModel,
    incidence_matrix: np.ndarray,
) -> IdentifiabilityReport:
    if incidence_matrix.shape[1] != len(model.factors):
        raise ValueError("incidence matrix width does not match the model")
    row_basis, singular_values, rank = _row_space_basis(incidence_matrix)
    parameter_identifiable: dict[str, bool] = {}
    for index, factor_id in enumerate(model.factor_ids):
        unit = np.zeros(len(model.factors), dtype=float)
        unit[index] = 1.0
        parameter_identifiable[factor_id] = vector_in_row_space(unit, row_basis)

    target_identifiable = {
        target.id: vector_in_row_space(model.factor_vector(target.factors), row_basis)
        for target in model.targets
    }
    condition_number = None
    if rank:
        condition_number = float(singular_values[0] / singular_values[rank - 1])
    return IdentifiabilityReport(
        rank=rank,
        parameter_count=len(model.factors),
        singular_values=tuple(float(value) for value in singular_values),
        condition_number=condition_number,
        parameter_identifiable=parameter_identifiable,
        target_identifiable=target_identifiable,
    )
