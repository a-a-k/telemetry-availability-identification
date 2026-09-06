# Implementation roadmap

## Phase 1: rank and moment vertical slice

Status: implemented.

Evidence: `milestones/M0_RANK_AND_MOMENTS.md`.

- typed primitive factors and conjunctive observables;
- known state-independent observation masks;
- structural versus empirical identifiability;
- identified log-moment baseline;
- four-family RQ1 workflow with nested samples and provenance.

## Phase 2: exact observed likelihood reference

Status: implemented as milestone M1.

Evidence: `milestones/M1_EXACT_LIKELIHOOD_REFERENCE.md`.

- compile an episode and its mask into a likelihood factor;
- enumerate latent states for small models independently of the simulator;
- add a standard constrained optimizer as the B3 correctness reference;
- verify that equal likelihood objectives converge to equal optima on oracle cases;
- retain boundary and convergence status instead of silently selecting one optimum.

## Phase 3: proposed identification procedure

Status: partially implemented across milestones M1--M2. M2 supplies one proved
signature-reduction rule, direct reduced-likelihood optimization, and three-way
diagnostic output. General heterogeneous adapters, broader elimination rules,
and B1 remain later work.

Evidence: `milestones/M2_STRUCTURE_PRESERVING_REDUCTION.md`.

- factor-graph compilation from heterogeneous records;
- domain-local elimination rules with preservation tests;
- EM or direct sparse optimization for the same observed likelihood;
- three-way diagnostics: proved identifiable, proved ambiguous, unresolved;
- B1 and B2 estimators under matched data eligibility rules.

## Phase 4: uncertainty

Status: implemented in M4, with directed assumption stress in M5.

Evidence: `milestones/M4_SIMULTANEOUS_UNCERTAINTY.md` and
`milestones/M5_DIRECTED_STRESS_TESTS.md`.

- independent-campaign calibration on synthetic data;
- simultaneous observable-probability constraints for small ambiguous models;
- extrema of target availability over compatible parameter sets;
- block bootstrap implementation and coverage study for dependent episodes;
- separate input uncertainty from simulation Monte Carlo error.

## Phase 5: live ingestion and frozen validation

Status: implemented in M6 and M7. M7 completed technically, while its
predeclared primary contrast is incomplete and supports no superiority claim.

Evidence: `milestones/M6_LIVE_INGESTION_HARNESS.md` and
`milestones/M7_FROZEN_LIVE_VALIDATION.md`.

- versioned adapters for traces, lifecycle/health, deployment, and mesh evidence;
- explicit operation specifications and external-client success audit;
- immutable calibration model followed by independent test periods;
- DeathStarBench and OpenTelemetry Demo campaigns;
- B0-B4 comparisons and predeclared ablations.

## Phase 6: placement transfer

Status: implemented synthetically in M3 and evaluated on the frozen live M7
matrix. The live transfer result is conditional on topology support and the
declared homogeneous-new-domain assumption.

Evidence: `milestones/M3_NON_DIRECT_PLACEMENT_TRANSFER.md` and
`milestones/M7_FROZEN_LIVE_VALIDATION.md`.

- replace known placement metadata without target-configuration calibration;
- preserve only audited transferable residual parameters;
- predict availability change, configuration choice, and regret;
- expose violations of transfer assumptions rather than refitting them away.

## Phase 7: post-M7 diagnosis and Palladio comparison

Status: M8A complete; M8B diagnostic decomposition is next under the separately
labelled M8 protocol.

Evidence contract: `M8_M7_DIAGNOSTIC_PROTOCOL.md`.

- preserve all still-available M7 qualified, raw-sample, and analysis artifacts;
- independently verify identities, scores, denominators, and aggregation;
- diagnose bias, temporal behavior, semantic failures, and topology ambiguity;
- bootstrap and semantically validate a pinned Palladio reliability analyzer;
- compare fixed estimators and PCM/Palladio on aligned inputs before collecting
  any new live confirmation.
