# M7: frozen live validation and placement transfer

## Outcome

M7 is complete as an executed study, but its predeclared primary estimand is
incomplete and does not support a superiority claim. All 160 fresh live
campaigns and the frozen analysis completed successfully. The primary
proposed-minus-B2 Brier contrast was available for 117 campaigns and estimated
`+0.0002327` (negative would favor proposed), with a 95% interval from
`-0.0016586` to `+0.0021240` and `p=0.6853`. The protocol required all 160
campaigns for confirmatory interpretation, so this conditional estimate is
descriptive rather than a passed null or superiority test.

The missing predictions are a central empirical discrepancy. In the
primary `sampled_mixed` mode, all 80 campaigns without communication faults
(`N` and `ND`) had supported topology for all operations. Of the 80 campaigns
whose laws included communication faults (`NC` and `NCD`), 43 had at least one
operation whose successful learner traces neither supported nor excluded the
declared target group at the frozen thresholds. The frozen rule abstained in
these cases; they were not imputed or repaired after seeing test outcomes. The
cause of the mixed trace support and the adequacy of that rule require
post-result diagnosis.

Where proposed emitted, it matched the same-model B3 optimizer exactly, as it
must. The published calculation did not establish an advantage over the
strengthened B2 comparator. Together with the prediction--observation
discrepancy, this motivates a separately labelled diagnosis; it is not yet a
verdict that the overall approach succeeds or fails.

## Immutable execution and artifacts

