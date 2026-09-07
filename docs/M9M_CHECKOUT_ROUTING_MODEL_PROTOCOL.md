# M9M: checkout request-level routing-model test

Status: frozen before the first M9M remote candidate generation; technically
amended after failed integrity checks but before any held-out metric was
computed.

## Question

M9L localized most of checkout's calibration route-up residual to logical
requests whose retained trace represented a target-replica path that was down
while the aggregate two-replica union remained up. M9M asks the deliberately
narrow next question: can a request-level multi-call route representation,
learned without the evaluator, account for the checkout discrepancy on the
already retained test boundary?

This is a post-M7 diagnostic model test on one operation. It is not an
independent confirmation, does not revise M7, and cannot establish better
overall accuracy or lower end-to-end automatic cost than PMX.

## Source-grounded operation contract

The frozen driver creates a new user, obtains the fixed product before adding
one item to the cart, and then posts checkout. At the pinned OpenTelemetry Demo
commit, a successful one-item logical request has three required
ProductCatalog call sites:

1. the driver's product prerequisite through the frontend product endpoint;
2. CheckoutService's product lookup while preparing its single cart item; and
3. the frontend's product lookup while rendering the successful order response.

An earlier failure short-circuits later calls. HAProxy is configured for two h2
backends with `balance roundrobin` and 500 ms, fall-one/rise-one checks. These
facts reject the interpretation of checkout as literally one target call, but
they do not reveal an exact per-call backend decision. Connection reuse,
concurrent interleaving, health-aware removal, and recovery can make several
routing laws compatible with the source.

The contract job therefore verifies the local driver and HAProxy source plus
three files from the exact upstream commit. It records byte, SHA-256, Git-blob,
and marker identities before any model is fitted.

## Information boundary

The workflow has three sequential jobs. The middle job first stages the six
selected learner/boundary files per cell plus an 80-row predictor-only
reference extracted from the SHA-256-locked M7 `predictions.csv`. The reference
contains fixed identities, OR/B2 probabilities, and residual probabilities;
it contains no test request, empirical outcome, error, or score. Staging
verifies the complete source schema and copies exactly the eleven declared
columns. It neither copies nor parses an evaluator file. The combined source
download is then removed, and candidate generation receives only that bounded
tree plus the contract.

The request-footprint estimator uses baseline checkout traces retained by the
same deterministic `sampled_mixed` 0.7 trace rule. Selection and weighting do
not inspect semantic outcome. Valid footprints are exactly `{a}`, `{b}`, and
`{a,b}`. Each cell must have at least 20 retained baseline checkout traces,
95% resolved footprints, and a 90% both-replica footprint fraction for the
primary multi-replica interpretation gate. This uses richer trace structure
than M7's Boolean topology edge and its acquisition/processing cost remains
explicit; it is not retroactively counted as free M7 input.

The candidate job uploads its complete probability matrix before the third job
can download test requests or test health. Test outcomes therefore cannot tune
a formula, trace weight, fit threshold, candidate list, or prediction.

## Frozen models

Let `pa` and `pb` be the two binary path states in a latent state, and let `q`
remain the operation-specific clean-baseline residual. All non-checkout target
operations retain the M7 Boolean OR in the calibration likelihood. Checkout is
refitted under each predeclared route-success function:

- `m7_single_demand_or`: `max(pa,pb)`, the unchanged specified M7 model;
- `source_strict_round_robin_and`: `pa*pb`, the literal alternating multi-call
  requirement;
- `source_three_call_independent`: `((pa+pb)/2)^3`, three independent uniform
  assignments conditional on a persistent state;
- `source_two_client_affinity`: `((pa+pb)/2)^2`, two persistent client pools
  independently assigned to replicas;
- `learner_trace_requirement_mixture` (primary):
  `w_a*pa + w_b*pb + w_ab*pa*pb`, with weights from outcome-blind retained
  baseline footprints; and
- the unchanged M7 B2 marginal reference, carried as context rather than
  refitted or weakened.

The intermediate laws are mechanism sensitivities, not a menu from which the
best test score may be selected. Candidate-specific likelihood refitting uses
only sampled learner health and calibration outcomes, the same clean-baseline
`q`, parameter bounds, multistart count, and numerical tolerances as M7. The
original OR and B2 predictions are carried from the locked predictor-only M7
reference and must therefore reproduce frozen M7 within `1e-10`. OR is also
refitted from the learner inputs as an implementation audit, but this numerical
rerun does not replace the frozen predictor. All alternative fits must be
finite and stable across likelihood-equivalent starts within `1e-4`.

## Technical amendments before held-out scoring

The first run stopped in the contract job because the registered digest of the
711-byte M9L decision matrix had been transcribed incorrectly. The second
stopped in the candidate job because the generalized likelihood had omitted
M7's per-route-class probability floor. Both failures occurred without an
evaluator artifact in the fitting job.

The third run uploaded the complete candidate matrix and then stopped at the
evaluator's first integrity check, before constructing any held-out score. B2
matched the frozen M7 matrix exactly. A fresh OR optimization of the identical
learner likelihood differed in 78 of 120 checked fields at the deliberately
strict `1e-10` threshold; the largest absolute difference was only
`7.723766071165983e-09`, far below the already frozen `1e-4` equivalent-fit
tolerance. The correction does not relax either tolerance and does not change
a model, probability, outcome, metric, branch, or candidate order. It carries
the already published frozen OR/B2 predictor values through the sanitized
reference described above, while retaining the OR refit and checking its
difference against `1e-4`. This amendment was made without access to a test
outcome or held-out metric.

## Held-out scoring and branches

Only after candidate upload does the last job open the retained evaluator. It
uses the original one-second transition guard, 1.25-second alignment, and
stable checkout view. Every method is scored in every one of the 40 fixed N/ND
cells using Bernoulli Brier score, signed error, and absolute error. Inference
uses 10,000 campaign resamples within the four placement-by-law strata.

The primary model is called supported on this reused test only if all source,
trace, fit, and identity gates pass; its mean signed error is within the frozen
0.03 probability margin and its interval contains zero; and the paired upper
bounds for both Brier and absolute-error differences versus M7 OR are below
zero. This remains exploratory reused-test support, not confirmation.

If the primary rule fails but a predeclared intermediate law closes the signed
gap while the observation is bracketed between strict AND and OR in at least
32 cells, the result is `checkout_gap_bracketed_but_routing_law_unresolved`.
That branch does not promote the best-scoring sensitivity; it calls for
minimal assignment evidence. Separate branches cover primary overshoot,
continued overprediction under all request-level candidates, inconclusive
results, and integrity failure.

No branch generalizes beyond checkout, modifies M7, selects a new article
claim, reduces PMX's scientific priority, or authorizes live collection. A new
collection requires its own preregistration. All three jobs use
`timeout-minutes: 360`; full staging, fitting, and scoring run only in GitHub
Actions.
