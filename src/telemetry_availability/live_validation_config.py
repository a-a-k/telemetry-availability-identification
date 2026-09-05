from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence
from .live_stochastic_config import StochasticPilotConfig, load_stochastic_pilot_config

EXPECTED_METHODS = ("B0", "B1", "B2", "B3", "proposed", "B4")
EXPECTED_MODES = ("full", "sampled_mixed", "no_joint_health", "trace_only")
HEALTH_POLICIES = {"joint", "staggered", "none"}


@dataclass(frozen=True)
class LiveObservationMode:
    id: str
    health_policy: str
    health_keep_probability: float
    trace_keep_probability: float


@dataclass(frozen=True)
class LiveOperationSpec:
    id: str
    requires_target_group: bool
    specification_source: str


@dataclass(frozen=True)
class LiveAnalysisConfig:
    seed: int
    modes: tuple[LiveObservationMode, ...]
    methods: tuple[str, ...]
    primary_mode: str
    primary_contrast: str
    primary_metric: str
    primary_view: str
    aggregation_unit: str
    stratum_weighting: str
    operation_weighting: str
    confidence_level: float
    secondary_multiplicity: str
    time_bin_seconds: int
    health_alignment_tolerance_seconds: float
    transition_guard_seconds_each_side: int
    block_length_seconds: int
    sensitivity_block_length_seconds: int
    baseline_beta_prior_alpha: float
    baseline_beta_prior_beta: float
    optimizer_starts: int
    optimizer_max_iterations: int
    parameter_epsilon: float
    numerical_probability_floor: float
    rank_tolerance: float
    target_gradient_tolerance: float
    multistart_prediction_tolerance: float
    minimum_signal_observations: int
    minimum_pattern_observations: int
    minimum_operation_requests: int
    minimum_trace_operation_support: int
    required_target_trace_fraction: float
    maximum_nontarget_trace_fraction: float
    minimum_replica_trace_assignments: int
    source_placement: str
    target_placement: str
    homogeneous_new_domain_assumption: bool
    operations: dict[str, tuple[LiveOperationSpec, ...]]


@dataclass(frozen=True)
class FrozenLiveValidationConfig:
    id: str
    main_effectiveness: bool
    stochastic: StochasticPilotConfig
    stochastic_config_path: Path
    source_pilot_run_id: str
    source_pilot_commit: str
    source_pilot_recommendation_sha256: str
    resource_recovery_run_id: str
    resource_recovery_commit: str
    resource_recommendation_sha256: str
    selected_design: dict[str, Any]
    selected_design_sha256: str
    transition_guard_seconds_each_side: int
    repetitions: int
    request_namespace: str
    preflight_base_seed: int
    preflight_request_namespace: str
    analysis: LiveAnalysisConfig
    path: Path

    @property
    def expected_cells(self) -> int:
        return (
            len(self.stochastic.placement.runtime.profiles)
            * len(self.stochastic.placement.placements)
            * len(self.stochastic.laws)
            * self.repetitions
        )


def _positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be an integer") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _positive_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be numeric") from error
    if not result > 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _open_fraction(value: Any, label: str) -> float:
    result = _positive_float(value, label)
    if not result < 1:
        raise ConfigError(f"{label} must lie in (0, 1)")
    return result


def _closed_fraction(value: Any, label: str) -> float:
    result = _positive_float(value, label)
    if not result <= 1:
        raise ConfigError(f"{label} must lie in (0, 1]")
    return result


def _digest(value: Any, label: str, length: int) -> str:
    result = str(value)
    if len(result) != length or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise ConfigError(f"{label} must be a lowercase hexadecimal digest")
    return result


def _run_id(value: Any, label: str) -> str:
    result = str(value)
    if not result.isdigit():
        raise ConfigError(f"{label} must be numeric")
    return result


def _sibling_path(config_path: Path, value: Any, label: str) -> Path:
    relative = Path(str(value))
    if relative.is_absolute() or ".." in relative.parts or not relative.name:
        raise ConfigError(f"{label} must be a safe relative path")
    resolved = (config_path.parent / relative).resolve()
    if resolved.parent != config_path.parent:
        raise ConfigError(f"{label} must remain in the configuration directory")
    return resolved


