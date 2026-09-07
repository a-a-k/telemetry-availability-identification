# M9N: checkout temporal-failover model

## Outcome

M9N is complete. Its first execution, [run 34111689492](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34111689492),
passed all three jobs and selected the registered branch
`temporal_model_with_b0_advantage_on_reused_test`. Every integrity, calibration,
interval-sensitivity, and registered scoring gate passed. This is an exploratory
result on the reused checkout test, not independent confirmation or a revised
M7 result.

The primary marginal prediction is 0.765936 against the retained mean success
rate 0.773959. Its signed error is -0.008023, with stratified campaign-bootstrap
95% interval [-0.018671, +0.003344]. Its paired improvement over frozen M7 B0 is
-0.001497 Brier units, interval [-0.002231, -0.000710], and -0.015619 absolute
probability error, interval [-0.023850, -0.006515].

The main qualification is substantive: the age-free `learner_state_only`
control has almost exactly the same marginal forecast and score as the primary
temporal model. The age feature improves conditional request-level prediction
given held-out health, but M9N does not establish an incremental marginal
forecast benefit over the matched state-only control. The B0 comparison changes
both available health information and calibration filtering. Its positive
result cannot be attributed solely to episode age or used to claim a cheaper
automatic predictor.

## Frozen design and execution

The [protocol](../M9N_CHECKOUT_TEMPORAL_FAILOVER_PROTOCOL.md), JSON configuration,
implementation, and 11 new tests were committed before the first M9N remote
candidate generation or evaluator access:

