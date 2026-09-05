# M7 frozen live validation and placement-transfer protocol

## Freeze boundary and purpose

This document, `configs/m7_frozen_live.yaml`, both evidence-boundary files, the
analysis implementation, and the GitHub workflow are committed and pass CI
before the first M7 request is sent. M7C and M7C-R selected only the live
duration, transition guard, and balanced campaign budget. M7D exercised the
adapter without fitting a method. No M7C/M7D request, outcome, health tick,
trace, or schedule enters M7.

M7 asks two deliberately limited empirical questions:

1. How well do predictions learned from one 900-second calibration realization
   score on a separate 900-second realization of the same application,
   placement, and failure-law stratum?
2. When calibration comes only from the co-located placement, what can each
   method defensibly predict for an independently executed split placement?

The study evaluates a trace-supported topological availability abstraction. It
does not treat the controller schedule as truth and does not claim that a live
test rate is a latent parameter's ground truth.

## Runs, roles, and non-negotiable separation

The four-cell preflight uses both applications, both placements, `NCD`, and
repetition zero. It has seed `770036`, namespace `m7-preflight-v1`, and explicit
`pilot_only=true`, `preflight_only=true`, `main_effectiveness=false` labels.
The preflight qualification reads schemas and hashes, physically sequesters its
test period, and fits or scores no method. Its records are permanently excluded
from the main study.

The full run starts all 160 cells anew:

- two frozen public application revisions;
- co-located and split replicated-target placements;
- `N`, `NC`, `ND`, and `NCD` factor laws;
- ten independent campaigns per application--placement--law stratum;
- a 60-second clean baseline, 900-second calibration, and separate 900-second
  test period at four scheduled external attempts per second.

The full run uses acquisition seed `770034` and namespace `m7-main-v1`. Each
cell is an independent benchmark deployment and renewal realization. The 3,600
requests inside one period are repeated observations within a campaign, not
independent experimental replications.

Only the baseline and calibration portions cross the learner boundary. Test
request outcomes and ordinary test health are written under `evaluator/`.
Test health is used only to apply the predeclared transition exclusion during
scoring. Planned schedules, controller events, cause labels, intended/applied
times, and cleanup records are privileged audit evidence and are never parsed
by B0--B4 or the proposed procedure.

The public repository's included Actions artifact storage is finite. Every
successful full cell therefore retains the compact qualified learner/evaluator
bundle and a boundary audit containing hashes of every source and privileged
file. Complete raw source directories are retained for the four preflight
cells, for the four predeclared full `NCD/r0` audit-sample cells, and for every
failed cell, rather than selectively retaining favorable outcomes. This
storage rule is frozen before execution; it limits independent re-parsing of
the other 156 native trace files and is reported as a reproducibility
limitation.

## Operation residual and trace-discovered topology

The clean baseline is auxiliary learner evidence. For each operation `u`, its
residual semantic-success probability is frozen as the Jeffreys posterior mean

`q_u = (successful baseline attempts + 0.5) / (baseline attempts + 1)`.

This separates failures unrelated to the replicated target from the route
availability abstraction. The baseline contains no scheduled faults and is not
used as a test outcome.

Topology is reconstructed independently inside every campaign and observation
mode from successful native learner traces. A trace is retained by the mode's
deterministic mask. An operation is classified as target-requiring only if at
least 20 retained parsed traces support it and at least 80% contain the declared
replicated target service. It is classified as non-target if at most 5% contain
that service. Intermediate fractions, insufficient support, disagreement with
the pre-frozen M7B operation contract, or fewer than five assignments to either
replica cause an explicit method abstention. Missing downstream spans are never
converted into negative component states.

The M7B operation contract is retained only as a falsifiable pre-run check. The
analysis uses the classification recovered from M7 learner traces. Declared
replica and domain membership comes from deployment metadata, because call
traces cannot discover failure domains.

## Health signals and topological model

At each ordinary one-second health tick, `H_a,H_b` indicate that the respective
real container is running and not paused. `P_a,P_b` indicate that the instance
is also attached to its network and reported usable by the independently polled
HAProxy backend check. Thus `P_i` implies `H_i`; violations are counted.

For a co-located placement the fitted abstraction is

`H_i = G E_i`, `P_i = G E_i C_i`, and
`R_colocated = P_a OR P_b`.

For a split placement it is

`H_i = G_i E_i`, `P_i = G_i E_i C_i`, and
`R_split = P_a OR P_b`,

where `G_a` and `G_b` are independent draws with a common stationary
availability `g`. This homogeneous-new-domain assumption is required for the
co-located-to-split transfer and is reported as an assumption, not inferred
from traces. `E_a,E_b,C_a,C_b` and all active domain variables are independent
in the fitted abstraction. Factors absent from a law are fixed at one.

For a target-requiring operation, semantic success has probability `q_u R`;
for a non-target operation it has probability `q_u`. The likelihood enumerates
all latent states once per one-second bin and integrates states compatible with
whatever health signals survived the mask. Request counts within a bin enter as
binomial outcomes. Products over time are a stationary composite likelihood:
the analysis does not falsely claim renewal observations are temporally
independent. Uncertainty and hypothesis tests use independent campaigns.

