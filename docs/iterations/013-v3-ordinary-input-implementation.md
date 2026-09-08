# Итерация 013: реализован ordinary-calibration export до прикладного estimator

Вопрос и ожидаемый результат зафиксированы в [протоколе](../V3_ORDINARY_INPUT_QUALIFICATION_PROTOCOL.md): физически разделить ordinary calibration inputs и старые privileged поля, проверить downstream чтение и native graph inventory. Реализованы projector, consumer с process read boundary, frozen source config и workflow двух retained Petclinic NCD datasets. Пять искусственных unittest проходят, включая изменение privileged inputs без изменения primary output и реальное отклонение стороннего data read. Прикладной запуск на момент этой записи ещё не выполнялся; main campaigns=0, model fits=0.

Изменяются только новые файлы и роли v3. Frozen M7/PMX sources и результаты не переписаны. Library/version/source hashes фиксируются до remote run. Прежние evidence scopes и незакрытые условия сохраняются из [012](012-v3-source-audit-and-observation-roles.md); таблица ниже не означает выполнение нового G*.

| ID | Статус | Доказательство / область | Остаток |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | No-ML control chain и exact I2, регрессия не primary. | Прикладной G-ID/G*. |
| C02 | ЧАСТИЧНО | G/R/P/Φ map дополнена настоящими observation roles и transfer ambiguity. | Прикладной класс и proof-to-code соответствие. |
| C03 | ЧАСТИЧНО | 12/12 selected historical source files совпали с published archives. | Runtime/data replication и связь всех результатов/версий. |
| C04 | ЧАСТИЧНО | Ten-contract evidence 011 сохранено; первый native mapping create_visit. | Графовая поддержка всех десяти событий. |
| C05 | ЧАСТИЧНО | Historical/technical census не изменён, новых attempts нет. | Основной attempted census. |
| C06 | ЧАСТИЧНО | Petclinic runtime/8 conditions/PMX сохраняются; DB role явно ограничена. | Прикладной G*/transfer/cost. |
| C07 | ЧАСТИЧНО | Новый projector исключает Docker runtime-state поля из ordinary output; маски legacy collector не названы MCAR. | Remote qualification и observation law estimator. |
| C08 | ЧАСТИЧНО | Пять новых bounded tests проверяют noninterference, native fields, closed periods и actual process read boundary; прежние A/B/PMX controls сохранены. | Remote qualification и окончательные graph A/B/C. |
| C09 | ЧАСТИЧНО | M9X development + 64 Petclinic PMX forecasts + remote audit всех 341 contract members. | Независимое main сравнение G*. |
| C10 | ЧАСТИЧНО | Новый ordinary field allowlist и отдельный physical bundle; declared и native graph relations разделены. | Remote field/graph inventory и same-event estimator/G0 adaptation. |
| C11 | ЧАСТИЧНО | V3 draft 240/800, шесть contrasts, 99.1666667%. | Frozen executable main protocol, запуск после admission. |
| C12 | ЧАСТИЧНО | Новый consumer запрещает сторонние data reads/network/subprocess, synthetic closed-file read реально отклонён. | Подтвердить actual reads на retained native data, затем на основном builder. |
| C13 | ЧАСТИЧНО | Все historical/technical cells и absences сохранены. | Все main cells и attempted campaigns. |
| C14 | ЧАСТИЧНО | I2 диапазон не назван CI; local exact rational equality. | Реальная finite-sample uncertainty и main analysis. |
| C15 | ЧАСТИЧНО | 560/576 M7 и 64/64 PMX technical coverage не переопределены. | Main own/common support и not-estimable strata. |
| C16 | ЧАСТИЧНО | I2 доказывает неоднозначность обратного transfer даже при одинаковом полном source observation law. | Прикладной source-only prediction/change error/coverage. |
| C17 | ЧАСТИЧНО | Существующие resource files сохранены, новые source audit расходы не выданы за model cost. | Сопоставимый main cost ledger. |
| C18 | ЧАСТИЧНО | Новое ограничение input roles и дальнейшая correction scope документированы. | Новый projector/поддержанные оценки, пересчёт только затронутых результатов. |
| C19 | ЧАСТИЧНО | Frozen config связывает code/workflow/protocol/dependency hashes; source tags/archive audits 012 сохранены. | Remote artifacts и final reproducible package. |
| C20 | ПРОВЕРЕНО | По-прежнему три приложения, ≤2 deep mechanisms, main=0; только bounded controls/read-only audit. | Соблюдать лимит в дальнейшем. |
| C21 | ЧАСТИЧНО | Уточнены source semantics, privileged-role limits и population/causal distinction. | Final claim audit. |
| C22 | ЧАСТИЧНО | Все 30 критериев обновлены с областью, linked previous evidence и остатком. | Завершение исследования/пакета. |
| F01 | ЧАСТИЧНО | Historical code установлено точнее; отличия описания/реализации не замалчиваются. | Причины опубликованных deviations не назначены без вмешательств. |
| F02 | ЧАСТИЧНО | S1/I1 дополнены I2 composite-observation transfer proof и rational witness. | Формальный вклад для фактических observations и novelty audit. |
| F03 | ЧАСТИЧНО | Native inventory код использует parent IDs и DB peers, целевой predicate не выдумывает; standalone graph replay 011 сохранён. | Прикладная цепочка с реально оценёнными параметрами и Φ. |
| F04 | ЧАСТИЧНО | H-EXEC-01 остаётся кандидатом с альтернативами; data-role audit не назван cause. | Prospective intervention budget/seeds/analysis и результаты. |
| F05 | ЧАСТИЧНО | Preparation и downstream consumer разнесены по jobs/artifacts; privileged inputs не экспортируются; tests проверяют отсутствие влияния их значений. | Remote qualification и estimator для ordinary compound observations. |
| F06 | НЕ ПРОВЕРЕНО | Нет необоснованного назначения refinement или superiority. | ≤2 подтверждённых механизма, versions/ablations/G*. |
| F07 | ЧАСТИЧНО | Исторические selected source bytes теперь привязаны к published ZIP; MODELS status и metrics различаются. | Точное historical execution/data соответствие. |
| F08 | ЧАСТИЧНО | Main admission не снят из-за green CI/source audit; applied graph examples=0/3. | Прикладные цепочки и итог о причинах/границах. |

Прежние доказательства действуют в прежней области. Никакие main/test исходы здесь не открывались; используется только уже открытое development evidence. Пересчёт historical fit не нужен: новый метод будет вычисляться отдельно после определения observation law. Подтверждено только выполнение artificial input-boundary tests; наличие прикладного graph forecast не заявляется.

Следующее действие: запустить зафиксированный remote ordinary-input protocol на двух development datasets; получить exact input seals, четыре operation graph inventories каждого случая и actual six-file read audits. Большая основная серия этим запуском не начинается.
