# Prefix census adapter v2: historical qualification schema

The first [run 34217215671](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34217215671), head `29ce8bf5ab7e7d4a89aa6539352aa0bcd233b175`, failed before comparing observations: `KeyError: usable` in the first M7 learner manifest. Exact compact resource archive, API identity and failure log are preserved in `docs/evidence/health-prefix-audit-34217215671`. This failed technical attempt supplies no completed census or independent campaign.

Cause: M7 stores its qualification flag in `audit/boundary.json`; Petclinic additionally stores it in the learner manifest. The historical `load_qualified_cell` already checks the boundary. Adapter v1 incorrectly required the Petclinic manifest field for both sources.

Adapter `historical-health-census-adapter-v2` explicitly checks `boundary.usable is True` for every cell. Petclinic also requires `manifest.usable is True`; an absent M7 manifest flag is allowed only with a positive boundary. An explicit false flag is never ignored. Source archives, observation decoding, census denominators, statistical scope and outputs otherwise retain the [v1 protocol](HEALTH_PREFIX_AUDIT_PROTOCOL.md). A bounded two-schema control rejects negative/missing required flags; AST equality checks decoder/census/restore functions against the frozen first implementation.

The v1 code/config/workflow remain unchanged. The new v2 config locks this adapter, workflow, correction note, tests and reused source code before execution. It repeats the same complete 168-case diagnostic census because v1 produced none. Expected result remains 328 health files with all per-case counts, not merely a green job. No refits or outcome reads, no newly acquired test data, no main campaigns.
