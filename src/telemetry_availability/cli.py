from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import load_config
from .diagnostics import diagnose_identifiability
from .likelihood_reference import (
    aggregate_likelihood_reference,
    run_likelihood_reference,
)
from .m7_causal_diagnostics import run_m7_causal_diagnostics
from .live_budget_recovery import (
    load_macro_budget_recovery_config,
    recover_macro_budget,
)
from .live_config import load_live_harness_config
from .live_evidence import qualify_evidence_boundary, qualify_evidence_cell
from .live_evidence_config import load_evidence_boundary_config
from .live_fault_campaign import (
    aggregate_live_fault_diagnostics,
    run_live_fault_diagnostic,
)
from .live_fault_config import load_live_fault_config
from .live_harness import (
    aggregate_live_harness,
    select_live_profile,
    verify_live_profile,
)
from .live_ingestion import ingest_live_bundle, write_ingested_bundle
from .live_pilot import (
    aggregate_runtime_pilots,
    pin_compose_files,
    run_runtime_pilot,
)
from .live_pilot_config import load_runtime_pilot_config
from .live_placement_config import load_placement_pilot_config
from .live_placement_pilot import (
    aggregate_placement_pilots,
    prepare_placement_compose,
    run_placement_pilot,
)
from .live_stochastic_config import load_stochastic_pilot_config
from .live_stochastic_pilot import (
    aggregate_stochastic_freeze_pilots,
    run_stochastic_freeze_pilot,
)
from .live_validation import run_frozen_live_cell
from .live_validation_analysis import analyze_live_validation
from .live_validation_config import load_frozen_live_validation_config
from .m7_diagnostic_analysis import run_m7_diagnostic_audit
from .moments import structural_moment_rows
from .palladio_bootstrap import (
    apply_palladio_target_platform_lock,
    audit_palladio_example,
    audit_palladio_product,
    audit_palladio_source,
    load_palladio_bootstrap_config,
)
from .palladio_controls import (
    audit_palladio_capability_source,
    audit_palladio_control_models,
    audit_palladio_control_results,
    generate_palladio_control_models,
    load_palladio_controls_config,
)
from .palladio_mapping import (
    audit_palladio_application_evidence,
    audit_palladio_application_models,
    audit_palladio_application_results,
    generate_palladio_application_models,
    load_palladio_mapping_config,
)
from .palladio_aligned import (
    audit_palladio_aligned_evidence,
    audit_palladio_aligned_results,
    load_palladio_aligned_config,
    prepare_palladio_aligned_models,
    stage_palladio_aligned_learner_input,
)
from .reduction_experiment import (
    aggregate_reduction_experiment,
    run_reduction_experiment,
)
from .runner import aggregate_results, run_experiment
from .stress_config import load_stress_config
from .stress_experiment import aggregate_stress_experiment, run_stress_experiment
from .transfer_config import load_transfer_config
from .transfer_experiment import (
    aggregate_transfer_experiment,
    run_transfer_experiment,
)
from .uncertainty_config import load_uncertainty_config
from .uncertainty_experiment import (
    aggregate_uncertainty_experiment,
    run_uncertainty_experiment,
)


