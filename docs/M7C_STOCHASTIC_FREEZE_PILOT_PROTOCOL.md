# M7C stochastic-schedule and repetition-budget freeze pilot protocol

## Purpose and strict exclusion

M7C is the last disposable live pilot before M7. It replaces the regular M7A
and M7B diagnostic grids with independent stochastic failure processes and uses
a predeclared rule to select the M7 period duration, independent-pair budget,
and transition guard. It also tests whether overlapping primitive failures can
be applied, observed, released, and cleaned up on the replicated applications.

M7C does not fit the proposed model or B0--B4, estimate a placement benefit, or
test an effectiveness hypothesis. Its calibration and test labels identify two
independent process realizations only. Every request, trace, success fraction,
and schedule from M7C is permanently excluded from M7 estimation, validation,
and method comparison. Pilot outcomes may select only the three design
quantities named above by the frozen rules below.

## Matrix, unit of repetition, and resource scale

The matrix is:

- two pinned applications: DeathStarBench Social Network and OTel Demo;
- two M7B placements: two replicas in one logical domain and one replica in
  each of two logical domains;
- four failure laws: N, NC, ND, and NCD;
- four independently provisioned pilot repetitions;
- one fresh GitHub-hosted runner and application deployment per cell.

This yields 64 pilot cells. One cell contains a 60-second no-injection baseline
and independent 300-second calibration and test periods, with ten seconds for
complete recovery between stochastic periods. At four requests per second it
retains 2,640 counted baseline/period requests plus three semantic sentinels.
The matrix therefore schedules 168,960 counted requests and 192 sentinels over
approximately 704 fault/baseline runner-minutes before startup, stabilization,
trace flushing, and cleanup. Requests within a state episode are not treated as
independent repetitions; the fresh campaign pair is the planning unit.

The four pilot pairs per substantive cell are deliberately not added to the
later M7 repetition count. Pilot and main base seeds differ. Calibration, test,
workload, factor, application, placement, law, and repetition all enter the
stable seed derivation.

Before spending the full matrix budget, the same workflow may be dispatched in
`smoke` scope. That scope runs only split/NCD/repetition 0 for both applications,
whose frozen schedules contain same-replica overlap between pause and network
effects. It disables aggregation and can establish controller operability only;
its artifacts are diagnostic and cannot satisfy, replace, or be pooled with any
of the 64 cells in the subsequent `full` dispatch.

## Executable stochastic failure process

Each primitive factor follows its own alternating renewal process. Starting
from up, its next up duration is

`minimum_up + Exponential(mean_up - minimum_up)`

and its down duration is sampled uniformly between the declared minimum and
maximum. A new up interval for that factor starts after its preceding down
interval ends. Different factors have independent derived seeds and may
overlap. Events ending too near a period boundary are omitted so at least two
ordinary health-audit ticks remain after release. The exact planned schedule is
written before runtime actions.

| Mechanism | Minimum/mean up (s) | Down range (s) | Primitive factors |
|---|---:|---:|---|
| Individual | 12 / 35 | 5--9 | replica a; replica b |
| Communication | 20 / 55 | 4--8 | proxy-to-a backend path; proxy-to-b backend path |
| Common domain | 30 / 75 | 6--10 | one process per distinct domain in the placement |

Individual and common-domain events pause actual replica containers.
Communication events disconnect the selected replica, not the whole proxy,
from its only application network; this exercises a backend-specific residual
path while leaving HAProxy able to route to the alternative replica. In the
co-located placement the one domain event affects both replicas. In the split
placement independent domain-a and domain-b processes each affect one replica.

N enables the two individual factors. NC adds both communication factors. ND
adds every domain factor. NCD enables all applicable factors. The marginal
renewal specification for a mechanism is identical across applications and
placements; a split placement has two independent domain processes rather than
silently changing their per-domain distribution.

## Overlap-safe controller and independent observation

A single transition controller maintains a set of active causes per physical
effect and replica. Ending one event cannot unpause or reconnect a target still
covered by another active cause. Every transition reconciles desired and
observed Docker state, records controller time, verifies application, and at
release verifies the state implied by the remaining causes. The period ends
only after all cause sets are empty. A later boundary audit requires both
replicas and the proxy to be running, unpaused, on exactly one network, with
both HAProxy backends `UP`.

An independent one-second sampler records Docker running, paused, health, and
network state for both replicas and the proxy. It also records HAProxy backend
status, check state, and cumulative sessions. Event start and release must each
be visible in this ordinary series; their observed lags are retained. At least
85% of nominal service observations must be present for every baseline or
stochastic period. Controller intent and its privileged schedule are never
substituted for the state audit.

