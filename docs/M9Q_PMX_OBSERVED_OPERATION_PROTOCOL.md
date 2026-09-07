# M9Q: qualify an observed-operation adapter for the pinned PMX route

Status: prospective adapter design, written during independent M9P acquisition.
M9P's implementation, population and three confirmation questions are unchanged.
This separate development experiment uses artificial conformance traces and the
four already designated M7 raw audit samples. It does not use M9P observations,
fit request-availability forecasts, or score any evaluator outcome.

## Question and fixed scope

Can the recovered, byte-pinned PMX binary retain an explicitly adapted forest
of observed server operations, including their call edges, instance identities,
durations and span-error frequencies? This is a prerequisite to a later
end-to-end application comparison, not that comparison itself. M9H established
the command, and M9J established a working failure carrier; neither is reopened.

The source constraints and accepted M9I artifact are recorded in
`PMX_APPLICATION_INPUT_CONTRACT.md`. Two additional constraints are visible in
`TraceReconstructionService.addListOfChildSpansToSpan`: a CHILD_OF reference to
an absent span dereferences a null parent, and each root overwrites the previous
root variable. A forest must therefore be handled explicitly before invocation.

## Fixed adapter semantics

1. Read either Jaeger JSON or OTLP JSONL. Select original trace IDs exclusively
   from baseline/calibration membership in the retained `trace-join.csv`.
   Test IDs form a disjoint exclusion set. Outcome columns are never inputs.
   Preserve the native input hash and selection audit; real parsing and model
   extraction run in GitHub Actions only.
2. Normalize IDs, native typed attributes, service identity, start/duration,
   parent references, span kind and error evidence. Duplicate identical spans
   are counted once; conflicting duplicates, cycles, invalid durations and
   ambiguous CHILD_OF parents are explicit invalid-trace cases. No conflicting
   version is selected by file order.
3. Admit only explicitly marked SERVER spans (`span.kind=server` in Jaeger;
   OTLP kind 2 / SPAN_KIND_SERVER). Missing kinds do not establish server
   semantics. The audit retains counts of all other kinds and of their errors.
4. For each admitted span, follow the recorded parent chain to the nearest
   admitted ancestor. This contracts observed intermediate spans; it adds no
   unobserved operation. If the chain ends or reaches an absent parent, start
   a separate observed tree and record which case occurred. Reject cycles.
   Emit each tree as a separate PMX trace with a deterministic derived trace ID;
   preserve original trace/span identity in the sidecar. Never synthesize an
   external root. Multiple trees and missing parents remain explicit coverage
   limitations for a complete external-request model.
5. Define instance identity by the first available native declaration among
   `service.instance.id`, `container.id`, `container.name`, `k8s.pod.name`,
   and `host.name`, retaining the chosen key. If none is available, label the
   service instance unresolved. Do not use per-trace Jaeger process IDs as a
   stable replica identifier. Give each (service, instance declaration) a
   deterministic PMX component name and qualify each operation by that identity
   and its native name. This explicitly creates component types per observed
   instance to accommodate the pinned reconstruction's assembly lookup. It
   does not claim that PMX inferred interchangeable replica types or failover.
6. Set PMX `host.name` from an explicit host declaration. Synthetic cases use
   their fixture hosts. Each historical campaign uses one declared GitHub
   runner host because its Docker containers ran on that worker. Native
   container host labels and logical fault-domain declarations are retained
   separately; neither is silently interpreted as a physical host.
7. Convert integer native OTLP nanoseconds to microseconds with floor division;
   record discarded sub-microsecond remainders. Jaeger microseconds remain
   unchanged. Require positive representable duration and a signed-64-bit-safe
   accessor round trip. Hash-based operation names avoid the pinned Spring
   name exclusions. Add and disclose the `spring-webmvc` compatibility marker
   to every selected operation so that it survives the known merge rules.
8. Set `error=true` only from an explicit native error tag (boolean true or
   the exact case-insensitive string true), or OTLP ERROR status. Do not infer
   errors from HTTP status alone and do not import external semantic success.
   Record tag/status sources, discrepancies and errors on discarded spans.
   The denominator is observed eligible operation invocations. A missing
   invocation, timeout without a server span, propagated error, or unfinished
   span is not converted to an independent primitive failure probability.