def _comma_separated_positive_integers(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from error
    if not result or any(item <= 0 for item in result):
        raise argparse.ArgumentTypeError("sample sizes must be positive")
    if tuple(sorted(set(result))) != result:
        raise argparse.ArgumentTypeError("sample sizes must be strictly increasing")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taid")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser(
        "validate-config", help="validate a YAML experiment contract"
    )
    validate.add_argument("--config", required=True, type=Path)

    diagnose = commands.add_parser(
        "diagnose", help="report structural identifiability by family and mode"
    )
    diagnose.add_argument("--config", required=True, type=Path)
    diagnose.add_argument("--family", action="append")
    diagnose.add_argument("--mode", action="append")

    run = commands.add_parser(
        "run", help="generate and analyze synthetic observation campaigns"
    )
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--family", action="append")
    run.add_argument("--mode", action="append")
    run.add_argument("--repetitions", type=int)
    run.add_argument("--sample-sizes", type=_comma_separated_positive_integers)

    aggregate = commands.add_parser(
        "aggregate", help="combine workflow experiment shards"
    )
    aggregate.add_argument("--input-root", required=True, type=Path)
    aggregate.add_argument("--out", required=True, type=Path)

    reference = commands.add_parser(
        "run-likelihood-reference",
        help="compare log moments with the exact observed-likelihood reference",
    )
    reference.add_argument("--config", required=True, type=Path)
    reference.add_argument("--out", required=True, type=Path)
    reference.add_argument("--family", action="append")
    reference.add_argument("--mode", action="append")
    reference.add_argument("--repetitions", type=int)
    reference.add_argument("--sample-sizes", type=_comma_separated_positive_integers)

    aggregate_reference = commands.add_parser(
        "aggregate-likelihood-reference",
        help="combine exact-likelihood reference shards",
    )
    aggregate_reference.add_argument("--input-root", required=True, type=Path)
    aggregate_reference.add_argument("--out", required=True, type=Path)

    reduction = commands.add_parser(
        "run-reduction-experiment",
        help="compare the structure-preserving reduction with the exact reference",
    )
    reduction.add_argument("--config", required=True, type=Path)
    reduction.add_argument("--out", required=True, type=Path)
    reduction.add_argument("--family", action="append")
    reduction.add_argument("--mode", action="append")
    reduction.add_argument("--repetitions", type=int)
    reduction.add_argument("--sample-sizes", type=_comma_separated_positive_integers)

    aggregate_reduction = commands.add_parser(
        "aggregate-reduction-experiment",
        help="combine structure-preserving reduction shards",
    )
    aggregate_reduction.add_argument("--input-root", required=True, type=Path)
    aggregate_reduction.add_argument("--out", required=True, type=Path)

    validate_transfer = commands.add_parser(
        "validate-transfer-config",
        help="validate the non-direct placement-transfer experiment contract",
    )
    validate_transfer.add_argument("--config", required=True, type=Path)

    transfer = commands.add_parser(
        "run-transfer-experiment",
        help="run the matched B0-B4 non-direct placement-transfer experiment",
    )
    transfer.add_argument("--config", required=True, type=Path)
    transfer.add_argument("--out", required=True, type=Path)
    transfer.add_argument("--scenario", action="append")
    transfer.add_argument("--mode", action="append")
    transfer.add_argument("--repetitions", type=int)
    transfer.add_argument("--sample-sizes", type=_comma_separated_positive_integers)
    transfer.add_argument("--validation-episodes", type=int)

    aggregate_transfer = commands.add_parser(
        "aggregate-transfer-experiment",
        help="combine non-direct placement-transfer workflow shards",
    )
    aggregate_transfer.add_argument("--input-root", required=True, type=Path)
    aggregate_transfer.add_argument("--out", required=True, type=Path)

    validate_uncertainty = commands.add_parser(
        "validate-uncertainty-config",
        help="validate the simultaneous uncertainty experiment contract",
    )
    validate_uncertainty.add_argument("--config", required=True, type=Path)

    uncertainty = commands.add_parser(
        "run-uncertainty-experiment",
        help="run simultaneous confidence-set coverage experiments",
    )
    uncertainty.add_argument("--config", required=True, type=Path)
    uncertainty.add_argument("--out", required=True, type=Path)
    uncertainty.add_argument("--scenario", action="append")
    uncertainty.add_argument("--mode", action="append")
    uncertainty.add_argument("--repetitions", type=int)
    uncertainty.add_argument("--sample-sizes", type=_comma_separated_positive_integers)

    aggregate_uncertainty = commands.add_parser(
        "aggregate-uncertainty-experiment",
        help="combine simultaneous uncertainty workflow shards",
    )
    aggregate_uncertainty.add_argument("--input-root", required=True, type=Path)
    aggregate_uncertainty.add_argument("--out", required=True, type=Path)

    validate_stress = commands.add_parser(
        "validate-stress-config",
        help="validate the directed misspecification experiment contract",
    )
    validate_stress.add_argument("--config", required=True, type=Path)

    stress = commands.add_parser(
        "run-stress-experiment",
        help="run paired directed misspecification and telemetry-loss tests",
    )
    stress.add_argument("--config", required=True, type=Path)
    stress.add_argument("--out", required=True, type=Path)
    stress.add_argument("--series", action="append")
    stress.add_argument("--repetitions", type=int)
    stress.add_argument("--sample-sizes", type=_comma_separated_positive_integers)
    stress.add_argument("--bootstrap-replicates", type=int)

    aggregate_stress = commands.add_parser(
        "aggregate-stress-experiment",
        help="combine directed stress-test workflow shards",
    )
    aggregate_stress.add_argument("--input-root", required=True, type=Path)
    aggregate_stress.add_argument("--out", required=True, type=Path)

    validate_live = commands.add_parser(
        "validate-live-harness",
        help="validate the versioned live-ingestion and benchmark contract",
    )
    validate_live.add_argument("--config", required=True, type=Path)

    ingest_live = commands.add_parser(
        "ingest-live-bundle",
        help="validate and normalize one external telemetry bundle",
    )
    ingest_live.add_argument("--config", required=True, type=Path)
    ingest_live.add_argument("--benchmark", required=True)
    ingest_live.add_argument(
        "--bundle",
        type=Path,
        help="bundle directory; defaults to the profile's contract fixture",
    )
    ingest_live.add_argument("--out", required=True, type=Path)

    verify_live = commands.add_parser(
        "verify-live-profile",
        help="verify a frozen upstream checkout and its ingestion adapter fixture",
    )
    verify_live.add_argument("--config", required=True, type=Path)
    verify_live.add_argument("--benchmark", required=True)
    verify_live.add_argument("--checkout", required=True, type=Path)
    verify_live.add_argument("--out", required=True, type=Path)

    aggregate_live = commands.add_parser(
        "aggregate-live-harness",
        help="combine frozen benchmark-profile verification artifacts",
    )
    aggregate_live.add_argument("--config", required=True, type=Path)
    aggregate_live.add_argument("--input-root", required=True, type=Path)
    aggregate_live.add_argument("--out", required=True, type=Path)

    validate_pilot = commands.add_parser(
        "validate-runtime-pilot",
        help="validate the remote-only live runtime pilot contract",
    )
    validate_pilot.add_argument("--config", required=True, type=Path)

    pin_compose = commands.add_parser(
        "pin-live-compose",
        help="replace every rendered Compose image with its frozen digest",
    )
    pin_compose.add_argument("--config", required=True, type=Path)
    pin_compose.add_argument("--profile", required=True)
    pin_compose.add_argument("--input", required=True, type=Path)
    pin_compose.add_argument("--out", required=True, type=Path)
    pin_compose.add_argument("--audit", required=True, type=Path)
    pin_compose.add_argument(
        "--telemetry-output-directory",
        type=Path,
        help="mount a lossless OTel file-exporter sink into the collector",
    )

    run_pilot = commands.add_parser(
        "run-runtime-pilot",
        help="run one remote-only benchmark feasibility pilot",
    )
    run_pilot.add_argument("--config", required=True, type=Path)
    run_pilot.add_argument("--profile", required=True)
    run_pilot.add_argument("--checkout", required=True, type=Path)
    run_pilot.add_argument("--compose", required=True, type=Path)
    run_pilot.add_argument("--image-audit", required=True, type=Path)
    run_pilot.add_argument("--out", required=True, type=Path)

    aggregate_pilot = commands.add_parser(
        "aggregate-runtime-pilot",
        help="combine remote benchmark feasibility pilot artifacts",
    )
    aggregate_pilot.add_argument("--config", required=True, type=Path)
    aggregate_pilot.add_argument("--input-root", required=True, type=Path)
    aggregate_pilot.add_argument("--out", required=True, type=Path)

    validate_fault = commands.add_parser(
        "validate-live-fault-diagnostic",
        help="validate the remote-only fault-control and trace-linkage contract",
    )
    validate_fault.add_argument("--config", required=True, type=Path)

    run_fault = commands.add_parser(
        "run-live-fault-diagnostic",
        help="run one remote fault-control and trace-linkage diagnostic cell",
    )
    run_fault.add_argument("--config", required=True, type=Path)
    run_fault.add_argument("--profile", required=True)
    run_fault.add_argument("--law", required=True)
    run_fault.add_argument("--repetition", required=True, type=int)
    run_fault.add_argument("--checkout", required=True, type=Path)
    run_fault.add_argument("--compose", required=True, type=Path)
    run_fault.add_argument("--image-audit", required=True, type=Path)
    run_fault.add_argument("--out", required=True, type=Path)

    aggregate_fault = commands.add_parser(
        "aggregate-live-fault-diagnostics",
        help="combine remote fault-control and trace-linkage diagnostic cells",
    )
    aggregate_fault.add_argument("--config", required=True, type=Path)
    aggregate_fault.add_argument("--input-root", required=True, type=Path)
    aggregate_fault.add_argument("--out", required=True, type=Path)

    validate_placement = commands.add_parser(
        "validate-placement-pilot",
        help="validate the remote-only replicated-placement pilot contract",
    )
    validate_placement.add_argument("--config", required=True, type=Path)

    prepare_placement = commands.add_parser(
        "prepare-placement-compose",
        help="replace one pinned service with two replicas and a pinned proxy",
    )
    prepare_placement.add_argument("--config", required=True, type=Path)
    prepare_placement.add_argument("--profile", required=True)
    prepare_placement.add_argument("--placement", required=True)
    prepare_placement.add_argument("--input", required=True, type=Path)
    prepare_placement.add_argument("--base-audit", required=True, type=Path)
    prepare_placement.add_argument("--out", required=True, type=Path)
    prepare_placement.add_argument("--audit", required=True, type=Path)
    prepare_placement.add_argument("--haproxy", required=True, type=Path)

    run_placement = commands.add_parser(
        "run-placement-pilot",
        help="run one remote replicated-placement and operation-semantics cell",
    )
    run_placement.add_argument("--config", required=True, type=Path)
    run_placement.add_argument("--profile", required=True)
    run_placement.add_argument("--placement", required=True)
    run_placement.add_argument("--checkout", required=True, type=Path)
    run_placement.add_argument("--compose", required=True, type=Path)
    run_placement.add_argument("--image-audit", required=True, type=Path)
    run_placement.add_argument("--haproxy", required=True, type=Path)
    run_placement.add_argument("--out", required=True, type=Path)

    aggregate_placement = commands.add_parser(
        "aggregate-placement-pilots",
        help="combine the four replicated-placement pilot cells",
    )
    aggregate_placement.add_argument("--config", required=True, type=Path)
    aggregate_placement.add_argument("--input-root", required=True, type=Path)
    aggregate_placement.add_argument("--out", required=True, type=Path)

    validate_stochastic = commands.add_parser(
        "validate-stochastic-freeze-pilot",
        help="validate the remote-only stochastic schedule and budget pilot",
    )
    validate_stochastic.add_argument("--config", required=True, type=Path)

    run_stochastic = commands.add_parser(
        "run-stochastic-freeze-pilot",
        help="run one remote M7C stochastic freeze-pilot cell",
    )
    run_stochastic.add_argument("--config", required=True, type=Path)
    run_stochastic.add_argument("--profile", required=True)
    run_stochastic.add_argument("--placement", required=True)
    run_stochastic.add_argument("--law", required=True)
    run_stochastic.add_argument("--repetition", required=True, type=int)
    run_stochastic.add_argument("--checkout", required=True, type=Path)
    run_stochastic.add_argument("--compose", required=True, type=Path)
    run_stochastic.add_argument("--image-audit", required=True, type=Path)
    run_stochastic.add_argument("--out", required=True, type=Path)

    aggregate_stochastic = commands.add_parser(
        "aggregate-stochastic-freeze-pilots",
        help="combine all M7C stochastic freeze-pilot cells",
    )
    aggregate_stochastic.add_argument("--config", required=True, type=Path)
    aggregate_stochastic.add_argument("--input-root", required=True, type=Path)
    aggregate_stochastic.add_argument("--out", required=True, type=Path)

    validate_evidence = commands.add_parser(
        "validate-evidence-boundary",
        help="validate the M7D learner/evaluator evidence-separation contract",
    )
    validate_evidence.add_argument("--config", required=True, type=Path)

    qualify_evidence = commands.add_parser(
        "qualify-evidence-boundary",
        help="normalize M7C cells and audit the M7 learner/evaluator boundary",
    )
    qualify_evidence.add_argument("--config", required=True, type=Path)
    qualify_evidence.add_argument("--input-root", required=True, type=Path)
    qualify_evidence.add_argument("--out", required=True, type=Path)

    qualify_evidence_cell_parser = commands.add_parser(
        "qualify-evidence-cell",
        help="normalize one main M7 cell behind the frozen evidence boundary",
    )
    qualify_evidence_cell_parser.add_argument("--config", required=True, type=Path)
    qualify_evidence_cell_parser.add_argument("--input", required=True, type=Path)
    qualify_evidence_cell_parser.add_argument("--out", required=True, type=Path)

    validate_frozen_live = commands.add_parser(
        "validate-frozen-live-validation",
        help="validate the fully frozen M7 acquisition and analysis contract",
    )
    validate_frozen_live.add_argument("--config", required=True, type=Path)

    run_frozen_live = commands.add_parser(
        "run-frozen-live-cell",
        help="run one remote-only frozen M7 campaign cell",
    )
    run_frozen_live.add_argument("--config", required=True, type=Path)
    run_frozen_live.add_argument("--profile", required=True)
    run_frozen_live.add_argument("--placement", required=True)
    run_frozen_live.add_argument("--law", required=True)
    run_frozen_live.add_argument("--repetition", required=True, type=int)
    run_frozen_live.add_argument("--checkout", required=True, type=Path)
    run_frozen_live.add_argument("--compose", required=True, type=Path)
    run_frozen_live.add_argument("--image-audit", required=True, type=Path)
    run_frozen_live.add_argument("--out", required=True, type=Path)
    run_frozen_live.add_argument(
        "--execution-scope", required=True, choices=("preflight", "full")
    )

    analyze_frozen_live = commands.add_parser(
        "analyze-frozen-live-validation",
        help="fit and score the frozen M7 methods from qualified evidence",
    )
    analyze_frozen_live.add_argument("--config", required=True, type=Path)
    analyze_frozen_live.add_argument("--input-root", required=True, type=Path)
    analyze_frozen_live.add_argument("--out", required=True, type=Path)
    analyze_frozen_live.add_argument(
        "--scope", required=True, choices=("preflight", "full")
    )

    audit_m7 = commands.add_parser(
        "audit-m7-evidence",
        help="inventory preserved M7 evidence and independently audit its arithmetic",
    )
    audit_m7.add_argument("--config", required=True, type=Path)
    audit_m7.add_argument("--artifact-json", required=True, type=Path)
    audit_m7.add_argument("--qualified-root", required=True, type=Path)
    audit_m7.add_argument("--analysis-root", required=True, type=Path)
    audit_m7.add_argument("--raw-root", required=True, type=Path)
    audit_m7.add_argument("--source-run-id", required=True)
    audit_m7.add_argument("--out", required=True, type=Path)

    diagnose_m7 = commands.add_parser(
        "diagnose-m7-discrepancies",
        help="decompose M7 bias, time, semantics, and topology on preserved evidence",
    )
    diagnose_m7.add_argument("--config", required=True, type=Path)
    diagnose_m7.add_argument("--evidence-config", required=True, type=Path)
    diagnose_m7.add_argument("--qualified-root", required=True, type=Path)
    diagnose_m7.add_argument("--analysis-root", required=True, type=Path)
    diagnose_m7.add_argument("--raw-root", required=True, type=Path)
    diagnose_m7.add_argument("--out", required=True, type=Path)

    validate_recovery = commands.add_parser(
        "validate-macro-live-budget",
        help="validate the post-stopping M7C macro-resource recovery contract",
    )
    validate_recovery.add_argument("--config", required=True, type=Path)

    recover_budget = commands.add_parser(
        "recover-macro-live-budget",
        help="replay all M7C cells and select the narrowed macro repetition budget",
    )
    recover_budget.add_argument("--config", required=True, type=Path)
    recover_budget.add_argument("--input-root", required=True, type=Path)
    recover_budget.add_argument("--out", required=True, type=Path)

    validate_palladio = commands.add_parser(
        "validate-palladio-bootstrap",
        help="validate the remote-only pinned Palladio bootstrap contract",
    )
    validate_palladio.add_argument("--config", required=True, type=Path)

    lock_palladio_target = commands.add_parser(
        "lock-palladio-target-platform",
        help="audit and historically pin Palladio's mutable target dependency",
    )
    lock_palladio_target.add_argument("--config", required=True, type=Path)
    lock_palladio_target.add_argument("--target-file", required=True, type=Path)
    lock_palladio_target.add_argument(
        "--repository-evidence-dir", required=True, type=Path
    )
    lock_palladio_target.add_argument("--out", required=True, type=Path)

    audit_palladio_source_parser = commands.add_parser(
        "audit-palladio-source",
        help="audit the commit-pinned Palladio reliability source build",
    )
    audit_palladio_source_parser.add_argument("--config", required=True, type=Path)
    audit_palladio_source_parser.add_argument(
        "--checkout", required=True, type=Path
    )
    audit_palladio_source_parser.add_argument(
        "--build-log", required=True, type=Path
    )
    audit_palladio_source_parser.add_argument("--out", required=True, type=Path)

    audit_palladio_product_parser = commands.add_parser(
        "audit-palladio-product",
        help="hash and inventory the pinned Palladio Bench binary product",
    )
    audit_palladio_product_parser.add_argument(
        "--config", required=True, type=Path
    )
    audit_palladio_product_parser.add_argument(
        "--archive", required=True, type=Path
    )
    audit_palladio_product_parser.add_argument("--out", required=True, type=Path)

    audit_palladio_example_parser = commands.add_parser(
        "audit-palladio-example",
        help="audit repeated execution of the official Palladio reliability example",
    )
    audit_palladio_example_parser.add_argument(
        "--config", required=True, type=Path
    )
    audit_palladio_example_parser.add_argument(
        "--result", required=True, type=Path
    )
    audit_palladio_example_parser.add_argument(
        "--analyzer-checkout", required=True, type=Path
    )
    audit_palladio_example_parser.add_argument(
        "--example-checkout", required=True, type=Path
    )
    audit_palladio_example_parser.add_argument("--out", required=True, type=Path)

    validate_palladio_controls = commands.add_parser(
        "validate-palladio-controls",
        help="validate the frozen remote-only M9B Palladio control contract",
    )
    validate_palladio_controls.add_argument("--config", required=True, type=Path)

    generate_palladio_controls = commands.add_parser(
        "generate-palladio-controls",
        help="generate the frozen hand-checkable PCM control models",
    )
    generate_palladio_controls.add_argument("--config", required=True, type=Path)
    generate_palladio_controls.add_argument("--out", required=True, type=Path)
    generate_palladio_controls.add_argument(
        "--manifest", required=True, type=Path
    )

    audit_palladio_models = commands.add_parser(
        "audit-palladio-control-models",
        help="independently parse and audit generated M9B PCM control models",
    )
    audit_palladio_models.add_argument("--config", required=True, type=Path)
    audit_palladio_models.add_argument("--models", required=True, type=Path)
    audit_palladio_models.add_argument("--pcm-ecore", required=True, type=Path)
    audit_palladio_models.add_argument(
        "--bootstrap-config", required=True, type=Path
    )
    audit_palladio_models.add_argument("--out", required=True, type=Path)

    audit_palladio_capabilities = commands.add_parser(
        "audit-palladio-capability-source",
        help="audit pinned replication and communication semantics in analyzer source",
    )
    audit_palladio_capabilities.add_argument(
        "--config", required=True, type=Path
    )
    audit_palladio_capabilities.add_argument(
        "--analyzer-checkout", required=True, type=Path
    )
    audit_palladio_capabilities.add_argument("--out", required=True, type=Path)

    audit_palladio_results = commands.add_parser(
        "audit-palladio-control-results",
        help="audit M9B Palladio outputs against the frozen independent oracles",
    )
    audit_palladio_results.add_argument("--config", required=True, type=Path)
    audit_palladio_results.add_argument(
        "--model-manifest", required=True, type=Path
    )
    audit_palladio_results.add_argument(
        "--capability-manifest", required=True, type=Path
    )
    audit_palladio_results.add_argument("--result", required=True, type=Path)
    audit_palladio_results.add_argument("--models", required=True, type=Path)
    audit_palladio_results.add_argument("--out", required=True, type=Path)

    validate_palladio_mapping = commands.add_parser(
        "validate-palladio-application-mapping",
        help="validate the frozen M9C evidence and application-model contract",
    )
    validate_palladio_mapping.add_argument("--config", required=True, type=Path)

    audit_palladio_mapping_evidence = commands.add_parser(
        "audit-palladio-application-evidence",
        help="audit accepted M8B evidence and commit-pinned application sources",
    )
    audit_palladio_mapping_evidence.add_argument(
        "--config", required=True, type=Path
    )
    audit_palladio_mapping_evidence.add_argument(
        "--m8b-input-root", required=True, type=Path
    )
    audit_palladio_mapping_evidence.add_argument(
        "--artifact-metadata", required=True, type=Path
    )
    audit_palladio_mapping_evidence.add_argument(
        "--upstream-root", required=True, type=Path
    )
    audit_palladio_mapping_evidence.add_argument(
        "--repository-root", required=True, type=Path
    )
    audit_palladio_mapping_evidence.add_argument("--out", required=True, type=Path)

    generate_palladio_applications = commands.add_parser(
        "generate-palladio-application-models",
        help="generate the two frozen application PCM templates and placements",
    )
    generate_palladio_applications.add_argument(
        "--config", required=True, type=Path
    )
    generate_palladio_applications.add_argument("--out", required=True, type=Path)
    generate_palladio_applications.add_argument(
        "--manifest", required=True, type=Path
    )

    audit_palladio_applications = commands.add_parser(
        "audit-palladio-application-models",
        help="independently parse and audit the generated M9C PCM models",
    )
    audit_palladio_applications.add_argument("--config", required=True, type=Path)
    audit_palladio_applications.add_argument("--models", required=True, type=Path)
    audit_palladio_applications.add_argument(
        "--repository-root", required=True, type=Path
    )
    audit_palladio_applications.add_argument("--out", required=True, type=Path)

    audit_palladio_application_output = commands.add_parser(
        "audit-palladio-application-results",
        help="audit repeated M9C solver results against the frozen structural oracles",
    )
    audit_palladio_application_output.add_argument(
        "--config", required=True, type=Path
    )
    audit_palladio_application_output.add_argument(
        "--evidence-manifest", required=True, type=Path
    )
    audit_palladio_application_output.add_argument(
        "--model-manifest", required=True, type=Path
    )
    audit_palladio_application_output.add_argument(
        "--result", required=True, type=Path
    )
    audit_palladio_application_output.add_argument(
        "--models", required=True, type=Path
    )
    audit_palladio_application_output.add_argument(
        "--out", required=True, type=Path
    )

    validate_palladio_aligned = commands.add_parser(
        "validate-palladio-aligned-comparison",
        help="validate the frozen remote-only M9D aligned-input contract",
    )
    validate_palladio_aligned.add_argument("--config", required=True, type=Path)

    audit_palladio_aligned_input = commands.add_parser(
        "audit-palladio-aligned-evidence",
        help="audit all accepted M7/M8A/M9C inputs for M9D",
    )
    audit_palladio_aligned_input.add_argument("--config", required=True, type=Path)
    audit_palladio_aligned_input.add_argument(
        "--m8a-preserved-metadata", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--m8a-audit-metadata", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--m9c-contract-metadata", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--m9c-solver-metadata", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--m9c-acceptance-metadata", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--qualified-root", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--analysis-root", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument("--raw-root", required=True, type=Path)
    audit_palladio_aligned_input.add_argument(
        "--audit-root", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--m9c-contract-root", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--m9c-acceptance-root", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument(
        "--repository-root", required=True, type=Path
    )
    audit_palladio_aligned_input.add_argument("--out", required=True, type=Path)

    stage_palladio_aligned = commands.add_parser(
        "stage-palladio-aligned-learner-input",
        help="stage the physically learner-only M9D evidence tree",
    )
    stage_palladio_aligned.add_argument("--config", required=True, type=Path)
    stage_palladio_aligned.add_argument(
        "--qualified-root", required=True, type=Path
    )
    stage_palladio_aligned.add_argument("--out", required=True, type=Path)

    prepare_palladio_aligned = commands.add_parser(
        "prepare-palladio-aligned-models",
        help="replay frozen learner fits and generate admitted M9D PCM models",
    )
    prepare_palladio_aligned.add_argument("--config", required=True, type=Path)
    prepare_palladio_aligned.add_argument(
        "--learner-root", required=True, type=Path
    )
    prepare_palladio_aligned.add_argument(
        "--analysis-root", required=True, type=Path
    )
    prepare_palladio_aligned.add_argument(
        "--evidence-manifest", required=True, type=Path
    )
    prepare_palladio_aligned.add_argument("--models", required=True, type=Path)
    prepare_palladio_aligned.add_argument("--out", required=True, type=Path)

    audit_palladio_aligned_output = commands.add_parser(
        "audit-palladio-aligned-results",
        help="audit M9D solver fidelity and score held-out outcomes",
    )
    audit_palladio_aligned_output.add_argument("--config", required=True, type=Path)
    audit_palladio_aligned_output.add_argument("--contract", required=True, type=Path)
    audit_palladio_aligned_output.add_argument("--result", required=True, type=Path)
    audit_palladio_aligned_output.add_argument(
        "--qualified-root", required=True, type=Path
    )
    audit_palladio_aligned_output.add_argument(
        "--analysis-root", required=True, type=Path
    )
    audit_palladio_aligned_output.add_argument(
        "--audit-root", required=True, type=Path
    )
    audit_palladio_aligned_output.add_argument(
        "--m8a-preserved-metadata", required=True, type=Path
    )
    audit_palladio_aligned_output.add_argument(
        "--m8a-audit-metadata", required=True, type=Path
    )
    audit_palladio_aligned_output.add_argument("--out", required=True, type=Path)
    return parser


def _filter(
    items: Sequence[object], names: list[str] | None, label: str
) -> list[object]:
    if not names:
        return list(items)
    lookup = {getattr(item, "id"): item for item in items}
    unknown = set(names) - set(lookup)
    if unknown:
        raise ValueError(f"unknown {label}: {sorted(unknown)}")
    return [lookup[name] for name in names]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-config":
        config = load_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "families": [item.id for item in config.families],
                    "observation_modes": [item.id for item in config.observation_modes],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "diagnose":
        config = load_config(args.config)
        families = _filter(config.families, args.family, "families")
        modes = _filter(config.observation_modes, args.mode, "observation modes")
        rows = []
        for family in families:
            for mode in modes:
                report = diagnose_identifiability(
                    family,
                    structural_moment_rows(family, mode, config.max_moment_order),
                )
                rows.append(
                    {
                        "family": family.id,
                        "observation_mode": mode.id,
                        "rank": report.rank,
                        "parameter_count": report.parameter_count,
                        "full_rank": report.full_rank,
                        "parameter_identifiable": report.parameter_identifiable,
                        "target_identifiable": report.target_identifiable,
                        "condition_number": report.condition_number,
                    }
                )
        print(json.dumps(rows, indent=2, sort_keys=True))
        return 0

    if args.command == "run":
        config = load_config(args.config)
        manifest = run_experiment(
            config=config,
            config_path=args.config,
            output_directory=args.out,
            family_names=None if args.family is None else tuple(args.family),
            mode_names=None if args.mode is None else tuple(args.mode),
            repetitions=args.repetitions,
            sample_sizes=args.sample_sizes,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate":
        manifest = aggregate_results(args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "run-likelihood-reference":
        config = load_config(args.config)
        manifest = run_likelihood_reference(
            config=config,
            config_path=args.config,
            output_directory=args.out,
            family_names=None if args.family is None else tuple(args.family),
            mode_names=None if args.mode is None else tuple(args.mode),
            repetitions=args.repetitions,
            sample_sizes=args.sample_sizes,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-likelihood-reference":
        manifest = aggregate_likelihood_reference(args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "run-reduction-experiment":
        config = load_config(args.config)
        manifest = run_reduction_experiment(
            config=config,
            config_path=args.config,
            output_directory=args.out,
            family_names=None if args.family is None else tuple(args.family),
            mode_names=None if args.mode is None else tuple(args.mode),
            repetitions=args.repetitions,
            sample_sizes=args.sample_sizes,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-reduction-experiment":
        manifest = aggregate_reduction_experiment(args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-transfer-config":
        config = load_transfer_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "scenarios": [item.id for item in config.scenarios],
                    "observation_modes": [item.id for item in config.observation_modes],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run-transfer-experiment":
        config = load_transfer_config(args.config)
        manifest = run_transfer_experiment(
            config=config,
            config_path=args.config,
            output_directory=args.out,
            scenario_names=(None if args.scenario is None else tuple(args.scenario)),
            mode_names=None if args.mode is None else tuple(args.mode),
            repetitions=args.repetitions,
            sample_sizes=args.sample_sizes,
            validation_episodes=args.validation_episodes,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-transfer-experiment":
        manifest = aggregate_transfer_experiment(args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-uncertainty-config":
        config = load_uncertainty_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "confidence_level": config.confidence_level,
                    "scenarios": [item.id for item in config.transfer.scenarios],
                    "observation_modes": [
                        item.id for item in config.transfer.observation_modes
                    ],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run-uncertainty-experiment":
        config = load_uncertainty_config(args.config)
        manifest = run_uncertainty_experiment(
            config=config,
            config_path=args.config,
            output_directory=args.out,
            scenario_names=(None if args.scenario is None else tuple(args.scenario)),
            mode_names=None if args.mode is None else tuple(args.mode),
            repetitions=args.repetitions,
            sample_sizes=args.sample_sizes,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-uncertainty-experiment":
        manifest = aggregate_uncertainty_experiment(args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-stress-config":
        config = load_stress_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "series": [item.id for item in config.series],
                    "variants": {
                        item.id: [variant.id for variant in item.variants]
                        for item in config.series
                    },
                },
                indent=2,
            )
        )
        return 0

    if args.command == "run-stress-experiment":
        config = load_stress_config(args.config)
        manifest = run_stress_experiment(
            config=config,
            config_path=args.config,
            output_directory=args.out,
            series_names=None if args.series is None else tuple(args.series),
            repetitions=args.repetitions,
            sample_sizes=args.sample_sizes,
            bootstrap_replicates=args.bootstrap_replicates,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-stress-experiment":
        manifest = aggregate_stress_experiment(args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-live-harness":
        config = load_live_harness_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "contract": f"{config.contract.id}/v{config.contract.version}",
                    "benchmarks": [item.id for item in config.benchmarks],
                    "trace_adapters": sorted(
                        {item.trace_format for item in config.benchmarks}
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "ingest-live-bundle":
        config = load_live_harness_config(args.config)
        profile = select_live_profile(config, args.benchmark)
        bundle_directory = (
            profile.fixture_bundle if args.bundle is None else args.bundle
        )
        bundle = ingest_live_bundle(bundle_directory, config.contract, profile)
        manifest = write_ingested_bundle(bundle, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "verify-live-profile":
        config = load_live_harness_config(args.config)
        report = verify_live_profile(
            config,
            args.benchmark,
            args.checkout,
            args.out,
        )
        print(json.dumps(report["fixture_audit"]["counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-live-harness":
        config = load_live_harness_config(args.config)
        manifest = aggregate_live_harness(config, args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-runtime-pilot":
        config = load_runtime_pilot_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "pilot_only": config.pilot_only,
                    "profiles": [profile.id for profile in config.profiles],
                    "expected_requests_per_profile": 2
                    * config.requests_per_operation_per_period
                    * len(config.profiles[0].operations),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "pin-live-compose":
        config = load_runtime_pilot_config(args.config)
        audit = pin_compose_files(
            config,
            args.profile,
            args.input,
            args.out,
            args.audit,
            args.telemetry_output_directory,
        )
        print(json.dumps(audit, indent=2, sort_keys=True))
        return 0

    if args.command == "run-runtime-pilot":
        config = load_runtime_pilot_config(args.config)
        manifest = run_runtime_pilot(
            config,
            args.profile,
            args.checkout,
            args.compose,
            args.image_audit,
            args.out,
            args.execution_scope,
        )
        print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-runtime-pilot":
        config = load_runtime_pilot_config(args.config)
        manifest = aggregate_runtime_pilots(config, args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-live-fault-diagnostic":
        config = load_live_fault_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "diagnostic_only": config.diagnostic_only,
                    "profiles": [profile.id for profile in config.profiles],
                    "failure_laws": config.laws,
                    "expected_cells": len(config.profiles)
                    * len(config.laws)
                    * config.repetitions,
                    "requests_per_cell": 2 * config.requests_per_period,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "run-live-fault-diagnostic":
        config = load_live_fault_config(args.config)
        manifest = run_live_fault_diagnostic(
            config,
            args.profile,
            args.law,
            args.repetition,
            args.checkout,
            args.compose,
            args.image_audit,
            args.out,
        )
        print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-live-fault-diagnostics":
        config = load_live_fault_config(args.config)
        manifest = aggregate_live_fault_diagnostics(
            config,
            args.input_root,
            args.out,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-placement-pilot":
        config = load_placement_pilot_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "pilot_only": config.pilot_only,
                    "profiles": [profile.id for profile in config.profiles],
                    "placements": config.placements,
                    "expected_cells": len(config.profiles) * len(config.placements),
                    "requests_per_cell": len(config.runtime.profiles[0].operations)
                    + config.routing_probe_requests
                    + config.requests_per_fault_period,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "prepare-placement-compose":
        config = load_placement_pilot_config(args.config)
        audit = prepare_placement_compose(
            config,
            args.profile,
            args.placement,
            args.input,
            args.base_audit,
            args.out,
            args.audit,
            args.haproxy,
        )
        print(json.dumps(audit["placement_pilot"], indent=2, sort_keys=True))
        return 0

    if args.command == "run-placement-pilot":
        config = load_placement_pilot_config(args.config)
        manifest = run_placement_pilot(
            config,
            args.profile,
            args.placement,
            args.checkout,
            args.compose,
            args.image_audit,
            args.haproxy,
            args.out,
        )
        print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-placement-pilots":
        config = load_placement_pilot_config(args.config)
        manifest = aggregate_placement_pilots(config, args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-stochastic-freeze-pilot":
        config = load_stochastic_pilot_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "pilot_only": config.pilot_only,
                    "expected_cells": config.expected_cells,
                    "pilot_repetitions": config.pilot_repetitions,
                    "requests_per_cell": (
                        config.baseline_requests + 2 * config.requests_per_period
                    ),
                    "candidate_period_seconds": (
                        config.design_selection.candidate_period_seconds
                    ),
                    "candidate_main_repetitions": (
                        config.design_selection.candidate_main_repetitions
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "run-stochastic-freeze-pilot":
        config = load_stochastic_pilot_config(args.config)
        manifest = run_stochastic_freeze_pilot(
            config,
            args.profile,
            args.placement,
            args.law,
            args.repetition,
            args.checkout,
            args.compose,
            args.image_audit,
            args.out,
        )
        print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "aggregate-stochastic-freeze-pilots":
        config = load_stochastic_pilot_config(args.config)
        manifest = aggregate_stochastic_freeze_pilots(
            config,
            args.input_root,
            args.out,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-evidence-boundary":
        config = load_evidence_boundary_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "diagnostic_only": config.diagnostic_only,
                    "main_effectiveness": config.main_effectiveness,
                    "source_experiment_id": config.source_experiment_id,
                    "source_manifest_file": config.source_manifest_file,
                    "source_usable_field": config.source_usable_field,
                    "expected_source_cells": config.expected_source_cells,
                    "learner_period": config.learner_period,
                    "auxiliary_learner_periods": config.auxiliary_learner_periods,
                    "profiles": [profile.id for profile in config.profiles],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "qualify-evidence-boundary":
        config = load_evidence_boundary_config(args.config)
        manifest = qualify_evidence_boundary(config, args.input_root, args.out)
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "qualify-evidence-cell":
        config = load_evidence_boundary_config(args.config)
        summary = qualify_evidence_cell(config, args.input, args.out)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if args.command == "validate-frozen-live-validation":
        config = load_frozen_live_validation_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "main_effectiveness": config.main_effectiveness,
                    "expected_cells": config.expected_cells,
                    "requests_per_cell": (
                        config.stochastic.baseline_requests
                        + 2 * config.stochastic.requests_per_period
                    ),
                    "period_seconds": config.stochastic.period_seconds,
                    "repetitions": config.repetitions,
                    "selected_design_sha256": config.selected_design_sha256,
                    "primary_contrast": config.analysis.primary_contrast,
                    "primary_mode": config.analysis.primary_mode,
                    "methods": config.analysis.methods,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "run-frozen-live-cell":
        config = load_frozen_live_validation_config(args.config)
        manifest = run_frozen_live_cell(
            config,
            args.profile,
            args.placement,
            args.law,
            args.repetition,
            args.checkout,
            args.compose,
            args.image_audit,
            args.out,
            args.execution_scope,
        )
        print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "analyze-frozen-live-validation":
        config = load_frozen_live_validation_config(args.config)
        manifest = analyze_live_validation(
            config, args.input_root, args.out, args.scope
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "audit-m7-evidence":
        config = load_frozen_live_validation_config(args.config)
        manifest = run_m7_diagnostic_audit(
            config=config,
            artifact_json=args.artifact_json,
            qualified_root=args.qualified_root,
            analysis_root=args.analysis_root,
            raw_root=args.raw_root,
            output_directory=args.out,
            source_run_id=args.source_run_id,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "diagnose-m7-discrepancies":
        config = load_frozen_live_validation_config(args.config)
        evidence_config = load_evidence_boundary_config(args.evidence_config)
        manifest = run_m7_causal_diagnostics(
            config=config,
            evidence_config=evidence_config,
            qualified_root=args.qualified_root,
            analysis_root=args.analysis_root,
            raw_root=args.raw_root,
            output_directory=args.out,
        )
        print(json.dumps(manifest["row_counts"], indent=2, sort_keys=True))
        return 0

    if args.command == "validate-macro-live-budget":
        config = load_macro_budget_recovery_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "pilot_only": config.pilot_only,
                    "source_pilot_run_id": config.source_pilot_run_id,
                    "expected_strata": config.expected_strata,
                    "cell_specific_precision_claim": (
                        config.cell_specific_precision_claim
                    ),
                    "candidate_main_repetitions": (config.candidate_main_repetitions),
                    "target_macro_half_width": config.target_macro_half_width,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "recover-macro-live-budget":
        config = load_macro_budget_recovery_config(args.config)
        manifest = recover_macro_budget(config, args.input_root, args.out)
        print(
            json.dumps(
                manifest["recommendation"]["repetitions"],
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "validate-palladio-bootstrap":
        config = load_palladio_bootstrap_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "diagnostic_only": config.diagnostic_only,
                    "analyzer_commit": config.analyzer.commit,
                    "example_commit": config.official_example.commit,
                    "product_sha256": config.product.sha256,
                    "acceptance_ready": config.acceptance_ready,
                    "job_timeout_minutes": config.runtime.job_timeout_minutes,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "lock-palladio-target-platform":
        manifest = apply_palladio_target_platform_lock(
            args.config,
            args.target_file,
            args.repository_evidence_dir,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-source":
        manifest = audit_palladio_source(
            args.config, args.checkout, args.build_log, args.out
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-product":
        manifest = audit_palladio_product(args.config, args.archive, args.out)
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-example":
        manifest = audit_palladio_example(
            args.config,
            args.result,
            args.analyzer_checkout,
            args.example_checkout,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "validate-palladio-controls":
        config = load_palladio_controls_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "diagnostic_only": config.diagnostic_only,
                    "comparison_status": config.comparison_status,
                    "analyzer_commit": config.analyzer_commit,
                    "model_count": len(config.models),
                    "case_count": len(config.cases),
                    "repeat_runs": config.repeat_runs,
                    "job_timeout_minutes": config.job_timeout_minutes,
                    "remote_only": config.remote_only,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "generate-palladio-controls":
        manifest = generate_palladio_control_models(
            args.config, args.out, args.manifest
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-control-models":
        manifest = audit_palladio_control_models(
            args.config,
            args.models,
            args.pcm_ecore,
            args.bootstrap_config,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-capability-source":
        manifest = audit_palladio_capability_source(
            args.config, args.analyzer_checkout, args.out
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-control-results":
        manifest = audit_palladio_control_results(
            args.config,
            args.model_manifest,
            args.capability_manifest,
            args.result,
            args.models,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "validate-palladio-application-mapping":
        config = load_palladio_mapping_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "diagnostic_only": True,
                    "accuracy_comparison_status": "not_started",
                    "applications": [item.id for item in config.applications],
                    "operations": [item.operation for item in config.applications],
                    "model_count": len(config.models),
                    "repeat_runs": config.repeat_runs,
                    "job_timeout_minutes": config.job_timeout_minutes,
                    "remote_only": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "audit-palladio-application-evidence":
        manifest = audit_palladio_application_evidence(
            args.config,
            args.m8b_input_root,
            args.artifact_metadata,
            args.upstream_root,
            args.repository_root,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "generate-palladio-application-models":
        manifest = generate_palladio_application_models(
            args.config, args.out, args.manifest
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-application-models":
        manifest = audit_palladio_application_models(
            args.config, args.models, args.repository_root, args.out
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-application-results":
        manifest = audit_palladio_application_results(
            args.config,
            args.evidence_manifest,
            args.model_manifest,
            args.result,
            args.models,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "validate-palladio-aligned-comparison":
        config = load_palladio_aligned_config(args.config)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "experiment_id": config.id,
                    "role": "exploratory_post_result_debugging",
                    "observation_mode": config.observation_mode,
                    "opportunities": dict(config.expected_opportunities),
                    "expected_models": config.expected_models,
                    "expected_raw_runs": config.expected_raw_runs,
                    "technical_repetitions": config.technical_repetitions,
                    "job_timeout_minutes": 360,
                    "remote_only_full_execution": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "audit-palladio-aligned-evidence":
        manifest = audit_palladio_aligned_evidence(
            args.config,
            args.m8a_preserved_metadata,
            args.m8a_audit_metadata,
            args.m9c_contract_metadata,
            args.m9c_solver_metadata,
            args.m9c_acceptance_metadata,
            args.qualified_root,
            args.analysis_root,
            args.raw_root,
            args.audit_root,
            args.m9c_contract_root,
            args.m9c_acceptance_root,
            args.repository_root,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "stage-palladio-aligned-learner-input":
        manifest = stage_palladio_aligned_learner_input(
            args.config, args.qualified_root, args.out
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "prepare-palladio-aligned-models":
        manifest = prepare_palladio_aligned_models(
            args.config,
            args.learner_root,
            args.analysis_root,
            args.evidence_manifest,
            args.models,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    if args.command == "audit-palladio-aligned-results":
        manifest = audit_palladio_aligned_results(
            args.config,
            args.contract,
            args.result,
            args.qualified_root,
            args.analysis_root,
            args.audit_root,
            args.m8a_preserved_metadata,
            args.m8a_audit_metadata,
            args.out,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    raise AssertionError(f"unhandled command {args.command}")
