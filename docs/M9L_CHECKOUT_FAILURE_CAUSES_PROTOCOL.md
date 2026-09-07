# M9L: checkout route-up failure-cause discrimination

Status: completed on the first remote attempt; accepted run `34085244404`.

## Question and boundary

M9K exactly localized the retained OpenTelemetry Demo checkout overprediction
to the route-up residual term. Across 40 N/ND campaigns, health-defined route
exposure itself contributed almost nothing, while carrying the clean-baseline
residual success probability into requests classified as route-up contributed
`+0.180031` in test and `+0.177614` in calibration. M9L asks which observable
subclass of those route-up requests carries the calibration discrepancy.

This is the next experiment selected by the M9K machine decision. The taxonomy,
thresholds, target, and retained inputs below are fixed before reopening the
qualified request/trace tables. M9L does not change the M7 model, create a
replacement prediction, score a new method, invoke PMX, or collect new live
data.

The primary discrimination uses calibration because the frozen learner
boundary contains trace-derived target-replica sets only there. The evaluator
boundary intentionally has no trace graph. Test requests are used solely for a
predeclared aggregate within-request health corroboration; they cannot support
a target-replica cause assignment.

## Fixed population and evidence

The cohort is unchanged from M9K: OpenTelemetry Demo `checkout`, both logical
placements, failure laws N and ND, and repetitions 0--9. NC and NCD remain
excluded because communication-topology ambiguity was known before M9K. M9L
starts from each campaign's requests that meet the original M9K definition:

- period calibration (primary) or test (aggregate corroboration);
- checkout operation;
- request start aligned to the nearest full health tick within 1.25 seconds;
- outside the original one-second guard around any full-signal transition; and
- route-up at request start, defined as the union of replica-a and replica-b
  path signals.

M9L consumes the M8A preserved archive and independent inventory plus the
accepted M9K localization and decision artifacts. Their artifact IDs, run
commits, compressed digests, relevant decompressed bytes, and current source
inputs are locked in the configuration. All 360 files in the selected cells
are checked against M8A again. Per-cell stable/route-up request and success
counts must reproduce M9K exactly.

The full retained learner traces provide more diagnostic information than the
`sampled_mixed` forecasting mode used for M7 topology discovery. They are
therefore labelled additional post-result diagnostic evidence. Their use may
identify a cause boundary, but cannot be credited as the original forecast's
input or cost.

## Interval and replica classification

Both request start and completion are aligned to full health. The inclusive
sequence of health-tick indices from the nearest start tick through the nearest
completion tick defines the observed request interval. A target-replica set is
usable only if the retained trace is present, has at least one parsed span, and
the recorded set is a nonempty subset of `{a,b}` consistent with its recorded
replica count.

Every M9K route-up request enters exactly one class, in this frozen precedence:

1. `completion_health_unresolved`: completion cannot be aligned or precedes
   the start index;
2. `aggregate_union_lost_during_request`: the union of target paths is down at
   any observed tick after its up start;
3. `trace_target_unresolved_union_continuous`: aggregate union remains up, but
   no usable target-replica set is available;
4. `target_path_down_at_start_union_continuous`: aggregate union remains up,
   but at least one target replica represented in the trace has a down path at
   request start;
5. `target_path_lost_during_request_union_continuous`: every represented target
   path is up at start, but at least one is down at a later interval tick while
   the aggregate union remains up; and
6. `target_paths_continuously_up`: aggregate union and every target path
   represented in the retained trace remain up at all observed interval ticks.

The target-replica field is a set accumulated over the whole normalized trace.
It is not an exact per-call timestamp, an HAProxy decision log, or proof that a
specific call was sent while a path was down. The class names deliberately say
what was observed and do not overstate routing causality. A trace containing
both replicas is retained as both, not reduced to an invented selected replica.

Timeout counts are reported within every class but are descriptive. A timeout
flag alone does not distinguish target routing, overload, or another dependency.

## Exact residual allocation

