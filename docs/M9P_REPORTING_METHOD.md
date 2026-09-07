# Rendering the completed M9P aggregate results

The renderer was prepared before main-run candidate generation and evaluation.
It reads only `candidate-manifest.json`, `evaluation-manifest.json` and
`main-audit.json` from the completed run `34118845320` at
`bc03711b3a50daa90be305986dd12769a2d8ef30`. It does not read campaign observations,
fit a model, bootstrap an interval, choose a method or reclassify a result.

The figure displays all three registered contrasts, with separate x-axis
scales and the registered equivalence/adequacy regions. Point estimates,
interval endpoints and decisions are copied from the evaluation manifest.
Every inference panel is marked as blocked if any registered adequacy gate
fails. The conditional diagnostic is explicitly distinguished from the
learner-only marginal forecast.

## Completed-run summary audit

`scripts/audit_m9p_completed_summary.py --out OUTPUT` first requires the main
run to be completely successful at the frozen head and attempt. It verifies
all 124 completed jobs and all 485 declared source/summary artifact records,
using the same one-day retention tolerance as the frozen 90-day retention gate.
It downloads only the five generated summary archives, verifies their ZIP
byte lengths and SHA-256 digests, checks candidate/evaluation file seals and
the candidate-upload/access order, and compares the readiness file locks to
the exact frozen Git bytes. It checks reported matrix identities, without
recomputing predictions, scores, bootstrap intervals or decisions.

The additional cost summary adds the final audit job to the remote report's
explicitly incomplete runner-hour total and aggregates the generated cost
rows once per method. Native telemetry, learner bundles and evaluator bundles
are not downloaded. The full artifact API snapshot, compact artifact locks
and verification report accompany the five local summary archives.

## Reproduction

Use a separate plotting environment; the experiment dependencies are unchanged.
The initial renderer check used Python 3.13, Matplotlib 3.11.1 and NumPy 2.4.4.
For example, after retrieving and verifying the three generated manifests:

```text
python -m pip install matplotlib==3.11.1 numpy==2.4.4
python scripts/render_m9p_confirmation.py --candidate INPUT/candidate-manifest.json --evaluation INPUT/evaluation-manifest.json --audit INPUT/main-audit.json --out OUTPUT
```

The output is `m9p-confirmation.pdf`, `.svg`, `.png` and
`figure-provenance.json`. The provenance records the exact input byte lengths
and SHA-256 digests, renderer digest, library versions and source run/commit.
Artifact API provenance and seal verification belong to the completed-run
audit; matching a manifest's declared identifiers alone is not authentication
of an arbitrary downloaded file.

The local layout check used three explicitly artificial input manifests and
the `--illustrative-only` option. Such figures are watermarked and their footer
states that no campaign results or artifact census were verified. Both the
admissible and blocked layouts were rendered, and missing metrics, an
inconsistent gate, a wrong source run, and absent artificial-input disclosure
were rejected. No live learner or evaluator bundle was used in that check.

These are nominal 98.333% percentile bootstrap intervals with Bonferroni
allocation of a 0.05 family error budget. Plot labels do not imply an exact
finite-sample joint coverage theorem for dependent live requests. The
resampling unit and inferential scope remain those in the frozen protocol.
