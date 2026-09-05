# M7C-R resource recovery after the predeclared stopping condition

## Why a revision is required

The complete M7C run reached its intended stopping condition: every one of the
64 acquisition cells passed, 900 seconds and a one-second transition guard were
selected, but none of 10, 15, 20, 30, or 40 repetitions could guarantee a
two-sided 0.015 half-width for the noisiest individual application--placement--
law cell. The worst one-sided planning standard deviation was 0.1980 and the
40-pair projection was 0.0633.

The original protocol explicitly permits either a larger resource budget or a
narrower claim after this outcome, followed by a documented rerun of the full
pilot analysis. It does not permit weakening a gate in order to obtain a
favorable method result. No M7 method has been fit and no M7 outcome exists at
the time of this revision.

## Narrowed estimand, unchanged precision threshold

M7C-R drops the claim that every one of 16 live cells will estimate its own
calibration-to-test mean to within 0.015. Those cell-specific results will be
reported with their intervals and interpreted descriptively.

The primary live method contrast is instead an equally weighted macro-average
over all 16 application--placement--law strata. This is aligned with the
predeclared primary proposed-minus-B2 contrast: methods are paired on the same
campaigns, then operation results are averaged within a stratum and strata are
given equal weight. Request volume cannot silently reweight the two systems or
the four laws. Application-specific and cell-specific contrasts remain visible
secondary results and cannot replace the macro result if they disagree.

The target two-sided 95% half-width remains exactly 0.015. Candidate balanced
budgets remain 10, 15, 20, 30, and 40 pairs per stratum.

## Predeclared macro-variance calculation

Let `s_j^2` be the four-pair sample variance of the same pilot planning proxy in
stratum `j`: test-minus-calibration semantic endpoint rate. For `J=16` equally
weighted strata, the estimated variance of one balanced macro repetition is

~~~text
V = sum_j s_j^2 / J^2.
~~~

Heterogeneous stratum variances are retained. A Welch--Satterthwaite effective
degree of freedom is

~~~text
nu = V^2 / sum_j ((s_j^2 / J^2)^2 / 3),
~~~

where three is the within-stratum pilot degree of freedom. The one-sided 90%
upper planning variance is `V * nu / chi2_0.10(nu)`. For candidate `n`, the
projected standard error divides its square root by `sqrt(n)` and the 95%
half-width uses a Student critical value with `J*(n-1)` degrees of freedom. The
smallest candidate meeting 0.015 is selected.

This calculation concerns a balanced macro endpoint proxy. It is neither a
power calculation nor an estimate of the future method contrast. Independent
campaigns, not requests or health ticks, remain the repetition unit.

## Immutable inputs and acceptance

The recovery workflow downloads all cell artifacts from M7C run 33977809019,
re-executes the original aggregate, and requires:

- all original technical quality counts except the expected design-selection
  failure to equal zero;
- exactly the original stopping condition, with duration and guard already
  selected and repetition budget unselected;
- one source run and commit `5ee628d448a63b313a6f950002ae50e105dc8270`;
- an exact SHA-256 match to the original machine-readable recommendation;
- all 16 strata and four pilot pairs per stratum;
- an admitted macro repetition candidate.

The recovery produces a new selected-design hash. It never edits the original
recommendation, raw cells, threshold, candidate grid, failure schedules, or
endpoint observations.

## Interpretation boundary

Passing M7C-R would justify a resource budget for one predeclared balanced macro
contrast. It would not justify precise conclusions for an individual law or
application, validate a model, or show that the endpoint proxy matches the
variance of proposed-minus-B2. The main report must show heterogeneity and all
cell intervals even if the macro-average is favorable.
