# Первый прикладной graph build/replay v3

[Run 34215477704](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34215477704), head `e257c8e64e6fab7ca57c93ea20599b55e97e2102`, завершился успешно. Исполнен заранее [замороженный протокол](../PETCLINIC_GRAPH_OBSERVATION_TECHNICAL_PROTOCOL.md). Это два retained development примера `create_visit`, NCD, версии `G-OBS-create-visit-technical-v1`. Основной метод G* ещё не выбран; main campaigns = 0.

| Проверка / результат | Colocated | Split |
| --- | --- | --- |
| External calibration attempts / probe ticks | 900 / 901 | 900 / 901 |
| Native spans данной операции | 5759 | 5928 |
| Native graph nodes / edges | 3 / 2 | 3 / 2 |
| Проверенные external boundary roots / неожиданные missing parents | 900 / 0 | 900 / 0 |
| Joint categories `(00,01,10,11)` | `(130,137,143,491)` | `(81,169,188,463)` |
| Вероятность графового события | 771/901 = 0.855715871254162 | 820/901 = 0.9100998890122086 |
| Неизвестные probe verdicts | 0 | 0 |
| Фактически прочитанные data files builder / replay | 6 / 1 | 6 / 1 |
| Внутреннее время build / replay, s | 1.004466011 / 0.001588766 | 0.991196489 / 0.001506742 |
| Процесс wall time build / replay, s | 1.15 / 0.23 | 1.15 / 0.16 |
| Process max RSS build / replay, KiB | 167812 / 36548 | 169312 / 36680 |

Граф `api-gateway → visits-service → observed-db-client-30f7b3f9b2fb3df3` извлечён из native relations и DB CLIENT peer. Две Visits replica instance identities установлены из native resources. Для каждого missing root parent проверено точное соответствие внешнему заголовку `sha256('client:'+request_id)[:16]`; потеря внутренних родителей не принята за внешний root.

Builder имеет физический ordinary role из пяти JSON и seal; Docker/injection/evaluator в нём отсутствуют. Read guard действует до загрузки seal и на протяжении построения. Другой job получает только сохранённую модель: его фактический data read set — один `model.json`. Прогноз, model digest и источник совпали между build/replay. Все blocked-read списки пусты. Модельные SHA256: colocated `aba0fad8cb5cec103fc0ae8ec5b93e40ea6f2b8e88a9ddb0236589aed7ec1d6c`, split `4232d26a907eca41da6d1e4dccdb8d8e15ceaa0d2b57c9bceb34fb7c55c4d1e3`.

В обоих replay удаление входящих рёбер обязательного DB target меняет ответ на **0**, а перестановка рёбер сохраняет весь результат. Таким образом, восстановленная структура действительно передаётся в вычисление. Вероятности не получены подстановкой успешности `create_visit`: calibration business labels не используются для параметров. Joint law сохраняет наблюдаемую зависимость реплик без допущения их независимости.

Это вероятность идеальной статической доступности требуемых узлов при наблюдаемом HAProxy eligibility law. Gateway и DB явно приняты детерминированно доступными; routing идеальный, delay/retry/queue не моделируются, состояние считается постоянным внутри операции. Соответствие этому событию полного ответа 201 за 2 s с persisted row **не установлено**. Физические причины отказов не идентифицированы, future stationarity предполагается, finite-sample uncertainty не оценена. Совпавшие нижняя и верхняя границы здесь относятся к empirical observation law, не являются доверительным интервалом. Transfer unsupported без дополнительного закона изменения совместного распределения.

Расходы выше включают конкретные build/replay процессы; внутреннее время не включает interpreter/import. Acquisition, initial native parsing, ordinary projection, download, installation и ручная работа здесь не измерены заново. Ни полная стоимость метода, ни выигрыш над PMX, ни scalability из этих чисел не следуют.

Сохранены [семь точных компактных ZIP и все их members](../evidence/petclinic-graph-observation-34215477704/verified-archives.json), проверены API size/digest, CRC и байты каждого файла. [Сводный remote report](../evidence/petclinic-graph-observation-34215477704/qualification/files/qualification.json) и [все artifact metadata](../evidence/petclinic-graph-observation-34215477704/all-artifact-metadata.json) привязаны к head/run. Полные модели остаются только в GitHub artifacts `10051577882` и `10051577244`, retention 90 дней. Скрипт `scripts/retain_petclinic_graph_observation.py` скачивает только перечисленные compact roles и проверяет имена members до записи.

Прикладная цепочка продемонстрирована для одного приложения и одной операции в двух размещениях. Допуск основного G* требует ещё его окончательного класса/вариантов, доказательств применимости и примеров для остальных приложений. Независимая PMX qualification остаётся действительной в своей области, но main accuracy comparison ещё не проведено.
