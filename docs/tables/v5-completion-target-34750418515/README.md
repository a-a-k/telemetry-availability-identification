# Completion/deadline target: identification, joint differences and costs

All 120 planned calibration/test positions are retained. E versus R tests sufficiency; the three R routes must agree on common support. See operation-baseline.csv and all-mask-settings.csv for all bounds, support and external checks.

Costs below are median first-answer seconds over three paired rounds. Full/direct ratios are formed within each round before aggregation. All routes compute R with relevant-coordinate optimization; process start, input decoding, construction and saved first answers are included. Repeated ready-model queries are separate. Source telemetry export and archive verification are outside the boundary. Copies add no independent observations.

| Application | Attempts | Full → R, s | Full → projection → R, s | Direct → R, s | Full/direct | Projected/direct |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deathstarbench_social_network | 3600 | 1.609446 | 1.588221 | 1.508174 | 1.062826 | 1.053132 |
| deathstarbench_social_network | 7200 | 2.628986 | 2.635150 | 2.477996 | 1.058159 | 1.060640 |
| deathstarbench_social_network | 14400 | 4.869497 | 4.911142 | 4.377915 | 1.113751 | 1.114161 |
| opentelemetry_demo | 3600 | 4.027817 | 4.036858 | 3.887894 | 1.039223 | 1.027877 |
| opentelemetry_demo | 7200 | 7.304674 | 7.256753 | 7.018139 | 1.038608 | 1.036760 |
| opentelemetry_demo | 14400 | 14.517959 | 14.530901 | 14.160640 | 1.023953 | 1.027666 |
| spring_petclinic_microservices | 3600 | 1.997300 | 2.000653 | 1.893378 | 1.060917 | 1.054580 |
| spring_petclinic_microservices | 7200 | 3.305701 | 3.330947 | 3.103857 | 1.065963 | 1.071419 |
| spring_petclinic_microservices | 14400 | 6.050161 | 5.982446 | 5.398195 | 1.114623 | 1.108231 |

Every one of the 81 process observations, all stages and first-answer CPU/RSS are in [paired-costs.csv](paired-costs.csv). [cost-summary.csv](cost-summary.csv) includes ranges and volume growth; [ready-query-summary.csv](ready-query-summary.csv) reports every operation and route.

Masking uses identical attempt/primitive-coordinate keys for both routes, before completion aggregation. The native-failure-associated mask uses observed completion failures, not external Y; it is explicitly distinct from the earlier Y-associated mechanism. State masks keep the declared group vocabulary and deadline observations fixed. Additional topology discovery from deleted traces is outside this experiment.
