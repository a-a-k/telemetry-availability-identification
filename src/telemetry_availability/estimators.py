from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .diagnostics import IdentifiabilityReport
from .model import ConjunctiveModel
from .moments import MomentEstimate, moment_matrix


@dataclass(frozen=True)
class LogMomentFit:
    status: str
    parameter_estimates: dict[str, float | None]
    target_estimates: dict[str, float | None]
    usable_moment_count: int


def fit_log_moments(
    model: ConjunctiveModel,
    estimates: tuple[MomentEstimate, ...],
    report: IdentifiabilityReport,
) -> LogMomentFit:
    usable = tuple(item for item in estimates if item.value > 0.0)
    if not usable:
        return LogMomentFit(
            status="no_positive_moments",
            parameter_estimates={name: None for name in model.factor_ids},
            target_estimates={target.id: None for target in model.targets},
            usable_moment_count=0,
        )

    incidence = moment_matrix(usable, len(model.factors))
    log_moments = np.log(np.asarray([item.value for item in usable], dtype=float))
    weights = np.sqrt(np.asarray([item.observation_count for item in usable], dtype=float))
    weights /= float(np.max(weights))
    weighted_incidence = incidence * weights[:, None]
    weighted_log_moments = log_moments * weights

    log_parameters, _, _, _ = np.linalg.lstsq(
        weighted_incidence,
        weighted_log_moments,
        rcond=None,
    )
    projected = False

    parameter_estimates: dict[str, float | None] = {}
    for index, factor_id in enumerate(model.factor_ids):
        if report.parameter_identifiable[factor_id]:
            log_value = float(log_parameters[index])
            projected = projected or log_value > 0.0
            parameter_estimates[factor_id] = float(np.exp(min(log_value, 0.0)))
        else:
            parameter_estimates[factor_id] = None

    target_estimates: dict[str, float | None] = {}
    for target in model.targets:
        if report.target_identifiable[target.id]:
            log_value = float(model.factor_vector(target.factors) @ log_parameters)
            projected = projected or log_value > 0.0
            target_estimates[target.id] = float(np.exp(min(log_value, 0.0)))
        else:
            target_estimates[target.id] = None

    if report.full_rank:
        status = "full_rank_boundary_projection" if projected else "full_rank"
    else:
        status = (
            "partial_identification_boundary_projection"
            if projected
            else "partial_identification"
        )
    return LogMomentFit(
        status=status,
        parameter_estimates=parameter_estimates,
        target_estimates=target_estimates,
        usable_moment_count=len(usable),
    )
