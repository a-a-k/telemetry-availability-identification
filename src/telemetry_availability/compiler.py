from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import prod

import numpy as np

from .diagnostics import IdentifiabilityReport, diagnose_identifiability
from .likelihood import enumerate_latent_states, observable_states
from .model import ConjunctiveModel, Factor, Observable, Target
from .moments import structural_moment_rows
from .observation import EpisodeBatch, ObservationPolicy


class IdentificationStatus(StrEnum):
    PROVED_IDENTIFIABLE = "proved_identifiable"
    PROVED_AMBIGUOUS = "proved_ambiguous"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class AmbiguityWitness:
    first_probabilities: tuple[float, ...]
    second_probabilities: tuple[float, ...]
    first_quantity: float
    second_quantity: float
    max_observable_moment_difference: float


@dataclass(frozen=True)
class CompiledFactorGroup:
    id: str
    members: tuple[str, ...]
    observable_signature: tuple[int, ...]
    probability: float


@dataclass(frozen=True)
class CompiledObservationModel:
    original_model: ConjunctiveModel
    policy: ObservationPolicy
    reduced_model: ConjunctiveModel | None
    observable_positions: tuple[int, ...]
    factor_groups: tuple[CompiledFactorGroup, ...]
    inactive_factors: tuple[str, ...]
    original_report: IdentifiabilityReport
    reduced_report: IdentifiabilityReport | None
    parameter_status: dict[str, IdentificationStatus]
    target_status: dict[str, IdentificationStatus]
    parameter_witnesses: dict[str, AmbiguityWitness]
    target_witnesses: dict[str, AmbiguityWitness]
    target_reduced_factors: dict[str, tuple[str, ...] | None]

    @property
    def original_state_count(self) -> int:
        return 2 ** len(self.original_model.factors)

    @property
    def reduced_state_count(self) -> int:
        return 0 if self.reduced_model is None else 2 ** len(self.reduced_model.factors)

    def reduce_batch(self, batch: EpisodeBatch) -> EpisodeBatch:
        if self.reduced_model is None:
            raise ValueError("compiled model has no supported observables")
        return EpisodeBatch(
            values=batch.values[:, self.observable_positions],
            observed=batch.observed[:, self.observable_positions],
        )


def _complete_structural_matrix(
    model: ConjunctiveModel,
    policy: ObservationPolicy,
) -> np.ndarray:
    return structural_moment_rows(model, policy, max_order=len(model.observables))


def _status(identifiable: bool) -> IdentificationStatus:
    return (
        IdentificationStatus.PROVED_IDENTIFIABLE
        if identifiable
        else IdentificationStatus.PROVED_AMBIGUOUS
    )


def _null_witness(
    model: ConjunctiveModel,
    matrix: np.ndarray,
    quantity: np.ndarray,
    epsilon: float = 1e-8,
) -> AmbiguityWitness | None:
    if matrix.shape[0] == 0:
        row_basis = np.zeros((0, matrix.shape[1]), dtype=float)
    else:
        _, singular_values, vh = np.linalg.svd(matrix, full_matrices=True)
        threshold = max(matrix.shape) * np.finfo(float).eps * singular_values[0]
        rank = int(np.count_nonzero(singular_values > threshold))
        row_basis = vh[:rank]
    if row_basis.shape[0]:
        residual = quantity - row_basis.T @ (row_basis @ quantity)
    else:
        residual = quantity.copy()
    if np.linalg.norm(residual) <= 1e-10:
        return None
    direction = residual / np.max(np.abs(residual))
    first_log = np.log(model.factor_probabilities)
    lower = np.log(epsilon)
    upper = np.log(1.0 - epsilon)

    candidates: list[tuple[float, np.ndarray]] = []
    for sign in (-1.0, 1.0):
        signed = sign * direction
        limits = []
        for value, delta in zip(first_log, signed, strict=True):
            if delta > 0:
                limits.append((upper - value) / delta)
            elif delta < 0:
                limits.append((lower - value) / delta)
        positive_limits = [limit for limit in limits if limit > 0]
        if positive_limits:
            step = min(0.5, 0.5 * min(positive_limits))
            if step > 1e-8:
                candidates.append((step, signed))
    if not candidates:
        return None
    step, signed_direction = max(
        candidates,
        key=lambda item: abs(float(quantity @ (item[0] * item[1]))),
    )
    second_log = first_log + step * signed_direction
    first_moments = np.exp(matrix @ first_log) if matrix.shape[0] else np.asarray([])
    second_moments = np.exp(matrix @ second_log) if matrix.shape[0] else np.asarray([])
    maximum_difference = (
        float(np.max(np.abs(first_moments - second_moments)))
        if first_moments.size
        else 0.0
    )
    return AmbiguityWitness(
        first_probabilities=tuple(float(value) for value in np.exp(first_log)),
        second_probabilities=tuple(float(value) for value in np.exp(second_log)),
        first_quantity=float(np.exp(quantity @ first_log)),
        second_quantity=float(np.exp(quantity @ second_log)),
        max_observable_moment_difference=maximum_difference,
    )


def _group_id(members: tuple[str, ...]) -> str:
    return members[0] if len(members) == 1 else "product__" + "__".join(members)


