# M0 report: conjunctive rank and log-moment slice

## Status and evidence

Status: complete.

- Tested commit: `dfee7db51d549bf5671b6e5aac51b848677ef391`.
- CI run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33956971692>.
- Diagnostic run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33957010919>.
- Full run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33957077847>.
- Aggregate artifact: `rq1-aggregate-33957077847` (GitHub retention expiry: 2026-10-05).

The full aggregate manifest records a clean Linux run on the tested commit with
Python 3.13.15, NumPy 2.4.4, PyYAML 6.0.2, and four independently executed family
shards.

## What was implemented

The milestone implements the restricted conjunctive primitive-factor model used
to exercise the proposed T1 rank criterion. Primitive domain, residual instance,
and residual communication states are independent Bernoulli variables.
Observable health and trace outcomes are conjunctions of those states.

For observable moments, the implementation constructs

```text
log(m) = H log(p)
```

and determines whether individual log-parameters and conjunctive target vectors
belong to the row space of `H`. It separately records structural support from the
observation policy and empirical support after finite-sample eligibility rules.
A weighted log-moment fit emits only quantities supported by the empirical row
space.

The frozen matrix contains four factor-graph families, three observation modes,
three nested sample sizes (100, 500, and 2,000), and 200 independent campaigns.
The independent unit is a campaign; sample-size prefixes within a campaign are
not counted as independent replicates.

## How it was evaluated

The full experiment was sharded by factor-graph family in GitHub Actions and then
aggregated without local recomputation. It produced:

| Table | Rows |
|---|---:|
| Dataset fits | 7,200 |
| Parameter evaluations | 37,800 |
| Target evaluations | 7,200 |
| Raw observable moments | 82,656 |
| Predeclared summary cells | 36 |

Moments required at least 20 jointly observed episodes. Algebraically duplicate
factor unions were represented by the deterministic highest-exposure row for
fitting while every raw moment remained in the artifact.

## Results

Full telemetry produced full structural rank in every family: 3/3 for
same-domain replicas, 6/6 for mandatory fan-out, 5/5 for the communication
bottleneck, and 7/7 for the two-domain path.

Removing synchronous health observations reduced same-domain replicas to rank
2/3 and made its non-direct `both_replicas_live` target unidentifiable. Trace-only
observation reduced primitive ranks to 0/3, 3/6, 1/5, and 1/7 respectively. The
target remained identifiable in the last three families because it was itself a
recorded request-success outcome.

The finite-sample full-rank diagnosis agreed with the structural classification
in every summary cell except `two_domain_path/no_joint_health` at size 100. That
cell reached full empirical rank in 65.5% of 200 campaigns (mean rank 6.47/7),
then reached 100% at sizes 500 and 2,000. The staggered four-way health exposure
and the predeclared minimum of 20 joint observations explain this practical
support failure.

For full telemetry, parameter MAE decreased from 0.0165--0.0192 at size 100 to
0.0036--0.0043 at size 2,000. Target MAE decreased from 0.0291--0.0338 to
0.0067--0.0077. The estimator emitted no structurally unjustified individual
parameter estimates; the recorded false-confident rate was zero.

## Interpretation

The result validates the implementation of the algebraic boundary for this
restricted, correctly specified model. It shows that more data can repair a
finite-sample loss of usable equations but cannot repair structural rank loss.
It also distinguishes identifiability of a requested availability functional
from identifiability of all latent factors.

This milestone is not evidence that a trace-discovered topology is correct or
that the abstraction predicts a running system. The data generator exactly
satisfies the estimator's independent conjunctive assumptions; three targets are
directly observed; missingness is known and state-independent; and no matched
likelihood reference, uncertainty coverage, live validation, or placement
transfer is included. M0 is therefore a theorem-linked mechanism check, not the
article's primary comparative evaluation.
