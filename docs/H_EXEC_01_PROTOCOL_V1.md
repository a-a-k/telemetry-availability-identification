# H-EXEC-01: prospective routing and execution boundary package v1

Authority: correction v3; follows qualified technical graph chains for3/3 apps
(iterations016,021). Frozen with executable acquisition and analysis before the
first technical block. No H result is yet asserted. Main campaigns remain0.

Motivation/version: corrected historical M7/full/current OTel checkout predicts
0.9291864417 versus0.6843229167 observed on55/80 issued campaigns, signed error
+24.4863525064pp. On its stable view the signed error is still+19.8760226475pp.
Sources: exact corrected operation-summary.csv in rescore34220234444 and complete
correction milestone019. These are historical development data and earlier
operation semantics. They motivate this prospective question, not an estimated
causal fraction of that error. This package uses the qualified whole-operation
2-second contracts and cannot by itself explain AINA, whose scenario p is known.

Question: when replica b remains healthy, can routing to paused replica a prevent
successful complete checkout despite existence of a live required route? Does
explicitly removing a from routing repair that deficit under the same physical
state? A secondary question compares a fresh pause with an already sustained pause.
These are facets of one H-EXEC mechanism, not three separately selected mechanisms.

Fixed runtime: OTel source8c47d47c9ac27710d2b2a153bcd53e483bffe66d; existing pinned
runtime image digests and placement renderer; colocated logical domains; same
two product-catalog replicas, shared DB, all other services unchanged. HAProxy3.0
uses its existing HTTP/2 roundrobin/L4 check policy and timeout configuration.
The only setup additions are a captured traceparent routing log and a private
admin socket. Instrumentation has its own version; overhead is not claimed absent.

Four intervention arms, each in a fresh deployment:

| Arm | Normal baseline |30-second conditioning |30-second measured window |
| --- | --- | --- | --- |
| sham |both replicas running|both running, unchanged routing|both running|
| transition |both running|both running|pause a immediately before first measured request|
| settled |both running|pause a before conditioning starts|keep a paused|
| repaired |both running|pause a and disable a in HAProxy before conditioning starts|same paused a, requests routed to b|

The baseline is60 seconds. Every period uses4 complete operations/second with the
same balanced/shuffled operation sequence within each block; three operations
retain their fixed2-second total budget and no driver retries. Each cell has480
external business attempts (240+120+120), including40 measured checkout attempts.
Non-target negative control: GET /favicon.ico every2 seconds, response200 with
exact source Git blob ae9cadf5115d64064416bf8f847568e5f7da4de8 and123125 bytes.
This public static asset is not an eleventh main business operation. Requests and
negative controls use identical schedules in every arm. Control bytes are checked
remotely; only hashes, counts and status/timing metadata need compact retention.

Planned size: first1 technical block of4 arms, excluded from inference; then8 new
independent blocks of4 arms (32 campaigns), each on fresh runners/deployments.
Assignments to four job slots are independently permuted within block from a
predeclared seed. Workload sequence is shared within block and varies across
blocks. Exact seeds and assignment tables are in configs/h_exec_01_v1.json: assignment qualification2026090810/study2026090811, workload qualification2026090812/study2026090814, analysis2026090813. Code, workflow and repository/source hashes are frozen before the first technical block; study uses a disjoint seed namespace. No outcome-dependent N increase, method selection or optional stopping.
Total budget36 cells/17280 business attempts, of which1280 study checkout outcomes
belong to the measured windows. Maximum30 minutes/cell and3 concurrent runners
(18 runner-hours acquisition-job bound). Four plan/analysis jobs add at most40 runner-minutes across the two phases; total runner bound18h40m. Native/raw storage planning allowance is200MB/cell,7.2GB total; actual bytes and deviations are reported, not used to omit cells.
This is a resource allocation, not a power or precision guarantee.

Two co-primary checkout success contrasts, computed as equal-weight paired block
means: A=sham−settled (adverse deficit); B=repaired−settled (routing repair).
Both are predicted positive with a practical magnitude of at least5pp. Family
alpha=.05, two-sided exact within-pair randomized-label tests at.025 each, with
all2^8 sign assignments and ties included. Display paired8-block bootstrap
10000-resample central97.5% intervals using a fixed analysis seed; finite-sample
bootstrap coverage is not guaranteed. Statistical support for each primary
requires its predicted sign, at least5pp mean, and exact p≤.025. The joint claim
requires both plus qualified manipulation and diagnostic evidence. Report every
contrast regardless of sign. Transition-versus-settled and other operations,
static controls, latencies and timing bins are predeclared secondary diagnostics;
they cannot replace a failed primary or establish another confirmed mechanism.

