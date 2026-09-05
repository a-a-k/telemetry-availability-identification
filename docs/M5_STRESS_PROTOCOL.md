# M5 directed misspecification protocol

## Purpose and non-strawman comparison rule

M5 characterizes the boundary of the M3--M4 procedure. It does not posit a
generic weak baseline and then add arbitrary noise. Each series changes exactly
one predeclared assumption, keeps a paired neutral control, and applies the
unchanged M4 procedure and the same-model B3 likelihood to the same records.
Where the violation is identifiable with additional structure, a
mechanism-aware reference is included. That reference is labelled as privileged
when it receives the simulated selection or topology law; it is a diagnostic
upper bound, not a deployable baseline.

The intended successful outcome is not universal robustness. A violation may
bias both the proposed point fit and B3. The relevant questions are: what error
appears, whether the declared diagnostic sees it, whether guarded use abstains,
and whether explicitly modelling the mechanism removes the failure.

## Common design

The five mandatory directed series use paired variants and independent campaign
seeds. Sample sizes 500 and 2,000 are nested prefixes; 200 campaigns are the
replication units. The medium-common-cause M3 scenario is the base unless a
series predeclares a matched marginal. Full runs execute only in GitHub Actions.

Reported quantities include all six M4 availability/change/choice functionals
when meaningful. The rare-branch series reports target-mixture availability;
the readiness series also reports direct current availability because an
instantaneous factorization can become logically incompatible with its records.
Coverage and width are always paired. Point error, signed bias, decision
coverage, wrong-decision rate, regret, diagnostic flag rate, fit rejection, and
runtime are retained per campaign.

Four roles are distinguished:

- `proposed_raw`: the unchanged M4 confidence-set procedure under its declared
  iid, state-independent-mask, and correct-domain assumptions;
- `proposed_guarded`: the same result, withheld whenever the predeclared
  diagnostic fires;
- `b3_assumed_model`: the matched exact likelihood (and its ordinary Wald
  interval where regular) under the same potentially wrong assumptions;
- `mechanism_aware_reference`: a selection-aware likelihood, block bootstrap,
  corrected topology, or branch-aware estimate, depending on the series.

`b0_endpoint_persistence` is retained where a directly observed current endpoint
exists. A pointwise oracle truth is evaluator-only and never passed to the raw or
guarded learner.

If individually valid observable intervals have no jointly compatible parameter
set, the procedure emits `incompatible_observation_constraints` and no target
interval. It does not reorder an inverted numerical range or silently widen that
model-rejection symptom into an ordinary confidence result. The same-model B3
point, when it exists, is retained in its own row to measure misspecification
bias.

## S1: exporter loss coupled to a domain failure

Calibration uses staggered health observations plus two OR traces. Both trace
records share an exporter mask. In the control, retention is 0.70 regardless of
state. In the stress, retention is 0.741489 when domain A is up and 0.05 when it
is down. With stationary domain availability 0.94, the marginal retention is
still exactly 0.70. Thus missing-count and sample-size advantages cannot explain
the contrast.

The unchanged likelihood conditions on the mask and is intentionally unaware of
this selection. The mechanism-aware reference includes the known
state-dependent mask probability in the enumerated latent-state likelihood.
The diagnostic compares staggered domain-A health success between trace-present
and trace-absent episodes with a two-sided Fisher exact test at alpha 0.01.

Expectation: the neutral control remains calibrated; the coupled mask biases
the apparent trace success upward and can overstate transfer. The association
diagnostic should usually fire at n=2,000. Failure to fire is reported rather
than treated as evidence that missingness is ignorable.

## S2: persistent episodes at fixed stationary marginals

Every primitive follows an independent stationary two-state Markov chain. The
control has lag-one correlation zero; the stress has correlation 0.90. The
one-time joint distribution, all primitive marginals, and every placement truth
are therefore the same as in M3. Only temporal information changes.

The raw procedure still uses iid binomial constraints. The reference uses a
circular moving-block bootstrap with fixed block length 50 and 199 resamples,
refitting the same exact likelihood on each resample. It reports Bonferroni
percentile intervals for the predeclared transfer availability and choice
difference. Lag-one endpoint correlation is tested at alpha 0.01.

