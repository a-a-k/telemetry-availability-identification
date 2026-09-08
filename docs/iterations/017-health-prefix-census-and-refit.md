# Итерация 017 — полный census ошибки health decoder и заморозка пересчёта

Дата: 2026-09-08. План [v3](../SIMPAT_CORRECTION_V3.md). Вопрос: какие сохранённые observation files затронуты ошибкой literal HAProxy check_status, и можно ли отдельно воспроизвести старую версию перед её исправленным пересчётом?

Версия decoder historical-health-prefix-v1, успешный census adapter v3. [Run 34217614608](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34217614608), head 92f0cdb49ef31c1efe6aebb28b350e100f7e4391, success. [Полный результат](../milestones/HEALTH_PREFIX_CENSUS.md): 168 identities / 328 files; calibration affected 119/160 M7 и 8/8 Petclinic, test-health 117/160 M7. При объединении периодов M7 affected 143/160. Forecast/MAE effect ещё не вычислен.

Роли: открытые historical/development данные, privileged audit. Два неудачных preparation runs сохранены отдельно; после второго добавлен обязательный staged-Git-byte freeze gate. Никакой main campaign не добавлено, бизнес-исходы в census не загружены, старые bytes не изменены. Подготовлен [frozen refit/parity protocol](../HEALTH_PREFIX_REANALYSIS_PROTOCOL.md) на все 17,856 slots/version, со старым likelihood/seed/modes и отдельным physical learner role. Два bounded loader tests прошли; application fits этой correction-версии ещё не запускались при записи.

