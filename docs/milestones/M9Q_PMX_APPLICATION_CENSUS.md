# M9Q: historical PMX observed-operation application census

Status: complete as a four-sample application census; no sample establishes the
full frozen projection contract. All four results are retained. This stage
produces no availability forecasts or effectiveness comparison.

The accepted execution is [34125799582](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34125799582)
at `e349db8ef235c3dfc89ba0e9ca440be1b8c017ed`, from
2026-09-07T13:09:32Z through 13:13:04Z. Its application config SHA-256 is
`4a633fac8d73224339cfa8b262127fbae88f23870e842b98789a422cf6dd3b7b`.
The exact-head CI [34125798730](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34125798730)
passed. The census records technical completion separately from scientific
qualification; a successful Actions job is not a projection-fidelity pass.

## Preserved entry gate and first technical failure

The artificial adapter conformance and explicit retained-output oracle repair
are reported in [the conformance report](M9Q_PMX_OBSERVED_OPERATION_CONFORMANCE.md).
The original six prospective conformance failures remain recorded. The application
job checked the accepted repaired artifact and its exact file hash before access
to the historical source archives.

The first application run [34125261493](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34125261493)
at `5868cac7503a44d9462559871441821e9327c803` passed that gate and the source
checks, then rejected the existing `sentinel` period in `trace-join.csv` before
native parsing or extraction. Its preparation and four-missing-sample census
artifacts are retained. The documented correction accepts the four historical
period labels, excludes test and sentinel, and rejects overlap with learner IDs.
No adapter, invocation budget, operation-error rule or fidelity oracle changed.
See [the execution contract](../M9Q_APPLICATION_CENSUS_EXECUTION.md).

Each repaired selection contains exactly 240 baseline and 3,600 calibration
trace IDs. The 3,600 test and three sentinel IDs are excluded. Membership uses
only period and trace ID; outcome columns are not read. All twelve historical
source files match M8A's independent inventory. No M9P data enters this stage.

## Complete application census

All samples are the four predeclared M7 NCD/r0 raw audit samples. The eligible
projection requires an explicit SERVER kind, retains qualified operation and
instance identities, contracts recorded non-server ancestors, and separates
observed trees when parents are missing. These are disclosed adapter semantics,
not a claim that the native instrumentation is equivalent to Spring-WebMVC.

| Sample | Selected original traces | Valid native spans | Selected SERVER spans | Observed trees | Operations / distinct call edges | PMX invocations | Frozen result |
|---|---:|---:|---:|---:|---:|---:|---|
| DeathStarBench colocated | 3,840 | 54,142 | 0 | 0 | 0 / 0 | 0 | No explicitly marked server input |
| DeathStarBench split | 3,840 | 55,467 | 0 | 0 | 0 / 0 | 0 | No explicitly marked server input |
| OpenTelemetry Demo colocated | 3,840 | 106,346 | 43,415 | 7,101 | 20 / 27 | 1 | Usage-entry mismatch |
| OpenTelemetry Demo split | 3,840 | 100,549 | 41,071 | 6,909 | 20 / 27 | 1 | Usage-entry mismatch |

The DeathStarBench outcome concerns this adapter's explicit-kind requirement.
All selected native traces exist, but none contains an eligible span. It is not
an empty native stream or evidence that PMX cannot model DeathStarBench. Recovering
operation roles there requires an additional source-grounded instrumentation or
mapping contract; silently labeling every span as SERVER would change the task.

For both OpenTelemetry samples, all selected SERVER spans were reconstructed
exactly once with matching trace/span/operation/parent inventory and nanosecond
bounds corresponding to the microsecond input. The operation set, per-operation
error probabilities, call-edge set, component set, operation ownership, and
allocation references all match their independent learner oracles. The two
models retain 707 and 1,110 eligible error spans respectively. This verifies the
reported observed-operation frequencies, including propagated errors; it does
not make them independent primitive failure probabilities.

Neither placement passes the seventh check, usage-entry counts. Both have the
source-defined closed population 10 and zero think time. For each sample the
root-frequency oracle expects one static GET entry and one static POST entry,
after the already accepted relative-count normalization. The generated models
instead contain seven entry operations and 116 / 54 static entries:

| Native service and operation | Expected colocated / split | Actual colocated | Actual split |
|---|---:|---:|---:|
| frontend-proxy GET | 1 / 1 | 52 | 12 |
| frontend-proxy POST | 1 / 1 | 22 | 9 |
| frontend POST /api/checkout | 0 / 0 | 11 | 4 |
| frontend GET | 0 / 0 | 1 | 3 |
| frontend POST | 0 / 0 | 1 | 1 |
| frontend GET /api/products/[productId]/index | 0 / 0 | 10 | 15 |
| frontend POST /api/cart | 0 / 0 | 19 | 10 |

The native labels here are resolved through the retained mapping; hashed PMX
operation and component identities remain in the artifacts. Static entries are
neither counts of measured requests nor an external workload replay.

## Retained-output diagnosis, without another extractor run

[34128536931](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34128536931)
at `5781ad77dc55f30e6fb6b0927927d3637917e641` verified all six source archives
against their complete compressed byte lengths and SHA-256 digests, all 44
learner-contract files, both copied contracts and fidelity records, and all ten
generated core PCM files. It exported only compact derived descriptions locally.
It performed zero PMX invocations, fits, forecasts or evaluator reads, and did
not amend a gate.

