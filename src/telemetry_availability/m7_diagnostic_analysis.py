from __future__ import annotations

import csv
import json
import math
import os
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path
from statistics import fmean, variance
from typing import Any, Iterable

from scipy.stats import t

from .live_validation import frozen_live_matrix
from .live_validation_analysis import QualifiedCell, discover_qualified_cells
from .live_validation_config import FrozenLiveValidationConfig
from .provenance import environment_manifest, file_sha256


class M7DiagnosticError(RuntimeError):
    """Raised when preserved M7 evidence fails a diagnostic integrity check."""


ARTIFACT_FIELDS = (
    "artifact_id",
    "name",
    "kind",
    "size_in_bytes",
    "expired",
    "expires_at",
    "digest",
)
FILE_FIELDS = ("evidence_group", "relative_path", "size_in_bytes", "sha256")
IDENTITY_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "expected_artifact",
    "artifact_present",
    "qualified_cell_present",
    "source_run_id",
    "source_run_matches",
    "source_commit",
)
ANALYSIS_FILE_FIELDS = (
    "filename",
    "size_in_bytes",
    "stored_sha256",
    "recomputed_sha256",
    "matches",
)
SCORE_AUDIT_FIELDS = (
    "profile",
    "failure_law",
    "repetition",
    "mode",
    "scope",
    "source_placement",
    "target_placement",
    "method",
    "view",
    "operation",
    "prediction",
    "stored_test_requests",
    "recomputed_test_requests",
    "stored_test_successes",
    "recomputed_test_successes",
    "stored_test_success_fraction",
    "recomputed_test_success_fraction",
    "stored_brier_score",
    "recomputed_brier_score",
    "brier_difference",
    "stored_signed_prediction_error",
    "recomputed_signed_prediction_error",
    "signed_error_difference",
    "stored_absolute_prediction_error",
    "recomputed_absolute_prediction_error",
    "absolute_error_difference",
    "prediction_in_test_block_interval",
    "matches",
)
SUMMARY_AUDIT_FIELDS = (
    "scope",
    "mode",
    "view",
    "method",
    "stored_complete_campaigns",
    "recomputed_complete_campaigns",
    "stored_mean_brier_score",
    "recomputed_mean_brier_score",
    "brier_difference",
    "stored_mean_signed_prediction_error",
    "recomputed_mean_signed_prediction_error",
    "signed_error_difference",
    "stored_mean_absolute_prediction_error",
    "recomputed_mean_absolute_prediction_error",
    "absolute_error_difference",
    "stored_prediction_interval_compatibility_fraction",
    "recomputed_prediction_interval_compatibility_fraction",
    "compatibility_difference",
    "matches",
)
DISCREPANCY_FIELDS = (
    "id",
    "observation",
    "hypothesis",
    "test",
    "result",
    "status",
    "next_action",
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    fieldnames = tuple(fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _artifact_kind(name: str, source_run_id: str) -> str:
    suffix = f"-{source_run_id}"
    if not name.endswith(suffix):
        return "other_run_or_name"
    if name.startswith("m7-qualified-"):
        return "qualified_cell"
    if name.startswith("m7-raw-audit-sample-"):
        return "raw_audit_sample"
    if name == f"m7-frozen-analysis-{source_run_id}":
        return "analysis"
    return "other"


def load_artifact_inventory(path: str | Path, source_run_id: str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    pages = payload if isinstance(payload, list) else [payload]
    artifacts: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            raise M7DiagnosticError("artifact API payload contains a non-object page")
        page_artifacts = page.get("artifacts", [])
        if not isinstance(page_artifacts, list):
            raise M7DiagnosticError("artifact API page has a non-list artifacts field")
        artifacts.extend(page_artifacts)
    unique: dict[int, dict[str, Any]] = {}
    for artifact in artifacts:
        artifact_id = int(artifact["id"])
        if artifact_id in unique:
            raise M7DiagnosticError(f"duplicate artifact id {artifact_id}")
        unique[artifact_id] = artifact
    return [
        {
            "artifact_id": artifact_id,
            "name": str(item["name"]),
            "kind": _artifact_kind(str(item["name"]), source_run_id),
            "size_in_bytes": int(item["size_in_bytes"]),
            "expired": bool(item.get("expired", False)),
            "expires_at": str(item.get("expires_at", "")),
            "digest": str(item.get("digest") or ""),
        }
        for artifact_id, item in sorted(unique.items())
    ]


def inventory_files(groups: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, root in sorted(groups.items()):
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            rows.append(
                {
                    "evidence_group": group,
                    "relative_path": path.relative_to(root).as_posix(),
                    "size_in_bytes": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    return rows


def _find_analysis_directory(root: Path) -> Path:
    matches = []
    for manifest_path in root.rglob("manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if manifest.get("kind") == "frozen_live_validation_analysis":
            matches.append(manifest_path.parent)
    if len(matches) != 1:
        raise M7DiagnosticError(
            f"expected one frozen M7 analysis directory, found {len(matches)}"
        )
    return matches[0]


def audit_analysis_files(analysis_directory: Path) -> list[dict[str, Any]]:
    manifest = json.loads(
        (analysis_directory / "manifest.json").read_text(encoding="utf-8")
    )
    stored_files = manifest.get("files", {})
    rows = []
    for filename, manifest_key in (
        ("predictions.csv", "predictions_sha256"),
        ("scores.csv", "scores_sha256"),
        ("cell-diagnostics.csv", "cell_diagnostics_sha256"),
        ("contrasts.csv", "contrasts_sha256"),
        ("summary.csv", "summary_sha256"),
    ):
        path = analysis_directory / filename
        recomputed = file_sha256(path)
        stored = str(stored_files.get(manifest_key, ""))
        rows.append(
            {
                "filename": filename,
                "size_in_bytes": path.stat().st_size,
                "stored_sha256": stored,
                "recomputed_sha256": recomputed,
                "matches": stored == recomputed,
            }
        )
    return rows


def _source_identity(cell: QualifiedCell) -> tuple[str, str]:
    source = cell.boundary.get("source_provenance", {})
    environment = source.get("environment", {})
    run_id = str(environment.get("github", {}).get("GITHUB_RUN_ID", ""))
    commit = str(environment.get("git", {}).get("commit", ""))
    return run_id, commit


def audit_identities(
    config: FrozenLiveValidationConfig,
    cells: list[QualifiedCell],
    artifact_names: set[str],
    source_run_id: str,
) -> list[dict[str, Any]]:
    lookup = {cell.identity: cell for cell in cells}
    rows = []
    for item in frozen_live_matrix(config):
        identity = (
            str(item["profile"]),
            str(item["placement"]),
            str(item["law"]),
            int(item["repetition"]),
        )
        name = (
            f"m7-qualified-{identity[0]}-{identity[1]}-{identity[2]}-"
            f"r{identity[3]}-{source_run_id}"
        )
        cell = lookup.get(identity)
        run_id, commit = ("", "") if cell is None else _source_identity(cell)
        rows.append(
            {
                "profile": identity[0],
                "placement": identity[1],
                "failure_law": identity[2],
                "repetition": identity[3],
                "expected_artifact": name,
                "artifact_present": name in artifact_names,
                "qualified_cell_present": cell is not None,
                "source_run_id": run_id,
                "source_run_matches": run_id == source_run_id,
                "source_commit": commit,
            }
        )
    return rows


def _transition_times(cell: QualifiedCell) -> tuple[float, ...]:
    return tuple(
        current.at
        for previous, current in zip(cell.test_health, cell.test_health[1:])
        if current.signals != previous.signals
    )


def _is_guarded(at: float, transitions: tuple[float, ...], guard: int) -> bool:
    insertion = bisect_left(transitions, at)
    return any(
        abs(at - transitions[index]) <= guard
        for index in (insertion - 1, insertion)
        if 0 <= index < len(transitions)
    )


def outcome_counts(
    cells: Iterable[QualifiedCell], guard_seconds: int
) -> dict[tuple[Any, ...], tuple[int, int]]:
    result: dict[tuple[Any, ...], tuple[int, int]] = {}
    for cell in cells:
        transitions = _transition_times(cell)
        grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
        for request in cell.test_requests:
            grouped[("all_sequence", request.operation)].append(request.success)
            if not _is_guarded(request.at, transitions, guard_seconds):
                grouped[("stable", request.operation)].append(request.success)
                grouped[("stable_block_sensitivity", request.operation)].append(
                    request.success
                )
        for (view, operation), values in grouped.items():
            result[(*cell.identity, view, operation)] = (len(values), sum(values))
    return result


def audit_scores(
    score_rows: Iterable[dict[str, str]],
    counts: dict[tuple[Any, ...], tuple[int, int]],
    tolerance: float = 1e-12,
) -> list[dict[str, Any]]:
    audited = []
    for row in score_rows:
        key = (
            row["profile"],
            row["target_placement"],
            row["failure_law"],
            int(row["repetition"]),
            row["view"],
            row["operation"],
        )
        if key not in counts:
            raise M7DiagnosticError(f"score row has no matching test outcomes: {key}")
        requests, successes = counts[key]
        prediction = float(row["prediction"])
        rate = successes / requests
        brier = (
            successes * (prediction - 1.0) ** 2
            + (requests - successes) * prediction**2
        ) / requests
        signed = prediction - rate
        absolute = abs(signed)
        differences = (
            requests - int(row["test_requests"]),
            successes - int(row["test_successes"]),
            rate - float(row["test_success_fraction"]),
            brier - float(row["brier_score"]),
            signed - float(row["signed_prediction_error"]),
            absolute - float(row["absolute_prediction_error"]),
        )
        matches = differences[0] == 0 and differences[1] == 0 and all(
            abs(value) <= tolerance for value in differences[2:]
        )
        audited.append(
            {
                **{field: row[field] for field in SCORE_AUDIT_FIELDS if field in row},
                "repetition": int(row["repetition"]),
                "prediction": prediction,
                "stored_test_requests": int(row["test_requests"]),
                "recomputed_test_requests": requests,
                "stored_test_successes": int(row["test_successes"]),
                "recomputed_test_successes": successes,
                "stored_test_success_fraction": float(row["test_success_fraction"]),
                "recomputed_test_success_fraction": rate,
                "stored_brier_score": float(row["brier_score"]),
                "recomputed_brier_score": brier,
                "brier_difference": differences[3],
                "stored_signed_prediction_error": float(
                    row["signed_prediction_error"]
                ),
                "recomputed_signed_prediction_error": signed,
                "signed_error_difference": differences[4],
                "stored_absolute_prediction_error": float(
                    row["absolute_prediction_error"]
                ),
                "recomputed_absolute_prediction_error": absolute,
                "absolute_error_difference": differences[5],
                "prediction_in_test_block_interval": _bool(
                    row["prediction_in_test_block_interval"]
                ),
                "matches": matches,
            }
        )
    return audited


def _cell_metrics(
    rows: Iterable[dict[str, Any]], operation_counts: dict[str, int]
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
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
    for key, values in groups.items():
        if len(values) != operation_counts[str(key[0])]:
            continue
        result.append(
            {
                "profile": key[0],
                "failure_law": key[1],
                "repetition": key[2],
                "mode": key[3],
                "scope": key[4],
                "source_placement": key[5],
                "target_placement": key[6],
                "method": key[7],
                "view": key[8],
                "brier_score": fmean(
                    float(row["recomputed_brier_score"]) for row in values
                ),
                "signed_prediction_error": fmean(
                    float(row["recomputed_signed_prediction_error"])
                    for row in values
                ),
                "absolute_prediction_error": fmean(
                    float(row["recomputed_absolute_prediction_error"])
                    for row in values
                ),
                "compatibility": fmean(
                    float(bool(row["prediction_in_test_block_interval"]))
                    for row in values
                ),
            }
        )
    return result


def audit_summary(
    stored_rows: Iterable[dict[str, str]],
    cell_metrics: Iterable[dict[str, Any]],
    tolerance: float = 1e-12,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in cell_metrics:
        groups[(row["scope"], row["mode"], row["view"], row["method"])].append(
            row
        )
    stored = {
        (row["scope"], row["mode"], row["view"], row["method"]): row
        for row in stored_rows
    }
    if set(groups) != set(stored):
        raise M7DiagnosticError("stored and recomputed summary keys differ")
    audited = []
    for key, values in sorted(groups.items()):
        source = stored[key]
        recomputed = {
            "complete_campaigns": len(values),
            "mean_brier_score": fmean(float(row["brier_score"]) for row in values),
            "mean_signed_prediction_error": fmean(
                float(row["signed_prediction_error"]) for row in values
            ),
            "mean_absolute_prediction_error": fmean(
                float(row["absolute_prediction_error"]) for row in values
            ),
            "prediction_interval_compatibility_fraction": fmean(
                float(row["compatibility"]) for row in values
            ),
        }
        differences = {
            name: recomputed[name] - float(source[name])
            for name in (
                "mean_brier_score",
                "mean_signed_prediction_error",
                "mean_absolute_prediction_error",
                "prediction_interval_compatibility_fraction",
            )
        }
        matches = int(source["complete_campaigns"]) == recomputed[
            "complete_campaigns"
        ] and all(abs(value) <= tolerance for value in differences.values())
        audited.append(
            {
                "scope": key[0],
                "mode": key[1],
                "view": key[2],
                "method": key[3],
                "stored_complete_campaigns": int(source["complete_campaigns"]),
                "recomputed_complete_campaigns": recomputed["complete_campaigns"],
                "stored_mean_brier_score": float(source["mean_brier_score"]),
                "recomputed_mean_brier_score": recomputed["mean_brier_score"],
                "brier_difference": differences["mean_brier_score"],
                "stored_mean_signed_prediction_error": float(
                    source["mean_signed_prediction_error"]
                ),
                "recomputed_mean_signed_prediction_error": recomputed[
                    "mean_signed_prediction_error"
                ],
                "signed_error_difference": differences[
                    "mean_signed_prediction_error"
                ],
                "stored_mean_absolute_prediction_error": float(
                    source["mean_absolute_prediction_error"]
                ),
                "recomputed_mean_absolute_prediction_error": recomputed[
                    "mean_absolute_prediction_error"
                ],
                "absolute_error_difference": differences[
                    "mean_absolute_prediction_error"
                ],
                "stored_prediction_interval_compatibility_fraction": float(
                    source["prediction_interval_compatibility_fraction"]
                ),
                "recomputed_prediction_interval_compatibility_fraction": recomputed[
                    "prediction_interval_compatibility_fraction"
                ],
                "compatibility_difference": differences[
                    "prediction_interval_compatibility_fraction"
                ],
                "matches": matches,
            }
        )
    return audited


def _stratified_inference(
    values_by_stratum: dict[tuple[Any, ...], list[float]], confidence: float
) -> dict[str, float]:
    nonempty = {key: values for key, values in values_by_stratum.items() if values}
    means = [fmean(values) for values in nonempty.values()]
    estimate = fmean(means)
    strata = len(nonempty)
    variance_terms = []
    denominator_terms = []
    for values in nonempty.values():
        if len(values) < 2:
            continue
        term = variance(values) / len(values) / strata**2
        variance_terms.append(term)
        denominator_terms.append(term**2 / (len(values) - 1))
    total_variance = sum(variance_terms)
    standard_error = math.sqrt(total_variance)
    degrees = (
        total_variance**2 / sum(denominator_terms)
        if denominator_terms and sum(denominator_terms) > 0
        else math.inf
    )
    critical = float(t.ppf(0.5 + confidence / 2, degrees))
    p_value = (
        2 * float(t.sf(abs(estimate / standard_error), degrees))
        if standard_error > 0
        else (1.0 if estimate == 0 else 0.0)
    )
    return {
        "campaigns": sum(len(values) for values in nonempty.values()),
        "strata": strata,
        "estimate": estimate,
        "standard_error": standard_error,
        "degrees_of_freedom": degrees,
        "confidence_lower": estimate - critical * standard_error,
        "confidence_upper": estimate + critical * standard_error,
        "two_sided_p_value": p_value,
    }


def audit_primary_contrast(
    config: FrozenLiveValidationConfig,
    cell_metrics: Iterable[dict[str, Any]],
    contrast_rows: Iterable[dict[str, str]],
    tolerance: float = 1e-12,
) -> dict[str, Any]:
    primary = next(row for row in contrast_rows if _bool(row["primary"]))
    filtered = [
        row
        for row in cell_metrics
        if row["scope"] == "current"
        and row["mode"] == config.analysis.primary_mode
        and row["view"] == config.analysis.primary_view
        and row["method"] in {"proposed", "B2"}
    ]
    lookup = {
        (
            row["profile"],
            row["failure_law"],
            row["repetition"],
            row["source_placement"],
            row["target_placement"],
            row["method"],
        ): row
        for row in filtered
    }
    values: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for row in filtered:
        if row["method"] != "proposed":
            continue
        pair_key = (
            row["profile"],
            row["failure_law"],
            row["repetition"],
            row["source_placement"],
            row["target_placement"],
            "B2",
        )
        paired = lookup.get(pair_key)
        if paired is None:
            continue
        stratum = (row["profile"], row["target_placement"], row["failure_law"])
        values[stratum].append(float(row["brier_score"]) - float(paired["brier_score"]))
    recomputed = _stratified_inference(values, config.analysis.confidence_level)
    comparisons = {}
    for field in (
        "campaigns",
        "strata",
        "estimate",
        "standard_error",
        "degrees_of_freedom",
        "confidence_lower",
        "confidence_upper",
        "two_sided_p_value",
    ):
        stored_value: float | int
        if field in {"campaigns", "strata"}:
            stored_value = int(primary[field])
            matches = stored_value == recomputed[field]
        else:
            stored_value = float(primary[field])
            matches = abs(stored_value - recomputed[field]) <= tolerance
        comparisons[field] = {
            "stored": stored_value,
            "recomputed": recomputed[field],
            "difference": recomputed[field] - stored_value,
            "matches": matches,
        }
    return {
        "scope": primary["scope"],
        "mode": primary["mode"],
        "view": primary["view"],
        "contrast": primary["contrast"],
        "complete": _bool(primary["complete"]),
        "comparisons": comparisons,
        "matches": all(item["matches"] for item in comparisons.values()),
    }


def _initial_discrepancy_rows(quality: dict[str, int]) -> list[dict[str, Any]]:
    identity_ok = quality["identity_mismatches"] == 0
    arithmetic_ok = (
        quality["score_mismatches"] == 0
        and quality["summary_mismatches"] == 0
        and quality["primary_contrast_mismatches"] == 0
    )
    return [
        {
            "id": "D01",
            "observation": "The M7 primary result used only 117 of 160 campaigns.",
            "hypothesis": "Campaign or placement identifiers were mismatched.",
            "test": "Match the frozen 160-cell matrix, artifact names, cell identities, and source run.",
            "result": "No mismatch found." if identity_ok else "Mismatch found; inspect identity-audit.csv.",
            "status": "not_supported" if identity_ok else "supported",
            "next_action": "Diagnose topology abstention." if identity_ok else "Repair only affected identity joins.",
        },
        {
            "id": "D02",
            "observation": "M7 showed no established Brier-score gain over strengthened B2.",
            "hypothesis": "A denominator, Bernoulli Brier formula, or aggregation-weight error caused the result.",
            "test": "Recompute every score from sequestered request outcomes, then repeat operation, campaign, and equal-stratum aggregation.",
            "result": "No arithmetic discrepancy found." if arithmetic_ok else "Arithmetic discrepancy found; inspect audit tables.",
            "status": "not_supported" if arithmetic_ok else "supported",
            "next_action": "Decompose observed prediction bias." if arithmetic_ok else "Repair only affected calculations and version the correction.",
        },
        {
            "id": "D03",
            "observation": "Both proposed and B2 overpredicted independent test success in the published analysis.",
            "hypothesis": "Baseline residual, injected calibration, or transfer assumptions account for the signed bias.",
            "test": "Decompose baseline, calibration, prediction, and test rates by application, operation, law, and placement.",
            "result": "Not tested in M8A.",
            "status": "unresolved",
            "next_action": "Run M8B bias decomposition without tuning a filter to the outcome.",
        },
        {
            "id": "D04",
            "observation": "Communication-law cells frequently crossed the frozen topology ambiguity band.",
            "hypothesis": "Conditional paths, fallback, partial span delivery, trace boundaries, or replica assignment explain the mixed support.",
            "test": "Inspect normalized examples and replay the parser for the four retained raw samples.",
            "result": "Not tested in M8A.",
            "status": "unresolved",
            "next_action": "Run M8B topology and raw-trace diagnostics.",
        },
        {
            "id": "D05",
            "observation": "Stable and all-sequence results differ in their retained requests.",
            "hypothesis": "Alignment, transition, timeout, or HTTP-2xx semantic failures explain part of the discrepancy.",
            "test": "Audit the entire temporal sequence and the four retained raw semantic samples.",
            "result": "Not tested in M8A.",
            "status": "unresolved",
            "next_action": "Run M8B temporal and semantic diagnostics.",
        },
    ]


def run_m7_diagnostic_audit(
    config: FrozenLiveValidationConfig,
    artifact_json: str | Path,
    qualified_root: str | Path,
    analysis_root: str | Path,
    raw_root: str | Path,
    output_directory: str | Path,
    source_run_id: str,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise M7DiagnosticError("full M7 diagnostics may run only in GitHub Actions")
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    qualified_path = Path(qualified_root)
    analysis_path = Path(analysis_root)
    raw_path = Path(raw_root)

    artifacts = load_artifact_inventory(artifact_json, source_run_id)
    _write_csv(output / "artifact-inventory.csv", ARTIFACT_FIELDS, artifacts)
    files = inventory_files(
        {
            "analysis": analysis_path,
            "qualified": qualified_path,
            "raw_audit_sample": raw_path,
        }
    )
    _write_csv(output / "file-inventory.csv", FILE_FIELDS, files)

    cells = discover_qualified_cells(qualified_path)
    analysis_directory = _find_analysis_directory(analysis_path)
    artifact_names = {str(row["name"]) for row in artifacts}
    identities = audit_identities(config, cells, artifact_names, source_run_id)
    _write_csv(output / "identity-audit.csv", IDENTITY_FIELDS, identities)
    analysis_files = audit_analysis_files(analysis_directory)
    _write_csv(
        output / "analysis-file-audit.csv", ANALYSIS_FILE_FIELDS, analysis_files
    )

    scores = _rows(analysis_directory / "scores.csv")
    counts = outcome_counts(cells, config.analysis.transition_guard_seconds_each_side)
    score_audit = audit_scores(scores, counts)
    _write_csv(output / "score-recalculation.csv", SCORE_AUDIT_FIELDS, score_audit)
    operation_counts = {
        profile: len(operations)
        for profile, operations in config.analysis.operations.items()
    }
    cell_metrics = _cell_metrics(score_audit, operation_counts)
    summary_audit = audit_summary(
        _rows(analysis_directory / "summary.csv"), cell_metrics
    )
    _write_csv(output / "summary-recalculation.csv", SUMMARY_AUDIT_FIELDS, summary_audit)
    primary = audit_primary_contrast(
        config, cell_metrics, _rows(analysis_directory / "contrasts.csv")
    )
    (output / "primary-contrast-recalculation.json").write_text(
        json.dumps(primary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    category_counts = {
        kind: sum(row["kind"] == kind for row in artifacts)
        for kind in ("qualified_cell", "raw_audit_sample", "analysis")
    }
    quality = {
        "artifact_total_mismatches": int(len(artifacts) != 165),
        "qualified_artifact_count_mismatches": int(
            category_counts["qualified_cell"] != config.expected_cells
        ),
        "raw_artifact_count_mismatches": int(
            category_counts["raw_audit_sample"] != 4
        ),
        "analysis_artifact_count_mismatches": int(category_counts["analysis"] != 1),
        "unexpected_artifacts": sum(
            row["kind"] not in {"qualified_cell", "raw_audit_sample", "analysis"}
            for row in artifacts
        ),
        "expired_artifacts": sum(bool(row["expired"]) for row in artifacts),
        "qualified_cell_count_mismatches": int(len(cells) != config.expected_cells),
        "identity_mismatches": sum(
            not bool(row["artifact_present"])
            or not bool(row["qualified_cell_present"])
            or not bool(row["source_run_matches"])
            for row in identities
        ),
        "source_commit_count_mismatches": int(
            len({row["source_commit"] for row in identities}) != 1
        ),
        "analysis_file_hash_mismatches": sum(
            not bool(row["matches"]) for row in analysis_files
        ),
        "score_mismatches": sum(not bool(row["matches"]) for row in score_audit),
        "summary_mismatches": sum(
            not bool(row["matches"]) for row in summary_audit
        ),
        "primary_contrast_mismatches": int(not primary["matches"]),
    }
    discrepancies = _initial_discrepancy_rows(quality)
    _write_csv(
        output / "discrepancy-register.csv", DISCREPANCY_FIELDS, discrepancies
    )

    manifest = {
        "schema_version": 1,
        "kind": "m7_posthoc_integrity_and_arithmetic_diagnostic",
        "diagnostic_only": True,
        "changes_m7_predictions_or_scores": False,
        "source_run_id": source_run_id,
        "source_analysis_directory": analysis_directory.name,
        "artifact_counts": category_counts,
        "row_counts": {
            "artifacts": len(artifacts),
            "inventoried_files": len(files),
            "identities": len(identities),
            "score_recalculations": len(score_audit),
            "summary_recalculations": len(summary_audit),
            "discrepancies": len(discrepancies),
        },
        "quality": quality,
        "primary_contrast_recalculation": primary,
        "interpretation_boundary": (
            "This audit can reject integrity and arithmetic explanations. It does "
            "not establish why predictions or topology support disagreed with "
            "observations, and does not decide whether the overall approach succeeds."
        ),
        "files": {
            path.name: file_sha256(path)
            for path in sorted(output.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
        "environment": environment_manifest(),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failures = {name: value for name, value in quality.items() if value}
    if failures:
        raise M7DiagnosticError(f"M8A diagnostic acceptance failures: {failures}")
    return manifest
