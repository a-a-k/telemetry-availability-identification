# Итерация 018 — полный refit и граница воспроизведения неидентифицированных точек

Дата 2026-09-08, план [v3](../SIMPAT_CORRECTION_V3.md). Вопрос: воспроизводятся ли исторические прогнозы перед изолированным исправлением health decoder, и как сохранить область, где исправление не меняет входы?

[Run 34218526868](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34218526868), head e6f2c11afe9d4b51b466b4d2ba9f66573d8fbfe9: подготовка и три builder jobs успешны, 168 случаев и 17856 slots/version sealed. Итоговый strict parity job failed: 30 B3/trace_only/DeathStar transfer вероятностей не воспроизвелись, сохранив статус raw_unidentified_optimizer_point. [Полный результат/числа/evidence](../milestones/HEALTH_PREFIX_REFIT.md). Роль — те же opened historical/development данные, main=0, новых независимых кампаний нет.

Неудачный strict gate сохранён. [Новый dependency/rescore protocol](../HEALTH_PREFIX_DEPENDENCY_AND_RESCORE_PROTOCOL.md) не меняет tolerance: exact historical rows переносятся для всех 7776 unaffected-input slots, 10080 affected slots должны пройти исходный критерий. До любых test outcome reads проверяется этот scope. Bounded actual likelihood equality и same-source/different-transfer control пройдены; window control сохраняет все бизнес-исходы и меняет только stable membership. Main graph-method adequacy не выводится из historical correction.

