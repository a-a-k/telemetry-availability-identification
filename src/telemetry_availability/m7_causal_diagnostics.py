from __future__ import annotations

import json
import math
import os
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

from .live_evidence import qualify_evidence_cell
from .live_evidence_config import EvidenceBoundaryConfig
from .live_validation_analysis import (
    QualifiedCell,
    discover_qualified_cells,
    infer_topology,
)
from .live_validation_config import FrozenLiveValidationConfig
from .m7_diagnostic_analysis import (
    M7DiagnosticError,
    _bool,
    _find_analysis_directory,
    _rows,
    _write_csv,
)
from .provenance import environment_manifest, file_sha256


PERIOD_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "operation",
    "period_view",
    "requests",
    "semantic_successes",
    "success_rate",
    "timeouts",
    "timeout_fraction",
    "trace_fields_available",
    "successful_traces",
    "successful_traces_with_target",
    "successful_traces_without_target",
    "successful_trace_target_fraction",
)
BIAS_DETAIL_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "operation",
    "method",
    "prediction_status",
    "prediction",
    "route_prediction",
    "residual_success_probability",
    "baseline_requests",
    "baseline_rate",
    "calibration_requests",
    "calibration_rate",
    "test_all_requests",
    "test_all_rate",
    "test_stable_requests",
    "test_stable_rate",
    "calibration_minus_test_stable",
    "baseline_minus_test_stable",
    "prediction_minus_test_stable",
    "stable_brier_score",
)
BIAS_STRATUM_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "operation",
    "method",
    "expected_campaigns",
    "emitted_campaigns",
    "mean_baseline_rate",
    "mean_calibration_rate",
    "mean_prediction",
    "mean_test_all_rate",
    "mean_test_stable_rate",
    "mean_calibration_minus_test_stable",
    "mean_baseline_minus_test_stable",
    "mean_prediction_minus_test_stable",
    "mean_stable_brier_score",
)
TEMPORAL_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "operation",
    "test_requests",
    "stable_requests",
    "transition_guarded_requests",
    "unaligned_requests",
    "test_success_rate",
    "stable_success_rate",
    "guarded_success_rate",
    "stable_minus_all_success_rate",
    "test_timeouts",
    "stable_timeouts",
    "guarded_timeouts",
    "health_transitions",
)
TRANSITION_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "operation",
    "transition_direction",
    "phase",
    "distance_band",
    "requests",
    "semantic_successes",
    "success_rate",
    "timeouts",
    "timeout_fraction",
)
TOPOLOGY_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "mode",
    "operation",
    "expected_requires_target",
    "inferred_requires_target",
    "status",
    "trace_support",
    "target_trace_fraction",
    "replica_a_assignments",
    "replica_b_assignments",
)
TOPOLOGY_BRANCH_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "operation",
    "branch_class",
    "successful_requests",
    "successful_traces",
    "successful_traces_with_target",
    "successful_traces_without_target",
    "successful_trace_target_fraction",
    "successful_requests_without_trace",
)
TOPOLOGY_EXAMPLE_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "operation",
    "evidence_class",
    "request_id",
    "period",
    "branch_class",
    "span_count",
    "services",
    "target_replicas",
)
RAW_SEMANTIC_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "period",
    "operation",
    "requests",
    "http_2xx",
    "immediate_successes",
    "semantic_successes",
    "http_2xx_semantic_failures",
    "immediate_semantic_disagreements",
    "timeouts",
    "non_2xx",
    "transport_errors",
)
SEMANTIC_REASON_FIELDS = (
    "profile",
    "placement",
    "period",
    "operation",
    "status_code",
    "semantic_success",
    "semantic_reason",
    "count",
)
REPLAY_FIELDS = (
    "profile",
    "placement",
    "failure_law",
    "repetition",
    "filename",
    "original_sha256",
    "replayed_sha256",
    "matches",
    "error",
)
DISCREPANCY_FIELDS = (
    "id",
    "observation",
    "hypothesis",
    "test",
    "result",
    "status",
    "interpretation_limit",
)


