# M9D: aligned-input Palladio debugging comparison

Status: frozen before the first M9D remote parameter recovery or Palladio
execution.

## Purpose and claim boundary

M9D is the first common table requested by the Palladio continuation plan. It
tests whether the accepted M9C PCM mapping preserves a frozen M7 likelihood
prediction when both calculations receive the same learner-only parameter
realization. It then places that linked PCM/Palladio result beside the frozen
B0, B2, and proposed predictions and scores all emitted values against the same
preserved test outcomes.

Palladio-Analyzer-Reliability solves a supplied PCM. It does not infer
reliability parameters from telemetry. The linked variant is therefore named
`PCM-PAR/B3-parameters`, not a standalone Palladio estimator. On the admissible
support it is also reported as `PCM-PAR/admissible`, which inherits the exact
topology and identification gates of frozen proposed. Its equality with
proposed is expected and is a transformation/solver fidelity check, not an
independent accuracy replication.

M9D is an exploratory post-result debugging analysis. M7 and M8 outcomes were
already known. No M9D result can retroactively make M7 confirmatory or change
its current interpretation: the published calculations establish no
predictive gain and disagree with observations, while the causes remain
insufficiently diagnosed for an overall success/failure verdict.

## Fixed questions

1. Does M7-to-PCM-to-PAR preserve the direct B3/proposed probability under the
   same stationary parameters and operation semantics?
2. How do B0, strengthened B2, proposed, and the linked PCM result compare with
   the preserved independent test requests on their declared support?
3. What coverage is achieved, why is a prediction absent, and does the PCM
   bridge introduce any additional abstention or solver failure?
4. What incremental computation, memory, and model-update work does PCM export
   and solving require after the common likelihood preparation?

The first question supplies technical acceptance gates. Accuracy, coverage,
and resource direction are substantive results and can never make a workflow
pass or fail.

## Frozen evidence and population

The only empirical source is the renewed M8A copy of frozen M7 run
`33990678586`, source commit
`b1925736f314da610debd23a586d7b7d00cae7ca`. Its 160 qualified campaign
bundles and frozen analysis tables are byte-audited against the accepted M8A
inventory before any fit. Exact artifact ids, names, sizes, digests, inner-file
hashes, code locks, and accepted M9C manifests are in
`configs/m9d_palladio_aligned_comparison.json`.

The two operations are the M7B routing probes mapped before M9D:

- DeathStarBench Social Network: `read_user_timeline`;
- OpenTelemetry Demo: `browse_product`.

They were selected before Palladio output and not for favorable M7 error. They
are purposive probes rather than a representative sample of all six M7
operations, so M9D does not generalize accuracy to the four unmapped operations.

The first aligned comparison uses only `sampled_mixed`, the frozen primary M7
observability mode. This is fixed before M9D solving and is not selected from a
new multi-mode result. There are 240 operation-level opportunities:

- current: two applications by two placements by four laws by ten campaigns,
  or 160;
- transfer: two applications by one colocated source by four laws by ten
  colocated/split campaign pairs, or 80.

The historical predictions already show the frozen support: B0 emits 240;
B2, B3, and proposed each emit on the same 184 rows for these operations and
this mode. The other 56 rows, 41 current and 15 transfer, have status
`topology_ambiguous_target_fraction`. This previously published inventory is a
reproduction gate, not a new outcome. The exact 24-stratum table is frozen in
the M9D configuration.

Each campaign is the unit of accuracy analysis. Transfer pairs the colocated
learner with the separately executed split evaluator having the same
application, law, and repetition. Telemetry masks are not independent live
campaigns. The distinct outcome views are frozen `stable` and `all_sequence`;
the retained 46-second stable sensitivity rows are used only for block-interval
compatibility because its point outcome and Brier score duplicate `stable`.

## Fixed variants

- `B0`: frozen calibration endpoint persistence.
- `B2`: frozen strengthened available-moments comparator, including its joint
  health branch where admitted.
- `B3-direct`: frozen raw best likelihood point, retained as an implementation
  reference.
- `proposed-direct`: the same likelihood point only where the original
  identification guard emits.
- `PCM-PAR/B3-parameters`: explicit M9C application PCM populated by the
  deterministic B3 optimizer realization.
- `PCM-PAR/admissible`: the same solver value restricted to the exact emitted
  support of `proposed-direct`.

No `PCM+B2` topology is constructed. B2 identifies a route functional from
moments; it does not uniquely identify `g, e_a, e_b, c_a, c_b`. Forcing that
scalar into a detailed two-resource PCM would require an arbitrary
factorization or projection and would create a straw-man comparison. B2 remains
the strong direct comparator on the same evidence.

