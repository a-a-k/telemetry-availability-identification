from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import t

from .live_validation_config import (
    FrozenLiveValidationConfig,
    LiveAnalysisConfig,
    LiveObservationMode,
    LiveOperationSpec,
)
from .live_validation import frozen_live_matrix
from .provenance import environment_manifest, file_sha256
from .runner import _write_csv


class LiveValidationAnalysisError(RuntimeError):
    """Raised when qualified M7 evidence violates the frozen analysis contract."""


SIGNALS = ("ha", "hb", "pa", "pb")

PREDICTION_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "mode",
    "scope",
    "source_placement",
    "target_placement",
    "method",
    "operation",
    "requires_target_group",
    "prediction",
    "status",
    "route_prediction",
    "residual_success_probability",
    "fit_nll",
    "fit_status",
    "identification_rank",
    "identification_dimension",
    "target_gradient_residual",
    "multistart_prediction_range",
)

SCORE_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "mode",
    "scope",
    "source_placement",
    "target_placement",
    "method",
    "view",
    "block_length_seconds",
    "operation",
    "prediction",
    "test_requests",
    "test_successes",
    "test_success_fraction",
    "brier_score",
    "signed_prediction_error",
    "absolute_prediction_error",
    "test_block_mean_lower",
    "test_block_mean_upper",
    "prediction_in_test_block_interval",
)

DIAGNOSTIC_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "mode",
    "calibration_requests",
    "calibration_unaligned_requests",
    "calibration_transition_guarded_requests",
    "test_requests",
    "test_unaligned_requests",
    "test_transition_guarded_requests",
    "health_ticks",
    "observed_ha",
    "observed_hb",
    "observed_pa",
    "observed_pb",
    "complete_path_ticks",
    "health_signal_contradictions",
    "retained_traces",
    "topology_operations_confirmed",
    "topology_operations_unsupported",
    "replica_a_trace_assignments",
    "replica_b_trace_assignments",
    "optimizer_finite_starts",
    "optimizer_converged_starts",
    "best_nll",
    "b3_fit_status",
    "current_target_identified",
    "transfer_target_identified",
    "current_multistart_range",
    "transfer_multistart_range",
)

CONTRAST_FIELDS = (
    "scope",
    "mode",
    "view",
    "metric",
    "contrast",
    "campaigns",
    "strata",
    "estimate",
    "standard_error",
    "degrees_of_freedom",
    "confidence_lower",
    "confidence_upper",
    "two_sided_p_value",
    "holm_adjusted_p_value",
    "complete",
    "primary",
)

