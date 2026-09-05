from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Callable, Iterable

import numpy as np
from scipy.optimize import OptimizeResult, minimize
from scipy.special import expit, logit
from scipy.stats import chi2, fisher_exact

from .boolean_model import BooleanFactorModel, BooleanObservable, BooleanTarget
from .likelihood import (
    ExactLikelihoodFit,
    ObservedPatternTable,
    compress_observed_patterns,
    observable_states,
)
from .model import Factor
from .observation import EpisodeBatch
from .transfer import TARGET_ADD, TARGET_CURRENT, TARGET_SPLIT
from .uncertainty import (
    CHOICE_DIFFERENCE,
    DELTA_ADD,
    DELTA_SPLIT,
    IntervalEstimate,
    clopper_pearson_interval,
    quantity_values,
)


@dataclass(frozen=True)
class DiagnosticResult:
    id: str
    statistic: float | None
    p_value: float | None
    threshold: float
    evidence_count: int
    flagged: bool
    status: str


def iid_latent_states(
    model: BooleanFactorModel,
    episode_count: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if episode_count <= 0:
        raise ValueError("episode_count must be positive")
    return rng.random((episode_count, len(model.factors))) < model.factor_probabilities


def markov_latent_states(
    model: BooleanFactorModel,
    episode_count: int,
    lag1_autocorrelation: float,
    rng: np.random.Generator,
) -> np.ndarray:
    if episode_count <= 0:
        raise ValueError("episode_count must be positive")
    if not 0.0 <= lag1_autocorrelation < 1.0:
        raise ValueError("lag-one autocorrelation must lie in [0, 1)")
    probabilities = model.factor_probabilities
    result = np.empty((episode_count, len(probabilities)), dtype=bool)
    result[0] = rng.random(len(probabilities)) < probabilities
    up_after_up = probabilities + lag1_autocorrelation * (1.0 - probabilities)
    up_after_down = probabilities * (1.0 - lag1_autocorrelation)
    for row in range(1, episode_count):
        transition = np.where(result[row - 1], up_after_up, up_after_down)
        result[row] = rng.random(len(probabilities)) < transition
    return result


def full_batch(
    model: BooleanFactorModel,
    latent_states: np.ndarray,
) -> EpisodeBatch:
    values = observable_states(model, latent_states)
    return EpisodeBatch(values=values, observed=np.ones_like(values, dtype=bool))


def exporter_loss_batch(
    model: BooleanFactorModel,
    latent_states: np.ndarray,
    retention_when_domain_up: float,
    retention_when_domain_down: float,
    health_rng: np.random.Generator,
    trace_rng: np.random.Generator,
) -> EpisodeBatch:
    values = observable_states(model, latent_states)
    observed = np.zeros_like(values, dtype=bool)
    health_positions = np.asarray(
        [index for index, item in enumerate(model.observables) if item.kind == "health"],
        dtype=int,
    )
    trace_positions = np.asarray(
        [index for index, item in enumerate(model.observables) if item.kind == "trace"],
        dtype=int,
    )
    choices = health_rng.integers(0, len(health_positions), size=len(latent_states))
    observed[np.arange(len(latent_states)), health_positions[choices]] = True
    domain_position = model.factor_ids.index("domain_a")
    retention = np.where(
        latent_states[:, domain_position],
        retention_when_domain_up,
        retention_when_domain_down,
    )
    kept = trace_rng.random(len(latent_states)) < retention
    observed[:, trace_positions] = kept[:, None]
    return EpisodeBatch(values=values, observed=observed)


def _binary_fisher_diagnostic(
    diagnostic_id: str,
    group: np.ndarray,
    outcome: np.ndarray,
    alpha: float,
) -> DiagnosticResult:
    group = np.asarray(group, dtype=bool)
    outcome = np.asarray(outcome, dtype=bool)
    if group.shape != outcome.shape:
        raise ValueError("diagnostic vectors must have the same shape")
    group_count = int(np.count_nonzero(group))
    other_count = int(len(group) - group_count)
    if group_count == 0 or other_count == 0:
        return DiagnosticResult(
            diagnostic_id,
            None,
            None,
            alpha,
            len(group),
            False,
            "insufficient_groups",
        )
    success_group = int(np.count_nonzero(outcome & group))
    success_other = int(np.count_nonzero(outcome & ~group))
    table = np.asarray(
        [
            [success_group, group_count - success_group],
            [success_other, other_count - success_other],
        ],
        dtype=int,
    )
    result = fisher_exact(table, alternative="two-sided")
    statistic = success_group / group_count - success_other / other_count
    p_value = float(result.pvalue)
    return DiagnosticResult(
        diagnostic_id,
        float(statistic),
        p_value,
        alpha,
        len(group),
        p_value < alpha,
        "complete",
    )


def exporter_mask_diagnostic(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    alpha: float,
) -> DiagnosticResult:
    positions = {item.id: index for index, item in enumerate(model.observables)}
    trace_position = positions["current_success"]
    health_positions = [positions["replica_a_health"], positions["replica_b_health"]]
    selected = np.any(batch.observed[:, health_positions], axis=1)
    if not np.any(selected):
        return DiagnosticResult(
            "trace_mask_vs_domain_a_health",
            None,
            None,
            alpha,
            0,
            False,
            "no_domain_a_health",
        )
    health_value = np.any(
        batch.values[:, health_positions] & batch.observed[:, health_positions],
        axis=1,
    )
    return _binary_fisher_diagnostic(
        "trace_mask_vs_domain_a_health",
        batch.observed[selected, trace_position],
        health_value[selected],
        alpha,
    )


def lag_one_diagnostic(
    values: np.ndarray,
    alpha: float,
) -> DiagnosticResult:
    vector = np.asarray(values, dtype=float)
    if len(vector) < 4 or float(np.var(vector)) == 0.0:
        return DiagnosticResult(
            "endpoint_lag1_dependence",
            None,
            None,
            alpha,
            len(vector),
            False,
            "insufficient_variation",
        )
    correlation = float(np.corrcoef(vector[:-1], vector[1:])[0, 1])
    statistic = len(vector) * (len(vector) + 2.0) * correlation**2 / (len(vector) - 1.0)
    p_value = float(chi2.sf(statistic, 1))
    return DiagnosticResult(
        "endpoint_lag1_dependence",
        correlation,
        p_value,
        alpha,
        len(vector),
        p_value < alpha,
        "complete",
    )


def cross_domain_diagnostic(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    alpha: float,
) -> DiagnosticResult:
    positions = {item.id: index for index, item in enumerate(model.observables)}
    first = positions["current_success"]
    second = positions["anchor_success"]
    selected = batch.observed[:, first] & batch.observed[:, second]
    if not np.any(selected):
        return DiagnosticResult(
            "cross_domain_or_dependence",
            None,
            None,
            alpha,
            0,
            False,
            "no_joint_trace",
        )
    return _binary_fisher_diagnostic(
        "cross_domain_or_dependence",
        batch.values[selected, first],
        batch.values[selected, second],
        alpha,
    )


def readiness_implication_diagnostic(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
) -> DiagnosticResult:
    positions = {item.id: index for index, item in enumerate(model.observables)}
    selected_positions = (
        positions["replica_a_health"],
        positions["replica_b_health"],
        positions["current_success"],
    )
    selected = np.all(batch.observed[:, selected_positions], axis=1)
    expected = (
        batch.values[:, selected_positions[0]]
        | batch.values[:, selected_positions[1]]
    )
    violation = selected & (expected != batch.values[:, selected_positions[2]])
    count = int(np.count_nonzero(violation))
    trials = int(np.count_nonzero(selected))
    return DiagnosticResult(
        "health_or_trace_logical_violation",
        float(count),
        0.0 if count else 1.0,
        0.0,
        trials,
        count > 0,
        "complete" if trials else "no_joint_records",
    )


def support_diagnostic(
    branch_counts: tuple[int, int],
    minimum: int,
) -> DiagnosticResult:
    smallest = min(branch_counts)
    return DiagnosticResult(
        "minimum_branch_support",
        float(smallest),
        None,
        float(minimum),
        sum(branch_counts),
        smallest < minimum,
        "complete",
    )


def _weighted_mask_objective(
    logits: np.ndarray,
    table: ObservedPatternTable,
    selection_weights: np.ndarray,
) -> tuple[float, np.ndarray]:
    probabilities = expit(logits)
    states = table.latent_states.astype(float)
    log_weights = states @ np.log(probabilities) + (1.0 - states) @ np.log1p(-probabilities)
    state_weights = np.exp(log_weights)
    weighted_compatibility = table.compatible_states.astype(float) * selection_weights
    pattern_probabilities = weighted_compatibility @ state_weights
    if np.any(pattern_probabilities <= 0.0) or not np.all(np.isfinite(pattern_probabilities)):
        return float("inf"), np.full_like(logits, np.nan)
    counts = table.counts.astype(float)
    objective = -float(counts @ np.log(pattern_probabilities))
    scores = states - probabilities[None, :]
    derivatives = weighted_compatibility @ (state_weights[:, None] * scores)
    gradient = -np.sum(
        (counts / pattern_probabilities)[:, None] * derivatives,
        axis=0,
    )
    return objective, gradient


def fit_selection_aware_likelihood(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    retention_when_domain_up: float,
    retention_when_domain_down: float,
    initial_probabilities: np.ndarray | None = None,
    epsilon: float = 1e-6,
) -> ExactLikelihoodFit:
    table = compress_observed_patterns(model, batch)
    trace_positions = [
        index for index, item in enumerate(model.observables) if item.kind == "trace"
    ]
    kept = np.any(table.masks[:, trace_positions], axis=1)
    domain = table.latent_states[:, model.factor_ids.index("domain_a")]
    retention = np.where(
        domain,
        retention_when_domain_up,
        retention_when_domain_down,
    )
    selection_weights = np.where(kept[:, None], retention[None, :], 1.0 - retention[None, :])
    lower = logit(epsilon)
    upper = logit(1.0 - epsilon)
    starts: list[np.ndarray] = []
    if initial_probabilities is not None:
        starts.append(np.asarray(initial_probabilities, dtype=float))
    starts.extend(np.full(len(model.factors), value) for value in (0.5, 0.8, 0.95))
    unique: list[np.ndarray] = []
    for start in starts:
        if start.shape != (len(model.factors),):
            raise ValueError("initial probabilities do not match the model")
        if not any(np.allclose(start, existing) for existing in unique):
            unique.append(start)
    results: list[OptimizeResult] = []
    for start in unique:
        result = minimize(
            _weighted_mask_objective,
            logit(np.clip(start, epsilon, 1.0 - epsilon)),
            args=(table, selection_weights),
            method="L-BFGS-B",
            jac=True,
            bounds=[(lower, upper)] * len(model.factors),
            options={"maxiter": 1_000, "ftol": 1e-12, "gtol": 1e-8, "maxls": 50},
        )
        results.append(result)
    finite = [result for result in results if np.isfinite(float(result.fun))]
    if not finite:
        return ExactLikelihoodFit(
            "optimization_failed",
            False,
            None,
            None,
            max((int(item.nit) for item in results), default=0),
            None,
            0,
            0,
            len(results),
            None,
            None,
            "no finite selection-aware optimum",
        )
    best = min(finite, key=lambda item: float(item.fun))
    probabilities = expit(np.asarray(best.x, dtype=float))
    _, gradient = _weighted_mask_objective(np.asarray(best.x, dtype=float), table, selection_weights)
    successful = [item for item in finite if bool(item.success)]
    near = [item for item in finite if float(item.fun) <= float(best.fun) + 1e-7]
    spread = (
        max(
            float(np.max(np.abs(expit(np.asarray(item.x)) - probabilities)))
            for item in near
        )
        if near
        else None
    )
    boundary_count = int(
        np.count_nonzero(
            (probabilities <= epsilon * 10.0)
            | (probabilities >= 1.0 - epsilon * 10.0)
        )
    )
    converged = bool(best.success) or float(np.linalg.norm(gradient, ord=np.inf)) < 1e-5
    status = "complete" if converged else "optimization_warning"
    if converged and boundary_count:
        status = "boundary_solution"
    return ExactLikelihoodFit(
        status=status,
        converged=converged,
        probabilities=probabilities if converged else None,
        negative_log_likelihood=float(best.fun),
        iterations=int(best.nit),
        gradient_infinity_norm=float(np.linalg.norm(gradient, ord=np.inf)),
        boundary_parameter_count=boundary_count,
        successful_starts=len(successful),
        attempted_starts=len(results),
        near_optimal_parameter_spread=spread,
        objective_spread=(
            max(float(item.fun) for item in finite) - min(float(item.fun) for item in finite)
        ),
        message=str(best.message),
    )


def matched_two_domain_model(
    base: BooleanFactorModel,
    domain_probability: float,
) -> BooleanFactorModel:
    original = {factor.id: factor.probability for factor in base.factors}
    marginal = {
        "replica_a": original["domain_a"] * original["replica_a"],
        "replica_b": original["domain_a"] * original["replica_b"],
        "anchor_a": original["domain_b"] * original["anchor_a"],
        "anchor_b": original["domain_b"] * original["anchor_b"],
    }
    factors = (
        Factor("domain_a", domain_probability, "domain"),
        Factor("replica_a", marginal["replica_a"] / domain_probability, "instance_residual"),
        Factor("replica_b", marginal["replica_b"] / domain_probability, "instance_residual"),
        Factor("domain_b", domain_probability, "domain"),
        Factor("anchor_a", marginal["anchor_a"] / domain_probability, "instance_residual"),
        Factor("anchor_b", marginal["anchor_b"] / domain_probability, "instance_residual"),
    )
    return BooleanFactorModel(base.id + "_matched_domains", factors, base.observables, base.targets)


def shared_domain_model(two_domain: BooleanFactorModel) -> BooleanFactorModel:
    source = {factor.id: factor for factor in two_domain.factors}
    factors = (
        Factor("shared_domain", source["domain_a"].probability, "domain"),
        source["replica_a"],
        source["replica_b"],
        source["anchor_a"],
        source["anchor_b"],
    )
    observables = (
        BooleanObservable("replica_a_health", (("shared_domain", "replica_a"),), "health"),
        BooleanObservable("replica_b_health", (("shared_domain", "replica_b"),), "health"),
        BooleanObservable("anchor_a_health", (("shared_domain", "anchor_a"),), "health"),
        BooleanObservable("anchor_b_health", (("shared_domain", "anchor_b"),), "health"),
        BooleanObservable(
            "current_success",
            (("shared_domain", "replica_a"), ("shared_domain", "replica_b")),
            "trace",
        ),
        BooleanObservable(
            "anchor_success",
            (("shared_domain", "anchor_a"), ("shared_domain", "anchor_b")),
            "trace",
        ),
    )
    targets = (
        BooleanTarget(
            TARGET_CURRENT,
            (("shared_domain", "replica_a"), ("shared_domain", "replica_b")),
        ),
        BooleanTarget(
            TARGET_SPLIT,
            (("shared_domain", "replica_a"), ("shared_domain", "replica_b")),
        ),
    )
    return BooleanFactorModel(two_domain.id + "_hidden_merged", factors, observables, targets)


def shared_domain_quantity_values(
    model: BooleanFactorModel,
    probabilities: dict[str, float] | None = None,
) -> dict[str, float]:
    values = (
        {factor.id: factor.probability for factor in model.factors}
        if probabilities is None
        else probabilities
    )
    gamma = values["shared_domain"]
    first = values["replica_a"]
    second = values["replica_b"]
    current = gamma * (1.0 - (1.0 - first) * (1.0 - second))
    split = current
    add = gamma * (1.0 - (1.0 - first) * (1.0 - second) ** 2)
    return {
        TARGET_CURRENT: current,
        TARGET_SPLIT: split,
        TARGET_ADD: add,
        DELTA_SPLIT: 0.0,
        DELTA_ADD: add - current,
        CHOICE_DIFFERENCE: split - add,
    }


def readiness_batch(
    model: BooleanFactorModel,
    episode_count: int,
    recovery_probability: float,
    lag_episodes: int,
    state_rng: np.random.Generator,
    residual_rng: np.random.Generator,
    burn_in: int = 500,
) -> EpisodeBatch:
    if lag_episodes < 0 or not 0.0 < recovery_probability <= 1.0:
        raise ValueError("readiness settings are invalid")
    probabilities = model.factor_probabilities
    domain_position = model.factor_ids.index("domain_a")
    stationary = probabilities[domain_position]
    failure_probability = (1.0 - stationary) * recovery_probability / stationary
    if failure_probability > 1.0:
        raise ValueError("recovery probability is incompatible with stationarity")
    total = burn_in + episode_count
    domain = np.empty(total, dtype=bool)
    domain[0] = state_rng.random() < stationary
    for index in range(1, total):
        if domain[index - 1]:
            domain[index] = state_rng.random() >= failure_probability
        else:
            domain[index] = state_rng.random() < recovery_probability
    ready = np.empty(total, dtype=bool)
    remaining = 0
    for index in range(total):
        if not domain[index]:
            ready[index] = False
            remaining = 0
        else:
            recovered = index > 0 and not domain[index - 1]
            if recovered:
                remaining = lag_episodes
            ready[index] = remaining == 0
            if remaining:
                remaining -= 1
    latent = residual_rng.random((total, len(model.factors))) < probabilities
    latent[:, domain_position] = domain
    latent = latent[burn_in:]
    ready = ready[burn_in:]
    values = observable_states(model, latent)
    positions = {item.id: index for index, item in enumerate(model.observables)}
    factor_positions = {factor_id: index for index, factor_id in enumerate(model.factor_ids)}
    values[:, positions["current_success"]] = ready & (
        latent[:, factor_positions["replica_a"]]
        | latent[:, factor_positions["replica_b"]]
    )
    return EpisodeBatch(values=values, observed=np.ones_like(values, dtype=bool))


def readiness_quantity_values(
    model: BooleanFactorModel,
    recovery_probability: float,
    lag_episodes: int,
) -> dict[str, float]:
    values = {factor.id: factor.probability for factor in model.factors}
    gamma = values["domain_a"]
    failure_probability = (1.0 - gamma) * recovery_probability / gamma
    stay_up = 1.0 - failure_probability
    effective = gamma * stay_up**lag_episodes
    first = values["replica_a"]
    second = values["replica_b"]
    gamma_b = values["domain_b"]
    current = effective * (1.0 - (1.0 - first) * (1.0 - second))
    split = 1.0 - (1.0 - effective * first) * (1.0 - gamma_b * second)
    add = effective * (1.0 - (1.0 - first) * (1.0 - second) ** 2)
    return {
        TARGET_CURRENT: current,
        TARGET_SPLIT: split,
        TARGET_ADD: add,
        DELTA_SPLIT: split - current,
        DELTA_ADD: add - current,
        CHOICE_DIFFERENCE: split - add,
    }


def circular_block_indices(
    sample_size: int,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    if sample_size <= 0 or block_length <= 0:
        raise ValueError("sample and block lengths must be positive")
    starts = rng.integers(0, sample_size, size=ceil(sample_size / block_length))
    offsets = np.arange(block_length)
    return ((starts[:, None] + offsets[None, :]) % sample_size).ravel()[:sample_size]


def block_bootstrap_ranges(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    point_probabilities: np.ndarray | None,
    quantities: Iterable[str],
    confidence_level: float,
    replicates: int,
    block_length: int,
    rng: np.random.Generator,
    fit_function: Callable[[BooleanFactorModel, ObservedPatternTable], ExactLikelihoodFit],
    value_function: Callable[[BooleanFactorModel, dict[str, float] | None], dict[str, float]] = quantity_values,
) -> dict[str, IntervalEstimate]:
    selected = tuple(quantities)
    unavailable = {
        quantity: IntervalEstimate(None, None, None, "block_bootstrap_unavailable")
        for quantity in selected
    }
    if point_probabilities is None or replicates <= 0:
        return unavailable
    point_map = dict(zip(model.factor_ids, point_probabilities, strict=True))
    point = value_function(model, point_map)
    draws: dict[str, list[float]] = {quantity: [] for quantity in selected}
    for _ in range(replicates):
        indices = circular_block_indices(len(batch.values), block_length, rng)
        resampled = EpisodeBatch(batch.values[indices], batch.observed[indices])
        try:
            table = compress_observed_patterns(model, resampled)
        except ValueError:
            continue
        fit = fit_function(model, table)
        if not fit.converged or fit.probabilities is None:
            continue
        values = value_function(
            model,
            dict(zip(model.factor_ids, fit.probabilities, strict=True)),
        )
        for quantity in selected:
            draws[quantity].append(values[quantity])
    minimum_successes = max(5, int(ceil(0.8 * replicates)))
    alpha = (1.0 - confidence_level) / len(selected)
    result: dict[str, IntervalEstimate] = {}
    for quantity in selected:
        values = draws[quantity]
        if len(values) < minimum_successes:
            result[quantity] = unavailable[quantity]
            continue
        lower, upper = np.quantile(values, (alpha / 2.0, 1.0 - alpha / 2.0))
        result[quantity] = IntervalEstimate(
            float(lower),
            float(upper),
            point[quantity],
            "moving_block_bootstrap_bonferroni",
        )
    return result


def block_bootstrap_binary_interval(
    values: np.ndarray,
    confidence_level: float,
    replicates: int,
    block_length: int,
    rng: np.random.Generator,
) -> IntervalEstimate:
    vector = np.asarray(values, dtype=bool)
    draws = np.empty(replicates, dtype=float)
    for index in range(replicates):
        selected = circular_block_indices(len(vector), block_length, rng)
        draws[index] = float(np.mean(vector[selected]))
    alpha = 1.0 - confidence_level
    lower, upper = np.quantile(draws, (alpha / 2.0, 1.0 - alpha / 2.0))
    return IntervalEstimate(
        float(lower),
        float(upper),
        float(np.mean(vector)),
        "moving_block_bootstrap",
    )


def direct_binary_interval(
    values: np.ndarray,
    confidence_level: float,
) -> IntervalEstimate:
    vector = np.asarray(values, dtype=bool)
    successes = int(np.count_nonzero(vector))
    lower, upper = clopper_pearson_interval(successes, len(vector), confidence_level)
    return IntervalEstimate(lower, upper, successes / len(vector), "clopper_pearson")


def branch_target_interval(
    branch: np.ndarray,
    success: np.ndarray,
    target_branch_b_share: float,
    confidence_level: float,
    minimum_observations: int,
) -> tuple[IntervalEstimate, tuple[int, int]]:
    branch = np.asarray(branch, dtype=bool)
    success = np.asarray(success, dtype=bool)
    counts = (int(np.count_nonzero(~branch)), int(np.count_nonzero(branch)))
    bounds: list[tuple[float, float]] = []
    estimates: list[float | None] = []
    for selected, count in ((~branch, counts[0]), (branch, counts[1])):
        if count == 0:
            bounds.append((0.0, 1.0))
            estimates.append(None)
        else:
            hits = int(np.count_nonzero(success[selected]))
            bounds.append(
                clopper_pearson_interval(
                    hits,
                    count,
                    confidence_level,
                    comparisons=2,
                )
            )
            estimates.append(hits / count)
    share = target_branch_b_share
    lower = (1.0 - share) * bounds[0][0] + share * bounds[1][0]
    upper = (1.0 - share) * bounds[0][1] + share * bounds[1][1]
    point = (
        (1.0 - share) * float(estimates[0]) + share * float(estimates[1])
        if min(counts) >= minimum_observations
        and estimates[0] is not None
        and estimates[1] is not None
        else None
    )
    return IntervalEstimate(lower, upper, point, "branch_simultaneous_exact"), counts