## Learner-only parameter recovery

Historical B0/B2/B3/proposed rows are imported from the byte-locked
`predictions.csv`; they are not renamed or refitted as new methods. The full B3
parameter vector was not persisted, so M9D deterministically replays only the
fixed `sampled_mixed` fits to recover an internal solver witness.

Before replay, the workflow stages `learner/` and `audit/` only. The stage must
contain zero `evaluator/`, `test-requests.csv`, and `test-health.csv` paths. A
learner-only loader constructs empty evaluator fields and then calls the
unchanged M7 `prepare_mode`, `fit_exact_model`, and `predict_cell` functions.
Their files, configuration, and exact NumPy/SciPy/Python dependency versions
are locked to M7.

After staging, the combined M8A source, audit, M9C input copies, and metadata
directories are removed from the fitting job. Only `manifest.json` and the
byte-locked `predictions.csv` remain in a separate reference directory. The
adapter completes all 160 fits before it opens that prediction table; the
table is used only to reject a replay mismatch. Neither frozen `scores.csv`
nor evaluator outcomes are present for fitting or PCM generation.

Exactly 160 unique fits are replayed, one per application, source placement,
law, and repetition. The 80 colocated fits are reused for their current and
transfer predictions; 240 is the number of prediction opportunities, not the
number of optimizations. For all 240 opportunities and each of
B0/B2/B3/proposed, recovered prediction,
route, residual, status, fit status/NLL, rank/dimension, target-gradient
residual, and multistart range must agree with the frozen row within `1e-12`
where numeric and exactly where categorical. A mismatch stops before PCM
generation. The fit continues to use every topology-confirmed target operation
in its M7 cell, not just the selected M9D probe; the exact fit-operation list is
retained.

Even when the route functional is identified, its individual fitted factors
can lie on a likelihood-equivalent nuisance ridge. M9D calls the saved vector
an optimizer realization, not separately recovered causal resource
probabilities. One historical admitted fit has status `finite_nonconvergence`;
it is retained and disclosed rather than filtered after the fact.

## Fixed PCM mapping

For a recovered vector, absent-law factors are exactly one: `g=1` without `D`,
and `c_a=c_b=1` without `C`. The selected operation residual is `q`.

- colocated: common resource availability `g`; path resources `e_a`, `e_b`;
- split: perfect common resource; path resources `g*e_a`, `g*e_b`;
- link failure: `1-sqrt(c_a)` and `1-sqrt(c_b)` because PAR applies the raw
  link probability independently to request and response transfer;
- resource ratio coordinates: `MTTF=A`, `MTTR=1-A`.

The independent success oracle is therefore:

- colocated:
  `q*g*[e_a*c_a + (1-e_a*c_a)*e_b*c_b]`;
- split:
  `q*[g*e_a*c_a + (1-g*e_a*c_a)*g*e_b*c_b]`.

The 184 eligible rows must produce 184 directories and, for two measured
solver passes, 368 raw records. Thirty-one models have eight non-degenerate
physical states and 153 have four. All models reuse the M9C template without a
per-cell manual edit.

This remains a stationary Boolean-OR abstraction of a health-routed pool. It is
not literal round-robin or retry execution, a temporal Docker-network outage
model, a claim of physical host isolation, or an estimate of separate failure
and repair durations. Folding `g*e` into split resources also preserves success
probability while losing failure-cause attribution.

## Eligibility and coverage

The raw `PCM-PAR/B3-parameters` bridge is generated when frozen B3 emitted, an
exact fit exists, and all required values are finite. `PCM-PAR/admissible`
exposes that same raw result only when proposed emitted under its original
identification guard. These supports happen to coincide on all 184 fixed
`sampled_mixed` rows, but the two roles remain distinct. M9C source
documentation cannot override an
ambiguous M7 trace classification in this aligned-input comparison; doing so
would privilege PCM with extra structural information.

B0 keeps its original broader coverage. B2, B3, and proposed keep their exact
historical statuses. A mapping, XMI, load, or solver failure remains a visible
additional PCM failure and is never replaced by the direct prediction. Rows
outside the two fixed operations and primary mode are outside the population,
not abstentions.

Coverage is reported as numerator/240 and by application, scope, placement,
and law. Conditional accuracy is shown beside full-population coverage. Missing
predictions are never imputed, and selective accuracy is not merged with
coverage into an invented composite score.

## Technical acceptance gates

The Java harness contains no oracle or expected accuracy value. A downstream
Python job must establish:

