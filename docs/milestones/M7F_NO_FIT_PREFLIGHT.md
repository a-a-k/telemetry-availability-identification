# M7F: separate no-fit main-path preflight

## Outcome

M7F is complete. The accepted GitHub Actions run exercised exactly four fresh
cells---two applications by two placements at `NCD/r0`---through the same
deployment, acquisition, native-telemetry, evidence-separation, and aggregate
qualification path that the full M7 campaign will use. All four campaign jobs
and the no-fit boundary audit succeeded. The aggregate is usable and every
quality counter is zero.

M7F fitted no model, computed no score, selected no method, and changed no
scientific configuration. Its sole result is that the frozen main path is
technically executable while test evidence remains physically sequestered.

## Immutable references

- frozen acquisition and analysis implementation:
  [`4db1797f4d306506f130a438e625c76e483f27f3`](https://github.com/a-a-k/telemetry-availability-identification/commit/4db1797f4d306506f130a438e625c76e483f27f3);
- preflight-scope wiring correction and 360-minute job timeouts:
  [`6afe4f61e77f0939c77dd64b113fd24b6a6f0e21`](https://github.com/a-a-k/telemetry-availability-identification/commit/6afe4f61e77f0939c77dd64b113fd24b6a6f0e21);
- accepted two-version CI:
  [run 33988035197](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33988035197),
  successful on Python 3.11 and 3.13;
- superseded preflight:
  [run 33985914972](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33985914972),
  retained as a failed provenance check;
- accepted preflight:
  [run 33988106712](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33988106712),
  successful;
- main configuration SHA-256:
  `42b5611f99051f52ba3c2250b2e82f50ece2ae2e275be7e13796a170b2586b6a`;
- inherited selected-design SHA-256:
  `b4a7f3c71d93c5f216e33f3f7e012703ee47916cc2e767e65120246019bf9b00`.

The accepted qualification manifest has SHA-256
`df8432272528a3598650201d151a8987f7b4565f7a1c4b4917e83335f92ce1f0`;
its cell table has SHA-256
`59a78ffbbc2d927fde298ea4b06e03ab165d5542572d35391a84d965544732db`.

| Artifact | Id | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| Superseded boundary `m7-preflight-boundary-33985914972` | 9975659187 | 829,912 | `1dbc20827d5c7b01e3771a962b1730af8df19f3a58b71569b662ad64d4129951` | 2026-10-05 |
| Accepted boundary `m7-preflight-boundary-33988106712` | 9976283309 | 838,503 | `43dc076505374acefc4e9473ed831717e93d0d0edce024cf767f3655a1652c83` | 2026-10-05 |
| Accepted raw DeathStarBench/co-located | 9976253141 | 4,995,084 | `f87dc3ed15705d62780806a3a33e1b75ec89f012cba7b8a983ea0d1d15e5326f` | 2026-09-06 |
| Accepted raw DeathStarBench/split | 9976253065 | 5,000,423 | `3e6914cb627df1caec6885fc2829de81971161dc3b5068f9005a1bc7469baba4` | 2026-09-06 |
| Accepted raw OTel Demo/co-located | 9976263754 | 17,473,648 | `f8f24e2940e0f665f90815badd6e9efa4bf923ca1aaafb6e634bbe9c30ca2df7` | 2026-09-06 |
| Accepted raw OTel Demo/split | 9976263809 | 16,886,623 | `2d8f8554117f2b67f3c7c9db39184f1583947649927fa37567bf1b5c80174b2f` | 2026-09-06 |

GitHub reports artifact digests with a `sha256:` prefix; the table omits only
that prefix. Raw preflight evidence is intentionally transient. The compact
boundary bundle retains normalized learner/evaluator evidence, audit records,
and source hashes for 30 days.

## What was exercised

Each job checked out the exact benchmark revision, rendered and digest-locked
its compose deployment, created two real target replicas behind the frozen
proxy, applied the frozen co-located or split logical-domain placement, and ran
the full baseline/calibration/test acquisition schedule. It then retained raw
native traces and independent request/health evidence. The aggregate job used
the preflight evidence-boundary contract to normalize learner evidence and
physically place test requests and health below `evaluator/`.

The preflight and main roles remain disjoint. The accepted cell manifests say
`pilot_only=true`, `preflight_only=true`, `main_effectiveness=false`,
`analysis_frozen=true`, and `campaign_scope=preflight`. All four learner request
streams directly carry the `m7-preflight-v1-` prefix. All 44 factor-by-period
seed entries in the four raw planned schedules equal the deterministic
derivations from base seed `770036`; zero equal the corresponding derivations
from main seed `770034`. The future main branch selects seed `770034` and
namespace `m7-main-v1` instead. Every accepted cell also records the frozen
configuration digest and the single source run and commit.

As a runtime safety margin requested before the full launch, job-level
`timeout-minutes` is 360 for `campaign`, `preflight_audit`, and `analyze`.
This changes neither scheduled duration nor requests, seeds, masks, thresholds,
estimand, or analysis. Accepted campaign jobs actually took 33 minutes 22
seconds to 34 minutes 30 seconds; the audit took 39 seconds.

## Accepted technical result

| Application | Placement | Baseline requests | Calibration requests | Calibration health ticks | Topology edges | Replica assignments a/b | Trace-link fraction | Sequestered test requests | Test health ticks | Quality failures |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| DeathStarBench Social Network | co-located | 240 | 3,600 | 900 | 15 | 1,117 / 1,270 | 1.000 | 3,600 | 900 | 0 |
| DeathStarBench Social Network | split | 240 | 3,600 | 900 | 15 | 1,243 / 1,154 | 1.000 | 3,600 | 900 | 0 |
| OpenTelemetry Demo | co-located | 240 | 3,600 | 900 | 13 | 2,220 / 2,113 | 1.000 | 3,600 | 900 | 0 |
| OpenTelemetry Demo | split | 240 | 3,600 | 900 | 13 | 967 / 974 | 1.000 | 3,600 | 900 | 0 |
| Total | both | 960 | 14,400 | 3,600 | 56 | 5,547 / 5,511 | 1.000 in every cell | 14,400 | 3,600 | 0 |

The aggregate reports four source and four qualified cells, no cell-processing
error, no missing or duplicate cell, one source workflow run, one source
commit, no declared-run mismatch, no unusable cell, and zero learner/test
request-id overlap. Cell audits additionally report no missing source file,
count mismatch, duplicate request or span, invalid trace record, unparsed linked
trace, unknown replica, missing topology or health tick, insufficient replica
support, denied learner field, or privileged file copied into learner evidence.
The full-analysis job was skipped by construction.

## Superseded attempt and narrow repair

The first four campaign jobs completed, but their boundary audit correctly
rejected all cells. The workflow passed `--execution-scope preflight` to the
CLI parser, while the CLI call omitted that parsed argument when invoking
`run_frozen_live_cell`. Python therefore used the function's `full` default.
Each source manifest had four wrong role labels and the main usability field;
the aggregate recorded `source_label_mismatches=4` and `source_unusable=1` per
cell. Transport, counts, trace parsing, topology, health, replica support,
test sequestering, and request-id separation had otherwise passed.

Because that attempt also followed the main seed/namespace branch, the entire
run is excluded and no row is reused. No semantic outcome, fit, score, method
ranking, or effect from it was used to make the repair. Inspection was limited
to job state, exception text, provenance labels, and boundary quality counters.

The repair forwards the already-required CLI argument and adds a regression
test asserting `preflight` reaches the runtime function. It simultaneously
raises all three workflow timeouts to 360 minutes. All 101 local unit/config
smokes and the two-version remote CI passed, and the frozen configuration hash
was unchanged. M7F was then regenerated from fresh deployments and accepted.

## Interpretation and limitations

M7F shows that both applications and placements can traverse the exact frozen
M7 acquisition and anti-leakage path under one deliberately difficult law, and
that the role boundary rejects a mislabeled run rather than silently accepting
it. The observed native traces support a nonempty topology and both target
replicas, while held-out requests and health remain evaluator-only.

It does not show that the trace-discovered abstraction is correct or sufficient,
that any target is identifiable, that proposed improves strengthened B2, that
co-located or split placement is better, or that the complete 160-cell matrix
will have no operational failure. The per-cell counts above are transport and
support diagnostics, not effectiveness evidence. M7F covers only `NCD/r0` and
must never be pooled with M7.

With these limits, M7F removes the predeclared technical gate. The next step is
the fresh 160-cell full workflow at the report commit. It must use
`main_effectiveness=true`, seed `770034`, namespace `m7-main-v1`, and the same
frozen configuration digest; only that run may support the live validation and
placement-transfer claims.

## Completion checks

- Heavy execution occurred only in GitHub Actions.
- The accepted run used one clean commit and the frozen configuration digest.
- All four campaign jobs and the no-fit boundary audit succeeded.
- Preflight and main seeds, namespaces, usability fields, and role labels are
  separate.
- All source, count, native-trace, topology, health, replica, and boundary
  quality gates passed.
- Test requests and test health are physically sequestered with zero request-id
  overlap.
- The superseded mislabeled run and its one-line repair remain auditable.
- No model was fitted and no effectiveness or transfer result was inspected.
