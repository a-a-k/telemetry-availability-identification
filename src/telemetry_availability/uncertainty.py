from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Callable

import numpy as np
from scipy.special import expit, logit
from scipy.stats import beta, norm

from .boolean_model import BooleanFactorModel
from .likelihood import (
    ExactLikelihoodFit,
    ObservedPatternTable,
    negative_log_likelihood_and_gradient,
)
from .observation import EpisodeBatch, ObservationPolicy
from .transfer import (
    TARGET_ADD,
    TARGET_CURRENT,
    TARGET_SPLIT,
    transfer_probabilities,
)
from .transfer_identifiability import (
    PROVED_IDENTIFIABLE,
    diagnose_transfer_targets,
)


DELTA_SPLIT = "change_split_minus_current"
DELTA_ADD = "change_add_minus_current"
CHOICE_DIFFERENCE = "choice_split_minus_add"
QUANTITIES = (
    TARGET_CURRENT,
    TARGET_SPLIT,
    TARGET_ADD,
    DELTA_SPLIT,
    DELTA_ADD,
    CHOICE_DIFFERENCE,
)
AVAILABILITY_QUANTITIES = {TARGET_CURRENT, TARGET_SPLIT, TARGET_ADD}


@dataclass(frozen=True)
class EvidenceInterval:
    domain: str
    statistic: str
    observable_ids: tuple[str, ...]
    successes: int
    trials: int
    estimate: float
    lower: float
    upper: float
    truth: float

    @property
    def covers_truth(self) -> bool:
        return self.lower <= self.truth <= self.upper


@dataclass(frozen=True)
class DomainEvidence:
    domain: str
    first: EvidenceInterval | None
    second: EvidenceInterval | None
    joint: EvidenceInterval | None
    unions: tuple[EvidenceInterval, ...]


@dataclass(frozen=True)
class ParameterBox:
    lower: tuple[float, float, float]
    upper: tuple[float, float, float]


@dataclass(frozen=True)
class DomainBoxResult:
    boxes: tuple[ParameterBox, ...]
    visited_nodes: int
    truncated: bool
    status: str


@dataclass(frozen=True)
class IntervalEstimate:
    lower: float | None
    upper: float | None
    point: float | None
    status: str

    @property
    def width(self) -> float | None:
        if self.lower is None or self.upper is None:
            return None
        return self.upper - self.lower


@dataclass(frozen=True)
class SimultaneousRangeResult:
    intervals: dict[str, IntervalEstimate]
    domain_a: DomainBoxResult
    domain_b: DomainBoxResult
    identification_status: str


def clopper_pearson_interval(
    successes: int,
    trials: int,
    confidence_level: float,
    comparisons: int = 1,
) -> tuple[float, float]:
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError("binomial counts are invalid")
    if not 0.0 < confidence_level < 1.0 or comparisons <= 0:
        raise ValueError("confidence level and comparison count are invalid")
    alpha = (1.0 - confidence_level) / comparisons
    lower = (
        0.0
        if successes == 0
        else float(beta.ppf(alpha / 2.0, successes, trials - successes + 1))
    )
    upper = (
        1.0
        if successes == trials
        else float(beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes))
    )
    return lower, upper


def _factor_truths(model: BooleanFactorModel) -> dict[str, float]:
    return {factor.id: factor.probability for factor in model.factors}


