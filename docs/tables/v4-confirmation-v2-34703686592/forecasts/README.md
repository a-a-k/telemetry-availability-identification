# Independent main comparison: retained remote tables

Source run `34703686592`, head `12ddb09369ee6e0b60ca4c7db6fe1e749530b7df`, mode `main`. Planned campaigns: 18; operation cells per method: 60; retained method slots: 600. Source SHA256: `71349aae975a745b614ec86742af76d554e7da6dd6143d75e6971c13e65db04f`.

These tables copy metrics already computed by the frozen remote analysis. No local fitting, replay, bootstrap or imputation is performed. Null estimates remain null. Own-support means cannot be interpreted as paired comparisons when support differs. This generated export is not a publication-readiness verdict.

## Own support and error

| Application | Method | Points / planned | MAE (pp) | Signed (pp) | Brier | Median AE (pp) | P90 AE (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| deathstarbench_social_network | Gstar | 18 / 18 | 0.944444 | 0.148148 | 0.0536055 | 0.375 | 2.64167 |
| deathstarbench_social_network | GID | 6 / 18 | 0 | 0 | 0 | 0 | 0 |
| deathstarbench_social_network | Gselected | 6 / 18 | 0 | 0 | 0 | 0 | 0 |
| deathstarbench_social_network | G_without_deadline | 6 / 18 | 0 | 0 | 0 | 0 | 0 |
| deathstarbench_social_network | G_without_selection | 18 / 18 | 0.944444 | 0.148148 | 0.0536055 | 0.375 | 2.64167 |
| deathstarbench_social_network | G_without_completion | 9 / 18 | 0.194444 | -0.194444 | 0.0166308 | 0 | 0.75 |
| deathstarbench_social_network | G0 | 18 / 18 | 5.9537 | 5.9537 | 0.059537 | 5.75 | 13.0083 |
| deathstarbench_social_network | B0 | 18 / 18 | 0.944444 | 0.148148 | 0.0536055 | 0.375 | 2.64167 |
| deathstarbench_social_network | PMX | 18 / 18 | 0.944444 | 0.148148 | 0.0536055 | 0.375 | 2.64167 |
| deathstarbench_social_network | PMX_inclusive | 18 / 18 | 0.809221 | -0.185602 | 0.053561 | 0.37184 | 2.64046 |
| opentelemetry_demo | Gstar | 12 / 18 | 2 | 0.490741 | 0.129267 | 1.91667 | 3.29167 |
| opentelemetry_demo | GID | 0 / 18 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | Gselected | 0 / 18 | not estimable | not estimable | not estimable | not estimable | not estimable |
| opentelemetry_demo | G_without_deadline | 10 / 18 | 2.04167 | 0.689815 | 0.130793 | 1.91667 | 2.96667 |
| opentelemetry_demo | G_without_selection | 12 / 18 | 2 | 0.490741 | 0.129267 | 1.91667 | 3.29167 |
| opentelemetry_demo | G_without_completion | 12 / 18 | 2 | 0.490741 | 0.129267 | 1.91667 | 3.29167 |
| opentelemetry_demo | G0 | 17 / 18 | 15.8241 | 15.8241 | 0.158241 | 12.4167 | 24.85 |
| opentelemetry_demo | B0 | 18 / 18 | 2.18519 | -0.212963 | 0.12887 | 2.08333 | 4.15 |
| opentelemetry_demo | PMX | 9 / 18 | 1.97059 | 1.93001 | 0.125695 | 1.83333 | 4.81473 |
| opentelemetry_demo | PMX_inclusive | 18 / 18 | 14.0005 | -14.0005 | 0.151725 | 12.653 | 22.3025 |
| spring_petclinic_microservices | Gstar | 24 / 24 | 0.925926 | 0.268519 | 0.0293121 | 0.111111 | 2.34444 |
| spring_petclinic_microservices | GID | 12 / 24 | 0 | 0 | 0 | 0 | 0 |
| spring_petclinic_microservices | Gselected | 12 / 24 | 0 | 0 | 0 | 0 | 0 |
| spring_petclinic_microservices | G_without_deadline | 12 / 24 | 0 | 0 | 0 | 0 | 0 |
| spring_petclinic_microservices | G_without_selection | 24 / 24 | 0.925926 | 0.268519 | 0.0293121 | 0.111111 | 2.34444 |
| spring_petclinic_microservices | G_without_completion | 12 / 24 | 0 | 0 | 0 | 0 | 0 |
| spring_petclinic_microservices | G0 | 24 / 24 | 3.125 | 3.125 | 0.03125 | 1.66667 | 7.61111 |
| spring_petclinic_microservices | B0 | 24 / 24 | 0.925926 | 0.268519 | 0.0293121 | 0.111111 | 2.34444 |
| spring_petclinic_microservices | PMX | 24 / 24 | 0.921976 | 0.274644 | 0.0293112 | 0.111111 | 2.34444 |
| spring_petclinic_microservices | PMX_inclusive | 24 / 24 | 1.26529 | -0.591467 | 0.0297451 | 0.0396123 | 3.13222 |

## Prespecified paired contrasts

Negative differences favour Gstar only on the displayed complete common campaign support. Intervals are the frozen paired campaign bootstrap, conditional on retained support. Nonsignificance does not establish equivalence and no finite-sample familywise guarantee is asserted.

| Application | Comparator | MAE difference (pp) | Interval (pp) | Complete campaigns | Common cells | Status |
| --- | --- | --- | --- | --- | --- | --- |
| deathstarbench_social_network | G0 | -5.00926 | [-5.773148148148147, -3.907407407407409] | 6 | 18 | estimable_on_reported_complete_common_support |
| deathstarbench_social_network | PMX | -1.85037e-15 | [-3.700743415417189e-15, 1.2335811384723961e-15] | 6 | 18 | estimable_on_reported_complete_common_support |
| opentelemetry_demo | G0 | -13.6574 | not estimable | 4 | 12 | point_only_insufficient_independent_common_campaigns |
| opentelemetry_demo | PMX | -0.0816981 | [-0.41899294342781684, 0.46691914356917036] | 3 | 9 | estimable_on_reported_complete_common_support |
| spring_petclinic_microservices | G0 | -2.19907 | [-2.4305555555555562, -1.9768518518518496] | 6 | 24 | estimable_on_reported_complete_common_support |
| spring_petclinic_microservices | PMX | 0.0039496 | [-0.003263969171483916, 0.009019905755933144] | 6 | 24 | estimable_on_reported_complete_common_support |

## Coverage limitations

| Application | Method | Absent cells | Reason |
| --- | --- | --- | --- |
| deathstarbench_social_network | GID | 12 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | Gselected | 12 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | G_without_deadline | 12 | not_point_identified_under_declared_observation_law |
| deathstarbench_social_network | G_without_completion | 9 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | Gstar | 5 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | Gstar | 1 | unexplained native parent boundary |
| opentelemetry_demo | GID | 17 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | GID | 1 | unexplained native parent boundary |
| opentelemetry_demo | Gselected | 17 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | Gselected | 1 | unexplained native parent boundary |
| opentelemetry_demo | G_without_deadline | 7 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | G_without_deadline | 1 | unexplained native parent boundary |
| opentelemetry_demo | G_without_selection | 5 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | G_without_selection | 1 | unexplained native parent boundary |
| opentelemetry_demo | G_without_completion | 5 | not_point_identified_under_declared_observation_law |
| opentelemetry_demo | G_without_completion | 1 | unexplained native parent boundary |
| opentelemetry_demo | G0 | 1 | shared_graph_extraction_unsupported: unexplained native parent boundary |
| opentelemetry_demo | PMX | 9 | unsupported_conditional_propagation_or_positivity |
| spring_petclinic_microservices | GID | 12 | not_point_identified_under_declared_observation_law |
| spring_petclinic_microservices | Gselected | 12 | not_point_identified_under_declared_observation_law |
| spring_petclinic_microservices | G_without_deadline | 12 | not_point_identified_under_declared_observation_law |
| spring_petclinic_microservices | G_without_completion | 12 | not_point_identified_under_declared_observation_law |

## Measured stage costs

Shared acquisition and extraction are counted once. Stage and process totals overlap and must not be summed. Untimed integration labour, incremental update, monitoring off/on overhead and scaling are unknown, not zero.

| Method | Stage | Observations | Median seconds | P90 seconds |
| --- | --- | --- | --- | --- |
| B0 | identification | 18 | 0.00596273 | 0.00616881 |
| G0 | identification | 59 | 0.00110424 | 0.00260731 |
| G0 | solve | 59 | 6.6013e-05 | 0.00010211 |
| PMX_shared_variants | derived_binary_build | 18 | 7.57 | 9.628 |
| PMX_shared_variants | independent_pmx_extraction_process | 60 | 23.4318 | 28.8644 |
| PMX_shared_variants | input_and_projection_process_total | 18 | 11.3754 | 19.9044 |
| PMX_shared_variants | native_projection | 60 | 2.34195 | 7.03218 |
| shared_acquisition | acquisition_and_export_process_total | 18 | 2096.92 | 2210.89 |
| shared_graph_family | extraction | 59 | 0.203327 | 0.696836 |
| shared_graph_family | identification | 59 | 0.00309346 | 0.00635948 |
| shared_graph_family | solve | 59 | 0.0011956 | 0.00356524 |
| shared_native_pool | native_parse | 18 | 3.34846 | 9.25012 |

## Stable and source-only transfer views

The unchanged forecasts on stable attempts are in `stable.csv`; primary results use all qualified attempts. Source-only transfer reports 0 points over 0 planned slots (coverage 0). Unsupported transfer is not replaced by target calibration.

## Reuse and audit scope

CSV files retain all operations, statuses, exact serialized structured fields and missing values. The source comparison JSON and its separate candidate/evaluator seals remain the authority. Archive verification proves retention integrity; full run-level scientific qualification must be assessed separately.