def _sha256(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _expected_selected_design(
    stochastic: StochasticPilotConfig,
    selected: dict[str, Any],
) -> dict[str, Any]:
    return {
        "period_seconds": int(selected["period_seconds"]),
        "repetitions": int(selected["repetitions"]),
        "transition_guard_seconds_each_side": int(
            selected["transition_guard_seconds_each_side"]
        ),
        "request_rate_per_second": stochastic.request_rate_per_second,
        "main_base_seed": stochastic.main_base_seed,
        "laws": {
            name: list(mechanisms) for name, mechanisms in stochastic.laws.items()
        },
        "placements": stochastic.placement.placements,
        "renewal_processes": {
            name: asdict(process)
            for name, process in stochastic.renewal_processes.items()
        },
    }


def _analysis_config(
    raw_analysis: dict[str, Any],
    pilot: StochasticPilotConfig,
    selected_guard: int,
) -> LiveAnalysisConfig:
    modes = []
    for raw_mode in _sequence(
        raw_analysis.get("observation_modes"), "observation modes"
    ):
        data = _mapping(raw_mode, "observation mode")
        health_policy = str(data.get("health_policy", ""))
        if health_policy not in HEALTH_POLICIES:
            raise ConfigError(f"health_policy must be one of {sorted(HEALTH_POLICIES)}")
        modes.append(
            LiveObservationMode(
                id=str(data.get("id", "")),
                health_policy=health_policy,
                health_keep_probability=_closed_fraction(
                    data.get("health_keep_probability"),
                    "health_keep_probability",
                ),
                trace_keep_probability=_closed_fraction(
                    data.get("trace_keep_probability"),
                    "trace_keep_probability",
                ),
            )
        )
    if tuple(mode.id for mode in modes) != EXPECTED_MODES:
        raise ConfigError(f"observation modes must equal the frozen order {EXPECTED_MODES}")
    expected_mode_contracts = {
        "full": ("joint", 1.0, 1.0),
        "sampled_mixed": ("joint", 0.4, 0.7),
        "no_joint_health": ("staggered", 1.0, 0.7),
        "trace_only": ("none", 1.0, 0.7),
    }
    for mode in modes:
        if (
            mode.health_policy,
            mode.health_keep_probability,
            mode.trace_keep_probability,
        ) != expected_mode_contracts[mode.id]:
            raise ConfigError(f"observation mode {mode.id!r} violates its frozen mask")

    methods = tuple(
        str(value) for value in _sequence(raw_analysis.get("methods"), "methods")
    )
    if methods != EXPECTED_METHODS:
        raise ConfigError(f"methods must equal the frozen order {EXPECTED_METHODS}")

    primary = _mapping(raw_analysis.get("primary"), "primary analysis")
    temporal = _mapping(raw_analysis.get("temporal"), "temporal analysis")
    baseline = _mapping(raw_analysis.get("baseline"), "baseline calibration")
    optimizer = _mapping(raw_analysis.get("optimizer"), "optimizer")
    identification = _mapping(raw_analysis.get("identification"), "identification")
    topology = _mapping(raw_analysis.get("topology"), "topology")
    transfer = _mapping(raw_analysis.get("transfer"), "transfer")

    raw_operations = _mapping(raw_analysis.get("operations"), "operations")
    expected_profiles = {profile.id for profile in pilot.placement.runtime.profiles}
    if set(raw_operations) != expected_profiles:
        raise ConfigError("analysis operations must cover every runtime profile")
    operations: dict[str, tuple[LiveOperationSpec, ...]] = {}
    runtime_lookup = {
        profile.id: profile for profile in pilot.placement.runtime.profiles
    }
    for profile_id, raw_items in raw_operations.items():
        items = tuple(
            LiveOperationSpec(
                id=str(data.get("id", "")),
                requires_target_group=data.get("requires_target_group") is True,
                specification_source=str(data.get("specification_source", "")),
            )
            for raw in _sequence(raw_items, f"operations for {profile_id}")
            for data in (_mapping(raw, f"operation for {profile_id}"),)
        )
        if any(not item.id or not item.specification_source for item in items):
            raise ConfigError("operation ids and specification sources must be nonempty")
        if len({item.id for item in items}) != len(items):
            raise ConfigError(f"operation ids for {profile_id!r} must be unique")
        if {item.id for item in items} != set(runtime_lookup[profile_id].operations):
            raise ConfigError(
                f"analysis operations do not match runtime profile {profile_id!r}"
            )
        operations[profile_id] = items

    source_placement = str(transfer.get("source_placement", ""))
    target_placement = str(transfer.get("target_placement", ""))
    if {source_placement, target_placement} != set(pilot.placement.placements):
        raise ConfigError("transfer must name the two frozen placements exactly")
    if transfer.get("homogeneous_new_domain_assumption") is not True:
        raise ConfigError("the new-domain transfer assumption must be explicit")
    if tuple(
        str(value)
        for value in _sequence(transfer.get("paired_by"), "transfer paired_by")
    ) != ("application", "failure_law", "repetition"):
        raise ConfigError("transfer pairing must be application/failure_law/repetition")
    if transfer.get("target_calibration_is_forbidden") is not True:
        raise ConfigError("transfer must forbid target-placement calibration")
    if baseline.get("estimator") != "beta_posterior_mean":
        raise ConfigError("baseline estimator must be beta_posterior_mean")
    if optimizer.get("algorithm") != "bounded_multistart_lbfgsb":
        raise ConfigError("optimizer algorithm must be bounded_multistart_lbfgsb")
    if tuple(
        str(value)
        for value in _sequence(topology.get("discovery_periods"), "discovery periods")
    ) != ("baseline", "calibration"):
        raise ConfigError("topology discovery periods must be baseline/calibration")
    if topology.get("absent_spans_are_not_negative_states") is not True:
        raise ConfigError("missing spans must not be interpreted as negative states")

    config = LiveAnalysisConfig(
        seed=_positive_int(raw_analysis.get("seed"), "analysis seed"),
        modes=tuple(modes),
        methods=methods,
        primary_mode=str(primary.get("mode", "")),
        primary_contrast=str(primary.get("contrast", "")),
        primary_metric=str(primary.get("metric", "")),
        primary_view=str(primary.get("view", "")),
        aggregation_unit=str(primary.get("aggregation_unit", "")),
        stratum_weighting=str(primary.get("stratum_weighting", "")),
        operation_weighting=str(primary.get("operation_weighting", "")),
        confidence_level=_open_fraction(
            raw_analysis.get("confidence_level"), "confidence_level"
        ),
        secondary_multiplicity=str(raw_analysis.get("secondary_multiplicity", "")),
        time_bin_seconds=_positive_int(
            temporal.get("time_bin_seconds"), "time_bin_seconds"
        ),
        health_alignment_tolerance_seconds=_positive_float(
            temporal.get("health_alignment_tolerance_seconds"),
            "health_alignment_tolerance_seconds",
        ),
        transition_guard_seconds_each_side=_positive_int(
            temporal.get("transition_guard_seconds_each_side"),
            "analysis transition guard",
        ),
        block_length_seconds=_positive_int(
            temporal.get("block_length_seconds"), "block_length_seconds"
        ),
        sensitivity_block_length_seconds=_positive_int(
            temporal.get("sensitivity_block_length_seconds"),
            "sensitivity_block_length_seconds",
        ),
        baseline_beta_prior_alpha=_positive_float(
            baseline.get("beta_prior_alpha"), "baseline beta_prior_alpha"
        ),
        baseline_beta_prior_beta=_positive_float(
            baseline.get("beta_prior_beta"), "baseline beta_prior_beta"
        ),
        optimizer_starts=_positive_int(optimizer.get("starts"), "optimizer starts"),
        optimizer_max_iterations=_positive_int(
            optimizer.get("max_iterations"), "optimizer max_iterations"
        ),
        parameter_epsilon=_open_fraction(
            optimizer.get("parameter_epsilon"), "parameter_epsilon"
        ),
        numerical_probability_floor=_open_fraction(
            optimizer.get("numerical_probability_floor"),
            "numerical_probability_floor",
        ),
        rank_tolerance=_open_fraction(
            identification.get("rank_tolerance"), "rank_tolerance"
        ),
        target_gradient_tolerance=_open_fraction(
            identification.get("target_gradient_tolerance"),
            "target_gradient_tolerance",
        ),
        multistart_prediction_tolerance=_open_fraction(
            identification.get("multistart_prediction_tolerance"),
            "multistart_prediction_tolerance",
        ),
        minimum_signal_observations=_positive_int(
            identification.get("minimum_signal_observations"),
            "minimum_signal_observations",
        ),
        minimum_pattern_observations=_positive_int(
            identification.get("minimum_pattern_observations"),
            "minimum_pattern_observations",
        ),
        minimum_operation_requests=_positive_int(
            identification.get("minimum_operation_requests"),
            "minimum_operation_requests",
        ),
        minimum_trace_operation_support=_positive_int(
            topology.get("minimum_operation_support"),
            "minimum trace operation support",
        ),
        required_target_trace_fraction=_closed_fraction(
            topology.get("required_target_fraction"),
            "required_target_trace_fraction",
        ),
        maximum_nontarget_trace_fraction=_open_fraction(
            topology.get("maximum_nontarget_fraction"),
            "maximum_nontarget_trace_fraction",
        ),
        minimum_replica_trace_assignments=_positive_int(
            topology.get("minimum_replica_assignments"),
            "minimum_replica_trace_assignments",
        ),
        source_placement=source_placement,
        target_placement=target_placement,
        homogeneous_new_domain_assumption=True,
        operations=operations,
    )
    frozen_primary = (
        config.primary_mode,
        config.primary_contrast,
        config.primary_metric,
        config.primary_view,
        config.aggregation_unit,
        config.stratum_weighting,
        config.operation_weighting,
    )
    if frozen_primary != (
        "sampled_mixed",
        "proposed_minus_B2",
        "brier_score",
        "stable",
        "campaign",
        "equal",
        "equal",
    ):
        raise ConfigError("primary analysis must equal the frozen macro Brier contrast")
    if config.secondary_multiplicity != "holm":
        raise ConfigError("secondary_multiplicity must be holm")
    if config.time_bin_seconds != 1:
        raise ConfigError("time_bin_seconds must equal the one-second health cadence")
    if config.transition_guard_seconds_each_side != selected_guard:
        raise ConfigError("analysis transition guard must match the selected design")
    if config.sensitivity_block_length_seconds != 2 * config.block_length_seconds:
        raise ConfigError("sensitivity block length must be twice the frozen block")
    numeric_freeze = {
        "confidence_level": (config.confidence_level, 0.95),
        "health_alignment_tolerance_seconds": (
            config.health_alignment_tolerance_seconds,
            1.25,
        ),
        "block_length_seconds": (float(config.block_length_seconds), 23.0),
        "baseline_beta_prior_alpha": (config.baseline_beta_prior_alpha, 0.5),
        "baseline_beta_prior_beta": (config.baseline_beta_prior_beta, 0.5),
        "optimizer_starts": (float(config.optimizer_starts), 8.0),
        "optimizer_max_iterations": (
            float(config.optimizer_max_iterations),
            1000.0,
        ),
        "parameter_epsilon": (config.parameter_epsilon, 1e-5),
        "numerical_probability_floor": (
            config.numerical_probability_floor,
            1e-12,
        ),
        "rank_tolerance": (config.rank_tolerance, 1e-7),
        "target_gradient_tolerance": (config.target_gradient_tolerance, 1e-6),
        "multistart_prediction_tolerance": (
            config.multistart_prediction_tolerance,
            1e-4,
        ),
        "minimum_signal_observations": (
            float(config.minimum_signal_observations),
            20.0,
        ),
        "minimum_pattern_observations": (
            float(config.minimum_pattern_observations),
            10.0,
        ),
        "minimum_operation_requests": (
            float(config.minimum_operation_requests),
            20.0,
        ),
        "minimum_trace_operation_support": (
            float(config.minimum_trace_operation_support),
            20.0,
        ),
        "required_target_trace_fraction": (
            config.required_target_trace_fraction,
            0.8,
        ),
        "maximum_nontarget_trace_fraction": (
            config.maximum_nontarget_trace_fraction,
            0.05,
        ),
        "minimum_replica_trace_assignments": (
            float(config.minimum_replica_trace_assignments),
            5.0,
        ),
    }
    changed = [
        name
        for name, (actual, expected) in numeric_freeze.items()
        if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15)
    ]
    if changed:
        raise ConfigError(f"analysis constants violate the frozen values: {changed}")
    return config


