# M4 completion report: simultaneous uncertainty

## Outcome

M4 is complete. The experiment propagated simultaneous exact-binomial
constraints through a conservative numerical parameter-set enclosure for all
M3 telemetry modes. Across the 45 scenario/mode/size cells, simultaneous
coverage of all six target quantities ranged from 0.955 to 1.000 (mean across
cells 0.9926). Width contracted with sample size in every proposed
scenario/mode/quantity cell. Trace-only data narrowed the currently observed
endpoint but correctly left split availability at width 1 and the placement
choice difference at width 2.

This is a coverage result under the frozen iid, correctly specified generator.
It is not evidence of robustness to dependent episodes, informative exporter
loss, or a wrong failure-domain map; M5 tests those assumptions directly.

## Frozen implementation and workflow evidence

- implementation commit: `35616880c701bbc6aafa45d0970a3dcfa5378e2f`;
- CI run `33962616556`: passed on Python 3.11 and 3.13, including 36 unit tests
  and all bounded smoke/configuration checks;
- adaptive-grid diagnostic run `33962668069`: passed all three scenario shards
  and aggregate quality gates;
- full run `33962760595`: passed all three 200-campaign scenario shards and the
  aggregate job in 13 minutes 30 seconds wall-clock;
- aggregate artifact `m4-aggregate-33962760595`: artifact id `9968638288`,
  9,532,754 compressed bytes, retained through 2026-10-05.

An earlier diagnostic run, `33962435129`, used a fixed grid tolerance. Inspection
showed that it could hide large-sample contraction behind discretization. It was
superseded before the full run by the predeclared adaptive tolerance
`max(0.004, min(0.02, 0.20/sqrt(n)))` and is not used as result evidence.

The aggregate manifest records CPython 3.13.15 on Linux, NumPy 2.4.4, SciPy
1.17.1, PyYAML 6.0.2, a clean worktree, and the tested Git/GitHub SHA above.

## What was implemented

For every available observable statistic, M4 builds a two-sided
Clopper--Pearson interval with alpha divided by the number of constraints in the
dataset. The union bound remains valid even though health intersections, unions,
and traces are dependent. The number of nonduplicate constraints is 8 for full
or joint-health data, 10 for sampled mixed data, 6 for staggered health plus
traces, and 2 for trace-only data.

For each two-replica domain, the search uses `u=gamma*eta1`,
`v=gamma*eta2`, and `g=gamma`, contracts boxes against marginal/joint/union
constraints, and retains any box not proved incompatible. Monotone algebra then
encloses current, split, and added-replica availability and their changes. A
placement is emitted only if the complete interval for `split-add` lies on one
side of zero. Unprocessed boxes at the node budget are retained, so numerical
truncation widens rather than deliberately narrows an answer.

Comparators were run on exactly the same campaign prefixes:

- ordinary marginal B3 Wald intervals;
- six-quantity Bonferroni B3 Wald intervals;
- direct endpoint Clopper--Pearson for current availability only;
- A5 fixed-input simulation-only intervals, explicitly omitting calibration
  uncertainty.

The full artifact contains 270,000 interval rows, 9,000 confidence-set rows,
61,200 constraint rows, 45,000 decision rows, 1,350 interval summaries, 45 set
summaries, and 225 decision summaries.

## Coverage

The simultaneous observable-set coverage ranged from 0.930 to 0.990 across the
45 cells (mean 0.9713). The corresponding all-six-target coverage ranged from
0.955 to 1.000. Target coverage can exceed observable-set coverage because a
missed primitive-statistic interval need not move any target outside its wider
propagated envelope.

The lowest proposed marginal coverage was 0.955 for current availability in the
medium, trace-only, n=500 cell; its Wilson 95% interval is [0.917, 0.976]. All
other proposed quantity cells were at least 0.965, and transfer quantities were
typically 0.99--1.00. Thus no observed cell contradicts nominal coverage at the
precision available from 200 independent campaigns, while the systematic excess
shows that the construction is conservative.

At n=2,000 in the sampled-mixed mode, a representative comparison is:

