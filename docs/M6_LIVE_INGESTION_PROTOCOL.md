# M6 versioned live-ingestion and benchmark-harness protocol

## Scope

M6 turns the article's data table into an executable boundary between a running
benchmark and the statistical learner. It does not run a reliability campaign
and does not count fixture records as live validation. M7 supplies independent
calibration/test measurements; M6 only establishes that such measurements can
be represented, audited, frozen, and passed to the later estimator without
silent completion.

The contract identifier is `taid.live_bundle`, version 1. Backward-incompatible
changes require a new version and adapter. A bundle contains an immutable
manifest, an external-request census, distributed traces, deployment/runtime
metadata, health/lifecycle records, network/mesh evidence, injection audit, and
an operation specification.

## Required sources and semantics

### External requests

Every initiated request is recorded independently of server-side telemetry.
Required fields are request id, optional trace id, start/completion time,
operation class, period (`calibration` or `test`), outcome, success, and timeout.
A failed or timed-out request with no root span is valid evidence and is never
dropped merely because no trace was exported.

### Distributed traces

M6 supports two input adapters:

- OTLP JSON resource/scope spans, used by the OpenTelemetry Demo profile;
- Jaeger JSON trace/process objects, used by the DeathStarBench profile.

Both normalize to trace/span/parent ids, service, instance, operation, start/end
time, status, and typed attributes. Missing downstream spans remain missing; an
adapter does not infer a network or component cause from absence alone.

### Deployment and health metadata

Deployment rows provide instance id, service, version, validity interval,
declared failure domain, and routing policy. Every span instance must map to
exactly one active deployment row at its timestamp. Health rows distinguish
`liveness`, `readiness`, and `restart`; state is `up`, `down`, or `unknown`.
Running/liveness is not relabelled as operation readiness.

### Mesh and injection audit

Mesh rows identify source, target, logical call, attempt, and transport outcome.
They help classify an observed interaction but do not turn a generic application
error into a network failure. Injection rows separately record intended,
applied, and independently verified times plus a confirmation flag. This keeps
the fault command distinct from realized unavailability.

### Operation specification

Operation classes and immediate/eventual semantics are explicit manual inputs.
Each specification declares its entry service, accepted external outcomes,
required effects, and conditional branch classes. Branch weights come from the
external request census or a declared target scenario, never only from successful
traces. M6 reports the number of manually supplied operations, effects, and
branch rules rather than calling them automatically discovered.

## Period integrity and leakage checks

The manifest declares disjoint UTC half-open calibration and test windows and a
separate workload, failure, and sampling seed for each. Every request belongs to
exactly its labelled window. No injection's verified interval may cross a period
boundary. M6 rejects duplicate request/span ids, unknown operation classes,
orphan trace ids, cyclic/missing parents within an exported trace, negative
durations, path traversal, digest mismatch, ambiguous deployment ownership, and
benchmark/commit disagreement.

The frozen profile additionally links every declared operation to a concrete
workload source path and a set of literal request/handler markers. The harness
checks those markers at the exact upstream commit. This establishes provenance
for the operation classes; it does not establish that the tiny fixture follows
the upstream runtime distribution.

Calibration and test are not made independent merely by labels. M7 must also use
fresh seeds and must not split a continuous incident. The contract checks these
observable prerequisites; it cannot prove causal independence.

## Audit output

Ingestion emits normalized CSV tables plus a JSON audit containing:

- external request count by period and operation, including failures/timeouts;
- root-trace coverage and the count of requests with no exported trace;
- exported traces not present in the request census;
- span-to-deployment mapping failures and declared domain/service counts;
- health state/signal counts and stale-health exposure;
- mesh logical-call/attempt counts;
- intended/applied/verified/confirmed injection counts;
- operation support, branch support, and manual-input counts;
- period, seed, digest, and structural-integrity checks.

The workflow fails only on contract violations. Low trace coverage, unknown
health, and missing optional mesh evidence are reported quality properties, not
silently repaired.

## Frozen benchmark profiles

M6 uses two independently maintained public test systems:

| Profile | Frozen upstream commit | Deployment/workload evidence |
|---|---|---|
| DeathStarBench Social Network | `6ecb09706140f8730b5385c08f1386c654c3c526` | Docker Compose plus compose-post and two timeline wrk2 scripts |
| OpenTelemetry Demo | `8c47d47c9ac27710d2b2a153bcd53e483bffe66d` | Compose, Locust load generator, and OTel Collector configuration |

The remote M6 workflow sparsely checks out each exact revision, verifies the
predeclared paths, Compose service names, and operation-specific workload
markers, ingests the matching adapter fixture twice, and uploads the normalized
bundle and audit. Fixture records are deliberately tiny contract examples. The
report must not call them measurements of either system.

## Quality gates and completion criterion

M6 is complete when both pinned profiles pass on GitHub Actions and the aggregate
artifact records:

- exact upstream and implementation commits;
- zero schema, digest, time-window, identity, parent-graph, deployment-map, and
  cross-period incident failures;
- preservation of untraced external failures;
- successful normalization by both trace adapters;
- deterministic re-ingestion of the fixture bundles;
- explicit manual-input and telemetry-coverage counts.

No availability accuracy, coverage, transfer, or failure-injection claim follows
from M6. Those require the frozen live campaigns in M7.
