# M7D: learner/evaluator evidence-boundary qualification

## Outcome

M7D is complete as a diagnostic anti-leakage milestone. All 64 M7C schemas were
converted into physically separated learner, evaluator, and audit bundles. The
accepted aggregate contains 76,800 calibration requests and 76,800 sequestered
test requests with no request-id overlap, 19,216 calibration health ticks,
19,211 sequestered test health ticks, and 864 trace-discovered service edges.
Every cell passed and every calibration request had parsed native trace support.

The learner never receives the exact fault schedule, event/cause identifiers,
controller transition timestamps, cleanup record, final controller state, or
test outcomes. M7D fits no model and computes no effectiveness metric; all of
its source requests remain excluded from M7.

## Frozen implementation and evidence

- initial executable boundary commit:
  `dab71c3a6e64546cc0ae5c873a27317fa969e08d`;
- accepted tail-classification and tested commit:
  `63a48e57eb12898d5bc4f9706c38941b4d6dd86a`;
- accepted CI:
  [run 33982119303](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33982119303),
  successful on Python 3.11 and 3.13;
- first complete qualification:
  [run 33981034409](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33981034409),
  retained and failed on three over-classified OTel tail fragments;
- accepted complete qualification:
  [run 33982131486](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33982131486),
  successful;
- immutable source evidence: M7C
  [run 33977809019](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33977809019)
  at commit `5ee628d448a63b313a6f950002ae50e105dc8270`.

| Artifact | Id | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| Failed partial audit `m7d-evidence-boundary-33981034409` | 9973768675 | 4,502,729 | `ad31752acfce10532defb654b31220fcac964913fc7cc5e2d2f4905ff9eff910` | 2026-10-05 |
| Accepted `m7d-evidence-boundary-33982131486` | 9974074336 | 4,508,745 | `b6d54817e8c3979302a4a84c6af838d65e225607bbedba6ef18a8068f505aa2f` | 2026-10-05 |

The accepted aggregate manifest has SHA-256
`d899b0993d41f99a51c8faeeda74e6c08f792f28e4ad7b8e8a35be694f0046b6`;
its cell table has SHA-256
`b697122a3c683ece78d3b72cb478e97842fcb4965aea062ccf58a0440e7ee4e7`.
The run used CPython 3.13.15, NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2
with a clean worktree.

## What was implemented

Each source cell is transformed into three directories. `learner/` contains
only calibration-period external semantic outcomes, normalized calibration
trace features, the calibration health series, a trace-supported topology edge
table, and declared deployment/routing metadata. `evaluator/` contains test
outcomes and the independent test health series. `audit/` contains hashes,
quality gates, and the evidence-boundary decision.

DeathStarBench spans are parsed from the native Jaeger JSON response. Service
identity comes from the span process, target-replica identity from its hostname,
and directed edges from `CHILD_OF` references. OTel Demo spans are parsed from
the native collector's OTLP JSON-lines sink; service and replica identity come
from resource attributes and edges from parent span identifiers. Only externally
assigned calibration trace IDs are materialized in learner rows.

The health adapter pivots each nominal tick into one synchronous proxy plus
replica-a plus replica-b observation. Running, paused, container-health, network
membership, and HAProxy backend/check status are retained, but the cause and
controller event are not. Missing, duplicated, errored, or incomplete ticks are
hard failures. Test health is available only to the evaluator so the frozen
stable-interval rule can detect transitions without privileged event times.

The boundary recursively rejects denied event/controller field names in learner
schemas and checks that no privileged source file is copied below `learner/`.
It also checks exact source experiment/role labels, one source run and commit,
request counts and uniqueness, no calibration/test overlap, trace linkage,
parsed span support, nonempty topology, both target replicas, and complete
health ticks.

## Accepted result

| Application | Cells | Calibration requests | Calibration health ticks | Topology edges | Replica assignments a/b | Sequestered test requests | Test health ticks |
|---|---:|---:|---:|---:|---:|---:|---:|
| DeathStarBench Social Network | 32 | 38,400 | 9,610 | 480 | 12,255 / 12,347 | 38,400 | 9,607 |
| OpenTelemetry Demo | 32 | 38,400 | 9,606 | 384 | 22,295 / 22,826 | 38,400 | 9,604 |
| Total | 64 | 76,800 | 19,216 | 864 | 34,550 / 35,173 | 76,800 | 19,211 |

All 64 cell summaries are usable. Calibration trace-link fraction is exactly
1.0 in every cell. Each cell has 12--15 distinct normalized topology edges; the
smallest target-replica support in any cell is 199 assignments for replica a
and 218 for replica b. Aggregate source-count, duplicate-cell, processing,
unusable-cell, cross-period overlap, source-run, source-commit, and declared-run
quality counters are all zero.

The result also demonstrates physical sequestering: the aggregate has zero
calibration/test request-id overlap, test request tables and test health exist
only under `evaluator/`, no denied learner field was found, and no privileged
controller file was copied or parsed to construct learner evidence.

## Retained failed attempt and narrow repair

The first complete run qualified 61 cells and marked three OTel Demo cells
unusable, each solely because `invalid_trace_records=1`. All 1,200 calibration
request traces in each affected cell were already present and parsed, their
topologies and both replicas had support, and all leakage and health checks
passed.

Inspection of the retained raw artifacts showed the same operational pattern in
all three cells: the only malformed record was the physical final line, the file
did not end with a line terminator, and Docker had stopped the append-only
collector sink during an in-progress write. None of the three fragments
contained a calibration trace ID; two ended before any trace ID and the third
contained two unrelated IDs.

The repair classifies exactly this case as a counted nonfatal observation. A
malformed interior line, a malformed line with a terminator, or an unterminated
tail containing any calibration trace ID remains a hard failure. Unit tests pin
all three branches. Requalification of the three real files produced one
nonfatal tail count and zero quality failures per cell, after which the complete
64-cell workflow was rerun from the immutable source artifacts.

The accepted manifest records three
`truncated_nonlearner_tail_trace_records`; it does not erase them. This change
narrows the parser's classification of unrelated shutdown debris and cannot
complete or repair missing learner spans.

## Interpretation and limitations

Passing M7D shows that a common, reviewable evidence boundary is executable for
both native tracing formats and that ordinary calibration evidence exposes a
service graph and both real target replicas without controller or held-out
outcome leakage. It also gives strengthened B2 and the proposed procedure the
same admitted inputs rather than constructing a weak comparator from less data.

It does not show that traces recover the mandatory operation semantics, that
the discovered topology is complete, that the factorization is correct, or that
the target is identifiable. Deployment/domain membership and operation
predicates are declared inputs, not falsely attributed to trace discovery.
Forced sampling and controlled logical domains also remain experimental
limitations.

The test health series is evaluator evidence, not learner evidence. It may only
apply the already frozen transition guard using ordinary observed changes; it
cannot tune parameters or reveal event causes. Any future use of the privileged
controller schedule must be a separately labelled oracle/abstraction audit.

## Completion checks

- All heavy source evidence was produced and requalified only in GitHub Actions.
- All 64 cells from one pinned run and commit were processed and accepted.
- Calibration and test request IDs are disjoint and test evidence is physically
  sequestered.
- Every calibration request has parsed native trace support.
- Every cell exposes a nonempty trace-derived graph and both target replicas.
- Calibration and test health ticks satisfy the complete proxy/a/b schema.
- No denied controller field or privileged source file reaches the learner.
- The three shutdown-tail observations and the initially failed run remain
  visible and independently auditable.
- No estimator, method comparison, or prediction was executed in M7D.
