# M5: directed misspecification and telemetry-loss stress tests

## Outcome

M5 is complete. Five separately generated assumption violations were evaluated
against paired neutral controls with the unchanged M4 procedure, the matched B3
likelihood, a direct endpoint baseline where meaningful, and explicitly
privileged mechanism-aware references. All 4,400 campaign prefixes completed in
GitHub Actions and every deterministic integrity gate passed.

The result is intentionally not universal robustness. State-dependent exporter
loss and a wrong failure-domain map caused large, increasingly confident errors
in the assumed likelihood. Persistent episodes caused substantial interval
undercoverage even though point estimates remained useful. Rare or unseen
branches required wide or withheld target-mixture predictions. Readiness delay
made the instantaneous health model logically incompatible with the data. The
predeclared diagnostics usually detected these signatures, and guarded output
was always withheld after a flag, but missed flags at smaller samples did not
make the remaining output safe.

## Frozen evidence and provenance

- implementation and predeclared protocol commit:
  `18564bf1b9c5bd1cce0bb871540e7a5c85af9b11`;
- explicit incompatible-constraint representation and tested commit:
  `8cea96efdc8694e8323af2f5270cb7fc63163ec0`;
- CI: [run 33964718493](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33964718493),
  successful on Python 3.11 and 3.13;
- accepted diagnostic workflow:
  [run 33964762435](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33964762435),
  successful;
- frozen full workflow:
  [run 33964880473](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33964880473),
  successful;
- aggregate artifact: `m5-aggregate-33964880473`, id `9969926713`,
  2,638,834 compressed bytes, SHA-256
  `907ac58006f85d3e03e73d9454e67564a3765a9f7dbd30db0feede2b0cf5545f`,
  retained through 2026-10-05.

The five shard artifacts and ids are:

| Series | Artifact id | Compressed bytes |
|---|---:|---:|
| exporter loss | 9969162082 | 724,037 |
| temporal bursts | 9969919757 | 673,488 |
| wrong domain map | 9969135834 | 651,720 |
| rare branch | 9969098700 | 152,543 |
| readiness lag | 9969125103 | 450,612 |

The aggregate ran on CPython 3.13.15 with NumPy 2.4.4, SciPy 1.17.1,
and PyYAML 6.0.2. Its manifest records a clean worktree, exact tested SHA,
workflow identifiers, dependency versions, and source-shard count; the frozen
configuration is versioned at the tested commit.

## What was implemented

Each series has its own generator and changes one named assumption while keeping
a paired variant with the same campaign, sample size, and relevant marginals.
Sizes 500 and 2,000 are nested prefixes of 200 independently seeded campaigns.
The learner does not receive generator truth or a violation label.

- **Exporter loss:** independent 0.70 trace retention is paired with
  domain-state-dependent retention having exactly the same marginal rate. The
  reference likelihood is given the selection law; the learner is not.
- **Temporal bursts:** iid primitive states are paired with stationary Markov
  chains having lag-one correlation 0.90 and unchanged one-time marginals. The
  reference uses a circular moving-block bootstrap with block length 50 and 199
  resamples.
- **Wrong domain map:** two independent declared domains are paired with two
  labels backed by the same hidden domain. The reference receives the corrected
  five-factor topology.
- **Rare branch:** calibration branch-B shares are 0.50, 0.01, and 0 while the
  target mixture is fixed at 0.50. The branch-aware exact interval assigns an
  unseen branch the honest range [0,1].
- **Readiness lag:** immediate readiness is paired with a three-episode delay
  after recovery while the supplied health field continues to mean liveness.
  The evaluator never relabels liveness as readiness.

The unchanged raw procedure, diagnostic-gated version, B3 assumed-model fit,
mechanism-aware reference, and B0 endpoint persistence are stored separately.
The implementation retains points, intervals, diagnostic availability, fit and
boundary states, abstentions, decisions, exact regret, paired campaign effects,
and runtime. A contradictory confidence system is represented as
`incompatible_observation_constraints`; inverted bounds are never reordered
into a plausible-looking interval.

## Executed matrix and integrity

The full aggregate contains:

- 4,400 campaign-prefix rows;
- 102,000 quantity/method estimate rows;
- 4,400 diagnostic rows and 22 diagnostic summaries;
- 16,000 placement decisions and 80 decision summaries;
- 260 paired stress-minus-control effects;
- 510 estimation/coverage summaries.

