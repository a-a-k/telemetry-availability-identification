# M9K: single-operation localization of the retained overprediction

Status: completed on the first remote attempt; accepted run `34055967110`.

## Question and scope

M8B showed that the proposed calculation's largest retained operation-level
overprediction is OpenTelemetry Demo `checkout`: its unweighted mean signed
error is `+0.178069` over 55 emitted rows. M9K asks where that discrepancy
enters for this one operation. It does not alter a prediction, estimate a new
accuracy claim, or search across operations for a favorable explanation.

The target was selected from accepted M8B before M9K. The diagnostic cohort is
fixed to both placements, laws N and ND, and repetitions 0--9: 40 campaigns.
NC and NCD are excluded because M8B already established communication-specific
topology ambiguity. N/ND retain a mean checkout discrepancy of `+0.173061`, so
the localization does not depend on that ambiguity.

M9J has closed the current bounded external-tool diagnostic. M9K invokes no
PMX code and does not authorize an adapter. It returns attention to the
unexplained discrepancy in the proposed model, as required by the preliminary
article assessment.

## Frozen evidence

The workflow consumes only retained artifacts:

- the M8A preservation of all 160 qualified M7 cells and its independent file
  inventory/integrity audit;
- the accepted M8B causal-diagnostic artifact and its pre-M9K operation ranking;
- the M9J machine decision and the repository milestone report, without
  rewriting M9J's failed stdout-slot gate; and
- the frozen M7 prediction manifest and table.

Artifact IDs, run commits, compressed digests, relevant decompressed file
digests, source commit, and current analysis/configuration files are byte-locked
in the M9K configuration. All 360 files in the selected 40 qualified cells are
checked against M8A's independently retained inventory before analysis.

## Exact decomposition

For each campaign, checkout calibration and test requests are aligned to the
nearest full health tick with the original 1.25-second tolerance. Route-up is
the frozen path union `max(replica_a_path, replica_b_path)`. Stable requests use
the original one-second guard around any health-signal transition.

Let `q` be the frozen clean-baseline residual success probability, `r_model`
the frozen proposed route probability, `r_obs` the fraction of aligned stable
requests whose full health tick is route-up, `y_up` their success fraction, and
`y_down` the success fraction when route-down. The saved prediction is
`q * r_model`, while the aligned empirical rate is
`r_obs * y_up + (1-r_obs) * y_down`. M9K uses the exact identity

`q*r_model - y = q*(r_model-r_obs) + r_obs*(q-y_up) - (1-r_obs)*y_down`.

The terms have fixed interpretations:

1. `route_state_exposure`: the fitted stationary route probability differs
   from route exposure at request times;
2. `route_up_residual_invariance`: clean-baseline residual success was carried
   into fault-period requests that the health representation calls route-up;
3. `route_down_success_offset`: observed successes while route-down compensate
   some overprediction and expose fallback or state-measurement limitations.

The identity must reconstruct every cell's frozen signed error to `1e-12`.
These are diagnostic counterfactual components, not replacement predictions.

## Localization rule

Cell means are kept equally weighted, matching M8B's descriptive operation
summary. Uncertainty uses 10,000 deterministic stratified campaign bootstraps:
ten repetitions are resampled within each placement-by-law stratum. A positive
component is called dominant only if:

- it exceeds the other positive component with a 95% bootstrap lower bound
  above zero;
- it has the same positive sign in at least 32 of 40 test cells; and
- for `route_up_residual_invariance`, a positive calibration-period version is
  also required, so the result cannot be attributed only to test drift.

If neither component meets its rule, localization remains non-unique. Alignment
must cover at least 99.5% of operation requests, every cell-period stable view
must retain at least 500 requests, and the frozen prediction/M8B recomputation
must have zero mismatches. Integrity failure is separate from a substantive
non-localization.

## Interpretation branches

- Residual-invariance dominance localizes the model discrepancy to the boundary
  where clean `q` and binary route-up semantics are assumed sufficient during
  faults. It does not uniquely distinguish coarse health probes, internal
  service failure, overload, timeout propagation, or an omitted dependency.
- Route-state-exposure dominance localizes the main gap to the stationary route
  probability versus request-time exposure, motivating an exposure-conditioned
  model test.
- A diffuse result means the existing evidence decomposes but cannot isolate
  one boundary; the next experiment must instrument the competing causes rather
  than tune a parameter.

No branch generalizes checkout to other operations. No branch changes M7,
becomes confirmatory accuracy evidence, or decides the paper's overall success
or failure. The preliminary article position remains: the specified-model
calculation is supported, while better accuracy and lower end-to-end automatic
forecast cost than PMX have not been demonstrated.

## Workflow

The workflow has exactly three jobs:

1. audit retained artifact identities and freeze the target contract;
2. audit the selected qualified files and run the checkout decomposition;
3. apply the frozen localization rule and select the next discriminating
   experiment.

All three jobs use `timeout-minutes: 360`. Full artifact download, hashing, and
analysis run only in GitHub Actions. Local work is limited to configuration,
unit tests, and synthetic arithmetic smokes.
