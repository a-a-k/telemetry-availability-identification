# Methods draft: identification and use of a telemetry-parameterized model

Working methodological text, updated 8 September 2026. Under the accepted
[correction plan](SIMPAT_CORRECTION_PLAN.md), the primary method estimates
parameters of its declared stochastic model without ML or learned forecast
corrections. The [complete M7 census](milestones/M7_COMPLETE_OPERATION_CENSUS.md)
reports all six original operations. M9N-M9P below is retained as separate
temporal-regression diagnostics, outside the primary method and its evidence. It does not substitute a failed
integration control for the outstanding independent PMX accuracy comparison.
It is not a final abstract, novelty verdict or claim that the initial article
design has been fully realized.

## Prediction target and observation contract

We distinguish the probability law of collected telemetry from the probability
of a semantically successful user operation. Let `X` denote latent primitive
states, `p` their model parameters, and `g_u(X,c)` the specified success function
for operation `u` in context `c`. The target is

```text
A_u,c(p) = E_p[g_u(X,c)].
```

The context fixes deployment, operation, response semantics, timeout and routing
policy. A static Boolean route is one possible `g_u`; the interpretation must
be validated for the operation. A request with repeated downstream calls or
stateful failover may require timing and routing state that the static route
does not represent. An accurately computed static union then need not predict
the external request outcome.

The observation contract specifies potential measurements `Y=f(X)`, the mask
of available coordinates, their common population and weighting, and the data
boundary available when producing a forecast. Health-tick probabilities,
request-weighted outcomes and trace-conditioned span errors are different
quantities until an explicit correspondence relates them. A missing span is
not automatically an observed failed request.

In the proved family, primitives are independent Bernoulli variables with
parameters in a nonempty open product box in `(0,1)^d`. Each potential
observation is a conjunction `Y_i=∏_(j∈A_i)X_j`. The mask has a known fixed
distribution independent of primitive state and parameters. Shared causes can
be represented by a primitive appearing in several conjunctions; arbitrary
dependence between the primitives themselves is outside this family.

The topology and measurement semantics in the restricted experiments are
configured inputs. The live adapters provide separate, versioned mappings from
telemetry to those inputs. Neither the identification theorem nor the current
signature compiler establishes automatic extraction of a correct request
success function from arbitrary traces.

## Population identification of a target

For every nonempty set `J` of observations jointly available with positive
mask probability, include its joint success moment. Independent primitives
give a monomial indexed by the union of the corresponding primitive sets:

```text
m_J(p) = E[∏_(i∈J)Y_i] = ∏_(j∈union_(i∈J) A_i)p_j.
log m = H log p.
```

`H` contains the distinct union-incidence rows. It must represent the complete
supported moment family; selecting a few low-order moments can omit information
present in the actual observation law. Inclusion–exclusion recovers every
binary observation-pattern probability from these moments. Consequently two
interior parameter vectors have the same masked observation law exactly when
`H log p = H log p'`.

For a finite target polynomial in canonical form,

```text
F(p) = Σ_α c_α p^α,
```

global identification throughout the open parameter box holds exactly when
every exponent with nonzero coefficient belongs to `row(H)`. A row certificate
`H^T a_α=α` gives the observable expression
`F=Σ_α c_α exp(a_α^T log m)`. Conversely, a target constant on every observation
fiber has zero derivative along every `v∈ker(H)` throughout the box. Linear
independence of its distinct exponential terms forces every `α^T v` to vanish.
The [complete proof](CONJUNCTIVE_OBSERVATION_TARGET_THEOREMS.md) also distinguishes
global identification from exceptional parameter points or fibers.

Every Boolean success function has a multilinear expectation polynomial under
independent primitives. The criterion therefore covers arbitrary Boolean
targets under conjunctive observations. It does not cover arbitrary Boolean
observations, unknown informative missingness, boundary-only domains or
additional equality-constrained parameter spaces. Expanding a general truth
table can require exponentially many terms.

The separate exact rational reference emits row combinations for supported
terms or a null-space certificate for an unsupported term. The latter proves
global nonidentification within the stated contract; it is not a pair of
counterfactual parameter vectors at an arbitrary supplied estimate. Unsupported
input semantics receive no theorem-based verdict. A finite sample with too
little observed support is also distinguished from structural ambiguity in the
population law.

For example, observing only the disjoint path products `p_1p_2` and `p_3p_4`
identifies their union as `m_1+m_2-m_1m_2`, while none of the four individual
probabilities is identified. In contrast, the marginal moments of the shared
paths `p_1p_2` and `p_2p_3` alone do not identify their union; adding their
synchronous joint moment suffices. These examples concern the information contract, not the
accuracy of an estimated current endpoint under a deployment change.

Log-probability linearization, rank-based network tomography and inseparable
parameter combinations are established antecedents. Their attribution and the
limits of the present literature comparison are recorded in
[RELATED_WORK_SCOPE.md](RELATED_WORK_SCOPE.md). The result used here is a
restricted target certificate with an explicit observation contract, rather
than a claim of first introducing inverse identification from telemetry.

