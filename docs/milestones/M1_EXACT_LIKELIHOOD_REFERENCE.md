# M1 report: exact observed-likelihood reference

## Status and evidence

Status: complete.

- Tested commit: `73bbac48703947b1e482f5098368d53d7841760e`.
- CI run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33958786457>.
- Diagnostic run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33958816128>.
- Full run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33958870916>.
- Aggregate artifact: `m1-aggregate-33958870916` (2,314,241 bytes; GitHub retention expiry: 2026-10-05).

The full manifest records a clean four-shard Linux run on the tested commit with
Python 3.13.15, NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2.

## What was implemented

M1 adds an exact observed-data likelihood reference for every M0 family and
observation policy. The implementation enumerates all primitive binary states,
maps them deterministically to observables, compresses records by mask and
observed-value pattern, and sums the probabilities of compatible states. Mask
probability is conditioned away because the M1 mechanism is known and
state-independent.

The B3 reference maximizes this likelihood with bounded multistart L-BFGS-B in
logit coordinates and an analytic gradient. It retains convergence, boundary,
objective, gradient, and near-optimal parameter-spread diagnostics. An
unsuccessful start cannot displace an objective-equivalent successful result.
Individual quantities unsupported by the empirical row space remain withheld
even when the optimizer selects a point on a likelihood ridge.

The original weighted log-moment estimator is explicitly labeled B2. B2 and B3
receive the same nested campaign prefixes. Target truth is evaluated through an
independent latent-state summation rather than the model's product shortcut.

## How it was evaluated

The predeclared M1 protocol was committed before the diagnostic and full runs.
The frozen M0 configuration was reused without changing seeds, family
probabilities, observation modes, sample sizes, or repetitions. The full run
produced:

| Table | Rows |
|---|---:|
| Method fits | 14,400 |
| Parameter and target evaluations | 90,000 |
| Compressed observation patterns | 52,943 |
| Method summary cells | 72 |
| Paired summary cells | 36 |

Every B3 fit used three fixed starts and, after the first nested prefix, the
preceding solution as a warm start. Paired MAE differences are computed within a
campaign as `B3 - B2`; negative values favor B3. These are descriptive effects,
not confidence intervals.

## Verification results

- No exact-likelihood optimization failed in 7,200 B3 fits.
- Whenever B2 supplied a complete parameter vector, there were zero cases where
  the selected B3 negative log likelihood exceeded the B2 candidate by more than
  `1e-6`.
- No method emitted a structurally unsupported individual parameter estimate.
- B3 statuses were 4,040 regular convergences, 765 boundary convergences, 1,795
  detected non-unique multistart solutions, and 600 expected no-observation cases
  for the health-only family under trace-only input.
- Median fit time was 0.00068 seconds for B2 and 0.00604 seconds for B3 on shared
  GitHub runners. The roughly nine-fold ratio is descriptive; both costs are
  negligible for these tiny graphs and shared runners are not controlled
  benchmarking hardware.

## Estimation results

With full telemetry, B2 and B3 were nearly equivalent. At sample size 2,000 the
parameter MAEs were:

| Family | B2 MAE | B3 MAE | Paired B3-B2 |
|---|---:|---:|---:|
| Communication bottleneck | 0.004006 | 0.003957 | -0.000049 |
| Mandatory fan-out | 0.003595 | 0.003600 | +0.000005 |
| Same-domain replicas | 0.004211 | 0.004211 | approximately 0 |
| Two-domain path | 0.004259 | 0.004131 | -0.000128 |

The same-domain full model is saturated by its three moments, so numerical
agreement is expected rather than evidence of B2 superiority.

Under staggered health observations, exact likelihood used incomplete records
more efficiently. At sample size 2,000:

| Family | B2 MAE | B3 MAE | B3 campaign win rate |
|---|---:|---:|---:|
| Communication bottleneck | 0.011087 | 0.007532 | 80.5% |
| Mandatory fan-out | 0.008344 | 0.004689 | 86.0% |
| Two-domain path | 0.017279 | 0.010235 | 86.0% |

For the two-domain path at size 100, the predeclared 20-observation threshold let
B2 estimate every structurally identifiable parameter in only 131 of 200
campaigns. B3 completed all 200 because it uses the exact record likelihood
without discarding a low-count pattern; among the 131 complete pairs, its mean
within-campaign parameter-MAE difference was -0.01931 and it won 84.0% of pairs.

Boundary solutions were common at size 100, especially for staggered health:
83.5% for the communication bottleneck, 85.5% for fan-out, and 91.5% for the
two-domain path. The configured primitive availabilities are high, so small
effective samples often contain no observed failure for one component. Boundary
contact is therefore a finite-data result to be covered by uncertainty analysis,
not an optimization failure.

For directly observed request-success targets, B2 and B3 target errors were
usually identical up to numerical precision. This confirms that a more complex
latent fit cannot manufacture information beyond a directly observed Bernoulli
outcome in the unchanged setting.

## Interpretation

M1 rejects a convenient but unsupported claim of universal estimator advantage.
B2 is effectively as accurate as the exact reference in saturated, fully
observed cases. B3 has a material advantage only where incomplete records contain
information that the thresholded moment procedure discards. This locates a real
mechanism for the later method: consistent use of heterogeneous partial records,
not comparison against trace-only input.

The multistart reference also independently exposes likelihood ridges in the
same-domain/no-joint-health and single-trace regimes, while the structural
diagnostic prevents arbitrary ridge points from being reported as recovered
causes.

M1 remains a correctly specified small-model experiment. It does not establish
novelty over standard likelihood optimization, counterfactual utility, interval
coverage, robustness to an incorrect observation model, scalability, or live
validity. M2 must therefore compare an identification-aware structured procedure
against B1-B3 on exactly the same likelihood and must attribute any statistical
agreement with B3 as expected.
