# Итерация 005: образ построен, live warmup выявил DTO/tracing дефекты

Вопрос/ожидание до запуска — [JDK correction protocol](../PETCLINIC_BOOTSTRAP_JDK_CORRECTION.md): установить тот же verified JDK и выполнить неизменный bootstrap. Run 34199064678/head 591e5760a0bc4802cec660c24bf12c30fd2ee7e8 построил source без Java-изменений, затем сохранил 243 warmup attempts и завершился failure по исходному 420 s gate. [Exact compact archive, build manifest и полный census](../evidence/petclinic-bootstrap-34199064678/failure-census.json).

Новое доказательство: приложение отвечает, исходная БД и оба Visits доступны; ошибка сравнения описания данных — birthDate timestamp и name-only PetType DTO. Логи также доказали, что старый switch не отключает Micrometer/Zipkin в Boot 4. Прежний текст контракта/трассировки был неточен, а не приложение «недоступно». Причины и отдельное исправление определены в [v2 protocol](../PETCLINIC_RUNTIME_V2_PROTOCOL.md). Основных кампаний, fault-control попыток, модельных fits и прогнозов нет.

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | Build/probe не обучают модели; [003](003-pmx-context-comparison.md) без изменений. | Primary остаётся без ML. |
| C02 | ПРОВЕРЕНО | [002 specification](../ORIGINAL_MODEL_NO_ML_SPECIFICATION.md) сохранена; Petclinic Java источники закреплены. | Интеграция его зависимостей в candidate models ещё впереди. |
| C03 | ПРОВЕРЕНО | [001 M7 census](001-m7-complete-census.md) не менялся. | Warmup не увеличивает n. |
| C04 | ОТКЛОНЕНИЕ | 69 HTTP-200 replies каждой read owners/card операции отвергнуты oracle; source Pet.Date и Gateway PetType объясняют mismatches. | v2 учитывает UTC-midnight birthDate и name-only тип только в карточке; остальные поля/deadlines/visits сохраняются. |
| C05 | НЕ ПРОВЕРЕНО | 243/243 unique warmup request IDs сохранены с исходными verdicts. | До native control census дело не дошло; sampling/linkage ещё не квалифицированы. |
| C06 | ОТКЛОНЕНИЕ | Пinned image построен, shared-DB read responses получены; build artifact 10045092166, image ID в build-manifest. | Нужен полный 192-attempt fault-control/native gate на исправленном описании; образ повторно не собирать. |
| C07 | НЕ ПРОВЕРЕНО | Контроллер faults ещё не запускался, контрольные 192 попытки отсутствуют. | Проверить оба пути, all-down и live-process communication failure, затем logical domains в stochastic package. |
| C08 | ПРОВЕРЕНО | Старые 12 bounded semantic scenarios проходили локально; добавлены v2 wrong date/type/partial/duplicate/timeout проверки. | CI выявил отсутствие pytest: тесты переведены на принятый unittest; модельные correctness controls M9S/U/X сохранены. |
| C09 | ПРОВЕРЕНО | [003 independent PMX historical comparison](003-pmx-context-comparison.md) сохраняет действие. | Petclinic native PMX ещё не квалифицирован. |
| C10 | ОТКЛОНЕНИЕ | Публичный DTO содержит меньше полей, чем Customers entity; неверный oracle обнаружен до main series. | Поля сверены с исходником, v1 outcomes сохранены; на future cases используется versioned contract. |
| C11 | НЕ ПРОВЕРЕНО | Подготовительный bootstrap не выдаётся за author 8-condition package или 240-campaign main. | После квалификации выполнить один полный technical package. |
| C12 | Н/П | Здесь нет learner fit/evaluator comparison. | Изоляция будущей серии остаётся обязательной. |
| C13 | НЕ ПРОВЕРЕНО | Main campaigns=0; warmup и failure остаются в подготовительной истории. | 800 новых operation cells ещё не получены. |
| C14 | Н/П | Нет availability estimates или hypothesis tests. | Последние три payload replay проверяют только исправленный deterministic oracle, не accuracy модели. |
| C15 | ПРОВЕРЕНО | Все 243 attempts и исходные false/true verdicts находятся в compact.zip и failure-census. | Ни один отказ не стёрт и не переименован в успешную кампанию. |
| C16 | НЕ ПРОВЕРЕНО | Source-only transfer не запускался; [003](003-pmx-context-comparison.md) без изменений. | Не читать target calibration при последующей проверке. |
| C17 | ПРОВЕРЕНО | Maven wall 23,84 s, Docker build 13,45 s, save 4,48 s; GNU time/RSS и JAR/image bytes в exact build archive/manifest. | Это отдельные build stages; не полные затраты моделей и не monitoring overhead. |
| C18 | ПРОВЕРЕНО | DTO и tracing причины воспроизведены источниками/логами; отдельные v2 modules/config/workflow, тот же image. | Затронуты Petclinic semantic qualification и tracing; все четыре операции/шесть controls повторяются, v1 не заменяется. |
| C19 | ПРОВЕРЕНО | Compact ZIP 182461 B, SHA1750e93e… verified; manifest/source git-blob hashes/actual image ID сохранены. | Полный 456549451 B build ZIP остаётся remote, его actual bytes будут проверены при restore. |
| C20 | ПРОВЕРЕНО | Устранён JDK setup failure и получен работающий source build; live responses дали новые конкретные причины. | Следующий запуск использует тот же build вместо повторной сборки, исправляет только установленные дефекты. |
| C21 | ПРОВЕРЕНО | Warmup mismatch не трактуется как нулевая надёжность приложения; tracing support не объявлен. | Все утверждения ограничены наблюдавшимися build и payload/log evidence. |
| C22 | ПРОВЕРЕНО | Протокол, полный failure census, immutable source/build provenance, причина/исправление и все 22 статуса сохранены. | Petclinic qualification и публикационный пакет ещё не завершены. |

Исторические M7/M9P/PMX comparisons остаются неизменными. Единственное следующее действие: квалифицировать v2 runtime на exact retained image, повторив все затронутые deterministic controls и native census. После этого — восемь stochastic условий из плана, без изменения их числа по наблюдаемому преимуществу метода.
