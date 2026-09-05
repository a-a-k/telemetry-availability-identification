# M7C: stochastic schedule and live-resource freeze pilot

## Outcome

M7C is complete, including the protocol-permitted resource recovery recorded as
M7C-R. All 64 remote pilot cells passed their technical acquisition gates. The
pilot selected 900 seconds for each calibration and test period and a one-second
exclusion guard on each side of a health-detected transition.

The original repetition rule then reached its intended stopping condition. None
of 10, 15, 20, 30, or 40 campaign pairs could guarantee a 0.015 half-width for
the noisiest one of the 16 individual application--placement--law cells. The
aggregate therefore failed instead of silently choosing the largest candidate.

Before any M7 model was fit or effectiveness result existed, M7C-R narrowed the
precision claim to the equally weighted macro-average over all 16 predeclared
strata. It retained the 0.015 threshold and the original candidate grid. The
audited replay selected 10 independent campaigns per stratum, or 160 M7 cells.
Individual-stratum estimates will remain visible with intervals but will be
descriptive rather than advertised as meeting the 0.015 precision target.

All 169,152 M7C request records--168,960 scheduled period attempts plus 192
semantic sentinels--are engineering and resource evidence only. They are
permanently excluded from M7 fitting, method comparison, and effectiveness
claims.

## Frozen implementation and evidence

- initial M7C implementation commit:
  `b8bd5fd845909e758036e8b49f3f4c13ba985789`;
- accepted M7C cell implementation and full-pilot commit:
  `5ee628d448a63b313a6f950002ae50e105dc8270`;
- final exact-code two-application preflight:
  [run 33976882426](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33976882426),
  successful;
- complete 64-cell pilot and expected stopping condition:
  [run 33977809019](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33977809019),
  all cell jobs successful and aggregate failed only on
  `design_selection_failures=1`;
- M7C-R implementation and tested commit:
  `9693c7ad594596281f35022513baa9b8d4d4c94b`;
- CI for M7C-R:
  [run 33982192275](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33982192275),
  successful on Python 3.11 and 3.13;
- immutable-input M7C-R replay:
  [run 33982201605](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33982201605),
  successful.

The full pilot produced 64 cell artifacts and one aggregate, 269,896,849
compressed bytes in total. The full pilot and accepted recovery replay ran on
CPython 3.13.15 with NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2, and both
manifests record clean worktrees at their tested commits.

