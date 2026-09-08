# Итерация 004: четыре Petclinic контракта и отказ установки JDK

Вопрос/ожидание до запуска — [bootstrap protocol](../PETCLINIC_BOOTSTRAP_PROTOCOL.md): неизменный Petclinic source, общая БД, четыре полных внешних события и реальные native traces, 192 контрольные попытки. Source-only SQL inspection и 12 маленьких искусственных semantic tests прошли. Run 34198870157 на d548f01153d889f2a36c5d2c3bc32a6b4e9937fa остановился на setup-java: четырёхчастная версия `17.0.20.1+1` отвергнута parser SemVer. Maven, Docker, нагрузка и native parse не выполнялись. [Сохранённый журнал](../evidence/petclinic-bootstrap-34198870157-failed.log).

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | petclinic_contract/bootstrap не содержат fit или ML; [003](003-pmx-context-comparison.md) без изменений. | Модель не менялась. |
| C02 | ПРОВЕРЕНО | [002 specification](../ORIGINAL_MODEL_NO_ML_SPECIFICATION.md) сохранена. | Mapping Petclinic зависимостей в candidate модели ещё не исполнен. |
| C03 | ПРОВЕРЕНО | [001 полный M7 census](001-m7-complete-census.md) без изменений. | Нового n нет. |
| C04 | НЕ ПРОВЕРЕНО | Четыре Petclinic contracts с 2 s deadline; 12 tests проверяют fallback, partial list, timeout, duplicate/lost write и неправильный ack ID. | Искусственные проверки прошли, live execution не начался; общие десять контрактов не закрыты. |
| C05 | НЕ ПРОВЕРЕНО | Проект census задаёт один ID и outcome каждому запросу независимо от trace. | Ни одной live попытки в этом запуске. |
| C06 | ОТКЛОНЕНИЕ | Pinned source/OCI/agent, SQL-derived oracle и общий MySQL заданы; setup-java error до сборки. | Прямая установка того же verified JDK archive в отдельном workflow. |
| C07 | НЕ ПРОВЕРЕНО | В коде изолированная application network, сохранённые DB/telemetry networks; пооперационные breaker instances. | Нужна фактическая проверка Running/Paused/network и правильных независимых исходов. |
| C08 | ПРОВЕРЕНО | 12 bounded semantic tests; M9S/M9U/M9X вычислительные доказательства [003](003-pmx-context-comparison.md) переиспользованы. | Petclinic не запускался в PMX/Palladio. |
| C09 | ПРОВЕРЕНО | Независимое сравнение исторических двух приложений [003](003-pmx-context-comparison.md) без изменений. | Petclinic ещё не включён. |
| C10 | НЕ ПРОВЕРЕНО | Seed-derived complete card и SQL exactly-once oracle заданы независимо от native errors. | Нужны live observations, без приравнивания pending audit к успеху. |
| C11 | НЕ ПРОВЕРЕНО | Author plan 240/800 сохранён; bootstrap явно development_only и main_campaigns=0. | Technical 8-condition package и main matrix ещё не выполнялись. |
| C12 | Н/П | В запуске нет fit/evaluator. | Н/П не закрывает изоляцию будущих learner/evaluator artifacts. |
| C13 | НЕ ПРОВЕРЕНО | Setup failure не посчитан observation или campaign. | Требуются все 800 новых operation cells/причины отсутствия. |
| C14 | Н/П | Новых данных/прогнозов/тестов гипотез нет. | Будущий подтверждающий анализ остаётся по плану. |
| C15 | ПРОВЕРЕНО | Исходный неуспешный workflow и журнал сохранены, отсутствие данных явно обозначено. | Ни один scientific case не отброшен. |
| C16 | НЕ ПРОВЕРЕНО | [002/003](003-pmx-context-comparison.md) без изменений. | Target calibration access должен быть физически исключён в transfer. |
| C17 | НЕ ПРОВЕРЕНО | Нет build/load costs: приложение не стартовало. | Это отсутствие измерения, не нулевая стоимость модели; следующий workflow сохраняет GNU time и размеры. |
| C18 | ПРОВЕРЕНО | Известен точный trigger/parser error; source/application/контракты не затронуты. | Новый workflow исправляет только установку JDK; прошлые числа не требуют пересчёта. |
| C19 | ПРОВЕРЕНО | Frozen head, original workflow, source commit, OCI digests, agent SHA, сохранённый setup log. | Бинарный runtime artifact ещё не создан. |
| C20 | ПРОВЕРЕНО | Source/SQL анализ дал конкретные shared-DB и route-breaker настройки; bounded tests прошли. | После одного setup failure меняется способ установки, а не повторяется тот же action. |
| C21 | ПРОВЕРЕНО | Никакого заявления о live support или успешной main series. | Доказана только корректность искусственных semantic controls и причина setup failure. |
| C22 | ПРОВЕРЕНО | Все статусы, исходный протокол, код, тесты и exact setup failure перечислены. | Runtime qualification не завершена. |

Следующее действие заранее определено в [JDK correction protocol](../PETCLINIC_BOOTSTRAP_JDK_CORRECTION.md): установить тот же официальный архив с фактической проверкой SHA, исполнить неизменный bootstrap и сохранить его полный outcome census. Исходный workflow не изменялся. Отказ не относится к стохастической модели или Petclinic endpoint semantics.
