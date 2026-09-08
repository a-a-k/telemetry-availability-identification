# Selected-replica demand and deadline: one bounded execution refinement

This version develops the routing/execution boundary supported by
[H-EXEC](milestones/H_EXEC_01_SEALED_STUDY_CONFIRMATION.md). It is a finite model
core with semantic and identification controls, not an admitted application G*
or an additional confirmed mechanism. Its inputs are declared model objects and
masked observations; no privileged controller state, endpoint residual, learned
regression or automatic assumption of independent calls is introduced.

## Model and implemented class

Keep the discovered directed graph G, its sync/async types, replica bindings R,
the declared entry and required targets. A finite state is w = (X, D, T).
X contains Boolean capability/edge coordinates used by graph traversal. Shared
coordinates may gate multiple replicas or edges. For each controlled required
service s and replica r, D_sr says that at least one mandatory call selects r.
T says the complete required execution meets the declared external deadline.
The law P(X,D,T) is arbitrary and joint; replicas, demands and timing are not
factorized. The implementation supports at most 16 total Boolean coordinates.

The supported execution class assumes capabilities remain fixed during one
operation, every selected call is mandatory, selected incapable replicas cannot
be rescued by a later retry, and repeated calls to one replica have the same
capability verdict. D is therefore a set of required replicas, not a call-count
exponent. Request-specific errors, state changes and rescued failures require a
different observation/state contract; they are not silently represented by this
class. T is a model coordinate whose observation must be justified. It is not
automatically the sum of span durations, a health-probe verdict or semantic Y.

Let B(w) be the existing graph predicate: every declared target is synchronously
reachable through capable services/edges. Write C_sr(X) for the conjunction of
the capability gates of replica r. Define

```text
J_s(w) = (OR_r D_sr) AND (AND_r (NOT D_sr OR C_sr(X)))
R(w)   = B(w) AND (AND_controlled_s J_s(w))
E(w)   = R(w) AND T
```

The three persisted variants use the same graph, observation categories and
joint law: B (reachability ablation), R (selected-replica restriction without
deadline) and E (the complete bounded refinement). These are ablations of one
execution hypothesis, not three separately selected H mechanisms. No final main
method binding is assigned by the component's `primary_variant` field.

The graph enters every state's traversal. Removing an incoming edge needed to
reach a required DB changes an otherwise successful prediction to zero; edge
order does not change any result. Replica demands bind to actual declared R
entries and cannot alias capability/timing coordinates. A saved model replays
in a separate process using only its JSON state, graph and sufficient counts.

## S2: semantic reduction and its boundary

**Conditions.** G/R, required targets and the supported execution class above are
fixed. The concrete execution-to-state map h is complete enough that capability,
mandatory selection and T have those meanings. Required background dependencies
and full business-result conditions are included or have explicit, justified
deterministic reductions. The external business event satisfies Y = E(h(W)).

**Claim.** E <= R <= B pointwise. Therefore E_P B - E_P E is nonnegative and equals
P(B=1,E=0). Reachability and execution probabilities coincide exactly when the
discordant event has zero mass. For equivalence under every allowed state law,
the predicates must agree at every allowed state.

**Proof.** R conjoins restrictions to B and E conjoins T to R. Their Boolean
difference B-E is the indicator of B=1,E=0. Taking expectation gives the result.
If there is a discordant allowed state, the point mass on it disproves equality
for every law. Conversely pointwise equality gives equality under every law.
This is an elementary event-restriction identity, not a new general theorem.

**Counterexample and consequence.** With a incapable, b capable and a required
selection of both, B=1 and R=E=0. Selecting only b repairs this particular gap;
T=0 can still make E=0. H-EXEC supplies a scoped live routing intervention, but
does not prove arbitrary probes equal X, establish the invariance of P after a
placement change, or establish this class for all ten applications' operations.
Outside Y=E(h(W)), the model's nonnegative internal gap does not constrain the
sign of empirical business-availability error. Negative historical bias remains
possible and is not contradicted by the elementary inequality.

## I4: joint observation law, target certificates and attainable bounds

Observation O=(M,w_M) gives a mask and observed coordinates, with arbitrary
state-dependent missingness. For each category o let F(o) be the nonempty set of
consistent complete states. For a fixed population observation law Q, and any
of the three predicates f or their paired differences, the exact feasible range is

```text
L_f = SUM_o Q(o) min_{w in F(o)} f(w)
U_f = SUM_o Q(o) max_{w in F(o)} f(w).
```

**Proof and identification condition.** Conditional expectation in each fiber
lies between its extrema. Put the entire conditional mass on a minimizing or
maximizing state independently within each category to attain either endpoint
while preserving Q. The range collapses exactly when f is constant on every
positive-mass fiber. Parameters may remain ambiguous even when the requested
target is constant. This is the finite conditional-support argument already
attributed in [I3](GRAPH_OBSERVATION_LAW_V3.md), extended to the explicit joint
execution state; it is not claimed as a new general partial-identification result.

The estimator counts **all** observation categories, including masked ones,
and replaces Q by their empirical frequencies. It evaluates the saved graph on
every compatible state and retains exact rational bounds plus low/high state
witnesses for ambiguous categories. Bounds on B-E, B-R and R-E use the same
joint completions directly; subtracting separate marginal intervals can give
impossible negative gaps. A non-singleton target returns `prediction=null`.
No MCAR completion or arbitrary latent optimizer point is substituted.

These are ranges conditional on an empirical observation law, not confidence
intervals. Unseen categories in a finite calibration sample do not establish
zero population mass. A future forecast needs an explicit stability assumption;
source-only placement transfer needs identification of the changed state law or
transport assumptions. This component provides neither an automatic causal
transport rule nor a physical domain/network-cause decomposition.

Two small examples show why a joint law is required:

- Two mandatory calls with route words AA/BB equally often versus AB/BA equally
  often have identical one-half per-position marginals. In state (a,b)=(0,1),
  execution probabilities are 1/2 and 0. The independent-call value 1/4 is an
  extra assumption, not identified by those marginals.
- Equal-mass capability states 01/10 with routing always to the capable replica
  versus always to the incapable replica give execution 1 versus 0, while all
  capability and demand-coordinate marginals agree. Separately fitting routing
  and capability distributions loses the relevant dependence.

## Observation and application obligations

The [ten-operation census](milestones/V3_EXECUTION_OBSERVATION_CENSUS.md) establishes
some available observations, not the map h: OTel `study.replica` labels survive
despite absent standard instance IDs; DeathStar call entries need an explicit
source/parent adapter; Petclinic failed calls may not have target SERVER spans.
Missing route evidence must remain masked. All 46 observed Petclinic timeouts
have no native error flag, so no-error cannot be used as a semantic success or
timeliness certificate. A known observed footprint need not contain an attempted
call whose telemetry was lost or that never reached a SERVER.

Before application admission, bind every X/D/T field to an ordinary source and
state its clock, reporting, conditioning, missingness and repeat assumptions.
Include DB/background nodes in G; list every deterministic reduction. Preserve
all attempts and abstain or report ranges where observations do not identify
the target. Native observations of a successful call do not identify the
counterfactual capability of every unselected replica. No data-derived equality
between this predicate and a complete business contract is assumed.

Nine bounded tests exercise routing and deadline distinctions, both joint-law
counterexamples, sharp ambiguity witnesses, target identification without full
parameter identification, paired gap bounds, graph mutation/equivalence,
separate-process replay and invalid semantics. No full application model is
fitted locally. The next step is a source-grounded application binding and its
independent A/B and technical controls, with comparison to G0 kept explicit.
