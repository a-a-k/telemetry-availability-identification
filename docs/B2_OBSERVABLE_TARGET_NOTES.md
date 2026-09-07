# Observable targets in the implemented B2 reference

Status: mathematical exposition of the existing frozen M7 reference, prepared
during M9P acquisition. This note changes no estimator, score or experiment.
It does not claim a new inclusion-exclusion identity or a general identification
procedure. The implementation anchor is `_route_estimates` and its helper
functions in `src/telemetry_availability/live_validation_analysis.py`, SHA-256
`0b58ddd271a6eccbdd3d1f2879fae6e333825c4a95f2667ad1ecb1d12c646132`.

## A two-replica observable functional

Let `H_a,H_b` indicate operational replica health and let `C_a,C_b` indicate
the residual usability of the two communication paths. Define usable paths
`P_a=H_a*C_a`, `P_b=H_b*C_b`, and a single logical demand's route response
`R=P_a OR P_b`. All expectations below refer to the same population and the
same eligible request-time distribution.

Suppose the pair `(C_a,C_b)` is independent of `(H_a,H_b)` and its coordinates
are mutually independent. The health coordinates may be dependent. Write

```
h_a = E[H_a],  h_b = E[H_b],  h_ab = E[H_a*H_b],
p_a = E[P_a],  p_b = E[P_b].
```

For positive `h_a,h_b`, route availability is the observable functional

```
A_R = p_a + p_b - h_ab * (p_a/h_a) * (p_b/h_b).
```

Indeed, `p_a=h_a*E[C_a]` and `p_b=h_b*E[C_b]`, while the assumptions give
`E[P_a*P_b]=h_ab*E[C_a]*E[C_b]`. Substituting into the two-event
inclusion-exclusion identity proves the result. The proof does not recover or
require a unique factorization of health dependence into hidden failure
parameters. Full independence of the communication variables is a sufficient
condition, not a necessary characterization of every law satisfying the final
moment equality.

Under independent health coordinates, `h_ab=h_a*h_b`, and the expression
reduces to `p_a+p_b-p_a*p_b`. The frozen implementation uses this independent
branch for split placement or a failure law without the common-domain factor.
For colocated common-domain laws it uses the joint-health expression when its
required empirical inputs qualify. These are assumptions of the specified
model; a placement label alone cannot establish independence in an arbitrary
deployment.

If `h_a=0`, path containment implies `p_a=0` and `h_ab=0`, so `A_R=p_b`
without identifying `E[C_a]`. The symmetric boundary is analogous. This
population extension is distinct from the implementation's finite-sample
epsilon denominator and clipping policy.

## Why the assumptions matter

The five listed moments are not sufficient under unrestricted communication
dependence. For example, let both replicas always be healthy and let each
path have marginal usability one half. Independent communication states give
route availability three quarters, whereas perfectly shared communication
states give one half. Both cases have identical `h_a,h_b,h_ab,p_a,p_b`.
This is a direct ambiguity witness for that observation set.

If the joint usable-path moment `E[P_a*P_b]` is also observed, the union is
identified directly without the residual-communication independence condition.
The implemented B4 takes a direct empirical union over complete health/path
ticks. Its empirical eligibility differs from B2's separate marginal and
joint-health requirements. A comparison must preserve those input policies
and cannot credit one method with another method's observation support.

More generally, with `k` usable paths `P_i=H_i*C_i`, mutually independent
residual communication variables independent of the entire health vector
give

```
Pr(any P_i=1)
  = sum over nonempty S of (-1)^(|S|+1)
      * E[product_{i in S} H_i] * product_{i in S} E[C_i].
```

If the needed health conjunction moments and positive health/path marginals
are observable, substituting `E[C_i]=E[P_i]/E[H_i]` identifies this target.
This ordinary inclusion-exclusion construction can require exponentially many
moments. It is not a scalability result, a necessary condition for target
identification, or the implementation of a general B2 network estimator.
Special structure may reduce the required moments; that reduction must be
proved for the actual structure.

## From a usable route to an operation outcome

An operation forecast `A_Y=q*A_R` requires a separate response assumption.
For example, it follows if success requires `R=1`, failures with `R=0` cannot
succeed, and `Pr(Y=1 | R=1, relevant covariates)=q` is invariant over the
target population. Estimating `q` from a baseline additionally requires
transporting that residual response law from baseline to the target period.

This assumption is stronger than correct topology discovery or correct
evaluation of a Boolean union. A checkout with several required downstream
calls, timeouts, persistent connections or age-dependent recovery need not
behave like one demand that succeeds whenever either backend is usable.
The retained M9K-M9N diagnostics examine precisely this response-model gap.
The algebra above cannot override those observations or certify the original
operation prediction.

The M9P temporal model explicitly conditions the one-path response on observed
episode age and changes the response model while retaining a restricted
single-operation target. Its mean-forecast relation to matched endpoint and
state-only controls is derived separately in `M9P_CALIBRATION_IDENTITY.md`.
Conditional response information and identification of a latent failure-factor
vector are different questions.

## Endpoint fallback and transfer are separate branches

When the required joint-health information is unavailable, the frozen B2 may
use `_route_mle`. That function estimates one route probability from the
qualifying calibration operation outcomes under their fixed baseline `q`
values. With one operation, a known positive `q`, and an interior solution,
the population identity is `A_R=Pr(Y=1)/q`. With several operations, the code
maximizes their shared-route Bernoulli likelihood. This is an outcome-based
fallback and depends on the same response-invariance assumption. It does not
identify the route from telemetry moments alone.

The implementation's transfer branch uses `1-(1-p_a)*(1-p_b)`. For a transfer
from a shared domain to independent domains, this is justified only if the
intervention preserves both usable-path marginals and makes the target path
states independent under the specified model. A new placement can also change
latency, load, path quality, failure marginals or remaining common causes.
Current-period observation equivalence does not identify that unrestricted
interventional distribution. The explicit restricted transfer design and its
evidence are documented in `milestones/M3_NON_DIRECT_PLACEMENT_TRANSFER.md`
and the M7 report.

M3 uses a different, explicitly calibrated two-domain synthetic design and
additional available-moment identities. Its B2 implementation is not the same
function as the frozen M7 live reference analyzed here. The shared comparator
label is not a basis for pooling their estimators or experimental results.

## Finite observations and measurement policy

The observable identities concern population probabilities. The live code
requires minimum marginal/joint counts, applies smoothed means, protects small
denominators and projects derived probabilities into `[0,1]`. Separate sampled
moments can be mutually inconsistent in finite data; those operations are a
specific estimation policy rather than an identification proof. Boundary
behavior, unsupported branches and uncertainty must be reported separately.

To consistently estimate the stated population moments, missingness and
sampling must preserve the relevant marginal and joint laws, or be accounted
for by a justified observation model. Individually observed marginals do not
by themselves reveal an unobserved joint moment. With temporal dependence,
an asymptotic frequency interpretation further needs an appropriate stationary
or otherwise justified averaging regime; an i.i.d. binomial error calculation
does not follow merely from the algebra.

Finally, uniform health-tick averages and request-arrival-weighted averages are
different estimands in general. Fixed offered load helps specify the design,
but actual dispatch delays, operation mixes, filtering and state-dependent
selection still need a common target definition. The stable-subset M9P analysis
states that target explicitly and uses campaign-level stratified uncertainty.
Neither a correct moment identity nor a narrow sampling interval resolves a
misspecified response model or an unjustified deployment-transfer assumption.