SUMMARY_FIELDS = (
    "scope",
    "mode",
    "view",
    "method",
    "complete_campaigns",
    "mean_brier_score",
    "mean_signed_prediction_error",
    "mean_absolute_prediction_error",
    "prediction_interval_compatibility_fraction",
)


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def _stable_uniform(seed: int, *parts: object) -> float:
    material = "|".join([str(seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _smoothed_mean(
    successes: float,
    observations: int,
    analysis: LiveAnalysisConfig,
) -> float:
    return (
        successes + analysis.baseline_beta_prior_alpha
    ) / (
        observations
        + analysis.baseline_beta_prior_alpha
        + analysis.baseline_beta_prior_beta
    )


@dataclass(frozen=True)
class HealthTick:
    at: float
    elapsed_seconds: float
    signals: tuple[int, int, int, int]


@dataclass(frozen=True)
class RequestRecord:
    period: str
    request_id: str
    operation: str
    at: float
    success: int
    trace_present: bool
    span_count: int
    services: frozenset[str]
    target_replicas: frozenset[str]


@dataclass(frozen=True)
class EvaluationRequest:
    operation: str
    at: float
    success: int


@dataclass(frozen=True)
class QualifiedCell:
    profile: str
    placement: str
    failure_law: str
    repetition: int
    target_service: str
    learner_requests: tuple[RequestRecord, ...]
    health: tuple[HealthTick, ...]
    test_requests: tuple[EvaluationRequest, ...]
    test_health: tuple[HealthTick, ...]
    boundary: dict[str, Any]
    directory: Path

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return (self.profile, self.placement, self.failure_law, self.repetition)


@dataclass(frozen=True)
class TopologyResult:
    operation: str
    inferred_requires_target: bool | None
    expected_requires_target: bool
    status: str
    trace_support: int
    target_trace_fraction: float
    replica_a_assignments: int
    replica_b_assignments: int


@dataclass(frozen=True)
class TickEvidence:
    observed: tuple[int | None, int | None, int | None, int | None]
    outcomes: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class PreparedMode:
    mode: LiveObservationMode
    operations: tuple[LiveOperationSpec, ...]
    q_by_operation: dict[str, float]
    topology: dict[str, TopologyResult]
    ticks: tuple[TickEvidence, ...]
    raw_signals: tuple[tuple[int, int, int, int], ...]
    calibration_by_operation: dict[str, tuple[int, ...]]
    retained_traces: int
    unaligned_calibration: int
    guarded_calibration: int
    health_signal_contradictions: int


@dataclass(frozen=True)
class FitCandidate:
    parameters: dict[str, float]
    nll: float
    converged: bool
    message: str
    current_route: float
    transfer_route: float


@dataclass(frozen=True)
class ExactFit:
    best: FitCandidate | None
    candidates: tuple[FitCandidate, ...]
    parameter_names: tuple[str, ...]
    status: str
    current_identified: bool
    transfer_identified: bool
    rank: int
    dimension: int
    current_gradient_residual: float
    transfer_gradient_residual: float
    current_prediction_range: float
    transfer_prediction_range: float


def _health_signal(row: dict[str, str], replica: str) -> tuple[int, int]:
    observed = _bool(row[f"replica_{replica}_observed"])
    if not observed:
        raise LiveValidationAnalysisError("qualified health tick hides a replica")
    instance = int(
        _bool(row[f"replica_{replica}_running"])
        and not _bool(row[f"replica_{replica}_paused"])
    )
    backend = str(row[f"replica_{replica}_backend_status"]).upper()
    check = str(row[f"replica_{replica}_backend_check_status"]).upper()
    path = int(
        instance
        and int(float(row[f"replica_{replica}_network_count"])) > 0
        and backend == "UP"
        and check in {"", "L4OK"}
    )
    return instance, path


def _health_ticks(path: Path) -> tuple[HealthTick, ...]:
    result = []
    for row in _rows(path):
        ha, pa = _health_signal(row, "a")
        hb, pb = _health_signal(row, "b")
        result.append(
            HealthTick(
                at=_timestamp(row["observed_at"]),
                elapsed_seconds=float(row["elapsed_seconds"]),
                signals=(ha, hb, pa, pb),
            )
        )
    return tuple(sorted(result, key=lambda item: item.at))


def load_qualified_cell(directory: str | Path) -> QualifiedCell:
    cell = Path(directory)
    learner_manifest = json.loads(
        (cell / "learner" / "manifest.json").read_text(encoding="utf-8")
    )
    boundary = json.loads(
        (cell / "audit" / "boundary.json").read_text(encoding="utf-8")
    )
    if boundary.get("usable") is not True:
        raise LiveValidationAnalysisError(f"unusable evidence boundary at {cell}")
    deployment = json.loads(
        (cell / "learner" / "deployment.json").read_text(encoding="utf-8")
    )
    requests = tuple(
        RequestRecord(
            period=row["period"],
            request_id=row["request_id"],
            operation=row["operation"],
            at=_timestamp(row["started_at"]),
            success=int(_bool(row["semantic_success"])),
            trace_present=_bool(row["trace_present"]),
            span_count=int(row["span_count"]),
            services=frozenset(filter(None, row["services"].split(";"))),
            target_replicas=frozenset(
                filter(None, row["target_replicas"].split(";"))
            ),
        )
        for row in _rows(cell / "learner" / "requests.csv")
    )
    evaluation = tuple(
        EvaluationRequest(
            operation=row["operation"],
            at=_timestamp(row["started_at"]),
            success=int(_bool(row["semantic_success"])),
        )
        for row in _rows(cell / "evaluator" / "test-requests.csv")
    )
    identity = (
        str(learner_manifest["profile"]),
        str(learner_manifest["placement"]),
        str(learner_manifest["failure_law"]),
        int(learner_manifest["repetition"]),
    )
    return QualifiedCell(
        profile=identity[0],
        placement=identity[1],
        failure_law=identity[2],
        repetition=identity[3],
        target_service=str(deployment["target_service"]),
        learner_requests=requests,
        health=_health_ticks(cell / "learner" / "health.csv"),
        test_requests=evaluation,
        test_health=_health_ticks(cell / "evaluator" / "test-health.csv"),
        boundary=boundary,
        directory=cell,
    )


def discover_qualified_cells(input_root: str | Path) -> list[QualifiedCell]:
    root = Path(input_root)
    manifests = sorted(root.rglob("learner/manifest.json"))
    cells = [load_qualified_cell(path.parents[1]) for path in manifests]
    identities = [cell.identity for cell in cells]
    if len(identities) != len(set(identities)):
        raise LiveValidationAnalysisError("duplicate qualified cell identities")
    return sorted(cells, key=lambda cell: cell.identity)


def _transition_times(ticks: tuple[HealthTick, ...]) -> tuple[float, ...]:
    return tuple(
        current.at
        for previous, current in zip(ticks, ticks[1:], strict=False)
        if current.signals != previous.signals
    )


def _near_transition(at: float, transitions: tuple[float, ...], guard: int) -> bool:
    insertion = bisect_left(transitions, at)
    return any(
        abs(at - transitions[index]) <= guard
        for index in (insertion - 1, insertion)
        if 0 <= index < len(transitions)
    )


def _nearest_tick(at: float, ticks: tuple[HealthTick, ...]) -> tuple[int, float]:
    if not ticks:
        return -1, math.inf
    times = _tick_times(ticks)
    insertion = bisect_left(times, at)
    candidates = [index for index in (insertion - 1, insertion) if 0 <= index < len(ticks)]
    index = min(candidates, key=lambda item: abs(ticks[item].at - at))
    return index, abs(ticks[index].at - at)


@lru_cache(maxsize=None)
def _tick_times(ticks: tuple[HealthTick, ...]) -> tuple[float, ...]:
    return tuple(tick.at for tick in ticks)


def infer_topology(
    cell: QualifiedCell,
    mode: LiveObservationMode,
    operations: tuple[LiveOperationSpec, ...],
    analysis: LiveAnalysisConfig,
) -> tuple[dict[str, TopologyResult], int]:
    retained = []
    for request in cell.learner_requests:
        if request.period not in {"baseline", "calibration"}:
            continue
        keep = _stable_uniform(
            analysis.seed,
            *cell.identity,
            mode.id,
            "trace",
            request.request_id,
        ) < mode.trace_keep_probability
        if keep and request.success and request.trace_present and request.span_count > 0:
            retained.append(request)

    results: dict[str, TopologyResult] = {}
    for specification in operations:
        rows = [row for row in retained if row.operation == specification.id]
        target_rows = [row for row in rows if cell.target_service in row.services]
        fraction = len(target_rows) / len(rows) if rows else math.nan
        if len(rows) < analysis.minimum_trace_operation_support:
            inferred = None
            status = "insufficient_trace_support"
        elif fraction >= analysis.required_target_trace_fraction:
            inferred = True
            status = "confirmed"
        elif fraction <= analysis.maximum_nontarget_trace_fraction:
            inferred = False
            status = "confirmed"
        else:
            inferred = None
            status = "ambiguous_target_fraction"
        replica_counts = Counter(
            replica for row in target_rows for replica in row.target_replicas
        )
        if inferred is not None and inferred != specification.requires_target_group:
            status = "frozen_specification_mismatch"
        if inferred is True and any(
            replica_counts[replica] < analysis.minimum_replica_trace_assignments
            for replica in ("a", "b")
        ):
            status = "insufficient_replica_assignments"
        results[specification.id] = TopologyResult(
            operation=specification.id,
            inferred_requires_target=inferred,
            expected_requires_target=specification.requires_target_group,
            status=status,
            trace_support=len(rows),
            target_trace_fraction=fraction,
            replica_a_assignments=replica_counts["a"],
            replica_b_assignments=replica_counts["b"],
        )
    return results, len(retained)


def _mask_signals(
    cell: QualifiedCell,
    mode: LiveObservationMode,
    tick_index: int,
    signals: tuple[int, int, int, int],
    analysis: LiveAnalysisConfig,
) -> tuple[int | None, int | None, int | None, int | None]:
    if mode.health_policy == "none":
        return (None, None, None, None)
    if mode.health_policy == "staggered":
        offset = int(
            _stable_uniform(analysis.seed, *cell.identity, mode.id, "stagger-offset")
            * 2
        )
        observe_a = (tick_index + offset) % 2 == 0
        return (
            signals[0] if observe_a else None,
            signals[1] if not observe_a else None,
            signals[2] if observe_a else None,
            signals[3] if not observe_a else None,
        )
    return tuple(
        value
        if _stable_uniform(
            analysis.seed,
            *cell.identity,
            mode.id,
            "health",
            tick_index,
            signal,
        )
        < mode.health_keep_probability
        else None
        for signal, value in zip(SIGNALS, signals, strict=True)
    )  # type: ignore[return-value]


def prepare_mode(
    cell: QualifiedCell,
    mode: LiveObservationMode,
    analysis: LiveAnalysisConfig,
) -> PreparedMode:
    operations = analysis.operations[cell.profile]
    q_by_operation: dict[str, float] = {}
    calibration_by_operation: dict[str, tuple[int, ...]] = {}
    for specification in operations:
        baseline = [
            row.success
            for row in cell.learner_requests
            if row.period == "baseline" and row.operation == specification.id
        ]
        if len(baseline) < analysis.minimum_operation_requests:
            q_by_operation[specification.id] = math.nan
        else:
            q_by_operation[specification.id] = _smoothed_mean(
                sum(baseline), len(baseline), analysis
            )
        calibration_by_operation[specification.id] = tuple(
            row.success
            for row in cell.learner_requests
            if row.period == "calibration" and row.operation == specification.id
        )

    topology, retained_traces = infer_topology(cell, mode, operations, analysis)
    target_operations = tuple(
        item.id
        for item in operations
        if topology[item.id].status == "confirmed"
        and topology[item.id].inferred_requires_target is True
    )
    operation_index = {operation: index for index, operation in enumerate(target_operations)}
    outcomes: list[list[list[int]]] = [
        [[0, 0] for _ in target_operations] for _ in cell.health
    ]
    unaligned = 0
    guarded = 0
    transitions = _transition_times(cell.health)
    for request in cell.learner_requests:
        if request.period != "calibration" or request.operation not in operation_index:
            continue
        tick_index, distance = _nearest_tick(request.at, cell.health)
        if distance > analysis.health_alignment_tolerance_seconds:
            unaligned += 1
            continue
        if _near_transition(
            request.at, transitions, analysis.transition_guard_seconds_each_side
        ):
            guarded += 1
        slot = outcomes[tick_index][operation_index[request.operation]]
        slot[0] += 1
        slot[1] += request.success

    masked = tuple(
        _mask_signals(cell, mode, index, tick.signals, analysis)
        for index, tick in enumerate(cell.health)
    )
    tick_evidence = tuple(
        TickEvidence(
            observed=observed,
            outcomes=tuple((int(values[0]), int(values[1])) for values in per_operation),
        )
        for observed, per_operation in zip(masked, outcomes, strict=True)
    )
    contradictions = sum(
        (signals[2] > signals[0]) + (signals[3] > signals[1])
        for signals in (tick.signals for tick in cell.health)
    )
    return PreparedMode(
        mode=mode,
        operations=operations,
        q_by_operation=q_by_operation,
        topology=topology,
        ticks=tick_evidence,
        raw_signals=tuple(tick.signals for tick in cell.health),
        calibration_by_operation=calibration_by_operation,
        retained_traces=retained_traces,
        unaligned_calibration=unaligned,
        guarded_calibration=guarded,
        health_signal_contradictions=contradictions,
    )


@dataclass(frozen=True)
class LatentTemplate:
    placement: str
    bits: np.ndarray
    signals: np.ndarray
    route: np.ndarray


@dataclass(frozen=True)
class LikelihoodData:
    template: LatentTemplate
    consistency: np.ndarray
    log_outcome_route_down: np.ndarray
    log_outcome_route_up: np.ndarray
    multiplicities: np.ndarray
    masks: tuple[tuple[bool, bool, bool, bool], ...]
    mask_has_outcome: tuple[bool, ...]


def _parameter_names(failure_law: str) -> tuple[str, ...]:
    names = ["ea", "eb"]
    if "D" in failure_law:
        names.insert(0, "g")
    if "C" in failure_law:
        names.extend(("ca", "cb"))
    return tuple(names)


def _latent_template(placement: str) -> LatentTemplate:
    if placement == "colocated":
        bits = np.asarray(tuple(itertools.product((0, 1), repeat=5)), dtype=int)
        g, ea, eb, ca, cb = bits.T
        ha = g * ea
        hb = g * eb
    elif placement == "split":
        bits = np.asarray(tuple(itertools.product((0, 1), repeat=6)), dtype=int)
        ga, gb, ea, eb, ca, cb = bits.T
        ha = ga * ea
        hb = gb * eb
    else:
        raise LiveValidationAnalysisError(f"unknown placement {placement!r}")
    pa = ha * ca
    pb = hb * cb
    signals = np.column_stack((ha, hb, pa, pb)).astype(int)
    route = np.maximum(pa, pb).astype(int)
    return LatentTemplate(
        placement=placement,
        bits=bits,
        signals=signals,
        route=route,
    )


def _state_probabilities(
    template: LatentTemplate,
    parameters: dict[str, float],
) -> np.ndarray:
    g = parameters.get("g", 1.0)
    values = (
        np.asarray(
            [g, parameters["ea"], parameters["eb"], parameters.get("ca", 1.0), parameters.get("cb", 1.0)],
            dtype=float,
        )
        if template.placement == "colocated"
        else np.asarray(
            [g, g, parameters["ea"], parameters["eb"], parameters.get("ca", 1.0), parameters.get("cb", 1.0)],
            dtype=float,
        )
    )
    factors = np.where(template.bits == 1, values, 1.0 - values)
    probabilities = np.prod(factors, axis=1)
    total = float(probabilities.sum())
    if not total > 0:
        raise LiveValidationAnalysisError("latent-state probabilities have zero mass")
    return probabilities / total


def route_probability(parameters: dict[str, float], placement: str) -> float:
    template = _latent_template(placement)
    probabilities = _state_probabilities(template, parameters)
    return float(probabilities @ template.route)


def _target_operations(prepared: PreparedMode) -> tuple[str, ...]:
    return tuple(
        item.id
        for item in prepared.operations
        if prepared.topology[item.id].status == "confirmed"
        and prepared.topology[item.id].inferred_requires_target is True
    )


def _binomial_log_kernel(successes: int, attempts: int, probability: float) -> float:
    if not attempts:
        return 0.0
    return successes * math.log(probability) + (attempts - successes) * math.log1p(
        -probability
    )


def _likelihood_data(
    prepared: PreparedMode,
    placement: str,
    analysis: LiveAnalysisConfig,
) -> LikelihoodData:
    operations = _target_operations(prepared)
    compressed = Counter((tick.observed, tick.outcomes) for tick in prepared.ticks)
    records = list(compressed)
    template = _latent_template(placement)
    consistency = np.ones((len(records), len(template.route)), dtype=float)
    down_logs = np.zeros(len(records), dtype=float)
    up_logs = np.zeros(len(records), dtype=float)
    multiplicities = np.asarray([compressed[record] for record in records], dtype=float)
    mask_counts: Counter[tuple[bool, bool, bool, bool]] = Counter()
    mask_outcomes: Counter[tuple[bool, bool, bool, bool]] = Counter()
    floor = analysis.numerical_probability_floor
    for row_index, (observed, outcomes) in enumerate(records):
        mask = tuple(value is not None for value in observed)
        mask_counts[mask] += compressed[(observed, outcomes)]
        if sum(attempts for attempts, _ in outcomes):
            mask_outcomes[mask] += compressed[(observed, outcomes)]
        for signal_index, value in enumerate(observed):
            if value is not None:
                consistency[row_index] *= (
                    template.signals[:, signal_index] == value
                )
        for operation, (attempts, successes) in zip(operations, outcomes, strict=True):
            q = prepared.q_by_operation[operation]
            down_logs[row_index] += _binomial_log_kernel(
                successes, attempts, floor
            )
            up_logs[row_index] += _binomial_log_kernel(
                successes, attempts, min(max(q, floor), 1.0 - floor)
            )
    admitted_masks = tuple(
        mask
        for mask, count in sorted(mask_counts.items())
        if count >= analysis.minimum_pattern_observations
    )
    return LikelihoodData(
        template=template,
        consistency=consistency,
        log_outcome_route_down=down_logs,
        log_outcome_route_up=up_logs,
        multiplicities=multiplicities,
        masks=admitted_masks,
        mask_has_outcome=tuple(
            mask_outcomes[mask] >= analysis.minimum_pattern_observations
            for mask in admitted_masks
        ),
    )


def _vector_parameters(
    names: tuple[str, ...], values: np.ndarray
) -> dict[str, float]:
    return {name: float(value) for name, value in zip(names, values, strict=True)}


def _negative_log_likelihood(
    values: np.ndarray,
    names: tuple[str, ...],
    data: LikelihoodData,
    floor: float,
) -> float:
    parameters = _vector_parameters(names, values)
    probabilities = _state_probabilities(data.template, parameters)
    down_mass = data.consistency @ (
        probabilities * (data.template.route == 0)
    )
    up_mass = data.consistency @ (
        probabilities * (data.template.route == 1)
    )
    log_down = np.log(np.maximum(down_mass, floor)) + data.log_outcome_route_down
    log_up = np.log(np.maximum(up_mass, floor)) + data.log_outcome_route_up
    values_by_record = np.logaddexp(log_down, log_up)
    result = -float(data.multiplicities @ values_by_record)
    return result if math.isfinite(result) else math.inf


def _observable_features(
    values: np.ndarray,
    names: tuple[str, ...],
    data: LikelihoodData,
) -> np.ndarray:
    parameters = _vector_parameters(names, values)
    probabilities = _state_probabilities(data.template, parameters)
    features: list[float] = []
    for mask, has_outcome in zip(data.masks, data.mask_has_outcome, strict=True):
        indexes = [index for index, observed in enumerate(mask) if observed]
        for pattern in itertools.product((0, 1), repeat=len(indexes)):
            consistent = np.ones(len(probabilities), dtype=bool)
            for index, value in zip(indexes, pattern, strict=True):
                consistent &= data.template.signals[:, index] == value
            features.append(float(probabilities[consistent].sum()))
            if has_outcome:
                features.append(
                    float(
                        probabilities[
                            consistent & (data.template.route == 1)
                        ].sum()
                    )
                )
    return np.asarray(features, dtype=float)


def _numerical_jacobian(
    function: Any,
    point: np.ndarray,
    epsilon: float,
) -> np.ndarray:
    baseline = np.asarray(function(point), dtype=float)
    jacobian = np.zeros((len(baseline), len(point)), dtype=float)
    for index in range(len(point)):
        step = max(1e-6, abs(point[index]) * 1e-5)
        lower = point.copy()
        upper = point.copy()
        lower[index] = max(epsilon, point[index] - step)
        upper[index] = min(1.0 - epsilon, point[index] + step)
        width = upper[index] - lower[index]
        jacobian[:, index] = (
            np.asarray(function(upper), dtype=float)
            - np.asarray(function(lower), dtype=float)
        ) / width
    return jacobian


def _target_gradient(
    names: tuple[str, ...],
    point: np.ndarray,
    placement: str,
    epsilon: float,
) -> np.ndarray:
    return _numerical_jacobian(
        lambda values: np.asarray(
            [route_probability(_vector_parameters(names, values), placement)]
        ),
        point,
        epsilon,
    )[0]


def _gradient_residual(jacobian: np.ndarray, gradient: np.ndarray, rank: int) -> float:
    if not rank:
        return float(np.linalg.norm(gradient))
    _, _, right = np.linalg.svd(jacobian, full_matrices=False)
    basis = right[:rank]
    projected = basis.T @ (basis @ gradient)
    return float(np.linalg.norm(gradient - projected))


def fit_exact_model(
    cell: QualifiedCell,
    prepared: PreparedMode,
    analysis: LiveAnalysisConfig,
) -> ExactFit:
    target_operations = _target_operations(prepared)
    if not target_operations:
        return ExactFit(
            best=None,
            candidates=(),
            parameter_names=(),
            status="no_trace_supported_target_operations",
            current_identified=False,
            transfer_identified=False,
            rank=0,
            dimension=0,
            current_gradient_residual=math.nan,
            transfer_gradient_residual=math.nan,
            current_prediction_range=math.nan,
            transfer_prediction_range=math.nan,
        )
    if any(not math.isfinite(prepared.q_by_operation[item]) for item in target_operations):
        return ExactFit(
            best=None,
            candidates=(),
            parameter_names=(),
            status="insufficient_clean_baseline",
            current_identified=False,
            transfer_identified=False,
            rank=0,
            dimension=0,
            current_gradient_residual=math.nan,
            transfer_gradient_residual=math.nan,
            current_prediction_range=math.nan,
            transfer_prediction_range=math.nan,
        )
    names = _parameter_names(cell.failure_law)
    data = _likelihood_data(prepared, cell.placement, analysis)
    epsilon = analysis.parameter_epsilon
    bounds = [(epsilon, 1.0 - epsilon)] * len(names)
    start_seed = int(
        _stable_uniform(analysis.seed, *cell.identity, prepared.mode.id, "optimizer")
        * (2**63 - 1)
    )
    generator = np.random.default_rng(start_seed)
    starts = [np.full(len(names), 0.9, dtype=float)]
    starts.extend(
        generator.uniform(0.55, 0.99, size=len(names))
        for _ in range(analysis.optimizer_starts - 1)
    )
    candidates: list[FitCandidate] = []
    for start in starts:
        result = minimize(
            _negative_log_likelihood,
            start,
            args=(names, data, analysis.numerical_probability_floor),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": analysis.optimizer_max_iterations, "ftol": 1e-12},
        )
        if not math.isfinite(float(result.fun)):
            continue
        parameters = _vector_parameters(names, np.asarray(result.x, dtype=float))
        candidates.append(
            FitCandidate(
                parameters=parameters,
                nll=float(result.fun),
                converged=bool(result.success),
                message=str(result.message),
                current_route=route_probability(parameters, cell.placement),
                transfer_route=route_probability(parameters, "split"),
            )
        )
    if not candidates:
        return ExactFit(
            best=None,
            candidates=(),
            parameter_names=names,
            status="all_starts_nonfinite",
            current_identified=False,
            transfer_identified=False,
            rank=0,
            dimension=len(names),
            current_gradient_residual=math.nan,
            transfer_gradient_residual=math.nan,
            current_prediction_range=math.nan,
            transfer_prediction_range=math.nan,
        )
    candidates.sort(key=lambda item: item.nll)
    best = candidates[0]
    equivalent = [
        item
        for item in candidates
        if item.nll - best.nll <= 1e-6 * max(1.0, abs(best.nll))
    ]
    current_range = max(item.current_route for item in equivalent) - min(
        item.current_route for item in equivalent
    )
    transfer_range = max(item.transfer_route for item in equivalent) - min(
        item.transfer_route for item in equivalent
    )
    point = np.asarray([best.parameters[name] for name in names], dtype=float)
    jacobian = _numerical_jacobian(
        lambda values: _observable_features(values, names, data), point, epsilon
    )
    singular = np.linalg.svd(jacobian, compute_uv=False)
    threshold = analysis.rank_tolerance * max(1.0, singular[0] if len(singular) else 0.0)
    rank = int(np.sum(singular > threshold))
    current_gradient = _target_gradient(names, point, cell.placement, epsilon)
    transfer_gradient = _target_gradient(names, point, "split", epsilon)
    current_residual = _gradient_residual(jacobian, current_gradient, rank)
    transfer_residual = _gradient_residual(jacobian, transfer_gradient, rank)
    current_identified = (
        current_residual
        <= analysis.target_gradient_tolerance * (1.0 + np.linalg.norm(current_gradient))
        and current_range <= analysis.multistart_prediction_tolerance
    )
    transfer_identified = (
        transfer_residual
        <= analysis.target_gradient_tolerance * (1.0 + np.linalg.norm(transfer_gradient))
        and transfer_range <= analysis.multistart_prediction_tolerance
    )
    status = "regular" if best.converged else "finite_nonconvergence"
    if any(
        value <= epsilon * 1.01 or value >= 1.0 - epsilon * 1.01
        for value in best.parameters.values()
    ):
        status = "boundary" if best.converged else "boundary_nonconvergence"
    return ExactFit(
        best=best,
        candidates=tuple(candidates),
        parameter_names=names,
        status=status,
        current_identified=current_identified,
        transfer_identified=transfer_identified,
        rank=rank,
        dimension=len(names),
        current_gradient_residual=current_residual,
        transfer_gradient_residual=transfer_residual,
        current_prediction_range=current_range,
        transfer_prediction_range=transfer_range,
    )


def _signal_mean(
    prepared: PreparedMode,
    signal_index: int,
    analysis: LiveAnalysisConfig,
) -> tuple[float, int]:
    values = [
        tick.observed[signal_index]
        for tick in prepared.ticks
        if tick.observed[signal_index] is not None
    ]
    if len(values) < analysis.minimum_signal_observations:
        return math.nan, len(values)
    return _smoothed_mean(sum(int(value) for value in values), len(values), analysis), len(values)


def _joint_health_mean(
    prepared: PreparedMode,
    analysis: LiveAnalysisConfig,
) -> tuple[float, int]:
    pairs = [
        (tick.observed[0], tick.observed[1])
        for tick in prepared.ticks
        if tick.observed[0] is not None and tick.observed[1] is not None
    ]
    if len(pairs) < analysis.minimum_pattern_observations:
        return math.nan, len(pairs)
    successes = sum(int(left) * int(right) for left, right in pairs)
    return _smoothed_mean(successes, len(pairs), analysis), len(pairs)


def _complete_route_mean(
    prepared: PreparedMode,
    analysis: LiveAnalysisConfig,
) -> tuple[float, int]:
    rows = [
        tick.observed
        for tick in prepared.ticks
        if all(value is not None for value in tick.observed)
    ]
    if len(rows) < analysis.minimum_pattern_observations:
        return math.nan, len(rows)
    successes = sum(int(row[2]) or int(row[3]) for row in rows)
    return _smoothed_mean(successes, len(rows), analysis), len(rows)


def _route_mle(
    prepared: PreparedMode,
    analysis: LiveAnalysisConfig,
) -> float:
    operations = _target_operations(prepared)
    records = []
    for operation in operations:
        outcomes = prepared.calibration_by_operation[operation]
        q = prepared.q_by_operation[operation]
        if len(outcomes) >= analysis.minimum_operation_requests and math.isfinite(q):
            records.append((len(outcomes), sum(outcomes), q))
    if not records:
        return math.nan
    floor = analysis.numerical_probability_floor

    def objective(route: float) -> float:
        return -sum(
            _binomial_log_kernel(
                successes,
                attempts,
                min(max(q * route, floor), 1.0 - floor),
            )
            for attempts, successes, q in records
        )

    result = minimize_scalar(
        objective,
        bounds=(analysis.parameter_epsilon, 1.0 - analysis.parameter_epsilon),
        method="bounded",
        options={"xatol": 1e-10},
    )
    return float(result.x) if math.isfinite(float(result.fun)) else math.nan


def _route_estimates(
    cell: QualifiedCell,
    prepared: PreparedMode,
    analysis: LiveAnalysisConfig,
) -> dict[str, tuple[float, str]]:
    ha, _ = _signal_mean(prepared, 0, analysis)
    hb, _ = _signal_mean(prepared, 1, analysis)
    pa, _ = _signal_mean(prepared, 2, analysis)
    pb, _ = _signal_mean(prepared, 3, analysis)
    endpoint = _route_mle(prepared, analysis)
    independent = (
        1.0 - (1.0 - pa) * (1.0 - pb)
        if math.isfinite(pa) and math.isfinite(pb)
        else math.nan
    )
    b1_status = "estimated" if math.isfinite(independent) else "insufficient_path_marginals"

    if cell.placement == "split" or "D" not in cell.failure_law:
        b2_current = independent
        b2_status = b1_status
    elif all(math.isfinite(value) for value in (ha, hb, pa, pb)):
        h_joint, joint_count = _joint_health_mean(prepared, analysis)
        ca = min(1.0, max(0.0, pa / max(ha, analysis.parameter_epsilon)))
        cb = min(1.0, max(0.0, pb / max(hb, analysis.parameter_epsilon)))
        if math.isfinite(h_joint):
            b2_current = min(
                1.0,
                max(0.0, pa + pb - h_joint * ca * cb),
            )
            b2_status = f"joint_health_moment_n{joint_count}"
        elif math.isfinite(endpoint):
            b2_current = endpoint
            b2_status = "endpoint_or_fallback_without_joint_health"
        else:
            b2_current = math.nan
            b2_status = "insufficient_joint_health_and_endpoint"
    elif math.isfinite(endpoint):
        b2_current = endpoint
        b2_status = "endpoint_or_fallback_without_health_marginals"
    else:
        b2_current = math.nan
        b2_status = "insufficient_available_moments"

    b2_transfer = independent
    b2_transfer_status = (
        "new_domain_from_path_marginals"
        if math.isfinite(independent)
        else "unsupported_without_path_marginals"
    )
    b4_current, complete = _complete_route_mean(prepared, analysis)
    return {
        "B1_current": (independent, b1_status),
        "B1_transfer": (independent, b1_status),
        "B2_current": (b2_current, b2_status),
        "B2_transfer": (b2_transfer, b2_transfer_status),
        "B4_current": (
            b4_current,
            f"empirical_joint_path_n{complete}"
            if math.isfinite(b4_current)
            else "insufficient_complete_path_ticks",
        ),
        "endpoint": (endpoint, "calibration_endpoint_route_mle"),
    }


def _prediction_row(
    cell: QualifiedCell,
    prepared: PreparedMode,
    fit: ExactFit,
    scope: str,
    target_placement: str,
    method: str,
    specification: LiveOperationSpec,
    prediction: float,
    status: str,
    route: float = math.nan,
) -> dict[str, Any]:
    best = fit.best
    residual = (
        fit.current_gradient_residual
        if scope == "current"
        else fit.transfer_gradient_residual
    )
    prediction_range = (
        fit.current_prediction_range
        if scope == "current"
        else fit.transfer_prediction_range
    )
    return {
        "profile": cell.profile,
        "failure_law": cell.failure_law,
        "repetition": cell.repetition,
        "mode": prepared.mode.id,
        "scope": scope,
        "source_placement": cell.placement,
        "target_placement": target_placement,
        "method": method,
        "operation": specification.id,
        "requires_target_group": specification.requires_target_group,
        "prediction": prediction if math.isfinite(prediction) else "",
        "status": status,
        "route_prediction": route if math.isfinite(route) else "",
        "residual_success_probability": (
            prepared.q_by_operation[specification.id]
            if math.isfinite(prepared.q_by_operation[specification.id])
            else ""
        ),
        "fit_nll": best.nll if best is not None else "",
        "fit_status": fit.status,
        "identification_rank": fit.rank,
        "identification_dimension": fit.dimension,
        "target_gradient_residual": residual if math.isfinite(residual) else "",
        "multistart_prediction_range": (
            prediction_range if math.isfinite(prediction_range) else ""
        ),
    }


def predict_cell(
    cell: QualifiedCell,
    prepared: PreparedMode,
    fit: ExactFit,
    analysis: LiveAnalysisConfig,
    scope: str = "current",
) -> list[dict[str, Any]]:
    if scope not in {"current", "transfer"}:
        raise ValueError("scope must be current or transfer")
    target_placement = cell.placement if scope == "current" else analysis.target_placement
    estimates = _route_estimates(cell, prepared, analysis)
    exact_route = math.nan
    if fit.best is not None:
        exact_route = (
            fit.best.current_route if scope == "current" else fit.best.transfer_route
        )
    exact_identified = fit.current_identified if scope == "current" else fit.transfer_identified
    rows: list[dict[str, Any]] = []
    for specification in prepared.operations:
        operation = specification.id
        q = prepared.q_by_operation[operation]
        topology = prepared.topology[operation]
        calibration = prepared.calibration_by_operation[operation]
        b0 = (
            _smoothed_mean(sum(calibration), len(calibration), analysis)
            if len(calibration) >= analysis.minimum_operation_requests
            else math.nan
        )
        for method in analysis.methods:
            route = math.nan
            if method == "B0":
                prediction = b0
                status = "endpoint_persistence" if math.isfinite(b0) else "insufficient_calibration_requests"
            elif topology.status != "confirmed":
                prediction = math.nan
                status = f"topology_{topology.status}"
            elif not specification.requires_target_group:
                prediction = q
                status = "clean_baseline_residual" if math.isfinite(q) else "insufficient_clean_baseline"
            elif method == "B1":
                route, status = estimates[f"B1_{scope}"]
                prediction = q * route if math.isfinite(q) and math.isfinite(route) else math.nan
            elif method == "B2":
                route, status = estimates[f"B2_{scope}"]
                prediction = q * route if math.isfinite(q) and math.isfinite(route) else math.nan
            elif method == "B4":
                if scope == "transfer":
                    prediction = math.nan
                    status = "structural_abstention_on_unobserved_placement"
                else:
                    route, status = estimates["B4_current"]
                    prediction = q * route if math.isfinite(q) and math.isfinite(route) else math.nan
            elif method == "B3":
                route = exact_route
                prediction = q * route if math.isfinite(q) and math.isfinite(route) else math.nan
                status = (
                    "same_model_exact_likelihood"
                    if exact_identified
                    else "raw_unidentified_optimizer_point"
                )
            elif method == "proposed":
                if exact_identified:
                    route = exact_route
                    prediction = q * route if math.isfinite(q) and math.isfinite(route) else math.nan
                    status = "identified_exact_likelihood"
                else:
                    prediction = math.nan
                    status = "identification_guard_abstention"
            else:  # frozen by configuration validation
                raise LiveValidationAnalysisError(f"unknown method {method!r}")
            rows.append(
                _prediction_row(
                    cell,
                    prepared,
                    fit,
                    scope,
                    target_placement,
                    method,
                    specification,
                    prediction,
                    status,
                    route,
                )
            )
    return rows


def _block_interval(
    requests: list[EvaluationRequest],
    block_seconds: int,
    confidence_level: float,
) -> tuple[float, float]:
    if not requests:
        return math.nan, math.nan
    origin = min(request.at for request in requests)
    blocks: dict[int, list[int]] = defaultdict(list)
    for request in requests:
        blocks[int((request.at - origin) // block_seconds)].append(request.success)
    means = np.asarray(
        [sum(values) / len(values) for _, values in sorted(blocks.items())],
        dtype=float,
    )
    center = float(means.mean())
    if len(means) < 2:
        return center, center
    standard_error = float(means.std(ddof=1) / math.sqrt(len(means)))
    critical = float(t.ppf(0.5 + confidence_level / 2, len(means) - 1))
    return max(0.0, center - critical * standard_error), min(
        1.0, center + critical * standard_error
    )


def _evaluation_views(
    cell: QualifiedCell,
    analysis: LiveAnalysisConfig,
) -> tuple[tuple[str, int, list[EvaluationRequest]], ...]:
    transitions = _transition_times(cell.test_health)
    stable = [
        request
        for request in cell.test_requests
        if not _near_transition(
            request.at,
            transitions,
            analysis.transition_guard_seconds_each_side,
        )
    ]
    return (
        ("stable", analysis.block_length_seconds, stable),
        ("all_sequence", analysis.block_length_seconds, list(cell.test_requests)),
        (
            "stable_block_sensitivity",
            analysis.sensitivity_block_length_seconds,
            stable,
        ),
    )


def score_predictions(
    predictions: Iterable[dict[str, Any]],
    target_cell: QualifiedCell,
    analysis: LiveAnalysisConfig,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for view, block_length, requests in _evaluation_views(target_cell, analysis):
        by_operation = {
            operation.id: [
                request for request in requests if request.operation == operation.id
            ]
            for operation in analysis.operations[target_cell.profile]
        }
        for prediction_row in predictions:
            if prediction_row["profile"] != target_cell.profile:
                raise LiveValidationAnalysisError("prediction/test profile mismatch")
            if prediction_row["failure_law"] != target_cell.failure_law:
                raise LiveValidationAnalysisError("prediction/test law mismatch")
            if int(prediction_row["repetition"]) != target_cell.repetition:
                raise LiveValidationAnalysisError("prediction/test repetition mismatch")
            raw_prediction = prediction_row["prediction"]
            if raw_prediction == "":
                continue
            prediction = float(raw_prediction)
            operation_requests = by_operation[prediction_row["operation"]]
            if not operation_requests:
                continue
            outcomes = np.asarray(
                [request.success for request in operation_requests], dtype=float
            )
            test_rate = float(outcomes.mean())
            brier = float(np.mean((prediction - outcomes) ** 2))
            lower, upper = _block_interval(
                operation_requests, block_length, analysis.confidence_level
            )
            rows.append(
                {
                    "profile": target_cell.profile,
                    "failure_law": target_cell.failure_law,
                    "repetition": target_cell.repetition,
                    "mode": prediction_row["mode"],
                    "scope": prediction_row["scope"],
                    "source_placement": prediction_row["source_placement"],
                    "target_placement": target_cell.placement,
                    "method": prediction_row["method"],
                    "view": view,
                    "block_length_seconds": block_length,
                    "operation": prediction_row["operation"],
                    "prediction": prediction,
                    "test_requests": len(outcomes),
                    "test_successes": int(outcomes.sum()),
                    "test_success_fraction": test_rate,
                    "brier_score": brier,
                    "signed_prediction_error": prediction - test_rate,
                    "absolute_prediction_error": abs(prediction - test_rate),
                    "test_block_mean_lower": lower,
                    "test_block_mean_upper": upper,
                    "prediction_in_test_block_interval": lower <= prediction <= upper,
                }
            )
    return rows


def _cell_diagnostic(
    cell: QualifiedCell,
    prepared: PreparedMode,
    fit: ExactFit,
    analysis: LiveAnalysisConfig,
) -> dict[str, Any]:
    observed_counts = [
        sum(tick.observed[index] is not None for tick in prepared.ticks)
        for index in range(len(SIGNALS))
    ]
    complete_paths = sum(
        tick.observed[2] is not None and tick.observed[3] is not None
        for tick in prepared.ticks
    )
    topology_values = list(prepared.topology.values())
    test_transitions = _transition_times(cell.test_health)
    test_unaligned = 0
    test_guarded = 0
    for request in cell.test_requests:
        _, distance = _nearest_tick(request.at, cell.test_health)
        test_unaligned += distance > analysis.health_alignment_tolerance_seconds
        test_guarded += _near_transition(
            request.at,
            test_transitions,
            analysis.transition_guard_seconds_each_side,
        )
    return {
        "profile": cell.profile,
        "placement": cell.placement,
        "failure_law": cell.failure_law,
        "repetition": cell.repetition,
        "mode": prepared.mode.id,
        "calibration_requests": sum(
            len(values) for values in prepared.calibration_by_operation.values()
        ),
        "calibration_unaligned_requests": prepared.unaligned_calibration,
        "calibration_transition_guarded_requests": prepared.guarded_calibration,
        "test_requests": len(cell.test_requests),
        "test_unaligned_requests": test_unaligned,
        "test_transition_guarded_requests": test_guarded,
        "health_ticks": len(prepared.ticks),
        "observed_ha": observed_counts[0],
        "observed_hb": observed_counts[1],
        "observed_pa": observed_counts[2],
        "observed_pb": observed_counts[3],
        "complete_path_ticks": complete_paths,
        "health_signal_contradictions": prepared.health_signal_contradictions,
        "retained_traces": prepared.retained_traces,
        "topology_operations_confirmed": sum(
            item.status == "confirmed" for item in topology_values
        ),
        "topology_operations_unsupported": sum(
            item.status != "confirmed" for item in topology_values
        ),
        "replica_a_trace_assignments": sum(
            item.replica_a_assignments for item in topology_values
        ),
        "replica_b_trace_assignments": sum(
            item.replica_b_assignments for item in topology_values
        ),
        "optimizer_finite_starts": len(fit.candidates),
        "optimizer_converged_starts": sum(item.converged for item in fit.candidates),
        "best_nll": fit.best.nll if fit.best is not None else "",
        "b3_fit_status": fit.status,
        "current_target_identified": fit.current_identified,
        "transfer_target_identified": fit.transfer_identified,
        "current_multistart_range": (
            fit.current_prediction_range
            if math.isfinite(fit.current_prediction_range)
            else ""
        ),
        "transfer_multistart_range": (
            fit.transfer_prediction_range
            if math.isfinite(fit.transfer_prediction_range)
            else ""
        ),
    }


def _cell_metric_rows(
    scores: list[dict[str, Any]],
    operation_counts: dict[str, int],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in scores:
        key = (
            row["profile"],
            row["failure_law"],
            int(row["repetition"]),
            row["mode"],
            row["scope"],
            row["source_placement"],
            row["target_placement"],
            row["method"],
            row["view"],
        )
        groups[key].append(row)
    result = []
    for key, rows in groups.items():
        profile = str(key[0])
        if len(rows) != operation_counts[profile]:
            continue
        result.append(
            {
                "profile": profile,
                "failure_law": key[1],
                "repetition": key[2],
                "mode": key[3],
                "scope": key[4],
                "source_placement": key[5],
                "target_placement": key[6],
                "method": key[7],
                "view": key[8],
                "brier_score": float(np.mean([float(row["brier_score"]) for row in rows])),
                "signed_prediction_error": float(
                    np.mean([float(row["signed_prediction_error"]) for row in rows])
                ),
                "absolute_prediction_error": float(
                    np.mean([float(row["absolute_prediction_error"]) for row in rows])
                ),
                "compatibility": float(
                    np.mean(
                        [bool(row["prediction_in_test_block_interval"]) for row in rows]
                    )
                ),
            }
        )
    return result


def _stratified_inference(
    values_by_stratum: dict[tuple[Any, ...], list[float]],
    confidence_level: float,
) -> dict[str, float]:
    nonempty = {key: values for key, values in values_by_stratum.items() if values}
    if not nonempty:
        return {
            "estimate": math.nan,
            "standard_error": math.nan,
            "degrees_of_freedom": math.nan,
            "confidence_lower": math.nan,
            "confidence_upper": math.nan,
            "two_sided_p_value": math.nan,
        }
    stratum_means = [float(np.mean(values)) for values in nonempty.values()]
    estimate = float(np.mean(stratum_means))
    strata = len(nonempty)
    variance_terms = []
    denominator_terms = []
    for values in nonempty.values():
        if len(values) < 2:
            continue
        variance = float(np.var(values, ddof=1)) / len(values) / strata**2
        variance_terms.append(variance)
        denominator_terms.append(variance**2 / (len(values) - 1))
    total_variance = sum(variance_terms)
    standard_error = math.sqrt(total_variance)
    degrees = (
        total_variance**2 / sum(denominator_terms)
        if denominator_terms and sum(denominator_terms) > 0
        else math.inf
    )
    critical = float(t.ppf(0.5 + confidence_level / 2, degrees))
    if standard_error > 0:
        statistic = estimate / standard_error
        p_value = 2 * float(t.sf(abs(statistic), degrees))
    else:
        p_value = 1.0 if estimate == 0 else 0.0
    return {
        "estimate": estimate,
        "standard_error": standard_error,
        "degrees_of_freedom": degrees,
        "confidence_lower": estimate - critical * standard_error,
        "confidence_upper": estimate + critical * standard_error,
        "two_sided_p_value": p_value,
    }


def _contrast_rows(
    cell_metrics: list[dict[str, Any]],
    config: FrozenLiveValidationConfig,
    scope: str,
) -> list[dict[str, Any]]:
    analysis = config.analysis
    lookup = {
        (
            row["profile"],
            row["failure_law"],
            row["repetition"],
            row["mode"],
            row["scope"],
            row["source_placement"],
            row["target_placement"],
            row["view"],
            row["method"],
        ): row
        for row in cell_metrics
        if row["scope"] == scope
    }
    combinations = sorted(
        {
            (row["mode"], row["view"])
            for row in cell_metrics
            if row["scope"] == scope
        }
    )
    result = []
    for mode, view in combinations:
        for comparator in ("B0", "B1", "B2", "B3", "B4"):
            values_by_stratum: dict[tuple[Any, ...], list[float]] = defaultdict(list)
            for row in cell_metrics:
                if (
                    row["scope"] != scope
                    or row["mode"] != mode
                    or row["view"] != view
                    or row["method"] != "proposed"
                ):
                    continue
                key = (
                    row["profile"],
                    row["failure_law"],
                    row["repetition"],
                    row["mode"],
                    row["scope"],
                    row["source_placement"],
                    row["target_placement"],
                    row["view"],
                    comparator,
                )
                paired = lookup.get(key)
                if paired is None:
                    continue
                stratum = (
                    (row["profile"], row["target_placement"], row["failure_law"])
                    if scope == "current"
                    else (row["profile"], row["failure_law"])
                )
                values_by_stratum[stratum].append(
                    float(row["brier_score"]) - float(paired["brier_score"])
                )
            inference = _stratified_inference(
                values_by_stratum, analysis.confidence_level
            )
            expected_strata = 16 if scope == "current" else 8
            expected_campaigns = expected_strata * config.repetitions
            campaigns = sum(map(len, values_by_stratum.values()))
            complete = (
                len(values_by_stratum) == expected_strata
                and campaigns == expected_campaigns
                and all(len(values) == config.repetitions for values in values_by_stratum.values())
            )
            primary = (
                scope == "current"
                and mode == analysis.primary_mode
                and view == analysis.primary_view
                and comparator == "B2"
            )
            result.append(
                {
                    "scope": scope,
                    "mode": mode,
                    "view": view,
                    "metric": "brier_score",
                    "contrast": f"proposed_minus_{comparator}",
                    "campaigns": campaigns,
                    "strata": len(values_by_stratum),
                    **{
                        key: value if math.isfinite(value) else ""
                        for key, value in inference.items()
                    },
                    "holm_adjusted_p_value": "",
                    "complete": complete,
                    "primary": primary,
                }
            )
    return result


def _apply_holm(rows: list[dict[str, Any]]) -> None:
    secondary = [
        row
        for row in rows
        if not row["primary"] and row["two_sided_p_value"] != ""
    ]
    ordered = sorted(secondary, key=lambda row: float(row["two_sided_p_value"]))
    running = 0.0
    total = len(ordered)
    for index, row in enumerate(ordered):
        adjusted = min(1.0, (total - index) * float(row["two_sided_p_value"]))
        running = max(running, adjusted)
        row["holm_adjusted_p_value"] = running


def _summary_rows(cell_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in cell_metrics:
        groups[(row["scope"], row["mode"], row["view"], row["method"])].append(row)
    return [
        {
            "scope": key[0],
            "mode": key[1],
            "view": key[2],
            "method": key[3],
            "complete_campaigns": len(rows),
            "mean_brier_score": float(np.mean([row["brier_score"] for row in rows])),
            "mean_signed_prediction_error": float(
                np.mean([row["signed_prediction_error"] for row in rows])
            ),
            "mean_absolute_prediction_error": float(
                np.mean([row["absolute_prediction_error"] for row in rows])
            ),
            "prediction_interval_compatibility_fraction": float(
                np.mean([row["compatibility"] for row in rows])
            ),
        }
        for key, rows in sorted(groups.items())
    ]


def _expected_identities(
    config: FrozenLiveValidationConfig, scope: str
) -> set[tuple[str, str, str, int]]:
    all_identities = {
        (
            row["profile"],
            row["placement"],
            row["law"],
            int(row["repetition"]),
        )
        for row in frozen_live_matrix(config)
    }
    if scope == "full":
        return all_identities
    if scope == "preflight":
        return {
            identity
            for identity in all_identities
            if identity[2] == "NCD" and identity[3] == 0
        }
    raise LiveValidationAnalysisError("scope must be preflight or full")


def analyze_live_validation(
    config: FrozenLiveValidationConfig,
    input_root: str | Path,
    output_directory: str | Path,
    scope: str,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise LiveValidationAnalysisError(
            "M7 qualified-evidence analysis may run only in GitHub Actions"
        )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    cells = discover_qualified_cells(input_root)
    expected = _expected_identities(config, scope)
    observed = {cell.identity for cell in cells}
    cell_lookup = {cell.identity: cell for cell in cells}

    prediction_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    prepared_by_cell_mode: dict[tuple[Any, ...], PreparedMode] = {}
    fit_by_cell_mode: dict[tuple[Any, ...], ExactFit] = {}
    for cell in cells:
        for mode in config.analysis.modes:
            prepared = prepare_mode(cell, mode, config.analysis)
            fit = fit_exact_model(cell, prepared, config.analysis)
            key = (*cell.identity, mode.id)
            prepared_by_cell_mode[key] = prepared
            fit_by_cell_mode[key] = fit
            prediction_rows.extend(
                predict_cell(cell, prepared, fit, config.analysis, "current")
            )
            if cell.placement == config.analysis.source_placement:
                prediction_rows.extend(
                    predict_cell(cell, prepared, fit, config.analysis, "transfer")
                )
            diagnostic_rows.append(
                _cell_diagnostic(cell, prepared, fit, config.analysis)
            )

    score_rows: list[dict[str, Any]] = []
    predictions_by_target: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in prediction_rows:
        target_identity = (
            row["profile"],
            row["target_placement"],
            row["failure_law"],
            int(row["repetition"]),
        )
        predictions_by_target[target_identity].append(row)
    for target_identity, predictions in predictions_by_target.items():
        target = cell_lookup.get(target_identity)
        if target is not None:
            score_rows.extend(
                score_predictions(predictions, target, config.analysis)
            )

    operation_counts = {
        profile: len(operations)
        for profile, operations in config.analysis.operations.items()
    }
    cell_metrics = _cell_metric_rows(score_rows, operation_counts)
    contrast_rows = _contrast_rows(cell_metrics, config, "current")
    contrast_rows.extend(_contrast_rows(cell_metrics, config, "transfer"))
    _apply_holm(contrast_rows)
    summary_rows = _summary_rows(cell_metrics)

    _write_csv(output / "predictions.csv", PREDICTION_FIELDS, prediction_rows)
    _write_csv(output / "scores.csv", SCORE_FIELDS, score_rows)
    _write_csv(output / "cell-diagnostics.csv", DIAGNOSTIC_FIELDS, diagnostic_rows)
    _write_csv(output / "contrasts.csv", CONTRAST_FIELDS, contrast_rows)
    _write_csv(output / "summary.csv", SUMMARY_FIELDS, summary_rows)

    source_runs = {
        str(
            cell.boundary.get("source_provenance", {})
            .get("environment", {})
            .get("github", {})
            .get("GITHUB_RUN_ID", "")
        )
        for cell in cells
    } - {""}
    source_commits = {
        str(
            cell.boundary.get("source_provenance", {})
            .get("environment", {})
            .get("git", {})
            .get("commit", "")
        )
        for cell in cells
    } - {""}
    declared_run = os.environ.get("M7_SOURCE_RUN_ID", "")
    proposed_lookup = {
        (
            row["profile"], row["failure_law"], row["repetition"], row["mode"],
            row["scope"], row["source_placement"], row["target_placement"], row["operation"],
        ): row
        for row in prediction_rows
        if row["method"] == "proposed" and row["prediction"] != ""
    }
    b3_lookup = {
        (
            row["profile"], row["failure_law"], row["repetition"], row["mode"],
            row["scope"], row["source_placement"], row["target_placement"], row["operation"],
        ): row
        for row in prediction_rows
        if row["method"] == "B3" and row["prediction"] != ""
    }
    agreement_mismatches = sum(
        key not in b3_lookup
        or abs(float(row["prediction"]) - float(b3_lookup[key]["prediction"])) > 1e-12
        for key, row in proposed_lookup.items()
    )
    quality = {
        "source_cell_count_mismatches": int(len(cells) != len(expected)),
        "missing_expected_cells": len(expected - observed),
        "unexpected_cells": len(observed - expected),
        "unusable_boundaries": sum(cell.boundary.get("usable") is not True for cell in cells),
        "source_run_count_mismatches": int(len(source_runs) != 1),
        "source_commit_count_mismatches": int(len(source_commits) != 1),
        "declared_source_run_mismatches": int(
            bool(declared_run) and source_runs != {declared_run}
        ),
        "proposed_b3_prediction_mismatches": agreement_mismatches,
        "nonfinite_emitted_predictions": sum(
            row["prediction"] != "" and not math.isfinite(float(row["prediction"]))
            for row in prediction_rows
        ),
    }
    substantive = {
        "fit_status_counts": dict(Counter(row["b3_fit_status"] for row in diagnostic_rows)),
        "topology_unsupported_cell_modes": sum(
            int(row["topology_operations_unsupported"]) > 0 for row in diagnostic_rows
        ),
        "proposed_current_abstentions": sum(
            row["method"] == "proposed"
            and row["scope"] == "current"
            and row["prediction"] == ""
            for row in prediction_rows
        ),
        "proposed_transfer_abstentions": sum(
            row["method"] == "proposed"
            and row["scope"] == "transfer"
            and row["prediction"] == ""
            for row in prediction_rows
        ),
        "b4_transfer_abstentions": sum(
            row["method"] == "B4"
            and row["scope"] == "transfer"
            and row["prediction"] == ""
            for row in prediction_rows
        ),
        "complete_primary_contrast": any(
            row["primary"] and row["complete"] for row in contrast_rows
        ),
    }
    primary = next((row for row in contrast_rows if row["primary"]), None)
    manifest = {
        "schema_version": 1,
        "kind": "frozen_live_validation_analysis",
        "experiment_id": config.id,
        "main_effectiveness": True,
        "analysis_frozen": True,
        "scope": scope,
        "source_workflow_run_ids": sorted(source_runs),
        "source_commits": sorted(source_commits),
        "expected_cells": len(expected),
        "observed_cells": len(cells),
        "primary_estimand": (
            "equal-operation, equal-stratum campaign-level proposed-minus-B2 "
            "Brier score under sampled_mixed stable evaluation"
        ),
        "primary_result": primary,
        "quality": quality,
        "substantive_outcomes_not_acceptance_gates": substantive,
        "row_counts": {
            "predictions": len(prediction_rows),
            "scores": len(score_rows),
            "cell_diagnostics": len(diagnostic_rows),
            "contrasts": len(contrast_rows),
            "summary": len(summary_rows),
        },
        "files": {
            "config_sha256": file_sha256(config.path),
            "predictions_sha256": file_sha256(output / "predictions.csv"),
            "scores_sha256": file_sha256(output / "scores.csv"),
            "cell_diagnostics_sha256": file_sha256(output / "cell-diagnostics.csv"),
            "contrasts_sha256": file_sha256(output / "contrasts.csv"),
            "summary_sha256": file_sha256(output / "summary.csv"),
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise LiveValidationAnalysisError(f"M7 analysis acceptance failures: {failures}")
    return manifest
