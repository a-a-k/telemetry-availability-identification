# Итерация 000: принятие корректировки, 8 сентября 2026 года

Вопрос: как продолжить работу по новой авторской корректировке, сохранив действительные старые доказательства?

Ожидаемый проверяемый результат: обе авторские версии 1.0 внесены без изменения в рабочую документацию, все 22 критерия имеют исходный статус, следующий анализ определён.

Версия до изменения: `7bd0a1394fd350d0129b3bf244222700364b22e9`. Данные: открытые M7 и завершённые PMX-контроли; это разработка, новых кампаний нет. [План](../SIMPAT_CORRECTION_PLAN.md), [чек-лист](../SIMPAT_ITERATION_CHECKLIST.md).

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | НЕ ПРОВЕРЕНО | [M7 implementation](../../src/telemetry_availability/live_validation_analysis.py), frozen M7 commit b1925736f314da610debd23a586d7b7d00cae7ca; M9P is separate temporal-regression diagnostics. | Проверить весь путь основного прогноза и опубликовать его зависимости. |
| C02 | НЕ ПРОВЕРЕНО | [Methods draft](../ARTICLE_METHODS_DRAFT.md) has restricted static model boundaries. | Полная таблица G/R/P/Φ и всех параметров ещё не составлена. |
| C03 | НЕ ПРОВЕРЕНО | [M8A](../milestones/M8A_M7_EVIDENCE_AND_ARITHMETIC_AUDIT.md): 160 identities, 36,459 scores independently reproduced. Exact original M7 analysis ZIP SHA verified locally 397fdc72d9a41fc30d265726e72690c75e4617949208048d629d19d7ea14b5ad. | Следующая итерация: полный численный census 480 операций, включая отсутствующие прогнозы. |
| C04 | НЕ ПРОВЕРЕНО | [M9T](../milestones/M9T_PMX_REQUEST_CORRESPONDENCE.md) describes six existing operations and compound roots. | Требуются десять полных контрактов с численными deadlines; Petclinic ещё не реализован. |
| C05 | НЕ ПРОВЕРЕНО | [M9U](../milestones/M9U_PMX_REQUEST_CONFORMANCE.md): 12 exact controlled request inventories; retained audit run 34192089947: all 12 historical operation inventories match. | Доказательство относится к контролям и четырём сохранённым кампаниям; новых 240 кампаний нет. |
| C06 | НЕ ПРОВЕРЕНО | Petclinic prescribed in accepted plan §4; application has not been deployed by this continuation. | Зафиксировать источник, образы, общую БД и четыре семантических оракула. |
| C07 | НЕ ПРОВЕРЕНО | [M9U controls](../M9U_PMX_REQUEST_CONFORMANCE_PROTOCOL.md) cover repeated calls, compound roots, missing traces and swallowed/propagated errors. | Общий домен, живая коммуникационная ошибка и прикладная деградация ещё не образуют полный набор десяти контрактов. |
| C08 | ПРОВЕРЕНО | [M9S](../milestones/M9S_PMX_PMF_BRIDGE.md), run 34187887857, commit fcafcd9375966817a675c76cec2e5b7c97c7d781: 16 positive oracle passes at 1e-12; [M9U](../milestones/M9U_PMX_REQUEST_CONFORMANCE.md): 44 additional passes. | Это проверка ограниченных конструкций; новые рекурсивные контексты ещё не квалифицированы. Повтор старых контролей не нужен. |
| C09 | НЕ ПРОВЕРЕНО | [M9V protocol](../M9V_PMX_APPLICATION_COMPARISON_PROTOCOL.md): independent native source, preserved source hashes, endpoint-assisted external wrapper explicitly charged. | Прикладная цепочка не завершена; выбрать и зафиксировать новый основной PMX-вариант до новой проверки. |
| C10 | НЕ ПРОВЕРЕНО | [M9T](../milestones/M9T_PMX_REQUEST_CORRESPONDENCE.md), [M9U](../milestones/M9U_PMX_REQUEST_CONFORMANCE.md) separate semantic truth and native error flags. | Проверить равенство событий и допустимых данных всех методов на всех десяти операциях. |
| C11 | НЕ ПРОВЕРЕНО | Accepted correction plan §7: 240 campaigns, 800 campaign-operation cells per method. | Исполнимый новый манифест ещё не зафиксирован; прежний черновик 128 кампаний отменён. |
| C12 | НЕ ПРОВЕРЕНО | [M9V protocol](../M9V_PMX_APPLICATION_COMPARISON_PROTOCOL.md) seals before evaluation; historical outcomes already opened. | Все исправления на M7 являются разработкой. Новая трёхприложенная граница доступа ещё не проверена. |
| C13 | НЕ ПРОВЕРЕНО | No new 240-campaign comparative series launched. | После технического пакета зафиксировать и исполнить всю матрицу, сохраняя незавершённые случаи. |
| C14 | НЕ ПРОВЕРЕНО | [M8A](../milestones/M8A_M7_EVIDENCE_AND_ARITHMETIC_AUDIT.md) proves historical score arithmetic. | Новая сводка: pp, MAE, quantiles, campaign bootstrap, парность и общая область. |
| C15 | НЕ ПРОВЕРЕНО | [M7](../milestones/M7_FROZEN_LIVE_VALIDATION.md): primary topology abstentions retained. | Требуется полный census старых шести операций, затем всех десяти новых. |
| C16 | НЕ ПРОВЕРЕНО | [M7 transfer protocol](../M7_LIVE_VALIDATION_PROTOCOL.md) and frozen transfer predictions exist. | Сводка переноса и аудит нулевого доступа новой цепочки к целевой калибровке впереди. |
| C17 | НЕ ПРОВЕРЕНО | [M9U manual actions](../M9U_MANUAL_ACTIONS.csv), PMX/solver resource logs retained; [M7](../milestones/M7_FROZEN_LIVE_VALIDATION.md) reports campaign costs. | Полных сопоставимых build/solve/update costs нет; неизвестное время не равно нулю; monitoring overhead не заявляется. |
| C18 | ОТКЛОНЕНИЕ | Recovery run 34192728551: uncaught StackOverflowError interrupts first OTel case and second passes. Audit 34193396638 confirms cycles in six OTel operation graphs. | Сохранить все 14 завершённых записей; исправить учёт исключений и отдельно проверить контекстную идентичность. Исходные M7/M9S/M9U не затронуты. |
| C19 | ПРОВЕРЕНО | This iteration copies both user documents byte-for-byte; source SHA-256 in plan-adoption.json. Existing M7 archive digest verified. PMX audit head 7bd0a1394fd350d0129b3bf244222700364b22e9, run 34193396638, CI 34193396783 succeeded. | Проверено происхождение текущей документационной итерации; это не завершение воспроизводимости будущей серии. |
| C20 | ПРОВЕРЕНО | The adopted plan bounds one 240-campaign series and prioritizes old-data census. Current PMX audit yielded measured cycle/context counts. | Новый проект не добавлен; перейти к сводке без повторного сбора M7. |
| C21 | НЕ ПРОВЕРЕНО | [Claim ledger](../ARTICLE_CLAIM_LEDGER.md) distinguishes restricted proof, solver correctness and temporal diagnostics. | Пересобрать утверждения основного метода без ML по итоговым таблицам; не объявлять успех/провал статьи. |
| C22 | ПРОВЕРЕНО | This record assigns every C01-C22 a status, evidence boundary and next action. | Закрыта только регистрация плана; весь доказательный пакет ещё не готов. |

Предыдущие доказательства: неизменные M7, M8A, M9S, M9T и M9U сохраняют свою заявленную область. M9N–M9P — отдельная временная регрессионная диагностика, не основной метод. Повтор checkout не увеличивает число независимых M7-кампаний.

Требует пересчёта: завершение квалификации прикладных PMX-прогнозов после исправления технической цепочки. Один первый проход DeathStar из аварийного запуска не удовлетворяет правилу двух проходов. Исторические исходы открыты; исправленный анализ M7 остаётся разработкой.

Новый проверенный факт: аудит 34193396638 обнаружил циклы во всех шести OTel-моделях (1/2/3 по операции на размещение) и ни одного в шести DeathStar-моделях. Наблюдаемых полных контекстов вызова OTel — 8/13/48 против 5/9/22 исходных операций. Это локализует гипотезу переполнения стека; исправление пока не проверено.

Следующее действие: воспроизводимая полная сводка из сохранённых M7 predictions/scores, со всеми 160 идентификаторами, 480 комбинациями, причинами отсутствия, разрезами full/stable и воспроизведением исторических итогов. Новые сборы для этой сводки не нужны.
