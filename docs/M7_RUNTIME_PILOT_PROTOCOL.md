# M7P runtime-feasibility pilot protocol

## Purpose and separation from the main experiment

M7P is a disposable infrastructure pilot between the completed ingestion harness
and the frozen M7 live study. It asks whether the exact benchmark revisions and
container images can run on GitHub-hosted Linux, whether the six predeclared
operations can be invoked by an independent client, and whether each native
telemetry path emits nonempty raw trace evidence.

The pilot estimates no availability parameter, compares no method, selects no
favourable fault regime, and contributes no request or trace to the article's
effectiveness results. Its only allowed consequences are: keep the planned M7
instrumentation if technically usable, or repair/document it and repeat the
pilot before freezing M7. Main-run sample size, fault laws, and acceptance rules
must be declared separately before reading main test outcomes.

## Frozen inputs

The source revisions and operation classes are those already verified in M6:

- DeathStarBench Social Network at
  `6ecb09706140f8730b5385c08f1386c654c3c526`, using compose-post,
  read-home-timeline, and read-user-timeline;
- OpenTelemetry Demo at
  `8c47d47c9ac27710d2b2a153bcd53e483bffe66d`, using browse-product,
  add-to-cart, and checkout.

Every Compose image is locked by OCI/Docker manifest digest in
`configs/m7_runtime_pilot.yaml`. The DeathStarBench upstream uses mutable
`latest` tags; M7P replaces them after rendering Compose. OTel Demo is rendered
with `DEMO_VERSION=3.0.0`, then every application and dependency image is also
replaced by its recorded digest. The workflow removes build directives and
fails if any rendered service image lacks a lock.

## Workload and periods

There is one pilot pair per application. Each half executes 20 sequential
external-client attempts for each of the three operations, for 120 counted
attempts per application. Calibration and test labels are disjoint and separated
by two seconds, with different deterministic workload seeds. They exercise the
period machinery but are not statistical replicates.

The client records every initiated request, HTTP/transport outcome, start/end
time, operation, and period. A DeathStarBench user is registered before counted
traffic. OTel checkout creates and fills a distinct cart before submitting the
order. Success in this pilot means HTTP 2xx; eventual application effects are not
audited and therefore no semantic availability conclusion is allowed.

No fault is injected. This isolates deployment, operation, and trace-export
failures before the fault controller is introduced. A no-fault pilot is not the
N/NC/ND/NCD live matrix and is not its control group.

## Native telemetry checks

- DeathStarBench retains its Jaeger agent/all-in-one path and probabilistic
  sampler. After a 15-second flush, the workflow saves the unmodified Jaeger API
  response for service `nginx-web-server`.
- OTel Demo retains its OTLP collector path. Its existing debug exporter is set
  to detailed verbosity through the supported extra configuration, and the raw
  collector log is saved after the same flush interval.

The pilot does not join a trace to a particular census row. That exact join and
the normalized M6 bundle are requirements of the subsequent M7 protocol.

## Predeclared technical acceptance criteria

A profile is usable only if all of the following hold:

1. the checked-out source `HEAD` equals the configured commit;
2. all rendered images are digest-locked and the running image identifiers are
   recorded;
3. the frontend becomes reachable within 360 seconds;
4. all 120 client attempts are retained and at least 95% return HTTP 2xx;
5. raw native telemetry contains at least six exported traces;
6. request, trace, image-lock, Compose-state, and container-log artifacts are
   uploaded even when a check fails.

Six traces is only a nonempty-path check, not an acceptable coverage level for
M7. The aggregate job requires both profiles; it reports results but cannot turn
pilot traffic into main evidence.

## Interpretation rules

Passing M7P supports only runtime feasibility of the selected revisions on the
ephemeral runner. Failing M7P identifies an infrastructure incompatibility and
is not evidence for or against the statistical method. High pilot success says
nothing about behavior under injected failures. A trace count is not an
independent sample size. GitHub-hosted containers share one physical machine, so
future declared failure domains must be described as controlled logical fault
groups unless independently provisioned hosts are used.