def compile_observation_model(
    model: ConjunctiveModel,
    policy: ObservationPolicy,
) -> CompiledObservationModel:
    matrix = _complete_structural_matrix(model, policy)
    original_report = diagnose_identifiability(model, matrix)
    parameter_status = {
        factor.id: _status(original_report.parameter_identifiable[factor.id])
        for factor in model.factors
    }
    target_status = {
        target.id: _status(original_report.target_identifiable[target.id])
        for target in model.targets
    }
    parameter_witnesses: dict[str, AmbiguityWitness] = {}
    for index, factor in enumerate(model.factors):
        if parameter_status[factor.id] == IdentificationStatus.PROVED_AMBIGUOUS:
            quantity = np.zeros(len(model.factors), dtype=float)
            quantity[index] = 1.0
            witness = _null_witness(model, matrix, quantity)
            if witness is None:
                parameter_status[factor.id] = IdentificationStatus.UNRESOLVED
            else:
                parameter_witnesses[factor.id] = witness
    target_witnesses: dict[str, AmbiguityWitness] = {}
    for target in model.targets:
        if target_status[target.id] == IdentificationStatus.PROVED_AMBIGUOUS:
            witness = _null_witness(model, matrix, model.factor_vector(target.factors))
            if witness is None:
                target_status[target.id] = IdentificationStatus.UNRESOLVED
            else:
                target_witnesses[target.id] = witness

    observable_positions = tuple(
        index
        for index, observable in enumerate(model.observables)
        if policy.includes_kind(observable.kind)
        and policy.sampling_by_kind.get(observable.kind, 1.0) > 0.0
    )
    if not observable_positions:
        return CompiledObservationModel(
            original_model=model,
            policy=policy,
            reduced_model=None,
            observable_positions=(),
            factor_groups=(),
            inactive_factors=model.factor_ids,
            original_report=original_report,
            reduced_report=None,
            parameter_status=parameter_status,
            target_status=target_status,
            parameter_witnesses=parameter_witnesses,
            target_witnesses=target_witnesses,
            target_reduced_factors={target.id: None for target in model.targets},
        )

    signatures: dict[tuple[int, ...], list[str]] = {}
    for factor_id in model.factor_ids:
        signature = tuple(
            int(factor_id in model.observables[position].factors)
            for position in observable_positions
        )
        signatures.setdefault(signature, []).append(factor_id)
    inactive = tuple(signatures.pop(tuple(0 for _ in observable_positions), []))
    groups = tuple(
        CompiledFactorGroup(
            id=_group_id(tuple(members)),
            members=tuple(members),
            observable_signature=signature,
            probability=float(
                prod(
                    factor.probability
                    for factor in model.factors
                    if factor.id in members
                )
            ),
        )
        for signature, members in sorted(signatures.items())
    )
    factor_to_group = {
        member: group.id
        for group in groups
        for member in group.members
    }
    original_factor_lookup = {factor.id: factor for factor in model.factors}
    reduced_factors = tuple(
        Factor(
            id=group.id,
            probability=group.probability,
            role=(
                original_factor_lookup[group.members[0]].role
                if len(group.members) == 1
                else "identified_product"
            ),
        )
        for group in groups
    )
    reduced_observables = tuple(
        Observable(
            id=model.observables[position].id,
            kind=model.observables[position].kind,
            factors=tuple(
                group.id
                for group in groups
                if any(
                    member in model.observables[position].factors
                    for member in group.members
                )
            ),
        )
        for position in observable_positions
    )

    target_reduced_factors: dict[str, tuple[str, ...] | None] = {}
    reduced_targets: list[Target] = []
    for target in model.targets:
        selected = set(target.factors)
        representable = not bool(selected.intersection(inactive))
        mapped: list[str] = []
        for group in groups:
            intersection = selected.intersection(group.members)
            if intersection and intersection != set(group.members):
                representable = False
                break
            if intersection:
                mapped.append(group.id)
        if representable and mapped:
            target_reduced_factors[target.id] = tuple(mapped)
            reduced_targets.append(Target(target.id, tuple(mapped)))
        else:
            target_reduced_factors[target.id] = None

    reduced_model = ConjunctiveModel(
        id=f"{model.id}__{policy.id}__reduced",
        factors=reduced_factors,
        observables=reduced_observables,
        targets=tuple(reduced_targets),
    )
    reduced_report = diagnose_identifiability(
        reduced_model,
        _complete_structural_matrix(reduced_model, policy),
    )
    return CompiledObservationModel(
        original_model=model,
        policy=policy,
        reduced_model=reduced_model,
        observable_positions=observable_positions,
        factor_groups=groups,
        inactive_factors=inactive,
        original_report=original_report,
        reduced_report=reduced_report,
        parameter_status=parameter_status,
        target_status=target_status,
        parameter_witnesses=parameter_witnesses,
        target_witnesses=target_witnesses,
        target_reduced_factors=target_reduced_factors,
    )


def exact_observable_distribution(model: ConjunctiveModel) -> dict[tuple[bool, ...], float]:
    latent = enumerate_latent_states(len(model.factors))
    states = observable_states(model, latent)
    probabilities = model.factor_probabilities
    float_states = latent.astype(float)
    weights = np.exp(
        float_states @ np.log(probabilities)
        + (1.0 - float_states) @ np.log1p(-probabilities)
    )
    distribution: dict[tuple[bool, ...], float] = {}
    for state, weight in zip(states, weights, strict=True):
        key = tuple(bool(value) for value in state)
        distribution[key] = distribution.get(key, 0.0) + float(weight)
    return distribution
