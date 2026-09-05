# M7B replicated-placement and operation-semantics pilot protocol

## Purpose and exclusion from effectiveness evidence

M7B is a disposable engineering pilot between the accepted single-replica M7A
diagnostic and the frozen M7 study. It asks whether a placement change can be
implemented as a real change in which running replica containers survive one
logical-domain intervention, rather than as a relabelling of identical data. It
also freezes executable operation-success predicates before any M7 test period.

M7B estimates no availability model, compares no B0--B4 method, and provides no
input to the later estimators. Its regular four-event schedule and forced trace
sampling are diagnostic. No request-success difference between placements is an
acceptance criterion, and no such difference may be reported as transfer
effectiveness. Only routing, semantics, acquisition, intervention, and cleanup
mechanics may be repaired after this pilot.

## Four-cell matrix and exact extension

The matrix is two applications by two placements, one independent GitHub job per
cell. The exact benchmark commits, application images, disabled OTel generator,
initialization, telemetry receivers, and 30-second stabilization are inherited
from accepted M7A.

For each application, the pinned Compose definition of one key service is
replaced by two separately named containers running the same digest-locked image
and one explicit HAProxy endpoint retaining the original service name and port.
DeathStarBench replicates `user-timeline-service` behind a TCP proxy on port
9090. OTel Demo replicates `product-catalog` behind an h2-aware HTTP proxy on
port 3550. HAProxy `3.0-alpine` is locked to the configured multi-platform
manifest digest. The generated proxy configuration and extended image audit are
retained and hashed.

The two placements are:

| Placement | Replica a | Replica b | Domain-a intervention |
|---|---|---|---|
| co-located | domain a | domain a | pauses both containers |
| split | domain a | domain b | pauses only replica a |

The two domains are controlled logical domains on one GitHub-hosted machine;
they are not presented as independent physical hosts. The application callers
continue to address the original service name, which now resolves only to the
proxy. Replica labels, hostnames, trace resource attributes where supported, and
the placement audit make the actual container mapping explicit.

## Routing proof

Before fault traffic, 48 concurrent requests exercise the operation that must
traverse the replicated service: user-timeline read in DeathStarBench and product
browse in OTel Demo. HAProxy CSV statistics are captured immediately before and
after. Both named backends must be `UP`, each must receive at least one new
session, and at least 90% of routing-probe responses must pass the operation's
semantic predicate. This checks actual traffic use rather than inferring it from
the presence of two Compose services.

The routing burst is an integration probe, not the main workload distribution.
Its rows remain in the M7B namespace only.

## Executable operation semantics

One sentinel of every selected operation must pass both HTTP and content rules
before the fault period:

- DeathStarBench compose-post requires the exact acknowledgement. Nonempty
  timeline reads require a JSON array with the declared post fields; the exact
  empty object `{}` is also accepted because the pinned upstream Lua endpoint
  serializes an empty Lua table in that form. Arbitrary JSON objects are still
  rejected. The counted home-timeline read uses follower 1, who follows author
  0, rather than reading the author's normally empty home timeline. In addition,
  the sentinel post must eventually appear in the owner's user timeline and the
  follower's home timeline. This eventual fan-out audit is stored separately;
  later immediate availability must not silently claim eventual completion.
- OTel product browse requires the selected product id; add-to-cart requires the
  returned cart to contain that product with positive quantity; checkout
  requires nonempty order and shipping-tracking identifiers. These are frozen
  synchronous response predicates, not claims about later email delivery.

Every response body is retained losslessly with its request id and SHA-256.
`immediate_success` and `semantic_success` are separate fields. A malformed HTTP
2xx therefore cannot count as an operation success.

## Placement intervention period

The 40-second period schedules 160 external attempts at four per second with a
deterministically shuffled, near-balanced operation sequence. A one-second
auditor samples the two replica containers and the proxy. Four non-overlapping
three-second events start at seconds 4, 12, 20, and 28:

1. pause replica a;
2. pause replica b;
3. pause every replica assigned to domain a;
4. disconnect the proxy from its only application network.

Docker state verifies each application and restoration. Original proxy network
aliases are restored. After the request period a five-second recovery window is
followed by a final audit requiring both replicas and the proxy to be running,
unpaused, attached to one network, and visible as `UP` backends.

The controller schedule is never learner evidence in M7. M7B has no learner at
all. Fault-period success counts are retained only to diagnose whether the
extended application continued to execute; they cannot pass or fail a cell.

## Trace and evidence contract

As in M7A, each counted request receives a deterministic sampled trace context.
The complete external census exists independently of native telemetry. Raw
Jaeger JSON or the lossless mounted OTel Collector JSON-lines stream is retained,
and a join table records every assigned id. At least 80% of semantically
successful requests must be linked. This remains a forced-sampling transport
test rather than an estimate of natural trace coverage.

Every job uploads the base rendered and pinned Compose documents, extended
Compose and image audit, HAProxy configuration, all requests and exact responses,
routing statistics, semantic/effect audit, health series, intervention audit,
trace join, raw telemetry, final state, runtime inventory, runner details,
service logs, and resource snapshot even on failure.

## Technical acceptance and next decision

A cell is usable only when exact commits and all running image locks match; the
extended placement audit matches the requested cell; every expected request and
operation is retained; all sentinels and the DeathStarBench eventual audit pass;
both proxy backends serve routing traffic; all four interventions have the exact
placement-dependent targets and are verified/restored; health support is at
least 30 observations per replica/proxy; trace linkage is at least 80%; and the
final state is clean. The aggregate requires all four unique usable cells.

A successful M7B permits freezing M7's stochastic schedule and placement matrix.
It cannot establish that replication improves availability, that HAProxy models
every production routing policy, or that logical Docker domains behave like
physical infrastructure. A failed pilot triggers an auditable infrastructure or
semantic-contract repair and a full repeat without weakening these thresholds.
