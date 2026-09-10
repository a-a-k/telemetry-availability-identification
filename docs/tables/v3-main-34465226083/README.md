# Independent main comparison: retained remote tables

Source run `34465226083`, head `d857ea65ca9da7fa9ae4ee1198317487475246a7`, mode `main`. Planned campaigns: 240; operation cells per method: 800; retained method slots: 8000. Source SHA256: `474e3c771ac91731960d1750458962b237b1967a2c3ec1291bf44e75149dd794`.

These tables copy metrics already computed by the frozen remote analysis. No local fitting, replay, bootstrap or imputation is performed. Null estimates remain null. Own-support means cannot be interpreted as paired comparisons when support differs. This generated export is not a publication-readiness verdict.

## Own support and error

| Application | Method | Points / planned | MAE (pp) | Signed (pp) | Brier | Median AE (pp) | P90 AE (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| deathstarbench_social_network | Gstar | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | GID | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | Gselected | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | G_without_deadline | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | G_without_selection | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | G_without_completion | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | G0 | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | B0 | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | PMX | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| deathstarbench_social_network | PMX_inclusive | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | Gstar | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | GID | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | Gselected | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | G_without_deadline | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | G_without_selection | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | G_without_completion | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | G0 | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | B0 | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | PMX | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | PMX_inclusive | 0 / 240 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | Gstar | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | GID | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | Gselected | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | G_without_deadline | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | G_without_selection | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | G_without_completion | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | G0 | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | B0 | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | PMX | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |
| spring_petclinic_microservices | PMX_inclusive | 0 / 320 | not estimable | not estimable | not estimable | not estimable | not estimable |

## Prespecified paired contrasts

Negative differences favour Gstar only on the displayed complete common campaign support. Intervals are the frozen paired campaign bootstrap, conditional on retained support. Nonsignificance does not establish equivalence and no finite-sample familywise guarantee is asserted.

| Application | Comparator | MAE difference (pp) | Interval (pp) | Complete campaigns | Common cells | Status |
| --- | --- | --- | --- | --- | --- | --- |
| deathstarbench_social_network | G0 | not estimable | not estimable | 0 | 0 | not_estimable_no_complete_common_campaign |
| deathstarbench_social_network | PMX | not estimable | not estimable | 0 | 0 | not_estimable_no_complete_common_campaign |
| opentelemetry_demo | G0 | not estimable | not estimable | 0 | 0 | not_estimable_no_complete_common_campaign |
| opentelemetry_demo | PMX | not estimable | not estimable | 0 | 0 | not_estimable_no_complete_common_campaign |
| spring_petclinic_microservices | G0 | not estimable | not estimable | 0 | 0 | not_estimable_no_complete_common_campaign |
| spring_petclinic_microservices | PMX | not estimable | not estimable | 0 | 0 | not_estimable_no_complete_common_campaign |

## Coverage limitations

| Application | Method | Absent cells | Reason |
| --- | --- | --- | --- |
| deathstarbench_social_network | Gstar | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | GID | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | Gselected | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | G_without_deadline | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | G_without_selection | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | G_without_completion | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | G0 | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | B0 | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | PMX | 240 | acquisition_or_evaluator_unavailable |
| deathstarbench_social_network | PMX_inclusive | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | Gstar | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | GID | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | Gselected | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | G_without_deadline | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | G_without_selection | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | G_without_completion | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | G0 | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | B0 | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | PMX | 240 | acquisition_or_evaluator_unavailable |
| opentelemetry_demo | PMX_inclusive | 240 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | Gstar | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | GID | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | Gselected | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | G_without_deadline | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | G_without_selection | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | G_without_completion | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | G0 | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | B0 | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | PMX | 320 | acquisition_or_evaluator_unavailable |
| spring_petclinic_microservices | PMX_inclusive | 320 | acquisition_or_evaluator_unavailable |

## Measured stage costs

Shared acquisition and extraction are counted once. Stage and process totals overlap and must not be summed. Untimed integration labour, incremental update, monitoring off/on overhead and scaling are unknown, not zero.

| Method | Stage | Observations | Median seconds | P90 seconds |
| --- | --- | --- | --- | --- |

## Stable and source-only transfer views

The unchanged forecasts on stable attempts are in `stable.csv`; primary results use all qualified attempts. Source-only transfer reports 0 points over 8000 planned slots (coverage 0). Unsupported transfer is not replaced by target calibration.

## Reuse and audit scope

CSV files retain all operations, statuses, exact serialized structured fields and missing values. The source comparison JSON and its separate candidate/evaluator seals remain the authority. Archive verification proves retention integrity; full run-level scientific qualification must be assessed separately.
