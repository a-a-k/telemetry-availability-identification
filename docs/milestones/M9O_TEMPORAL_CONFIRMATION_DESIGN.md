# M9O: independent temporal-confirmation design

## Outcome

M9O is complete as a preregistration and precision-planning milestone. Its first
three-job execution, [run 34113304974](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34113304974),
selected **30 repetitions per stratum, 120 new campaigns in total**, and produced
an audited prospective identity matrix. It collected no new observations.
The design is ready for acquisition/analysis implementation and a separate
four-cell no-fit preflight; independent effectiveness confirmation is still
outstanding.

The selected count follows the frozen grid and inflated-pilot-variance rule in
[M9O_TEMPORAL_CONFIRMATION_PROTOCOL.md](../M9O_TEMPORAL_CONFIRMATION_PROTOCOL.md).
Conditional mechanism precision required 23 repetitions per stratum and marginal
signed-error precision required 27. Thus the first sufficient value in
`[10, 15, 20, 30, 40]` was 30. The cap was not enlarged after observing the result.

## Why the design differs from a simple rerun

M9N's conditional age effect and its improved marginal score relative to frozen
M7 B0 are separate results. Its state-only marginal predictions were nearly
identical to the temporal predictions. A new experiment that again compared
only temporal forecasts to the older B0 would not isolate the value of age.

The prospective design therefore retains the midpoint model and freezes:

- a matched state-only control with the same full health inputs, baseline q,
  filtering, and censoring;
- a matched stable-endpoint Jeffreys estimate over exactly the same calibration
  request subset, without multiplying by q a second time;
- all-calibration endpoint and source-literal 500 ms descriptive controls;
- distinct conditional-mechanism, marginal-equivalence, and mean-calibration
  criteria, with a shared family error allocation.

Only a conditional Brier improvement can establish temporal information given
test health. A material marginal advantage over matched state only requires a
simultaneous upper bound below -0.002 Brier units. Practical equivalence requires
the whole corresponding interval inside [-0.002, +0.002]. Mean calibration
requires the complete signed-error interval inside [-0.03, +0.03]. These criteria
were frozen before planning and any new data. The matched stable-endpoint
comparison remains a descriptive control, not an unregistered inferential claim.

This is a deliberately narrow replication of stable checkout behavior at the
pinned application revision and N/ND laws. It cannot establish all-traffic
availability, general temporal transfer, an exact HAProxy assignment mechanism,
or a lower-cost automatic model than PMX.

## Execution and checks

