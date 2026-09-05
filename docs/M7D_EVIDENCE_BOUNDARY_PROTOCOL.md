# M7D learner/evaluator evidence-boundary qualification protocol

## Purpose and non-effectiveness status

M7D freezes and executes the data boundary that the main M7 analysis will use.
It asks whether the two native tracing formats and the independently sampled
health/deployment evidence can be converted into a common learner bundle
without exposing the learner to the fault controller or the held-out period.

M7D is diagnostic only. It may use all 64 M7C pilot cells to exercise schemas,
but it does not fit a model, tune an estimator, compare B0--B4, or score a
prediction. M7C and M7D requests remain permanently excluded from M7
effectiveness evidence. A favorable endpoint or placement result in these
pilots cannot select an analysis rule.

## Three physically separated evidence tiers

For each source cell the executable adapter writes three directories:

1. `learner/` contains calibration-period external semantic outcomes, native
   trace-derived service graphs and replica assignments, one-second
   health/lifecycle/network observations, and declared deployment/routing
   metadata.
2. `evaluator/` contains only held-out test-period external semantic outcomes.
   It is not an input to topology discovery, fitting, model selection, or
   numerical tuning.
3. `audit/` records boundary checks and hashes. The exact planned schedule,
   controller event identifiers and cause sets, intended/applied/verified
   transition times, cleanup records, and final controller state are privileged
   engineering evidence. Their contents are never parsed to construct learner
   rows.

The failure-law label is retained as a predeclared experimental stratum. It
does not reveal any event time or cause realization. Deployment domain labels
are also allowed: placement is a known configuration input, not something that
service-call traces can establish. This distinction prevents a topology claim
from quietly treating failure-domain membership as trace-discovered.

## Native trace normalization

DeathStarBench evidence is read from the frozen Jaeger JSON response. A span's
service comes from its Jaeger process, its replica identity from the process
hostname, and directed service edges from `CHILD_OF` parent relationships.
OpenTelemetry Demo evidence is streamed one OTLP JSON object per line. Service
and replica identity come from resource attributes and edges from span and
parent-span identifiers. Only trace ids assigned to calibration requests are
materialized; unrelated, baseline, sentinel, and test traces are ignored.

The normalized request row retains semantic success, timeout, operation and
branch class, trace presence, the observed service set, and the set of target
replicas actually represented by spans. Multiple target replicas in one trace
are retained as such rather than forced into one backend. Service edges are
reported with both span and distinct-trace support. Declared replica-to-domain
assignments are written separately from the trace-discovered graph.

## Health normalization

Three independently collected rows at each nominal calibration tick are
pivoted into one aligned observation: proxy plus replicas `a` and `b`. The
learner sees container running/paused/health state, network membership count,
and HAProxy backend/check state. It does not see why a state changed. Missing,
duplicate, errored, or incomplete ticks fail qualification instead of being
completed from the controller schedule.

This is deliberately stronger evidence than traces alone. It matches the
article's heterogeneous-telemetry question and gives the strengthened B2 a
fair opportunity to use synchronous health moments. Trace-only and source-loss
ablations in M7 will be deterministic masks of this same admitted evidence,
not separately generated easier datasets.

## Qualification matrix and frozen gates

The input must be one complete, technically accepted 64-cell M7C workflow run
from one commit. Every cell must satisfy all of the following:

- calibration and sequestered test request counts match the signed source
  manifest, request ids are unique, and their intersection is empty;
- every trace declared present by the transport census has at least one parsed
  span, invalid/duplicate spans and unknown target-replica identities are zero,
  and at least 80% of semantic successes retain a native trace;
- the calibration trace graph has at least one cross-service edge and both
  target replicas have positive trace assignment support;
- every calibration health tick contains exactly the proxy and both replicas
  with no sampler error;
- none of the denied controller/event field names occurs in the learner schema
  and no privileged source file is copied below `learner/`;
- all source cells name one workflow run, one tested commit, the expected
  pilot experiment, and `pilot_only=true`.

The workflow fails on any violation but uploads the partial audit. Thresholds
are transport and schema requirements only; no fault-period success fraction
can fail M7D.

## Consequences for the main comparison

M7 will give B0--B4 and the proposed procedure the same admitted raw periods
and masks. B0 uses the direct calibration endpoint rate. B1 removes common
dependence while retaining the same eligible component/channel evidence. B2
uses all available synchronous health moments and complete-case communication
evidence. B3 optimizes the same observed likelihood as the proposed procedure;
agreement wherever the proposed method emits an identified target is a
required correctness check, not an accuracy advantage. B4 receives the same
jointly observed states and must abstain from an unsupported placement transfer
rather than receiving oracle completion.

The primary live contrast remains proposed versus strengthened B2 under the
predeclared incomplete mixed mask. Comparisons with B0, B1, and B4 are
diagnostic and cannot by themselves support superiority. The event/controller
records may later parameterize the explicitly privileged O2 abstraction audit,
which must be labeled separately from every learner method.

## Interpretation boundary

Passing M7D will show only that the evidence boundary is executable on every
pilot schema and that ordinary calibration telemetry exposes the two replicas
and a trace-derived service graph without test or controller leakage. It will
not show that the Boolean factor model is correct, parameters are identifiable,
predictions are calibrated, domains are physically independent, or placement
effects transfer. Those are outcomes or diagnostics of the separately frozen
M7 campaign.
