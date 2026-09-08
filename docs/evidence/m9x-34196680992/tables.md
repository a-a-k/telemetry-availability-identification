# M9X: воспроизводимые численные таблицы

Только четыре сохранённые M7 NCD/r0 кампании, 12 operation cells, 14 400 test requests. Прогнозы — вероятности; ошибки — процентные пункты. «—» означает сохранённое отсутствие прогноза.

| Приложение | Placement | Операция | Наблюдение | proposed | B2 | B0 | endpoint_all | PMX inclusive | PMX conditional |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DeathStar | colocated | compose_post | 0.829167 | — | — | 0.847211 | 0.847500 | 0.819250 | 0.847500 |
| DeathStar | colocated | read_home_timeline | 1.000000 | 0.993827 | 0.993827 | 0.999584 | 1.000000 | 1.000000 | 1.000000 |
| DeathStar | colocated | read_user_timeline | 0.785833 | — | — | 0.812240 | 0.812500 | 0.775260 | 0.812500 |
| DeathStar | split | compose_post | 0.824167 | 0.905786 | 0.887006 | 0.870525 | 0.870833 | 0.842531 | 0.870833 |
| DeathStar | split | read_home_timeline | 1.000000 | 0.993827 | 0.993827 | 0.999584 | 1.000000 | 1.000000 | 1.000000 |
| DeathStar | split | read_user_timeline | 0.770000 | 0.905786 | 0.887006 | 0.824729 | 0.825000 | 0.794750 | 0.825000 |
| OTel | colocated | add_to_cart | 0.804167 | — | — | 0.842215 | 0.842500 | 0.703347 | — |
| OTel | colocated | browse_product | 0.796667 | 0.872957 | 0.852498 | 0.846378 | 0.846667 | 0.709755 | — |
| OTel | colocated | checkout | 0.725833 | — | — | 0.754788 | 0.755000 | 0.572097 | — |
| OTel | split | add_to_cart | 0.814167 | — | — | 0.780600 | 0.780833 | 0.584819 | — |
| OTel | split | browse_product | 0.798333 | — | — | 0.801415 | 0.801667 | 0.616418 | — |
| OTel | split | checkout | 0.677500 | — | — | 0.629059 | 0.629167 | 0.395504 | — |

Полный census текущих случаев: предложенный метод и B2 5/12, B0/endpoint_all/PMX inclusive 12/12, PMX conditional 6/12. Условный PMX не поддерживает все шесть OTel случаев из-за swallowed-child/positivity guards; proposed/B2 имеют семь topology_ambiguous_target_fraction. Все причины присутствуют в candidate-predictions/coverage-census.

## Ошибки и охват

Средние вычислены только на выданных прогнозах данного метода; строки с разным охватом нельзя использовать как общий рейтинг.

| View | Метод | Охват | Bias, п.п. | MAE, п.п. | Brier |
| --- | --- | --- | --- | --- | --- |
| all_sequence | B0 | 12/12 | +1.5208 | 2.9015 | 0.14130277 |
| stable | B0 | 12/12 | -1.3080 | 2.0767 | 0.12475828 |
| all_sequence | B2 | 5/12 | +4.4666 | 4.9604 | 0.10096747 |
| stable | B2 | 5/12 | +2.3731 | 2.8669 | 0.08498842 |
| all_sequence | PMX_conditional_local | 6/12 | +2.4444 | 2.4444 | 0.10636910 |
| stable | PMX_conditional_local | 6/12 | +0.0790 | 0.3643 | 0.09030249 |
| all_sequence | PMX_inclusive | 12/12 | -8.4342 | 9.1527 | 0.15741278 |
| stable | PMX_inclusive | 12/12 | -11.2629 | 11.2629 | 0.14765702 |
| all_sequence | endpoint_all | 12/12 | +1.5486 | 2.9097 | 0.14131285 |
| stable | endpoint_all | 12/12 | -1.2802 | 2.0633 | 0.12475457 |
| all_sequence | proposed | 5/12 | +5.6270 | 6.1208 | 0.10300019 |
| stable | proposed | 5/12 | +3.5335 | 4.0273 | 0.08622385 |

## Парные сравнения на общем охвате

Знак — comparator минус PMX. Каждая строка использует строго одни operation cells; это описательные контрасты открытых данных без CI или нового подтверждающего теста. По одному повтору на placement/NCD не даёт оценки вариации между повторами будущей серии.

