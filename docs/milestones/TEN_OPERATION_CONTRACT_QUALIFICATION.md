# Новая версия шести прежних contracts прошла live qualification

Run [34205650183](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34205650183), head `a5b71467b69dff6ee1d3d6bacc7bace5497654c1`: оба application jobs success по заранее заданному [protocol](../EXISTING_APPLICATION_CONTRACT_QUALIFICATION_PROTOCOL.md). В каждом приложении все 240 normal-state attempts и три sentinels прошли новые external contracts. Каждая из шести операций дала 80/80 timely complete successes, все проверки counts/IDs/deadlines/trace-linkage true, invalid native traces и malformed records отсутствуют. Это проверка interface до main, не availability effectiveness result.

| Приложение | Операции | Baseline attempts | Sentinels | Job wall |
| --- | ---: | ---: | ---: | ---: |
| DeathStar | 3 | 240/240 | 3/3 | 178 s |
| OTel | 3 | 240/240 | 3/3 | 232 s |

Job wall включает setup/pull/start/qualification/log/artifact stages, не только 60 s baseline и не стоимость модели. Отдельные GNU time/RSS для pull/start/qualification и Docker stats snapshots сохранены. Они не доказывают monitoring overhead или peak memory всех контейнеров во времени.

Изменения contracts проверены на реальных pinned responses: OTel product/cart/order содержит ожидаемые поля, unique cart user/quantity и full checkout payload проходят; одна общая 2 s граница применяется ко всей HTTP sequence. Все intermediate HTTP payloads/IDs/offsets находятся в raw artifact. Предварительно искусственные controls доказали failure для трёх шагов по 0.8 s, wrong prerequisite, partial response и dribble-body timeout. DeathStar сохраняет исходное acknowledgement/timeline predicate с явно ограниченной completeness claim. Подробная [таблица всех десяти событий](../TEN_EXTERNAL_OPERATION_CONTRACTS.md).

Четыре Petclinic contracts уже отдельно прошли 192 deterministic fault-control attempts в [qualified runtime](PETCLINIC_RUNTIME_QUALIFICATION.md). Совместно это даёт live interface qualification десяти операций, но не означает завершения stochastic/PMX/main comparisons. Старые M7 outcomes и методы не изменены, temporal ML не добавлялась.

[Verified archive inventory](../evidence/ten-contract-34205650183/verified-archives.json) содержит actual ZIP sizes/SHA, source API metadata и summary hashes. Оба exact compact ZIP и все их файлы сохранены в Git после byte-by-byte сверки с архивами. Полные application/native artifacts остаются remote на 90 days; локально не загружались. Source application commits/OCI lock manifests находятся рядом с summaries.
