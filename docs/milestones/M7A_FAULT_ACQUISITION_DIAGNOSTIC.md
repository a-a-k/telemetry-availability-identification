# M7A: fault-control and request--trace linkage diagnostic

## Outcome

M7A is complete as the final single-replica acquisition diagnostic. Across two
running applications and the four predeclared N, NC, ND, and NCD law labels,
the accepted GitHub Actions run retained all 1,920 scheduled external attempts,
all 48 interventions were independently verified and restored, and all 1,920
deterministic request trace ids were found in native telemetry. Every one-second
health series met its support threshold and the eight-cell aggregate passed with
all 19 quality counters equal to zero.

This is deliberately not effectiveness evidence. M7A fits no model, compares no
method, uses one short forced-sampling pair per cell, and has a regular diagnostic
event grid. Request outcomes and traces from both attempts are excluded from M7.
The supported conclusion is only that the external census, native telemetry,
fault controller, independent state audit, and calibration--test cleanup can be
made complete enough to freeze the later live study.

## Frozen implementation and evidence

- initial acquisition implementation commit:
  `acf11a04a8e4b4dad70694f533536f5fd9c2e446`;
- lossless OTel acquisition repair and tested commit:
  `71836087be70c9017d76d04db062bf62d3f8f35e`;
- CI: [run 33969714343](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33969714343),
  successful on Python 3.11 and 3.13;
- accepted M7A workflow:
  [run 33969721957](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33969721957),
  successful, attempt 1;
- superseded diagnostic workflow:
  [run 33969015066](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33969015066),
  failed as designed on four incomplete OTel linkage cells.

The accepted aggregate ran on CPython 3.13.15 with NumPy 2.4.4, SciPy 1.17.1,
and PyYAML 6.0.2. Every manifest records a clean worktree at the tested commit.
Artifacts are retained by GitHub through 2026-10-05.

| Accepted artifact | Id | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| `m7a-aggregate-33969721957` | 9970602971 | 1,680 | `b94b6352364571d3b53114ef556890fa1aaf4862e8802722a3d7513dda6f917c` |
| DeathStarBench N | 9970582846 | 165,379 | `a07b3e2c9fd4e620173ade7b76e8b3a20e2f5babbbb06f15f63b76b5d1f2f0cc` |
| DeathStarBench NC | 9970583191 | 165,018 | `9095bcb8145992bc47e65c013cece6edcddad6f6b0aae36f1f6c862d21fe35f7` |
| DeathStarBench ND | 9970582973 | 164,154 | `5b44287958c8b2273f778fcf348df7df0d006d5aa059dd09bf181ae9e0cef242` |
| DeathStarBench NCD | 9970581860 | 168,010 | `489c078e60f8d9f8dc644599e41e8f27140f829bea0d095585c37b92c3c8bb6d` |
| OTel Demo N | 9970588805 | 936,162 | `dea32ee1f43fb778bfb5b61a5fee04193935cae0aae6c028a962c9c4c2006cd9` |
| OTel Demo NC | 9970589523 | 857,674 | `9dfaf67246e1f22ce282684bda0bd45955c28ff5f28cdcb60c448f5732ddb7bb` |
| OTel Demo ND | 9970590362 | 912,657 | `2181517737ae44d98639b1bdf3676cc61953f832f4e03db715b68bb26dbecf14` |
| OTel Demo NCD | 9970588651 | 778,335 | `f814502874e59bdd87391fa3789f2a1491f35863d96edac4451096f3ffd1f929` |

## What was implemented

The workflow expands to eight independent jobs and checks out the exact
benchmark commits used by M7P. It renders Compose, removes only the predeclared
OTel upstream generator, digest-locks every active image, and later compares the
running-container inventory with the lock audit. Runtime execution is rejected
outside GitHub Actions.

Each cell contains separate 30-second calibration and test-labelled periods.
Each period schedules 120 logical attempts at four per second, balanced across
three operation classes, with distinct deterministic workload and fault seeds.
Sixteen workers and a two-second request timeout keep blocked requests from
silently reducing the intended exposure. The complete census is written before
trace matching and retains transport errors, timeouts, and missing traces.

The fault controller runs three independently jittered three-second events per
period. N uses individual container pause; NC adds network disconnect; ND adds a
simultaneous two-service logical-domain pause; NCD contains all three mechanisms.
For every event the artifact separates controller intent, application time,
Docker-state verification, restoration, and any error. A second thread samples
running, paused, and health state once per second. No request-success count is a
build gate.

Every logical attempt carries a deterministic externally assigned trace id:
sampled Jaeger `uber-trace-id` for the frozen DeathStarBench instrumentation and
W3C `traceparent` for OTel Demo. DeathStarBench evidence is the raw Jaeger query
response. OTel evidence is an unmodified OTLP/JSON-lines stream written by the
same native collector to a mounted file exporter. The ordinary debug exporter
and complete Compose log remain supplementary diagnostics. A separate join
table records trace presence without deleting an untraced request.