def _timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _float_or_blank(value: Any) -> float | str:
    return "" if value in {None, ""} else float(value)


def _rate(successes: int, requests: int) -> float | str:
    return successes / requests if requests else ""


def _cell_rows(cell: QualifiedCell) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    return (
        _rows(cell.directory / "learner" / "requests.csv"),
        _rows(cell.directory / "evaluator" / "test-requests.csv"),
    )


def _transitions(cell: QualifiedCell) -> list[dict[str, Any]]:
    result = []
    for previous, current in zip(cell.test_health, cell.test_health[1:]):
        if previous.signals == current.signals:
            continue
        before_route = int(bool(previous.signals[2] or previous.signals[3]))
        after_route = int(bool(current.signals[2] or current.signals[3]))
        if before_route > after_route:
            direction = "route_degradation"
        elif before_route < after_route:
            direction = "route_recovery"
        else:
            direction = "other_signal_change"
        result.append({"at": current.at, "direction": direction})
    return result


def _nearest_index(value: float, ordered: tuple[float, ...]) -> tuple[int, float]:
    if not ordered:
        return -1, math.inf
    insertion = bisect_left(ordered, value)
    candidates = [
        index
        for index in (insertion - 1, insertion)
        if 0 <= index < len(ordered)
    ]
    index = min(candidates, key=lambda item: abs(value - ordered[item]))
    return index, abs(value - ordered[index])


def _period_summary(
    cell: QualifiedCell,
    operation: str,
    period_view: str,
    rows: list[dict[str, str]],
    trace_fields: bool,
) -> dict[str, Any]:
    successes = sum(_bool(row["semantic_success"]) for row in rows)
    timeouts = sum(_bool(row.get("timed_out", "")) for row in rows)
    successful_traces = 0
    with_target = 0
    without_target = 0
    if trace_fields:
        traced_rows = [
            row
            for row in rows
            if _bool(row["semantic_success"])
            and _bool(row["trace_present"])
            and int(row["span_count"]) > 0
        ]
        successful_traces = len(traced_rows)
        with_target = sum(
            cell.target_service in set(filter(None, row["services"].split(";")))
            for row in traced_rows
        )
        without_target = successful_traces - with_target
    return {
        "profile": cell.profile,
        "placement": cell.placement,
        "failure_law": cell.failure_law,
        "repetition": cell.repetition,
        "operation": operation,
        "period_view": period_view,
        "requests": len(rows),
        "semantic_successes": successes,
        "success_rate": _rate(successes, len(rows)),
        "timeouts": timeouts,
        "timeout_fraction": _rate(timeouts, len(rows)),
        "trace_fields_available": trace_fields,
        "successful_traces": successful_traces if trace_fields else "",
        "successful_traces_with_target": with_target if trace_fields else "",
        "successful_traces_without_target": without_target if trace_fields else "",
        "successful_trace_target_fraction": (
            _rate(with_target, successful_traces) if trace_fields else ""
        ),
    }


def period_rate_rows(
    cells: Iterable[QualifiedCell], config: FrozenLiveValidationConfig
) -> list[dict[str, Any]]:
    result = []
    guard = config.analysis.transition_guard_seconds_each_side
    for cell in cells:
        learner, test = _cell_rows(cell)
        transitions = tuple(item["at"] for item in _transitions(cell))
        operations = [item.id for item in config.analysis.operations[cell.profile]]
        for operation in operations:
            for period in ("baseline", "calibration"):
                selected = [
                    row
                    for row in learner
                    if row["operation"] == operation and row["period"] == period
                ]
                result.append(
                    _period_summary(cell, operation, period, selected, True)
                )
            operation_test = [row for row in test if row["operation"] == operation]
            stable = [
                row
                for row in operation_test
                if _nearest_index(_timestamp(row["started_at"]), transitions)[1] > guard
            ]
            guarded = [
                row
                for row in operation_test
                if _nearest_index(_timestamp(row["started_at"]), transitions)[1] <= guard
            ]
            for view, selected in (
                ("test_all", operation_test),
                ("test_stable", stable),
                ("test_transition_guarded", guarded),
            ):
                result.append(
                    _period_summary(cell, operation, view, selected, False)
                )
    return result