| Приложение | PMX | Comparator | Общий охват | ΔMAE, п.п. | ΔBrier |
| --- | --- | --- | --- | --- | --- |
| DeathStar | PMX_inclusive | proposed | 4/6 | +4.6659 | +0.00605650 |
| DeathStar | PMX_inclusive | B2 | 4/6 | +3.7269 | +0.00419138 |
| DeathStar | PMX_inclusive | B0 | 6/6 | +1.3794 | +0.00083461 |
| DeathStar | PMX_inclusive | endpoint_all | 6/6 | +1.3844 | +0.00084834 |
| DeathStar | PMX_conditional_local | proposed | 4/6 | +3.2021 | +0.00499326 |
| DeathStar | PMX_conditional_local | B2 | 4/6 | +2.2631 | +0.00312814 |
| DeathStar | PMX_conditional_local | B0 | 6/6 | -0.0049 | -0.00001373 |
| DeathStar | PMX_conditional_local | endpoint_all | 6/6 | +0.0000 | +0.00000000 |
| OTel | PMX_inclusive | proposed | 1/6 | -1.0621 | -0.00173337 |
| OTel | PMX_inclusive | B2 | 1/6 | -3.1080 | -0.00443648 |
| OTel | PMX_inclusive | B0 | 6/6 | -13.8820 | -0.03305463 |
| OTel | PMX_inclusive | endpoint_all | 6/6 | -13.8704 | -0.03304822 |
| OTel | PMX_conditional_local | proposed | 0/6 | — | — |
| OTel | PMX_conditional_local | B2 | 0/6 | — | — |
| OTel | PMX_conditional_local | B0 | 0/6 | — | — |
| OTel | PMX_conditional_local | endpoint_all | 0/6 | — | — |

## Контекст и точная реконструкция

| Случай | Исходные операции | Контексты | Запросы | Spans с wrapper | Контекст, с |
| --- | --- | --- | --- | --- | --- |
| deathstar-colocated--compose_post | 18 | 18 | 1200 | 15094 | 1.9894 |
| deathstar-colocated--read_home_timeline | 4 | 4 | 1200 | 4800 | 0.6528 |
| deathstar-colocated--read_user_timeline | 7 | 9 | 1200 | 4339 | 0.7034 |
| deathstar-split--compose_post | 17 | 17 | 1200 | 15345 | 2.3337 |
| deathstar-split--read_home_timeline | 4 | 4 | 1200 | 4800 | 0.7052 |
| deathstar-split--read_user_timeline | 5 | 7 | 1200 | 4597 | 0.7405 |
| otel-colocated--add_to_cart | 9 | 13 | 1200 | 10759 | 2.1511 |
| otel-colocated--browse_product | 5 | 8 | 1200 | 5748 | 1.1418 |
| otel-colocated--checkout | 22 | 48 | 1200 | 27388 | 5.1097 |
| otel-split--add_to_cart | 9 | 13 | 1200 | 10235 | 2.1409 |
| otel-split--browse_product | 5 | 8 | 1200 | 5568 | 1.1676 |
| otel-split--checkout | 22 | 48 | 1200 | 25748 | 4.6329 |

## Стоимость

Полное время wall и peak RSS относятся к явно названному процессу; суммы последовательных стадий не равны времени параллельного workflow. Общий сбор M7 не повторялся и не приписан каждому методу.

| Стадия | Wall, с | Peak RSS, KiB |
| --- | --- | --- |
| M9X prepare, включая проверку/чтение сохранённых входов | 31.78 | 701380 |
| 12 прикладных PMX invocations, сумма / max RSS | 310.03 | 2893296 |
| 3 искусственных PMX invocations, сумма / max RSS | 66.64 | 320036 |
| Холодная сборка Palladio | 266.82 | 2529776 |
| Solver JVM/Maven, все 46 записей | 77.33 | 2409944 |

Контекстная проекция 12 случаев: 23.4689 с. Bridge 23 моделей: 0.1424 с. Сумма job wall: 1066 с. Все 11 ZIP: 42,503,493 байт.

Показываются отдельно startup PMX (20 с на вызов), build, process wall и каждый load/solve в costs.json. Новых fits предложенного метода нет, но это не нулевая стоимость его первоначального fit: раздельное время последнего здесь не выгружено. Человеко-минуты интеграции, отдельный monitoring overhead и масштабирование не измерены.