Each cell uploads its request census, trace join, raw telemetry, health series,
intervention audit, rendered and pinned Compose, image audit, runtime inventory,
service log, resource snapshot, runner details, and manifest even when a quality
gate fails. Aggregation requires exactly the configured eight unique cells.

## Accepted-run result

| Application | Law | Requests | HTTP 2xx | Failed/timeout outcome | Requests with trace | Native trace ids | Injections verified/restored |
|---|---|---:|---:|---:|---:|---:|---:|
| DeathStarBench | N | 240 | 224 | 16 | 240 | 241 | 6/6 |
| DeathStarBench | NC | 240 | 213 | 27 | 240 | 242 | 6/6 |
| DeathStarBench | ND | 240 | 219 | 21 | 240 | 240 | 6/6 |
| DeathStarBench | NCD | 240 | 215 | 25 | 240 | 242 | 6/6 |
| OTel Demo | N | 240 | 214 | 26 | 240 | 778 | 6/6 |
| OTel Demo | NC | 240 | 210 | 30 | 240 | 775 | 6/6 |
| OTel Demo | ND | 240 | 212 | 28 | 240 | 766 | 6/6 |
| OTel Demo | NCD | 240 | 210 | 30 | 240 | 771 | 6/6 |

The aggregate therefore contains 1,920 requests, 1,717 immediate HTTP
successes, 203 retained non-successes, 4,055 distinct native trace ids, 48
verified/restored intervention records, and 960 health observations. Every
service-period has 30 health observations, above the fixed minimum of 20. All
successful and unsuccessful requests were trace-linkable in this forced-sampled
run. The larger OTel native count reflects prerequisite and background traces;
it is not an independent-request count.

The accepted result has zero checkout, image-lock, running-container, request,
operation, seed-collision, injection-count, injection-verification,
injection-restoration, health-support, telemetry-collection, duplicate-id,
linkage, missing-cell, unexpected-cell, and usability errors. Calibration and
test workload seeds and fault seeds are distinct in every cell.

The HTTP-success counts are shown only to demonstrate that non-successes remain
in the census. With one short regular schedule they neither estimate an
availability probability nor support a comparison between law labels or
applications.

## Retained failed attempt and repair

The first workflow used the OTel Collector's detailed debug output from Docker
logs as its raw source. DeathStarBench passed all four cells with 100% linkage,
but OTel linked only 22.3% (N), 4.3% (NC), 24.1% (ND), and 62.6% (NCD) of
successful requests. The aggregate retained all cells and reported four
`linked_success_fraction_below_minimum` and four `unusable_cells` errors.

Raw evidence showed that assigned trace ids propagated correctly when present.
The pinned upstream Compose document limits the collector's JSON-file Docker log
to two 5 MiB files, so the higher-rate detailed exporter rotated early records
before end-of-cell collection. The varying fractions were a storage-window
artifact, not stochastic sampling coverage.

The repair added the mounted file exporter while leaving the native receiver and
trace pipeline in place. Matrix, applications, commits, operations, request rate,
period length, event schedules, seeds, and the 80% linkage threshold were not
changed. No estimator existed to tune. The failed aggregate remains artifact
`m7a-aggregate-33969015066`, id `9970403088`, SHA-256
`0541d004c1747aba15d1e2464c799004ad3fedc689bd72609a9595b0982f1c3e`;
its eight cell artifacts and exact provenance remain attached to the failed run.

## Interpretation and next boundary

M7A establishes that controlled pauses, network membership changes, and grouped
logical-domain pauses can be audited and cleaned up while a duration-controlled
client and independent health sampler run. It also establishes complete linkage
under forced sampling for these revisions and this load. It does not establish
natural production trace coverage, physical failure-domain independence,
eventual operation correctness, stationarity, model adequacy, interval coverage,
or placement-transfer accuracy.

Before M7 is frozen, M7B must add two actual key-service replicas and an explicit
auditable load balancer, verify that both replicas serve traffic, define stronger
operation-effect checks, and demonstrate the co-located versus split logical
domain intervention semantics. M7B will remain disposable. Only then can the
stochastic 16-cell, independently repeated calibration--test study be frozen;
neither M7P, M7A, nor M7B rows may be pooled into it.

## Completion checks

- 69 local unit tests and 12 subtests passed; no live workload ran locally.
- CI passed on both supported Python versions.
- All eight remote cells and their exact aggregate completed successfully.
- All 1,920 planned requests and all failures were retained.
- Every assigned request trace id was found in native telemetry.
- All 48 planned interventions were verified and restored.
- Every health service-period exceeded the fixed minimum support.
- Every active rendered and running image matched its digest lock.
- The failed first attempt, repair, artifacts, and interpretation boundary are
  recorded rather than discarded.
