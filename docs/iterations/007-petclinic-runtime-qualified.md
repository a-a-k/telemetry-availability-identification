# Итерация 007: Petclinic runtime прошёл все детерминированные проверки

Вопрос и ожидаемые результаты заранее заданы в [v3 protocol](../PETCLINIC_RUNTIME_V3_PROTOCOL.md): на том же image заменить TCP health на HTTP health и повторить все 192 attempts, дополнительно доказав TCP counterexample. Run [34201555957](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34201555957), head `301756d39fa6aec8b110dd1d89d0228282684e7c`, success. Все восемь summary gates true. Подробные counts, границы и provenance — [milestone](../milestones/PETCLINIC_RUNTIME_QUALIFICATION.md).

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | Model fits=0; [002](002-original-formalism-map.md) сохранена. | Primary без ML. |
| C02 | ПРОВЕРЕНО | Source controllers, shared SQL DB, replica placement закреплены в runtime. | Полный mapping Petclinic в обе candidate models ещё впереди. |
| C03 | ПРОВЕРЕНО | [001](001-m7-complete-census.md) без изменений. | 192 controls не прибавляются к 160 историческим кампаниям. |
| C04 | ПРОВЕРЕНО | 4 операции × 6 controls × 8 attempts, strict payload/deadline/persistence verdicts. | Whole-sequence contracts шести других операций ещё требуют новой версии. |
| C05 | ПРОВЕРЕНО | 192/192 unique attempts имеют Gateway SERVER trace; обе Visits identities; invalid native parse=0. | Coverage большой stochastic серии проверяется отдельно. |
| C06 | ПРОВЕРЕНО | Normal/recovered/one-a/one-b по 32/32, оба Visits читают/пишут одну DB. | Qualification детерминированная; новые stochastic условия ещё впереди. |
| C07 | ПРОВЕРЕНО | All-down/communication ломают только две зависимые операции; running/unpaused+DB/telemetry networks сохранены при communication fault. | Logical domains на одном физическом runner; это не независимые машины. |
| C08 | ПРОВЕРЕНО | Paused TCP connect=true и HTTP health=false воспроизведены для a и b; HTTP backend sets совпадают с controls. | Не доказательство адекватности availability estimator. |
| C09 | ПРОВЕРЕНО | [003](003-pmx-context-comparison.md) независимая PMX qualification без изменений. | Petclinic PMX/model interfaces ещё предстоит квалифицировать. |
| C10 | ПРОВЕРЕНО | Empty-visits fallback не success, delayed write не спасает deadline verdict; owners/vets неизменно проверяются полностью. | Поздний audit доказывает наличие записи, не точный момент commit. |
| C11 | НЕ ПРОВЕРЕНО | Runtime acceptance готова для одного пакета 8 stochastic условий. | Это ещё не 240-campaign main. |
| C12 | Н/П | Ни fit, ни evaluator сравнения в этой итерации. | Новые sealed learner/evaluator jobs обязательны. |
| C13 | НЕ ПРОВЕРЕНО | Main campaigns=0. | 800 operation cells пока отсутствуют. |
| C14 | Н/П | Только deterministic expected outcomes; нет availability scores/CI. | Основной 10000 paired campaign bootstrap впереди. |
| C15 | ПРОВЕРЕНО | Все 192 outcomes, 6 controls, прошлый v2 failure сохранены отдельно. | Состав controls и deadlines не менялся после наблюдений. |
| C16 | НЕ ПРОВЕРЕНО | Transfer не запускался. | Не читать target calibration при source-only прогнозировании. |
| C17 | ПРОВЕРЕНО | Exact image reused; compose up 16.86 s/down 4.00 s и CLI RSS в compact archive. | CLI RSS не является суммарной RAM приложения; model costs ещё не измерялись. |
| C18 | ПРОВЕРЕНО | Все затронутые controls повторены после конкретной HTTP-health correction; оба TCP negative probes сохранены. | Первые v1/v2 failures не заменены новыми числами. |
| C19 | ПРОВЕРЕНО | ZIP 154400 B и SHA f5ad66e7… проверены; pinned source/image/config/head в evidence. | Full native artifact остаётся remote, retained 90 days. |
| C20 | ПРОВЕРЕНО | Новый результат: полный runtime acceptance, доказанный TCP/HTTP механизм. | Далее один предусмотренный technical package, без дополнительных effectiveness серий. |
| C21 | ПРОВЕРЕНО | Qualification означает исполнение contracts/controls, не superiority/accuracy. | Claim ledger расширяется только фактически полученными доказательствами. |
| C22 | ПРОВЕРЕНО | Протокол, exact source evidence, milestone, correction chain и 22 статуса сохранены. | Полная новая comparative серия ещё обязательна. |
