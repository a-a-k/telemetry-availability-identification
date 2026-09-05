# M3 non-direct placement-transfer protocol

## Purpose and anti-strawman constraint

M3 asks whether calibration telemetry from the current placement supports a
prediction for two unobserved placement changes. It does not fit on outcomes
from either target placement. The experiment includes the direct endpoint,
independence, same-model moment, exact same-model likelihood, and empirical
joint baselines. B3 and the proposed procedure share the exact fitted likelihood;
agreement whenever a target is identified is required, not counted as an
accuracy advantage.

The proposed output differs from a raw B3 point only when the data leave a
transfer target ambiguous: it attaches an analytic certificate and withholds
that target. Raw optimizer values are retained under B3, explicitly labeled as
unsupported, to measure the consequence of treating one point on a likelihood
ridge as a recovered model.

## Calibration model and non-direct targets

Each scenario has two replicas in domain A and two anchors in domain B. For a
domain state `gamma` and residual instance states `eta`, health is their
conjunction. Calibration can expose four health indicators and two OR traces:

~~~text
current_success = (domain_a AND replica_a) OR (domain_a AND replica_b)
anchor_success  = (domain_b AND anchor_a)  OR (domain_b AND anchor_b)
~~~

No calibration record contains a target-placement outcome. The three reported
availability functionals are:

~~~text
current = gamma_a * (1 - (1 - eta_a) * (1 - eta_b))
split   = 1 - (1 - gamma_a * eta_a) * (1 - gamma_b * eta_b)
add     = gamma_a * (1 - (1 - eta_a) * (1 - eta_b)^2)
~~~

`split` moves replica B to the independently calibrated domain B. `add` keeps
the placement and adds a same-type residual replica in domain A. Reusing the
residual probability after movement/addition is a stated synthetic transfer
assumption; M5 will violate it deliberately.

## Frozen scenarios

Replica health marginals are 0.90 and 0.88 in every scenario. Anchor marginals
are 0.91 and 0.89, and domain B is 0.96. Only domain A changes, so marginal-only
methods receive the same population inputs while the correct placement choice
changes.

| Scenario | Domain A | Current | Split | Add | True choice |
|---|---:|---:|---:|---:|---|
| weak common cause | 0.99 | 0.980000 | 0.985333 | 0.988889 | add |
| medium common cause | 0.94 | 0.937447 | 0.989872 | 0.939837 | split |
| strong common cause | 0.91 | 0.909670 | 0.992835 | 0.909989 | split |

The weak case has a deliberately small choice margin. It prevents decision
accuracy from becoming trivial at the smallest sample size.

## Observation modes

| Mode | Supported evidence | Role |
|---|---|---|
| `full` | all health and traces | well-observed positive control |
| `sampled_mixed` | health retained with probability 0.40 and traces with 0.70 | primary incomplete-telemetry contrast |
| `joint_health_only` | synchronous health, no traces | simple moment-positive control |
| `no_joint_health` | one staggered health value per episode plus both OR traces | heterogeneous evidence unavailable to joint-health-only estimation |
| `trace_only` | both OR traces only | proved-ambiguous negative control |

Sampling masks are known and state-independent in M3. Values are shared across
observation modes within a campaign, and sample sizes 100, 500, and 2,000 are
nested prefixes. There are 200 independently generated campaigns per scenario
and mode, giving 9,000 calibration datasets. Nested prefixes are never counted
as independent repetitions.

## Identification certificate

For a domain with health marginals `m1`, `m2`, joint health `j`, and OR-trace
probability `o`, the supported analytic recoveries are:

~~~text
gamma = m1 * m2 / j
gamma = m1 * m2 / (m1 + m2 - o)
~~~

Thus synchronous health identifies a domain, and staggered health plus an OR
trace also identifies it. Trace-only records identify the two current OR
probabilities but not their domain/residual decompositions. For every ambiguous
target the artifact contains two interior parameter vectors with equal complete
supported-observation distributions and a different target value.

## Methods

- B0, endpoint persistence: carry the current endpoint rate to each new
  placement. It legitimately predicts zero change but cannot distinguish the
  two choices.
- B1, independent marginals: use the two replica health marginals and remove the
  shared-domain dependence. This is the predeclared common-cause ablation, not
  the principal comparator.
- B2, available domain moments: recover each domain from joint health when
  available or from health marginals plus its OR trace otherwise. This stronger
  version avoids denying B2 information that is analytically usable.
- B3, exact observed likelihood: enumerate all latent states and optimize the
  same Boolean observation model. Its raw point is retained even on a proved
  ridge, but that output is marked unsupported.
- Proposed, identification-aware likelihood: use the exact B3 fit and emit only
  parameter/target quantities covered by the analytic certificate.
- B4, empirical joint distribution: estimate the current OR from jointly
  observed health. It does not extrapolate an unseen placement.

B0 and B4 are expected to be competitive for the current endpoint. B3 is the
strong same-model statistical reference. Lack of a proposed-versus-B3 accuracy
difference in identified regimes is the expected correctness result.

## Outcomes and analysis

Primary transfer outcomes are absolute error of the change from current
availability, correct choice between `split` and `add`, exact regret, and
decision coverage. Secondary outcomes are target-level MAE/bias, parameter
MAE/bias, convergence/boundary status, and runtime. Unsupported decision rate is
reported separately from ordinary decision coverage.

All error comparisons are paired within the same scenario, observation mode,
sample size, and campaign. The tables report proposed-minus-baseline mean and
median absolute-error differences. A deterministic percentile interval for the
mean uses 2,000 resamples of whole campaigns. Resampling is performed separately
at every nested sample size; prefixes themselves are not resampling units.

For an independent outcome check, each scenario/campaign also receives 10,000
new Bernoulli validation episodes per target. Exact enumerated probabilities are
the primary synthetic truth; validation rates quantify the noise that a live
test estimate would retain and are never exposed to an estimator.

## Predeclared expectations and quality gates

- proposed and B3 predictions must agree to `1e-12` wherever the proposed
  procedure emits a value;
- every ambiguity witness must preserve all supported observable-event
  probabilities to `1e-12` and change its target by more than `1e-6`;
- the proposed procedure must make zero decisions in a mode whose two transfer
  targets are not proved identifiable;
- B1 should systematically prefer `add`, succeeding in the weak scenario and
  failing as common-cause strength reverses the true choice;
- B2 and exact likelihood should agree with increasing data under fully
  informative evidence; exact likelihood may use sampled heterogeneous records
  more efficiently, but universal superiority is not hypothesized;
- raw B3 outputs on trace-only data are diagnostic artifacts, not defensible
  recovered transfer predictions.

The GitHub aggregate job fails the first three implementation-quality checks.

## Interpretation boundary

M3 supports a synthetic RQ3 claim for one explicit two-domain Boolean placement
change. It does not establish general Boolean identifiability, robustness to an
incorrect domain map, time dependence, informative exporter loss, or live-system
validity. Those are separate milestones. A result favorable only against B1,
B0, or B4 cannot establish an estimation advantage; the matched B3 result and
the strengthened B2 comparison remain central.