- preregistration and tested commit:
  [`58b61e45102e823b666a67224dd8b204f12f7c80`](https://github.com/a-a-k/telemetry-availability-identification/commit/58b61e45102e823b666a67224dd8b204f12f7c80);
- first and accepted run: `34113304974`, created `2026-09-07T10:47:50Z`,
  completed by `2026-09-07T10:49:06Z`;
- CI: [run 34113304275](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34113304275), successful;
- local checks: all 222 unit tests passed in 11.205 seconds; seven shell blocks
  and workflow YAML parsed. Tests used small synthetic variance inputs only;
  the complete retained-table planning calculation ran in Actions.

| Job | UTC start | UTC finish | Duration |
|---|---|---|---:|
| Locked M9N pilot contract | 10:47:54 | 10:48:19 | 25 s |
| Frozen precision calculation | 10:48:21 | 10:48:45 | 24 s |
| Published-design arithmetic and identity audit | 10:48:47 | 10:49:05 | 18 s |

Each job used `timeout-minutes: 360`. The contract verified both source artifact
identities and four exact input files, including the accepted M9N branch.
Planning read existing candidate and campaign-score tables; it did not reread
raw test requests, refit models, recalculate M9N scores, or collect data. The last
job checked the published file hashes, precision arithmetic, complete identity
matrix, namespace/seed declarations, and explicit zero-observation boundary.
There was no failed remote attempt or post-result correction.

## Precision result

The three 98.3333% individual intervals use a Bonferroni family alpha of 0.05.
The working normal critical value is 2.3939797998. The prespecified variance
envelope yields a multiplier of 5.4408056631 over each pilot sample variance,
which exceeds the alternative fourfold variance floor.

| Quantity | Target half-width | Required repetitions per stratum | Working half-width at 30 |
|---|---:|---:|---:|
| Conditional temporal minus state-only Brier | 0.003 | 23 | 0.002574284 |
| Marginal temporal minus state-only Brier | 0.002 | 1 | 0.000001375 |
| Primary marginal signed error | 0.020 | 27 | 0.018909626 |

At 20 repetitions, the conditional half-width is 0.003153 and signed-error
half-width 0.023159, so 20 fails both targets. Thirty satisfies all three working
targets. The tiny marginal-difference planning variance reflects the pilot's
near-identical predictions; it is not evidence that future variability is zero.
The minimum of ten repetitions still applies, and the shared design uses 30.

These are working approximations, not promised coverage, precision, power, or
effectiveness. The normal/chi-square assumptions are planning approximations
for bounded campaign scores and were disclosed before the calculation. A
future wide interval, missing campaign, or failed adequacy gate remains an
incomplete or inconclusive result, not a reason to extend the sample until it
becomes favorable.

## Frozen prospective matrix and cost

The matrix contains one fresh OpenTelemetry checkout campaign for each
placement in `{colocated, split}`, law in `{N, ND}`, and repetition in `0..29`.
Each has a 60-second baseline, 900-second calibration, and separate 900-second
test realization. The existing mixed-operation driver remains at four requests
per second. The benchmark revision remains
`8c47d47c9ac27710d2b2a153bcd53e483bffe66d`.

The request namespace is `m9p-temporal-confirm-v1`; main, excluded-preflight,
and analysis seed roots are respectively 2026090701, 2026090702, and 2026090703.
These declarations do not by themselves prove evidence independence. The
preflight and main acquisition must verify fresh executions, request IDs,
factor-specific schedules, deployment/image provenance, and absence of reused
M7 or pilot files.

Nominal main runner time is **62 hours summed across campaigns**:
`120 * (60 + 900 + 900) / 3600`. This excludes benchmark startup, preflight,
uploads, and retries, and is not a wall-clock completion estimate. Health
observation and selection costs must be recorded for all matched controls;
temporal episode construction/fitting is an additional cost. No measured
end-to-end comparison with PMX is available.

## Accepted artifacts

All artifacts were unexpired when checked and have retention through
2026-12-06 10:47:51 UTC. Compressed digests below are GitHub metadata;
downloaded individual files and the audit-to-design link were hash-verified.

| Artifact | ID | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| `m9o-pilot-contract-34113304974` | 10015225171 | 51,370 | `2485e340acc63121aab6e0250fa99109bf0b63edee1175899072f6b7affbb18c` |
| `m9o-confirmation-design-34113304974` | 10015238498 | 2,864 | `b3e2a2bb557d421fd7c3d7f6b7b1f305205db2e0be9dc85df60d200e9789f01a` |
| `m9o-confirmation-audit-34113304974` | 10015249333 | 1,021 | `332b84c15f3893b74f72c647889d4cdaad2c28a9c9d6779c278df28de8461631` |

| File | Bytes | SHA-256 |
|---|---:|---|
| `design.json` | 2,525 | `7d18996f33c01d5f09d0244b5d2a9bd3b45c44e43d2b53b89e85be2c87faecfc` |
| `precision-grid.csv` | 1,163 | `20f01f93b5dd8a0ed02a72e9f64039750db9f5d8001ff695039847e6dcb8bcf7` |
| `prospective-campaigns.csv` | 8,250 | `ceb54a1600049e464c2002a71a905c00bb013793fa4494a7a84bdf6b430d685e` |
| `audit.json` | 452 | `6be4f5bba2131613252e2b5d05a1e4fd3b4006195e98fc0ec75e64f9e25a7ca0` |

## Completion boundary and next step

The protocol, executable planning rule, tests, successful full remote planning
run, prospective matrix, and audit are complete. This closes M9O's design task,
not the proposed confirmation. Both output manifests explicitly contain
`new_independent_observations: 0` and `full_live_collection_authorized: false`.
The latter is an experimental gate: the acquisition implementation and no-fit
preflight have not yet been completed.

The next step is `m9p_separate_no_fit_confirmation_preflight`: implement and
audit prospective acquisition/analysis against the frozen design; verify the
four-cell no-fit path before the 120-cell main run. An independently
parameterized PMX comparison remains separately outstanding. Neither M9N nor
this planning artifact supplies it or changes PMX's scientific priority.
