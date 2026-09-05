from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import log

import numpy as np
from scipy.optimize import OptimizeResult, minimize
from scipy.special import expit, logit

from .model import ConjunctiveModel
from .observation import EpisodeBatch


@dataclass(frozen=True)
class ObservedPatternTable:
    """Compressed sufficient input for the exact observed-data likelihood."""

    masks: np.ndarray
    values: np.ndarray
    counts: np.ndarray
    latent_states: np.ndarray
    compatible_states: np.ndarray

    @property
    def pattern_count(self) -> int:
        return int(self.counts.size)

    @property
    def informative_episode_count(self) -> int:
        informative = np.any(self.masks, axis=1)
        return int(np.sum(self.counts[informative]))


@dataclass(frozen=True)
class ExactLikelihoodFit:
    status: str
    converged: bool
    probabilities: np.ndarray | None
    negative_log_likelihood: float | None
    iterations: int
    gradient_infinity_norm: float | None
    boundary_parameter_count: int
    successful_starts: int
    attempted_starts: int
    near_optimal_parameter_spread: float | None
    objective_spread: float | None
    message: str


def enumerate_latent_states(parameter_count: int) -> np.ndarray:
    """Enumerate states independently of the simulator's random draw path."""

    if parameter_count <= 0:
        raise ValueError("parameter_count must be positive")
    return np.asarray(tuple(product((False, True), repeat=parameter_count)), dtype=bool)


def observable_states(model: ConjunctiveModel, latent_states: np.ndarray) -> np.ndarray:
    if latent_states.ndim != 2 or latent_states.shape[1] != len(model.factors):
        raise ValueError("latent state table does not match the model")
    factor_index = {factor_id: index for index, factor_id in enumerate(model.factor_ids)}
    columns = []
    for observable in model.observables:
        positions = [factor_index[factor_id] for factor_id in observable.factors]
        columns.append(np.all(latent_states[:, positions], axis=1))
    return np.column_stack(columns).astype(bool, copy=False)


def compress_observed_patterns(
    model: ConjunctiveModel,
    batch: EpisodeBatch,
) -> ObservedPatternTable:
    if batch.values.shape[1] != len(model.observables):
        raise ValueError("episode batch does not match the model")

    counts: dict[tuple[tuple[bool, ...], tuple[bool, ...]], int] = {}
    for observed, values in zip(batch.observed, batch.values, strict=True):
        mask_key = tuple(bool(value) for value in observed)
        value_key = tuple(bool(value and is_observed) for value, is_observed in zip(values, observed, strict=True))
        key = (mask_key, value_key)
        counts[key] = counts.get(key, 0) + 1

    ordered = sorted(counts)
    masks = np.asarray([key[0] for key in ordered], dtype=bool)
    values = np.asarray([key[1] for key in ordered], dtype=bool)
    frequencies = np.asarray([counts[key] for key in ordered], dtype=np.int64)
    latent = enumerate_latent_states(len(model.factors))
    observable = observable_states(model, latent)
    compatibility = np.ones((len(ordered), len(latent)), dtype=bool)
    for row, (mask, value) in enumerate(zip(masks, values, strict=True)):
        if np.any(mask):
            compatibility[row] = np.all(observable[:, mask] == value[mask], axis=1)

    if np.any(np.sum(compatibility, axis=1) == 0):
        raise ValueError("an observed pattern is impossible under the compiled model")
    return ObservedPatternTable(
        masks=masks,
        values=values,
        counts=frequencies,
        latent_states=latent,
        compatible_states=compatibility,
    )


def _state_probabilities(probabilities: np.ndarray, latent_states: np.ndarray) -> np.ndarray:
    state = latent_states.astype(float)
    log_weights = state @ np.log(probabilities) + (1.0 - state) @ np.log1p(-probabilities)
    return np.exp(log_weights)


def negative_log_likelihood_and_gradient(
    logits: np.ndarray,
    table: ObservedPatternTable,
) -> tuple[float, np.ndarray]:
    probabilities = expit(logits)
    weights = _state_probabilities(probabilities, table.latent_states)
    compatibility = table.compatible_states.astype(float)
    pattern_probabilities = compatibility @ weights
    if np.any(pattern_probabilities <= 0.0) or not np.all(np.isfinite(pattern_probabilities)):
        return float("inf"), np.full_like(logits, np.nan)

    counts = table.counts.astype(float)
    negative_log_likelihood = -float(counts @ np.log(pattern_probabilities))
    state_scores = table.latent_states.astype(float) - probabilities[None, :]
    pattern_derivatives = compatibility @ (weights[:, None] * state_scores)
    gradient = -np.sum(
        (counts / pattern_probabilities)[:, None] * pattern_derivatives,
        axis=0,
    )
    return negative_log_likelihood, gradient


def negative_log_likelihood(
    probabilities: np.ndarray,
    table: ObservedPatternTable,
) -> float:
    vector = np.asarray(probabilities, dtype=float)
    if vector.shape != (table.latent_states.shape[1],):
        raise ValueError("probability vector does not match the pattern table")
    if np.any(vector <= 0.0) or np.any(vector >= 1.0):
        raise ValueError("probabilities must lie strictly between zero and one")
    value, _ = negative_log_likelihood_and_gradient(logit(vector), table)
    return value


