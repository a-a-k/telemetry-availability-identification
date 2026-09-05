# M1 exact observed-likelihood reference protocol

## Purpose

M1 introduces the article-design B3 reference: a standard numerical optimizer on
the exact observed-data likelihood of the same primitive-factor model and the
same masked episode records. It is a correctness and difficulty reference, not a
weaker model selected to make the log-moment method look favorable.

The compared methods are:

- `b2_log_moment`: the M0 weighted log-moment baseline with the predeclared
  minimum of 20 joint observations;
- `b3_exact_likelihood`: exact latent-state enumeration followed by bounded,
  analytic-gradient, multistart L-BFGS-B optimization.

No method receives latent states or generator probabilities during fitting.

## Exact likelihood

For each small family, all primitive binary states are enumerated independently
of the simulator's random draw path. They are deterministically mapped to
observable states. Records are compressed by their observation mask and observed
values. Conditional on the known state-independent mask, the likelihood of one
pattern is the sum of primitive-state probabilities compatible with that
pattern.

The optimizer uses parameter bounds `[1e-6, 1 - 1e-6]`, analytic gradients in
logit coordinates, three fixed starts (0.5, 0.8, and 0.95), and the preceding
nested-prefix solution as an additional warm start where available. All start
objectives, convergence, boundary contact, and near-optimal parameter spread are
diagnostic outputs. The lowest-objective successful start is selected; an
unsuccessful start cannot displace an equivalent converged solution by numerical
noise. Structurally unsupported individual estimates are withheld
even if a numerical optimizer selects one point on a likelihood ridge.

Target truth is independently evaluated by summing enumerated primitive-state
probabilities rather than invoking the product shortcut used by the original
model helper.

## Frozen matrix and outputs

The data matrix, seeds, family definitions, modes, repetitions, and nested sample
sizes are inherited unchanged from `configs/rq1_synthetic.yaml`. Methods operate
on the exact same generated campaign prefix.

Predeclared outputs are:

- convergence, boundary, multistart spread, runtime, and likelihood objective;
- individual parameter and target availability, MAE, and signed bias;
- false-confident estimate rate;
- within-campaign paired MAE difference, reported as B3 minus B2;
- compressed observed-pattern counts sufficient to reproduce the likelihood.

A negative paired difference favors B3. Win rates and raw differences are
descriptive in M1; simultaneous uncertainty and coverage are deferred to M3.
Runtime is diagnostic because shared GitHub runners are not a controlled
benchmarking environment.

## Interpretation rules

Agreement on well-observed identifiable cases is a correctness check, not an
original-method victory. Better likelihood accuracy would show the statistical
cost of the transparent moment baseline. Similar accuracy would narrow the case
for a more complex estimator to automation, ambiguity diagnostics, uncertainty,
or computational structure.

Trace-only and no-joint-health modes remain observation ablations, not competing
methods. Directly observed targets cannot establish counterfactual utility; M2
must introduce non-direct targets and placement transfer before model utility is
claimed.
