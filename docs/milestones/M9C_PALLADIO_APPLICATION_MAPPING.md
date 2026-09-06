# M9C: source-grounded Palladio application mapping

## Outcome

M9C is complete. A byte-audited 16-row correspondence table now maps the eight
mandatory concerns for one preselected operation in each application. Four PCM
instances implement the two application templates under colocated and split
logical domains. The pinned Palladio reliability analyzer solved every instance
twice and matched all predeclared structural-witness probabilities within
floating-point precision.

This establishes a checked path from the retained M7 application evidence to a
specific, explicit PCM abstraction. It does not establish predictive accuracy:
M9C uses no M7 fitted parameter, prediction, score, or test outcome. The next
milestone may perform an explicitly exploratory comparison on aligned preserved
inputs.

The M7 interpretation remains unchanged. Its published calculations establish
no predictive gain and disagree with observations; the causes remain
insufficiently diagnosed for an overall success/failure verdict.

## Frozen design and implementation history

The protocol, numeric witnesses, independent formulas, source selection, and
acceptance rules were committed before the first solver output:

- preregistration and implementation:
  [`57aa408a19146fd68f9ac1b0e80344dcfc17f1ed`](https://github.com/a-a-k/telemetry-availability-identification/commit/57aa408a19146fd68f9ac1b0e80344dcfc17f1ed);
- accepted evidence-wiring correction:
  [`45539a33f4b150cb961981dbcd27c55427cf3cf4`](https://github.com/a-a-k/telemetry-availability-identification/commit/45539a33f4b150cb961981dbcd27c55427cf3cf4);
- accepted M9C workflow:
  [run 34026488176](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34026488176);
- matching Python 3.11/3.13 CI:
  [run 34026480758](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34026480758).

The first workflow attempt,
[run 34026391347](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34026391347),
was rejected before model generation and before any Palladio execution. The
source-evidence audit found that two semantic-response markers had been assigned
to `live_pilot.py`, while their definitions are in
`live_placement_pilot.py`. Commit `45539a3` corrected only that provenance
wiring and added a unit test that verifies every frozen study marker against
its byte-locked file. It did not change the operation selection, model,
parameters, formulas, or acceptance thresholds.

All full work ran remotely. Local checks were limited to JSON/CLI validation,
static XML generation and parsing, source-marker hashing, and unit tests. All
three workflow jobs used `timeout-minutes: 360`.

## Evidence correspondence

The selected operations were fixed by M7B as routing probes, independently of
Palladio output and accuracy:

| Application | Operation | Entry | Replicated target | Protocol |
|---|---|---|---|---|
| DeathStarBench Social Network | `read_user_timeline` | `nginx-web-server` | `user-timeline-service:9090` | TCP/Thrift behind HAProxy |
| OpenTelemetry Demo | `browse_product` | `frontend` | `product-catalog:3550` | gRPC h2 behind HAProxy |

The accepted evidence job verified the exact M8B artifact, six study files, and
ten upstream source files at the original application commits. Source inspection
shows a synchronous mandatory target call for both fixed driver requests. It
also shows why a one-node target is not being presented as the entire
application:

- DeathStarBench enters through nginx, calls UserTimelineService, uses a
  Redis/Mongo conditional path, and calls PostStorageService;
- OTel Demo enters through frontend and calls ProductCatalog.GetProduct; the
  fixed default USD path avoids a Currency call, while product-catalog still
  includes feature-flag and PostgreSQL behavior.

Those internal mechanisms and all other non-target causes are explicitly
collapsed into an operation-level semantic residual. The residual is a model
boundary, not a claim that the dependencies do not exist or that their causes
were recovered.

### Retained topology facts

For the full M8B view, N and ND provide unambiguous structural support for the
selected calls:

| Application/operation | N/ND rows | Confirmed | Successful-trace support | Replica A assignments | Replica B assignments | Target fraction |
|---|---:|---:|---:|---:|---:|---:|
| DeathStarBench / `read_user_timeline` | 40 | 40 | 45,624 | 23,177 | 22,447 | 1.0 |
| OTel Demo / `browse_product` | 40 | 40 | 44,806 | 22,302 | 22,504 | 1.0 |

Communication-fault data retain an unresolved discrepancy rather than being
silently promoted to structural truth:

| Application/operation | NC/NCD rows | Confirmed | Ambiguous | Trace support | With target | Without target |
|---|---:|---:|---:|---:|---:|---:|
| DeathStarBench / `read_user_timeline` | 40 | 25 | 15 | 43,401 | 81,317 across branch table | 7,708 across branch table |
| OTel Demo / `browse_product` | 40 | 14 | 26 | 42,294 | 71,514 across branch table | 15,586 across branch table |

Every selected operation has retained target-present and target-absent examples,
and assignments to both replicas. Because the pinned source requires the call
for these inputs, the PCM template uses a mandatory target path while recording
the successful target-absent traces as unresolved evidence consistent with
partial span delivery or another as-yet-unidentified mechanism. M9C does not
claim to have resolved that M8B ambiguity.

## PCM abstraction

Each application template contains:

- one operation-boundary/router component with a single semantic-residual
  InternalAction;
- two distinct target-replica components, required roles, assembly contexts,
  allocation contexts, resource containers, and communication links;
- a RecoveryAction whose alternate path handles both CPU-unavailability and
  network-induced failure types;
- one usage scenario named for the frozen application operation;
- no duplicate allocation contexts masquerading as native replication.

The HAProxy configuration uses health-checked round robin. In a stable binary
backend state, request success requires at least one complete path. The PCM
primary/fallback sequence encodes that stationary Boolean-OR success condition;
it is not claimed to reproduce literal round-robin ordering or to prove that
HAProxy retries an arbitrary failed request.

For colocated replicas, one shared required resource gates both paths. For split
placement, independent domain availability is composed into each path resource.
This matches the predeclared logical fault-domain semantics. It does not claim
physical host separation: all M7 containers shared the CI host, and the proxy
was outside the injected replica domains.

The M7 communication intervention is an interval-long Docker-network
disconnection. The pinned analyzer instead applies link failure independently
to request and response message transfers. M9C uses
`q_pcm = 1 - sqrt(c_path)` so that the two-transfer call has marginal success
`c_path`. This is exact for the one-request witness under the stated equal,
independent transfer assumption, but does not reproduce outage duration or
temporal correlation.

PCM receives dimensionless `MTTF=A`, `MTTR=1-A` coordinates to realize
stationary availability `A`. They are not estimates of failure and repair
times. Separate MTTF and MTTR remain unidentified by one availability and would
require a censoring-aware duration analysis for any temporal claim.

## Predeclared witness and accepted results

Both applications use the same non-empirical witness, preventing an
application-specific fit from entering this milestone:

- residual success `r=0.97`;
- common-domain availability `g=0.90`;
- individual availability `e_a=0.80`, `e_b=0.70`;
- communication call success `c_a=0.90`, `c_b=0.85`.

The independent formulas frozen in the protocol are:

- colocated route:
  `g * [e_a*c_a + (1-e_a*c_a)*e_b*c_b]`;
- split route:
  `g*e_a*c_a + (1-g*e_a*c_a)*g*e_b*c_b`;
- operation success: `r * route`.

The Java harness did not contain expected values. A downstream Python job
compared its raw records to the frozen JSON:

| Application | Placement | Physical states | Oracle | Palladio run 1 | Palladio run 2 |
|---|---|---:|---:|---:|---:|
| DeathStarBench | colocated | 8 | 0.774001800000 | 0.774001800000 | 0.774001800000 |
| DeathStarBench | split | 4 | 0.811401120000 | 0.811401120000 | 0.811401120000 |
| OTel Demo | colocated | 8 | 0.774001800000 | 0.774001800000 | 0.774001800000 |
| OTel Demo | split | 4 | 0.811401120000 | 0.811401120000 | 0.811401120000 |

Across eight raw records:

- maximum oracle error: `1.1102230246251565e-16`;
- maximum success-plus-failure residual:
  `1.1102230246251565e-16`;
- maximum physical-state mass residual: `0`;
- maximum technical-repeat delta: `0`;
- every expected physical state was evaluated.

The split witness is higher because independent logical domain factors leave a
larger probability that at least one complete path is available. This is a
property of the declared witness and dependence structure, not an empirical
claim that split M7 deployment improved availability.

## Artifacts and resources

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m9c-palladio-contract-34026488176` | 9987214676 | 1,160,392 | `f9e5ab7f5a63696241222b91ba4f7660c7de30bb5fd49b875711988e92cc3ed8` | 2026-12-05 |
| `m9c-palladio-application-models-34026488176` | 9987264993 | 82,562 | `30e9ce5926f8d826f6ea91b0f84b4ce6841bdc44e1e631abfa48652de6434e6c` | 2026-12-05 |
| `m9c-palladio-acceptance-34026488176` | 9987270345 | 2,612 | `1585d3ed0cc66466b4faf4a0d017cdbb156ec27b7bb1f10c0f5f3255e3c2a227` | 2026-12-05 |

The contract artifact retains the accepted M8B tables, GitHub artifact
metadata, all ten pinned upstream files, the correspondence CSV, generated XMI,
and independent audits. The solver artifact retains target-lock evidence,
capability audit, raw results, complete build log, test reports, and resource
measurements.

| Measured command | Wall time | Maximum RSS |
|---|---:|---:|
| M8B/source correspondence audit | 0.79 s | 110,132 KiB |
| PCM generation plus structural audit | 1.54 s | 106,688 KiB |
| Palladio clean build and eight solves | 2 min 51.69 s | 1,867,864 KiB |
| Acceptance audit | 0.98 s | 108,196 KiB |

These measurements include different work boundaries and must not be used as a
method-runtime comparison. The Palladio command includes a clean Maven/Tycho
build; later comparison timing must separate setup, model preparation, warm
solver execution, and end-to-end cost.

## Interpretation and next step

M9C removes two potential straw-man constructions from the next comparison:
it does not use one allocation context twice despite the analyzer's unsupported
replication path, and it does not treat a raw link probability as a one-call
failure probability. It also records the actual operation success predicates,
source-visible dependencies, logical placement meaning, and every collapsed or
unsupported part.

What is established is narrower: for these two operation boundaries, the
explicit PCM encoding implements the same predeclared stationary probability
model as the independent oracle. Application accuracy, adequacy of the residual
factorization, temporal behavior, and comparative model-construction cost are
still open.

The next admissible milestone is M9D: an exploratory aligned-input debugging
comparison using preserved calibration evidence. It must keep fixed M7
estimators unchanged, use the same operation semantics and parameter evidence
for Palladio, report abstentions and unsupported mappings, and distinguish
algebraic agreement from agreement with held-out requests. No new live
collection is justified before that diagnostic comparison.

## Completion checks

- The mapping protocol and all numeric witnesses preceded solver output.
- The accepted run used commit `45539a3` and three 360-minute jobs.
- Accepted M8B identity and every selected source/study file passed its lock.
- The correspondence table contains 16/16 required rows.
- Four model instances contain distinct explicit replica paths and no native
  replication claim.
- Eight solver records match their external oracles and conserve all mass.
- The rejected pre-solver attempt and its exact correction are retained.
- No M7 prediction, score, test outcome, or fitted parameter entered M9C.
- The unresolved-cause M7 interpretation is preserved.
