# V3: реальные входы и граница идентификации

Область: source inspection на commit `f2615363d6c4dbaf1238b40b7d432f90193c6a74`, агрегированные native construct inventories восьми Petclinic technical campaigns. Полные native данные локально не разбирались, новые fit/кампании не запускались. Первая операция для дальнейшей прикладной цепочки — **Petclinic create_visit**: один внешний запрос, Gateway→Visits→MySQL, две Visits replicas, один shared database, 2 s + полная проверка ответа/записи.

**Вывод:** текущий learner artifact содержит разные информационные роли. Нельзя целиком передать его новому primary estimator только потому, что он называется learner и не содержит test outcomes. Изолированный M7 fit использует и runtime-state inspection; это отдельное ограничение от нулевого чтения test.

## Источник → сведения → разрешённое использование

| Поля / происхождение | Что действительно наблюдается | Роль в v3 |
| --- | --- | --- |
| `learner/requests.csv`: request_id/trace_id/operation/period, внешняя semantic_success, latency | Все baseline/calibration attempts, включая failures и отсутствие trace. В Petclinic create_visit success — своевременный правильный 201 с требуемой сохранённой записью по контракту. | Calibration outcome допустим для B0/оглашённого estimation method. Это наблюдение бизнес-результата, не метка истинного latent cause. Test строки не передавать. |
| `native/calibration-native.json`: native trace/span/parent IDs, kind, time, error/status, service/instance, db/peer attributes | События исполнения выбранных calibration trace IDs. Отсутствие span возможно при failed execution, потере/отсутствии instrumentation или другом control flow. | Вход extraction/observation model. Missing span не равен dead service. SERVER/CLIENT не менять местами; исторические failure/outcome labels не переписывать. |
| `study.replica`, `service.instance.id`, статические deployment mappings | Соответствие observed instance декларации a/b; не состояние отказа. | Явно объявленные R metadata, со source provenance. |
| Native MySQL CLIENT `db.system`, peer host/port/database | Наблюдаемая связь конкретного caller с DB endpoint; shared peer объединяется. | Допустима как **наблюдаемая клиентская связь**. Не создавать якобы наблюдавшийся DB SERVER span и не оценивать независимый DB crash rate из этой записи. |
| `topology-edges.csv`: source/target/supporting_spans/supporting_traces | `_topology_rows` агрегирует parent links; same-service spans и отсутствующие родители пропускаются, тип ребра и call context не сохраняются. | Историческая coarse projection; для v3 extraction недостаточно, когда существенны sync/async, repeats, client DB endpoint или operation context. Нельзя использовать её как ground truth. |
| `replica_*_backend_status`, `replica_*_backend_check_status` из HAProxy stats | Состояние конечного автомата health checker и результат последней проверки, для Petclinic GET /actuator/health. В старых приложениях тип L4. | Кандидат обычной telemetry, с её собственной observation law. Это составная/возможно устаревшая оценка; UP/L7OK не прямое измерение независимого primitive θ. |
| `replica_*_running`, `replica_*_paused`, `replica_*_network_count`, proxy runtime state | `_health_sampler` вызывает `_inspect_containers`: Docker State.Running/Paused и NetworkSettings.Networks. | В новом primary bundle **исключить**. Эти поля раскрывают runtime/injected state; сохранить для privileged diagnostic/auditor. Статические deployment сведения объявляются отдельно. |
| `*_observed`, error, timestamps | Наличие/успех объединённого сбора Docker inspection и HAProxy stats. Общее exception может закрыть всю tick. | Нельзя автоматически объявить MCAR. Для нового ordinary-probe export нужно сохранить исходные ошибки/время HAProxy отдельно от Docker inspector. |
| `deployment.json`: source_declared_dependencies, database_shared, placement, check type | Объявления по source/controllers/SQL schema. Это не trace-derived necessity. | Разрешённые ручные metadata, перечисленные в методе/стоимости. Не подменять ими обнаруженные рёбра незаметно. |
| `audit/boundary.json`: checks, usability и provenance | Техническое качество acquisition, в старой схеме среди checks есть test-health/census. | Не передавать post-test quality поля новому estimator. Data completeness/census проверяется отдельно; решение о наличии кандидата/absence должно иметь заранее заданную причину и полный attempted census. |
| fault schedules, active causes, подтверждения pause/network actions, test health/outcomes | Привилегированная ground truth/проверочные исходы | Только auditor/evaluator после candidate freeze; не primary fit и не source-only transfer. |

Точные функции: [health sampler](../src/telemetry_availability/live_stochastic_pilot.py), [health schema/projection](../src/telemetry_availability/live_evidence.py), [Petclinic acquisition](../src/telemetry_availability/petclinic_stochastic_preflight.py), [isolated M7 decoder](../src/telemetry_availability/isolated_stochastic_fit.py), [native inventory](../scripts/summarize_petclinic_native_constructs.py).

