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
from .live_config import load_live_harness_config
from .live_harness import (
    aggregate_live_harness,
    select_live_profile,
    verify_live_profile,
)
from .live_ingestion import ingest_live_bundle, write_ingested_bundle
from .moments import structural_moment_rows
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

    validate = commands.add_parser("validate-config", help="validate a YAML experiment contract")
    validate.add_argument("--config", required=True, type=Path)

    diagnose = commands.add_parser("diagnose", help="report structural identifiability by family and mode")
    diagnose.add_argument("--config", required=True, type=Path)
    diagnose.add_argument("--family", action="append")
    diagnose.add_argument("--mode", action="append")

    run = commands.add_parser("run", help="generate and analyze synthetic observation campaigns")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--family", action="append")
    run.add_argument("--mode", action="append")
    run.add_argument("--repetitions", type=int)
    run.add_argument("--sample-sizes", type=_comma_separated_positive_integers)

    aggregate = commands.add_parser("aggregate", help="combine workflow experiment shards")
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
    return parser


def _filter(items: Sequence[object], names: list[str] | None, label: str) -> list[object]:
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
                    "observation_modes": [
                        item.id for item in config.observation_modes
                    ],
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
            scenario_names=(
                None if args.scenario is None else tuple(args.scenario)
            ),
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
            scenario_names=(
                None if args.scenario is None else tuple(args.scenario)
            ),
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
        bundle_directory = profile.fixture_bundle if args.bundle is None else args.bundle
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

    raise AssertionError(f"unhandled command {args.command}")
