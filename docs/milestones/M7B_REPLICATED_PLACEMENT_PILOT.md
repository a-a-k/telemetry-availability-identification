# M7B: replicated placement, routing, and operation-semantics pilot

## Outcome

M7B is complete as a disposable engineering pilot. Two real instances of one
key service were started behind a digest-locked HAProxy in each of two live
applications. The accepted four-cell GitHub Actions run demonstrated that both
named backends served semantic traffic, the configured co-located and split
logical-domain interventions affected different running-container sets, every
operation sentinel passed its content predicate, and every intervention was
verified and restored. The aggregate contains all four expected cells and all
28 quality counters are zero.

The result answers an important anti-strawman question: the placement treatment
is not a metadata-only relabelling of one instance, and success is not defined
as any HTTP 2xx. It still does not show that the proposed estimator is better
than B0--B4, that either placement has higher availability, or that two logical
Docker domains reproduce physical infrastructure. All 844 pilot requests are
excluded from M7 effectiveness evidence.

## Frozen implementation and evidence

- initial M7B implementation commit:
  `5b197eb5323e6fcc835854b252a96decd4fa9d26`;
- DeathStarBench wire-semantics repair and accepted tested commit:
  `9e81f82398fd6923a4a8102b8d76d7f0ebe1f308`;
- accepted CI:
  [run 33971942776](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33971942776),
  successful on Python 3.11 and 3.13;
- accepted M7B workflow:
  [run 33971951003](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33971951003),
  successful, attempt 1;
- retained superseded workflow:
  [run 33971493488](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33971493488),
  failed on the two DeathStarBench semantic gates and succeeded on both OTel
  cells.

The accepted aggregate ran on CPython 3.13.15 with NumPy 2.4.4, SciPy 1.17.1,
and PyYAML 6.0.2. Every manifest records a clean worktree at the accepted
commit. Artifacts are retained by GitHub through 2026-10-05.

| Accepted artifact | Id | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| `m7b-aggregate-33971951003` | 9971233564 | 1,523 | `ee917befd66ef24cef0f148d98e702c526d002ef420041a040b878a53b7ad34d` |
| DeathStarBench co-located | 9971215762 | 168,639 | `8d23896f1e0f59e42b3a38fd7af1da7ee59ff925e4078a7c7b6a48368682d69e` |
| DeathStarBench split | 9971214334 | 170,730 | `3d737fd7eee9d9a4a1c462546d78b18cd989a39b68fd6ffc71f2f8657d676ee6` |
| OTel Demo co-located | 9971222251 | 750,086 | `25607f80ea905b146a196b45e47c8d9b82b1bc380e5f8364925254df4c52eea4` |
| OTel Demo split | 9971219492 | 776,532 | `4d392c0d6a4c2b66268e446a6da299cfa1334619e6c37572161b0257a761c636` |

## What was implemented

The workflow creates four independent jobs: two pinned applications crossed
with co-located and split placements. In DeathStarBench, the original
`user-timeline-service` is replaced by two separately named containers behind a
TCP HAProxy retaining the original name and port. In OTel Demo the same
transformation is applied to `product-catalog`, using an h2-aware proxy. The
HAProxy 3.0 Alpine multi-platform manifest and every active application image
are digest-locked. The upstream OTel load generator remains disabled so only
the study client contributes counted requests.

Replica a and b both carry `domain_a` in the co-located cell. In the split cell,
replica a carries `domain_a` and replica b carries `domain_b`. These assignments
are executable: a common-domain event enumerates labels on actual containers,
pausing two backends in the co-located cell and only backend a in the split
cell. The proxy is a separate communication boundary. Generated Compose,
HAProxy configuration, labels, image audit, and runtime inventory are retained.

Before any intervention, a 48-request concurrent burst exercises the operation
that traverses the replicated service. HAProxy statistics taken immediately
before and after must show at least one new session on both named backends, both
backends `UP`, and at least 90% semantically valid responses.

One sentinel for each of three operations then applies executable content
semantics. DeathStarBench requires the exact compose acknowledgement and valid
timeline wire content; the composed post must subsequently be present in both
the author's user timeline and follower 1's home timeline. The counted home
read also targets follower 1, who follows author 0, rather than a normally empty
author home timeline. OTel requires the selected product id, a cart containing
that product with positive quantity, and nonempty order and shipping identifiers.
Exact response bytes and hashes are retained separately from HTTP status.

The 40-second fault period schedules 160 attempts at four per second. At
seconds 4, 12, 20, and 28 it applies three-second individual-a, individual-b,
domain-a, and proxy-network events. A one-second independent sampler records the
two replicas and proxy. Controller intent, observed application, restoration,
and final clean state are separately audited. The fault-period success count is
never an acceptance gate.

Every counted request receives a deterministic forced-sampled native trace id.
The external census exists before trace matching; all failures and exact bodies
remain present. Raw Jaeger JSON or the lossless mounted OTel Collector stream,
the request--trace join, health series, fault audit, runtime diagnostics, and
manifest are uploaded even when a gate fails. Runtime execution is rejected
outside GitHub Actions.