def extract_simultaneous_evidence(
    model: BooleanFactorModel,
    batch: EpisodeBatch,
    confidence_level: float,
) -> tuple[DomainEvidence, DomainEvidence, tuple[EvidenceInterval, ...]]:
    positions = {observable.id: index for index, observable in enumerate(model.observables)}
    probabilities = _factor_truths(model)
    raw_specs: list[
        tuple[str, str, tuple[str, ...], np.ndarray, np.ndarray, float]
    ] = []
    pair_specs = (
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
    for domain, first_factor, second_factor, first_id, second_id, union_id in pair_specs:
        gamma = probabilities[domain]
        first_truth = gamma * probabilities[first_factor]
        second_truth = gamma * probabilities[second_factor]
        joint_truth = gamma * probabilities[first_factor] * probabilities[second_factor]
        union_truth = first_truth + second_truth - joint_truth
        first_position = positions[first_id]
        second_position = positions[second_id]
        union_position = positions[union_id]
        raw_specs.extend(
            (
                (
                    domain,
                    "first_marginal",
                    (first_id,),
                    batch.observed[:, first_position],
                    batch.values[:, first_position],
                    first_truth,
                ),
                (
                    domain,
                    "second_marginal",
                    (second_id,),
                    batch.observed[:, second_position],
                    batch.values[:, second_position],
                    second_truth,
                ),
                (
                    domain,
                    "joint_health",
                    (first_id, second_id),
                    batch.observed[:, first_position]
                    & batch.observed[:, second_position],
                    batch.values[:, first_position]
                    & batch.values[:, second_position],
                    joint_truth,
                ),
                (
                    domain,
                    "health_union",
                    (first_id, second_id),
                    batch.observed[:, first_position]
                    & batch.observed[:, second_position],
                    batch.values[:, first_position]
                    | batch.values[:, second_position],
                    union_truth,
                ),
                (
                    domain,
                    "or_trace",
                    (union_id,),
                    batch.observed[:, union_position],
                    batch.values[:, union_position],
                    union_truth,
                ),
            )
        )
    available: list[
        tuple[str, str, tuple[str, ...], np.ndarray, np.ndarray, float]
    ] = []
    for spec in raw_specs:
        if int(np.count_nonzero(spec[3])) == 0:
            continue
        if spec[1] in {"health_union", "or_trace"} and any(
            existing[0] == spec[0]
            and existing[1] in {"health_union", "or_trace"}
            and np.array_equal(existing[3], spec[3])
            and np.array_equal(existing[4] & existing[3], spec[4] & spec[3])
            for existing in available
        ):
            continue
        available.append(spec)
    comparisons = len(available)
    intervals: list[EvidenceInterval] = []
    for domain, statistic, observable_ids, observed, event, truth in available:
        trials = int(np.count_nonzero(observed))
        successes = int(np.count_nonzero(event & observed))
        lower, upper = clopper_pearson_interval(
            successes,
            trials,
            confidence_level,
            comparisons,
        )
        intervals.append(
            EvidenceInterval(
                domain=domain,
                statistic=statistic,
                observable_ids=observable_ids,
                successes=successes,
                trials=trials,
                estimate=successes / trials,
                lower=lower,
                upper=upper,
                truth=truth,
            )
        )
    by_domain: list[DomainEvidence] = []
    for domain in ("domain_a", "domain_b"):
        lookup = {
            interval.statistic: interval
            for interval in intervals
            if interval.domain == domain
        }
        by_domain.append(
            DomainEvidence(
                domain=domain,
                first=lookup.get("first_marginal"),
                second=lookup.get("second_marginal"),
                joint=lookup.get("joint_health"),
                unions=tuple(
                    interval
                    for interval in intervals
                    if interval.domain == domain
                    and interval.statistic in {"health_union", "or_trace"}
                ),
            )
        )
    return by_domain[0], by_domain[1], tuple(intervals)


def _intersects(lower: float, upper: float, interval: EvidenceInterval | None) -> bool:
    return interval is None or not (upper < interval.lower or lower > interval.upper)


def _union_bounds(evidence: DomainEvidence) -> tuple[float, float] | None:
    if not evidence.unions:
        return None
    return (
        max(interval.lower for interval in evidence.unions),
        min(interval.upper for interval in evidence.unions),
    )


def _contract_box(
    box: ParameterBox,
    evidence: DomainEvidence,
) -> ParameterBox | None:
    lower = list(box.lower)
    upper = list(box.upper)
    union_bounds = _union_bounds(evidence)
    for _ in range(3):
        if evidence.first is not None:
            lower[0] = max(lower[0], evidence.first.lower)
            upper[0] = min(upper[0], evidence.first.upper)
        if evidence.second is not None:
            lower[1] = max(lower[1], evidence.second.lower)
            upper[1] = min(upper[1], evidence.second.upper)
        if evidence.joint is not None:
            lower[0] = max(lower[0], evidence.joint.lower)
            lower[1] = max(lower[1], evidence.joint.lower)
        if union_bounds is not None:
            upper[0] = min(upper[0], union_bounds[1])
            upper[1] = min(upper[1], union_bounds[1])
            lower[2] = max(lower[2], union_bounds[0])

        upper[0] = min(upper[0], upper[2])
        upper[1] = min(upper[1], upper[2])
        lower[2] = max(lower[2], lower[0], lower[1])
        if any(lo > hi for lo, hi in zip(lower, upper, strict=True)):
            return None

        if evidence.joint is not None:
            if evidence.joint.upper > 0.0:
                lower[2] = max(
                    lower[2],
                    lower[0] * lower[1] / evidence.joint.upper,
                )
            if evidence.joint.lower > 0.0:
                upper[2] = min(
                    upper[2],
                    upper[0] * upper[1] / evidence.joint.lower,
                )
        if union_bounds is not None:
            joint_lower = max(
                0.0,
                lower[0] + lower[1] - union_bounds[1],
            )
            joint_upper = min(
                upper[0],
                upper[1],
                upper[0] + upper[1] - union_bounds[0],
            )
            if joint_upper > 0.0:
                lower[2] = max(lower[2], lower[0] * lower[1] / joint_upper)
            if joint_lower > 0.0:
                upper[2] = min(upper[2], upper[0] * upper[1] / joint_lower)
        lower[2] = min(1.0, lower[2])
        upper[2] = min(1.0, upper[2])
        if any(lo > hi for lo, hi in zip(lower, upper, strict=True)):
            return None
    return ParameterBox(tuple(lower), tuple(upper))


def _box_possible(box: ParameterBox, evidence: DomainEvidence) -> bool:
    u_lower, v_lower, gamma_lower = box.lower
    u_upper, v_upper, gamma_upper = box.upper
    if gamma_upper < max(u_lower, v_lower) or gamma_lower <= 0.0:
        return False
    joint_lower = u_lower * v_lower / gamma_upper
    joint_upper = min(u_upper, v_upper, u_upper * v_upper / gamma_lower)
    if not _intersects(joint_lower, joint_upper, evidence.joint):
        return False
    union_lower = max(0.0, u_lower + v_lower - joint_upper)
    union_upper = min(1.0, u_upper + v_upper - joint_lower)
    return all(
        _intersects(union_lower, union_upper, interval)
        for interval in evidence.unions
    )


def branch_domain_boxes(
    evidence: DomainEvidence,
    tolerance: float,
    max_nodes: int,
) -> DomainBoxResult:
    epsilon = 1e-9
    initial = _contract_box(
        ParameterBox((epsilon, epsilon, epsilon), (1.0, 1.0, 1.0)),
        evidence,
    )
    if initial is None or not _box_possible(initial, evidence):
        return DomainBoxResult((), 1, False, "empty")
    stack = [initial]
    leaves: list[ParameterBox] = []
    visited = 0
    while stack and visited < max_nodes:
        raw = stack.pop()
        box = _contract_box(raw, evidence)
        visited += 1
        if box is None or not _box_possible(box, evidence):
            continue
        widths = np.asarray(box.upper) - np.asarray(box.lower)
        dimension = int(np.argmax(widths))
        if widths[dimension] <= tolerance:
            leaves.append(box)
            continue
        midpoint = (box.lower[dimension] + box.upper[dimension]) / 2.0
        left_upper = list(box.upper)
        left_upper[dimension] = midpoint
        right_lower = list(box.lower)
        right_lower[dimension] = midpoint
        stack.append(ParameterBox(tuple(right_lower), box.upper))
        stack.append(ParameterBox(box.lower, tuple(left_upper)))

    truncated = bool(stack)
    if stack:
        for raw in stack:
            box = _contract_box(raw, evidence)
            if box is not None and _box_possible(box, evidence):
                leaves.append(box)
    status = "outer_boxes_truncated" if truncated else "outer_boxes_complete"
    if not leaves:
        status = "empty"
    return DomainBoxResult(tuple(leaves), visited, truncated, status)


def _current_value(u: float, v: float, gamma: float) -> float:
    return u + v - u * v / gamma


def _add_value(u: float, v: float, gamma: float) -> float:
    return gamma * (1.0 - (1.0 - u / gamma) * (1.0 - v / gamma) ** 2)


def _pad_interval(lower: float, upper: float, minimum: float, maximum: float) -> tuple[float, float]:
    padding = 1e-12
    return max(minimum, lower - padding), min(maximum, upper + padding)


def _range_over_boxes(
    boxes: tuple[ParameterBox, ...],
    function: Callable[[float, float, float], float],
) -> tuple[float, float]:
    lowers = [function(*box.lower) for box in boxes]
    uppers = [function(*box.upper) for box in boxes]
    return _pad_interval(min(lowers), max(uppers), 0.0, 1.0)


def _derived_intervals(
    availability: dict[str, tuple[float, float]],
    status: str,
    direct_derived: dict[str, tuple[float, float]] | None = None,
) -> dict[str, IntervalEstimate]:
    current = availability[TARGET_CURRENT]
    split = availability[TARGET_SPLIT]
    add = availability[TARGET_ADD]
    ranges: dict[str, tuple[float, float]] = {
        TARGET_CURRENT: current,
        TARGET_SPLIT: split,
        TARGET_ADD: add,
        DELTA_SPLIT: _pad_interval(split[0] - current[1], split[1] - current[0], -1.0, 1.0),
        DELTA_ADD: _pad_interval(add[0] - current[1], add[1] - current[0], -1.0, 1.0),
        CHOICE_DIFFERENCE: _pad_interval(split[0] - add[1], split[1] - add[0], -1.0, 1.0),
    }
    if direct_derived is not None:
        ranges.update(direct_derived)
    return {
        quantity: IntervalEstimate(lower, upper, None, status)
        for quantity, (lower, upper) in ranges.items()
    }


def _product_range(
    first: tuple[float, float],
    second: tuple[float, float],
) -> tuple[float, float]:
    values = (
        first[0] * second[0],
        first[0] * second[1],
        first[1] * second[0],
        first[1] * second[1],
    )
    return min(values), max(values)


def _direct_change_ranges(
    boxes: tuple[ParameterBox, ...],
    gamma_b_lower: float,
    gamma_b_upper: float,
) -> dict[str, tuple[float, float]]:
    split_lowers: list[float] = []
    split_uppers: list[float] = []
    add_lowers: list[float] = []
    add_uppers: list[float] = []
    choice_lowers: list[float] = []
    choice_uppers: list[float] = []
    for box in boxes:
        x_lower, y_lower, gamma_lower = box.lower
        x_upper, y_upper, gamma_upper = box.upper
        residual_lower = max(0.0, y_lower / gamma_upper)
        residual_upper = min(1.0, y_upper / gamma_lower)

        split_coefficient = (
            gamma_b_lower * (1.0 - x_lower) - (gamma_upper - x_lower),
            gamma_b_upper * (1.0 - x_upper) - (gamma_lower - x_upper),
        )
        split_range = _product_range(
            (residual_lower, residual_upper),
            split_coefficient,
        )
        split_lowers.append(split_range[0])
        split_uppers.append(split_range[1])

        residual_endpoint_values = (
            residual_lower * (1.0 - residual_lower),
            residual_upper * (1.0 - residual_upper),
        )
        residual_factor_lower = min(residual_endpoint_values)
        residual_factor_upper = (
            0.25
            if residual_lower <= 0.5 <= residual_upper
            else max(residual_endpoint_values)
        )
        domain_gap_lower = max(0.0, gamma_lower - x_upper)
        domain_gap_upper = max(0.0, gamma_upper - x_lower)
        add_lowers.append(residual_factor_lower * domain_gap_lower)
        add_uppers.append(residual_factor_upper * domain_gap_upper)

        def choice_value(
            residual: float,
            x_value: float,
            gamma_value: float,
            gamma_b_value: float,
        ) -> float:
            return residual * (
                (1.0 - x_value) * gamma_b_value
                - (gamma_value - x_value) * (2.0 - residual)
            )

        lower_x = x_lower
        lower_gamma = gamma_upper
        lower_gamma_b = gamma_b_lower
        lower_candidates = [
            choice_value(value, lower_x, lower_gamma, lower_gamma_b)
            for value in (residual_lower, residual_upper)
        ]
        gap = lower_gamma - lower_x
        linear = (1.0 - lower_x) * lower_gamma_b - 2.0 * gap
        if gap > 0.0:
            vertex = -linear / (2.0 * gap)
            if residual_lower <= vertex <= residual_upper:
                lower_candidates.append(
                    choice_value(vertex, lower_x, lower_gamma, lower_gamma_b)
                )
        choice_lowers.append(min(lower_candidates))

        upper_candidates = [
            choice_value(value, x_upper, gamma_lower, gamma_b_upper)
            for value in (residual_lower, residual_upper)
        ]
        choice_uppers.append(max(upper_candidates))

    return {
        DELTA_SPLIT: _pad_interval(
            min(split_lowers),
            max(split_uppers),
            -1.0,
            1.0,
        ),
        DELTA_ADD: _pad_interval(
            min(add_lowers),
            max(add_uppers),
            0.0,
            1.0,
        ),
        CHOICE_DIFFERENCE: _pad_interval(
            min(choice_lowers),
            max(choice_uppers),
            -1.0,
            1.0,
        ),
    }


def simultaneous_target_ranges(
    model: BooleanFactorModel,
    policy: ObservationPolicy,
    domain_a_evidence: DomainEvidence,
    domain_b_evidence: DomainEvidence,
    tolerance: float,
    max_nodes: int,
) -> SimultaneousRangeResult:
    identification = diagnose_transfer_targets(policy)
    transfer_status = identification[TARGET_SPLIT].status
    if transfer_status != PROVED_IDENTIFIABLE:
        union_bounds = _union_bounds(domain_a_evidence)
        current = (
            union_bounds
            if union_bounds is not None
            else (0.0, 1.0)
        )
        availability = {
            TARGET_CURRENT: current,
            TARGET_SPLIT: (0.0, 1.0),
            TARGET_ADD: (current[0], 1.0),
        }
        direct_derived = {
            DELTA_SPLIT: (-1.0, 1.0),
            DELTA_ADD: (0.0, 1.0 - current[0]),
            CHOICE_DIFFERENCE: (-1.0, 1.0),
        }
        empty_result = DomainBoxResult((), 0, False, "not_branched_ambiguous")
        return SimultaneousRangeResult(
            intervals=_derived_intervals(
                availability,
                "proved_ambiguous_outer",
                direct_derived,
            ),
            domain_a=empty_result,
            domain_b=empty_result,
            identification_status=transfer_status,
        )

    domain_a = branch_domain_boxes(domain_a_evidence, tolerance, max_nodes)
    domain_b = branch_domain_boxes(domain_b_evidence, tolerance, max_nodes)
    if not domain_a.boxes or not domain_b.boxes:
        availability = {
            TARGET_CURRENT: (0.0, 1.0),
            TARGET_SPLIT: (0.0, 1.0),
            TARGET_ADD: (0.0, 1.0),
        }
        return SimultaneousRangeResult(
            intervals=_derived_intervals(availability, "empty_set_conservative_fallback"),
            domain_a=domain_a,
            domain_b=domain_b,
            identification_status=transfer_status,
        )

    current = _range_over_boxes(domain_a.boxes, _current_value)
    union_bounds = _union_bounds(domain_a_evidence)
    if union_bounds is not None:
        current = (
            max(current[0], union_bounds[0]),
            min(current[1], union_bounds[1]),
        )
    add = _range_over_boxes(domain_a.boxes, _add_value)
    gamma_b_lower = min(box.lower[2] for box in domain_b.boxes)
    gamma_b_upper = max(box.upper[2] for box in domain_b.boxes)
    split_lowers: list[float] = []
    split_uppers: list[float] = []
    for box in domain_a.boxes:
        u_lower, v_lower, gamma_lower = box.lower
        u_upper, v_upper, gamma_upper = box.upper
        moved_lower = gamma_b_lower * v_lower / gamma_upper
        moved_upper = min(1.0, gamma_b_upper * v_upper / gamma_lower)
        split_lowers.append(1.0 - (1.0 - u_lower) * (1.0 - moved_lower))
        split_uppers.append(1.0 - (1.0 - u_upper) * (1.0 - moved_upper))
    split = _pad_interval(min(split_lowers), max(split_uppers), 0.0, 1.0)
    status = (
        "simultaneous_outer_truncated"
        if domain_a.truncated or domain_b.truncated
        else "simultaneous_outer"
    )
    direct_derived = _direct_change_ranges(
        domain_a.boxes,
        gamma_b_lower,
        gamma_b_upper,
    )
    return SimultaneousRangeResult(
        intervals=_derived_intervals(
            {
                TARGET_CURRENT: current,
                TARGET_SPLIT: split,
                TARGET_ADD: add,
            },
            status,
            direct_derived,
        ),
        domain_a=domain_a,
        domain_b=domain_b,
        identification_status=transfer_status,
    )


def quantity_values(
    model: BooleanFactorModel,
    probabilities: dict[str, float] | None = None,
) -> dict[str, float]:
    availability = transfer_probabilities(model, probabilities)
    current = availability[TARGET_CURRENT]
    split = availability[TARGET_SPLIT]
    add = availability[TARGET_ADD]
    return {
        **availability,
        DELTA_SPLIT: split - current,
        DELTA_ADD: add - current,
        CHOICE_DIFFERENCE: split - add,
    }


def _quantity_limits(quantity: str) -> tuple[float, float]:
    return (0.0, 1.0) if quantity in AVAILABILITY_QUANTITIES else (-1.0, 1.0)


def likelihood_wald_ranges(
    model: BooleanFactorModel,
    table: ObservedPatternTable,
    fit: ExactLikelihoodFit,
    confidence_level: float,
    simultaneous: bool,
) -> dict[str, IntervalEstimate]:
    unavailable = {
        quantity: IntervalEstimate(None, None, None, "wald_unavailable")
        for quantity in QUANTITIES
    }
    if not fit.converged or fit.probabilities is None:
        return unavailable
    logits = logit(np.clip(fit.probabilities, 1e-9, 1.0 - 1e-9))
    step = 1e-4
    hessian = np.zeros((len(logits), len(logits)), dtype=float)
    for index in range(len(logits)):
        left = logits.copy()
        right = logits.copy()
        left[index] -= step
        right[index] += step
        _, left_gradient = negative_log_likelihood_and_gradient(left, table)
        _, right_gradient = negative_log_likelihood_and_gradient(right, table)
        hessian[:, index] = (right_gradient - left_gradient) / (2.0 * step)
    hessian = (hessian + hessian.T) / 2.0
    eigenvalues = np.linalg.eigvalsh(hessian)
    if not np.all(np.isfinite(eigenvalues)) or float(np.min(eigenvalues)) <= 1e-7:
        return unavailable
    covariance = np.linalg.inv(hessian)
    comparisons = len(QUANTITIES) if simultaneous else 1
    alpha = (1.0 - confidence_level) / comparisons
    critical = float(norm.ppf(1.0 - alpha / 2.0))
    point = quantity_values(
        model,
        dict(zip(model.factor_ids, fit.probabilities, strict=True)),
    )
    result: dict[str, IntervalEstimate] = {}
    for quantity in QUANTITIES:
        gradient = np.zeros(len(logits), dtype=float)
        for index in range(len(logits)):
            left = logits.copy()
            right = logits.copy()
            left[index] -= step
            right[index] += step
            left_value = quantity_values(
                model,
                dict(zip(model.factor_ids, expit(left), strict=True)),
            )[quantity]
            right_value = quantity_values(
                model,
                dict(zip(model.factor_ids, expit(right), strict=True)),
            )[quantity]
            gradient[index] = (right_value - left_value) / (2.0 * step)
        variance = float(gradient @ covariance @ gradient)
        if not np.isfinite(variance) or variance < -1e-12:
            result[quantity] = unavailable[quantity]
            continue
        standard_error = sqrt(max(0.0, variance))
        minimum, maximum = _quantity_limits(quantity)
        result[quantity] = IntervalEstimate(
            max(minimum, point[quantity] - critical * standard_error),
            min(maximum, point[quantity] + critical * standard_error),
            point[quantity],
            "wald_bonferroni" if simultaneous else "wald_marginal",
        )
    return result


def simulation_only_ranges(
    model: BooleanFactorModel,
    probabilities: dict[str, float] | None,
    confidence_level: float,
    episodes: int,
) -> dict[str, IntervalEstimate]:
    if probabilities is None:
        return {
            quantity: IntervalEstimate(None, None, None, "simulation_only_unavailable")
            for quantity in QUANTITIES
        }
    point = quantity_values(model, probabilities)
    critical = float(norm.ppf(0.5 + confidence_level / 2.0))
    availability_se = {
        target: sqrt(point[target] * (1.0 - point[target]) / episodes)
        for target in (TARGET_CURRENT, TARGET_SPLIT, TARGET_ADD)
    }
    standard_errors = {
        **availability_se,
        DELTA_SPLIT: sqrt(
            availability_se[TARGET_SPLIT] ** 2
            + availability_se[TARGET_CURRENT] ** 2
        ),
        DELTA_ADD: sqrt(
            availability_se[TARGET_ADD] ** 2
            + availability_se[TARGET_CURRENT] ** 2
        ),
        CHOICE_DIFFERENCE: sqrt(
            availability_se[TARGET_SPLIT] ** 2
            + availability_se[TARGET_ADD] ** 2
        ),
    }
    result: dict[str, IntervalEstimate] = {}
    for quantity in QUANTITIES:
        minimum, maximum = _quantity_limits(quantity)
        result[quantity] = IntervalEstimate(
            max(minimum, point[quantity] - critical * standard_errors[quantity]),
            min(maximum, point[quantity] + critical * standard_errors[quantity]),
            point[quantity],
            "fixed_input_simulation_only",
        )
    return result
