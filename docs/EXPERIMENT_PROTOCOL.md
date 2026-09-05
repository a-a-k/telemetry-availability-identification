# RQ1 synthetic identifiability protocol

## Scientific question

Under which supported observation mechanisms are primitive domain, residual
instance, and residual channel probabilities identifiable, and how does finite
sample size affect estimation error and practical rank diagnostics?

This protocol instantiates the restricted conjunctive submodel proposed for T1.
It does not stand in for the later live-system validation of the full simulation
model.

## Data-generating process

For each family and independent campaign, the generator samples the maximum
configured number of primitive Bernoulli states once. Observable values are
deterministic conjunctions of those states. Sample sizes 100, 500, and 2,000 are
nested prefixes of the same campaign.

Observation masks are generated separately from primitive values. This makes the
initial missingness mechanism known and non-informative. All trace observables in
an episode share one root-trace sampling decision. The no-joint-health mode exposes
exactly one health observable per episode and therefore removes simultaneous
health moments without pretending that the underlying states are independent.

The initial protocol deliberately excludes exporter loss correlated with a host
failure. That mechanism will be a separate misspecification experiment.

## Structural reference

For every observation mode, all supported observable subsets up to the configured
moment order are enumerated before data generation. Their primitive-factor unions
form the structural incidence matrix H. Its rank and row space define the reference
classification for this restricted model.

An individual log-parameter is identifiable when its unit vector belongs to the
row space of H. A conjunctive target is identifiable when its factor-incidence
vector belongs to the same row space. General Boolean predicates are intentionally
not classified by this criterion.

## Finite-sample procedure

For each nested prefix:

1. Retain moment rows with at least 20 jointly observed episodes.
2. Collapse algebraically duplicate factor-union rows to the deterministic
   highest-exposure representative; preserve every raw moment in the artifact.
3. Compute empirical rank, singular values, and condition number.
4. Fit a weighted log-moment baseline using the available positive moments.
5. Emit estimates only for parameters or target functionals classified as
   identifiable from the usable rows.
6. Compare estimates with generator truth in evaluator-only output.

The learner receives observable values and masks. It does not receive primitive
states or generator probabilities during estimation.

## Matrix and unit of repetition

The full configuration contains:

- four factor-graph families;
- three observation modes;
- three nested sample sizes;
- 200 independent campaigns.

This yields 7,200 fitted prefixes. The independent repetition is the campaign,
not the prefix and not an individual observable record. Any later confidence
analysis must preserve this grouping.

## Predeclared output metrics

- structural and empirical rank;
- full-rank diagnosis accuracy;
- target-identifiability diagnosis accuracy;
- parameter estimate availability and MAE;
- parameter signed bias;
- target estimate availability, MAE, and signed bias;
- false-confident parameter rate;
- fit completion rate and moment counts.

Coverage is not reported by this slice because a valid joint uncertainty procedure
has not yet been implemented. Monte Carlo variation of the generated campaigns is
not presented as interval coverage.

## Interpretation boundary

A full-rank result shows identifiability only for the configured primitive
conjunctive model and supported observation moments. It does not prove that a real
telemetry source obeys the same observation mechanism, that the inverse problem is
well-conditioned, or that a general endpoint predicate is identifiable.
