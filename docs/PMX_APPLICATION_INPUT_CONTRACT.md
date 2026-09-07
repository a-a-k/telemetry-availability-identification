# Remaining application contract for the recovered PMX binary

Status: source-backed preparation for a later adapter design. This note was
written while the separate M9P no-fit preflight was running. It invokes no PMX
process, reads no new learner or evaluator data, and establishes no application
accuracy result.

The source is the accepted M9I artifact `m9i-embedded-source-34052517285`,
artifact ID 9994975626, from
[run 34052517285](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34052517285).
Its GitHub archive digest is
`26d16c1e9ad2a7606729143b50a306d9eed7f948dfd64b8cfe8b93cbcff7d4f6`.
The retained source manifest matched
`865789aedcfab3c62d77def985ed81187bbd57f946d2f4b32e902943457a0a1e`,
and all 25 source files matched the manifest-linked byte inventory. M9I and M9J
remain the authoritative execution evidence; this inspection does not rerun
their controls or revise their machine decisions.

## Concrete source constraints

| Boundary | Exact source behavior | Consequence for an application adapter |
|---|---|---|
| JSON envelope | `ReaderOpenTelemetry` consumes `TraceRecordOTLP.data`, with per-trace processes and spans. `SpanOTLP` describes the Jaeger-shaped model. | Convert the native OTLP resource/scope envelope explicitly; the bundle name does not imply acceptance of arbitrary OTLP JSON. Preserve trace/span IDs and references. |
| Time units | The reader converts span start and duration from nanoseconds to microseconds. | Declare input units and validate a known duration. Copying conventional Jaeger-shaped numeric values without checking their units is insufficient. |
| Tags | The retained model's tag values are strings. | Apply an explicit typed-value conversion; preserve the original native representation in an audit sidecar. |
| Trace admission | `checkTrace` requires at least one span passing `Util.checkSpan`, which checks the Spring-WebMVC library marker and excludes several named controller/handler patterns. | A native server-span selection policy must be specified and tested. An adapter-produced compatibility marker must be disclosed as adaptation, not claimed to be original application instrumentation. |
| Error preservation | Errors are detected before tree merging; M9I showed that a removed child's internal error marker is not propagated to its surviving carrier. | Validate carrier ownership and aggregation for the chosen operation boundaries. A recognized tag on any child is insufficient. |
| Host identity | `getExecutionContainerName` requires `host.name`, takes its value and appends a server suffix. | Supply observed or declared host identity with provenance. Replica identity and common-domain membership are distinct inputs. |
| Component/allocation identity | Component and assembly names derive from `serviceName`; allocation lookup uses that assembly-derived name. | Distinct processes sharing a service name are not automatically distinct deployed replicas. Audit the emitted instances before claiming replicated deployment recovery. |
| Operation identity | `resolveOperation` looks up the operation by its name alone before registering it with a component. | Check collisions across services. Any qualified naming rule must be deterministic and recorded before conversion. |
| Failure probability | The PCM transformer uses operation failure and success counts, with zero if failures are absent and one if successes are absent. | Freeze the denominator and zero-support interpretation. These are per-operation trace-derived counts; they are not automatically external semantic-request availability. |

The empty loop in `FailureEstimationService` does not invalidate the working
failure transformation: the observed execution path increments counts in
`TraceReconstructionService`, and the downstream PCM transformer consumes those
counts. M9J exercised that route. A source stub must not be used to claim that
the demonstrated functional-failure mechanism is absent.

The reconstruction source also contains unfinished network/failed-call mapping
comments. Those comments alone do not establish an ecosystem limitation. The
application contract must directly verify whether the particular produced PCM
captures the study's declared replication, common-domain events, repeated calls
and external checkout semantics.

## Bounded next design

A later adapter preregistration can use this recovered entrypoint and these
known source constraints. Its first conformance cases should exercise distinct
questions with independent expected structures:

1. A known span duration and parent/child relationship survive envelope and
   unit conversion.
2. Two services with the same local operation label remain distinct under the
   declared naming rule.
3. Two deployed replicas and their host/domain declarations remain distinguishable
   where the claimed model requires them.
4. Matched success/failure traces produce the specified operation-resolved
   counts after carrier merging, including a failing child and a successful
   sibling. The oracle resolves model references rather than stdout positions.
5. Missing spans, incomplete roots and a client timeout are retained as coverage
   cases instead of silently entering a success denominator.

The concrete mapping and expected outputs must be frozen before those cases
are executed. Passing them would qualify a measured adapter; it would not yet
establish prediction accuracy or lower automation cost. Natural-data fitting
must subsequently use only permitted learner trace IDs, with parameters and
predictions frozen before evaluator access. Span-error markers and external
semantic outcomes must remain separately identified; any use of the latter
to parameterize PMX is an additional input to be charged explicitly.

M9P retains all successful main native streams for 90 days to make this later
audit possible. Their retention neither admits raw streams into the temporal
learner job nor supplies an independently parameterized PMX comparison by
itself. The three M9O confirmation questions proceed under their existing
protocol regardless of this preparatory source inspection.