Expectation: point errors remain broadly comparable, while iid intervals
under-cover and the block procedure restores part, not necessarily all, of the
lost coverage. Bootstrap coverage is an empirical result, not a guarantee.

## S3: two declared domains that share one hidden failure domain

Both declared domains have availability 0.94 and retain the same instance
marginals in control and stress. The control samples independent domain states.
The stress makes the two declared domain indicators the same latent state while
leaving the learner's two-domain model unchanged. A move across the declared
labels therefore provides no common-cause diversification in the stress.

The mechanism-aware reference fits a five-factor model with one shared domain.
The diagnostic is a two-sided independence test between the two simultaneously
observed domain OR outcomes. This directly tests a cross-domain implication of
the declared topology; it does not use the target-placement outcome.

Expectation: the unchanged model can predict a spurious split benefit. The
guarded procedure should abstain when cross-domain dependence is visible. The
test cannot certify that all unflagged domain maps are correct.

## S4: rare and unseen conditional branch

An observed request class selects branch A or B. Their exact success
probabilities are 0.985 and 0.78. The target workload has a 0.50 share of branch
B. Calibration shares are 0.50 (control), 0.01 (rare), and 0 (unseen), so the
experiment changes support rather than backend reliability.

The branch-aware procedure constructs simultaneous exact binomial intervals for
both branch probabilities and propagates them to the target mixture. A branch
with no exposure contributes [0,1]; no prior or pooled endpoint value silently
fills it. A B3 saturated branch likelihood is available only when both branches
are observed. Direct endpoint persistence ignores the mixture change. The
diagnostic fires when either branch has fewer than 20 calibration observations.

Expectation: supported controls are narrow and calibrated; rare/unseen targets
are wide or unavailable, while endpoint persistence can be precise for the wrong
mixture. This series evaluates honest support handling, not superiority over an
oracle that knows the unseen branch.

## S5: readiness delay after recovery

Domain A follows a stationary two-state process with availability 0.94 and
down-to-up probability 0.25. The control becomes ready immediately. In the
stress, operation readiness remains false for three episodes after recovery,
while the supplied health field continues to mean liveness. Residual instance
states and the second domain retain their M3 meanings.

The compiled instantaneous model requires the current OR trace to equal the OR
of the two jointly observed replica-health fields. The primary diagnostic counts
violations of this deterministic implication; any violation rejects that data
contract. The raw exact likelihood is allowed to fail on impossible patterns,
and the guarded method must abstain. A direct endpoint point estimate and a
moving-block interval remain descriptive references for current availability;
they do not identify a placement transfer mechanism.

Expectation: the control satisfies the implication exactly. The delayed series
is rejected rather than coerced into a fitted instantaneous model. This isolates
semantic health/readiness mismatch from generic random application failures.

## Paired analysis and quality gates

Every stressed campaign is paired with its neutral control by repetition and
sample size. Aggregate tables report raw results and paired stress-minus-control
changes with campaign bootstrap intervals. With 200 campaigns, empirical rates
are accompanied by Wilson intervals.

Build gates are deterministic rather than outcome-seeking:

- no malformed available interval;
- no guarded estimate or decision survives a fired diagnostic;
- equal marginal trace retention in the two exporter variants to numerical
  tolerance;
- equal stationary primitive marginals in the temporal variants;
- equal component marginals in the domain-map variants;
- zero readiness implication violations in the instantaneous control;
- B3 and the proposed raw point agree whenever both use the same successful fit;
- every requested variant and paired campaign appears exactly once.

Coverage, diagnostic power, and accuracy are scientific outcomes and are never
CI pass/fail gates.

## Interpretation boundary

These are deliberately isolated synthetic violations. They demonstrate failure
signatures and the value of specific audits; they do not show that the same
diagnostics have perfect power in a live system, nor that every misspecification
is detectable from insufficient telemetry. Multiple simultaneous violations,
clock skew, route changes, overload, and ordinary application errors remain
outside M5 unless added as separately named series.
