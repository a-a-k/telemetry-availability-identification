# Two-path observable bounds when B2 independence assumptions are relaxed

Status: mathematical preparation, independent of pending M9P outcomes. No
estimator or frozen experiment is changed. These elementary probability bounds
are not proposed as a novel union formula or a new general optimization method.
Atom-based probability bounding and its linear-programming formulation are
established work; see the primary treatment and historical references in
[Boros and Lee, arXiv:2110.10672v4](https://arxiv.org/html/2110.10672), and
[Prékopa (1990)](https://pubsonline.informs.org/doi/10.1287/opre.38.2.227).
The purpose here is to state the precise assumptions needed by the study's
two-path observable target, with an explicit proof in this restricted setting.

## Common observation measure

Let `H_a,H_b` be health events and `P_a,P_b` path-up events, with
`P_a` contained in `H_a` and `P_b` contained in `H_b`. Write

```text
h_a = Pr(H_a),  h_b = Pr(H_b),  h_ab = Pr(H_a ∩ H_b),
p_a = Pr(P_a),  p_b = Pr(P_b),  h_union = h_a + h_b - h_ab.
```

All probabilities refer to the same population and weighting of times or
requests. Different health-tick and request-weighted estimands cannot be
substituted into the formulas without an additional correspondence argument.
The observable values must be feasible:

```text
0 ≤ h_a,h_b ≤ 1,
max(0,h_a+h_b-1) ≤ h_ab ≤ min(h_a,h_b),
0 ≤ p_a ≤ h_a,  0 ≤ p_b ≤ h_b.
```

The target in this note is the static route union `A = Pr(P_a ∪ P_b)`. It is
not automatically checkout's semantic-request success, where repeated calls,
router state, failover age and response semantics require their own model.

## Proposition 1: only containment is assumed

Under the common-measure and containment conditions above, with otherwise
arbitrary dependence, the exact identified interval is

```text
max(p_a, p_b, p_a+p_b-h_ab) ≤ A ≤ min(p_a+p_b, h_union).
```

Both endpoints and every value between them are attainable while preserving
the five observable probabilities.

Proof. Put `J=Pr(P_a ∩ P_b)`. Containment gives
`J≤min(p_a,p_b,h_ab)` and `P_a∪P_b` contained in `H_a∪H_b`, hence
`J≥max(0,p_a+p_b-h_union)`. Subtract these bounds from `p_a+p_b`.

For attainability, partition the health space into disjoint masses
`h_10=h_a-h_ab`, `h_01=h_b-h_ab`, `h_11=h_ab`, and
`h_00=1-h_union`. Let `α` and `β` be the amounts of `P_a` and `P_b`
placed inside the shared `H_a∩H_b` cell. Their feasible ranges are

```text
max(0,p_a-h_10) ≤ α ≤ min(p_a,h_ab),
max(0,p_b-h_01) ≤ β ≤ min(p_b,h_ab).
```

Inside that cell, two subsets with masses `α,β` have attainable intersection
range `[max(0,α+β-h_ab), min(α,β)]`. The remaining path masses fit in the
exclusive health cells by construction. Choosing the upper endpoints of `α,β`
attains `J=max possible=min(p_a,p_b,h_ab)`. Choosing their lower endpoints
attains `J=min possible=max(0,p_a+p_b-h_union)`. Splitting the health cells
into finitely many atoms realizes these constructions. Convex mixtures of the
two joint laws preserve the five observables and attain every intermediate
target value. No independence assumption was used.

This bound handles zero health directly. For example, `h_a=0` forces
`p_a=h_ab=0`, and both target endpoints equal `p_b`. A numerical epsilon
denominator is not part of this population argument.

## Proposition 2: the communication vector is independent of health

Now assume `P_a=H_a∩C_a`, `P_b=H_b∩C_b`, and the vector `(C_a,C_b)`
is independent of `(H_a,H_b)`. Allow arbitrary dependence between `C_a`
and `C_b`, and let `h_a,h_b>0`. Then `c_a=p_a/h_a`, `c_b=p_b/h_b`,
and the exact interval becomes

```text
p_a+p_b - h_ab·min(c_a,c_b)
    ≤ A ≤
p_a+p_b - h_ab·max(0,c_a+c_b-1).
```

Proof. The communication intersection probability ranges sharply between
`max(0,c_a+c_b-1)` and `min(c_a,c_b)`. For any value in this range, construct
the corresponding two-Bernoulli communication law independently of the fixed
health law. Then `J=h_ab·Pr(C_a∩C_b)`, giving both endpoints and the full
interval. This is a restriction of Proposition 1's feasible law class.

If communication events are additionally mutually independent, the interval
reduces to the B2 target functional discussed in
[`B2_OBSERVABLE_TARGET_NOTES.md`](B2_OBSERVABLE_TARGET_NOTES.md):

```text
A = p_a+p_b - h_ab·(p_a/h_a)·(p_b/h_b).
```

This last conclusion identifies the target under extra assumptions. It does
not derive the independence assumptions from the five observed probabilities.
When joint path-up probability is itself observed on the common population,
`A=p_a+p_b-Pr(P_a∩P_b)` instead follows directly, without either independence
condition. That is a different information contract.

## Same observables, different assumptions

Take `h_a=0.8`, `h_b=0.7`, `h_ab=0.6`, `p_a=0.6`, `p_b=0.35`.
Then `h_union=0.9`, `c_a=0.75`, and `c_b=0.5`.

| Assumptions beyond the five observables | Identified static route target |
|---|---|
| Path containment only | `[0.60, 0.90]` |
| Communication vector independent of health | `[0.65, 0.80]` |
| Also independent communication events | `0.725` |

The narrower values arise from stronger restrictions on dependence. Increased
precision under those restrictions is not evidence that the restrictions are
correct. None of these numbers is a result from M7 or M9P.

## Sampling uncertainty and a small exact atom formulation

There are nine feasible binary assignments `(H_a,H_b,P_a,P_b)` satisfying
`P_a≤H_a` and `P_b≤H_b`: one in health cell 00, two each in 10 and 01,
and four in 11. Put a nonnegative probability on each atom and constrain their
sum to one. The five observables and the union target are linear functions of
these nine masses. Minimizing and maximizing the union under equality
constraints therefore gives Proposition 1's interval directly.

If simultaneous confidence constraints for the five population moments have
coverage at least `1-α`, replace the five equalities by those constraints and
optimize over the resulting atom set. Whenever the true moments satisfy the
constraints, the true atom law is feasible, so the target interval contains
the true static-route probability. This is a conditional coverage implication,
not a claim that a particular live confidence procedure has that coverage.
An empty feasible set must be reported, not silently repaired by unrelated
clipping. Numerical uncertainty in optimization also needs an explicit bound
before calling an implementation conservative.

Temporal dependence does not invalidate these population event identities;
it can invalidate a sampling procedure that treats repeated ticks as iid.
Informative missingness can also change the moments being estimated. The M5
results remain relevant to those two issues. General graphs require many more
atoms; the nine-variable construction is specific to this two-path example
and does not establish a scalable general graph procedure.

A bounded local algebra check compared the closed-form first interval with
both optima of the nine-atom LP for six artificial probability vectors,
including zero health, disjoint health, complete health and the table above.
All endpoint differences were below `1e-12`. This check used no campaign data
and does not replace the attainability proof.

These propositions supply a small assumption ledger and attainable ambiguity
examples for the article's target-identification argument. They are not
implemented as a new live predictor or added retrospectively to the M9P
comparison family.
