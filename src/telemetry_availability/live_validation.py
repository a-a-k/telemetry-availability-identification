from __future__ import annotations

from pathlib import Path
from typing import Any

from .live_stochastic_pilot import (
    StochasticCellPurpose,
    _run_stochastic_cell,
)
from .live_validation_config import FrozenLiveValidationConfig
from .provenance import file_sha256


def frozen_live_matrix(config: FrozenLiveValidationConfig) -> list[dict[str, Any]]:
    rows = []
    for profile in config.stochastic.placement.runtime.profiles:
        repository = profile.repository.removeprefix(
            "https://github.com/"
        ).removesuffix(".git")
        for placement in config.stochastic.placement.placements:
            for law in config.stochastic.laws:
                for repetition in range(config.repetitions):
                    rows.append(
                        {
                            "profile": profile.id,
                            "repository": repository,
                            "commit": profile.commit,
                            "compose_file": profile.compose_file,
                            "placement": placement,
                            "law": law,
                            "repetition": repetition,
                        }
                    )
    return rows


def frozen_live_preflight_matrix(
    config: FrozenLiveValidationConfig,
) -> list[dict[str, Any]]:
    return [
        row
        for row in frozen_live_matrix(config)
        if row["law"] == "NCD" and row["repetition"] == 0
    ]


def run_frozen_live_cell(
    config: FrozenLiveValidationConfig,
    profile_id: str,
    placement: str,
    law: str,
    repetition: int,
    checkout_directory: str | Path,
    compose_path: str | Path,
    image_audit_path: str | Path,
    output_directory: str | Path,
    execution_scope: str = "full",
) -> dict[str, Any]:
    if execution_scope not in {"preflight", "full"}:
        raise ValueError("execution_scope must be preflight or full")
    preflight = execution_scope == "preflight"
    if preflight and (law != "NCD" or repetition != 0):
        raise ValueError("preflight is frozen to NCD repetition 0")
    purpose = StochasticCellPurpose(
        kind="frozen_live_validation_campaign",
        manifest_filename="campaign-manifest.json",
        role_fields={
            "pilot_only": preflight,
            "main_effectiveness": not preflight,
            "analysis_frozen": True,
            "preflight_only": preflight,
            "campaign_scope": execution_scope,
            "source_pilot_run_id": config.source_pilot_run_id,
            "source_pilot_commit": config.source_pilot_commit,
            "source_pilot_recommendation_sha256": (
                config.source_pilot_recommendation_sha256
            ),
            "resource_recovery_run_id": config.resource_recovery_run_id,
            "resource_recovery_commit": config.resource_recovery_commit,
            "resource_recommendation_sha256": (
                config.resource_recommendation_sha256
            ),
            "selected_design_sha256": config.selected_design_sha256,
            "live_config_sha256": file_sha256(config.path),
        },
        usability_field=(
            "usable_for_live_preflight"
            if preflight
            else "usable_for_live_analysis"
        ),
        repetition_count=config.repetitions,
        base_seed=(
            config.preflight_base_seed
            if preflight
            else config.stochastic.main_base_seed
        ),
        request_namespace=(
            config.preflight_request_namespace
            if preflight
            else config.request_namespace
        ),
        failure_label="M7 preflight" if preflight else "M7",
    )
    return _run_stochastic_cell(
        config.stochastic,
        profile_id,
        placement,
        law,
        repetition,
        checkout_directory,
        compose_path,
        image_audit_path,
        output_directory,
        purpose,
    )
