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

Status: in progress as milestone M2.

- factor-graph compilation from heterogeneous records;
- domain-local elimination rules with preservation tests;
- EM or direct sparse optimization for the same observed likelihood;
- three-way diagnostics: proved identifiable, proved ambiguous, unresolved;
- B1 and B2 estimators under matched data eligibility rules.

## Phase 4: uncertainty

- independent-campaign calibration on synthetic data;
- simultaneous observable-probability constraints for small ambiguous models;
- extrema of target availability over compatible parameter sets;
- block bootstrap implementation and coverage study for dependent episodes;
- separate input uncertainty from simulation Monte Carlo error.

## Phase 5: live ingestion and frozen validation

- versioned adapters for traces, lifecycle/health, deployment, and mesh evidence;
- explicit operation specifications and external-client success audit;
- immutable calibration model followed by independent test periods;
- DeathStarBench and OpenTelemetry Demo campaigns;
- B0-B4 comparisons and predeclared ablations.

## Phase 6: placement transfer

- replace known placement metadata without target-configuration calibration;
- preserve only audited transferable residual parameters;
- predict availability change, configuration choice, and regret;
- expose violations of transfer assumptions rather than refitting them away.