In the retained exact source, `ExecutionTrace.toMessageTrace` sorts executions
by start time. `WorkloadService.getStartMessage` selects the receiving execution
of the earliest message. This can differ from the root defined by parent IDs.
The audit observes a descendant starting before the projected root in 2,569 of
7,101 colocated trees and 4,208 of 6,909 split trees, with maximum leads of 753
and 786 microseconds. There are also 1,362 and 2,164 trees with multiple earliest
spans. The five internal entry operations above are also the operations found
at those earlier descendant positions.

This supports a timestamp-versus-parent-root explanation of the extra usage
operations. It does not uniquely establish why the original timestamps differ
(clock behavior, instrumentation boundaries and other causes are distinct), nor
does it reproduce the exact treatment of tied starts. No matching usage log lines
were present in retained stdout. The original failure therefore remains an
observed projection mismatch, rather than being converted to a pass by another
post-result oracle change.

Source anchors are from the already preserved M9I and M9Q source archives:

| File | Bytes | SHA-256 |
|---|---:|---|
| WorkloadService.java | 2,888 | `8b55696be1d2edb62ff4c46932e8f40d21435ee95dfb249a7e4d9ae290992aa1` |
| ExecutionTrace.java | 12,823 | `394132dbff39cd99da61633d533cfb5faab880417ccafd200b3a3772d30584ab` |

## Coverage and measured costs

Both OpenTelemetry samples adapt all original selected trace IDs, but have 7,101
and 6,909 missing-parent roots and 2,176 / 2,043 original traces with multiple
observed trees. Thus coverage of trace IDs does not establish complete external
request reconstruction. There are no malformed JSON records or unresolved
instance spans under the declared fallback rules. The numbers of discarded
non-server error spans are 190, 166, 727 and 1,147 in table order. Missing requests
and timeout failures without a selected server span are outside these frequencies.

| Sample | Native stream bytes charged | Selection / parsing / projection seconds | PMX elapsed seconds, including startup | PMX maximum RSS, KiB |
|---|---:|---:|---:|---:|
| DeathStarBench colocated | 55,939,259 | 2.241 | No invocation | Not measured |
| DeathStarBench split | 56,876,338 | 1.959 | No invocation | Not measured |
| OpenTelemetry Demo colocated | 209,683,042 | 10.576 | 77.038 | 2,664,460 |
| OpenTelemetry Demo split | 208,626,026 | 11.935 | 51.130 | 4,260,572 |

Each PMX invocation exited zero, includes 20 seconds of startup, and stayed below
the predeclared 1,800-second internal watchdog. The complete preparation process
took 30.77 seconds and peaked at 996,564 KiB RSS; its per-sample timers exclude
some shared checking and output writing. These historical native files contain
the full preserved campaign stream, although only the declared learner IDs enter
the projection. File sizes charge that shared acquisition artifact, not just the
selected observations. Six application artifacts total 37,446,534 compressed
bytes. The cost of downloads, original acquisition, adaptation engineering and
monitoring overhead is not an isolated extractor runtime and is not inferred
from these numbers.

## Artifacts and retention

All six application artifacts have source run 34125799582 and source head
e349db8ef235c3dfc89ba0e9ca440be1b8c017ed. They were unexpired at the audit and
retain until 2026-12-06T13:09:32Z. Names share suffix `-34125799582-a1`.

| Name prefix | ID | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| m9q-application-learners | 10020054857 | 22,701,700 | `aae7d4d42af0a69be551ac7d043f213a5586344560142195f93c0c15fd49d98e` |
| m9q-application-result-deathstar-colocated | 10020084953 | 2,705 | `b8e511e52eabb6dc7c0d889c1e2775001bad937de50c5906cdb200205b07d222` |
| m9q-application-result-deathstar-split | 10020079560 | 2,701 | `88f38fd91cb6d4399e674c652c9f64b3e3b57c08a372d6f9403207d56783c9ae` |
| m9q-application-result-otel-colocated | 10020125363 | 7,610,311 | `03ac57d4a9f02777696f55fa8f593a06ba222ae6e49a9ed123f69f175fdc98cb` |
| m9q-application-result-otel-split | 10020116368 | 7,127,411 | `25f5bc5370ef6ccf19d3a0c0e28680786ab011055e9f8dfad1e90df0c774df2c` |
| m9q-application-census | 10020141593 | 1,706 | `07c98a7a974933c58b43fb30281f0e6bed0ec2ab2764376dbca46d15f43e1ad1` |

`application-census.json` is 9,066 bytes with SHA-256
`6fbc56a16c7cda881a28deb0e1eb77649a621b4c12cc115a9d4bc860f32c376f`.
The descriptive audit artifact `m9q-retained-application-description-34128536931-a1`
has ID 10021098138, 4,900 compressed bytes, digest
`988e243921d0a2681913258172c56bd8cc8c457ed6acdf38f3f1a4e7d2422a6c`, and
expiry 2026-12-06T13:38:37Z. Its JSON is 35,868 bytes with SHA-256
`9c180d8172d9ba839096dc18667b2038c500f728d6ce8d4af52bd7e4aab840ed`.

## Scientific continuation

M9Q establishes a working extraction path for these OpenTelemetry observed
operations and identifies explicit limits of its current application contract.
The outstanding comparison needs a shared semantic request, treatment of
propagated errors, missing spans and requests, replication and temporal state,
and independent parameterization before scoring availability. The current
workload should not be treated as that shared request model. Integration cost
does not reduce PMX's relevance, and these four reused samples do not establish
either method's predictive superiority.