## Accepted-run result

| Application | Placement | Requests | Semantic successes | Fault-period successes | Requests with trace | Native trace ids | Backend sessions a/b | Injections verified/restored | Health samples |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DeathStarBench | co-located | 211 | 199 | 148/160 | 211 | 214 | 7/7 | 4/4 | 120 |
| DeathStarBench | split | 211 | 200 | 149/160 | 211 | 213 | 6/6 | 4/4 | 120 |
| OTel Demo | co-located | 211 | 196 | 145/160 | 211 | 647 | 24/24 | 4/4 | 117 |
| OTel Demo | split | 211 | 199 | 148/160 | 211 | 654 | 24/24 | 4/4 | 117 |

All 51 pre-fault requests per cell--three sentinels and 48 routing probes--were
semantically valid. The remaining 50 non-successes occurred during declared
fault periods and were retained. Consequently the aggregate contains 844
requests, 794 semantic successes, 590 fault-period successes, 1,728 distinct
native trace ids, 16 verified/restored intervention records, and 474 health
observations. All 844 assigned request ids were found in native telemetry; the
acceptance metric over semantic successes is therefore also 100% in every cell.

The routing evidence rules out an idle decorative replica: DeathStarBench
registered 7/7 and 6/6 new sessions on a/b, while OTel registered 24/24 in both
placements. Every routing response passed its semantic predicate and both
backends were `UP` before and after the burst.

The health series also observed the treatment distinction. In each co-located
cell both replicas were paused for six sampled ticks: three for their individual
event and three for the shared domain-a event. In each split cell replica a had
six paused ticks while replica b had only its three individual-event ticks. The
proxy had three disconnected ticks in every cell. Each service had 39 or 40
valid observations, above the fixed minimum of 30, with no sampling error. The
final audit found every replica and proxy running, unpaused, on exactly one
network, with both backends `UP`.

The different fault-period success counts are diagnostic observations from one
short, regularly forced schedule. They are not probability estimates and no
placement contrast, confidence interval, model fit, or method comparison is
computed from them.

## Retained failed attempt and repair

In the initial workflow both OTel cells passed. Both DeathStarBench cells also
passed routing, eventual-effect, trace-linkage, image, intervention, health, and
cleanup checks, but each reported one `sentinel_semantic_failures`. The exact
retained response showed HTTP 200 with body `{}` for an empty home timeline.

The pinned upstream Lua code constructs an empty timeline as an empty Lua table;
lua-cjson serializes that ambiguous value as `{}`, while nonempty timelines are
JSON arrays. Our first validator incorrectly required an array in all cases.
This was a study-harness mismatch, not an application or replication failure.

The repair accepts only the exact empty object as the upstream empty value and
continues to reject arbitrary objects and malformed post arrays. It also changes
the counted home read from author 0 to initialized follower 1 so ordinary reads
exercise a populated, causally meaningful feed. A unit test pins both the wire
rule and follower selection. The four-cell matrix, benchmark revisions, image
digests, proxy, placements, schedule, workload rate, seeds, thresholds, and all
fault mechanics were unchanged, and the complete matrix was rerun on one new
commit.

The failed aggregate remains artifact `m7b-aggregate-33971493488`, id
`9971109088`, SHA-256
`9430c3a7fa1c20a20f445e88ae0a06d6ac78614d8f76ac216cf751d0f9558075`.
Its four cell artifacts remain attached to the failed run.

## Interpretation and next boundary

M7B establishes a technically credible treatment and response contract for the
next stage. A reviewer can inspect two running replicas, observed per-backend
traffic, placement-dependent pause sets, semantic response bodies, post fan-out,
native traces, and cleanup rather than relying on topology labels alone.

The boundary remains material. Both logical domains share one GitHub-hosted
kernel, Docker daemon, and physical machine; HAProxy is one explicit routing
policy; trace contexts are forced sampled; and one deterministic 40-second
schedule cannot characterize stochastic availability. Replication itself may
also introduce state, consistency, or routing effects beyond the conjunctive
failure model. Those are limitations to measure or diagnose, not facts that M7B
has eliminated.

The next pre-registration step must freeze a genuinely stochastic event process,
independent calibration and test periods, the number and unit of repetitions,
natural telemetry-loss policies, estimand and exclusions, and matched B0--B4
analysis before inspecting effectiveness outcomes. M7P, M7A, and M7B data may
inform engineering feasibility and resource budgeting only; none may be pooled
with that frozen campaign.

## Completion checks

- 77 local unit tests passed; no live application ran locally.
- CI passed on both supported Python versions.
- All four independently provisioned remote cells and the aggregate passed.
- Both named backends served semantic routing traffic in every cell.
- All 12 operation sentinels and both DeathStarBench fan-out audits passed.
- All 844 planned requests, including 50 non-successes, were retained and linked.
- All 16 planned interventions were verified and restored with exact targets.
- Placement-dependent health observations matched the declared treatment.
- Every rendered and running image matched its digest lock; final state was clean.
- The failed first attempt, exact repair, artifacts, and inference boundary remain
  auditable.
