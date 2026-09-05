from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product

import numpy as np

from .boolean_model import BooleanFactorModel
from .likelihood import enumerate_latent_states, observable_states
from .observation import ObservationPolicy
from .transfer import (
    TARGET_ADD,
    TARGET_CURRENT,
    TARGET_IDS,
    TARGET_SPLIT,
    transfer_probabilities,
)


PROVED_IDENTIFIABLE = "proved_identifiable"
PROVED_AMBIGUOUS = "proved_ambiguous"
UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class TargetIdentification:
    target: str
    status: str
    certificate: str


@dataclass(frozen=True)
class AmbiguityWitness:
    target: str
    first_probabilities: dict[str, float]
    second_probabilities: dict[str, float]
    first_target: float
    second_target: float
    max_observable_difference: float


def _kind_available(policy: ObservationPolicy, kind: str) -> bool:
    return policy.includes_kind(kind) and policy.sampling_by_kind.get(kind, 1.0) > 0.0


def diagnose_transfer_targets(
    policy: ObservationPolicy,
) -> dict[str, TargetIdentification]:
    """Return analytic certificates for the fixed two-domain transfer design.

    A domain and two residuals are recovered either from two health marginals and
    their joint moment, or from the same marginals and the corresponding OR trace:
    gamma = m1*m2/joint = m1*m2/(m1+m2-or).
    """

    health = _kind_available(policy, "health")
    trace = _kind_available(policy, "trace")
    joint_health = health and policy.supports_joint(("health", "health"))
    domain_identified = health and (joint_health or trace)
    if joint_health:
        domain_certificate = "two_health_marginals_and_joint_health_moment"
    elif health and trace:
        domain_certificate = "two_health_marginals_and_or_trace"
    else:
        domain_certificate = ""

    result: dict[str, TargetIdentification] = {}
    if trace:
        result[TARGET_CURRENT] = TargetIdentification(
            TARGET_CURRENT,
            PROVED_IDENTIFIABLE,
            "direct_current_or_trace_probability",
        )
    elif domain_identified:
        result[TARGET_CURRENT] = TargetIdentification(
            TARGET_CURRENT,
            PROVED_IDENTIFIABLE,
            domain_certificate,
        )
    elif health:
        result[TARGET_CURRENT] = TargetIdentification(
            TARGET_CURRENT,
            PROVED_AMBIGUOUS,
            "health_marginals_admit_distinct_common_domain_probabilities",
        )
    else:
        result[TARGET_CURRENT] = TargetIdentification(
            TARGET_CURRENT,
            UNRESOLVED,
            "configured_signals_do_not_support_a_certificate",
        )

    if domain_identified:
        result[TARGET_ADD] = TargetIdentification(
            TARGET_ADD,
            PROVED_IDENTIFIABLE,
            domain_certificate,
        )
        result[TARGET_SPLIT] = TargetIdentification(
            TARGET_SPLIT,
            PROVED_IDENTIFIABLE,
            f"both_domains_identified_by_{domain_certificate}",
        )
    elif trace and not health:
        result[TARGET_ADD] = TargetIdentification(
            TARGET_ADD,
            PROVED_AMBIGUOUS,
            "or_trace_preserves_multiple_domain_residual_decompositions",
        )
        result[TARGET_SPLIT] = TargetIdentification(
            TARGET_SPLIT,
            PROVED_AMBIGUOUS,
            "two_or_traces_preserve_multiple_cross_domain_decompositions",
        )
    elif health:
        result[TARGET_ADD] = TargetIdentification(
            TARGET_ADD,
            PROVED_AMBIGUOUS,
            "health_marginals_admit_distinct_common_domain_probabilities",
        )
        result[TARGET_SPLIT] = TargetIdentification(
            TARGET_SPLIT,
            PROVED_AMBIGUOUS,
            "health_marginals_admit_distinct_cross_domain_decompositions",
        )
    else:
        result[TARGET_ADD] = TargetIdentification(
            TARGET_ADD,
            UNRESOLVED,
            "configured_signals_do_not_support_a_certificate",
        )
        result[TARGET_SPLIT] = TargetIdentification(
            TARGET_SPLIT,
            UNRESOLVED,
            "configured_signals_do_not_support_a_certificate",
        )
    if set(result) != set(TARGET_IDS):
        raise AssertionError("transfer diagnostic did not classify every target")
    return result