| ID | Статус | Доказательство / область | Остаток |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | No-ML control chain и exact I2, регрессия не primary. | Прикладной G-ID/G*. |
| C02 | ЧАСТИЧНО | Реальные G/R/P/Φ и observation law прошли build/replay для create_visit в двух размещениях. | Обоснование adequacy и окончательный основной класс. |
| C03 | ЧАСТИЧНО | 12/12 selected historical source files совпали с published archives. | Runtime/data replication и связь всех результатов/версий. |
| C04 | ЧАСТИЧНО | Ten-contract evidence 011 сохранено; первый native mapping create_visit. | Графовая поддержка всех десяти событий. |
| C05 | ЧАСТИЧНО | Historical/technical census не изменён, новых attempts нет. | Основной attempted census. |
| C06 | ЧАСТИЧНО | Petclinic runtime/8 conditions/PMX сохраняются; DB role явно ограничена. | Прикладной G*/transfer/cost. |
| C07 | ЧАСТИЧНО | Полный census: 484 M7 calibration ticks, 537 test-health ticks, 97 Petclinic calibration ticks меняют path bits. | Versioned refit и downstream scoring; adequacy отдельно. |
| C08 | ЧАСТИЧНО | Три decoder controls + два schema/AST + два loader controls; 168 identities/328 files remote census прошёл. | Historical legacy parity, corrected fits/scoring; other-app graph chains. |
| C09 | ЧАСТИЧНО | M9X development + 64 Petclinic PMX forecasts + remote audit всех 341 contract members. | Независимое main сравнение G*. |
| C10 | ЧАСТИЧНО | Реальный physical ordinary role содержит только разрешённые поля; native/declaration/DB-client роли отдельно. | Same-event graph estimator и G0 adaptation. |
| C11 | ЧАСТИЧНО | V3 draft 240/800, шесть contrasts, 99.1666667%. | Frozen executable main protocol, запуск после admission. |
| C12 | ЧАСТИЧНО | В двух builder/replay парах фактические reads только шесть ordinary files / один model.json, forbidden reads 0. | Полная будущая sealed candidate→evaluator цепочка. |
| C13 | ЧАСТИЧНО | Все historical/technical cells и absences сохранены. | Все main cells и attempted campaigns. |
| C14 | ЧАСТИЧНО | I2 диапазон не назван CI; local exact rational equality. | Реальная finite-sample uncertainty и main analysis. |
| C15 | ЧАСТИЧНО | 560/576 M7 и 64/64 PMX technical coverage не переопределены. | Main own/common support и not-estimable strata. |
| C16 | ЧАСТИЧНО | Transfer новой empirical-joint версии явно unsupported без дополнительных law assumptions, target inputs не используются. | Обоснованные transfer estimates/bounds и change error. |
| C17 | ЧАСТИЧНО | Build 0.991–1.004 s internal, process 1.15 s; replay internal 0.00151–0.00159 s, process 0.16–0.23 s; RSS сохранён. | Полный сопоставимый cost ledger, acquisition/parse/shared/cold costs. |
| C18 | ЧАСТИЧНО | Оба preparation failures сохранены; причина schema и Git CRLF установлена; staged-byte freeze gate принят; полный census исправленной версии завершён. | Пересчитать все dependent forecasts и stable/all-sequence metrics; auxiliary-series scope. |
| C19 | ЧАСТИЧНО | Точные compact evidence graph replay и полного census в Git; девять source archives verified remote; хеши до dispatch проверяются по Git index. | Parity/refit archive и final long-term package. |
| C20 | ПРОВЕРЕНО | По-прежнему три приложения, ≤2 deep mechanisms, main=0; только bounded controls/read-only audit. | Соблюдать лимит в дальнейшем. |
| C21 | ЧАСТИЧНО | Уточнены source semantics, privileged-role limits и population/causal distinction. | Final claim audit. |
| C22 | ЧАСТИЧНО | Все 30 критериев обновлены с областью, linked previous evidence и остатком. | Завершение исследования/пакета. |
| F01 | ЧАСТИЧНО | Объём parser defect установлен, он не назначен научной причиной M7/AINA deviations. | Причинный intervention package и объяснение published discrepancies. |
| F02 | ЧАСТИЧНО | I3 имеет условия, sharpness proof, вычислительные controls и finite-sample границу. | Новизна/реальная семантическая привязка ко всем приложениям. |
| F03 | ПРОВЕРЕНО | В области Petclinic create_visit technical-v1: native graph→saved model→fresh-job replay; structural/equivalence controls пройдены. | Обобщение на основной G* и другие операции/приложения. |
| F04 | ЧАСТИЧНО | H-EXEC-01 остаётся кандидатом с альтернативами; data-role audit не назван cause. | Prospective intervention budget/seeds/analysis и результаты. |
| F05 | ЧАСТИЧНО | Decoder correctness, empirical graph probability и physical/business adequacy разделены; census не выдаётся за accuracy. | Полный correction effect и independent adequacy validation. |
| F06 | НЕ ПРОВЕРЕНО | Нет необоснованного назначения refinement или superiority. | ≤2 подтверждённых механизма, versions/ablations/G*. |
| F07 | ЧАСТИЧНО | Исторические selected source bytes теперь привязаны к published ZIP; MODELS status и metrics различаются. | Точное historical execution/data соответствие. |
| F08 | ЧАСТИЧНО | Прикладной технический кандидат продемонстрирован для 1/3 приложений; окончательный G* ещё не выбран. | Остальные приложения, условия main admission и причины/границы. |

Прежние 011–016 evidence сохраняются в своих областях, включая 1/3 applied graph technical examples и независимые PMX forecasts. Старые M7 прогнозы/метрики сохраняются как decoder-v0; corrected claims ожидают refit/parity и полного rescore. PMX decoder не использует, но парное сравнение с M7 может измениться на M7 стороне. Дополнительные исторические серии не включены в этот census и требуют dependency audit при повторном использовании.

Новые проверочные business outcomes не открывались, source data уже development. Подтверждён сам parser defect и полный affected-input census. Его влияние на accuracy и научная причинность не установлены. Одно следующее действие: исполнить frozen isolated refit/parity на всех 168 случаях, сохранив каждое отсутствие и проверив воспроизведение старых вероятностей/статусов перед correction attribution.
