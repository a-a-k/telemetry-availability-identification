# M9K: checkout overprediction localization

## Outcome

M9K is complete. The first and only accepted workflow attempt passed all three
jobs and selected the frozen machine branch
`checkout_overprediction_localized_to_fault_period_route_up_residual_mismatch`.
On the 40 predeclared OpenTelemetry Demo checkout campaigns, the retained mean
prediction--observation gap is `+0.173061`. Its exact decomposition is:

| Test component | Mean | Stratified bootstrap 95% interval |
|---|---:|---:|
| route-state exposure | +0.000917 | [-0.003456, +0.005177] |
| route-up residual invariance | +0.180031 | [+0.172425, +0.187534] |
| route-down success offset | -0.007888 | [-0.008895, -0.006958] |
| total frozen prediction minus observation | +0.173061 | [+0.164809, +0.181159] |

Thus the overprediction is not primarily explained by fitting a stationary
route probability that differs from request-time route exposure. It enters at
the boundary where the clean-baseline residual `q` is carried into fault-period
requests whose full binary health state says at least one target-replica path is
up. That component is positive in all 40 test campaigns and exceeds the
route-state component by `+0.179115` with bootstrap interval
`[+0.170200, +0.188340]`.

The same distinction is already present in learner calibration data. The
calibration route-up residual component is `+0.177614`, interval
`[+0.168564, +0.186999]`, and is positive in all 40 campaigns. Its route-state
component is `-0.000246`, interval `[-0.003203, +0.002636]`. This corroboration
rejects an explanation based only on calibration-to-test drift, while not
turning the post-M7 diagnostic into confirmatory accuracy evidence.

M9K localizes a representation/conditional-invariance boundary; it does not
identify a unique physical cause. In particular, retained aggregate health
alone cannot distinguish a request being routed to the unavailable replica,
load-balancer/backend-state lag, an omitted checkout dependency, an internal
application failure, overload, or timeout propagation. The frozen next branch
is therefore `m9l_checkout_route_up_failure_cause_discrimination`.

## Implementation and execution