## Reduction and matched estimation

The implemented M2 compiler groups primitives with identical membership across
retained conjunctions. For each group `G`, replace its primitives by
`Z_G=∏_(j∈G)X_j`, with parameter `q_G=∏_(j∈G)p_j`. Disjoint groups give
independent Bernoulli variables, and every retained observation is unchanged
pointwise after substitution. This preserves the complete observation law and
its exact likelihood. Inactive primitives integrate out.

Independent box constraints map to the product of the exact group-product
intervals. Optimizing the reduced and original likelihood over these matched
feasible sets therefore gives the same attainable objective values. A prior
or penalty must also be transformed correctly if one is added; selecting a
single optimum with a regularizer does not establish that the data identify
its constituent parameters.

The exact reference likelihood sums the independent primitive-state masses
consistent with each observed pattern and mask. With independent episodes,
pattern counts can be used in the corresponding multinomial log likelihood;
the known mask factor is parameter-independent. Temporal dependence does not
justify treating every request or tick as an independent replicate of that
sampling model.

Signature grouping is a sufficient reduction rule. It neither finds every
identifiable target nor removes every likelihood ridge. For example,
`m_1=p_1p_2`, `m_2=p_2p_3`, `m_3=p_3p_4` have four distinct columns but identify
`p_1p_4=m_1m_3/m_2`. Target certificates must be retained separately, especially
when a target involves only part of a merged group.

The matched original likelihood is the correctness comparator: both methods
use the same observations and law. Agreement of their fitted objectives is
expected under correct reduction and successful optimization. It establishes
neither extra statistical information nor predictive superiority. The
[M2 report](milestones/M2_STRUCTURE_PRESERVING_REDUCTION.md) retains all 7,200
paired checks, the 26 ambiguity witnesses and the unreduced negative controls;
its small state spaces do not establish large-graph scalability. The later
polynomial reference is separate and has not been inserted retrospectively
into those experiments.

## Structural ambiguity and sampling uncertainty

An identified target can still be estimated imprecisely. Conversely, infinite
sampling precision cannot remove a target's variation across observationally
equivalent parameters. Let `C_α` be a simultaneous confidence region for the
supported population probabilities. The model-compatible parameter set and
target interval are

```text
P_α = {p in the declared parameter domain : m(p) in C_α},
I_α = [inf_(p∈P_α) F(p), sup_(p∈P_α) F(p)].
```

Whenever the true model law is in `C_α`, its target lies in `I_α`. This is a
coverage implication conditional on the observation and sampling assumptions,
not a proof that an arbitrary confidence procedure applied to dependent live
telemetry has its advertised coverage. A numerical implementation must preserve
outward optimization error. An empty feasible set is reported explicitly.

M4 uses standard simultaneous probability constraints and conservative
propagation under its iid correctly specified generator. M5 then examines
directed violations. These experiments are distinct from the M9P paired
campaign bootstrap; neither procedure licenses a universal robustness claim.

A two-path example makes the role of dependence assumptions explicit. On one
common probability measure, let `P_a⊆H_a`, `P_b⊆H_b`, with observed health
marginals `h_a,h_b`, joint health `h_ab`, and path marginals `p_a,p_b`. Under
containment alone the static union has the sharp interval

```text
[max(p_a,p_b,p_a+p_b-h_ab), min(p_a+p_b,h_a+h_b-h_ab)].
```

If `P_i=H_i∩C_i` and the entire communication vector is independent of the
health vector, the communication marginals are `c_i=p_i/h_i` for positive
health support. Arbitrary dependence within that communication vector gives

```text
[p_a+p_b-h_ab min(c_a,c_b),
 p_a+p_b-h_ab max(0,c_a+c_b-1)].
```

Additional independence between `C_a` and `C_b` yields the B2 point functional
`p_a+p_b-h_ab c_a c_b`. Thus the same five observable probabilities can support
a broad interval or a single value under different assumptions. The
[attainability proofs and zero-support cases](B2_SHARP_OBSERVABLE_BOUNDS.md)
are explicit. This small probability-bound formulation is standard atom-based
reasoning, not a new general network optimization algorithm. M7 B2 and the
synthetic M3 B2 also have different observable contracts.

## Semantic validation and comparison boundary

Identification answers which quantities the specified observation law can
determine. Independent validation answers whether the specified success law
predicts the operation's semantic outcome. M9K–M localized the static checkout
discrepancy to one-path episodes and the request's repeated calls; M9N developed
a temporal model on retained data. M9P completed a frozen 120-campaign independent
confirmation separating conditional mechanism information, marginal gain relative
to a state-only model, and adequacy of the mean forecast. All five gates passed:
conditional information replicated, marginal temporal/state Brier was practically
equivalent within ±0.002, and mean signed error was adequate within ±0.03 despite
an entirely negative interval. The completed-run report preserves the exact
intervals, matched endpoint controls, information costs and evidence seals.