For cell `i`, let `q_i` be the unchanged clean-baseline residual probability,
`N_i` the number of all stable calibration checkout requests, and `n_ic` and
`f_ic` the route-up requests and failures in class `c`. The class contribution
is

`e_ic = (f_ic - (1-q_i)*n_ic) / N_i`.

Because the classes are exhaustive, their sum must exactly reproduce M9K's
calibration `route_up_residual_invariance` for every cell to tolerance `1e-12`.
The classes are also combined into four fixed candidates:

- `aggregate_interval_loss`: class 2;
- `observed_replica_path_loss`: classes 4 and 5;
- `observed_paths_continuously_up`: class 6; and
- `evidence_unresolved`: classes 1 and 3.

For test, where replica traces are forbidden, the same calculation has only
completion-unresolved, aggregate-union-lost, and aggregate-union-continuous
parts. These must sum to the M9K test residual. They are not replacement
predictions.

## Frozen discrimination rule

Campaign means remain equally weighted. Uncertainty uses 10,000 deterministic
campaign bootstraps within each placement-by-law stratum. A calibration
candidate is dominant only if its mean and 95% lower bound are positive, all
three bootstrap lower bounds for its pairwise differences from the other
candidates are positive, and its cell contribution is positive in at least 32
of 40 campaigns.

Trace-dependent branches additionally require both:

- the 95% lower bound for mean usable target-trace coverage among the selected
  route-up requests is at least 0.60; and
- the 95% interval for target-trace resolution among failures minus resolution
  among successes lies wholly within the predeclared equivalence margin
  `[-0.10,+0.10]`.

These gates prevent outcome-dependent missing traces from being interpreted as
a physical distinction. The aggregate-interval branch does not need trace
adequacy, but it must independently dominate the union-continuous part in the
test interval decomposition under the same bootstrap/sign rule. Completion
alignment must be at least 99.5%, every cell must contain at least 500 selected
route-up requests, and both exact M9K residual identities must pass.

If a substantive candidate wins but its applicable adequacy/corroboration gate
fails, or if no candidate uniquely dominates, the result is
`evidence_unresolved`. Missingness is neither imputed nor dropped.

## Interpretation branches

- Aggregate interval loss means the point-in-time route state is inadequate for
  this multi-call request duration and motivates a fixed duration-aware model
  test.
- Observed replica-path loss means union availability hides material loss on
  replicas represented in the request trace and motivates request-level routing
  instrumentation/modeling. It does not prove the exact HAProxy choice time.
- Persistence with observed target paths continuously up rules out these two
  measured path-state explanations for the dominant retained component. It
  motivates a dependency/timeout/semantic audit, but does not prove that every
  dependency was healthy or that the product-catalog probes were perfect.
- Evidence unresolved means the preserved boundary cannot distinguish the
  candidates and the next step must freeze minimal new instrumentation before
  any collection.

No branch generalizes beyond checkout, becomes confirmatory accuracy evidence,
or establishes a better method. M9J remains a scoped diagnosis of one PMX
binary and M9L does not alter its gate or PMX's scientific priority. The article
position remains unchanged: the direction is substantive and the specified
calculation is supported, but better predictive accuracy and lower end-to-end
automatic forecast cost than PMX have not been demonstrated.

## Workflow and reporting

The workflow has exactly three jobs:

1. verify M8A/M9K artifact identities and the inherited M9K result;
2. download and audit the preserved cells, classify requests, reconstruct both
   residuals, and run the frozen bootstrap;
3. apply adequacy/corroboration gates and select the next M9M experiment.

All three jobs use `timeout-minutes: 360`. Full downloads, cell scans, and
bootstraps run only in GitHub Actions. Local activity is limited to repository
validation, unit tests, and synthetic taxonomy/arithmetic smokes. The milestone
report must record the accepted commit/run/artifacts, every integrity and
adequacy gate, class/candidate contributions, uncertainty, limitations, and the
selected next experiment.
