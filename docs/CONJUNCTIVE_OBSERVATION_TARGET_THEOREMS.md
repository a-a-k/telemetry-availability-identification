# Target identification under conjunctive observations

Status: restricted mathematical development. This note formalizes the observation
law behind M0/M2 and extends the target argument to finite polynomials, including
Boolean reliability targets. It does not change any frozen experiment or assert
novelty for log-linear identification. Log transforms of delivery probabilities,
rank conditions, and inseparable combinations are established in network
tomography; see [Bu et al., SIGMETRICS 2002, Section 3](https://nickduffield.net/download/papers/Bu_tomography_02.pdf)
and [Ma et al., IMC 2013, Sections 1–2](https://www.commsp.ee.ic.ac.uk/~wiser/publications/Liang/NetworkTomography-IMC13.pdf).
Monomial maps and log-linear models also belong to established algebraic
statistics; [Geiger, Meek and Sturmfels, 2006, Section 2](https://math.berkeley.edu/~bernd/AOS0092.pdf)
provides that background. The explicit propositions below are proved here for
this study's observation contract; those sources are not claimed to state this
exact application result.

The overlapping two-path ambiguity example also has a direct predecessor in
[Duffield, 2006, Sections 1.2–1.3](https://nickduffield.net/download/papers/D06-binary.pdf):
separate path-success rates preserve a multiplicative ambiguity, whereas
correlated measurements can distinguish a shared component. It should be used
here as an explanation of the observation boundary, with that attribution.

## Model and information boundary

Let independent Bernoulli primitives `X_1,...,X_d` have probabilities
`p=(p_1,...,p_d)` in a nonempty open product box contained in `(0,1)^d`.
For known sets `A_i`, the potential observations are conjunctions
`Y_i=∏_{j∈A_i}X_j`. A known observation mask is independent of the primitive
state and has a fixed distribution not depending on `p`. Only coordinates
allowed by a realized mask are observed.

Include every nonempty subset `J` of observations jointly available with
positive mask probability. Its joint success moment is

```text
m_J(p) = E[∏_{i∈J}Y_i] = ∏_{j∈union_{i∈J} A_i}p_j.
```

Let `H` contain the distinct incidence vectors of those primitive unions.
Write `θ=log p`; then `log m=Hθ`. If no observation is supported, `H` has
zero rows and `d` columns. Empty-subset moments are one and need no row.

The common population and state-independent mask are essential. Unknown
informative missingness, conditional exposure depending on hidden state,
nonconjunctive observations, dependencies between primitives, or extra equality
constraints on `p` require a different argument. Finite-sample estimates need
not obey the exact population moment identities.

## Proposition 1: complete supported moments determine the observation law

Two interior parameter vectors have the same masked-observation law if and only
if `H log p = H log p'`.

Proof. Equality of the observation law implies equality of every supported
joint success moment, since the corresponding mask events have positive fixed
probability and are independent of the state. Conversely, for any supported
mask `S` and positive coordinates `J⊆S`, the probability of a binary pattern is

```text
Pr(Y_J=1, Y_(S\J)=0)
    = Σ_(K⊆S\J) (-1)^|K| m_(J∪K).
```

Thus the complete supported moments recover every conditional pattern law.
Multiplying by the fixed mask probabilities recovers the full observation law.
Since all primitive probabilities are positive, equality of the monomial
moments is equivalent to equality of their logarithms. This establishes the
claim. Truncating `H` to selected moment orders may lose the converse.

Consequently an observational equivalence class is the intersection of
`θ+ker H` with the open log-parameter box. This describes population ambiguity,
not a confidence region or a fitted likelihood's numerical condition number.

## Proposition 2: exact global criterion for polynomial targets

Let a target be a finite polynomial with like terms already collected,

```text
F(p) = Σ_(α∈E) c_α p^α,    p^α = ∏_j p_j^(α_j),
```

where the exponent vectors `α` are distinct nonnegative integer vectors and
every retained coefficient `c_α` is nonzero. Then `F` is determined by the
observation law throughout the open parameter box if and only if every
`α∈E` belongs to the real row space of `H`.

Sufficiency. For each `α`, choose `a_α` such that `H^T a_α=α`. Then

```text
F(p) = Σ_α c_α exp(a_α^T log m) = Σ_α c_α ∏_r m_r^(a_α,r).
```

This is a function of supported population moments. Different valid choices
of `a_α` agree on the model's feasible moments. Coefficients and powers can be
negative; empirical moments near zero can make this expression unstable.

Necessity. If `F` is constant on every observational fiber, then, for every
`v∈ker H`, the derivative along `θ+t v` is zero at every point of the open
log box:

```text
0 = Σ_α c_α (α^T v) exp(α^T θ).
```

Distinct multivariate exponentials are linearly independent on an open set.
One proof chooses a direction `w` avoiding the finitely many hyperplanes
`(α-β)^T w=0`; restriction to a sufficiently short line inside the set gives
univariate exponentials with distinct exponents. Successive derivatives form
a nonsingular Vandermonde system, so all coefficients vanish. Hence
`c_α(α^T v)=0` for every `α` and `v∈ker H`. Since `c_α≠0`, each exponent is
orthogonal to `ker H`, equivalently in `row H`.

If some exponent fails the condition, a kernel direction has a nonzero
directional-derivative polynomial. It is nonzero somewhere in any open box,
giving two nearby interior vectors with exactly the same observation law and
different targets. This proves failure of **global** identification. It does
not assert that a chosen direction changes the target at every supplied point,
or that every exceptional fiber is ambiguous. A single zero numerical gradient
is not an identification certificate.

Any Boolean target `g(X)` has a unique multilinear probability polynomial under
independent primitives, obtained by expanding

```text
F(p) = Σ_(x∈{0,1}^d) g(x) ∏_j p_j^(x_j)(1-p_j)^(1-x_j).
```

Thus Proposition 2 gives a complete global target criterion for arbitrary
Boolean **targets** under the stated conjunctive **observation** contract. It
is not a complete criterion for arbitrary Boolean observation maps. Expanding
a general truth table can require `2^d` coefficients; the proposition alone
does not supply a scalable graph algorithm.

## Examples and necessary distinctions

**Disjoint paths without joint observations.** Suppose only `p_1 p_2` and
`p_3 p_4` are observed. The route union has polynomial
`p_1p_2+p_3p_4-p_1p_2p_3p_4`. Its three exponents are the two rows of `H`
and their sum, so the target is identified as `m_1+m_2-m_1m_2`, although no
individual primitive is identified. This conclusion uses primitive independence.

**Shared path without versus with joint observations.** With only moments
`p_1p_2` and `p_2p_3`, the union target includes the additional monomial
`-p_1p_2p_3`, whose exponent is outside the two-row span. The union is not
globally identified. If both conjunctions are observed together, their joint
moment adds row `(1,1,1)` and identifies the union directly. It also identifies
all three primitive probabilities in the interior. Marginal moments alone and
synchronous observations are different information contracts.

**Identification beyond duplicate-column grouping.** For marginal moments
`m_1=p_1p_2`, `m_2=p_2p_3`, `m_3=p_3p_4`, all four columns of `H` are
different and its rank is three. Yet the target `p_1p_4=m_1m_3/m_2` is
identified. The row combination is `(1,-1,1)`. A compiler that only merges
identical columns is a sufficient law-preserving reduction, not the complete
space of identifiable functions.

**A stationary point is not a proof.** If the sole observation is `p_1p_2`,
the OR target is not identified. At `(1/2,1/2)`, its derivative along the
log-kernel direction `(1,-1)` is zero. Nevertheless `(1/2,1/2)` and
`(2/5,5/8)` both give observed moment `1/4`, while their OR probabilities
are `3/4` and `31/40`. A first-order diagnostic at that point misses the
change along the same fiber.

**An observed OR is outside this theorem's observation family.** If the only
observation is `X_1∨X_2`, its success probability is directly identified.
Applying the conjunctive `H` criterion to its polynomial terms as if they were
separately observed would be invalid. M3's Boolean observation certificates
therefore remain a separate analytic argument.

Zero/one parameter boundaries and constrained parameter spaces also need
separate treatment. For example, observing `p_1p_2=1` on the closed unit box
forces both probabilities to one even though the interior model is ambiguous.

## Proposition 3: duplicate-membership products preserve the full law

Partition active primitives by their identical membership columns across all
retained conjunction observations. For each group `G`, define the random
variable `Z_G=∏_(j∈G)X_j` and probability `q_G=∏_(j∈G)p_j`. The groups
are disjoint, so their variables are independent Bernoulli variables. Every
retained observation includes either the entire group or none of it and is
therefore exactly a conjunction of the corresponding `Z_G` variables.

This is a pointwise equality of observation maps, hence preserves the complete
masked-observation distribution and its exact likelihood under Proposition 1's
mask assumptions. Primitives with zero membership affect no observation and
integrate out. With independent primitive box constraints, each product's
image is the interval between the products of the group bounds, and every
value in the interval is attainable. Since the groups are disjoint, their
joint feasible image is the product of those intervals. Matched original and
reduced likelihood optimization therefore has the same attainable objective
values, provided the reduced model uses that exact image and no extra prior or
penalty. Optimizer convergence is a separate implementation issue.

Targets involving a proper part of a merged group are not automatically
preserved. Target certificates must be kept separately, and the product rule
does not remove every other rank deficiency or latent equivalence. These are
the limits relevant to M2's preserved negative controls.

## What this establishes for the article

The results separate three claims: a complete observation-law representation in
a restricted family, an exact target criterion within that family, and a
sufficient concrete likelihood-preserving reduction. They establish neither
uncertainty calibration under dependent telemetry nor semantic adequacy of a
static route for live checkout. M4/M5 and M9K–P address different questions.
An exact rational reference can certify the row-space algebra without treating
a floating-point rank tolerance as a proof; finite numerical predictions still
need their own stability and uncertainty analysis.

## Exact reference and bounded verification

`telemetry_availability.polynomial_identification` implements a separate exact
reference. `boolean_probability_terms` expands a supplied complete truth table
by an integer Boolean-lattice transform. `certify_polynomial_target` accepts
declared monomial moment exponents and canonical integer polynomial coefficients.
It returns rational row combinations for supported terms or an exact null
direction for an unsupported term. It does not infer whether supplied moments
are actually observable, fit campaign data, or amend historical compiler outputs.

Seven unit tests check all 16 two-primitive truth tables against independent
atom expectations at two rational parameter vectors, validate the returned
row/null certificates directly, and exercise the disjoint/shared path examples,
distinct-column reduction limit, stationary-point counterexample, zero/duplicate
rows, fractional row combinations and invalid inputs. These are bounded
algebra checks. They do not establish runtime scalability or a new empirical
milestone, and no live comparison includes this reference retrospectively.