| Artifact | Id | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m7c-aggregate-33977809019` | 9973657467 | 21,255 | `8a212f39117fc5fbe6a16366b69054e999e5b5ce5e5e089463cbfe9b5048c10c` | 2026-09-19 |
| `m7c-resource-recovery-33982201605` | 9974079015 | 28,000 | `b734f9586f8de7c18cf18d6d7181b434374ea46a7bd9358a5efb873786f404f4` | 2026-10-05 |

The original aggregate manifest and recommendation have SHA-256 digests
`25f42bc16038fd83d6d06dad5d3ce7bc844986d773fa7c2f5a54cf0b2cd7e76b`
and
`880a152c7aac6fc17f046ead4c6dec5f41e2093d5232ff8de728b3b58b0d2c25`.
M7C-R reproduced the latter digest exactly. Its new recommendation digest is
`1405f431a278a40ff6325a1a6f49940f8e087419666a80ad05b3ebf82cd97cb1`,
and the final selected-design digest is
`b4a7f3c71d93c5f216e33f3f7e012703ee47916cc2e767e65120246019bf9b00`.

## What was implemented

The matrix crosses two pinned applications, co-located and split logical-domain
placements, four failure laws, and four pilot repetitions. Each cell starts a
fresh replicated application and executes a 60-second clean baseline followed
by independent 300-second calibration and test periods at four external
requests per second. Calibration and test use distinct deterministic workload
and renewal-process seeds.

The law labels are cumulative mechanism sets: N contains independent replica
events; NC adds communication loss; ND adds a logical-domain event; and NCD
contains all three. Each active primitive follows its own bounded alternating
renewal process. Intent, application, independently observed transition,
release, period cleanup, and final clean state are retained. Fault-period
success is never an acceptance gate.

The pilot separately estimates request/health dependence block lengths, counts
realized events, measures controller-to-health observation lag, and computes a
calibration-to-test endpoint-rate difference for resource planning. Main-period
duration is selected from 900, 1,200, and 1,800 seconds using pre-generated main
schedules and the pilot block estimate. The transition guard is selected from
1, 2, 3, 5, and 8 seconds. Neither rule reads a method fit or a placement-effect
contrast.

The original repetition rule uses the one-sided 90% upper standard deviation of
each four-pair stratum and asks whether a two-sided 95% half-width is at most
0.015. M7C-R retains the same proxy observations but applies the documented
Welch--Satterthwaite upper-variance calculation to an equal-weight macro-average
over the 16 strata. Request volume cannot reweight applications or laws.

## Complete pilot result

The aggregate contains 64 cells, 192 period summaries, 480 factor-period rows,
and 169,152 request--trace join rows. Across the cell artifacts it retained
168,960 scheduled period attempts, including 19,789 semantic non-successes,
plus 192 semantic sentinels; 2,610 scheduled events; 2,610 independently
confirmed events; and 2,610 releases. All 169,152 trace-census rows were present
in native telemetry, the linked-success fraction was 1.0 in every cell, and all
final states were clean.

Every technical aggregate quality counter is zero. The sole nonzero counter is
the intended `design_selection_failures=1`. Thus the red workflow conclusion is
scientific control flow, not a failed deployment or missing-data run.

### Duration and transition guard

The 90th-percentile pilot dependence block was 23 seconds. At 900 seconds this
projects 39.13 effective blocks, above the fixed requirement of 30. Across
4,800 pre-generated factor periods, 98.792% met the candidate-specific event
minimum; the worst-stratum tenth percentile was exactly the required eight
events. Longer candidates also passed, so the smallest candidate, 900 seconds,
was selected.

There were 4,969 eligible observed transitions. The 95th-percentile
controller-to-health lag was 0.937714427 seconds and the maximum was
1.000013181 seconds. The smallest candidate, one second on each side, was
selected. Main stable-interval analyses will detect transitions from ordinary
health evidence, not from privileged controller timestamps.

### Original stopping condition

The noisiest stratum was OTel Demo, split placement, NC law. Its four-pair
sample SD was 0.0874044 and its one-sided upper planning SD was 0.198038.

| Candidate pairs per stratum | Worst projected 95% half-width | Passed 0.015 |
|---:|---:|---|
| 10 | 0.141668 | No |
| 15 | 0.109670 | No |
| 20 | 0.092685 | No |
| 30 | 0.073949 | No |
| 40 | 0.063336 | No |

Selecting hundreds of campaigns merely to make every individual cell precise
would consume the live-study budget without matching the paper's primary
cross-stratum method contrast. The protocol therefore took its explicit
stop-and-revise branch.

### M7C-R resource result

For the equally weighted 16-stratum planning quantity, the estimated SD of one
balanced macro repetition is 0.0105653. The Welch--Satterthwaite effective
degrees of freedom are 17.7923, and the one-sided 90% upper macro SD is
0.0136225.

| Candidate campaigns per stratum | Total independent cells | Projected 95% macro half-width | Passed 0.015 |
|---:|---:|---:|---|
| 10 | 160 | 0.008515 | Yes |
| 15 | 240 | 0.006931 | Yes |
| 20 | 320 | 0.005994 | Yes |
| 30 | 480 | 0.004887 | Yes |
| 40 | 640 | 0.004230 | Yes |

The smallest admitted candidate, 10, is frozen. The resulting main acquisition
matrix is two applications by two placements by four laws by ten independent
campaigns. The later analysis separately declares co-located learner evidence
as the source and the split deployment as the placement-transfer target.

## Retained engineering attempts

The first two-application preflight,
[run 33974403759](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33974403759),
failed on a redundant DeathStarBench transition and OTel health-sampling
cadence. The controller/audit repair was rerun successfully as
[run 33975579740](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33975579740).
A resolution-aware audit preflight then succeeded as
[run 33975894357](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33975894357),
followed by the final exact-code preflight at the full-run commit. These attempts
changed engineering validation only; the matrix, renewal distributions,
candidate grids, precision threshold, and endpoint resource proxy were not
selected from a method result.

## Interpretation and limitations

M7C establishes that the full stochastic acquisition path can sustain the
matrix, that the chosen period has the predeclared event and dependence support,
and that a one-second health-derived guard matches observed transition latency.
M7C-R establishes a feasible budget for one balanced macro contrast.

It does not establish that a Boolean availability model is adequate, that its
parameters or target are identified, or that the proposed procedure beats B2.
The four-pair variance estimates are uncertain despite the upper-variance rule,
and the endpoint calibration-to-test difference is only a resource proxy for
the future paired method contrast. The macro result can coexist with large and
scientifically important cell heterogeneity; all such estimates must be shown.

The domains are controlled logical Docker domains on one hosted runner, native
traces are forced sampled, the workload is fixed at four requests per second,
and 900 seconds cannot demonstrate long-run stationarity. These facts bound the
claim regardless of the eventual M7 result.

## Completion checks

- All 64 heavy pilot cells ran only in GitHub Actions and passed technically.
- The exact full-pilot commit passed the two-application preflight.
- All planned requests, traces, events, confirmations, releases, and cleanup
  evidence were retained.
- The original no-candidate stopping condition remains visible and hash-pinned.
- M7C-R changed the estimand scale, not the threshold, candidate grid, or data.
- The recovery replay verified the exact source run, commit, recommendation
  digest, and zero original technical failures.
- Duration, transition guard, repetition count, seed, schedules, laws, and
  placement map now have one signed selected-design digest.
- No M7 estimator or effectiveness observation existed before this freeze.
