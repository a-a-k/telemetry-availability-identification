# M4 simultaneous uncertainty protocol

## Purpose

M4 evaluates whether the M3 placement predictions carry honest input
uncertainty. The primary result is not a narrow interval by itself: coverage and
width must be reported together. A fixed fitted parameter vector plus additional
simulation episodes cannot remove calibration uncertainty.

The experiment reuses the frozen M3 generator, seeds, three common-cause
scenarios, five observation modes, nested sizes 100, 500, and 2,000, and 200
independent campaigns. It performs no fitting on target-placement outcomes.

## Simultaneous observation set

Within each dataset, every available population statistic receives a two-sided
exact Clopper--Pearson interval. The family error probability 0.05 is divided by
the number of constraints in that dataset. The union bound therefore does not
require the statistics to be independent.

The statistics are the two health marginals and, when synchronously observed,
the health intersection and union for each domain. An OR trace supplies a
separate union constraint when it comes from a different observation mask.
Exact duplicates are retained only once. The resulting comparison counts are:

| Mode | Simultaneous constraints |
|---|---:|
| full | 8 |
| sampled mixed | 10 |
| joint health only | 8 |
| staggered health plus traces | 6 |
| trace only | 2 |

The finite-sample statement is conditional on the known, state-independent M3
mask and the independent Bernoulli episodes. M5 separately violates these
assumptions.

## Parameterization and target enclosure

For each domain, let `u = gamma * eta1`, `v = gamma * eta2`, and `g = gamma`.
Then

~~~text
joint = u * v / g
union = u + v - u * v / g
~~~

with `0 <= u,v <= g <= 1`. A branch-and-bound procedure starts from this box,
contracts it with all confidence constraints, and discards a box only when its
interval image cannot intersect a required statistic interval. The maximum box
width at sample size `n` is fixed before the full run as
`max(0.004, min(0.02, 0.20 / sqrt(n)))`: 0.0200, 0.00894, and 0.00447 for the
three nested sizes. A finer large-sample grid prevents discretization from
masking statistical contraction. The search also stops after 12,000 visited
nodes per domain. If the node limit is reached, every unprocessed box is
retained; truncation can widen, but cannot intentionally narrow, the reported
envelope.

Monotonic formulas enclose current, split, and added-replica availability over
the retained boxes. Direct algebra is used for the two changes and the choice
difference to avoid unnecessary subtraction width:

~~~text
r = v / g
change_add = r * (1 - r) * (g - u)
change_split = r * (gamma_b * (1 - u) - (g - u))
choice_split_minus_add =
    r * ((1 - u) * gamma_b - (g - u) * (2 - r))
~~~

The output is called a conservative numerical outer enclosure, not a formally
machine-certified global optimum. Floating-point padding is added, truncated
boxes are retained, unit tests cover the algebra, and the workflow fails if a
generated truth leaves the target enclosure on any dataset whose simultaneous
observable set contains its generating statistics.

In the proved-ambiguous trace-only mode, no optimization-selected decomposition
is used. Split availability is `[0,1]`, the choice difference is `[-1,1]`, and
the add change uses only the structural fact that adding a replica cannot reduce
same-domain availability.

## Quantities

Intervals are reported for current, split, and add availability; both changes
from current; and `split - add`. A placement is selected only when the entire
choice-difference interval is strictly above or below zero. Otherwise the method
abstains.

## Comparators and ablation

- Proposed simultaneous observation set: the finite-sample Bonferroni
  Clopper--Pearson set and conservative target enclosure above.
- B3 marginal Wald: ordinary delta-method intervals from the numerical observed
  Hessian of the exact M3 likelihood.
- B3 Bonferroni Wald: the same Hessian and point fit with the error probability
  divided across all six quantities. This is the strongest standard asymptotic
  interval comparator in this milestone.
- B0 direct endpoint: an unadjusted exact Clopper--Pearson interval for the
  current trace only; it makes no transfer interval.
- A5 fixed-input simulation only: normal Monte Carlo error around the fitted B3
  probabilities for 10,000 simulation episodes, deliberately omitting input
  uncertainty. It is an ablation, not a strong baseline.

Wald and A5 transfer intervals are emitted only when the M3 structural
diagnostic proves the transfer parameters identifiable. A singular numerical
Hessian makes Wald unavailable rather than silently using a pseudoinverse.

## Metrics

For each quantity and method:

- interval availability;
- empirical coverage with a Wilson interval across 200 campaigns;
- mean and median width.

For the proposed set, the artifact also reports simultaneous coverage of all
observable constraints and simultaneous coverage of all six target quantities,
constraint count, box count, truncation/empty-set rate, and runtime. Decision
metrics are coverage, conditional accuracy with a Wilson interval, unconditional
wrong-decision rate, and regret.

Campaigns, not records or nested prefixes, are the replication unit. Coverage is
evaluated against exact generator truth; the independent M3 validation
proportions are not substituted as truth.

## Predeclared expectations

- Proposed simultaneous target coverage should be at least nominal up to
  finite repetition noise and should usually be conservative.
- Width should decrease with sample size and increase as telemetry is removed.
- Trace-only current intervals should shrink, while non-direct transfer remains
  broad and yields no proposed placement decision.
- Marginal Wald may approach nominal marginal coverage in regular large samples
  but does not claim familywise coverage; boundary fits may degrade it.
- Bonferroni Wald should be wider than marginal Wald but can still fail under
  boundary/nonregular behavior.
- A5 should under-cover whenever calibration error dominates the conditional
  simulation error.
- The close weak-common-cause choice should often remain unresolved even when a
  point estimator chooses correctly. Strong-common-cause decisions should
  become certifiable sooner.

## Workflow quality gates

The aggregate job requires:

- no malformed interval;
- no target-enclosure miss when the simultaneous observable set contains truth;
- no incorrect proposed decision when its choice interval contains truth;
- no narrowing of the trace-only split or choice ranges.

Nominal empirical coverage itself is not a build gate: it is a random scientific
outcome and must be reported with its uncertainty, not forced to pass.

## Interpretation boundary

The Clopper--Pearson guarantee applies to the iid, correctly specified synthetic
episode model and known state-independent masks. The box enclosure is
conservative and specialized to the two-domain transfer parameterization. This
milestone does not validate block bootstrap, dependent traces, informative
telemetry loss, model misspecification, or live-system calibration.
