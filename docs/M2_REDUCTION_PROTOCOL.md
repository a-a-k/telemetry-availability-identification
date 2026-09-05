# M2 structure-preserving likelihood reduction protocol

## Purpose

M2 evaluates the first identification-aware compilation rule rather than a new
statistical objective. The proposed procedure and B3 must optimize the same
observed likelihood. Any accuracy difference beyond numerical tolerance is a
failure, not a claimed advantage.

## Reduction rule

For the supported conjunctive model, every primitive factor has a binary
signature indicating membership in each observable retained by the observation
policy. Factors with the same nonzero signature always occur together. They are
replaced by one composite Bernoulli factor whose probability is the product of
their probabilities. Factors with an all-zero signature are removed from the
likelihood as structurally unobserved.

Because the groups are disjoint and their members co-occur in every supported
observable, replacing each group by its conjunction preserves the full joint
distribution of those observables. A target is representable after reduction
only when it contains every member or no member of each group and contains no
inactive factor.

The compiler enumerates the complete supported moment set for these small models
and labels each original parameter and conjunctive target as:

- `proved_identifiable` when its log-incidence vector lies in the row space;
- `proved_ambiguous` when a null-space witness gives two interior parameter
  vectors with equal observable moments and different quantity values;
- `unresolved` when neither certificate is produced.

The rule is tested by independently enumerating original and reduced observable
distributions for every configured family and mode. Equality is required to
floating-point tolerance.

## Matched experiment

The methods are:

- `b3_exact_likelihood`: the M1 exact likelihood on all original primitive
  states;
- `proposed_reduced_likelihood`: the identical optimizer and likelihood compiler
  after signature reduction.

The reduced bounds are the exact products of the original primitive bounds, so
the numerical parameter spaces remain equivalent. Both methods receive the same
campaign prefix. B3-derived products and proposed composite estimates are
reported on the same scale. Unsupported individual estimates remain absent.

The frozen M0 configuration supplies four families, three modes, three nested
sample sizes, and 200 campaigns. Diagnostic and full runs execute only in GitHub
Actions.

## Predeclared checks and metrics

- original and reduced parameter/state counts;
- distribution-preservation unit tests;
- explicit ambiguity witnesses and maximum observable-moment discrepancy;
- convergence, boundary contact, and runtime;
- objective equivalence for every converged pair, with tolerance
  `1e-6 * max(1, abs(B3 NLL))`;
- individual, identifiable-combination, and target estimate rates and MAE;
- paired error differences, defined as proposed minus B3;
- paired runtime ratio, defined as B3 divided by proposed.

The aggregate workflow fails when any paired likelihood objective violates the
predeclared equivalence tolerance.

## Interpretation boundary

Exact statistical agreement supports correctness of the reduction. State-space
or runtime reduction supports only a computational claim for observation patterns
that contain equivalent factors. Full-observation cases should not improve.
This milestone does not yet supply non-direct Boolean targets, B0/B1/B4, interval
coverage, robustness, trace-to-model adapters, or live validation. Those remain
separate milestones so a standard exact solver is never replaced by a weaker
comparator.