- preregistration and tested commit:
  [`16907146aaa32fac648a4d514956dce6e101c4a4`](https://github.com/a-a-k/telemetry-availability-identification/commit/16907146aaa32fac648a4d514956dce6e101c4a4);
- first and accepted experiment: run `34111689492`, created
  `2026-09-07T10:29:15Z`, completed by `2026-09-07T10:32:34Z`;
- CI: [run 34111678715](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34111678715), successful;
- local verification: 216 unit tests passed in 14.661 seconds, workflow YAML
  and ten shell blocks parsed, and repository locks validated. No full local
  experiment was run.

The unfinished Air work was recovered before completion of the workflow.
The pre-execution audit added an exact learner-file allowlist and byte/hash
reverification immediately before fitting, plus an unchanged-baseline-q check
against all frozen references. It clarified the 0.02 interval-sensitivity gate
as the mean of within-cell lower/midpoint/upper prediction spans; taking a span
of across-cell means could hide opposing shifts. No model or threshold was
selected from an M9N result. This work is recorded in
[M9N_MANUAL_ACTIONS.csv](../M9N_MANUAL_ACTIONS.csv).

The disclosed earlier probe inspected only the learner trees of two named
cells. It remains part of the post-hoc design history. The first attempt needed
no remote correction or rerun.

| Job | UTC start | UTC finish | Duration | Process wall time | Maximum RSS |
|---|---|---|---:|---:|---:|
| Contract | 10:29:19 | 10:29:39 | 20 s | 0.94 s | 107,036 KiB |
| Learner candidate freeze | 10:29:41 | 10:30:52 | 71 s | 47.55 s | 142,216 KiB |
| Held-out evaluation | 10:30:53 | 10:32:33 | 100 s | 75.14 s | 142,252 KiB |

All three jobs had `timeout-minutes: 360`. Source archives were removed before
fitting. The 480-row candidate artifact was uploaded at 10:30:50 UTC; the
separate evaluator job first downloaded retained test evidence at 10:31:12 UTC.
The accepted files, job ordering, and manifest hash chain were checked after
download. No PMX invocation or new live collection occurred.

## Learner evidence and fit integrity

M9N used full ordinary calibration health and five learner/boundary files per
cell, plus 240 sanitized predictor-only reference rows. Those health inputs are
richer than the original M7 `sampled_mixed` view and must be charged as additional
diagnostic information. The learner stage staged 200 files; it did not copy or
parse an evaluator file.

All 40 campaigns had a positive late-minus-early one-path-up success contrast.
The mean contrast was +0.385794, 95% interval [+0.369143, +0.401945]. This supports
a temporal signature within calibration without establishing an exact HAProxy
assignment, connection-reuse, or retry mechanism.

| Gate or audit | Observed |
|---|---:|
| Selected cells | 40 |
| Stable calibration requests, minimum | 874 |
| One-path-up requests, minimum | 133 |
| One-path-up episodes, minimum | 26 |
| Early one-path requests, minimum | 80 |
| Late one-path requests, minimum | 50 |
| Calibration age-interval width, maximum | 1.026635 s |
| Optimizer starts per fit | 8 finite; at least 1 converged |
| Equivalent-fit prediction range, maximum | 2.099e-7 |
| Frozen candidate rows | 480 |
| Parameter rows | 200 |
| Within-cell interval prediction span, maximum | 0.000656 |
| Mean within-cell interval prediction span | 0.000083582 |
| Selected retained files audited in evaluator | 360 |
| Stable marginal and conditional test requests, minimum | 908 |
| Test age-interval width, maximum | 1.022826 s |

The baseline Jeffreys q was 0.9938271604938271 in every cell and matched the
frozen references. All numerical outputs were frozen before held-out scoring.

## Marginal forecasts on the reused test

The following means give every campaign equal weight in the four fixed
placement-by-law strata. Every method was scored on the same stable test
requests. The bootstrap used 10,000 campaign resamples within strata. New
intervals for historical references use the M9N seed; their frozen predictions
and point scores are unchanged.

| Frozen method | Mean prediction | Signed error | Mean absolute error | Mean Brier |
|---|---:|---:|---:|---:|
| M7 OR | 0.947019 | +0.173061 | 0.173061 | 0.204104 |
| M9M static AND | 0.705532 | -0.068427 | 0.069149 | 0.178383 |
| M9M trace requirement | 0.705532 | -0.068427 | 0.069149 | 0.178383 |
| M9M two-client affinity | 0.735340 | -0.038619 | 0.042417 | 0.174978 |
| Source-literal 500 ms failover | 0.947265 | +0.173306 | 0.173306 | 0.204694 |
| Learner state only | 0.765945 | -0.008014 | 0.029804 | 0.173826 |
| Temporal logit, lower age | 0.765930 | -0.008029 | 0.029807 | 0.173826 |
| **Temporal logit, midpoint (primary)** | **0.765936** | **-0.008023** | **0.029802** | **0.173826** |
| Temporal logit, upper age | 0.766013 | -0.007946 | 0.029779 | 0.173824 |
| Monotone-bin sensitivity | 0.766696 | -0.007263 | 0.029491 | 0.173809 |
| Frozen M7 B0 | 0.733139 | -0.040820 | 0.045421 | 0.175322 |
| Frozen M7 B2 | 0.942419 | +0.168461 | 0.168461 | 0.202757 |

Primary minus OR was -0.030279 Brier, interval [-0.033174, -0.027284], and
-0.143259 absolute error, interval [-0.153639, -0.132073]. The primary passed
the closure rule and both B0 improvement rules. The monotone-bin model had the
smallest descriptive Brier, but it was not promoted.

The maximum per-cell difference between the primary and the age-free marginal
prediction was only 0.000138242. Their mean Brier difference was about -5.4e-8;
M9N did not preregister a marginal inferential comparison against state only.
There is a structural reason to expect similar marginal fits: when q=1, an
interior logistic fit with an intercept matches the observed mean success over
its fitting rows. Averaging both state-only and age-dependent fits over those
same one-path calibration covariates then gives the same marginal contribution.
Here q is slightly below one, so that exact identity is not asserted, but the
observed near-equality requires a matched-control continuation.

## Conditional mechanism diagnostic

Conditional scoring applied frozen curves to ordinary held-out health. The
primary conditional Brier was 0.043499, compared with 0.054409 for the nested
state-only control. Their paired difference was -0.010910, 95% interval
[-0.012433, -0.009458]. Thus episode age carries request-level information beyond
path state under the retained measurement policy.

This is a separate task from advance marginal forecasting. The much lower
conditional scores use test-health covariates that an advance constant forecast
does not have. They cannot be compared to the marginal table as an automation
gain. Conditional signed error remained -0.008785, interval
[-0.012731, -0.004732]; passing the registered conditional Brier gate does not
mean all conditional calibration discrepancies vanished.

The literal 500 ms reference does not explain the effective recovery. Stable
one-path records survive a one-second transition guard, so this reference has
already reached route probability one for them. Its near-OR forecast is an
expected consequence of the reference and observation contract, not evidence
that the physical health-check interval is incorrectly documented.

## Accepted artifacts

All three artifacts were unexpired when verified and are retained until
2026-12-06 10:29:16 UTC. The values below are GitHub's compressed archive digests;
individual downloaded files were checked separately against their manifests.

| Artifact suffix | ID | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| `contract-34111689492` | 10014601348 | 3,118 | `87094086ba06bcdf2b01337c74a98dcc3318158087e07f26596e5df8057dff9e` |
| `candidates-34111689492` | 10014640872 | 46,566 | `1659e65c220a9e79949ed8bbf541c88a957fd190506db5d19817685780fc7038` |
| `evaluation-34111689492` | 10014697606 | 62,670 | `ff8d15ec006bfed4eb694c9d888567f0fb3d6337c3d730f9251d10630a8b4c3b` |

Every full name starts with `m9n-checkout-temporal-`.

| Principal file | Bytes | SHA-256 |
|---|---:|---|
| `contract-manifest.json` | 7,446 | `561f1fa60258ad14316bbc002b41e76d1c0be0ef390657ab328ad947b520bd44` |
| `candidate-manifest.json` | 2,747 | `17f04de6331905e243c20a5d4b2db998b8a3b63ebf306036f08754893f1b8afa` |
| `candidate-predictions.csv` | 78,703 | `9806736e3818ec1dcf563cf07ce2b16a338bc5a54021b1f2ff08323df917273b` |
| `calibration-age-audit.csv` | 12,313 | `f66dfde6e1c5b3d49d329996ccf3890a72f748fdaa013837a63dd57f82a65af2` |
| `evaluation-manifest.json` | 34,352 | `af12932512e18617e8bfe6eb5ec00afbe682e9236a56315a141ba4e18b923daf` |
| `bootstrap-summary.csv` | 20,779 | `ac6f2f4dfa8f116d3b390a8ba8e26423ccf477c0e0c4b3e908316ba5040d990c` |
| `decision-matrix.csv` | 2,097 | `63ee5a1c8ae698126b1eef27a55bf970461d377ca0883a42688c7ae71b96ec04` |

## Interpretation and continuation

The evidence supports a temporal component in the retained checkout residual
and a substantially better stable-subset forecast than static OR. It does not
identify exact backend assignments, prove an incremental marginal contribution
of age over matched state only, generalize to other operations, or establish
lower end-to-end cost than PMX. The original broad article assessment remains
unchanged. The new narrow result should be added with its data-reuse and
information-cost qualifications, not substituted for M7.

The registered next branch is
`m9o_independent_temporal_confirmation_preregistration`. Its design must freeze
independent campaign identities, targets, sample size, and the learner/evaluator
boundary before collection. It must retain frozen M7 B0 and additionally include
a state-only model and an endpoint baseline using the same stable learner
selection. It must distinguish a marginal forecast advantage from conditional
temporal mechanism replication, charge health/filtering inputs, and retain the
separate unresolved independently parameterized PMX comparison. The reused M9N
test may inform a transparently labelled planning calculation, but cannot be
counted as a new confirmation campaign.
