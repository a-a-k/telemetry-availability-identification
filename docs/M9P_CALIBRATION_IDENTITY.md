# Why a temporal curve can improve conditional scores without changing a mean forecast

This algebra was recorded during the separate no-fit preflight, before any new
confirmation fit or evaluation. It explains a limitation of the specified M9N/M9P
marginalization, without asserting a result for the new campaigns.

## Intercept score equation

Consider the stable one-path calibration requests. Write their binary outcomes
as `y_i`, the fixed baseline residual probability as `q`, and the route response
as `z_i = sigmoid(beta0 + beta1*x_i)`, where `x_i = log(1 + age_i)`.
The specified Bernoulli probability is `p_i = q*z_i`.

At an interior optimum, the derivative of the log likelihood with respect to
the intercept is

```
sum_i (y_i - q*z_i) * (1-z_i)/(1-q*z_i) = 0.
```

This follows by differentiating `p_i`: its intercept derivative is
`q*z_i*(1-z_i)`, and the Bernoulli derivative with respect to `p_i` is
`(y_i-p_i)/(p_i*(1-p_i))`. The expression applies to finite logits, a fixed
`0 < q <= 1`, and an unconstrained stationary intercept. Active parameter bounds,
probability clipping and numerical stopping can invalidate an exact equality.

When `q=1`, the weights cancel. Therefore the temporal model's mean fitted
one-path probability equals the empirical one-path success fraction. A fitted
state-only intercept has the same mean. Provided the same stable calibration
covariates are used for marginalization, both methods then produce the same
marginal forecast, even if the temporal slope materially improves conditional
predictions. The equality does not assert equality of individual probabilities,
conditional likelihoods or held-out conditional scores.

For a state-only intercept, `z_i=z` is constant, so the common positive weight
also cancels when `q<1`. Thus `q*z = mean(y)` whenever that solution is inside
the allowed parameter bounds. An empirical success fraction above `q`, for
example, cannot yield such an interior solution.

For a temporal curve with `q<1`, the weights vary. Let `r_i=y_i-q*z_i`. The
intercept equation can equivalently be written

```
mean_i r_i = (1-q) * mean_i [z_i*r_i/(1-q*z_i)].
```

Consequently the ordinary residual mean need not vanish. Near-unity `q` alone
does not supply a uniform small-error bound: `1-q*z_i` may also be small. If an
explicit bound `z_i <= z_max < 1` holds, then

```
abs(mean_i r_i) <= (1-q)*z_max/(1-q*z_max),
```

using `abs(r_i)<=1`. This is a conservative algebraic bound, not a claimed
precision guarantee for the experiment. M9P does not replace its fitted
predictions or registered intervals with this bound.

## Relation to the matched endpoint

Let `n_j` and `s_j` be stable calibration attempts and successes with `j` usable
paths, for `j=0,1,2`, and let `N=n_0+n_1+n_2`, `S=s_0+s_1+s_2`.
The specified model assigns probability zero with neither path up and `q`
with both paths up. With an interior state-only fit and `n_1>0`, its marginal
probability is

```
A_state = (q*n_2 + s_1)/N.
A_state - S/N = (q*n_2 - s_2 - s_0)/N.
```

The matched stable endpoint is the Jeffreys estimate `(S+0.5)/(N+1)`.
Its difference from the empirical mean is `(0.5-S/N)/(N+1)`, whose absolute
value is at most `0.5/(N+1)`. Therefore, if the both-up and neither-up states
behave exactly as the specified model assumes, the state-only model equals
the empirical stable endpoint, and differs from its Jeffreys version only
by that finite-sample adjustment. With `q=1`, the same statement applies to
an interior temporal fit. Deviations can arise from state-specific residual
behavior, successes in the neither-up state, bounds or numerical effects.

These identities use the exact same stable subset and calibration exposure
weights. They do not equate the all-calibration endpoint with a stable-subset
estimate. Transition filtering, initial-episode censoring and ordinary-health
inputs can change both the selected response mean and its information cost.

## Scope of the implication

M9P's primary marginal probability averages over the same campaign's learner
covariates and predicts the held-out stable response mean. It does not
prospectively predict a different age/exposure distribution. A temporal curve
may contain useful conditional information while adding little to this
particular mean prediction. That combination is mathematically compatible.

Changing exposure weights can break the equality. If learner and target
age distributions differ, matching the learner response mean does not force
matching a target-weighted forecast. Assessing such a benefit would require
an independently specified target distribution and validation; a conditional
score using observed test health cannot establish that advance-forecast claim.

The identities justify retaining matched endpoint and state-only controls.
They neither resolve the independent PMX comparison nor prove that topology is
unnecessary for a different prediction target, deployment intervention or
failure-law transfer.
