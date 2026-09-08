# Petclinic: четыре операции и квалифицированный runtime

Run [34201555957](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34201555957) на head `301756d39fa6aec8b110dd1d89d0228282684e7c` прошёл все проверки. Это технические controls до основной comparative series; модельных fits и main campaigns нет. [Полный summary](../evidence/petclinic-v3-34201555957/bootstrap-summary.json), [исходные attempts](../evidence/petclinic-v3-34201555957/requests.json), [controls с доказательствами состояния](../evidence/petclinic-v3-34201555957/controls.json), [trace census](../evidence/petclinic-v3-34201555957/trace-census.json).

Каждая попытка — один HTTP request, один внешний request ID и deadline 2 s. Список владельцев проверяет все 10 владельцев и 13 pets; карточка владельца 6 — обоих pets и все четыре исходных visits. Добавление визита владельцу 1/pet 1 требует своевременного HTTP 201 с правильным payload и ровно одной постоянной записи с уникальным marker и тем же ID. Список vets проверяет всех шестерых и specialties. Записи и неизменяемая read fixture разделены. Нахождение записи после timeout не меняет failure; точный момент commit отдельным поздним SQL audit не измеряется.

| Контроль | Владельцы | Полная карточка | Создать визит | Ветеринары |
| --- | ---: | ---: | ---: | ---: |
| normal | 8/8 | 8/8 | 8/8 | 8/8 |
| only a | 8/8 | 8/8 | 8/8 | 8/8 |
| only b | 8/8 | 8/8 | 8/8 | 8/8 |
| both paused | 8/8 | 0/8 | 0/8 | 8/8 |
| communication failure, processes alive | 8/8 | 0/8 | 0/8 | 8/8 |
| recovered | 8/8 | 8/8 | 8/8 | 8/8 |

Всего 192 unique attempts, каждая имеет native Gateway SERVER span; обе Visits replica identities найдены, parse errors=0. Все ожидаемые outcomes совпадают: 160 success и 32 предусмотренных failures. HTTP-200 карточка с пустыми visits считается деградацией. Tracing не используется как oracle внешнего успеха.

Предыдущий v2 run 34200559774 сохранил два failed single-path controls. TCP health принимал paused process за UP: ядро завершало TCP handshake, приложение не отвечало. V3 сохранил тот же image и contracts, заменил HAProxy check на `GET /actuator/health`, expected 200, interval/timeout 500 ms, rise/fall 1. Отдельные probes для каждой paused replica доказали `tcp_connect=true`, `http_health=false`; backend UP sets во всех шести controls совпали с ожидаемыми. История — [006](../iterations/006-petclinic-tcp-health-counterexample.md), [007](../iterations/007-petclinic-runtime-qualified.md).

Обе Visits replicas используют один MySQL 8.4 InnoDB; Customers и Vets также зависят от него. Database, Customers, Vets и Gateway не являются целями инъекций и должны оставаться явно объявленными зависимостями моделей. Communication fault отключает только application network Visits, сохраняя database/telemetry networks и живые процессы. Domain placement логический на одном runner. Gateway retains исходный retry для POST; по маршрутам заданы отдельные circuit breakers, у карточки сохранён empty-visits fallback. Это явно настроенное deployment, не неизменённый upstream Docker Compose.

Source `spring-petclinic/spring-petclinic-microservices` commit `3858f9c630cf989bb6809a86edf47c2be78dc9f1`; image `sha256:48a71a0f944e3cda4fcf445a66371d0f76240a6b2603fc2d1c7395779cb71a0d`. Build artifact 10045092166 проверен при restore по actual ZIP SHA/size, всем 16 manifest files и загруженному Docker image ID. Qualified compact artifact 10046147410: 154400 B, SHA256 `f5ad66e772342a6e9c2e2866c9be2129d4fc5b9b8d001cddd5eb67e63e89d882`; [exact ZIP](../evidence/petclinic-v3-34201555957/compact.zip) проверен и сохранён в Git. Summary SHA256 `7f470ff086dd119f3ecfd876430ea954aee6ae993648dd83a0773fa38c644d98`.

Compose up/down занимали 16.86/4.00 s, их CLI max RSS 49620/48572 KiB. Это отдельные setup costs, не полная стоимость контейнеров или модели. Следующий предусмотренный этап — восемь stochastic условий с раздельными learner/evaluator artifacts и квалификацией model interfaces; технические данные исключены из будущих 240 main campaigns.
