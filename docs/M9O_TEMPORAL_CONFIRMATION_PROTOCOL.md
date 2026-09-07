# M9O: independent temporal-confirmation preregistration

Status: design and precision-planning rule frozen before the M9O remote planning
calculation and before any new collection. This milestone produces a design
artifact; it does not collect or confirm effectiveness data.

## Questions and matched controls

M9N selected independent confirmation, but its state-only marginal predictions
were nearly identical to its age-dependent predictions. Replication must
separate conditional temporal information from marginal forecasting benefit.
M9N, all previous M7-derived diagnostics, and the two design-probe cells are
excluded from the future confirmation sample. Their scores are disclosed pilot
inputs for planning only.

The future primary model remains the M9N midpoint logit, refitted on each new
campaign's learner period. The nested state-only model has exactly the same
health inputs, baseline q, stable selection, and one-path exclusion. The matched
stable endpoint uses a Jeffreys mean `(successes + 0.5)/(attempts + 1)` over
exactly those stable calibration requests, with no extra multiplication by q.
An all-calibration endpoint and the 500 ms reference remain descriptive controls.
Historical M7 constants are not silently carried forward as estimates for a
new campaign. No PAVA or age sensitivity replaces the primary after scoring.

The three prespecified inferential quantities are:

1. Conditional request-level Brier difference, midpoint minus state only.
   Temporal information replicates only if its simultaneous upper bound is
   below zero. This uses test-health covariates and is not an advance forecast.
2. Marginal Brier difference, midpoint minus state only. Practical equivalence
   requires its entire simultaneous interval to lie within [-0.002, +0.002].
   A material incremental advantage requires the upper bound below -0.002.
   Anything between those conditions is unresolved, not selected by sign.
3. Primary marginal signed error. Adequate mean calibration requires the entire
   simultaneous interval to lie within [-0.03, +0.03], a stronger criterion than
   merely including zero in a wide interval.

Use 10,000 campaign resamples within the four placement-by-law strata and
equal stratum weights. A family alpha of 0.05 is split over the three two-sided
intervals by Bonferroni (98.3333% individual intervals). All three quantities are
reported irrespective of outcome. Comparisons to the matched stable endpoint,
all-calibration endpoint, age sensitivities, and 500 ms reference are descriptive
controls; they cannot support a new inferential superiority claim in this family.
In particular, agreement with the endpoint control may explain a marginal result
through response averaging rather than architecture discovery.

## Target, independence, and data boundary

Retain the pinned OpenTelemetry application revision, checkout driver, placement
semantics, N/ND renewal laws, 4 requests/second mixed-operation driver, one-second
health polling, one-second transition guard, and M9N alignment/censoring rules.
The primary target is the stable checkout subset under this measurement policy.
It is not all-traffic availability, behavior during transitions, another
operation, transfer to a new failure law, or an exact routing assignment model.

Each new campaign has a 60-second baseline, a 900-second calibration period,
and a separate 900-second test realization. Use namespace
`m9p-temporal-confirm-v1`, base seed 2026090701, preflight seed 2026090702, and
analysis seed 2026090703. Preserve the existing factor-specific renewal seed
derivation, using the new seed root. The campaign identity matrix is generated
once from the selected repetition count, then hashed and published before main
collection. A new seed alone is not proof of independent evidence: require new
runner executions, new request IDs, fresh schedule realizations, and checks
against M7/pilot provenance and reused files.

Store learner and evaluator output separately. Sanitize predictor-only inputs,
freeze every prospective prediction and parameter artifact, and only then run
evaluation. Request outcomes and held-out health may not influence fitting,
sample-size extension, model selection, or inclusion. Preserve M9N's per-cell
adequacy and optimizer gates. No campaign may be dropped because it weakens a
result. Infrastructure retries retain original attempts and reasons; partial
scientific coverage yields an incomplete confirmation.

Before a main matrix, a separate four-cell no-fit preflight must verify the
namespace, seed separation, image digests, source/deployment compatibility,
request/health schema and timing, learner/evaluator separation, and artifact
retention. It cannot estimate these effects or tune the design. Its observations
are excluded from confirmation. The acquisition and analysis implementation must
be committed and audited against this protocol before the main run. M9O itself
contains no command capable of launching a live benchmark.

## Precision planning and resource gate

Planning reads only locked, already generated M9N campaign-score tables and
candidate predictions. It re-estimates neither M9N models nor test scores. For
each inferential quantity and each of the four strata, compute the ten-pilot-
campaign sample variance `s_h^2` with denominator 9.

Freeze target half-widths at 0.003 conditional Brier, 0.002 marginal Brier
difference, and 0.02 signed probability error. These are transparent design
choices made after M9N; they are not derived from an unpublished confirmation
effect. Let `M=3`, `H=4`, `alpha=0.05`, and
`z=Phi^-1(1-alpha/(2*M))`. Inflate each pilot variance by
`max(4, 9 / chi2.ppf(0.05/(H*M), 9))`. For target half-width `w`, the planning
requirement per stratum is

`n >= ceil(z^2 * sum_h inflated_variance_h / (H^2 * w^2))`.

Choose the first value in `[10, 15, 20, 30, 40]` meeting all three requirements.
If none meets them, publish `precision_budget_requires_redesign`; do not raise
the cap or change half-widths automatically. Publish requirements, achieved
working half-widths at every grid point, and nominal runner-hours. The nominal
cost is `4*n*(60+900+900)/3600`, excluding setup, uploads, preflight, and retries.
All three planning jobs and future experiment jobs use 360-minute timeouts.

This is a working normal approximation with an intentionally inflated pilot
variance, not guaranteed precision or a power calculation. Chi-square variance
limits are exact for normal populations; they are only a planning sensitivity
for these bounded campaign scores. The variance floor of four times the pilot
variance is also not a distribution-free bound. The underlying normal-mean
half-width and normal-variance formulas follow the
[NIST mean sample-size discussion](https://www.itl.nist.gov/div898/handbook/prc/section2/prc222.htm)
and [NIST variance-interval discussion](https://www.itl.nist.gov/div898/handbook/prc/section2/prc231.htm).
The stratified weighting, multiplicity allocation, inflation floor, and resource
grid are this protocol's explicit design choices. Actual confirmation intervals
and missingness determine the eventual conclusion; a narrow pilot interval does
not promise one.

## Information cost and claim boundary

Record bytes, request rows, health ticks, tracing requirements, preprocessing,
fit/evaluation time, runner time, and manual intervention separately for the
all-calibration endpoint, matched stable endpoint, state-only model, and temporal
model. The last three share full health and filtering costs; episode construction
and age fitting are additional temporal costs. Raw tracing is not a required
temporal-model input, but deployment/routing knowledge remains an input.

This design does not provide an independently parameterized PMX comparator.
That remains a separate gate for any general predictive-accuracy or end-to-end
cost claim against PMX. Its scientific priority is unchanged. Neither a
conditional replication nor marginal equivalence resolves that comparison or
establishes the novelty of a generic automatic availability model.

M9O's accepted artifact can make the design ready for implementation and a
no-fit preflight. It is not a completed main experiment and contains zero new
independent effectiveness observations.