All seven deterministic quality counters were zero: invalid intervals,
nonfinite truths, missing paired controls, B3/proposed point mismatches,
guarded estimates or decisions after a diagnostic rejection, and readiness
implication failures in the immediate-readiness control. Thus the experiment
was permitted to report poor coverage or accuracy, but not malformed or
selectively missing evidence.

The first diagnostic execution,
[run 33964605249](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33964605249),
is superseded but retained. Its aggregate correctly rejected five inverted
readiness intervals. The follow-up commit made the underlying incompatibility an
explicit no-interval status and added a regression test; it did not swap bounds
or relax the quality gate. The valid diagnostic and full runs used that fix.

## Diagnostic behavior

The table reports the fraction of all 200 campaigns flagged. Controls are shown
after the slash. The rare and unseen rows share the supported-branch control.

| Violation / diagnostic | n=500 stress / control | n=2,000 stress / control |
|---|---:|---:|
| domain-coupled exporter mask | 0.885 / 0.000 | 1.000 / 0.015 |
| persistent endpoint dependence | 0.950 / 0.010 | 1.000 / 0.010 |
| hidden merged domain | 1.000 / 0.005 | 1.000 / 0.015 |
| rare branch below 20 observations | 1.000 / 0.000 | 0.550 / 0.000 |
| unseen branch | 1.000 / 0.000 | 1.000 / 0.000 |
| liveness/readiness implication failure | 1.000 / 0.000 | 1.000 / 0.000 |

The falling rare-branch flag rate at n=2,000 is the declared absolute-support
rule working as specified: 45% of campaigns accumulated at least 20 branch-B
observations. It is not interpreted as lower test power. Control false-positive
rates of 0--1.5% are compatible with the individual alpha 0.01 checks at this
Monte Carlo resolution; no multiplicity-adjusted global detector is claimed.

Every n=2,000 stressed campaign was flagged for the other four mechanisms. At
n=500, however, the exporter and temporal tests missed 11.5% and 5% of
campaigns. Conditional coverage of the resulting guarded choice intervals was
only 0.043 and 0, respectively. A passed diagnostic is therefore not a model
certificate. Guarding prevents use after observed evidence of violation; it
cannot prove ignorability or iid behavior when power is limited.

## Result by mechanism

### State-dependent exporter loss

At n=2,000, the assumed B3 choice-difference point had MAE 0.06232 and signed
bias -0.06232; its Wald interval had zero coverage. Relative to the paired
independent-mask control, choice MAE increased by 0.05692 with a 95% campaign
bootstrap interval [0.05629, 0.05756], despite equal marginal trace retention.
B3 selected the wrong placement in all 200 campaigns, with mean regret 0.05004.

The unchanged proposed point is exactly the B3 point, as it should be. Its wider
choice interval also had zero coverage, but did not separate the two placements,
so the raw interval procedure made no placement decision. The selection-aware
reference reduced choice MAE to 0.00660 and selected correctly in all campaigns;
its split-availability MAE was 0.00134 versus 0.00409 for the assumed fit. The
diagnostic flagged every n=2,000 campaign and the guarded procedure withheld all
outputs. This is evidence against ignoring informative telemetry loss, not an
accuracy advantage over a matched correctly specified likelihood.

### Persistent episodes

Point estimates degraded but did not acquire a large systematic bias. At
n=2,000, persistent-minus-iid paired MAE increased by 0.00233 for split
availability and 0.01390 for the choice difference. The raw M4 interval retained
coverage 0.860 for split and 0.760 for choice, below its iid-control coverage of
1.000 in both quantities.

The fixed moving-block reference widened mean intervals from 0.01122 to 0.01621
for split and from 0.05233 to 0.08138 for choice. Coverage improved to 0.945 and
0.900, respectively. It therefore restored much, but not all, of the lost
coverage. Ordinary B3 Wald coverage was only 0.380 and 0.290. Raw proposed
intervals made a placement decision in 87.5% of n=2,000 campaigns and all of
those decisions were correct; that decision result does not repair quantity-
level undercoverage. The lag diagnostic fired in every n=2,000 campaign, so the
guarded method abstained.

### Hidden merged failure domain

The assumed two-domain model attributed false diversification to the declared
split. At n=2,000 its split-availability MAE and positive bias were both about
0.05046, with zero interval coverage. The choice-difference MAE was 0.05083.
The raw proposed interval chose a placement in every campaign and all 200 choices
were wrong; B3's point choice was likewise wrong in every campaign.