`isolated_stochastic_fit.health_signal` строит H=Running∧¬Paused, P=H∧(network_count>0)∧UP∧accepted_check_type. Это показывает, почему старое доказательство zero-test-read не подтверждает отсутствие privileged cause information. В Petclinic communication fault отключает только application network, а другие сети остаются: общее network_count не является точной меткой этой связи. Внешняя L7 проверка несёт другую информацию и должна оставаться самостоятельным наблюдением.

## Почему демонстратор I1 ещё нельзя применить к этой таблице

[graph-replay-v3-control-1](GRAPH_CHAIN_V3.md) предполагает прямые MCAR наблюдения примитивов. HAProxy даёт составное, зависящее от времени состояние. Native trace выборка зависит от исполнения/ошибок; полная linkage успешных попыток ничего не доказывает о наблюдаемости отказавших путей. Поэтому обычные поля нельзя переименовать в `direct-primitive-mcar-v1`, а Docker inspect нельзя использовать, чтобы искусственно закрыть эту нехватку.

Для прикладного класса нужно либо доказать идентифицируемость **целевого функционала** по составным наблюдениям, либо вернуть ограничение/отсутствие; полное восстановление всех latent θ не обязательно. Наблюдаемый бизнес-success Y нельзя просто встроить как единственную переменную модели и затем назвать raw frequency новым графовым методом: тогда структура снова перестанет определять прогноз.

## I2: контроль направления переноса при составных наблюдениях

Это популяционный анализ одного ограниченного подграфа, не новый primary G* и не причинное доказательство для реального приложения. Пусть A и B — доступные пути к двум репликам. Из обычных probes наблюдается **совместный** закон (A,B), без прямых состояний общих/индивидуальных причин. Остальные части операции по условию детерминированны; Φ=A∨B. Примитивы независимы, параметры строго положительны, изменения конфигурации меняют только объявленное sharing общей причины.

В colocated модели A=G X_a, B=G X_b. Пусть a=P(A), b=P(B), c=P(A B)>0. Тогда a=g x_a, b=g x_b, c=g x_a x_b, откуда g=ab/c, x_a=c/b, x_b=c/a. Разложение X_i на процесс/связь по этим наблюдениям может оставаться неоднозначным, но current target a+b−c определён. Если transfer создаёт независимые G_a/G_b с прежним margin g и сохраняет механизмы X_a/X_b, target split = a+b−ab. Это вывод **при заданном правиле изменения закона**, не доказательство, что реальная миграция сохраняет эти механизмы.

Обратное направление отличается. В split A=G_a X_a, B=G_b X_b, поэтому наблюдаются независимые A/B с margins a,b. Для любого допустимого g≥max(a,b) можно выбрать x_a=a/g,x_b=b/g и получить один и тот же source observation law. В colocated target тогда A_target=a+b−ab/g, что зависит от g. Например, source margins .6/.4 дают current .76 и один и тот же joint law при g=.8 и .9, но target .7 и .7333333333. Без дополнительных сведений unique point transfer не обоснован; inf/sup диапазон [max(a,b),a+b−ab]. При строгих внутренних параметрах концы могут быть только пределами.

Доказательство — непосредственная факторизация вероятностей; [независимое точное перечисление](evidence/graph-chain-v3/compound-transfer-controls.json) проверяет оба witness параметра и совпадение полного source observation law. Это более сильный критерий, чем близость нескольких optimizer starts. Диапазон относится к популяционной неоднозначности, не является CI конечной выборки. Конечновыборочная оценка joint law, masks и latency response ещё требуют отдельного метода.

## Требуемый следующий исполнимый интерфейс

1. Новый remote projector создаёт физически отдельный primary bundle из **calibration-only** исходников: native + внешний attempt census + только ordinary probes + статические декларации. Docker states/schedules/test-dependent audit поля остаются в диагностической роли. Frozen M7 files не меняются.
2. Native→operation graph сохраняет контекст/тип/повторы и происхождение DB client endpoint; required business result берётся из объявленного контракта. Объявленная и извлечённая структура различаются в output.
3. Для каждого используемого probe задан h(state, history, instrumentation); выбран поддерживаемый класс P/Φ. Instantaneous approximation и её граница проверяются отдельно от численной правильности.
4. Извлечённый graph/model replay реально вычисляется. Где обычные наблюдения не различают target, сохраняется ambiguity/absence. Где требуется новое измерение, фиксируются способ получения и его стоимость до подтверждающего пакета.

Пока эти пункты не выполнены, прикладных цепочек G* остаётся **0/3**. Первая H-EXEC-01 остаётся гипотезой о несовпадении статической достижимости и исполнения при переходе; найденные роли полей сами по себе не являются доказательством причины MAE.
