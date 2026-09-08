# Ordinary inputs DeathStar / OTel: qualified technical inventory

[Run34223543390](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34223543390), head e41468f845c8172fcb9a410ea71dd8b7792312c8, success. CI34223542687 success.
[Exact compact artifacts and hashes](../evidence/existing-ordinary-34223543390/verified-archives.json), [all artifact metadata](../evidence/existing-ordinary-34223543390/all-artifact-metadata.json), [protocol](../EXISTING_APPLICATION_ORDINARY_PROTOCOL.md).
Source34205650183 is reused as normal-window technical calibration, zero new independent campaigns. Main=0; model examples remain1/3.

| Application / operation | Requests | Native spans | Service-parent edges | External roots / request |
| --- | ---: | ---: | ---: | ---: |
| DeathStar compose_post |80|2320|11|1|
| DeathStar read_home_timeline |80|606|2|1|
| DeathStar read_user_timeline |80|634|2|1|
| OTel browse_product |80|640|2|1|
| OTel add_to_cart |80|1680|3|2|
| OTel checkout |80|5360|12|3|

Every request has a native trace. All missing-parent spans match the exact external client context and declared frontend root; no unexplained roots. OTel multiple roots correspond to the complete multi-call operation boundaries and are not missing telemetry. Both profiles have60 probe ticks, every replica UP/L4OK, collector malformed rows0, native malformed/invalid0. Each fresh inventory read exactly6 ordinary data files and no blocked/evaluator/legacy paths. Preparation retained whitelisted telemetry and ordinary probes, without privileged fields or sentinel requests.

DeathStar read_user_timeline has nginx→user-timeline→post-storage. OTel browse_product has frontend-proxy→frontend→product-catalog, plus an unresolved DB CLIENT peer placeholder. Native instance mapping is absent for both targets. These facts do not identify physical replica/domain state or business adequacy. The L4 all-up observation is not application readiness. Empty initial dependency declarations explicitly mean unknown.

Pinned source inspection establishes that OTel catalog uses PostgreSQL and its source compose declares astronomy-db/astronomy_db. A future explicit declaration adapter may complete missing endpoint fields only when compatible with every observed field; it must preserve the DB CLIENT relation and required dependency. This is not part of the successful inventory version and is not yet a qualified model result. DeathStar Redis/MongoDB/storage internals require separate semantic treatment; no missing span licenses their deletion.

Native parse seconds: DeathStar0.069296971, OTel0.378590702. Process time/RSS for preparation and isolated inventory remain in each retained resource-usage.txt; they are not directly comparable method costs. Four exact compact ZIPs total10419 bytes (2904,3028,1956,2531), all member hashes and CRC verified. Full ordinary archives10054735751/10054733042 remain remote. Local and Git evidence contains aggregate reports, not those data archives.

Next: freeze two ordinary graph builds with explicit source semantics, joint observation law and fresh model-only replay; then continue mechanism/class/admission work. Inventory alone completes zero new model examples.