- frozen acquisition and analysis implementation:
  [`4db1797f4d306506f130a438e625c76e483f27f3`](https://github.com/a-a-k/telemetry-availability-identification/commit/4db1797f4d306506f130a438e625c76e483f27f3);
- preflight-scope correction and 360-minute job timeouts:
  [`6afe4f61e77f0939c77dd64b113fd24b6a6f0e21`](https://github.com/a-a-k/telemetry-availability-identification/commit/6afe4f61e77f0939c77dd64b113fd24b6a6f0e21);
- tested report-and-launch commit:
  [`b1925736f314da610debd23a586d7b7d00cae7ca`](https://github.com/a-a-k/telemetry-availability-identification/commit/b1925736f314da610debd23a586d7b7d00cae7ca);
- accepted two-version CI immediately before launch:
  [run 33990607570](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33990607570);
- full campaign and frozen analysis:
  [run 33990678586](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33990678586),
  successful;
- main configuration SHA-256:
  `42b5611f99051f52ba3c2250b2e82f50ece2ae2e275be7e13796a170b2586b6a`;
- selected-design SHA-256 inherited from M7C-R:
  `b4a7f3c71d93c5f216e33f3f7e012703ee47916cc2e767e65120246019bf9b00`.

The analysis artifact `m7-frozen-analysis-33990678586` has id `9980257950`,
compressed size 730,747 bytes, GitHub-reported SHA-256
`397fdc72d9a41fc30d265726e72690c75e4617949208048d629d19d7ea14b5ad`,
and retention through 2026-12-04. Its unpacked manifest has SHA-256
`94a67139bef116d7d356261f28b1b842365b8a42a6d71d03c13d5666fa64f5fe`.

| Analysis file | Rows | Bytes | SHA-256 |
|---|---:|---:|---|
| `cell-diagnostics.csv` | 640 | 122,872 | `2f89018fddf8a98f50a70959dc467e72630fd2af62f341ee20d542c13f094a3f` |
| `predictions.csv` | 17,280 | 3,877,747 | `b19ffcba80c029d16e972fda58bce459c8114da8734511fa7f29948e9cb1fd60` |
| `scores.csv` | 36,459 | 8,903,269 | `aec3415b3326e8c387ebd8f35b6ac08b939893211f6dcf58ea49f6aa0f3adec5` |
| `summary.csv` | 117 | 14,584 | `c1582ea2dd0143a29c2daa68e4ab258c68599bd1d4a019e729c4050e04a0ba75` |
| `contrasts.csv` | 120 | 20,325 | `2a6b1e77fa13f67bbfefa0fb495c1241840c27bbd4dd49e10a1380f018b7550a` |

Exactly 165 artifacts were retained: 160 compact qualified cell bundles
(32,991,812 compressed bytes total), four predeclared `NCD/r0` raw audit
samples (44,576,337 bytes total), and the analysis artifact. Qualified bundles
are retained for 30 days, raw samples for seven days, and analysis for 90 days.
There was no outcome-dependent raw retention.

| Raw audit sample | Artifact id | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| DeathStarBench/co-located/NCD/r0 | 9977468544 | 4,784,292 | `3456d8f537e13fdcb6339a328ddd6e0f600b757b55b416fd6708e7061c11807b` |
| DeathStarBench/split/NCD/r0 | 9978379274 | 4,860,206 | `c88f8e8f45eae42073a6311f85b75868faa48365d7220176c5006bd24009be9d` |
| OTel Demo/co-located/NCD/r0 | 9979235668 | 17,548,469 | `3fcacc42252b9029b672ceb5129fe01fb54895dff437152e8436cec5235374f9` |
| OTel Demo/split/NCD/r0 | 9980093048 | 17,383,370 | `e54b4f49bfd48b99e29b6da483af73cb2e2727c35065207c37fb7938080a3d3e` |

The run used CPython 3.13.15, NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2
from a clean worktree. All source boundaries and the analysis name the single
run and commit above. The four raw samples carry `pilot_only=false`,
`preflight_only=false`, `main_effectiveness=true`, `campaign_scope=full`, and
the `m7-main-v1-` request prefix. Their planned schedule seeds were separately
checked before this report was committed: all 44 factor-by-period entries equal
the deterministic derivations from main seed `770034`, and zero equal the
corresponding derivations from accepted-preflight seed `770036`.

## Execution and technical acceptance

The matrix is exactly two applications by two placements by four failure laws
by ten independent campaigns. GitHub ran at most 20 jobs concurrently. All 160
campaign jobs succeeded; none failed, timed out, was cancelled, or was rerun.
Campaign jobs lasted 2,002--2,089 seconds (median 2,047 seconds). The final cell
completed 4 hours 33 minutes after the first started, and the analysis then
completed in 675 seconds. The preflight audit job was skipped by construction.

The source data contain 38,400 clean-baseline requests, 576,000 calibration
requests, and 576,000 independently generated test requests. There are 144,027
ordinary health ticks; the 27 ticks above the nominal 144,000 reflect inclusive
boundary sampling and were retained rather than normalized away. Eight target
calibration requests were farther than 1.25 seconds from a health tick and did
not enter a likelihood bin; no test request was unaligned. There were zero
`P_i > H_i` health contradictions.

The frozen stable view excluded 140,712 test requests within one second of an
ordinary observed health transition and scored the remaining 435,288 requests
(75.6%). The all-sequence view retained all 576,000; the 46-second sensitivity
changed only block compatibility intervals, not point predictions or Brier
scores.

The analysis observed all 160 expected cells and no unexpected cell. Every
qualified boundary was usable. Source-run, source-commit, declared-run, and
cell-count mismatches were zero. Every emitted value was finite, and there were
zero proposed/B3 prediction mismatches. These are technical acceptance facts;
none depends on a favorable method result.

## Primary result

The primary estimand is the equal-operation, equal-stratum campaign-level
`proposed - B2` request Brier contrast for current-placement prediction under
`sampled_mixed` telemetry on the stable test view. Negative favors proposed.

| Campaigns | Strata | Estimate | Standard error | df | 95% interval | Two-sided p | Complete |
|---:|---:|---:|---:|---:|---|---:|---|
| 117 / 160 | 16 | +0.0002327 | 0.0005074 | 2.363 | [-0.0016586, +0.0021240] | 0.6853 | No |

The interval spans small advantages in either direction, while the point
estimate is slightly unfavorable to proposed. More importantly, the frozen
rule says the result is confirmatory only with 160/160 paired campaign scores.
It is therefore invalid to call this either evidence of superiority or a
conclusive equivalence/null result. The low Satterthwaite degrees of freedom
reflect the uneven within-stratum counts created by non-random abstention.

The all-sequence version had the same 117 campaigns and estimated `+0.0007907`
with 95% interval `[-0.0013555, +0.0029369]` and `p=0.2933`. Thus transition
exclusion reduced the unfavorable point difference but did not reverse it or
restore completeness.

On the 117 campaigns summarized for both methods, strengthened B2 had mean
Brier `0.0922783`, mean signed prediction-minus-test-rate error `+0.04244`, and
23-second block compatibility `0.2821`. Proposed/B3 had mean Brier `0.0924300`,
signed error `+0.04955`, and compatibility `0.2764`. These descriptive summaries
indicate mild relative and material absolute overprediction; they are not a
replacement for the incomplete primary contrast.

## Why the primary result is incomplete

Topology is inferred separately inside every campaign and mask. At least 20
retained parsed traces and target presence in at least 80% are required for a
target-requiring operation; at most 5% is required for a non-target operation.
Every primary abstention had the explicit status
`topology_ambiguous_target_fraction`: no missing-support, replica-count, parser,
or optimizer condition caused primary incompleteness.

The table reports campaigns with all three operation predictions available.

| Application | Placement | N | ND | NC | NCD | Total |
|---|---|---:|---:|---:|---:|---:|
| DeathStarBench Social Network | co-located | 10/10 | 10/10 | 8/10 | 7/10 | 35/40 |
| DeathStarBench Social Network | split | 10/10 | 10/10 | 3/10 | 7/10 | 30/40 |
| OpenTelemetry Demo | co-located | 10/10 | 10/10 | 5/10 | 3/10 | 28/40 |
| OpenTelemetry Demo | split | 10/10 | 10/10 | 2/10 | 2/10 | 24/40 |
| Total | both | 40/40 | 40/40 | 18/40 | 19/40 | 117/160 |

All 43 incomplete campaigns lie in laws containing the communication factor.
They contain 109 ambiguous operation rows: 30 in DeathStarBench and 79 in OTel
Demo. The association is exact in this run but is not, by itself, proof of the
mechanism. It is consistent with communication faults changing which successful
traces reach or expose the replicated target, with conditional application
paths, or with incomplete downstream trace visibility. The learner evidence
cannot distinguish those explanations, and the controller schedule is
deliberately unavailable to the model.

The result is not a simple trace-sampling artifact. Full telemetry retained
531,599 learner traces and still classified 110 of 480 operation-by-campaign
topologies as unsupported. The three 70%-trace modes retained approximately
372,000 traces each and classified 109 as unsupported.

| Observation mode | Retained traces | Confirmed operation topologies | Unsupported | Cell-modes with any unsupported operation |
|---|---:|---:|---:|---:|
| full | 531,599 | 370 | 110 | 44 |
| no_joint_health | 372,039 | 371 | 109 | 44 |
| sampled_mixed | 372,069 | 371 | 109 | 43 |
| trace_only | 372,444 | 371 | 109 | 44 |

Across all four modes the manifest records 175 cell-modes with an unsupported
operation and 156 fits with no trace-supported target operation at all. This is
a failure of the proposed model's admission conditions, not a reason to lower
the frozen 80% threshold after seeing outcomes.

## Identification-aware abstention

For current-placement prediction, every topology-supported target was
numerically identifiable, including in `trace_only`; all 437 current-operation
abstentions across modes were topology abstentions. Transfer requires more.
Without any health marginals, the trace-only co-located learner often identifies
the current endpoint but not the counterfactual split endpoint.

| Scope | Mode | Complete proposed campaigns | Topology-abstained operation rows | Identification-guard operation rows |
|---|---|---:|---:|---:|
| current (160 possible) | full | 116 | 110 | 0 |
| current | no_joint_health | 116 | 109 | 0 |
| current | sampled_mixed | 117 | 109 | 0 |
| current | trace_only | 116 | 109 | 0 |
| transfer (80 possible) | full | 62 | 42 | 0 |
| transfer | no_joint_health | 62 | 41 | 0 |
| transfer | sampled_mixed | 63 | 41 | 0 |
| transfer | trace_only | 33 | 41 | 76 |

B3 retains a raw optimum on an unidentified ridge, whereas proposed suppressed
those 76 trace-only transfer operation predictions. B4 abstained on all 800
target-requiring transfer rows as predeclared because it has no observed joint
path completion in the target placement. These abstentions are successful
diagnostic behavior, not missing values to fill.

The 640 cell-mode fits were labeled 475 regular, 156 with no supported target
operation, seven finite nonconvergences, and two boundary fits. Every
nonconvergent case still had eight finite starts, seven converged starts, and a
current-target multistart range below `4.9e-8`; none explains primary
abstention. The status remains visible rather than being relabeled regular.

## Comparator and transfer results

Proposed and B3 have identical predictions and scores wherever proposed emits:
their paired difference is exactly zero and the hard mismatch count is zero.
This is a correctness result, not evidence that proposed is more accurate than
a standard matched likelihood optimizer. Proposed's additional behavior is its
identification guard.

For current-placement stable scoring, every available proposed-minus-B2 point
estimate was positive. No Holm-adjusted secondary comparison was significant;
the primary unadjusted p-value was `0.6853`. Every comparison was incomplete.

| Mode | Paired campaigns | Proposed - B2 Brier | 95% interval | Adjusted p |
|---|---:|---:|---|---:|
| full | 116 | +0.0007697 | [-0.0007306, +0.0022699] | 1.000 |
| no_joint_health | 116 | +0.0013454 | [-0.0044510, +0.0071417] | 1.000 |
| sampled_mixed (primary) | 117 | +0.0002327 | [-0.0016586, +0.0021240] | primary, unadjusted |
| trace_only | 29 across four strata | +0.0025974 | [-0.0242604, +0.0294552] | 1.000 |

The trace-only B2 comparison is especially limited: B2 requires path marginals
and could use its endpoint fallback in only 29 campaigns from four strata.

Transfer uses co-located calibration only and scores against the separately
executed split evaluator. B1 and B2 coincide here because both use the admitted
path marginals under the frozen homogeneous-new-domain assumption.

| Mode | Paired campaigns | Proposed - B2 Brier | 95% interval | Holm-adjusted p |
|---|---:|---:|---|---:|
| full | 62 / 80 | +0.0012875 | [-0.0000551, +0.0026300] | 1.000 |
| no_joint_health | 62 / 80 | +0.0005947 | [+0.0004394, +0.0007501] | 0.00997 |
| sampled_mixed | 63 / 80 | -0.0005805 | [-0.0085594, +0.0073984] | 1.000 |
| trace_only | 0 / 80 comparable to B2 | not estimable | not estimable | not estimable |

The no-joint result is a secondary, subset-conditional finding in the direction
of B2, not proposed. Across the 92 secondary contrasts receiving Holm
adjustment, 13 were significant; all were transfer contrasts and all had a
positive sign, meaning proposed was worse. They comprise full/no-joint
comparisons with B0, no-joint comparisons with B1/B2, and one trace-only
all-sequence comparison with B0. No adjusted current-placement contrast favored
either direction. All 120 contrast rows remain marked `complete=false`, so the
secondary findings cannot rescue or replace the incomplete primary estimand.

## Interpretation for the article

The live result supplies three candidate conditions to investigate when asking
“when is a trace-discovered topological model enough?” A useful point prediction
in this implementation would require all of the following:

1. retained successful traces classify each operation's dependency on the
   replicated target outside the frozen ambiguity band;
2. the admitted health/path evidence identifies the requested current or
   transfer functional;
3. the fitted abstraction is compatible enough with an independent test period
   for the prediction to be useful.

Condition 1 held uniformly for `N/ND` but failed often for `NC/NCD`. Condition 2
held for supported current targets but failed for 76 trace-only transfer
operation cases. Condition 3 is questionable even on the accepted primary
subset: both proposed and B2 overpredicted the stable test rate by roughly
4--5 percentage points on average, and their block-compatibility fractions were
only about 28%.

M7 does not establish predictive superiority over strengthened B2. It does show
that the implemented sufficiency check and abstention boundary are empirically
consequential, but whether they are adequate and how they should contribute to
the article remain open until the discrepancies are diagnosed. The earlier
anti-straw-man concern was addressed: B2 used the same evidence, joint health
when available, an endpoint fallback when necessary, and new-domain path
marginals for transfer. It was competitive throughout and significantly better
in one predeclared secondary transfer mode on the incomplete common subset.

The current result should be written as absence of an established gain together
with unresolved abstention and prediction--observation discrepancies, not
hidden by reporting only the 117 emitted campaigns. Proposed/B3 equality is an
implementation check. The present calculations alone do not establish whether
refusing unidentified points is sufficient scientific value, nor whether the
whole approach is successful or unsuccessful.

## Limitations and audit disclosures

- The failed first M7F attempt accidentally followed the main seed and request
  namespace for four `NCD/r0` schedules. No row from that run was pooled, no
  semantic outcome or score was inspected, and the full run used fresh
  deployments. The four deterministic schedule patterns were nevertheless
  exercised previously and this prevents a literal claim that no main schedule
  had ever run; the provenance failure and repair remain documented in M7F.
- Only four predeclared full cells retain complete raw native telemetry. The
  other 156 retain qualified evidence plus source and privileged-file hashes,
  limiting future independent parser replay.
- Logical domain placement is controlled metadata, not a discovered physical
  failure domain. Split-domain independence and homogeneous domain availability
  remain modeling assumptions.
- The analysis covers two exact benchmark revisions, one replicated service per
  application, six operations, four renewal-law labels, and ephemeral public
  runners. It does not establish general benchmark or topology behavior.
- Successful traces are selected by application and telemetry behavior.
  Communication-law topology ambiguity may reflect genuine conditional paths,
  semantic fallback, or missing downstream spans; the present learner boundary
  cannot identify which.
- The likelihood is a stationary composite likelihood. Test rates are noisy
  operational outcomes, not latent-parameter truth, and no privileged
  controller schedule is used to make the model look better.
- With only ten campaigns per stratum, topology abstention leaves some primary
  strata with two or three pairs and an effective `df=2.36`. A new threshold or
  topology rule would require a separately frozen study, not a reanalysis of
  M7.

## Completion checks

- All heavy acquisition and fitting ran only in GitHub Actions.
- All 160 independent campaign jobs and the frozen analysis succeeded under
  360-minute job timeouts.
- The matrix, source run, source commit, role labels, hashes, and evidence
  boundaries passed with zero technical quality failures.
- Main and preflight namespaces and seeds remained distinct; preflight rows were
  not read by the main analysis.
- Test evidence remained sequestered until the already frozen scoring stage.
- Primary incompleteness and every abstention were retained without imputation.
- Strengthened B2 and matched B3 were not weakened or replaced after outcomes.
- The report states the unfavorable sign, interval, p-value, adjusted secondary
  results, model-compatibility signal, and limitations.
- The frozen M7 calculation is closed and supplies no established superiority;
  its causal and article-level interpretation remains open. Any follow-up is
  separately labelled, versioned, and, where confirmatory, frozen.
