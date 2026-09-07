# A changed target exposure can separate equal calibration means

Mathematical note recorded before the M9P main evaluation. This is not a new
experiment, a change to M9P marginalization, or a claim that its target exposure
actually changed. It makes precise the final qualification in
[M9P_CALIBRATION_IDENTITY.md](M9P_CALIBRATION_IDENTITY.md).

Changing an input distribution while retaining the conditional output law is
the established covariate-shift setting. Importance weighting and suitable
model selection already have a substantial literature; for example,
[Sugiyama, Krauledat and Müller (2007)](https://jmlr.org/papers/volume8/sugiyama07a/sugiyama07a.pdf).
The identities below are elementary probability calculations, not a claim of a
new adaptation method or of that paper proving this study's live assumptions.

## Identity and bound

Let `Z` describe the context over which a marginal forecast is averaged,
including relevant health state and age. Fix two conditional prediction
functions `f(Z)` and `s(Z)` in `[0,1]`. Let `μ` and `ν` be the calibration and
target context distributions, and put `δ=f-s`, `ε=E_μ δ`. Then

```text
E_ν f - E_ν s = ε + ∫ δ d(ν-μ).
```

Thus equal calibration-weighted means (`ε=0`) do not imply equal target means.
With total variation defined as `TV(μ,ν)=sup_B |μ(B)-ν(B)|`,

```text
|E_ν δ - ε| ≤ TV(μ,ν) · (sup δ - inf δ),
```

where the extrema can be taken over the combined support, or replaced by valid
uniform bounds there. To prove the inequality, the positive and negative parts
of the signed measure `ν-μ` each have mass `TV(μ,ν)`. Bounding the two integrals
by the extrema of `δ` gives both signs of the inequality. The two-context
example below attains it.

The identity holds for fixed prediction functions and measures. For either
target mean to represent actual request success additionally requires the
appropriate conditional semantic law. In particular, a deployment or failure-
policy intervention can change `Pr(success | Z)` as well as the distribution
of `Z`; covariate reweighting alone then need not transport the outcome.
An advance forecast also needs a defensible target distribution available
before observing test health. Using realized test covariates gives a
conditional or retrospective quantity with a different information boundary.

## A sharp two-context illustration

Suppose context 0 has conditional success `a`, context 1 has success `b`,
with the same conditional law in calibration and target populations. The
calibration context weights are `(w,1-w)` and the target weights `(v,1-v)`.
If only the exact calibration mean `A=w a+(1-w)b` is observed and `0<w<1`,
the compatible conditional rates satisfy

```text
a_min = max(0, (A-(1-w))/w),    a_max = min(1, A/w),
b = (A-w a)/(1-w).
```

Therefore the target mean is the linear function

```text
A_target = [(1-v)/(1-w)] A + [(v-w)/(1-w)] a.
```

Its exact identified interval has endpoints obtained by substituting
`a_min` and `a_max` and ordering the results. Every intermediate value is
attainable. If `v=w`, the interval reduces to `A`. If a context is absent in
calibration, its target rate is unconstrained: for `w=1` the interval is
`[v A, v A+1-v]`, and for `w=0` it is `[(1-v)A, (1-v)A+v]`.

Take the artificial values `w=0.5`, `A=0.5`, `v=0.1`. The marginal observation
alone leaves the target in `[0.1,0.9]`. With additional context-specific outcome
information `a=0.2`, `b=0.8`, it becomes `0.74`. Reversing those conditional
rates preserves the calibration mean but instead gives target `0.26`.

For `f=(0.2,0.8)` and the constant comparator `s=(0.5,0.5)`, calibration means
agree. The target mean difference is `0.24`, attaining
`TV·osc(δ)=0.4·0.6`. Under the stated true conditional law, the marginal Brier
score at the correct target mean is `0.74·0.26=0.1924`, compared with `0.25`
at the unchanged mean 0.5. The difference `-0.0576` is the squared mean-bias
correction, from `E[(p-Y)^2]=A_target(1-A_target)+(p-A_target)^2`.

This illustration establishes a role for context-specific information. It does
not establish superiority of a temporal or architectural model: a stratified
endpoint estimate reweighted with the same context information also gives
0.74 at the population values. Any future comparison must include that matched
reference, charge the target-distribution information, and propagate sampling
uncertainty in the conditional rates and target weights.

## Consequence for the current study

M9P evaluates its frozen learner-weighted marginal forecast, not a prospectively
specified exposure-transfer task. A small marginal difference there cannot
establish that timing information is useless under every target exposure.
Conversely, a conditional score improvement cannot establish a useful
advance-forecast gain under a different exposure. The example specifies why
those claims are distinct and what additional information a later study would
need. It does not authorize changing the pending comparison or adding samples.