def _different_interior(lower: float, original: float) -> float:
    first = (lower + 1.0) / 2.0
    if abs(first - original) > 1e-3:
        return first
    second = (lower + first) / 2.0
    if abs(second - original) > 1e-3:
        return second
    return (first + 1.0) / 2.0


def _alternative_parameters(
    model: BooleanFactorModel,
    policy: ObservationPolicy,
) -> dict[str, float] | None:
    truth = {factor.id: factor.probability for factor in model.factors}
    health = _kind_available(policy, "health")
    trace = _kind_available(policy, "trace")
    if health and (policy.supports_joint(("health", "health")) or trace):
        return None
    alternative = truth.copy()
    pairs = (
        ("domain_a", "replica_a", "replica_b"),
        ("domain_b", "anchor_a", "anchor_b"),
    )
    for domain, first, second in pairs:
        gamma = truth[domain]
        first_marginal = gamma * truth[first]
        second_marginal = gamma * truth[second]
        if health:
            new_gamma = _different_interior(
                max(first_marginal, second_marginal),
                gamma,
            )
            alternative[domain] = new_gamma
            alternative[first] = first_marginal / new_gamma
            alternative[second] = second_marginal / new_gamma
        elif trace:
            union = gamma * (
                1.0 - (1.0 - truth[first]) * (1.0 - truth[second])
            )
            new_gamma = _different_interior(union, gamma)
            residual = 1.0 - np.sqrt(1.0 - union / new_gamma)
            alternative[domain] = new_gamma
            alternative[first] = float(residual)
            alternative[second] = float(residual)
        else:
            return None
    return alternative


def _state_weights(states: np.ndarray, probabilities: dict[str, float], model: BooleanFactorModel) -> np.ndarray:
    vector = np.asarray([probabilities[name] for name in model.factor_ids], dtype=float)
    numeric = states.astype(float)
    return np.prod(np.where(numeric > 0.5, vector, 1.0 - vector), axis=1)


def max_supported_distribution_difference(
    model: BooleanFactorModel,
    policy: ObservationPolicy,
    first: dict[str, float],
    second: dict[str, float],
) -> float:
    states = enumerate_latent_states(len(model.factors))
    values = observable_states(model, states)
    first_weights = _state_weights(states, first, model)
    second_weights = _state_weights(states, second, model)
    positions = tuple(
        index
        for index, observable in enumerate(model.observables)
        if _kind_available(policy, observable.kind)
    )
    maximum = 0.0
    for order in range(1, len(positions) + 1):
        for subset in combinations(positions, order):
            kinds = tuple(model.observables[index].kind for index in subset)
            if not policy.supports_joint(kinds):
                continue
            for outcome in product((False, True), repeat=order):
                compatible = np.all(values[:, subset] == np.asarray(outcome), axis=1)
                difference = abs(
                    float(np.sum(first_weights[compatible]))
                    - float(np.sum(second_weights[compatible]))
                )
                maximum = max(maximum, difference)
    return maximum


def ambiguity_witnesses(
    model: BooleanFactorModel,
    policy: ObservationPolicy,
) -> tuple[AmbiguityWitness, ...]:
    identification = diagnose_transfer_targets(policy)
    ambiguous = [
        target
        for target in TARGET_IDS
        if identification[target].status == PROVED_AMBIGUOUS
    ]
    if not ambiguous:
        return ()
    truth = {factor.id: factor.probability for factor in model.factors}
    alternative = _alternative_parameters(model, policy)
    if alternative is None:
        raise AssertionError("ambiguous transfer case lacks a constructed witness")
    first_targets = transfer_probabilities(model, truth)
    second_targets = transfer_probabilities(model, alternative)
    observable_difference = max_supported_distribution_difference(
        model,
        policy,
        truth,
        alternative,
    )
    return tuple(
        AmbiguityWitness(
            target=target,
            first_probabilities=truth,
            second_probabilities=alternative,
            first_target=first_targets[target],
            second_target=second_targets[target],
            max_observable_difference=observable_difference,
        )
        for target in ambiguous
    )
