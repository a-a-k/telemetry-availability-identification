# Identification of the completion-and-deadline target

## Position and fixed question

The contribution is a method for identification of stochastic availability models
of microservice operations from runtime telemetry, with formal justification of
target identifiability and computational reduction. Operation declarations,
success requirements and observation-binding rules are additional inputs.

This bounded extension uses the already opened independent confirmation source
34703686592, commit 12ddb09369ee6e0b60ca4c7db6fe1e749530b7df. Its sole final
aggregation failure is admitted by the unchanged audited source checker.
This is retrospective analysis of saved evidence, not another blinded validation.
No application deployment, new independent attempts, competitor tuning or new
Palladio/CUDD/aGrUM/Storm runs are planned. The previous scientific locks remain.

## 1. Two claims and their mathematical conditions

Write R=T AND AND_j C_j and E=K AND R. C includes the entry completion and all
source-declared logical mandatory groups, with the accepted one-retry binding.
K contains the remaining structural/selected-replica conditions (including the
existence of required structural edges). K here is NOT the aggregate completion
variable called K in some earlier reduction notes; call that aggregate U here.

For each observation o let F(o) be its nonempty admissible set of complete states
and w(o)>0 its empirical frequency. The declared model imposes Cartesian unknown
coordinate masks, retains their joint observation frequencies, and allows any
conditional law supported on each F(o). No coordinate independence is assumed.

**Event equivalence.** On any specified domain H, E=R iff there is no state in H
with R=1 and K=0. Physical assumptions may justify this on real executions while
it fails on the larger declared F(o). We do not silently add physical implications
to the frozen mask family after seeing their consequences.

**Sharp bounds.** For f in {E,R,D=R-E}, lower(f)=sum_o w(o) min_F(o) f and
upper(f)=sum_o w(o) max_F(o) f. Each endpoint is attainable by putting the
conditional mass at a corresponding extremizer in every observation fiber.
This statement concerns the declared family, not physical realizability of every
witness or confidence for future data. D is computed jointly, never by subtracting
independently optimized E/R intervals. Since E<=R, D is Boolean. Upper(D)=0
certifies equivalence almost surely for every admissible law; lower(D)>0 forces
a positive difference in probability; otherwise a difference is admissible but
not identified. Per-attempt D=[1,1] forces unequal events; D=[0,1] is undecided.

Positive observation weights and E<=R imply equality of the two aggregate lower
endpoints exactly when all fiber minima agree, and similarly for maxima. Equality
of both endpoints does not imply upper(D)=0: a fiber containing (R,K)=(0,1),
(1,0),(1,1) has E and R both in [0,1] but D in [0,1]. Conversely observed R=1
with unknown K can give R=[1,1] and E=[0,1]. These are required artificial controls.

**Representation equivalence for R.** Map each complete state to q(s)=(T,U),
U=AND C. Under the Cartesian contract the exact image of an observation fiber
is represented by T and U: U=false if an observed completion is false, true if
all are true, and unknown otherwise. Every state in that image has a preimage;
therefore every law on it lifts to an admissible original law. Combining identical
image masks by summing their empirical counts preserves the attainable R
probabilities and sharp endpoints. If additional cross-coordinate feasibility
constraints are imposed, use the exact constrained image and recheck this proof.

Direct identification and projection coincide when they use the same attempt
population, mandatory-group declarations, primitive observations, missing values
and weights. This is an implementation acceptance requirement. They are NOT
required to agree with E, or to share the full model's structural support checks.
The empirical bounds converge under a law of large numbers for the finite
observation-category frequencies and a fixed binding/support; this extension
does not provide new statistical coverage or establish stationarity of campaigns.

R alone does not retain K or contrasts such as reachability minus execution.
Two laws can have identical (T,U) but different K and hence different E or D.
This loss must be tied to the requested functional, not described as generic
information loss without a counterexample.

## 2. Independent direct route and support

The direct route receives native span records, attempt timestamps/identities,
operation declarations and the existing binding rules. It can reuse native
parsing/parent validation and logical completion interpretation. It must not call
the full constructor, construct replicas/demand masks, align health probes, or
project a previously constructed full state. It discovers only the required
logical-group vocabulary under the same declared service/database rules.
Missing declared edges/services leave completion evidence unknown and need not
cause the full model's structural refusal. Unclassified services or unsupported
parent/group interpretation remain explicit unsupported statuses. Neither route
receives external business outcomes as identification inputs.