- frozen implementation and protocol commit:
  [`9b69491a1e0ca76e6a656aae977c1c5c2b8e3d88`](https://github.com/a-a-k/telemetry-availability-identification/commit/9b69491a1e0ca76e6a656aae977c1c5c2b8e3d88);
- accepted remote execution:
  [run 34055967110](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34055967110);
- run attempt: first attempt, started `2026-09-06T19:47:08Z` and completed
  `2026-09-06T19:48:54Z`;
- local verification before launch: 189 unit tests, repository/configuration
  validation, Python compilation, workflow parsing, and synthetic arithmetic
  and decision smokes.

The workflow used exactly three jobs, each with `timeout-minutes: 360`:

1. the retained-identity and target contract completed in 20 seconds;
2. the 40-cell evidence audit and decomposition completed in 53 seconds;
3. the frozen decision completed in 21 seconds.

Full artifact download, hashing, reconstruction, and 10,000-resample
stratified bootstraps ran only in GitHub Actions. Local execution did not read
the full preserved M7 archive. M9K invoked PMX zero times and performed no live
collection.

## Accepted artifacts

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m9k-checkout-contract-34055967110` | 9995961364 | 3,597 | `9e6d0c5435174469653f95d29194b8f34e5a95acf4ef58ab6e4363fe645cff47` | 2026-12-05 19:47 UTC |
| `m9k-checkout-localization-34055967110` | 9995975814 | 33,696 | `98b17af2b8555f8e58b3df4fa55ab046356f4ccdc07fb824d008feff0ec116af` | 2026-12-05 19:47 UTC |
| `m9k-checkout-decision-34055967110` | 9995981451 | 2,262 | `395a94a4625e060ee2b5b87d5f6ea3caa671519253745924cdcd2d5f6cb3f5df` | 2026-12-05 19:47 UTC |

GitHub reports all three artifacts as unexpired and associates them with the
frozen commit and accepted run. The principal uncompressed identities are:

| File | Bytes | SHA-256 |
|---|---:|---|
| `contract-manifest.json` | 6,503 | `0861b8ec0bc889d0931b15419f605dbdba1e68f24406a8e0c6d67a55c3760f78` |
| `localization-manifest.json` | 4,418 | `d650993388103ef37486e4ca5938d9fa95a6da5bddfb9f7d29d12ff5e1aaca8b` |
| `cell-decomposition.csv` | 24,437 | `346ea85092af6c2ecf059455643a1be9a8690dbcf3b22b9c434aaf19a0999b82` |
| `period-state.csv` | 25,582 | `5dd518040ba697e06e398ae1e2cb2c74eda66b146e243f9f2939c785ec21bb2e` |
| `bootstrap-summary.csv` | 1,171 | `1710b7aaa008777e4f2741a6a97bdfd7eceeca85fe84a3b772bf31f63bb3c1b7` |
| `selected-file-audit.csv` | 56,541 | `daa78b1ee9d0b55731984c5a9f1f9bdf73d83bd398e22496515783c79b283a43` |
| `decision-manifest.json` | 2,132 | `c88a067948144f0096ce415fc0d730084f0c39552ebca2c549ad43f8f01c9f66` |

## Evidence and reconstruction checks

The contract revalidated the exact artifact IDs, run commits, compressed
digests, expiry, and locked manifest/table bytes for M8A, M8B, and M9J. It
reproduced the six-operation M8B ranking and the checkout cohort summary before
opening the preserved cell archive. The accepted inputs remained:

- profile `opentelemetry_demo`, operation `checkout`;
- placements `colocated` and `split`;
- noncommunication laws N and ND;
- repetitions 0--9, for 40 equally weighted campaigns;
- M7 method `proposed`, mode `sampled_mixed`, scope `current`, stable view.

The localization job then recorded:

| Check | Result |
|---|---:|
| qualified-manifest census | 160 |
| selected cells | 40 |
| selected files checked against M8A inventory | 360 |
| selected-file mismatches | 0 |
| frozen baseline-`q` mismatches | 0 |
| M8B reproduction mismatches | 0 |
| minimum request-to-health alignment | 1.000 |
| minimum stable requests in any cell-period | 874 |
| decomposition rows | 80 |
| maximum identity reconstruction error | 1.67e-16 |

The frozen mean prediction was `0.947019`; the stable test mean was `0.773959`.
The decomposition used exactly
`q*r_model-y = q*(r_model-r_obs) + r_obs*(q-y_up) - (1-r_obs)*y_down`
without refitting `q`, the route model, or any M7 score. All integrity and the
predeclared minimum-gap gates passed.

The result is consistent across the four fixed test strata. Mean route-up
residual components were `+0.1591` for colocated/N, `+0.1428` for
colocated/ND, `+0.1709` for split/N, and `+0.2474` for split/ND. The largest
remaining discrepancy is therefore split/ND, but M9L may use that ordering only
as a reported stratum fact, not to discard the other 30 campaigns or tune a
threshold.

## Interpretation with M9J

The two bounded tasks now have distinct answers:

- M9J explains why the original error-marked PMX control was silent in the
  tested binary: a detected marker is lost during a same-process child-to-parent
  merge, while placing the same marker on the surviving carrier activates the
  downstream failure transformation. This is scoped preprocessing/application
  cost and does not demote PMX or generalize to Palladio.
- M9K explains where the proposed model's checkout overprediction enters: not
  mainly through average route exposure, but through treating aggregate
  route-up as sufficient and carrying the clean residual probability into that
  state. This is not yet a unique physical-cause diagnosis.

Neither result demonstrates better predictive accuracy or lower end-to-end
automatic forecasting cost. Neither changes M7 predictions, resolves the full
article verdict, or transfers a MODELS review criterion into the SIMPAT study.
The defensible article position remains that the direction is substantive and
the specified-model calculation is supported, while the claimed advantage is
not established.

## Next milestone

M9L must discriminate causes inside the route-up residual using only evidence
that can identify them. The retained learner calibration table contains native
trace-derived target-replica assignments, while the held-out evaluator table
deliberately contains no trace graph. The next protocol will therefore freeze a
calibration-only request classification before reopening the 40 cell bundles:
target replica reached on an up path, target replica reached on a down path,
no target replica reached despite a linked trace, or no usable linked trace.
It will compare these classes with semantic success and preserve the unresolved
branch if trace support cannot separate routing from application/dependency
failure. It will not tune or replace the M7 prediction and will authorize no
new collection unless the retained-evidence discrimination proves impossible.

## Completion checks

- The checkout target, N/ND restriction, formula, thresholds, and branch rule
  were committed before the accepted run.
- The first attempt completed all three 360-minute-bounded jobs.
- All retained artifact identities and 360 selected cell files passed.
- The exact decomposition reconstructed every cell and reproduced M8B.
- Residual-invariance dominance and calibration corroboration passed the frozen
  bootstrap and sign rules.
- No PMX invocation, live collection, refit, revised prediction, or accuracy
  claim was made.
- The unique physical cause remains explicitly open and determines M9L.