def bias_rows(
    cells: list[QualifiedCell],
    analysis_directory: Path,
    periods: list[dict[str, Any]],
    config: FrozenLiveValidationConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    period_lookup = {
        (
            row["profile"],
            row["placement"],
            row["failure_law"],
            int(row["repetition"]),
            row["operation"],
            row["period_view"],
        ): row
        for row in periods
    }
    scores = {
        (
            row["profile"],
            row["target_placement"],
            row["failure_law"],
            int(row["repetition"]),
            row["operation"],
            row["method"],
            row["view"],
        ): row
        for row in _rows(analysis_directory / "scores.csv")
        if row["mode"] == config.analysis.primary_mode and row["scope"] == "current"
    }
    details = []
    for row in _rows(analysis_directory / "predictions.csv"):
        if (
            row["mode"] != config.analysis.primary_mode
            or row["scope"] != "current"
            or row["method"] not in {"B0", "B2", "proposed"}
        ):
            continue
        identity = (
            row["profile"],
            row["target_placement"],
            row["failure_law"],
            int(row["repetition"]),
            row["operation"],
        )
        baseline = period_lookup[(*identity, "baseline")]
        calibration = period_lookup[(*identity, "calibration")]
        test_all = period_lookup[(*identity, "test_all")]
        test_stable = period_lookup[(*identity, "test_stable")]
        prediction = _float_or_blank(row["prediction"])
        stable_score = scores.get((*identity, row["method"], "stable"))
        stable_rate = float(test_stable["success_rate"])
        details.append(
            {
                "profile": identity[0],
                "placement": identity[1],
                "failure_law": identity[2],
                "repetition": identity[3],
                "operation": identity[4],
                "method": row["method"],
                "prediction_status": row["status"],
                "prediction": prediction,
                "route_prediction": _float_or_blank(row["route_prediction"]),
                "residual_success_probability": _float_or_blank(
                    row["residual_success_probability"]
                ),
                "baseline_requests": baseline["requests"],
                "baseline_rate": baseline["success_rate"],
                "calibration_requests": calibration["requests"],
                "calibration_rate": calibration["success_rate"],
                "test_all_requests": test_all["requests"],
                "test_all_rate": test_all["success_rate"],
                "test_stable_requests": test_stable["requests"],
                "test_stable_rate": test_stable["success_rate"],
                "calibration_minus_test_stable": float(
                    calibration["success_rate"]
                )
                - stable_rate,
                "baseline_minus_test_stable": float(baseline["success_rate"])
                - stable_rate,
                "prediction_minus_test_stable": (
                    "" if prediction == "" else float(prediction) - stable_rate
                ),
                "stable_brier_score": (
                    "" if stable_score is None else float(stable_score["brier_score"])
                ),
            }
        )
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        groups[
            (
                row["profile"],
                row["placement"],
                row["failure_law"],
                row["operation"],
                row["method"],
            )
        ].append(row)
    strata = []
    for key, rows in sorted(groups.items()):
        emitted = [row for row in rows if row["prediction"] != ""]

        def mean(field: str, selected: list[dict[str, Any]] = emitted) -> float | str:
            values = [float(row[field]) for row in selected if row[field] != ""]
            return fmean(values) if values else ""

        strata.append(
            {
                "profile": key[0],
                "placement": key[1],
                "failure_law": key[2],
                "operation": key[3],
                "method": key[4],
                "expected_campaigns": config.repetitions,
                "emitted_campaigns": len(emitted),
                "mean_baseline_rate": mean("baseline_rate", rows),
                "mean_calibration_rate": mean("calibration_rate", rows),
                "mean_prediction": mean("prediction"),
                "mean_test_all_rate": mean("test_all_rate", rows),
                "mean_test_stable_rate": mean("test_stable_rate", rows),
                "mean_calibration_minus_test_stable": mean(
                    "calibration_minus_test_stable", rows
                ),
                "mean_baseline_minus_test_stable": mean(
                    "baseline_minus_test_stable", rows
                ),
                "mean_prediction_minus_test_stable": mean(
                    "prediction_minus_test_stable"
                ),
                "mean_stable_brier_score": mean("stable_brier_score"),
            }
        )
    return details, strata


def temporal_rows(
    cells: Iterable[QualifiedCell], config: FrozenLiveValidationConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    campaign_rows = []
    window_rows = []
    guard = config.analysis.transition_guard_seconds_each_side
    tolerance = config.analysis.health_alignment_tolerance_seconds
    for cell in cells:
        _, test = _cell_rows(cell)
        transitions = _transitions(cell)
        transition_times = tuple(item["at"] for item in transitions)
        health_times = tuple(item.at for item in cell.test_health)
        operations = [item.id for item in config.analysis.operations[cell.profile]]
        for operation in operations:
            rows = [row for row in test if row["operation"] == operation]
            stable = []
            guarded = []
            unaligned = 0
            windows: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
            for row in rows:
                at = _timestamp(row["started_at"])
                _, alignment_distance = _nearest_index(at, health_times)
                unaligned += int(alignment_distance > tolerance)
                transition_index, distance = _nearest_index(at, transition_times)
                if distance <= guard:
                    guarded.append(row)
                else:
                    stable.append(row)
                if transition_index < 0:
                    direction = "no_transition"
                    phase = "none"
                else:
                    transition = transitions[transition_index]
                    direction = str(transition["direction"])
                    phase = "after" if at >= float(transition["at"]) else "before"
                if distance <= 1:
                    band = "00_within_1s"
                elif distance <= 5:
                    band = "01_1_to_5s"
                elif distance <= 15:
                    band = "02_5_to_15s"
                else:
                    band = "03_over_15s_or_none"
                windows[(direction, phase, band)].append(row)

            def successes(selected: list[dict[str, str]]) -> int:
                return sum(_bool(row["semantic_success"]) for row in selected)

            def timeouts(selected: list[dict[str, str]]) -> int:
                return sum(_bool(row.get("timed_out", "")) for row in selected)

            all_rate = _rate(successes(rows), len(rows))
            stable_rate = _rate(successes(stable), len(stable))
            guarded_rate = _rate(successes(guarded), len(guarded))
            campaign_rows.append(
                {
                    "profile": cell.profile,
                    "placement": cell.placement,
                    "failure_law": cell.failure_law,
                    "repetition": cell.repetition,
                    "operation": operation,
                    "test_requests": len(rows),
                    "stable_requests": len(stable),
                    "transition_guarded_requests": len(guarded),
                    "unaligned_requests": unaligned,
                    "test_success_rate": all_rate,
                    "stable_success_rate": stable_rate,
                    "guarded_success_rate": guarded_rate,
                    "stable_minus_all_success_rate": (
                        float(stable_rate) - float(all_rate)
                        if stable_rate != "" and all_rate != ""
                        else ""
                    ),
                    "test_timeouts": timeouts(rows),
                    "stable_timeouts": timeouts(stable),
                    "guarded_timeouts": timeouts(guarded),
                    "health_transitions": len(transitions),
                }
            )
            for (direction, phase, band), selected in sorted(windows.items()):
                success_count = successes(selected)
                timeout_count = timeouts(selected)
                window_rows.append(
                    {
                        "profile": cell.profile,
                        "placement": cell.placement,
                        "failure_law": cell.failure_law,
                        "repetition": cell.repetition,
                        "operation": operation,
                        "transition_direction": direction,
                        "phase": phase,
                        "distance_band": band,
                        "requests": len(selected),
                        "semantic_successes": success_count,
                        "success_rate": _rate(success_count, len(selected)),
                        "timeouts": timeout_count,
                        "timeout_fraction": _rate(timeout_count, len(selected)),
                    }
                )
    return campaign_rows, window_rows


def topology_rows(
    cells: Iterable[QualifiedCell], config: FrozenLiveValidationConfig
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    diagnostics = []
    branches = []
    examples = []
    for cell in cells:
        operations = config.analysis.operations[cell.profile]
        for mode in config.analysis.modes:
            inferred, _ = infer_topology(cell, mode, operations, config.analysis)
            for operation in operations:
                item = inferred[operation.id]
                diagnostics.append(
                    {
                        "profile": cell.profile,
                        "placement": cell.placement,
                        "failure_law": cell.failure_law,
                        "repetition": cell.repetition,
                        "mode": mode.id,
                        "operation": operation.id,
                        "expected_requires_target": operation.requires_target_group,
                        "inferred_requires_target": (
                            ""
                            if item.inferred_requires_target is None
                            else item.inferred_requires_target
                        ),
                        "status": item.status,
                        "trace_support": item.trace_support,
                        "target_trace_fraction": item.target_trace_fraction,
                        "replica_a_assignments": item.replica_a_assignments,
                        "replica_b_assignments": item.replica_b_assignments,
                    }
                )
        learner, _ = _cell_rows(cell)
        eligible = [row for row in learner if row["period"] in {"baseline", "calibration"}]
        grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in eligible:
            grouped[(row["period"], row["operation"], row["branch_class"])].append(row)
        for (period, operation, branch), rows in sorted(grouped.items()):
            successful = [row for row in rows if _bool(row["semantic_success"])]
            traced = [
                row
                for row in successful
                if _bool(row["trace_present"]) and int(row["span_count"]) > 0
            ]
            with_target = [
                row
                for row in traced
                if cell.target_service
                in set(filter(None, row["services"].split(";")))
            ]
            without_target = [
                row
                for row in traced
                if cell.target_service
                not in set(filter(None, row["services"].split(";")))
            ]
            branches.append(
                {
                    "profile": cell.profile,
                    "placement": cell.placement,
                    "failure_law": cell.failure_law,
                    "repetition": cell.repetition,
                    "period": period,
                    "operation": operation,
                    "branch_class": branch,
                    "successful_requests": len(successful),
                    "successful_traces": len(traced),
                    "successful_traces_with_target": len(with_target),
                    "successful_traces_without_target": len(without_target),
                    "successful_trace_target_fraction": _rate(
                        len(with_target), len(traced)
                    ),
                    "successful_requests_without_trace": len(successful) - len(traced),
                }
            )
        by_operation: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in eligible:
            by_operation[row["operation"]].append(row)
        for operation, rows in sorted(by_operation.items()):
            successful = [row for row in rows if _bool(row["semantic_success"])]
            classes = {
                "target_present": [
                    row
                    for row in successful
                    if _bool(row["trace_present"])
                    and int(row["span_count"]) > 0
                    and cell.target_service
                    in set(filter(None, row["services"].split(";")))
                ],
                "target_absent": [
                    row
                    for row in successful
                    if _bool(row["trace_present"])
                    and int(row["span_count"]) > 0
                    and cell.target_service
                    not in set(filter(None, row["services"].split(";")))
                ],
                "successful_no_trace": [
                    row
                    for row in successful
                    if not _bool(row["trace_present"]) or int(row["span_count"]) <= 0
                ],
            }
            for evidence_class, candidates in classes.items():
                if not candidates:
                    continue
                row = min(candidates, key=lambda item: item["request_id"])
                examples.append(
                    {
                        "profile": cell.profile,
                        "placement": cell.placement,
                        "failure_law": cell.failure_law,
                        "repetition": cell.repetition,
                        "operation": operation,
                        "evidence_class": evidence_class,
                        "request_id": row["request_id"],
                        "period": row["period"],
                        "branch_class": row["branch_class"],
                        "span_count": row["span_count"],
                        "services": row["services"],
                        "target_replicas": row["target_replicas"],
                    }
                )
    return diagnostics, branches, examples


def raw_semantic_rows(
    raw_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Path]]:
    request_paths = sorted(raw_root.rglob("requests.csv"))
    summaries = []
    reason_counts: Counter[tuple[str, ...]] = Counter()
    for path in request_paths:
        rows = _rows(path)
        groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[
                (
                    row["profile"],
                    row["placement"],
                    row["failure_law"],
                    row["repetition"],
                    row["period"],
                    row["operation"],
                )
            ].append(row)
            reason_counts[
                (
                    row["profile"],
                    row["placement"],
                    row["period"],
                    row["operation"],
                    row["status_code"],
                    str(_bool(row["semantic_success"])).lower(),
                    row["semantic_reason"],
                )
            ] += 1
        for key, values in sorted(groups.items()):
            status_codes = [
                int(row["status_code"]) for row in values if row["status_code"]
            ]
            http_2xx = sum(200 <= status < 300 for status in status_codes)
            immediate = sum(_bool(row["immediate_success"]) for row in values)
            semantic = sum(_bool(row["semantic_success"]) for row in values)
            summaries.append(
                {
                    "profile": key[0],
                    "placement": key[1],
                    "failure_law": key[2],
                    "repetition": int(key[3]),
                    "period": key[4],
                    "operation": key[5],
                    "requests": len(values),
                    "http_2xx": http_2xx,
                    "immediate_successes": immediate,
                    "semantic_successes": semantic,
                    "http_2xx_semantic_failures": sum(
                        bool(row["status_code"])
                        and 200 <= int(row["status_code"]) < 300
                        and not _bool(row["semantic_success"])
                        for row in values
                    ),
                    "immediate_semantic_disagreements": sum(
                        _bool(row["immediate_success"])
                        != _bool(row["semantic_success"])
                        for row in values
                    ),
                    "timeouts": sum(_bool(row["timed_out"]) for row in values),
                    "non_2xx": len(status_codes) - http_2xx,
                    "transport_errors": sum(bool(row["error"]) for row in values),
                }
            )
    reasons = [
        {
            "profile": key[0],
            "placement": key[1],
            "period": key[2],
            "operation": key[3],
            "status_code": key[4],
            "semantic_success": key[5],
            "semantic_reason": key[6],
            "count": count,
        }
        for key, count in sorted(reason_counts.items())
    ]
    return summaries, reasons, request_paths


def replay_raw_samples(
    raw_root: Path,
    replay_root: Path,
    cells: list[QualifiedCell],
    evidence_config: EvidenceBoundaryConfig,
) -> list[dict[str, Any]]:
    lookup = {cell.identity: cell for cell in cells}
    rows = []
    filenames = (
        "cell-summary.json",
        "audit/boundary.json",
        "learner/manifest.json",
        "learner/deployment.json",
        "learner/requests.csv",
        "learner/health.csv",
        "learner/topology-edges.csv",
        "evaluator/test-requests.csv",
        "evaluator/test-health.csv",
    )
    for manifest_path in sorted(raw_root.rglob("pilot-manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        identity = (
            str(manifest["profile"]),
            str(manifest["placement"]),
            str(manifest["failure_law"]),
            int(manifest["repetition"]),
        )
        destination = replay_root / identity[0] / identity[1] / identity[2] / f"r{identity[3]}"
        original = lookup.get(identity)
        error = ""
        try:
            qualify_evidence_cell(evidence_config, manifest_path.parent, destination)
        except Exception as caught:  # keep the diagnostic artifact on replay failure
            error = f"{type(caught).__name__}: {caught}"
        for filename in filenames:
            original_path = None if original is None else original.directory / filename
            replayed_path = destination / filename
            original_hash = (
                file_sha256(original_path)
                if original_path is not None and original_path.is_file()
                else ""
            )
            replayed_hash = file_sha256(replayed_path) if replayed_path.is_file() else ""
            rows.append(
                {
                    "profile": identity[0],
                    "placement": identity[1],
                    "failure_law": identity[2],
                    "repetition": identity[3],
                    "filename": filename,
                    "original_sha256": original_hash,
                    "replayed_sha256": replayed_hash,
                    "matches": bool(original_hash) and original_hash == replayed_hash,
                    "error": error,
                }
            )
    return rows


def _discrepancy_rows(
    replay: list[dict[str, Any]], temporal: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    replay_mismatches = sum(not row["matches"] for row in replay)
    unaligned = sum(int(row["unaligned_requests"]) for row in temporal)
    return [
        {
            "id": "D03",
            "observation": "Both proposed and B2 overpredicted independent M7 test success on average.",
            "hypothesis": "The discrepancy enters at clean residual estimation, injected calibration, or model prediction.",
            "test": "Decompose all fixed stages by application, operation, law, and placement.",
            "result": "bias-detail.csv and bias-strata.csv record the decomposition.",
            "status": "evidence_generated_cause_not_assigned",
            "interpretation_limit": "Observed stage gaps are associations and do not alone identify a causal mechanism.",
        },
        {
            "id": "D04",
            "observation": "Communication-law campaigns often yielded mixed target-service support in successful traces.",
            "hypothesis": "Current parser drift produced the mixed support in retained raw samples.",
            "test": "Replay current normalization for four raw NCD/r0 samples and compare nine outputs byte-for-byte.",
            "result": f"{replay_mismatches} of {len(replay)} replayed files differ.",
            "status": "not_supported_on_four_samples" if replay_mismatches == 0 else "supported_on_retained_samples",
            "interpretation_limit": "Only four cells retain raw spans; exact replay cannot distinguish genuine conditional paths from source-time span loss.",
        },
        {
            "id": "D05",
            "observation": "M7 reported stable and all-sequence views and removed transition-adjacent requests from the former.",
            "hypothesis": "Timestamp/health alignment failure invalidated the saved score denominators.",
            "test": "Reconstruct transitions, stable membership, nearest health distance, timeouts, and fixed transition windows.",
            "result": f"{unaligned} test requests exceed the frozen health-alignment tolerance.",
            "status": "not_supported" if unaligned == 0 else "supported",
            "interpretation_limit": "Temporal associations do not justify changing the frozen guard or excluding operational transients.",
        },
    ]


def run_m7_causal_diagnostics(
    config: FrozenLiveValidationConfig,
    evidence_config: EvidenceBoundaryConfig,
    qualified_root: str | Path,
    analysis_root: str | Path,
    raw_root: str | Path,
    output_directory: str | Path,
) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise M7DiagnosticError("full M7 causal diagnostics may run only in GitHub Actions")
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    cells = discover_qualified_cells(qualified_root)
    if len(cells) != config.expected_cells:
        raise M7DiagnosticError(
            f"expected {config.expected_cells} qualified cells, found {len(cells)}"
        )
    analysis_directory = _find_analysis_directory(Path(analysis_root))
    raw_path = Path(raw_root)

    periods = period_rate_rows(cells, config)
    detail, strata = bias_rows(cells, analysis_directory, periods, config)
    temporal, windows = temporal_rows(cells, config)
    topology, branches, examples = topology_rows(cells, config)
    raw_semantics, semantic_reasons, raw_request_paths = raw_semantic_rows(raw_path)
    replay = replay_raw_samples(
        raw_path, output / "parser-replay", cells, evidence_config
    )
    discrepancies = _discrepancy_rows(replay, temporal)

    outputs = (
        ("period-rates.csv", PERIOD_FIELDS, periods),
        ("bias-detail.csv", BIAS_DETAIL_FIELDS, detail),
        ("bias-strata.csv", BIAS_STRATUM_FIELDS, strata),
        ("temporal-campaign-operation.csv", TEMPORAL_FIELDS, temporal),
        ("transition-windows.csv", TRANSITION_FIELDS, windows),
        ("topology-diagnostics.csv", TOPOLOGY_FIELDS, topology),
        ("topology-branches.csv", TOPOLOGY_BRANCH_FIELDS, branches),
        ("topology-examples.csv", TOPOLOGY_EXAMPLE_FIELDS, examples),
        ("raw-semantic-diagnostics.csv", RAW_SEMANTIC_FIELDS, raw_semantics),
        ("semantic-reasons.csv", SEMANTIC_REASON_FIELDS, semantic_reasons),
        ("parser-replay-audit.csv", REPLAY_FIELDS, replay),
        ("discrepancy-register.csv", DISCREPANCY_FIELDS, discrepancies),
    )
    for filename, fields, rows in outputs:
        _write_csv(output / filename, fields, rows)

    topology_status = Counter(
        (row["mode"], row["failure_law"], row["status"]) for row in topology
    )
    manifest = {
        "schema_version": 1,
        "kind": "m7_posthoc_causal_diagnostics",
        "diagnostic_only": True,
        "changes_m7_predictions_or_scores": False,
        "source_run_ids": sorted(
            {
                str(
                    cell.boundary.get("source_provenance", {})
                    .get("environment", {})
                    .get("github", {})
                    .get("GITHUB_RUN_ID", "")
                )
                for cell in cells
            }
        ),
        "row_counts": {
            "qualified_cells": len(cells),
            "raw_samples": len(raw_request_paths),
            "period_rates": len(periods),
            "bias_detail": len(detail),
            "bias_strata": len(strata),
            "temporal_campaign_operations": len(temporal),
            "transition_windows": len(windows),
            "topology_diagnostics": len(topology),
            "topology_branches": len(branches),
            "topology_examples": len(examples),
            "raw_semantic_diagnostics": len(raw_semantics),
            "parser_replay_files": len(replay),
        },
        "technical_quality": {
            "qualified_cell_count_mismatches": int(
                len(cells) != config.expected_cells
            ),
            "raw_sample_count_mismatches": int(len(raw_request_paths) != 4),
            "test_alignment_mismatches": sum(
                int(row["unaligned_requests"]) for row in temporal
            ),
            "parser_replay_errors": sum(bool(row["error"]) for row in replay),
        },
        "substantive_observations_not_acceptance_gates": {
            "parser_replay_file_mismatches": sum(
                not bool(row["matches"]) for row in replay
            ),
            "http_2xx_semantic_failures_in_four_raw_samples": sum(
                int(row["http_2xx_semantic_failures"]) for row in raw_semantics
            ),
            "topology_status_counts": {
                "|".join(key): count for key, count in sorted(topology_status.items())
            },
        },
        "fixed_diagnostic_windows_seconds": [1, 5, 15],
        "interpretation_boundary": (
            "This post-M7 decomposition can support or reject specific explanations "
            "on preserved data. It is not a tuned reanalysis, cannot recover missing "
            "raw spans for 156 cells, and does not decide overall success or failure."
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
    fatal = {
        key: value
        for key, value in manifest["technical_quality"].items()
        if key in {"qualified_cell_count_mismatches", "raw_sample_count_mismatches"}
        and value
    }
    if fatal:
        raise M7DiagnosticError(f"M8B input acceptance failures: {fatal}")
    return manifest
