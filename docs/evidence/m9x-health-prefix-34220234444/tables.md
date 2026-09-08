# M9X: исправление health decoder на прежних четырёх кампаниях

Старые таблицы сохранены. Новая версия использует исправленные M7 forecasts и общий исправленный stable mask. PMX forecasts и endpoint_all неизменны. Это описательное сравнение development data; новых PMX runs, кампаний и доверительных интервалов нет.

| View | Метод | Охват | Прежняя MAE, pp | Исправленная MAE, pp | Изменение, pp |
| --- | --- | --- | --- | --- | --- |
| all_sequence | B0 | 12/12 | 2.901454 | 2.901454 | +0.000000 |
| all_sequence | B2 | 5/12 | 4.960446 | 5.016334 | +0.055887 |
| all_sequence | PMX_conditional_local | 6/12 | 2.444444 | 2.444444 | +0.000000 |
| all_sequence | PMX_inclusive | 12/12 | 9.152744 | 9.152744 | +0.000000 |
| all_sequence | endpoint_all | 12/12 | 2.909722 | 2.909722 | +0.000000 |
| all_sequence | proposed | 5/12 | 6.120841 | 6.143610 | +0.022769 |
| stable | B0 | 12/12 | 2.076696 | 2.071226 | -0.005470 |
| stable | B2 | 5/12 | 2.866921 | 2.942280 | +0.075359 |
| stable | PMX_conditional_local | 6/12 | 0.364266 | 0.396252 | +0.031986 |
| stable | PMX_inclusive | 12/12 | 11.262933 | 11.241237 | -0.021696 |
| stable | endpoint_all | 12/12 | 2.063328 | 2.057858 | -0.005470 |
| stable | proposed | 5/12 | 4.027315 | 4.069556 | +0.042240 |

Парные ΔMAE = comparator − PMX на строго общем охвате; отрицательное значение означает меньшую MAE comparator только на этом подмножестве. Пустой охват не оценивается.

| View | Приложение | PMX | Comparator | Общий охват | ΔMAE, pp |
| --- | --- | --- | --- | --- | --- |
| all_sequence | deathstarbench_social_network | PMX_inclusive | proposed | 4/6 | +4.676167 |
| all_sequence | deathstarbench_social_network | PMX_inclusive | B2 | 4/6 | +3.763019 |
| all_sequence | deathstarbench_social_network | PMX_inclusive | B0 | 6/6 | +1.379437 |
| all_sequence | deathstarbench_social_network | PMX_inclusive | endpoint_all | 6/6 | +1.384375 |
| all_sequence | deathstarbench_social_network | PMX_conditional_local | proposed | 4/6 | +3.212365 |
| all_sequence | deathstarbench_social_network | PMX_conditional_local | B2 | 4/6 | +2.299217 |
| all_sequence | deathstarbench_social_network | PMX_conditional_local | B0 | 6/6 | -0.004938 |
| all_sequence | deathstarbench_social_network | PMX_conditional_local | endpoint_all | 6/6 | +0.000000 |
| all_sequence | opentelemetry_demo | PMX_inclusive | proposed | 1/6 | -0.989247 |
| all_sequence | opentelemetry_demo | PMX_inclusive | B2 | 1/6 | -2.973035 |
| all_sequence | opentelemetry_demo | PMX_inclusive | B0 | 6/6 | -13.882018 |
| all_sequence | opentelemetry_demo | PMX_inclusive | endpoint_all | 6/6 | -13.870419 |
| all_sequence | opentelemetry_demo | PMX_conditional_local | proposed | 0/6 | — |
| all_sequence | opentelemetry_demo | PMX_conditional_local | B2 | 0/6 | — |
| all_sequence | opentelemetry_demo | PMX_conditional_local | B0 | 0/6 | — |
| all_sequence | opentelemetry_demo | PMX_conditional_local | endpoint_all | 0/6 | — |
| stable | deathstarbench_social_network | PMX_inclusive | proposed | 4/6 | +2.328779 |
| stable | deathstarbench_social_network | PMX_inclusive | B2 | 4/6 | +1.415631 |
| stable | deathstarbench_social_network | PMX_inclusive | B0 | 6/6 | -1.667170 |
| stable | deathstarbench_social_network | PMX_inclusive | endpoint_all | 6/6 | -1.680550 |
| stable | deathstarbench_social_network | PMX_conditional_local | proposed | 4/6 | +3.212365 |
| stable | deathstarbench_social_network | PMX_conditional_local | B2 | 4/6 | +2.299217 |
| stable | deathstarbench_social_network | PMX_conditional_local | B0 | 6/6 | +0.013380 |
| stable | deathstarbench_social_network | PMX_conditional_local | endpoint_all | 6/6 | -0.000000 |
| stable | opentelemetry_demo | PMX_inclusive | proposed | 1/6 | -3.717317 |
| stable | opentelemetry_demo | PMX_inclusive | B2 | 1/6 | -5.701105 |
| stable | opentelemetry_demo | PMX_inclusive | B0 | 6/6 | -16.672851 |
| stable | opentelemetry_demo | PMX_inclusive | endpoint_all | 6/6 | -16.686208 |
| stable | opentelemetry_demo | PMX_conditional_local | proposed | 0/6 | — |
| stable | opentelemetry_demo | PMX_conditional_local | B2 | 0/6 | — |
| stable | opentelemetry_demo | PMX_conditional_local | B0 | 0/6 | — |
| stable | opentelemetry_demo | PMX_conditional_local | endpoint_all | 0/6 | — |

Все test attempts: 14400; stable: 10204 → 10132. PMX inclusive own coverage 12/12, conditional 6/12; причин улучшения и основного преимущества это не устанавливает.