The corrected-topology reference reduced split MAE to 0.00435, achieved 0.955
split-interval coverage, and chose correctly in every campaign. Relative to the
paired independent-domain control, raw split MAE increased by 0.04952,
bootstrap interval [0.04930, 0.04974]. The dependence diagnostic flagged every
stressed campaign at both sizes, so guarded output made no unsafe decision.
This is the clearest M5 example of why a deployment label alone is not evidence
of independent failure domains.

### Rare and unseen branches

For the supported 50/50 control at n=2,000, the simultaneous branch interval had
coverage 1.000 and mean width 0.03885; its point MAE was 0.00518. With a 1%
calibration share, the raw branch interval retained coverage 0.990 but widened
to 0.22312. A point was support-eligible in only 45% of campaigns; guarded output
retained exactly those campaigns and had conditional coverage 0.989.

With no branch-B observation, no branch point was fabricated. The honest target-
mixture interval had coverage 1.000 and mean width 0.50630. Guarded output
withheld it after the support diagnostic, while the raw interval remains useful
as an explicit partial-identification range. Endpoint persistence looked precise
but was wrong: at n=2,000 its target-mixture bias was +0.10271 and interval
coverage was zero. The paired rare and unseen increases in endpoint MAE were
0.09523 and 0.09725. More observations of the wrong workload mixture cannot
identify an unobserved conditional branch.

### Readiness delay

Every delayed-readiness campaign violated the deterministic implication between
the two liveness fields and current request success, so the guard rejected all
outputs. The assumed B3 likelihood was unavailable in all 400 delayed prefixes.
At n=2,000, 100 of 200 confidence systems were explicitly incompatible, 94 used
a conservative empty-set fallback, and only six returned an ordinary outer
set. The raw current interval was available in half the campaigns, with 0.940
conditional coverage only because fallback ranges produced a mean width of
0.940. At n=500, before constraints became sharp enough to contradict, its
coverage was only 0.205 with mean width 0.02545.

The direct endpoint point remained descriptive: its current-availability MAE
was 0.01743 versus 0.01186 in the immediate-readiness control. Its moving-block
interval achieved only 0.870 coverage at n=2,000. Notably, the immediate-
readiness control still uses a temporally dependent domain process; raw iid
current coverage there was 0.685. This series therefore validates the semantic
rejection signal but also supplies a negative uncertainty result: fixed block
length 50 is not automatically sufficient for every transition process.

## Computational cost

Temporal resampling dominated the experiment. Across 800 temporal prefixes,
mean recorded analysis time was 4.315 seconds and the sum was 3,451.8 seconds;
the GitHub shard took about 58 minutes. Mean per-prefix times for exporter,
wrong-map, readiness, and rare-branch series were approximately 0.343, 0.202,
0.144, and 0.0006 seconds. The other four shards completed in under five
minutes each including environment setup. This is a useful budget warning for
M7 block-length sensitivity and motivates campaign-level sharding rather than
silently reducing resamples.

## Interpretation

M5 supports five bounded conclusions:

1. Matching marginal trace retention does not make missingness ignorable; a
   state-coupled mask can reverse a placement choice under both the proposed
   point fit and matched B3.
2. Correct one-time marginals do not validate iid intervals. A block procedure
   can improve coverage without guaranteeing nominal performance for a fixed
   block length.
3. A wrong domain map can create a fully confident but fictitious
   diversification gain; an audited cross-domain dependence test can expose
   this particular violation.
4. Conditional branch support, rather than total request count, determines
   whether a changed workload mixture is predictable. An unseen branch must
   remain wide or unavailable.
5. Liveness and readiness are not interchangeable. Logical incompatibility is
   a scientifically meaningful outcome and must not be coerced into a fit.

The mechanism-aware methods are diagnostic references with simulated laws or
corrected topology, not deployable straw baselines. Conversely, the guards are
specific audits, not universal anomaly detectors. These isolated synthetic
violations do not establish their live-system power, cover simultaneous
violations, or justify selecting a convenient diagnostic after looking at test
outcomes. M7 must freeze its audits, block-length selection rule, and exclusions
using calibration/validation data before inspecting independent test results.

## Completion checks

- The full 4,400-prefix matrix ran only in GitHub Actions.
- All five stress generators retained their paired controls and fixed marginal
  equalities.
- Proposed and matched B3 points agreed whenever both existed.
- Every fired diagnostic removed guarded estimates and decisions.
- Contradictory constraints were explicit and no inverted interval survived.
- Coverage, error, diagnostic power, and decisions were reported even when
  unfavorable.
- Privileged references and direct endpoint baselines were labelled by role.
- The superseded diagnostic run and its implementation correction were retained.