| ID | Статус | Доказательство / область | Остаток |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | No-ML control chain и exact I2, регрессия не primary. | Прикладной G-ID/G*. |
| C02 | ЧАСТИЧНО | Реальные G/R/P/Φ и observation law прошли build/replay для create_visit в двух размещениях. | Обоснование adequacy и окончательный основной класс. |
| C03 | ЧАСТИЧНО | 12/12 selected historical source files совпали с published archives. | Runtime/data replication и связь всех результатов/версий. |
| C04 | ЧАСТИЧНО | Ten-contract evidence 011 сохранено; первый native mapping create_visit. | Графовая поддержка всех десяти событий. |
| C05 | ЧАСТИЧНО | Historical/technical census не изменён, новых attempts нет. | Основной attempted census. |
| C06 | ЧАСТИЧНО | Petclinic runtime/8 conditions/PMX сохраняются; DB role явно ограничена. | Прикладной G*/transfer/cost. |
| C07 | ЧАСТИЧНО | 168 paired refits используют прежнюю physical interpretation; source prefix defect и unaffected trace_only зависимость установлены. | Новый ordinary G* не должен наследовать privileged truth; causal adequacy отдельно. |
| C08 | ЧАСТИЧНО | 168 builds завершены; loader equivalence, actual likelihood mask invariance и same-source/different-transfer control пройдены. | Dependency qualification и full rescore, остальные applied graph примеры. |
| C09 | ЧАСТИЧНО | M9X development + 64 Petclinic PMX forecasts + remote audit всех 341 contract members. | Независимое main сравнение G*. |
| C10 | ЧАСТИЧНО | Реальный physical ordinary role содержит только разрешённые поля; native/declaration/DB-client роли отдельно. | Same-event graph estimator и G0 adaptation. |
| C11 | ЧАСТИЧНО | V3 draft 240/800, шесть contrasts, 99.1666667%. | Frozen executable main protocol, запуск после admission. |
| C12 | ЧАСТИЧНО | 168 per-cell read audits: восемь data files, blocked/evaluator/schedule/target-cal reads 0 во время guarded fit; candidates sealed before parity. | Полная обычная G* main цепочка, за пределами historical correction scope. |
| C13 | ЧАСТИЧНО | Все historical/technical cells и absences сохранены. | Все main cells и attempted campaigns. |
| C14 | ЧАСТИЧНО | Trace-only B3 nonidentified point mismatch сохранён, tolerance не расширен; corrected full forecasts отличаются отдельно от MAE. | Полный four-corner rescore и prospective main uncertainty. |
| C15 | ЧАСТИЧНО | 560/576 M7 и 64/64 PMX technical coverage не переопределены. | Main own/common support и not-estimable strata. |
| C16 | ЧАСТИЧНО | Transfer новой empirical-joint версии явно unsupported без дополнительных law assumptions, target inputs не используются. | Обоснованные transfer estimates/bounds и change error. |
| C17 | ЧАСТИЧНО | Build 0.991–1.004 s internal, process 1.15 s; replay internal 0.00151–0.00159 s, process 0.16–0.23 s; RSS сохранён. | Полный сопоставимый cost ledger, acquisition/parse/shared/cold costs. |
| C18 | ЧАСТИЧНО | Все 168 legacy/corrected builds выполнены; строгий replay gate отклонён по 30 nonidentified B3 trace_only transfer значениям. | Uniform dependency qualification 7776 unchanged/10080 affected, rescore и M9X-side correction. |
| C19 | ЧАСТИЧНО | Пять exact compact ZIP сохранили все candidate members, seals и 30 mismatches, learner archives remote only. | Scoring archive/final package. |
| C20 | ПРОВЕРЕНО | По-прежнему три приложения, ≤2 deep mechanisms, main=0; только bounded controls/read-only audit. | Соблюдать лимит в дальнейшем. |
| C21 | ЧАСТИЧНО | Уточнены source semantics, privileged-role limits и population/causal distinction. | Final claim audit. |
| C22 | ЧАСТИЧНО | Все 30 критериев обновлены с областью, linked previous evidence и остатком. | Завершение исследования/пакета. |
| F01 | ЧАСТИЧНО | Объём parser defect установлен, он не назначен научной причиной M7/AINA deviations. | Причинный intervention package и объяснение published discrepancies. |
| F02 | ЧАСТИЧНО | Контроль actual likelihood: одинаковое source r=.8, разные transfer .832/.808; semantic/identification bounds не названы новизной. | Полный основной класс и novelty audit. |
| F03 | ПРОВЕРЕНО | В области Petclinic create_visit technical-v1: native graph→saved model→fresh-job replay; structural/equivalence controls пройдены. | Обобщение на основной G* и другие операции/приложения. |
| F04 | ЧАСТИЧНО | H-EXEC-01 остаётся кандидатом с альтернативами; data-role audit не назван cause. | Prospective intervention budget/seeds/analysis и результаты. |
| F05 | ЧАСТИЧНО | 30 optimizer-point mismatches отделены от decoder effect; current full proposed сдвигается ≤.171 pp в OTel, не объясняя крупную старую ошибку. | Scoring membership/forecast separation и независимая adequacy. |
| F06 | НЕ ПРОВЕРЕНО | Нет необоснованного назначения refinement или superiority. | ≤2 подтверждённых механизма, versions/ablations/G*. |
| F07 | ЧАСТИЧНО | Исторические selected source bytes теперь привязаны к published ZIP; MODELS status и metrics различаются. | Точное historical execution/data соответствие. |
| F08 | ЧАСТИЧНО | Прикладной технический кандидат продемонстрирован для 1/3 приложений; окончательный G* ещё не выбран. | Остальные приложения, условия main admission и причины/границы. |

Прежние доказательства 011–017 сохраняются в их области. Refits не являются новыми independent repetitions. В этом refit этапе новых test outcomes не открывали; будущий evaluator читает ранее открытый historical M7 test после candidate/dependency seals. Все 30 несовпадений и исходный failed protocol сохраняются, причина конкретного platform-level выбора на плоской likelihood поверхности не установлена. Подтверждена независимость prediction inputs от prefix в trace_only и изменившаяся область health-aware fits.

Следующее действие: remote dependency qualification и полный four-corner M7 rescore с 34560 operation/view slots в каждом углу, исходными contrasts, own/common coverage и exact historical score reproduction. Затем обновить M7 сторону opened M9X PMX comparison; auxiliary series проверить перед повторным использованием.