The full constructor is the unchanged v4 function with a private replacement of
its final all-functional solver by a no-op. This changes no global or frozen
source file. Its full model and support are checked against the original saved
models outside all cost measurements. The first route computes only R through
its relevant coordinates; unrelated control states are never enumerated.

## 3. Complete semantic and missingness comparison

Use all 18 calibration and test campaigns, 60 operation positions per period;
preserve full/direct/common support, including every structural refusal. Audit
each direct primitive observation against the full route on common support.
Verify all three R routes exactly as rational numbers, category laws, and statuses.
For test data obtain Y from the already independently verified primary records.
Check both lower<=Y and Y<=upper for each event, and direct E=Y/R=Y only where
the respective event is determined. Never select attempts by event/Y agreement.

Reuse six missingness levels 0/.1/.25/.5/.75/1, three mechanism classes and five
information-restoration groups. Freeze one hidden-cell list keyed by attempt ID
and primitive observation name; apply that exact list to both routes before U
is formed. The common-support master vocabulary includes the original controls;
direct-only cases use their own declared primitive completion vocabulary and are
reported separately. The same percentage in independent coordinate spaces is
not an admissible comparison.

Uniform and whole-native-attempt ranking reuse seed 771622 and the prior hash
rule. To honor Y-only-for-validation, the failure-associated priority uses any
observed false *logical completion* instead of the former external Y. This is an
explicit new native-failure-associated mechanism, not an exact replay of the old
Y-associated masks. No new masks consult Y. Deadline observations are retained,
as before; this studies missing state evidence under a fixed declared vocabulary,
not topology reconstruction from deleted whole spans. Original unknowns remain.

Keep all per-case settings and compact per-attempt pattern counts. Report exact
E/R/D bounds, widths, point identification, Y incompatibilities in both directions,
forced/equivalent/undecided event differences, coincident marginal intervals with
possible joint differences, masks and all restoration budgets. Archive baseline
attempt records, actual mask plans and extremizing state witnesses. Independently
verify every distinct visited mask using the frozen formal predicate outside cost
timers. All-restore must recover the original observation law.

## 4. Three matched cost routes for one R

1. Saved observation records -> full identification -> optimized R query.
2. The same records -> full identification -> explicit (T,U) projection -> R query.
3. The same records -> direct (T,U) identification -> R query.

Use the same previously chosen first split/N/0 calibration campaign per
application, multipliers 1/2/4, scale orders [1,2,4]/[2,4,1]/[4,1,2], three
technical rounds and a rotating order of the three routes: 81 processes.
Renaming copied request/trace/span IDs uses the already qualified copy routine.
Counts 3600/7200/14400 remain computational workloads, not independent observations.

Before every route, warm the OS file cache by reading the same source files as
bytes. Each route runs in a fresh Python process with identical installed tools;
there is no claim to have flushed the shared VM hardware caches. Downloads, seal
checks, deterministic copies and installation precede all timers. Full routes
read the five existing input-role JSON files; the direct route needs requests,
native spans and declarations and can omit health and the manifest. Native spans
are the preserved input representation, not a new raw Jaeger/OTLP parser benchmark.

Primary wall time runs from parent process launch to the child's monotonic marker
immediately after saving the first models and R answers, including interpreter
start, record decoding, construction, necessary projection, query and serialization.
Child process CPU and peak RSS are sampled at this same first-answer point.
Internal read/build/project/query/save stages are retained separately. Additional
31 warm R queries on the ready representation are timed afterward and reported
separately; whole-process resource records include these later queries and are
not mislabeled as first-answer resources. No oracle or inter-route checks precede
later timed routes. All checks follow all 27 processes for each application.

Report every pair/triple and nine volume/application summaries, stage/CPU/RSS,
prepared query costs, model sizes and absolute/relative scaling. Results are not
required to favor direct identification. A full route can exploit an equivalent
sufficient representation; the experiment does not establish an optimal full
implementation or asymptotic dominance.

## 5. Completion and failure handling

Complete only after all planned positions, masks and timings are accounted for;
all claimed-equivalent R routes agree on common support; all distinct visited
mask witnesses pass an independent formal check; every E/R difference has a
recorded mask classification; full table/attempt evidence is retained and the
report is pushed. An unexplained R-route discrepancy fails qualification and is
not hidden by the allowance for scientifically meaningful E/R differences.
New observations are needed only if a semantic/binding correction changes
forecasts after inspecting outcomes. A proven equivalent transformation uses
saved-data verification. No manuscript, PDF or Word deliverable is part of this work.