| Scenario | Quantity | Proposed coverage / width | B3 marginal Wald | B3 Bonferroni Wald | A5 simulation-only |
|---|---|---:|---:|---:|---:|
| weak | split | 1.000 / 0.01746 | 0.915 / 0.00739 | 0.960 / 0.00995 | 0.780 / 0.00466 |
| medium | split | 1.000 / 0.01575 | 0.920 / 0.00519 | 0.985 / 0.00699 | 0.830 / 0.00389 |
| strong | split | 1.000 / 0.01340 | 0.965 / 0.00391 | 0.990 / 0.00527 | 0.915 / 0.00333 |
| weak | choice | 1.000 / 0.04810 | 0.940 / 0.01730 | 0.995 / 0.02329 | 0.530 / 0.00627 |
| medium | choice | 1.000 / 0.06521 | 0.955 / 0.02211 | 0.995 / 0.02976 | 0.600 / 0.01004 |
| strong | choice | 1.000 / 0.06504 | 0.945 / 0.02605 | 0.995 / 0.03507 | 0.600 / 0.01172 |

The table does not establish universal superiority. B3 Bonferroni is much
narrower and is well calibrated in these regular large-sample cells. Its
finite-sample/nonregular weakness is visible elsewhere: across available cells,
the lowest marginal and Bonferroni Wald coverage was 0.135 for the strong,
staggered-health, n=100 add-change quantity. Bonferroni correction cannot repair
a poor local Gaussian approximation. A5 is narrow because it answers the
conditional simulation question; its minimum observed coverage was 0.05 and its
mean across available cells was 0.497.

## Information loss and contraction

For the medium-common-cause scenario at n=2,000, proposed mean widths were:

| Observation mode | Split availability | Choice difference |
|---|---:|---:|
| full | 0.01060 | 0.05070 |
| sampled mixed | 0.01575 | 0.06521 |
| staggered health plus traces | 0.02745 | 0.09803 |
| trace only | 1.00000 | 2.00000 |

The ordering isolates information loss: full and joint-health-only are equal
because their trace unions duplicate jointly observed health information;
sampling and removal of joint health widen transfer ranges; trace-only records
cannot identify the decomposition needed for a move.

For every proposed cell, mean width decreased from n=100 to 500 to 2,000. For
example, medium sampled-mixed split width contracted 0.08454 -> 0.03033 ->
0.01575 and choice width contracted 0.25755 -> 0.12827 -> 0.06521.

## Placement decisions

No proposed decision was wrong in the full run. This includes abstentions, which
are counted as unavailable rather than correct. At n=2,000:

| Scenario | full / joint health | sampled mixed | staggered health + traces | trace only |
|---|---:|---:|---:|---:|
| weak | 0.000 | 0.000 | 0.000 | 0.000 |
| medium | 1.000 | 0.985 | 0.095 | 0.000 |
| strong | 1.000 | 1.000 | 0.310 | 0.000 |

Each number is decision coverage; conditional accuracy was 1.000 wherever the
proposed method decided. The weak case therefore gives the intended substantive
result: a close point-estimate preference is not promoted to a confident
placement claim. The medium and strong cases become certifiable as evidence
improves, while staggered health remains substantially less decisive.

By contrast, A5 decided in roughly half the weak n=2,000 campaigns and made
wrong decisions: wrong-decision rates were 0.025 in full/joint, 0.075 with
staggered health, and 0.090 in sampled mixed. Its extra simulation draws made the
conditional interval look precise without resolving input uncertainty.

## Numerical behaviour and quality gates

Mean enclosure runtime by cell ranged from 0.00065 seconds (analytical
trace-only fallback) to 0.488 seconds per dataset; the mean of cell means was
0.209 seconds. No confidence set was empty.

The 12,000-node budget was reached frequently in the least informative
staggered-health mode: 51--61% at n=100 and 86--96.5% at n=2,000 depending on
scenario. Sampled-mixed truncation fell with n and was zero or 1% at n=2,000;
full, joint-health-only, and trace-only cells did not truncate. Because pending
boxes are retained, this is an efficiency/tightness limitation rather than an
observed anti-conservative failure. Claims about optimal interval width would
require a higher-budget sensitivity analysis.

All aggregate deterministic gates were zero:

- malformed intervals: 0;
- target-enclosure misses conditional on observable-truth containment: 0;
- unsafe proposed decisions conditional on choice-truth containment: 0;
- trace-only transfer narrowing: 0.

## Interpretation and next milestone

M4 supports the narrow claim that, for this small correctly specified iid
two-domain model, simultaneous observable uncertainty can be propagated into
honest, informative transfer ranges in under one second per dataset. It also
quantifies the cost: intervals are wider than asymptotic B3 in regular cells and
may be numerically loose when evidence is staggered.

It does not support distribution-free coverage, automatic detection of model
error, arbitrary Boolean graphs, or live-system calibration. M5 therefore keeps
the same strong B3 reference and tests five named boundaries: domain-coupled
exporter loss, temporal bursts at fixed marginals, a hidden merged failure
domain, rare/unseen branches, and readiness lag.