## Workload and semantics

The M7B content predicates remain frozen. DeathStarBench uses compose post,
follower home-timeline read, and author user-timeline read; exact acknowledgement
and valid wire content are required, and the sentinel post must reach both the
owner and follower timelines. OTel uses product browse, add to cart, and
checkout; the selected product, positive cart item, and nonempty order/tracking
identifiers are required. Each period contains a deterministically shuffled,
near-balanced operation sequence. Exact response bytes and SHA-256 are retained.

The 60-second no-fault baseline must achieve at least 98% semantic success. This
is a saturation/application-health guard, not an estimator. No calibration or
test success fraction under injected failures is a technical acceptance gate.
HAProxy session deltas over the whole cell must show traffic on both named
backends.

Every request, including timeout, driver error, and malformed HTTP 2xx, is
retained in an external census. All requests carry deterministic forced-sampled
native trace contexts for this transport pilot. The Jaeger query bound is raised
from 1,000 to 10,000 traces and its lookback from one to two hours to cover the
declared pilot and candidate main cells; OTel continues to use its lossless
mounted collector file. At least 80% of semantic successes must
join to raw telemetry. This is not an estimate of natural production sampling.

## Frozen duration-selection rule

Candidate M7 period durations are 900, 1,200, and 1,800 seconds, corresponding
to 30-, 40-, and 60-minute calibration--test pairs before recovery. The rule
selects the smallest candidate satisfying both conditions:

1. Using the separate M7 seed and all schedules for the largest candidate
   repetition budget, at least 90% of primitive-factor periods contain at least
   eight complete events, and the tenth percentile within every
   application--placement--law--factor stratum is also at least eight.
2. Dividing the duration by the 90th percentile pilot block length gives at
   least 30 effective temporal blocks. For each pilot period, block length is
   the larger decorrelation length of one-second semantic request success and
   independently observed replica impairment. Decorrelation requires three
   consecutive absolute autocorrelations no greater than 0.10, searched to 120
   seconds.

Future main schedules are generated for this calculation before any M7 outcome
exists. The rule uses M7C state dependence to avoid treating requests as
independent, but it never uses a proposed-method error, B0--B4 comparison, or
placement-effect estimate.

## Frozen repetition-selection rule

For each application--placement--law cell, the four pilot values are the raw
test-minus-calibration semantic endpoint-rate differences. Their sample standard
deviation is inflated to a one-sided 90% chi-square upper confidence bound and
then lower-bounded by 0.015. For candidate independent-pair counts 10, 15, 20,
30, and 40, a two-sided 95% Student-t half-width is projected using the worst
cell's planning standard deviation. The smallest count with half-width at most
0.015 is selected.

This quantity budgets campaign-to-campaign endpoint variability. It is not a
power calculation for the future full-method-minus-B2 error contrast and cannot
be presented as one. M7 must retain paired campaign analysis, report all effect
intervals, and avoid optional stopping regardless of the selected count.

## Frozen transition rule

The empirical 95th percentile across all independently observed event-start and
release lags is compared with candidate symmetric guards of 1, 2, 3, 5, and 8
seconds. The smallest guard not shorter than that quantile is selected. M7 will
retain the full series and report a sensitivity analysis including transitions;
the guard defines only the primary stable-interval view.

## Acceptance and stopping rule

A cell is technically usable only if exact commits, extended placement, image
locks, runtime inventory, request census, operation balance, seeds, sentinels,
event schedule, overlap-safe applications/releases, ordinary transition
observations, health support, routing, trace linkage, period boundaries, and
final cleanup all pass. Fault-period success counts cannot fail a cell. The
aggregate requires all 64 unique cells and globally unique request and trace ids.

The aggregate writes cell, period, and factor-yield tables plus a machine-readable
recommendation and hash of the selected M7 design. If any of the three candidate
sets has no admissible value, M7 is not frozen and the workflow fails while
retaining all evidence. The permissible response is to broaden the resource
budget or narrow a predeclared claim/scenario, document that change, and rerun
the complete pilot analysis. It is not permissible to weaken a criterion after
looking for a desired method or placement result.

## Interpretation boundary

Passing M7C would show that this runner-level implementation can generate and
audit enough independent stochastic factor episodes to pre-fix a live-study
budget. It would not validate the factor model, physical-domain independence,
stationarity, transferability, or estimator accuracy. Both logical domains
still share a kernel and host. Controlled renewal failures intentionally improve
event support and are not claimed to reproduce an operational incident process.
Those limitations remain explicit targets for M7 diagnostics and directed
stress analysis.