Manipulation evidence: recorded Docker command start/completion and state checks,
actual health tick census, b readiness at period boundaries, all service state
snapshots and proxy admin responses. Intended paused/unpaused target state must
hold in at least95% of measured health ticks and b must remain running/unpaused.
No privileged field enters a primary graph estimator: this package is a causal
diagnostic, with the controller and evaluator explicitly allowed those fields.
Maintain a full attempted census. If a primary pair is missing or manipulation
is unqualified, retain observed results/absences and do not label its reduced
subset as the planned confirmatory contrast. Technical reruns require a recorded
infrastructure/code cause and new version where appropriate; they do not add N.

Routing logs retain actual selected backend, captured native trace ID, status,
duration and termination code. Join by the external trace census, retaining
unmatched/missing routes and failure/success-specific coverage separately.
Native traces remain unchanged, including errors, durations and multiple roots.
Requests can contain multiple catalog RPCs; never reduce their routes to one
fictitious call. Paused-a selections associated with failed complete requests
and successful b completions provide execution evidence; this association is not
an identified causal mediation fraction. All primary outcomes remain the complete
external event; HTTP200/gRPC200 alone does not replace it.

Alternative explanations: missing required dependencies, whole-event contract
errors, loss of trace/context, DB/background degradation, effective-probe/readiness
mismatch, persistent connections/queuing/history, and instrumentation cost. Fixed
contracts/sentinels, source/native graph, static control, boundary readiness,
normal baseline, full service snapshots and the explicit routing repair constrain
these alternatives. Any residual ambiguity must limit the causal conclusion.
The admin intervention uses known experimental state; it is not an admissible
oracle parameter source for G0/G-ID/G*, nor an automatically justified refinement.

Formal bridge (known probability fact, not claimed new theorem): for a static
two-route operation with actual readiness a,b∈{0,1}, one selected route, and
conditional selection probabilities pi_a+pi_b=1, actual success is a*pi_a+b*pi_b.
Ideal OR reachability is a∨b. Their deficit is
a*(1-b)*pi_b+b*(1-a)*pi_a≥0; equality requires no failed-route selection when a
healthy alternative exists. Averaging under arbitrary state/selection laws keeps
this condition almost surely. With K required independent route selections in a
fixed state(a,b)=(0,1), success=(pi_b)^K while reachability=1. Independence, fixed
state, no retries, perfect background and timely healthy completion are explicit
assumptions of that K-call example, not facts about this application's gRPC policy.
Nineteen exact artificial controls check this bridge independently of graph BFS; result in docs/evidence/h-exec-semantic-controls/exact-controls.json.

Retention: source/config/assignment/role seals, native/raw archives remote90 days,
compact full census, outcome/route/health coverage and manipulation reports,
phase costs including extraction/parse/evaluation, all attempted cells and failures.
No PMX/model fitting or main-series accuracy comparison in this package. A positive
result supports a scoped execution boundary; a negative result remains a result.
Neither result alone selects a final G*, licenses more than2 deep mechanisms,
establishes novelty, or satisfies the remaining v3 main admission criteria.

Execution evidence threshold, fixed before observation: at least10 failed measured checkout requests with an actual selected-a routing record, distributed across at least6/8 settled blocks. Static measured controls require120 attempts/arm, at least97% successful in each arm and at most3pp spread across arm rates. These are diagnostic acceptance tolerances, not statistical equivalence tests. The joint scoped H claim requires qualified complete32-cell design, both co-primary tests/effect thresholds, routing diagnostic threshold and static tolerance. Per-primary statistical support is also reported separately, including when the joint claim is unqualified.

The acquisition keeps a paused through a20-second post-request drain, then releases it and uses the existing trace flush. Native parsing and every diagnostic computation run in Actions. Its period labels baseline/calibration/test are names of warm-up/conditioning/measurement roles in this H package; they are not main-study learner/evaluator roles. Failure-law metadata H_EXEC_01 denotes the declared controlled intervention, with no renewal events. Successful-request-only selection is never applied.

The technical workflow first verifies repository locks and exact slot assignment, validates the added proxy syntax using a separately identified loopback-only syntax fixture, then runs all four arms. A subsequent study dispatch requires a successful four-arm qualification artifact with the same entire protocol-config SHA-256; the artifact API identity/bytes/digest and source head are checked. A changed protocol requires a new technical qualification. The study never silently treats the technical block as one of its8 blocks. Failed/missing cells remain in the aggregate attempted census, and no reduced subset is labelled the planned confirmation.

Implementation: h_exec_design_v1 (19 exact controls, assignments, exhaustive randomization), h_exec_live_v1 (instrumented acquisition), h_exec_compact_v1 (full request/route/native/state census), h_exec_analysis_v1 (gate and frozen analysis), .github/workflows/h-exec-01-v1.yml. Proxy capture/custom-log and admin command semantics follow the official HAProxy3.0 [configuration manual](https://docs.haproxy.org/3.0/configuration.html#8.2.6) and [management manual](https://docs.haproxy.org/3.0/management.html). Pure controls also verify the log parser preserves multiple calls and failures while separating foreign/missing context. Neither implementation completion nor technical qualification establishes the H claim.
