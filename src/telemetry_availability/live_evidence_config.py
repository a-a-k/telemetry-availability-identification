from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, _mapping, _sequence

TRACE_FORMATS = {"jaeger_json_v1", "otlp_jsonl_v1"}


@dataclass(frozen=True)
class EvidenceProfile:
    id: str
    trace_format: str
    raw_telemetry_file: str
    target_service: str
    replica_attribute: str
    replica_values: dict[str, str]


@dataclass(frozen=True)
class EvidenceBoundaryConfig:
    id: str
    diagnostic_only: bool
    source_experiment_id: str
    expected_source_cells: int
    learner_period: str
    minimum_trace_link_fraction: float
    minimum_replica_assignments_per_replica: int
    profiles: tuple[EvidenceProfile, ...]
    allowed_source_files: tuple[str, ...]
    privileged_source_files: tuple[str, ...]
    denied_learner_field_tokens: tuple[str, ...]
    path: Path

    def profile(self, profile_id: str) -> EvidenceProfile:
        selected = next((item for item in self.profiles if item.id == profile_id), None)
        if selected is None:
            raise ConfigError(f"unknown evidence profile {profile_id!r}")
        return selected


def _positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be an integer") from error
    if result <= 0:
        raise ConfigError(f"{label} must be positive")
    return result


def _closed_fraction(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"{label} must be numeric") from error
    if not 0 < result <= 1:
        raise ConfigError(f"{label} must lie in (0, 1]")
    return result


def _nonempty_strings(value: Any, label: str) -> tuple[str, ...]:
    result = tuple(str(item) for item in _sequence(value, label))
    if not result or any(not item for item in result):
        raise ConfigError(f"{label} must contain nonempty strings")
    if len(result) != len(set(result)):
        raise ConfigError(f"{label} must be unique")
    return result


def load_evidence_boundary_config(path: str | Path) -> EvidenceBoundaryConfig:
    config_path = Path(path).resolve()
    root = _mapping(
        yaml.safe_load(config_path.read_text(encoding="utf-8")),
        "evidence-boundary configuration",
    )
    if root.get("schema_version") != 1:
        raise ConfigError("evidence-boundary schema_version must equal 1")
    if root.get("diagnostic_only") is not True:
        raise ConfigError("evidence-boundary qualification must be diagnostic_only")

    profiles = []
    for raw_profile in _sequence(root.get("profiles"), "evidence profiles"):
        data = _mapping(raw_profile, "evidence profile")
        trace_format = str(data.get("trace_format", ""))
        if trace_format not in TRACE_FORMATS:
            raise ConfigError(f"trace_format must be one of {sorted(TRACE_FORMATS)}")
        raw_file = str(data.get("raw_telemetry_file", ""))
        if Path(raw_file).name != raw_file or not raw_file:
            raise ConfigError("raw_telemetry_file must be a plain file name")
        replica_values = {
            str(key): str(value)
            for key, value in _mapping(
                data.get("replica_values"), "replica values"
            ).items()
        }
        if set(replica_values.values()) != {"a", "b"}:
            raise ConfigError(
                "every profile must map trace identities to replicas a and b"
            )
        profiles.append(
            EvidenceProfile(
                id=str(data.get("id", "")),
                trace_format=trace_format,
                raw_telemetry_file=raw_file,
                target_service=str(data.get("target_service", "")),
                replica_attribute=str(data.get("replica_attribute", "")),
                replica_values=replica_values,
            )
        )
    if any(
        not profile.id or not profile.target_service or not profile.replica_attribute
        for profile in profiles
    ):
        raise ConfigError(
            "profile identifiers and service/attribute names must be nonempty"
        )
    if len({profile.id for profile in profiles}) != len(profiles):
        raise ConfigError("evidence profile ids must be unique")

    allowed = _nonempty_strings(root.get("allowed_source_files"), "allowed files")
    privileged = _nonempty_strings(
        root.get("privileged_source_files"), "privileged files"
    )
    if set(allowed).intersection(privileged):
        raise ConfigError("allowed and privileged source files must be disjoint")
    denied = _nonempty_strings(
        root.get("denied_learner_field_tokens"), "denied learner field tokens"
    )

    config = EvidenceBoundaryConfig(
        id=str(root.get("id", "")),
        diagnostic_only=True,
        source_experiment_id=str(root.get("source_experiment_id", "")),
        expected_source_cells=_positive_int(
            root.get("expected_source_cells"), "expected_source_cells"
        ),
        learner_period=str(root.get("learner_period", "")),
        minimum_trace_link_fraction=_closed_fraction(
            root.get("minimum_trace_link_fraction"),
            "minimum_trace_link_fraction",
        ),
        minimum_replica_assignments_per_replica=_positive_int(
            root.get("minimum_replica_assignments_per_replica"),
            "minimum_replica_assignments_per_replica",
        ),
        profiles=tuple(profiles),
        allowed_source_files=allowed,
        privileged_source_files=privileged,
        denied_learner_field_tokens=denied,
        path=config_path,
    )
    if not config.id or not config.source_experiment_id:
        raise ConfigError("experiment ids must be nonempty")
    if config.learner_period != "calibration":
        raise ConfigError("learner_period must be calibration")
    raw_files = {profile.raw_telemetry_file for profile in config.profiles}
    if not raw_files.issubset(set(config.allowed_source_files)):
        raise ConfigError("every raw trace file must be explicitly allowed")
    return config
