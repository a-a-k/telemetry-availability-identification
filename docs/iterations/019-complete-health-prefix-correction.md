# Итерация 019 — correction полного historical census и opened PMX comparison завершена

2026-09-08, план [v3](../SIMPAT_CORRECTION_V3.md). Вопрос: как изменились все зависимые исторические метрики после decoder correction, отдельно от stable membership и неидентифицированных optimizer points?

[Run 34220234444](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34220234444), head 38f5e01c7f5003a3cde84afc647fe4d2f3ae1180, success. [Числа/источники/границы](../milestones/HEALTH_PREFIX_COMPLETE_CORRECTION.md). 10080 affected-input slots прошли strict replay;7776 unaffected сохранили exact historical rows. Исходный refit replay failed для30 raw nonidentified points остаётся failed. Tolerance не менялся.

Полный M7 rescore имеет четыре forecast/window сочетания,34560 census slots каждое и576000 неизменных all-sequence attempts. Старые scorefields воспроизведены точно. M9X108 candidates/триviews обновлены по тем же четырём opened кампаниям; PMX24 и endpoint_all12 candidate objects неизменны, новые fit/PMX invocations0. Роли: historical/development; main campaigns = 0. Привилегированная historical correction не выдаётся за ordinary main G*.

| ID | Статус | Доказательство / область | Остаток |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | No-ML control chain и exact I2, регрессия не primary. | Прикладной G-ID/G*. |
| C02 | ЧАСТИЧНО | Реальные G/R/P/Φ и observation law прошли build/replay для create_visit в двух размещениях. | Обоснование adequacy и окончательный основной класс. |
| C03 | ЧАСТИЧНО | 12/12 selected historical source files совпали с published archives. | Runtime/data replication и связь всех результатов/версий. |
| C04 | ЧАСТИЧНО | Ten-contract evidence 011 сохранено; первый native mapping create_visit. | Графовая поддержка всех десяти событий. |
| C05 | ЧАСТИЧНО | Все 160 M7 campaigns, 576000 all-sequence attempts и 34560 census slots/угол сохранены; новые stable windows 435761 attempts. | Полная prospective v3 main матрица. |
| C06 | ЧАСТИЧНО | Petclinic runtime/8 conditions/PMX сохраняются; DB role явно ограничена. | Прикладной G*/transfer/cost. |
| C07 | ЧАСТИЧНО | 168 paired refits используют прежнюю physical interpretation; source prefix defect и unaffected trace_only зависимость установлены. | Новый ordinary G* не должен наследовать privileged truth; causal adequacy отдельно. |
| C08 | ЧАСТИЧНО | Strict historical score reproduction maxerror0; four-corner census прошёл; M9X arithmetic maxerror8.33e-17. | Два остальных applied graph examples и новая independent adequacy. |
| C09 | ЧАСТИЧНО | M9X correction пересчитана: все108 candidates/триviews, 24 PMX objects неизменны, empty OTel conditional common0/6 сохранён. | Независимое main G* comparison; corrected M7 не новый G*. |
| C10 | ЧАСТИЧНО | Реальный physical ordinary role содержит только разрешённые поля; native/declaration/DB-client роли отдельно. | Same-event graph estimator и G0 adaptation. |
| C11 | ЧАСТИЧНО | V3 draft 240/800, шесть contrasts, 99.1666667%. | Frozen executable main protocol, запуск после admission. |
| C12 | ЧАСТИЧНО | 168 per-cell read audits: восемь data files, blocked/evaluator/schedule/target-cal reads 0 во время guarded fit; candidates sealed before parity. | Полная обычная G* main цепочка, за пределами historical correction scope. |
| C13 | ЧАСТИЧНО | Все17856 forecast slots сохранены; full M7 rescore four corners/34560 slots каждый; нет исключения 30 raw-point mismatches из истории. | Main attempted census и все новые absences. |
| C14 | ЧАСТИЧНО | Original sampled_mixed/stable Brier contrast пересчитан: Δ.000212314, CI[-.001702533,.002127161], p.715273, 117 pairs. | Новая six-contrast main uncertainty; historical nonsignificance не equivalence. |
| C15 | ЧАСТИЧНО | Proposed/full current coverage370/480 неизменна; own/common/complete-campaign и empty PMX contrasts явно разделены. | Main own/common support. |
| C16 | ЧАСТИЧНО | Transfer новой empirical-joint версии явно unsupported без дополнительных law assumptions, target inputs не используются. | Обоснованные transfer estimates/bounds и change error. |
| C17 | ЧАСТИЧНО | Audit process159.35s/RSS555888KiB сохранён и отделён от стоимости методов; PMX не запускался. | Comparable end-to-end costs для новых методов. |
| C18 | ЧАСТИЧНО | Correction закрыта для160 M7/8 Petclinic/M9X: affected10080 strict parity,7776 exact historical carry-forward, full rescore; old failures сохранены. | Auxiliary v0 consumers имеют static inventory и требуют reanalysis перед reuse; future corrections. |
| C19 | ЧАСТИЧНО | Два exact aggregate archives rescore и updated M9X tables с источниками/hashes в evidence; raw/native остаются remote. | Final archive/long-term retention. |
| C20 | ПРОВЕРЕНО | По-прежнему три приложения, ≤2 deep mechanisms, main=0; только bounded controls/read-only audit. | Соблюдать лимит в дальнейшем. |
| C21 | ЧАСТИЧНО | Уточнены source semantics, privileged-role limits и population/causal distinction. | Final claim audit. |
| C22 | ЧАСТИЧНО | Все 30 критериев обновлены с областью, linked previous evidence и остатком. | Завершение исследования/пакета. |
| F01 | ЧАСТИЧНО | Parser correction изменила OTel checkout MAE24.46223→24.48635pp; она не объясняет крупное исходное отклонение. | Проверить H-EXEC и альтернативы посредством intervention. |
| F02 | ЧАСТИЧНО | Контроль actual likelihood: одинаковое source r=.8, разные transfer .832/.808; semantic/identification bounds не названы новизной. | Полный основной класс и novelty audit. |
| F03 | ПРОВЕРЕНО | В области Petclinic create_visit technical-v1: native graph→saved model→fresh-job replay; structural/equivalence controls пройдены. | Обобщение на основной G* и другие операции/приложения. |
| F04 | ЧАСТИЧНО | H-EXEC-01 остаётся кандидатом с альтернативами; data-role audit не назван cause. | Prospective intervention budget/seeds/analysis и результаты. |
| F05 | ЧАСТИЧНО | Forecast/window изменения разложены по2×2; исходные outcomecounts не изменены; baseline arithmetic exact. | Business adequacy нового graph method и sampling/identification error отдельно. |
| F06 | НЕ ПРОВЕРЕНО | Нет необоснованного назначения refinement или superiority. | ≤2 подтверждённых механизма, versions/ablations/G*. |
| F07 | ЧАСТИЧНО | Исторические selected source bytes теперь привязаны к published ZIP; MODELS status и metrics различаются. | Точное historical execution/data соответствие. |
| F08 | ЧАСТИЧНО | Прикладной технический кандидат продемонстрирован для 1/3 приложений; окончательный G* ещё не выбран. | Остальные приложения, условия main admission и причины/границы. |

Доказательства011–018 сохраняются с явными version/scope. Новых независимых test outcomes не получено: evaluator открыл уже известные historical M7 исходы после candidate/dependency qualification. Полная текущая correction закрывает160 M7 campaigns,8 Petclinic technical fits и opened M9X comparison. Auxiliary localization/routing/failover/temporal-confirmation остаются decoder-v0; static callsite inventory не доказывает их runtime impact и не допускает silent reuse как исправленных данных.

Подтверждено: исправление small parser defect не устраняет большую OTel error; нет установленного M7 превосходства надB2. Это не доказывает causal H и не устанавливает невозможность graph подхода. Следующее действие: перенести ordinary native→graph/model→isolated replay техническую цепочку на оставшиеся DeathStar и OTel, сохранив full-operation contracts и явные observation/semantic assumptions. Main admission пока не пройден.
