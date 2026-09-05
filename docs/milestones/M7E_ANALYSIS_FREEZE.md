# M7E: frozen acquisition and matched-analysis implementation

## Outcome

M7E is complete. The main live acquisition contract, anti-leakage boundary,
observation masks, B0--B4 comparators, identification-aware matched likelihood,
test scoring, campaign-level inference, and remote-only workflow were committed
and passed CI before any M7 preflight or main request was sent.

This milestone contains no live effectiveness result. Its result is an
executable, hashed analysis plan that cannot select a method, threshold, or
estimand after observing M7 outcomes.

## Immutable references

- implementation commit:
  [`4db1797f4d306506f130a438e625c76e483f27f3`](https://github.com/a-a-k/telemetry-availability-identification/commit/4db1797f4d306506f130a438e625c76e483f27f3);
- guard-test-only correction commit:
  [`c9e360b584e46161aff4642956cd3a07427d8f9b`](https://github.com/a-a-k/telemetry-availability-identification/commit/c9e360b584e46161aff4642956cd3a07427d8f9b);
- accepted two-version CI:
  [run 33985418927](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33985418927);
- superseded CI attempt retained for audit:
  [run 33985333303](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33985333303);
- main configuration SHA-256:
  `42b5611f99051f52ba3c2250b2e82f50ece2ae2e275be7e13796a170b2586b6a`;
- inherited selected-design SHA-256:
  `b4a7f3c71d93c5f216e33f3f7e012703ee47916cc2e767e65120246019bf9b00`.

Every remote cell must copy both hashes plus the M7C/M7C-R run, commit, and
recommendation digests into its source manifest. Both evidence-boundary
contracts reject a mismatch.

## What was implemented

### Frozen execution roles

The generalized stochastic runner preserves the accepted M7C behavior while
adding explicit cell purposes. M7 preflight and main cells use different seeds,
request namespaces, usability fields, and role labels:

- preflight: seed `770036`, namespace `m7-preflight-v1`,
  `pilot_only=true`, `preflight_only=true`, `main_effectiveness=false`;
- main: seed `770034`, namespace `m7-main-v1`, `pilot_only=false`,
  `preflight_only=false`, `main_effectiveness=true`.

The preflight matrix is exactly the two applications by two placements at
`NCD/r0`. Its aggregate performs evidence qualification only. The 160-cell main
matrix starts new deployments and new schedule realizations; no preflight row
can satisfy the main boundary labels.

### Evidence separation

The main learner receives clean baseline requests, fault-period calibration
requests, calibration health, native trace-derived topology, and declared
deployment metadata. Baseline retains its own period label and estimates only
the operation-specific residual semantic-success probability. Calibration
counts, baseline counts, trace joins, native parsing, and source hashes are
audited separately.

Test request outcomes and test health are physically written below
`evaluator/`. Test health is used only for the frozen transition exclusion at
scoring time. Planned schedules, controller events, causes, and transition
times remain privileged and cannot occur in learner schemas. A regression test
constructs baseline, calibration, and test records together and verifies that
baseline and calibration remain distinct while test is absent from learner
output.

### Live abstraction and likelihood

The normalized health series exposes instance signals `H_a,H_b` and routed-path
signals `P_a,P_b`. The co-located model uses one common-domain factor, while the
split model uses independent same-availability domain draws. Active individual,
communication, and domain factors follow the frozen `N/NC/ND/NCD` law; absent
factors are fixed at one.

The observed likelihood enumerates the 32 co-located or 64 split latent states
inside each one-second bin, matches the surviving health pattern, and integrates
the route state against operation-specific binomial request counts. Its temporal
product is explicitly interpreted as a stationary composite likelihood.
Inference never treats the thousands of requests within one campaign as
independent replications.

Eight deterministic-start bounded L-BFGS-B fits form B3. Proposed uses the same
fit and emits a target only when its gradient is in the numerical observable
row space and equivalent optima agree. When proposed emits, its prediction must
equal B3 to `1e-12`; this is a technical correctness gate and cannot be reported
as an accuracy advantage.

### Non-straw-man comparison

The principal comparator is the strengthened B2, not an independence-only
baseline. B2 uses every admitted path and instance marginal, synchronous
co-located health moments when available, channel ratios, and a calibration
endpoint-OR fallback when cross-replica health is unavailable. B3 is a second,
same-model statistical reference. B0 can be competitive for stationary direct
endpoints, and B4 is saturated on complete current-placement path pairs.

The primary contrast is proposed minus B2 Brier loss under `sampled_mixed`, not
proposed minus B0/B1. A favorable result only against B0, B1, or B4 is
insufficient. Equality with B3 is expected. No score sign, p-value, topology
support rate, model fit, abstention count, or placement benefit is a workflow
acceptance condition.

### Scoring and uncertainty

Predictions are scored on separately generated test outcomes. The primary view
excludes requests within one second of an ordinary observed health transition.
Brier scores are averaged equally over operations, paired within campaign, and
then weighted equally over the 16 application--placement--law strata. Ten
campaigns per stratum are the independent units. Standard errors and degrees of
freedom use the predeclared stratified Welch--Satterthwaite calculation.

All-sequence scoring, signed and absolute noisy-test-rate discrepancies,
block-based compatibility, 46-second block sensitivity, all methods/modes, and
co-located-to-split transfer are secondary. Secondary p-values receive Holm
adjustment. Missing identified predictions make the primary result incomplete;
they are not imputed.

## Verification results

The accepted CI ran on CPython 3.11 and 3.13. Both jobs passed:

- all 100 unit tests;
- the frozen M7 main and preflight configuration validators;
- both evidence-boundary validators;
- all existing M0--M7D contract validators;
- the existing bounded ingestion, likelihood, reduction, transfer,
  uncertainty, and stress smokes on Python 3.13.

The new synthetic tests verify deterministic masks, lack of cross-replica joint
health under staggering, complete health removal under trace-only evidence,
the analytic placement distinction, full-data numerical identifiability,
matched B3/proposed equality, trace-only transfer abstention, and mandatory B4
transfer abstention.

The superseded CI run failed one test because the test relied on the ambient
absence of `GITHUB_ACTIONS`; GitHub CI correctly sets it to `true`, so the test
continued into a deliberately missing checkout. The correction makes the
non-GitHub environment explicit inside the test. It changed no runtime code,
configuration, method, threshold, seed, or digest.

## Storage decision

Public-repository standard runner time is suitable for the 160-cell matrix, but
the included artifact-storage allowance is much smaller than the projected raw
native traces. Every successful cell therefore retains compact normalized
evidence and a boundary audit with hashes of all source and privileged files.
Full raw directories are retained by a predeclared rule for all preflight
cells, the four full `NCD/r0` audit cells, and any failed cell. This avoids
outcome-dependent retention while keeping the aggregate under the account
storage limit.

## Interpretation and next milestone

M7E shows that the live study is fully specified and mechanically testable. It
does not show that the topological abstraction fits either benchmark, that
transfer is identified in live data, that split placement helps, or that
proposed improves B2. Those are permitted outcomes of M7, including a null or
negative result.

M7F is the next milestone: run the separate four-cell no-fit preflight, retain
its schema/transport audit, and make no analysis change based on semantic
outcomes. Only after M7F passes may the 160-cell full workflow start.