This temporal extension is an explicitly specified conditional-response model
for checkout. It was developed through the preceding source and retained-data
diagnosis; the signature compiler did not automatically discover it. Confirming
that curve does not independently confirm the original static execution law,
identify every underlying fault cause, or extend the conjunctive-observation
theorem to a dynamic router. The mathematical and live results retain these
different model classes and development histories.

The conditional comparison uses observed test health to ask whether age carries
mechanism information. The marginal forecast is produced from learner data
before test access. Both may be useful, but they answer different questions.
The [intercept identity](M9P_CALIBRATION_IDENTITY.md) explains why an age curve
can improve conditional scores while giving nearly the same calibration-
weighted mean as a state-only or matched endpoint estimate. No conclusion about
a different future exposure distribution follows without a separate transport
and validation argument. The [target-exposure note](TARGET_EXPOSURE_AND_MEAN_FORECASTS.md)
gives the exact difference identity, a total-variation bound and an attainable
two-context example. It also retains a reweighted stratified endpoint as a
necessary matched comparator for any future exposure-transfer assessment.

External comparison also requires a semantic input contract. A software error
recorded on a parent operation can include a propagated child error. Treating
both inclusive rates as independent local failures counts overlapping events
twice. For an artificial two-level serial example with root error rate 0.2,
child error rate 0.1 and every child error propagated to the root, multiplying
inclusive success rates gives 0.72. Under an additional independent local-root
failure law, its conditional local rate is `(0.2-0.1)/(1-0.1)=1/9`, giving root
success 0.8. The bounded [M9R solver census](milestones/M9R_PMX_INCLUSIVE_ERROR_COMPOSITION.md)
initially produced no valid probability. The subsequent source-grounded
[M9S bridge](milestones/M9S_PMX_PMF_BRIDGE.md) represents integer loop counts as
equivalent point-mass distributions; all 16 positive solver controls then recover
0.72, 0.8, 1.0 and the additional random-loop oracle 0.724. Both original failure
boundaries reproduce. This confirms the artificial composition calculation,
not independence of local failures in a real application.

M9A–D verify pinned Palladio solver and mapping correspondence with supplied
aligned inputs. M9Q retains observed-operation extraction and usage-mapping
failures on four historical samples. An independently extracted architecture
needs the external-request boundary: [M9T](milestones/M9T_PMX_REQUEST_CORRESPONDENCE.md)
shows that the OTel driver groups several HTTP calls into one user operation
and that DeathStar semantic timeouts need not have a native span-error flag.
The complete independent extraction
and independently parameterized availability forecast remain a separate
comparison. Failed launch, extraction, serialization or solver boundaries are
reported as those boundaries; they are not assigned zero availability or used
to claim superior predictive accuracy.

[M9U](milestones/M9U_PMX_REQUEST_CONFORMANCE.md) subsequently qualifies the
external-request projection and both disclosed error parameterizations on six
artificial cases: 12 extractor invocations and all 44 numerical solver records
pass. The wrapper carries an additional observed endpoint outcome; native times
and provenance remain intact. A conditional-local variant abstains when a parent
swallows a child error. The repeated-call control deliberately differs from its
empirical request success under correlated errors, separating valid independent
composition from an adequate dependence model. M9V freezes the following
historical development comparison before fresh confirmation.

## Reproducibility and cost

Source acquisition, semantic qualification, method-specific inputs, extraction,
fitting and solving are reported separately. Health used for request selection
and temporal age remains an input even when native traces are not read by the
predictor. Zero method-specific trace bytes do not mean that the study collected
no traces. Shared parse timers do not measure an isolated implementation of
the endpoint comparator. Artifact sizes and runner duration also do not measure
monitoring overhead, which needs its own comparison.

Frozen workflows separate candidate generation from evaluator access, preserve
failed attempts and retain the complete declared campaign matrix. A missing
forecast is not a zero-valued forecast; conditional accuracy on a common
eligible subset is accompanied by coverage of the original matrix. Full runs
are executed in GitHub Actions. Local checks use source inspection, small
artificial examples and already generated aggregate reports.

The method and evidence can therefore support a sequence of scoped statements:
an observation contract, a target certificate, a law-preserving implemented
reduction, an uncertainty statement under a sampling model, and an independently
validated prediction for a declared operation. Each statement needs its own
evidence; none alone establishes the entire sequence.

The [original-model specification](ORIGINAL_MODEL_NO_ML_SPECIFICATION.md) maps every
G/R/P/Φ entity and every M7 probability to code, data and declared assumptions.
M7 uses a fixed two-path model and does not pass its preserved full dependency
graph or sync/async edge types to the solver. Its restrictions cannot be
attributed to the whole original formalism. The historical combined loader
preloads evaluator data; new forecasts require the isolated learner-only path.