def load_frozen_live_validation_config(
    path: str | Path,
) -> FrozenLiveValidationConfig:
    config_path = Path(path).resolve()
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "frozen live-validation configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("frozen live-validation schema_version must equal 1")
    if root.get("main_effectiveness") is not True:
        raise ConfigError("live validation must explicitly set main_effectiveness")

    stochastic_path = _sibling_path(
        config_path,
        root.get("stochastic_pilot_config"),
        "stochastic_pilot_config",
    )
    pilot = load_stochastic_pilot_config(stochastic_path)
    selected = dict(_mapping(root.get("selected_design"), "selected design"))
    expected_selected = _expected_selected_design(pilot, selected)
    if selected != expected_selected:
        raise ConfigError(
            "selected_design does not exactly match the stochastic pilot contract"
        )
    selected_hash = _digest(
        root.get("selected_design_sha256"), "selected_design_sha256", 64
    )
    if selected_hash != _sha256(selected):
        raise ConfigError("selected_design_sha256 does not match selected_design")
    period_seconds = _positive_int(selected["period_seconds"], "period_seconds")
    repetitions = _positive_int(selected["repetitions"], "repetitions")
    guard = _positive_int(
        selected["transition_guard_seconds_each_side"],
        "transition_guard_seconds_each_side",
    )
    if period_seconds not in pilot.design_selection.candidate_period_seconds:
        raise ConfigError("selected period is not an admitted pilot candidate")
    if repetitions not in pilot.design_selection.candidate_main_repetitions:
        raise ConfigError("selected repetitions are not an admitted pilot candidate")
    if guard not in pilot.design_selection.transition_guard_candidates_seconds:
        raise ConfigError("selected transition guard is not an admitted candidate")

    analysis = _analysis_config(
        _mapping(root.get("analysis"), "live analysis"), pilot, guard
    )
    if analysis.seed in {pilot.pilot_base_seed, pilot.main_base_seed}:
        raise ConfigError("analysis and acquisition seeds must differ")

    main_stochastic = replace(
        pilot,
        id=str(root.get("id", "")),
        pilot_only=False,
        pilot_repetitions=repetitions,
        period_seconds=period_seconds,
        pilot_base_seed=pilot.main_base_seed,
    )
    if not main_stochastic.id:
        raise ConfigError("live validation id must be nonempty")
    request_namespace = str(root.get("request_namespace", ""))
    if not request_namespace or request_namespace == "m7c":
        raise ConfigError("main request_namespace must be nonempty and distinct")
    preflight_namespace = str(root.get("preflight_request_namespace", ""))
    if not preflight_namespace or preflight_namespace in {"m7c", request_namespace}:
        raise ConfigError("preflight request namespace must be nonempty and distinct")
    preflight_seed = _positive_int(
        root.get("preflight_base_seed"), "preflight_base_seed"
    )
    if preflight_seed in {
        pilot.pilot_base_seed,
        pilot.main_base_seed,
        analysis.seed,
    }:
        raise ConfigError("preflight, pilot, main, and analysis seeds must differ")

    return FrozenLiveValidationConfig(
        id=main_stochastic.id,
        main_effectiveness=True,
        stochastic=main_stochastic,
        stochastic_config_path=stochastic_path,
        source_pilot_run_id=_run_id(
            root.get("source_pilot_run_id"), "source_pilot_run_id"
        ),
        source_pilot_commit=_digest(
            root.get("source_pilot_commit"), "source_pilot_commit", 40
        ),
        source_pilot_recommendation_sha256=_digest(
            root.get("source_pilot_recommendation_sha256"),
            "source_pilot_recommendation_sha256",
            64,
        ),
        resource_recovery_run_id=_run_id(
            root.get("resource_recovery_run_id"), "resource_recovery_run_id"
        ),
        resource_recovery_commit=_digest(
            root.get("resource_recovery_commit"), "resource_recovery_commit", 40
        ),
        resource_recommendation_sha256=_digest(
            root.get("resource_recommendation_sha256"),
            "resource_recommendation_sha256",
            64,
        ),
        selected_design=selected,
        selected_design_sha256=selected_hash,
        transition_guard_seconds_each_side=guard,
        repetitions=repetitions,
        request_namespace=request_namespace,
        preflight_base_seed=preflight_seed,
        preflight_request_namespace=preflight_namespace,
        analysis=analysis,
        path=config_path,
    )
