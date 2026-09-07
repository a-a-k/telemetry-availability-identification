# M9N: checkout temporal-failover model

Status: frozen before the first M9N remote candidate generation or evaluator
access.

## Question and evidential role

M9M placed the retained checkout success rate between static AND and OR in
39/40 cells. OR overpredicted by 0.173061, while the primary request-footprint
model coincided with AND and underpredicted by 0.068427. M9N asks the selected
narrow question: does success while exactly one HAProxy path is usable depend
on the age of the observed path-state episode, and can a learner-only temporal
model marginalize that behavior to the separate retained test realization?

M9N is an exploratory, post-M7/M9M diagnostic on one operation and the same
test realization. It cannot confirm a new model or revise M7. It distinguishes
two outputs: a learner-only marginal forecast and a conditional mechanism score
that applies already frozen parameters to ordinary held-out health. The latter
uses information unavailable to an advance forecast and can never support an
automation or cost claim.

## Disclosed bounded design probe

Before this freeze, two named qualified artifacts were downloaded to check the
retained schema: colocated/N/repetition 0 and split/ND/repetition 0. Only their
`learner/` trees were read. No `evaluator/` file was opened and no full matrix
was calculated locally. Fixed dyadic age summaries in those learner rows made a
multi-second recovery curve feasible, but they are part of the post-hoc design
history. Consequently neither the calibration temporal signature nor any M9N
result is confirmatory.

The primary curve is continuous rather than selected from the probe bins. The
bin edges 0, 1, 2, 4, 8, and 23 seconds are fixed from one-second polling,
dyadic resolution expansion, and M7's 23-second dependence block. The 4-second
early/late split is recorded before the remaining 38 learner cells are opened
by M9N.

## Source and temporal representation

The pinned deployment uses HAProxy round-robin across two h2 backends with a
500 ms check, `fall 1`, and `rise 1`. Ordinary retained health is sampled once
per second and records physical instance state plus HAProxy backend status. It
does not record an individual call's backend, client connection identity,
health-check phase, or retry.

An episode changes when the ordered pair of HAProxy path indicators `(Pa,Pb)`
changes at an ordinary health tick. For an episode first seen at tick `k`, the
true transition is interval-censored between tick `k-1` and tick `k`. Each
aligned request therefore has lower, midpoint, and upper episode ages. A
one-path-up episode already present at the first tick is left-censored and
excluded; both-up and neither-up requests do not need age. Requests within one
second of any change in the full `(Ha,Hb,Pa,Pb)` vector are excluded from both
calibration fitting and stable evaluation, matching M7's frozen view.

The source-literal 500 ms recovery is retained as a falsifiable reference, not
assumed true. It reaches one after 500 ms. The primary learner curve is

`sigmoid(beta0 + beta1 * log1p(midpoint_age_seconds))`

when exactly one path is up, one when both paths are up, and zero when neither
is up. Lower- and upper-age fits measure interval-censor sensitivity. A nested
state-only logistic control removes age. A fixed-bin, weighted monotone PAVA
control prevents the conclusion from depending only on the log-age functional
form. All use the unchanged clean-baseline Jeffreys `q`.

## Information boundary and candidate freeze

The workflow has three sequential jobs. The candidate job stages exactly five
learner/boundary files per cell: boundary, deployment, health, manifest, and
requests. It also stages predictor-only rows from locked M7 and M9M candidate
artifacts. Those rows contain no empirical test rate, error, or score. The
combined preservation and source candidate downloads are removed before fit.

Candidate generation reads full ordinary calibration health. This is richer
input than M7 `sampled_mixed` health and is explicitly charged as diagnostic
information cost. It fits every declared model in all 40 cells, writes the
calibration age/fit audits, freezes all 480 marginal probabilities and temporal
parameters, and uploads them before the evaluator job can download test health
or outcomes.

The learner-only marginal prediction averages each frozen route curve over the
same stable calibration checkout covariates without rereading outcomes during
averaging. This is a forecast for another realization of the same fixed driver,
placement, and failure law. Frozen references are M7 OR, B0, and B2 plus M9M
strict AND, trace requirement, and two-client affinity. B0 is the strong
low-information accuracy reference; a result only against OR is insufficient
for a predictive-advantage statement.

## Adequacy and fitting gates

Every cell must contain at least 500 stable calibration checkout requests, 100
stable one-path-up requests, eight observed one-path episodes, and 20 requests
on each side of the frozen 4-second recovery split. Age intervals may be at
most 1.1 seconds wide. All eight bounded deterministic optimizer starts must be
finite, at least one must converge, and likelihood-equivalent marginal
predictions must span no more than `1e-4`.

The learner-only temporal signature requires a positive late-minus-early
checkout success contrast in at least 32/40 cells and a stratified 95% bootstrap
lower bound above zero. Inadequacy is a substantive branch; it is not repaired
with evaluator data.

## Held-out scoring and decisions

The marginal evaluation scores every frozen constant prediction against the
same stable retained test requests using Bernoulli Brier, signed error, and
absolute error. The separately labeled conditional diagnostic applies frozen
state/age curves to aligned stable test health and computes request-level Brier.
Both use 10,000 campaign resamples within the four placement-by-law strata.

Temporal mechanism support requires all integrity and calibration gates, a
primary marginal signed-error point within 0.03 whose interval contains zero,
paired Brier and absolute-error improvement over OR, a mean prediction span no
larger than 0.02 across lower/midpoint/upper fits (compute the span within each
cell, then average across cells), and a conditional Brier upper
bound below the nested state-only model. A separate stronger label requires
paired Brier and absolute-error upper bounds below frozen B0. Without that B0
result, even a supported mechanism is not a predictive-accuracy advantage.

Predeclared branches distinguish support with or without B0 advantage,
conditional-only evidence, systematic under- or overprediction, absent
calibration recovery, inconclusive evidence, and integrity failure. No branch
selects the monotone, lower, upper, or other sensitivity by its held-out score.

## Interpretation boundary

Observed age dependence would be consistent with failover, stale connections,
or another transition-linked effect; it would not identify an exact HAProxy
assignment mechanism. Lack of age dependence would not prove that HAProxy has
no failover. A one-second poll is not a per-call log, and a conditional score
is not a deployable forecast.

No M9N branch generalizes beyond checkout, modifies prior scores, establishes
overall accuracy, reduces PMX's scientific priority, generalizes a tested PMX
binary to Palladio, or changes the article verdict. M9N invokes no PMX and makes
no live collection. Any assignment instrumentation is a later experiment that
requires its own preregistration. All three jobs use `timeout-minutes: 360`;
full staging, fitting, and evaluation run only in GitHub Actions.
