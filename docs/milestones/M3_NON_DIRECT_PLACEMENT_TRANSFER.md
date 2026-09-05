# M3 non-direct placement transfer

## Outcome

M3 is complete. The experiment predicts two placement outcomes that never occur
in calibration: moving one replica to an independently calibrated failure domain
and adding a same-type replica in the original domain. It evaluates B0--B4 on
matched campaigns, retains the exact B3 result as the statistical reference,
and gates proposed transfer predictions with analytic identifiability
certificates.

The result is deliberately narrower than a claim of universal model superiority.
Under complete joint health, the analytic B2 and exact likelihood are
statistically indistinguishable. Under sampled heterogeneous telemetry, exact
likelihood improves the harder cross-domain change estimate modestly. Under
trace-only telemetry, transfer is provably ambiguous and the proposed procedure
withholds it.

## Evidence and provenance

- Tested commit: `99be67e829f26cfa52c22cb7f59dc8d1116afd4e`.
- CI: [run 33961070790](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33961070790), successful on Python 3.11 and 3.13.
- Diagnostic workflow: [run 33961102120](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33961102120), successful.
- Frozen full workflow: [run 33961174113](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33961174113), successful in 2 minutes 44 seconds.
- Aggregate artifact: `m3-aggregate-33961174113`, 8,581,959 compressed bytes, retained by GitHub through 2026-10-05.
- Runtime environment: CPython 3.13.15 on Linux, NumPy 2.4.4,
  SciPy 1.17.1, and PyYAML 6.0.2.
- The aggregate manifest records a clean worktree, the tested commit, workflow
  identifiers, configuration digest, seeds, and dependency versions.

The protocol was committed before either non-smoke run in
`docs/M3_TRANSFER_PROTOCOL.md`.

## What was implemented

- OR-of-conjunction Boolean observables with independently enumerated latent
  states in the existing exact likelihood.
- A two-domain calibration model with four health indicators and two OR traces.
- Three fixed-marginal common-cause scenarios whose correct placement choice
  changes.
- Five observation modes: full, sampled mixed, joint-health-only, staggered
  health plus traces, and trace-only.
- Non-direct current, split-domain, and added-replica availability functionals.
- B0 endpoint persistence, B1 independent marginals, strengthened B2 available
  domain moments, B3 exact likelihood, identification-aware matched likelihood,
  and B4 empirical joint estimation.
- Analytic target-identification certificates and explicit ambiguity witnesses.
- Target-level error, change error, decision coverage, correct choice, exact
  regret, unsupported decisions, parameter error, convergence, boundary, and
  runtime tables.
- Deterministic 2,000-resample paired campaign bootstrap intervals for mean
  error differences.
- Independent 10,000-episode validation draws per scenario, campaign, and
  target; these are never exposed during fitting.

The strengthened B2 deserves emphasis. It uses joint health when available and
also uses the identity

~~~text
gamma = m1 * m2 / (m1 + m2 - OR)
~~~

when staggered health marginals and the matching OR trace are available. Thus it
is not made artificially unavailable merely because health records are not
synchronous.

## Executed matrix and integrity checks

The frozen run contains three scenarios, five observation modes, nested sizes
100, 500, and 2,000, and 200 independent campaigns: 9,000 calibration datasets.
The aggregate contains:

- 54,000 method fit rows;
- 162,000 parameter rows;
- 162,000 target prediction rows;
- 108,000 change prediction rows;
- 54,000 placement decision rows;
- 120,527 compressed observation-pattern rows;
- 1,800 independent validation rows;
- 45 structural classifications and six ambiguity witnesses.

All predeclared gates passed:

- zero proposed/B3 prediction mismatches where proposed emitted a value;
- zero failed ambiguity witnesses;
- zero unsupported proposed placement decisions;
- maximum witness discrepancy over complete supported observable distributions:
  `2.22e-16`;
- minimum witness-induced target change: `0.004245`.

The raw B3 optimizer made 1,800 unsupported trace-only decisions, exactly one for
each trace-only dataset. These values are kept as diagnostics rather than scored
as valid recovered predictions. Proposed coverage in that mode is zero by
design.

## Estimation and convergence

There were no optimizer failures. Among the 9,000 exact fits:

- 5,896 were regular converged fits;
- 1,304 converged at at least one probability boundary;
- all 1,800 trace-only fits were detected as non-unique.

Median B3 runtime per six-factor fit ranged from 0.0062 seconds for trace-only to
0.0104 seconds for staggered health plus traces. M3 therefore supplies a
correctness and small-model feasibility result, not a new scaling claim.

At size 2,000, proposed parameter MAE under full/joint health was about
0.0038--0.0046. Under sampled mixed telemetry it was 0.0053--0.0065, and under
staggered health plus traces it was 0.0062--0.0084. In the latter two modes it
was usually lower than B2 because likelihood uses the heterogeneous records
jointly. No individual parameter estimate is emitted in trace-only mode.

