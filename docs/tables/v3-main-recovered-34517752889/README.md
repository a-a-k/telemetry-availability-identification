# Independent main comparison: retained remote tables

Source run `34517752889`, head `d857ea65ca9da7fa9ae4ee1198317487475246a7`, mode `main`. Planned campaigns: 240; operation cells per method: 800; retained method slots: 8000. Source SHA256: `10144b774f57623070cd5057e783be1aade32cd7e8b946e1830f9a7c8eff2ccf`.

These tables copy metrics already computed by the frozen remote analysis. No local fitting, replay, bootstrap or imputation is performed. Null estimates remain null. Own-support means cannot be interpreted as paired comparisons when support differs. This generated export is not a publication-readiness verdict.

## Own support and error

| Application | Method | Points / planned | MAE (pp) | Signed (pp) | Brier | Median AE (pp) | P90 AE (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| deathstarbench_social_network | Gstar | 186 / 240 | 1.243 | -0.0413773 | 0.0714614 | 0.25 | 2.66667 |
| deathstarbench_social_network | GID | 201 / 240 | 7.84794 | 7.84794 | 0.0804755 | 7.08333 | 14.4167 |
| deathstarbench_social_network | Gselected | 121 / 240 | 2.87118 | 2.87118 | 0.0287118 | 0 | 13.0833 |
| deathstarbench_social_network | G_without_deadline | 180 / 240 | 6.23432 | 6.23432 | 0.0749824 | 5.5 | 12.5917 |
| deathstarbench_social_network | G_without_selection | 186 / 240 | 1.13264 | 0.251736 | 0.0714085 | 0.291667 | 2.375 |
| deathstarbench_social_network | G_without_completion | 126 / 240 | 0.571354 | -0.221007 | 0.0499096 | 0 | 1.83333 |
| deathstarbench_social_network | G0 | 201 / 240 | 8.12765 | 8.12765 | 0.0812765 | 7.16667 | 14.75 |
| deathstarbench_social_network | B0 | 240 / 240 | 1.21736 | 0.0930556 | 0.0711949 | 0.75 | 3.425 |
| deathstarbench_social_network | PMX | 240 / 240 | 1.21736 | 0.0930556 | 0.0711949 | 0.75 | 3.425 |
| deathstarbench_social_network | PMX_inclusive | 240 / 240 | 1.69832 | -0.998707 | 0.0715898 | 0.833333 | 5.07183 |
| opentelemetry_demo | Gstar | 135 / 240 | 2.14696 | 0.0453704 | 0.151203 | 1.75 | 4.38333 |
| opentelemetry_demo | GID | 240 / 240 | 20.2826 | 20.2826 | 0.205294 | 17.5417 | 32.7667 |
| opentelemetry_demo | Gselected | 126 / 240 | 17.4232 | 17.4232 | 0.175552 | 16.5417 | 29.6667 |
| opentelemetry_demo | G_without_deadline | 105 / 240 | 2.16057 | 0.378571 | 0.14491 | 1.58333 | 4.21667 |
| opentelemetry_demo | G_without_selection | 135 / 240 | 2.14431 | 0.169709 | 0.151216 | 1.75 | 4.33333 |
| opentelemetry_demo | G_without_completion | 129 / 240 | 2.47292 | 0.967361 | 0.158756 | 1.58333 | 4.35 |
| opentelemetry_demo | G0 | 240 / 240 | 20.7278 | 20.7278 | 0.207278 | 18.0833 | 33.4167 |
| opentelemetry_demo | B0 | 240 / 240 | 5.15208 | -0.890278 | 0.162795 | 2 | 13.1333 |
| opentelemetry_demo | PMX | 100 / 240 | 1.80243 | 0.145994 | 0.13932 | 1.32709 | 4.15042 |
| opentelemetry_demo | PMX_inclusive | 240 / 240 | 18.1889 | -17.2894 | 0.201021 | 14.7061 | 26.6925 |
| spring_petclinic_microservices | Gstar | 320 / 320 | 1.15069 | -0.457639 | 0.0427918 | 0 | 3.55556 |
| spring_petclinic_microservices | GID | 320 / 320 | 1.69618 | 1.60104 | 0.0432487 | 0.0555556 | 5.33333 |
| spring_petclinic_microservices | Gselected | 164 / 320 | 0.0787037 | 0.0324074 | 0.00205163 | 0 | 0 |
| spring_petclinic_microservices | G_without_deadline | 160 / 320 | 0 | 0 | 0 | 0 | 0 |
| spring_petclinic_microservices | G_without_selection | 320 / 320 | 1.075 | -0.188194 | 0.0427674 | 0 | 3.23333 |
| spring_petclinic_microservices | G_without_completion | 164 / 320 | 0.115741 | -0.115741 | 0.00206703 | 0 | 0 |
| spring_petclinic_microservices | G0 | 320 / 320 | 4.82639 | 4.82639 | 0.0482639 | 0.722222 | 13.7889 |
| spring_petclinic_microservices | B0 | 320 / 320 | 1.02812 | 0.0815972 | 0.0427436 | 0 | 3.11111 |
| spring_petclinic_microservices | PMX | 320 / 320 | 1.02719 | 0.0917177 | 0.0427428 | 0 | 3.11111 |
| spring_petclinic_microservices | PMX_inclusive | 320 / 320 | 2.06703 | -1.44599 | 0.0440105 | 0 | 7.12574 |

## Prespecified paired contrasts

Negative differences favour Gstar only on the displayed complete common campaign support. Intervals are the frozen paired campaign bootstrap, conditional on retained support. Nonsignificance does not establish equivalence and no finite-sample familywise guarantee is asserted.

| Application | Comparator | MAE difference (pp) | Interval (pp) | Complete campaigns | Common cells | Status |
| --- | --- | --- | --- | --- | --- | --- |
| deathstarbench_social_network | G0 | -6.99387 | not estimable | 52 | 186 | point_only_insufficient_independent_common_campaigns |
| deathstarbench_social_network | PMX | 0.109664 | not estimable | 52 | 186 | point_only_insufficient_independent_common_campaigns |
| opentelemetry_demo | G0 | -17.2931 | not estimable | 45 | 135 | point_only_insufficient_independent_common_campaigns |
| opentelemetry_demo | PMX | 0.157053 | [-0.16164288731329923, 0.44218461177295304] | 31 | 100 | estimable_on_reported_complete_common_support |
| spring_petclinic_microservices | G0 | -3.67569 | [-4.025928819444444, -3.325924479166667] | 80 | 320 | estimable_on_reported_complete_common_support |
| spring_petclinic_microservices | PMX | 0.123509 | [-0.011341600199597669, 0.25678273106736255] | 80 | 320 | estimable_on_reported_complete_common_support |

## Coverage limitations

| Application | Method | Absent cells | Reason |
| --- | --- | --- | --- |
| deathstarbench_social_network | Gstar | 15 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | Gstar | 39 | unexplained native parent boundary |
| deathstarbench_social_network | GID | 39 | unexplained native parent boundary |
| deathstarbench_social_network | Gselected | 80 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | Gselected | 39 | unexplained native parent boundary |
| deathstarbench_social_network | G_without_deadline | 21 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | G_without_deadline | 39 | unexplained native parent boundary |
| deathstarbench_social_network | G_without_selection | 15 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | G_without_selection | 39 | unexplained native parent boundary |
| deathstarbench_social_network | G_without_completion | 75 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | G_without_completion | 39 | unexplained native parent boundary |
| deathstarbench_social_network | G0 | 39 | shared_graph_extraction_unsupported: unexplained native parent boundary |
| opentelemetry_demo | Gstar | 105 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | Gselected | 114 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | G_without_deadline | 135 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | G_without_selection | 105 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | G_without_completion | 111 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | PMX | 140 | unsupported_conditional_propagation_or_positivity |
| spring_petclinic_microservices | Gselected | 156 | not_point_identified_under_declared_observation_law |
| spring_petclinic_microservices | G_without_deadline | 160 | not_point_identified_under_declared_observation_law |
| spring_petclinic_microservices | G_without_completion | 156 | not_point_identified_under_declared_observation_law |

## Measured stage costs

Shared acquisition and extraction are counted once. Stage and process totals overlap and must not be summed. Untimed integration labour, incremental update, monitoring off/on overhead and scaling are unknown, not zero.

| Method | Stage | Observations | Median seconds | P90 seconds |
| --- | --- | --- | --- | --- |
| B0 | identification | 240 | 0.00603923 | 0.00629387 |
| G0 | identification | 761 | 0.000198752 | 0.000601647 |
| G0 | solve | 761 | 8.9035e-05 | 0.000124439 |
| PMX_shared_variants | derived_binary_build | 240 | 8.875 | 12.599 |
| PMX_shared_variants | independent_pmx_extraction_process | 800 | 23.4831 | 29.0209 |
| PMX_shared_variants | input_and_projection_process_total | 240 | 11.3436 | 21.4513 |
| PMX_shared_variants | native_projection | 800 | 2.4378 | 6.956 |
| shared_acquisition | acquisition_and_export_process_total | 240 | 2081.69 | 2120.39 |
| shared_graph_family | extraction | 761 | 0.200484 | 0.751076 |
| shared_graph_family | identification | 761 | 0.00314813 | 0.00624504 |
| shared_graph_family | solve | 761 | 0.00109073 | 0.003624 |
| shared_native_pool | native_parse | 240 | 3.30599 | 9.33331 |

## Stable and source-only transfer views

The unchanged forecasts on stable attempts are in `stable.csv`; primary results use all qualified attempts. Source-only transfer reports 0 points over 8000 planned slots (coverage 0). Unsupported transfer is not replaced by target calibration.

## Reuse and audit scope

CSV files retain all operations, statuses, exact serialized structured fields and missing values. The source comparison JSON and its separate candidate/evaluator seals remain the authority. Archive verification proves retention integrity; full run-level scientific qualification must be assessed separately.