def exact_target_probability(model: ConjunctiveModel, factor_ids: tuple[str, ...]) -> float:
    """Compute a target truth by latent-state enumeration, not product shortcut."""

    latent = enumerate_latent_states(len(model.factors))
    probabilities = model.factor_probabilities
    weights = _state_probabilities(probabilities, latent)
    index = {factor_id: position for position, factor_id in enumerate(model.factor_ids)}
    unknown = set(factor_ids) - set(index)
    if unknown:
        raise KeyError(f"unknown target factors: {sorted(unknown)}")
    selected = [index[factor_id] for factor_id in factor_ids]
    satisfied = np.all(latent[:, selected], axis=1)
    return float(np.sum(weights[satisfied]))


def _candidate_starts(
    parameter_count: int,
    initial_probabilities: np.ndarray | None,
) -> tuple[np.ndarray, ...]:
    starts: list[np.ndarray] = []
    if initial_probabilities is not None:
        initial = np.asarray(initial_probabilities, dtype=float)
        if initial.shape != (parameter_count,):
            raise ValueError("initial probabilities do not match the model")
        starts.append(initial)
    starts.extend(
        np.full(parameter_count, value, dtype=float)
        for value in (0.5, 0.8, 0.95)
    )
    unique: list[np.ndarray] = []
    for candidate in starts:
        if not any(np.allclose(candidate, existing) for existing in unique):
            unique.append(candidate)
    return tuple(unique)


def fit_exact_observed_likelihood(
    model: ConjunctiveModel,
    table: ObservedPatternTable,
    initial_probabilities: np.ndarray | None = None,
    epsilon: float = 1e-6,
) -> ExactLikelihoodFit:
    if not 0.0 < epsilon < 0.5:
        raise ValueError("epsilon must lie in (0, 0.5)")
    if table.informative_episode_count == 0:
        return ExactLikelihoodFit(
            status="no_observations",
            converged=False,
            probabilities=None,
            negative_log_likelihood=None,
            iterations=0,
            gradient_infinity_norm=None,
            boundary_parameter_count=0,
            successful_starts=0,
            attempted_starts=0,
            near_optimal_parameter_spread=None,
            objective_spread=None,
            message="no observable values were retained",
        )

    lower = log(epsilon / (1.0 - epsilon))
    upper = -lower
    starts = _candidate_starts(len(model.factors), initial_probabilities)
    results: list[OptimizeResult] = []
    for start in starts:
        clipped = np.clip(start, epsilon, 1.0 - epsilon)
        result = minimize(
            negative_log_likelihood_and_gradient,
            logit(clipped),
            args=(table,),
            method="L-BFGS-B",
            jac=True,
            bounds=[(lower, upper)] * len(model.factors),
            options={"maxiter": 1_000, "ftol": 1e-12, "gtol": 1e-8, "maxls": 50},
        )
        results.append(result)

    finite = [result for result in results if np.isfinite(float(result.fun))]
    if not finite:
        return ExactLikelihoodFit(
            status="optimization_failed",
            converged=False,
            probabilities=None,
            negative_log_likelihood=None,
            iterations=max((int(result.nit) for result in results), default=0),
            gradient_infinity_norm=None,
            boundary_parameter_count=0,
            successful_starts=0,
            attempted_starts=len(results),
            near_optimal_parameter_spread=None,
            objective_spread=None,
            message="all starts returned non-finite objectives",
        )

    successful = [result for result in finite if bool(result.success)]
    selection_pool = successful if successful else finite
    best = min(selection_pool, key=lambda result: float(result.fun))
    best_probabilities = expit(np.asarray(best.x, dtype=float))
    objective_values = np.asarray([float(result.fun) for result in finite])
    tolerance = 1e-7 * max(1.0, abs(float(best.fun)))
    near_optimal = [
        expit(np.asarray(result.x, dtype=float))
        for result in selection_pool
        if float(result.fun) - float(best.fun) <= tolerance
    ]
    parameter_spread = 0.0
    if len(near_optimal) > 1:
        stack = np.vstack(near_optimal)
        parameter_spread = float(np.max(np.ptp(stack, axis=0)))
    gradient = np.asarray(best.jac, dtype=float)
    gradient_norm = float(np.max(np.abs(gradient))) if gradient.size else 0.0
    converged = bool(best.success) and np.all(np.isfinite(best_probabilities))
    boundary_count = int(
        np.count_nonzero(
            (best_probabilities <= epsilon * 1.01)
            | (best_probabilities >= 1.0 - epsilon * 1.01)
        )
    )
    if not converged:
        status = "optimization_failed"
    elif parameter_spread > 1e-3:
        status = "converged_nonunique"
    elif boundary_count:
        status = "converged_boundary"
    else:
        status = "converged"

    return ExactLikelihoodFit(
        status=status,
        converged=converged,
        probabilities=best_probabilities,
        negative_log_likelihood=float(best.fun),
        iterations=int(best.nit),
        gradient_infinity_norm=gradient_norm,
        boundary_parameter_count=boundary_count,
        successful_starts=len(successful),
        attempted_starts=len(results),
        near_optimal_parameter_spread=parameter_spread,
        objective_spread=float(np.max(objective_values) - np.min(objective_values)),
        message=str(best.message),
    )
