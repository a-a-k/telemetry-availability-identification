# M7A fault-control and request--trace linkage diagnostic protocol

## Purpose and exclusion from effectiveness evidence

M7A is the last disposable acquisition diagnostic before the M7 live protocol is
frozen. M7P showed that two application revisions and their native telemetry
paths run. M7A asks three narrower engineering questions that M7P did not answer:

1. can every externally counted logical attempt carry a deterministic trace id
   that is recoverable from native telemetry without deleting untraced failures;
2. can individual-container, communication-only, and grouped logical-domain
   interventions be applied, independently verified, and fully restored; and
3. can calibration and test-labelled periods use distinct schedules with no
   intervention crossing their boundary?

M7A estimates no model, compares no method, chooses no favourable failure law,
and contributes no request, trace, health sample, or intervention to M7. Its
forced trace sampling also differs from a natural production sampling policy.
The only permitted response to its outcomes is to repair acquisition mechanics,
fix the future duration/resource budget, and repeat this diagnostic before
freezing M7. Technical thresholds cannot be weakened after a failed run.

## Frozen matrix and revisions

The diagnostic contains eight independent GitHub jobs: two applications by four
failure laws, with one calibration--test pair per job.

| Law | Applied mechanisms |
|---|---|
| N | one service container paused |
| NC | individual pause plus network disconnect of the same named service |
| ND | individual pause plus simultaneous pause of a declared two-service group |
| NCD | all three mechanisms |

The exact source commits, image manifest digests, disabled OTel upstream
generator, 30-second post-start stabilization, operation classes, and native
telemetry transports are inherited from the accepted M7P configuration. The
DeathStarBench targets are `user-timeline-service` individually and together
with `home-timeline-service` as a logical domain. OTel Demo targets
`product-catalog` individually and together with `cart` as a logical domain.

All containers within a job share one GitHub-hosted machine. A grouped pause is
therefore a controlled *logical* failure domain, not evidence about independent
physical hosts. A Docker network disconnect keeps the target container running
and is classified as a communication intervention; it is not a claim to emulate
every packet-loss process.

## Period, workload, and schedule

Each period lasts 30 seconds and schedules exactly four external logical attempts
per second, for 120 attempts and 40 expected attempts per operation. Sixteen
workers prevent a two-second request timeout from serializing later scheduled
attempts. Operation order is a deterministic shuffle under the period seed.
Calibration and test use disjoint workload and fault seeds. After calibration,
the controller restores all resources, joins every worker, and waits five
seconds before test.

Interventions last three seconds. The first starts near second 5 and later
events are eight seconds apart, with deterministic seed-derived jitter bounded
by 0.5 seconds. The mechanism order is independently shuffled and cycled, so a
30-second NCD period contains one complete event of each type. Injector intent,
application time, verification, restoration, and errors are recorded separately.
No external success or failure count is a build gate.

The operation implementation is the accepted M7P external client. OTel cart and
checkout attempts retain their prerequisite calls as part of one logical
attempt. HTTP 2xx is the diagnostic immediate-success definition; M7 must freeze
additional eventual-effect checks before using live outcomes substantively.

## Trace identity and census

Every logical attempt receives a deterministic id derived from application,
law, repetition, period, and scheduled index. OTel uses a 128-bit W3C
`traceparent`; DeathStarBench uses a sampled 64-bit `uber-trace-id`, matching its
legacy Jaeger instrumentation. Multiple HTTP calls inside one OTel logical
attempt share the same absent external parent and therefore one trace id.

The independent request census is written before trace matching. After a
15-second flush, raw Jaeger API JSON or the OTel Collector's mounted OTLP/JSON
lines file-exporter stream is saved unaltered. The OTel debug exporter remains
available for service diagnostics, but its size-rotated Docker log is not the
request--trace linkage source. A separate join table records whether each
planned trace id appears.
A failed or timed-out request is retained even when its id is absent. At least
80% of HTTP-successful attempts must be linkable; this is a transport feasibility
threshold, not a claim about natural trace coverage.

The first eight-cell attempt disclosed that the upstream OTel Compose rotates
the collector's debug log at 5 MiB. All four OTel cells consequently lost early
records while all four DeathStarBench cells passed. Before the repeat, and
without inspecting any estimator result (none exists in M7A), acquisition was
repaired by adding the lossless mounted sink above. Workload, faults, seeds,
matrix, and the 80% threshold remain unchanged; both attempts are retained in
the milestone report.

## Independent health and intervention audit

A one-second sampler repeatedly inspects the two declared target containers. It
records running, paused, and Docker health state independently of the controller's
intent log. The injector verifies a pause from `State.Paused`, verifies a network
event by absence from the pre-recorded Docker network, and verifies restoration
after every event. Original service aliases are restored on reconnection.

These Docker observations are an acquisition auditor. The future learner must
receive only sources enumerated by the M7 protocol; intervention intent cannot
be silently passed in as a recovered latent state.

## Technical acceptance criteria

A diagnostic cell is usable only when:

- upstream `HEAD`, rendered/running image locks, and active container counts
  agree with the frozen configuration;
- both periods retain exactly 120 unique external attempts and all three
  operations are present;
- period workload and fault seeds are distinct;
- the planned number and mechanisms of interventions are recorded, every event
  is independently verified, and every target is restored;
- every target service has at least 20 independent health samples per period;
- at least 80% of HTTP-successful attempts are found in native telemetry;
- request, health, intervention, join, raw telemetry, runtime inventory, Compose
  state, service logs, and runner diagnostics are uploaded even on failure.

The aggregate requires all eight unique cells. It may fail on missing or invalid
evidence, but never on whether an intervention happened to cause a request
failure. A successful diagnostic establishes acquisition feasibility only.

## Interpretation boundary and next decision

M7A cannot estimate availability, diagnostic power, coverage, or the causal
effect of a fault class from one short pair. The regular event grid with jitter
is an integration workload, not the final stochastic law. Forced sampling can
alter overhead. Container pause and network membership are exact Docker states,
not independent observations of hardware failure. Period labels alone do not
create iid samples.

Only after all cells pass will M7 freeze its longer failure law, number of
campaigns, operation semantics, learner-visible evidence, block-length rule,
B0--B4 estimators, noisy-test comparison, and exclusion policy. M7A outputs stay
in a separately named artifact namespace and are never pooled with those runs.