- maximum `|PAR - independent oracle| <= 1e-12`;
- maximum `|oracle - frozen B3| <= 1e-12`;
- maximum `|PAR - proposed| <= 1e-12` on admissible support;
- success plus failure, and physical-state mass, each within `1e-12` of one;
- two measured passes equal within `1e-12`;
- evaluated state count equals total and the frozen 31/153 state inventory;
- zero evidence, identity, file, model, or result mismatches.

An evidence or technical-gate failure stops scoring and means an integration,
reproducibility, or semantic-mapping problem. It is not evidence that either
scientific approach is better.

## Scoring and interpretation

Only the final job joins frozen evaluator outcomes, after the model contract and
raw solver artifact exist. It independently recomputes request-level Bernoulli
Brier, signed prediction-minus-observation error, and absolute error from test
successes and requests. It also retains 23- and 46-second block compatibility.

Descriptive summaries use campaign rows and equal application/placement/law
stratum weight for current, and equal application/law weight for transfer.
Pairwise common-support tables use the M7 equal-stratum
Welch--Satterthwaite calculation on paired campaign differences. Current has
16 intended application/placement/law strata and transfer has eight intended
application/law strata; each represented stratum needs at least two pairs for
an interval. Incomplete intended support remains marked incomplete. Tables
include PCM/admissible versus proposed, B2, and B0, plus proposed versus B2 and
B0 and B2 versus B0. Contrasts are first minus second, so a negative Brier
difference favors the first method. They show denominator,
each method's coverage, paired campaigns, strata, estimate, and descriptive
95% interval. M9D computes no p-values and admits no equivalence or
non-inferiority claim.

For transfer, the workflow also records
`(predicted_split-predicted_colocated) -
 (observed_split-observed_colocated)` on complete pairs. Requests inside a
campaign and technical solver repetitions do not increase the independent
sample size.

Exact PCM/proposed equality validates the bridge only. Their equal Brier score
means that they share a prediction, not that Palladio independently confirms
its validity. Any difference between them is a defect to diagnose, not a
platform advantage. A difference from B2 primarily mixes likelihood-versus-
moment parameterization with PCM execution. M9D cannot by itself localize the
known prediction/observation discrepancy.

## Resource and manual-work accounting

All three workflow jobs use `timeout-minutes: 360`. The solver performs one
fixed warm-up using the lexicographically first admitted model; that execution
is excluded from its two measured passes, after which the same model is also
measured normally. Evidence audit,
mode preparation, likelihood fitting, PCM serialization/audit, one-time clean
Palladio build, per-model load/solve, full measured pass, scoring, and
end-to-end job use are retained separately where measurable. Wall time, peak
RSS, environment, model count, and state count accompany the result. A shared
historical M7 analysis time is not divided to invent separate B0 or B2 costs;
those entries are explicitly `not separately measured`.

Every admitted model is an automated update of the same five-file template:
zero template files are manually edited per cell, nine scalar XMI parameter
fields are written automatically (one residual-failure value, three MTTF and
three MTTR values, and two link-failure values), and manual interventions per
model are zero. Per-cell mode-preparation and likelihood-fit time,
parameter-only serialization time, XMI-audit time, and the automatic
colocated-to-split mapping time for transfer rows are recorded separately.

The prospective append-only action log is `docs/M9D_MANUAL_ACTIONS.csv`. It separates
human decisions, autonomous coding work, workflow automation, inherited M9A
installation, M9B semantic validation, M9C application mapping, adapter work,
and zero-edit per-cell updates. Historical active human minutes that were not
recorded remain unavailable rather than being reconstructed. Coding-agent time
is not human manual labour. Planned rows are explicitly marked and are not
counted as completed work; the final log hash is recorded in the accepted
manifest rather than frozen now.

## Execution and stopping rules

Heavy evidence replay, all likelihood fits, PCM generation over the full fixed
population, Palladio builds/solves, and scoring run only in GitHub Actions.
Local work is limited to configuration validation, unit tests, XML structural
smokes, and at most one synthetic or one-cell loader smoke.

Before the first remote run the source identities, two operations, mode,
population, formulas, labels, gates, tolerances, views, weighting, coverage
taxonomy, repetitions, expected state inventory, and output schemas are frozen.
No M7 threshold, mask, optimizer, estimator, transition guard, operation set,
or failure law may be changed after output. Accuracy direction and coverage are
never acceptance gates. Any correction must be justified by evidence identity,
replay, XMI, external oracle, probability-mass, or repeatability failure and be
recorded together with the rejected attempt.

After technical acceptance, M9D is reported regardless of the direction of
accuracy and coverage. A later end-to-end milestone must define how a PCM model
and its reliability parameters are obtained without silently inheriting the
study's intermediate likelihood model; M9D deliberately does not make that
claim.