A probability of `1e-12` is used only as a numerical log floor for an outcome
that the deterministic abstraction assigns zero probability. Such rows cannot
be made favorable by changing the floor and remain visible through fit and
health diagnostics.

## Observation modes

One deterministic seed (`770035`) constructs all masks before methods run. A
method never receives a more favorable realization than another method in the
same campaign and mode.

- `full`: retain all four health signals and all parsed learner traces.
- `sampled_mixed`: retain every health signal independently with probability
  0.4 and every eligible trace with probability 0.7.
- `no_joint_health`: alternate complete `(H_i,P_i)` observations between
  replicas, so cross-replica health is never synchronous; retain traces with
  probability 0.7.
- `trace_only`: retain no health values and retain traces with probability 0.7.

Health/request alignment may differ by at most 1.25 seconds. The primary test
view excludes requests within one second on either side of an ordinary observed
health-state change. This rule sees neither event intent nor cause. An
all-sequence analysis is secondary. The M7C dependence block is 23 seconds; a
46-second block is retained as a within-cell compatibility-interval
sensitivity analysis.

## Comparators and fairness

All six methods receive identical admitted rows and masks.

- **B0, endpoint persistence.** The operation-specific calibration endpoint
  rate, with the same Jeffreys smoothing, is carried to test. In transfer it is
  carried from co-located calibration to split test.
- **B1, independent path marginals.** It estimates every available `P_i`
  marginal and uses `1-(1-P_a)(1-P_b)`, explicitly discarding common
  dependence.
- **B2, strengthened available moments.** It uses all available `H_i` and
  `P_i` marginals. With synchronous co-located health it additionally uses the
  `H_a H_b` moment and the observed `P_i/H_i` channel ratios. Without that
  joint moment it uses the calibration endpoint OR likelihood as the fallback
  for the current placement. For split placement or transfer it uses both path
  marginals under the declared new-domain assumption. It receives no oracle
  event labels or hidden test state.
- **B3, matched standard likelihood.** Eight deterministic-start bounded
  L-BFGS-B fits optimize the same enumerated observed-data likelihood as the
  proposed point fit. A raw optimum is retained even on an unidentified ridge
  and is labeled as such.
- **Proposed, identification-aware likelihood.** It emits the matched B3 point
  only when the target gradient lies in the numerical row space of the
  observable-distribution Jacobian and equivalent multistart fits agree within
  `1e-4`. Otherwise it abstains. Wherever it emits, B3/proposed agreement to
  `1e-12` is a hard implementation gate, not an accuracy win.
- **B4, empirical joint path.** It estimates the current OR from complete
  `(P_a,P_b)` ticks. It abstains from split-placement transfer rather than
  receiving unobserved joint completion.

B0 can be difficult to beat for a stationary current endpoint, B2 is an
analytically strong same-evidence comparator, B3 is the same-model statistical
reference, and B4 is saturated when joint path observations are complete. A
favorable result only against B0, B1, or B4 cannot support a superiority claim.
Agreement or a null difference against B2/B3 is an informative result rather
than a workflow failure.

## Scoring, estimands, and inference

The primary proper score is request-level Brier loss on the sequestered stable
test view. Losses are first averaged equally across the three frozen operations
inside a campaign, then paired as `proposed - B2`, then averaged equally across
the 16 application--placement--law strata. Negative favors the proposed
procedure. The independent unit is the campaign. With ten campaigns per
stratum, the standard error is

`sqrt(sum_s variance_s / n_s) / 16`,

and degrees of freedom use the corresponding Welch--Satterthwaite expression.
A two-sided 95% interval and p-value are reported. The primary result is
confirmatory only if all 160 paired campaign scores exist; abstention makes it
incomplete rather than triggering imputation.

Secondary outputs include every method/mode, signed and absolute discrepancy
from the noisy test rate, Brier score, block-based prediction compatibility,
all-sequence scoring, and the 46-second block sensitivity. Secondary paired
contrasts are Holm-adjusted within the declared analysis family.

Transfer predictions use only a co-located learner bundle and are paired to the
split evaluator having the same application, law, and repetition. The split
learner bundle is never read to form that transfer prediction. Transfer is a
secondary eight-stratum estimand. B4 must abstain; trace-only transfer may also
be unidentified. Observed split test rates score predictions but are not
presented as parameter truth.

## Workflow acceptance and interpretation boundary

Technical gates cover the exact cell matrix, source run and commit uniformity,
digest/provenance labels, evidence-boundary usability, finite emitted values,
and B3/proposed equality. Topology ambiguity, model incompatibility,
identification abstention, empirical score direction, confidence-interval
sign, and placement benefit are substantive outcomes and cannot fail the
workflow.

M7 can show whether this particular trace-supported two-replica abstraction is
adequate for these operations, revisions, failure processes, and runner
environment. It cannot establish arbitrary Boolean-topology support, causal
failure-domain discovery, physical independence of split domains, universal
benchmark behavior, or superiority to a same-model likelihood optimizer. A
null result, widespread abstention, or poor calibration narrows the article's
claim; it is not repaired by replacing B2 or inspecting controller truth.
