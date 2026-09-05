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
| M5 | Directed misspecification and telemetry-loss stress tests | In progress | `M5_STRESS_PROTOCOL.md`; report follows the GitHub run |
| M6 | Versioned live-ingestion contract and benchmark harness | Planned | report follows integration evidence |
| M7 | Frozen live validation and placement transfer | Planned | report follows the campaign runs |

The order may expose a scientific stopping condition. In particular, failure to
distinguish the proposed procedure from a matched standard likelihood reference
must lead to a narrower claim or redesign, not to a weaker comparator.
