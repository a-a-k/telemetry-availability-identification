# Итерация 006: TCP health не гарантирует доступность единственного пути

Вопрос и ожидаемые проверки заранее заданы в [v2 protocol](../PETCLINIC_RUNTIME_V2_PROTOCOL.md). Run [34200559774](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34200559774), head `a1d0d4c07acb611777af171e2613cb6921dffc9d`, завершился failure после всех 192 попыток. Все native-trace gates прошли; два контроля одиночного пути не прошли. При доступной только a карточка дала 0/8, при доступной только b запись дала 0/8: round-robin продолжал направлять соответствующую операцию в paused process, чей TCP backlog принимал соединение.

Исходные 192 verdicts, container states, exact compact ZIP и provenance сохранены в [evidence](../evidence/petclinic-v2-34200559774/bootstrap-summary.json). ZIP 164974 B, SHA256 `2793a59b941c63c306c2f75b5c18ccb86a139e4d174599d5669490f3c741c935`; actual ZIP и все извлечённые файлы проверены. Ни один timeout не превращён в success.

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | Здесь нет fits; [002](002-original-formalism-map.md) без изменений. | Primary без ML. |
| C02 | ПРОВЕРЕНО | Исходная карта формализма сохранена; контейнеры/DB отражены в compose. | Petclinic candidate representation ещё требуется. |
| C03 | ПРОВЕРЕНО | [001](001-m7-complete-census.md), все 160/480 сохранены. | Контроли не добавляют main n. |
| C04 | ПРОВЕРЕНО | Все четыре v2 contracts исполнялись по 48 раз; DTO corrections работают. | Общие deadlines шести прежних операций ещё надо обновить отдельно. |
| C05 | ПРОВЕРЕНО | 192 unique attempts, 192 Gateway SERVER traces, clean native parse, обе replica identities. | Это bounded controls, не будущая stochastic linkage. |
| C06 | ОТКЛОНЕНИЕ | Normal и recovered 32/32; два single-path operation controls провалены. | Нужна корректировка proxy health, тот же image. |
| C07 | ОТКЛОНЕНИЕ | Both-down и live-process communication failure действуют; TCP health удерживает paused path UP. | v3 HTTP health + отдельный TCP/HTTP контрпример для каждой реплики. |
| C08 | ПРОВЕРЕНО | Семантический oracle обнаружил ошибку runtime; [003](003-pmx-context-comparison.md) calculator controls действуют. | Модельные controls Petclinic впереди. |
| C09 | ПРОВЕРЕНО | Независимая историческая PMX qualification [003] сохранена. | Petclinic PMX не запускался. |
| C10 | ПРОВЕРЕНО | HTTP-200 empty-visits fallback остаётся failure; timeout также failure. | Модели должны получать тот же внешний event. |
| C11 | НЕ ПРОВЕРЕНО | Это шесть детерминированных controls. | Не восемь stochastic условий и не main matrix. |
| C12 | Н/П | Fits отсутствуют. | Future learner/evaluator separation остаётся обязательной. |
| C13 | НЕ ПРОВЕРЕНО | Main campaigns=0. | Новые 800 operation cells впереди. |
| C14 | Н/П | Accuracy/significance здесь не вычисляются. | Нельзя выдавать долю control successes за availability estimate. |
| C15 | ПРОВЕРЕНО | Все 192 исходные verdicts и failed gates сохранены. | Полный source artifact остаётся remote. |
| C16 | НЕ ПРОВЕРЕНО | Transfer не выполнялся. | Source-only contract не ослаблен. |
| C17 | ПРОВЕРЕНО | Image restore проверяет actual archive и 16 файлов; compose up 13.56 s, down 4.51 s. | Эти стадии не равны полной стоимости приложения/моделей; их RSS — CLI, не sum контейнеров. |
| C18 | ПРОВЕРЕНО | Причина связана с TCP health; versioned v3 повторит все затронутые 192 controls. | Frozen v2 evidence/config не изменяются. |
| C19 | ПРОВЕРЕНО | Exact artifact/hash/head/image provenance в evidence. | Native ZIP не загружается локально. |
| C20 | ПРОВЕРЕНО | DTO и tracing исправлены, получены trace census и конкретный новый failover дефект. | Следующее действие проверяет установленную причину. |
| C21 | ПРОВЕРЕНО | V2 явно не qualified; trace qualification не объявлена availability qualification. | Ни новых effectiveness, ни superiority claims. |
| C22 | ПРОВЕРЕНО | Протокол, failure evidence и все 22 статуса сохранены. | Глобальный публикационный пакет не закрыт этой итерацией. |
