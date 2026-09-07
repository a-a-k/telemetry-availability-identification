"""Render the three registered M9P contrasts from completed aggregate manifests.

No campaign records are read and no estimate, interval or decision is recomputed.
The optional --illustrative-only flag requires explicitly marked artificial input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


RUN = "34118845320"
HEAD = "bc03711b3a50daa90be305986dd12769a2d8ef30"
CONFIG = "b11965da68f02b97fc3dac7c6a162807779a205f4a95efa696a70283422944ec"
ANALYSIS = "f0a13fd4181a515efe95a887432b1d2ec2b03e79f717897f797b6fd88f977890"
PANELS = (
    ("conditional_temporal_minus_state_brier", "Conditional information",
     "Temporal minus state-only Brier score; observed test health is used",
     "conditional_temporal_information", None),
    ("marginal_temporal_minus_state_brier", "Increment in the mean forecast",
     "Temporal minus state-only Brier score; forecast uses learner data only",
     "marginal_increment", 0.002),
    ("marginal_temporal_signed_error", "Mean forecast calibration",
     "Temporal forecast minus observed held-out success fraction",
     "mean_marginal_calibration", 0.03),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(candidate, evaluation, audit, illustrative_only=False):
    for record in (candidate, evaluation, audit):
        require(record.get("_illustrative_only", False) is illustrative_only,
                "Artificial inputs require --illustrative-only on all three files")
        require(str(record["source_run_id"]) == RUN, "Unexpected source run")
    for record in (candidate, evaluation):
        require(record["source_commit"] == HEAD, "Unexpected source commit")
        require(record["config_sha256"] == CONFIG, "Unexpected frozen configuration")
        require(record["analysis_implementation_sha256"] == ANALYSIS,
                "Unexpected frozen analysis")
    require(candidate["status"] == "all_prospective_candidates_frozen",
            "Candidates were not frozen")
    require(candidate["cells"] == 120 and candidate["candidate_rows"] == 840,
            "Incomplete candidate matrix")
    for flag in ("test_outcomes_accessed", "test_health_accessed", "raw_traces_staged",
                 "candidate_selection_after_test"):
        require(candidate[flag] is False, "Candidate boundary differs: " + flag)
    require(audit["status"] == "main_retention_and_acquisition_audit_passed",
            "Final acquisition and retention audit did not pass")
    require((audit["cells"], audit["compact_artifacts"], audit["raw_source_artifacts"])
            == (120, 360, 120), "Incomplete audited artifact census")
    gates = evaluation["gates"]
    require(set(gates) == {"learner_adequacy", "fit_integrity", "test_adequacy",
                          "interval_sensitivity", "complete_campaign_matrix"},
            "Unexpected inferential gates")
    require(all(type(value) is bool for value in gates.values()), "Nonboolean gate")
    admissible = all(gates.values())
    require(evaluation["inferential_claims_admissible"] is admissible,
            "Inference status contradicts gates")
    require(evaluation["status"] == ("independent_confirmation_complete" if admissible
            else "independent_confirmation_inadequate"), "Completion status differs")
    require(evaluation["conditional_score_is_advance_forecast"] is False
            and evaluation["general_accuracy_or_pmx_claim"] is False,
            "Claim scope differs")
    require(set(evaluation["intervals"]) == {row[0] for row in PANELS},
            "The complete three-contrast family is required")
    for metric, _, _, decision, _ in PANELS:
        interval = evaluation["intervals"][metric]
        require(all(math.isfinite(interval[key]) for key in ("estimate", "lower", "upper")),
                "Nonfinite reported interval")
        require(interval["lower"] <= interval["upper"], "Reversed reported interval")
        require(interval["campaigns"] == 120 and interval["resamples"] == 10000,
                "Unexpected campaign or bootstrap count")
        require(math.isclose(interval["confidence_level"], 1 - 0.05 / 3,
                             rel_tol=0, abs_tol=1e-12), "Unexpected interval level")
        require(isinstance(evaluation[decision], str), "Missing reported decision")
        if not admissible:
            require(evaluation[decision] == "inadequate_confirmation",
                    "A failed gate must block every inferential claim")
    return admissible


def render(candidate_path, evaluation_path, audit_path, output, illustrative_only=False):
    paths = (candidate_path, evaluation_path, audit_path)
    records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    admissible = validate(*records, illustrative_only)
    evaluation = records[1]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "svg.fonttype": "none", "pdf.fonttype": 42,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "axes.edgecolor": "#9aa3af"})
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 7.6))
    fig.subplots_adjust(left=0.09, right=0.96, top=0.755, bottom=0.20, hspace=1.15)
    fig.text(0.09, 0.958, "M9P · Independent temporal confirmation", fontsize=16,
             weight="bold", color="#142b43")
    fig.text(0.09, 0.913, "120 campaigns · 4 strata × 30 · 10,000 paired campaign bootstrap draws",
             fontsize=10.5)
    fig.text(0.09, 0.879, "98.333% percentile intervals; Bonferroni allocation of nominal family α = 0.05",
             fontsize=10, color="#4b5563")
    color = "#146a91" if admissible else "#6b7280"
    for index, (ax, panel) in enumerate(zip(axes, PANELS, strict=True)):
        metric, title, subtitle, decision, tolerance = panel
        row = evaluation["intervals"][metric]
        estimate, low, high = (row[key] for key in ("estimate", "lower", "upper"))
        extent = [0, estimate, low, high]
        if tolerance is not None:
            extent.extend((-tolerance, tolerance))
            ax.axvspan(-tolerance, tolerance, color="#e1eaf0", zorder=0)
            for cutoff in (-tolerance, tolerance):
                ax.axvline(cutoff, color="#8ba2b3", lw=0.9, ls=":")
        span = max(extent) - min(extent)
        padding = max(span * 0.13, 0.0002)
        ax.set_xlim(min(extent) - padding, max(extent) + padding)
        ax.set_ylim(-0.5, 0.5)
        ax.axvline(0, color="#485569", lw=0.9, ls="--")
        ax.hlines(0, low, high, color=color, lw=3, zorder=3)
        ax.vlines((low, high), -0.11, 0.11, color=color, lw=1.6, zorder=3)
        ax.scatter([estimate], [0], s=56, color=color, edgecolor="white", zorder=4)
        ax.set_yticks([])
        ax.tick_params(axis="x", labelsize=9, length=3)
        ax.ticklabel_format(axis="x", style="plain", useOffset=False)
        ax.text(0, 1.69, f"{chr(65 + index)}  {title}", transform=ax.transAxes,
                fontsize=12, weight="bold", color="#142b43")
        ax.text(0, 1.36, subtitle, transform=ax.transAxes, fontsize=9, color="#4b5563")
        status = evaluation[decision].replace("_", " ")
        ax.text(0, 1.02, f"{estimate:+.6g}  [{low:+.6g}, {high:+.6g}]",
                transform=ax.transAxes, fontsize=9, color=color)
        ax.text(1, 1.02, status, transform=ax.transAxes, ha="right", fontsize=9)
    source_note = ("Artificial inputs only; no campaign results or artifact census verified."
                   if illustrative_only else
                   f"Source: GitHub Actions {RUN} · {HEAD[:12]} · all 480 source artifacts audited.")
    fig.text(0.09, 0.075,
             "Shading: registered marginal equivalence (±0.002) and mean calibration (±0.03) regions.\n"
             "Separate x-axis scales. Panel A is a conditional diagnostic; it does not establish advance-forecast gain.\n"
             + source_note,
             fontsize=8.5, linespacing=1.5, color="#4b5563")
    if not admissible:
        fig.text(0.5, 0.49, "INFERENCE BLOCKED BY ADEQUACY GATES", ha="center",
                 rotation=24, fontsize=23, color="#a61c23", alpha=0.20)
    if illustrative_only:
        fig.text(0.5, 0.52, "ARTIFICIAL LAYOUT CHECK — NOT RESULTS", ha="center",
                 rotation=24, fontsize=23, color="#a61c23", alpha=0.25)
    output.mkdir(parents=True, exist_ok=True)
    for extension in ("pdf", "svg", "png"):
        fig.savefig(output / f"m9p-confirmation.{extension}", dpi=200, facecolor="white")
    plt.close(fig)
    provenance = {
        "status": "artificial_layout_check" if illustrative_only else "reported_aggregate_rendering",
        "source_run_id": RUN, "source_commit": HEAD,
        "inferential_claims_admissible": admissible,
        "estimates_intervals_decisions_recomputed": False,
        "inputs": {path.name: {"bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths},
        "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "matplotlib_version": matplotlib.__version__, "numpy_version": numpy.__version__,
    }
    (output / "figure-provenance.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "evaluation", "audit", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--illustrative-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(render(args.candidate, args.evaluation, args.audit,
                            args.out, args.illustrative_only), indent=2))


if __name__ == "__main__":
    main()
