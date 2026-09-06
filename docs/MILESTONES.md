# Experimental milestones

The repository advances through evidence-bearing milestones. A milestone is
complete only when its implementation and tests are committed, its non-smoke
experiment has completed in GitHub Actions, and a report records the tested
commit, workflow run, outputs, limitations, and interpretation.

Heavy experiments are never run locally. Local execution is restricted to unit
tests, configuration validation, and bounded smoke cases.

| Milestone | Scope | Status | Evidence |
|---|---|---|---|
| M0 | Conjunctive rank and log-moment vertical slice | Complete | `milestones/M0_RANK_AND_MOMENTS.md` |
| M1 | Exact observed-likelihood reference and matched B2/B3 comparison | Complete | `milestones/M1_EXACT_LIKELIHOOD_REFERENCE.md` |
| M2 | Identification-aware compiler and structure-preserving likelihood reduction | Complete | `milestones/M2_STRUCTURE_PRESERVING_REDUCTION.md` |
| M3 | Non-direct Boolean targets and synthetic placement transfer with B0-B4 | Complete | `milestones/M3_NON_DIRECT_PLACEMENT_TRANSFER.md` |
| M4 | Simultaneous uncertainty sets and coverage | Complete | `milestones/M4_SIMULTANEOUS_UNCERTAINTY.md` |
| M5 | Directed misspecification and telemetry-loss stress tests | Complete | `milestones/M5_DIRECTED_STRESS_TESTS.md` |
| M6 | Versioned live-ingestion contract and benchmark harness | Complete | `milestones/M6_LIVE_INGESTION_HARNESS.md` |
| M7P | Remote runtime and native-telemetry feasibility pilot | Complete | `milestones/M7P_RUNTIME_FEASIBILITY_PILOT.md`; never used as effectiveness evidence |
| M7A | Fault-control, health-audit, and request--trace linkage diagnostic | Complete | `milestones/M7A_FAULT_ACQUISITION_DIAGNOSTIC.md`; excluded from effectiveness evidence |
| M7B | Replicated placement, load-balancing, and effect-semantics pilot | Complete | `milestones/M7B_REPLICATED_PLACEMENT_PILOT.md`; excluded from effectiveness evidence |
| M7C | Stochastic schedule and repetition-budget freeze pilot | Complete | `milestones/M7C_STOCHASTIC_FREEZE_PILOT.md`; includes documented M7C-R claim narrowing and excludes all pilot data from effectiveness evidence |
| M7D | Learner/evaluator boundary and native-trace normalization | Complete | `milestones/M7D_LEARNER_EVIDENCE_BOUNDARY.md`; diagnostic only and excluded from effectiveness evidence |
| M7E | Frozen main acquisition, strong comparators, matched likelihood, and campaign inference | Complete | `milestones/M7E_ANALYSIS_FREEZE.md`; completed before any M7 remote request |
| M7F | Separate no-fit four-cell main-path preflight | Complete | `milestones/M7F_NO_FIT_PREFLIGHT.md`; accepted after a retained provenance-wiring failure and excluded from effectiveness evidence |
| M7 | Frozen live validation and placement transfer | Complete; primary incomplete | `milestones/M7_FROZEN_LIVE_VALIDATION.md`; 160/160 technical success, 117/160 primary pairs, no superiority claim |
| M8A | Preserve M7 evidence and independently audit identities, scores, and aggregation | Complete | `milestones/M8A_M7_EVIDENCE_AND_ARITHMETIC_AUDIT.md`; 165 artifacts preserved, 36,459 scores independently reproduced, zero mismatches |
| M8B | Decompose M7 bias, temporal behavior, semantic failures, and topology ambiguity | Complete | `milestones/M8B_M7_CAUSAL_DIAGNOSTICS.md`; all 576,000 test requests aligned, 32/32 normalized replay files matched, discrepancy localized but cause unresolved |
| M9A | Pin, build, inventory, and reproduce the official Palladio reliability analyzer example | Complete | `milestones/M9A_PALLADIO_RELIABILITY_BOOTSTRAP.md`; accepted three-job run pinned the product, rebuilt 5.2.2 under an audited historical target lock, and matched the independent 0.375 oracle twice |
| M9B | Validate Palladio semantics on independent hand-checkable reliability controls | Complete | `milestones/M9B_PALLADIO_SEMANTIC_CONTROLS.md`; all 15 predeclared cases matched their external oracles twice, with explicit replication and communication-mapping limits |
| M9C | Define the M7-to-PCM correspondence and build one minimal operation model per application | Complete | `milestones/M9C_PALLADIO_APPLICATION_MAPPING.md`; 16/16 mapping rows and four source-grounded operation-placement PCM instances passed, with eight solver records matching frozen structural oracles |
| M9D | Compare fixed M7 estimators and PCM/Palladio on aligned preserved inputs | Complete | `milestones/M9D_PALLADIO_ALIGNED_COMPARISON.md`; first-attempt three-job run solved 184 PCM instances twice with technical parity, retained 76.7% aggregate admissible coverage, and established no predictive gain over B2 |
| M9E | Audit the selected Retriever route for a reliability-ready full path on the two fixed applications | Complete, scope-corrected | `milestones/M9E_PALLADIO_FULL_PATH_FEASIBILITY.md`; accepted three-job run found four empty PCM shells and 5/15 readiness gates per application. `M9E_PMX_PERFORMABILITY_CORRECTION.md` limits that result to the tested Retriever branch and restores the headless OpenTelemetry PMX performability route as M9F's scientific priority |
| M9F | Audit reproducibility and semantic fit of the PMX performability route before choosing a manual continuation | In progress | `M9F_PMX_PERFORMABILITY_AUDIT_PROTOCOL.md` is frozen; `M9F_RUNTIME_AMENDMENT.md` retains superseded run 34040388551 and freezes an observable bounded launcher recovery before the accepted candidate; no accuracy scoring or new live collection |

The order may expose a scientific stopping condition. In particular, failure to
distinguish the proposed procedure from a matched standard likelihood reference
must lead to a narrower claim or redesign, not to a weaker comparator.
