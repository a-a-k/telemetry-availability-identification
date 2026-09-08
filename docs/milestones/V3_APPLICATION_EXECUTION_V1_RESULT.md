# Ten-operation execution binding v1: retained result and correction scope

Run [34249604323](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34249604323), frozen head `a7102d01fa4a3b6c2f0f438f6730c1656b1bba35`, passed all nine prepare/build/replay jobs. CI34249599056 passed. Scientific result: eight saved models, six point predictions and two ambiguous predictions; two additional operations explicitly unsupported. All ten operation statuses/4080 calibration attempts are accounted for; only 3920 attempts entered the eight supported model constructions. This is reused development calibration, not an independent accuracy result or main admission.

| Operation | Nodes / edges | v1 execution estimate | Scientific status |
| --- | --- | --- | --- |
| DeathStar compose_post | 12 / 11 | 1 | Normal-state technical point; source propagation assumed |
| DeathStar read_home_timeline | 3 / 2 | 1 | Observed seeded workload class |
| DeathStar read_user_timeline | 3 / 2 | 1 | Observed seeded workload class |
| OTel browse_product | 4 / 3 | 1 | Explicit astronomy DB CLIENT binding |
| OTel add_to_cart | — | absent | Partial Redis/Valkey peer lacks namespace declaration |
| OTel checkout | — | absent | Same Valkey declaration boundary |
| Petclinic list_owners | 3 / 2 | 1 | Fixed fixture and source propagation |
| Petclinic owner_details_with_visits | 4 / 4 | [0,119/150] | v1 erroneously applies L4 decoder to L7 contract; corrected version required |
| Petclinic create_visit | 3 / 2 | [0,182/225] | Same decoder-layer mismatch; corrected version required |
| Petclinic list_vets | 2 / 1 | 1 | Warm-cache class; DB absence is not universal independence |

Every saved model's full calculation hash reproduced in a separate model-only job. All27 required-edge removal controls returned exactly zero; equivalent edge order preserved each full result. Builders read exactly six ordinary files, replayers exactly model.json/seal.json, blocked accesses zero. These controls do not cure the declared semantic/observation limits.

Two precise issues were exposed and are preserved:

1. OTel cart CLIENT spans declare `db.system=redis`, address `valkey-cart`, port6379, but no namespace. V1 had only the astronomy PostgreSQL peer declaration and correctly returned unsupported rather than filling a guessed DB. Exact cart code, configuration and pinned StackExchange.Redis3.1.31 source now establish the default DB0 binding for a new version.
2. The new v1 application adapter hardcoded L4 while Petclinic's ordinary declaration and existing qualified adapter explicitly use L7OK. This turned successful observations into masks: create_visit has643/636 masked a/b values; owner-details621/618. No probe timestamps were missing or too old. These v1 bounds are retained as an implementation defect, not intrinsic nonidentifiability of the corrected observation model. The earlier frozen Petclinic graph adapter and earlier health-prefix corrections are unaffected.

Source review of the newly bound store also makes the optional-call boundary concrete: ignored EmptyCart errors must exclude nested DB work and replica demands from mandatory completion. Its spans and graph edges remain visible. This applies to the new OTel binding, which had no v1 forecast. [V2 correction protocol](../V3_APPLICATION_EXECUTION_V2.md) freezes these changes and exact calculation-hash checks on six unaffected operations.

Nine exact compact archives,23642bytes,24members, are retained in [the evidence directory](../evidence/v3-application-execution-34249604323/verified-archives.json), with metadata for all15 remote artifacts. Ordinary and full model archives remain remote. The strict retainer allowlists only preparation/fit/replay report files; it does not retrieve native/ordinary/model payloads. All original values, unsupported reasons, resource reports and source seals remain available.

Main campaigns0; no new independent N. The next result is the separately versioned corrected ten-operation build/replay, followed by final method/comparator bindings and admission checks.
