# M7P: runtime and native-telemetry feasibility pilot

## Outcome

M7P is complete as a disposable infrastructure milestone. Both frozen benchmark
revisions ran on separate GitHub-hosted Linux jobs, every active container image
was locked by manifest digest, the predeclared external client retained all 120
attempts per profile, and both native telemetry paths produced nonempty trace
evidence. The aggregate job passed every technical quality check.

This is not an effectiveness result. The pilot had no injected faults, estimates
no availability model, performs no method comparison, and contributes no rows to
M7. Its only supported conclusion is that the selected revisions, operations,
and telemetry transports are technically usable for freezing the live protocol.

## Frozen implementation and evidence

- initial protocol and implementation commit:
  `59096f5d29a7424ddaf56a1021cab8e32dd00930`;
- audited pilot repair and tested commit:
  `2df7d5628c66b1501549262ecdcafe8be8383acd`;
- CI: [run 33967547881](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33967547881),
  successful on Python 3.11 and 3.13;
- accepted M7P workflow: [run 33967554003](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33967554003),
  successful, attempt 1;
- aggregate artifact: `m7p-aggregate-33967554003`, id `9969951408`,
  1,160 compressed bytes, SHA-256
  `a32c7a4b8ae6a38aab4bac12a177d49677d6f820f757c5899f2f11549d5dc0eb`;
- DeathStarBench artifact: `m7p-deathstarbench_social_network-33967554003`,
  id `9969928084`, 41,907 bytes, SHA-256
  `920718f487ec688d80beb5661fb91541eb8fea4b069812b63482c685d75245a7`;
- OpenTelemetry Demo artifact: `m7p-opentelemetry_demo-33967554003`,
  id `9969940174`, 405,084 bytes, SHA-256
  `2b86400c91cbf16e777acdbd8e6b3e6cda62b48dda22234cce940ba5fef7d105`.

The artifacts are retained by GitHub through 2026-10-05. The aggregate and both
profile manifests record a clean worktree at the tested commit. Aggregation ran
on CPython 3.13.15 with NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2.

## What was implemented

The pilot workflow checks out the exact DeathStarBench Social Network and OTel
Demo commits independently, renders their upstream Compose configurations, and
replaces every active image reference with a configured manifest digest. Build
directives are removed. The pinning step fails on an unlocked active service, an
unused lock, a missing declared exclusion, or an ambiguous image alias. Runtime
inventory is compared with the lock audit rather than trusting the Compose file
alone.

For each application, a separate external Python client executes calibration
and test-labelled halves with distinct deterministic seeds. Each half contains
20 attempts for each of three operations. The labels exercise period separation
only; these short pilot halves are not statistical repetitions. Every request is
retained with its HTTP/transport outcome and timing. Runtime execution is
programmatically refused outside GitHub Actions.

DeathStarBench is stabilized for 30 seconds, then initialized with two users and
two directed follow relationships. This is the smallest nonempty graph needed
for its compose-post fan-out. Its upstream `latest` Jaeger reference is replaced
by the recorded Jaeger 1.57.0 multi-platform manifest digest, which retains the
legacy UDP agent receiver used by the frozen application revision. Raw telemetry
is saved from the Jaeger query API.

OTel Demo is also stabilized for 30 seconds. Its upstream `load-generator` is
explicitly removed from the pilot Compose document because the experiment has
one separately counted external client; the corresponding dependency edge and
image lock are removed and the exclusion is recorded in the audit. Raw detailed
collector output is saved through the upstream-supported extra configuration.

Both jobs upload rendered and pinned Compose documents, image-lock audit,
runtime container inventory, complete request census, native raw telemetry,
runner resources, Compose state, service logs, and container resource snapshots,
including on failure. The aggregate refuses either unusable profile.

## Accepted-run result

| Profile | Requests | HTTP 2xx | Native traces | Running / locked services | Status |
|---|---:|---:|---:|---:|---|
| DeathStarBench Social Network | 120 | 120 | 28 | 27 / 27 | usable |
| OpenTelemetry Demo | 120 | 120 | 159 | 19 / 19 | usable |

All aggregate quality counters were zero: checkout mismatch, request-count
mismatch, success below 0.95, insufficient traces, telemetry collection error,
unlocked rendered or running images, missing running containers, and unusable
profiles. The trace counts exceed the predeclared nonempty-path threshold of six
but are not interpreted as trace coverage or independent sample size. In
particular, OTel Demo can emit multiple traces for one external operation.

The counted workload portions were intentionally brief. DeathStarBench took
about 0.15 seconds for its calibration half and 0.13 seconds for its test half;
OTel Demo took about 2.00 and 0.71 seconds. These timings show that a duration-
controlled driver, rather than this sequential pilot count, is needed for M7's
fault-exposure windows.

## Superseded diagnostic run

The first execution, [run 33967096628](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33967096628),
failed and is retained as pilot diagnostic evidence. It is not silently pooled
with the accepted run:

- DeathStarBench retained all 120 attempts but compose-post returned HTTP 500
  for 40 attempts, yielding 80/120 successes. Its log identified an empty social
  graph during follower fan-out. The mutable Jaeger `latest` digest resolved to
  v1.76.0; no legacy UDP receiver appeared in the startup log and the query API
  returned zero traces.
- OTel Demo's 19 other application/telemetry services remained running, with
  their declared health checks passing, but the disabled upstream generator
  remained unhealthy. Compose therefore stopped before the
  external pilot even though that service was intentionally not part of the
  experiment workload.

Those observations motivated only infrastructure repairs allowed by the
predeclared pilot protocol: initialize the minimum required graph, use a Jaeger
digest compatible with the frozen sender, and exclude the conflicting upstream
generator. No sample size, fault regime, estimator, success threshold, or trace
threshold was changed. The invalid profile artifacts remain available as
`m7p-deathstarbench_social_network-33967096628` (id `9969787523`) and
`m7p-opentelemetry_demo-33967096628` (id `9969817753`).

## Interpretation and next boundary

M7P establishes runtime feasibility on one ephemeral GitHub runner generation.
It does not establish semantic correctness of every successful operation,
stationarity, independence, model adequacy under failures, or transferability of
component parameters. Both systems share one physical runner within a job;
therefore later Docker groups may represent controlled logical failure domains,
not independent physical hosts.

Before the first M7 test outcome is inspected, the live protocol must separately
freeze duration-controlled calibration/test windows, injection schedules and
audits, learner-visible sources, operation-level effect checks, campaign-level
repetition, block uncertainty, B0--B4 roles, exclusions, and placement semantics.
Pilot traffic and its observed success rates remain excluded from every such
estimate.

## Completion checks

- 61 local unit tests passed; no benchmark or campaign ran locally.
- Both exact upstream commits were observed.
- Every active rendered and running service matched a digest lock.
- Both profiles retained exactly 120 independently counted client attempts.
- Both profiles exceeded the fixed success and nonempty telemetry thresholds.
- All raw evidence and failure diagnostics were uploaded.
- The two-profile aggregate completed with all quality counters at zero.
- The failed first attempt and every pilot-only interpretation restriction are
  recorded rather than omitted.
