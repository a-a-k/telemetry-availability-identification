# M9Q: observed-operation adapter conformance

Status: artificial adapter contract accepted after an explicitly retained,
post-result usage-oracle repair; the four-sample application census is pending.
This is not an independently parameterized availability comparison.

## Result and original failure

The unchanged PMX binary completed all six prescribed invocations with exit
zero and repeat-consistent semantic outputs. It retained the three operations,
their component ownership, declared instance/host allocations, call edges, and
specified error probabilities in each of three artificial cases. The nested
case produced operation probabilities 0.2, 0.1 and 0, including the successful
sibling of a failing child. Qualified names preserved both same-service
instances and a colliding operation label in another service. Explicit
contraction and forest splitting retained all selected server operations.

The original conformance decision was nevertheless **false in all six
attempts**. Its additional workload oracle expected ten static entry nodes per
observed root operation. PMX emitted one. This was an invalid correspondence
between observational counts and the generated workload representation, not a
lost-operation result. The original protocol, implementation, input artifacts,
failed workflow and machine decision remain unchanged.

The separate source audit recovered 120 Java files from the byte-pinned core
and system-to-PCM bundles. `PCMUsageModelFactory2` emits
`Math.round(calls/callsMin)` entry nodes and hardcodes closed population ten,
with zero think time. For these fixtures its prescribed counts are one entry
per root operation. The fixed population is not an estimate of sample size.
The source and correction are documented in
[`M9Q_USAGE_ORACLE_REVIEW.md`](../M9Q_USAGE_ORACLE_REVIEW.md).

The repaired audit re-read all six retained outputs without invoking PMX. It
kept every structural and error-frequency check, corrected the workload
correspondence according to source, and added exact comparison of every
adapted `(trace ID, span ID, operation, parent)` record with PMX's labelled
reconstruction log. All six comparisons retained 30/30 server records, each
trace appeared exactly once, and reconstructed nanosecond bounds matched the
microsecond envelope. Thus the repaired acceptance verifies conservation more
directly than the original static-entry-node count.

## Execution and provenance

| Phase | Run | Tested commit | Decision |
|---|---|---|---|
| Original three cases, twice each | [34122721945](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34122721945) | `bd68c984c632318f5c15194a2f59143a52216da6` | Workflow failure; all six extractor exits zero; entry-node oracle false |
| Embedded source inspection | [34123438744](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34123438744) | `de1c2ebbbb82965baf5126c4616c63c82c0723d6` | Success; 120 files, zero dynamic invocations |
| Retained-output oracle repair | [34124080148](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34124080148) | `148535c6b84a497c0d70463a61367914483ceea7` | Success; all six repaired checks pass; zero dynamic invocations |

Original config SHA-256:
`ad9619886d889d3f1db6bb816515ea755a70c6ca50cf9ecafa7c5ca89bc0d826`.
Repair config SHA-256:
`7682247a51ad181f6b029a16695b85cbfac46be1961b9304c4eaa6c1173e6480`.
Repaired audit file: 12,527 bytes, SHA-256
`8c169e465cb703769e2f0302e3b9176368cc54c20d6589e454014cb7dcffca40`.

All jobs used a 360-minute limit. Dynamic controls used Python 3.13.15,
Temurin Java 11 and the unchanged 65,729,095-byte author JAR with SHA-256
`befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`.
The six invocations consumed 133.351 measured seconds, including 120 seconds
of prescribed startup stabilization, but excluding workflow setup, downloads,
source inspection and the later audit. This is not a full engineering-cost
measurement or an isolated method-runtime benchmark. Resource-usage files and
all failed-attempt outputs are retained.

The original implementation passed 253 local tests and both CI versions.
The repair added two meaningful artificial tests for Java rounding and keyed
span/parent/time conservation; exact-head CI 34124059019 passed. All local
execution was limited to source/config inspection, unit/synthetic cases and
reading retained derived artifacts. No real native full fit or PMX process ran
locally.

## Retained artifacts

| Artifact | ID | Compressed bytes | GitHub SHA-256 | Expiry (UTC) |
|---|---:|---:|---|---|
| Original frozen adapter contract | 10018835906 | 25,756 | `44e2e1933dbe737413472306d5268a1cd7a02df9008313d35b68d579349efe49` | 2026-12-06 12:35:44 |
| All original conformance attempts and decision | 10018916274 | 169,143 | `f1a01537da0b5a9ad70b739fa510e4dbd9934daa0350033782d68fe88c23c4f4` | 2026-12-06 12:35:44 |
| Embedded workload/core source | 10019108592 | 137,140 | `1de0aec1eda328444b6f11436e47a7ea97822806f3483d7b97e556ad7739541e` | 2026-12-06 12:43:41 |
| Repaired retained-output audit | 10019357941 | 1,892 | `0bc1803aafbc473797522e5bba06b488c94dd4fb4a4373bcc6659545322e9d06` | 2026-12-06 12:50:40 |

The 30 contract files and all 30 core PCM files matched their retained
manifests. All 120 embedded source files matched the source manifest, whose
SHA-256 is
`cdbd3b040000577aa1dea97e79d2c0f7677be5406a2a747782aabd69c0d3de59`.

## Scope of acceptance

Acceptance is explicitly conditional on the post-result oracle correction.
It supports applying the unchanged observed-operation adapter to the four
historical learner audit samples under a separate frozen acceptance record.
Each full historical sample has one prospective invocation with a 1,800-second
internal watchdog; this larger application-size limit is fixed before any such
extraction and leaves the six original 180-second control limits unchanged.
It does not rewrite the original prospective gate as passed, and technical
repeats do not increase the number of independent scientific campaigns.

The adapter deliberately adds compatibility markers and instance-qualified
component types, contracts observed intermediate spans, and splits forests
without inventing an external root. These are measured adaptation choices.
They do not demonstrate unmodified native instrumentation support or recovery
of interchangeable replicas, common-cause failure parameters or router policy.

The fitted resource-demand literals for 0.005-second leaves were approximately
0.002105263 seconds. The envelope and reconstructed time bounds are correct;
the resource-demand estimator and author defaults do not establish performance
calibration. The fixed closed workload and rounded entry mix are also distinct
from traffic replay. First-timestamp collisions in the source's workload map
remain a concrete application audit condition.

Operation span-error frequencies are not external semantic-request failure
probabilities. Propagated errors, missing invocations, client timeouts and
incomplete roots remain open for a later availability mapping. M9P independent
temporal confirmation proceeds under its existing protocol and receives no
input or design change from this conformance exercise.
