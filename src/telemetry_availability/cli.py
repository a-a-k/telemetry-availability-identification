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
from .moments import structural_moment_rows
from .runner import aggregate_results, run_experiment


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

    raise AssertionError(f"unhandled command {args.command}")