## Primary sampled-mixed contrast

The table reports change-MAE in probability units at size 2,000. The effect is
proposed minus strengthened B2; negative favors the proposed exact-likelihood
fit. Intervals resample the 200 matched campaigns.

| Scenario | Target | Proposed MAE | B2 MAE | Paired difference | 95% bootstrap interval |
|---|---|---:|---:|---:|---:|
| weak | split | 0.002767 | 0.003603 | -0.000836 | [-0.001172, -0.000487] |
| medium | split | 0.004565 | 0.006359 | -0.001794 | [-0.002464, -0.001141] |
| strong | split | 0.005185 | 0.006685 | -0.001500 | [-0.002236, -0.000783] |
| weak | add | 0.001113 | 0.001111 | +0.000001 | [-0.000003, +0.000006] |
| medium | add | 0.000428 | 0.000428 | +0.000001 | [-0.000002, +0.000003] |
| strong | add | 0.000103 | 0.000103 | +0.000000 | [-0.000000, +0.000000] |

The useful gain is specific: traces add finite-sample information for the
cross-domain split functional. They add essentially nothing for the same-domain
`add` change after its current endpoint and health statistics are known. Under
full and joint-health-only evidence, proposed and B2 agree to numerical
tolerance, as the anti-strawman design requires.

## Baseline behavior and placement decisions

B0 accurately measures the current endpoint but predicts zero change and cannot
choose between placements. In sampled mixed telemetry at size 2,000, proposed
current-endpoint MAE was 0.00267--0.00552 across scenarios, versus
0.00290--0.00624 for B0 and 0.00390--0.00705 for B4. These are modest differences;
the main reason to fit the model is transfer, not superior reconstruction of an
already observed endpoint.

B1 always prefers `add`. This is correct in the weak-common-cause scenario and
wrong in every medium and strong campaign at size 2,000. Its exact regret in
those scenarios is respectively 0.05004 and 0.08285. This is evidence about the
effect of omitted common causes, not a sufficient comparison by itself.

For medium common cause, proposed choice accuracy was 99.0--99.5% at size 100
depending on observation mode and 100% at sizes 500 and 2,000. For strong common
cause it was 100% throughout. The deliberately close weak case remains hard:

| Evidence | Proposed accuracy at 100 | at 500 | at 2,000 |
|---|---:|---:|---:|
| full or joint health | 60.0% | 71.0% | 84.5% |
| sampled mixed | 51.0% | 64.0% | 76.0% |
| staggered health plus traces | 46.0% | 60.0% | 72.0% |

In the weak sampled-mixed case at size 2,000, B2 reached 70.5% and proposed
76.0%; nevertheless B1 reached 100% because its fixed independence assumption
happens to select the true side of this scenario. This is a useful negative
result: better probability estimation does not guarantee the best finite-sample
binary decision near a 0.00356 choice margin. M4 must quantify decision
uncertainty rather than hiding this instability behind a point choice.

At size 100 with staggered health, B2 transfer coverage was only 57.5--63.0%
across scenarios because its predeclared per-moment minimum was not always met.
Exact likelihood converged and produced structurally supported outputs in all
campaigns, but M3 does not equate convergence with precision; interval width and
coverage are evaluated next.

## Independent validation check

The 10,000-episode test rates had mean absolute error from exact truth between
0.00068 and 0.00238 depending on scenario and target, with individual errors as
large as 0.01071. This confirms why exact synthetic truth is the primary scoring
quantity and why a live test proportion cannot be treated as error-free truth.

## Interpretation

M3 supports four bounded conclusions:

1. A model can add value over direct endpoint persistence specifically for an
   unobserved placement change; B0 and B4 cannot make that transfer by themselves.
2. Common-domain structure changes the correct replication decision even when
   all component health marginals are held fixed.
3. Exact same-model likelihood and the proposed procedure agree exactly where a
   prediction is supported. Relative to a strong analytic B2, its measurable
   gain is confined to heterogeneous sampled evidence and the cross-domain
   functional.
4. Structural gating prevents an optimizer-selected point on a proved ridge
   from becoming an unjustified placement recommendation.

The full result does not support claiming a universal accuracy advantage over
B2/B3. The identifiable full-data equality and B1's weak-scenario decision win
must remain visible in the paper.

## Limitations and next milestone

This is a six-factor synthetic model with known independent residual factors,
known placement, state-independent missingness, and a correct transfer assumption
for residual replica health. It does not cover unknown domains, state-dependent
exporter loss, temporal dependence, readiness delay, routing changes, or live
model mismatch. The Boolean certificate is specific to this two-domain family,
not a general theorem for arbitrary DNF predicates.

M4 now builds simultaneous finite-sample uncertainty sets. Its key checks are
coverage together with width, widening under telemetry loss, and whether the
weak-scenario choice should be withheld when the two placement intervals do not
separate.
