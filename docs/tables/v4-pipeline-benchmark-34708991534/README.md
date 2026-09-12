# Revised telemetry-to-first-answer pipeline and Palladio scaling

Run 34708991534, measurement source 4d5270008e6845bc55220869da721698be347e68. All 27 planned pairs are retained: fixed split/N/0 calibration for each application, volumes 3600/7200/14400 and three technical rounds. Copies are computational workloads, not independent observations.

The primary boundary starts at sealed prepared calibration roles with installed tools and ends at the first saved forecasts. Graph: revised v4 binding, six variants plus G0/B0, one build process. PMX: independent native projection/extraction, conditional_local and inclusive, collection, one application-only Palladio pass, saved first candidates. Interpreter/JVM starts and serialization are included. Acquisition, common role projection, transfer, replication and tool installation precede the boundary.

All additional graph replay, separate PMX second passes, known-probability controls and comparisons to frozen source forecasts follow ALL nine measurement pairs for the application. Their 57 retained process observations appear separately in verification-processes.csv and are not added to primary times. Qualification is required before a measured pair can become a successful speed ratio. Raw first/second solver files remain separate; the unchanged validator receives them as passes 0/1 after timing.

pipeline-summary.csv has median/min/max over three pairs per application/volume; speed ratios are formed within each pair first. paired-pipelines.csv keeps every original pair; stage-processes.csv keeps every primary command and resource. CPU is the sum of disjoint timed commands; memory is the greatest recorded process/children peak, not total runner RSS. Failure rows remain failures, never zero-time solves.

The original 20-second PMX launcher per operation is included. Startup-subtracted arithmetic is a decomposition of measured time, not a measurement of an optimized implementation. All graph-family results are computed, so graph time is an upper bound on Gstar-only work in this implementation. The PMX model count excludes the eight separate control models.

Scaling preserves empirical observations and topology, with renamed request/trace/span identities and shared probes. It measures input-volume scaling at fixed structure, not asymptotic growth in service count. Forecast points/statuses/bounds must reproduce source values to 1e-12. This is distinct from native exact-solver costs on already identified models and from the older two-pass verified-pipeline boundary.

Protocol: docs/V4_PIPELINE_BENCHMARK_V1.md; all clocks, resource scopes, recorded omissions and source hashes remain explicit.

## Полная таблица девяти сочетаний приложения и объёма

Время и парное ускорение: медиана [минимум; максимум] трёх повторов. CPU и память: медианы. Дополнительные проверки исключены из этих времён у обоих методов.

| Приложение | Попытки | Проверено пар | Наш конвейер, с | PMX/Palladio, с | PMX / наш, × | CPU наш / PMX, с | Память наш / PMX, MiB |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| DeathStarBench | 3600 | 3/3 | 2.421 [2.372; 2.548] | 167.907 [166.928; 171.856] | 69.367 [67.449; 70.371] | 2.950 / 245.830 | 208.223 / 2389.809 |
| DeathStarBench | 7200 | 3/3 | 4.127 [4.125; 4.176] | 191.862 [190.036; 192.308] | 46.047 [45.941; 46.618] | 4.700 / 279.480 | 306.637 / 3608.156 |
| DeathStarBench | 14400 | 3/3 | 7.885 [7.834; 8.034] | 249.690 [248.569; 250.622] | 31.731 [31.079; 31.783] | 8.440 / 373.460 | 521.035 / 4379.801 |
| OpenTelemetry | 3600 | 3/3 | 3.224 [3.122; 3.325] | 178.677 [175.093; 178.713] | 55.431 [53.744; 56.081] | 3.620 / 236.290 | 444.691 / 1852.469 |
| OpenTelemetry | 7200 | 3/3 | 5.980 [5.884; 5.984] | 264.828 [264.145; 266.138] | 44.503 [44.144; 45.009] | 6.440 / 398.910 | 787.871 / 2591.586 |
| OpenTelemetry | 14400 | 3/3 | 12.093 [11.990; 12.098] | 586.017 [585.881; 589.719] | 48.766 [48.437; 48.865] | 12.580 / 1004.320 | 1473.699 / 4355.898 |
| Petclinic | 3600 | 3/3 | 1.772 [1.771; 1.879] | 177.718 [177.628; 180.039] | 100.239 [95.826; 100.339] | 2.280 / 206.000 | 234.203 / 1604.094 |
| Petclinic | 7200 | 3/3 | 2.974 [2.922; 2.976] | 195.375 [195.308; 195.722] | 65.819 [65.619; 66.873] | 3.460 / 235.800 | 366.203 / 2293.723 |
| Petclinic | 14400 | 3/3 | 5.276 [5.179; 5.278] | 251.446 [251.367; 252.375] | 47.818 [47.655; 48.538] | 5.770 / 327.160 | 630.676 / 3798.812 |

## Все 27 исходных пар

Повтор — технический, начинается с 0. Порядок методов сохранён. Отказ не превращается в успешный коэффициент ускорения.