The adapter writes the PMX envelope, a span-level mapping with original
attributes, a per-trace coverage census, and independently counted operation
frequencies/edges. It preserves all original selected trace IDs in the census,
including those absent from raw telemetry or yielding no admissible tree.
Native streams remain authoritative for attributes omitted from PMX.

## Artificial conformance cases and oracles

One bounded remote invocation per case, repeated twice on identical inputs,
uses the unchanged author JAR, Java 11 and `main:main -of Options.txt`, with
20-second startup stabilization and the already demonstrated 180-second
internal watchdog. All workflow jobs have a 360-minute limit. No command
screen or launcher search is performed.

| Case | Independent expected result |
|---|---|
| nested operations and errors | Ten root operations each call one child and one successful sibling. One child error, two root errors: operation failure probabilities 0.1, 0.2 and 0; three distinct operations, two call edges; the sibling remains separate. |
| colliding local names and replicas | Two instances of one service and a different service share a local operation name. All three qualified operations and all three component instances survive; fixture host declarations remain distinguishable. |
| contracted parent and forest | Server-child ancestry across a CLIENT intermediate contracts to one edge; another server under an absent parent becomes a second tree with explicit incomplete-request status. Every selected server appears exactly once. |

Local unit tests also cover time quantization, absent traces, non-server errors,
conflicting duplicates, cycles, bad durations, learner/test overlap, and name
qualification. These tests are bounded artificial examples, not local full
fits. Dynamic PCM oracles resolve operation signatures, SEFFs, call targets
and allocation references by XML IDs. Stdout order is never an oracle. Durations
are checked in adapter records and the emitted model where a directly resolved
corresponding quantity exists; absence of a resolved model timing quantity is
reported as unverified, not replaced with a stdout-position assumption.

The structural gate also checks operation ownership and the counts of resolved
entry operations (ten root entries in the first two cases; ten entries for
each of the two forest roots in the third). The author options are unchanged
except for the input file path. Their CPU-count placeholder/defaults are
retained and disclosed, so extracted resource-demand literals are diagnostics
and do not establish a calibrated performance model. The fixed leaf duration
is 5,000 microseconds (0.005 seconds); record its resolved numeric comparison.
Malformed native JSONL records are counted and make completeness unresolved;
their contents are never replaced with inferred spans.

All model files, stdout, watchdog records, adapter mappings, input hashes and
timing/memory records are retained for 90 days, including failed cases. Technical
repetitions are not independent accuracy samples. A failed case is reported
before any separately labelled corrective experiment; no silent oracle change.

## Historical application census

After the artificial contract qualifies, apply the same frozen adapter to all
four M7 raw audit samples identified in M9G: both applications, both placements,
NCD, repetition 0. Obtain them from the exact M8A preserved artifact (ID
9983956440, run 34016153918, SHA-256
978b380bf54be67ec13b2ebbfaac4464ee5653106ee68176fefcf2db4e85e271).
Use every baseline/calibration trace ID in those four samples. They remain a
schema/application-development subset, never the 160-campaign accuracy census.

Report traces requested/present/adapted, server-span coverage, missing/ambiguous
roots, forests, rejected inputs, unresolved instances, observed operations and
call edges, and operation error counts. Run the pinned extractor once per
application sample only if the artificial conformance gate passes. Compare
emitted structures and error probabilities with the adapter's directly counted
operation oracle; retain mismatches without changing the input population.
Do not access evaluator files or compute availability prediction scores.

## Decision and continuation

Conformance requires all structural and error-frequency synthetic oracles on
both technical repeats, with no lost selected operation. Timing verification
has a separately reported scope. Application coverage and fidelity are reported
per sample, including zero-output and failure cases. Passing means that this
measured adapter can supply the demonstrated observed-operation model; it does
not imply correct external semantic-request availability, unobserved-call
coverage, temporal failover, common-cause representation, or lower monitoring
cost. Failure identifies a concrete adaptation issue in the selected binary.

The next comparison design must explicitly address these remaining semantic
conditions, propagated errors and missing-request selection before using an
extracted model as an independent availability forecast. It must freeze
parameters/predictions on learner inputs before evaluator access. M9P's
independent temporal confirmation proceeds regardless of this adapter result.