| Приложение | Повтор | Попытки | Порядок | Статус | Наш, с | PMX, с | PMX / наш, × |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| DeathStarBench | 0 | 3600 | graph/pmx | qualified | 2.548 | 171.856 | 67.449 |
| DeathStarBench | 0 | 7200 | pmx/graph | qualified | 4.176 | 191.862 | 45.941 |
| DeathStarBench | 0 | 14400 | graph/pmx | qualified | 8.034 | 249.690 | 31.079 |
| DeathStarBench | 1 | 7200 | graph/pmx | qualified | 4.125 | 192.308 | 46.618 |
| DeathStarBench | 1 | 14400 | pmx/graph | qualified | 7.885 | 250.622 | 31.783 |
| DeathStarBench | 1 | 3600 | pmx/graph | qualified | 2.372 | 166.928 | 70.371 |
| DeathStarBench | 2 | 14400 | graph/pmx | qualified | 7.834 | 248.569 | 31.731 |
| DeathStarBench | 2 | 3600 | graph/pmx | qualified | 2.421 | 167.907 | 69.367 |
| DeathStarBench | 2 | 7200 | pmx/graph | qualified | 4.127 | 190.036 | 46.047 |
| OpenTelemetry | 0 | 3600 | graph/pmx | qualified | 3.224 | 178.713 | 55.431 |
| OpenTelemetry | 0 | 7200 | pmx/graph | qualified | 5.984 | 264.145 | 44.144 |
| OpenTelemetry | 0 | 14400 | graph/pmx | qualified | 11.990 | 585.881 | 48.865 |
| OpenTelemetry | 1 | 7200 | graph/pmx | qualified | 5.980 | 266.138 | 44.503 |
| OpenTelemetry | 1 | 14400 | pmx/graph | qualified | 12.093 | 589.719 | 48.766 |
| OpenTelemetry | 1 | 3600 | pmx/graph | qualified | 3.325 | 178.677 | 53.744 |
| OpenTelemetry | 2 | 14400 | graph/pmx | qualified | 12.098 | 586.017 | 48.437 |
| OpenTelemetry | 2 | 3600 | graph/pmx | qualified | 3.122 | 175.093 | 56.081 |
| OpenTelemetry | 2 | 7200 | pmx/graph | qualified | 5.884 | 264.828 | 45.009 |
| Petclinic | 0 | 3600 | graph/pmx | qualified | 1.879 | 180.039 | 95.826 |
| Petclinic | 0 | 7200 | pmx/graph | qualified | 2.976 | 195.308 | 65.619 |
| Petclinic | 0 | 14400 | graph/pmx | qualified | 5.276 | 251.446 | 47.655 |
| Petclinic | 1 | 7200 | graph/pmx | qualified | 2.922 | 195.375 | 66.873 |
| Petclinic | 1 | 14400 | pmx/graph | qualified | 5.179 | 251.367 | 48.538 |
| Petclinic | 1 | 3600 | pmx/graph | qualified | 1.771 | 177.718 | 100.339 |
| Petclinic | 2 | 14400 | graph/pmx | qualified | 5.278 | 252.375 | 47.818 |
| Petclinic | 2 | 3600 | graph/pmx | qualified | 1.772 | 177.628 | 100.239 |
| Petclinic | 2 | 7200 | pmx/graph | qualified | 2.974 | 195.722 | 65.819 |

## Масштабирование по объёму наблюдений

Фиксированы структура и эмпирический закон; копирование не увеличивает независимую выборку.

| Приложение | Метод | Попытки | T(N) / T(3600) | Память / память(3600) | Попыток/с |
| --- | --- | ---: | ---: | ---: | ---: |
| DeathStarBench | graph | 3600 | 1.000 | 1.000 | 1487.259 |
| DeathStarBench | pmx | 3600 | 1.000 | 1.000 | 21.440 |
| DeathStarBench | graph | 7200 | 1.705 | 1.473 | 1744.591 |
| DeathStarBench | pmx | 7200 | 1.143 | 1.510 | 37.527 |
| DeathStarBench | graph | 14400 | 3.258 | 2.502 | 1826.152 |
| DeathStarBench | pmx | 14400 | 1.487 | 1.833 | 57.671 |
| OpenTelemetry | graph | 3600 | 1.000 | 1.000 | 1116.609 |
| OpenTelemetry | pmx | 3600 | 1.000 | 1.000 | 20.148 |
| OpenTelemetry | graph | 7200 | 1.855 | 1.772 | 1203.968 |
| OpenTelemetry | pmx | 7200 | 1.482 | 1.399 | 27.187 |
| OpenTelemetry | graph | 14400 | 3.751 | 3.314 | 1190.789 |
| OpenTelemetry | pmx | 14400 | 3.280 | 2.351 | 24.573 |
| Petclinic | graph | 3600 | 1.000 | 1.000 | 2031.556 |
| Petclinic | pmx | 3600 | 1.000 | 1.000 | 20.257 |
| Petclinic | graph | 7200 | 1.678 | 1.564 | 2421.290 |
| Petclinic | pmx | 7200 | 1.099 | 1.430 | 36.852 |
| Petclinic | graph | 14400 | 2.978 | 2.693 | 2729.138 |
| Petclinic | pmx | 14400 | 1.415 | 2.368 | 57.269 |

Все неперекрывающиеся команды основного таймера и CPU/RSS сохранены в [stage-processes.csv](stage-processes.csv); дополнительные проверки — в [verification-processes.csv](verification-processes.csv). [Полная сводка](pipeline-summary.csv) включает объёмы входов, spans, графы, категории, точечную поддержку, прикладные PCM-модели и арифметическое разложение фиксированного запуска PMX.
