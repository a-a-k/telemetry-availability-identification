# Итерация 012: точные исторические источники и реальные роли наблюдений

Вопрос: совпадают ли выбранные source tags с опубликованными архивами и какие existing inputs допустимы для v3 primary method? Ожидаемый результат — побайтовый аудит и source/observation map первой операции, без массовых новых запусков.

[V3 commit f261536](https://github.com/a-a-k/telemetry-availability-identification/commit/f2615363d6c4dbaf1238b40b7d432f90193c6a74) опубликован в main. [CI 34210906206](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34210906206) прошёл на Python 3.11/3.13. [Source audit 34210918952](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34210918952) с тем же head success. [Точные результаты](../evidence/v3-source-audit-34210918952/audit.json): 6/6 selected source files ICSE record 18271837 и 6/6 AINA record 17703953 совпали с выбранными tags; размеры/checksums/CRC архивов проверены. [PMX contract audit](../evidence/v3-source-audit-34210918952/pmx-contract-audit.json) отдельно проверил удалённый ZIP и SHA всех 341 members, включая exact metadata equality. Локально получен только compact audit ZIP 14,024 bytes, SHA-256 `eacc5711526689fcb4db5ff61d7c0f966be0ea9e069dbb84cf0c58b445196cc3`.

[Реальная source map](../V3_NATIVE_OBSERVATION_MAP.md) разделяет ordinary HAProxy observations, native events, declared metadata, calibration business outcomes и privileged Docker states. Старый M7 decoder использует Running/Paused/network_count; он сохраняется как historical/diagnostic вариант. Direct-primitive-MCAR theorem I1 нельзя применять к этому bundle без отдельного закона наблюдения. [I2 witness](../evidence/graph-chain-v3/compound-transfer-controls.json) и [воспроизводимый checker](../../scripts/check_v3_compound_transfer.py) показывают одинаковое полное source распределение при разных target predictions: .76 current, .7/.7333333333 после изменения sharing. Это artificial population counterexample, не прикладной причинный результат.

Статусы относятся к исследованию v3, а не только успешному job. Неизменённые ограничения полностью сохраняются из [011](011-v3-graph-chain-and-evidence.md).

| ID | Статус | Доказательство / область | Остаток |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | No-ML control chain и exact I2, регрессия не primary. | Прикладной G-ID/G*. |
| C02 | ЧАСТИЧНО | G/R/P/Φ map дополнена настоящими observation roles и transfer ambiguity. | Прикладной класс и proof-to-code соответствие. |
| C03 | ЧАСТИЧНО | 12/12 selected historical source files совпали с published archives. | Runtime/data replication и связь всех результатов/версий. |
| C04 | ЧАСТИЧНО | Ten-contract evidence 011 сохранено; первый native mapping create_visit. | Графовая поддержка всех десяти событий. |
| C05 | ЧАСТИЧНО | Historical/technical census не изменён, новых attempts нет. | Основной attempted census. |
| C06 | ЧАСТИЧНО | Petclinic runtime/8 conditions/PMX сохраняются; DB role явно ограничена. | Прикладной G*/transfer/cost. |
| C07 | ЧАСТИЧНО | Docker true-state inspection отделён от ordinary L7 telemetry. | Реальный observation law и H-interventions. |
| C08 | ЧАСТИЧНО | CI обеих версий прошёл; 25 graph controls, 8 PMX oracle passes и exact I2 witness. | Окончательные A/B/C нового метода. |
| C09 | ЧАСТИЧНО | M9X development + 64 Petclinic PMX forecasts + remote audit всех 341 contract members. | Независимое main сравнение G*. |
| C10 | ЧАСТИЧНО | Одинаковые pool/outcome требования сохранены; выявлена privileged часть old learner. | Новый physical primary bundle и G0 adaptation. |
| C11 | ЧАСТИЧНО | V3 draft 240/800, шесть contrasts, 99.1666667%. | Frozen executable main protocol, запуск после admission. |
| C12 | ЧАСТИЧНО | Existing zero-test-read evidence сохраняется; test-dependent quality metadata выявлены как отдельная роль. | Новый builder должен получать только pre-test ordinary inputs и статические metadata. |
| C13 | ЧАСТИЧНО | Все historical/technical cells и absences сохранены. | Все main cells и attempted campaigns. |
| C14 | ЧАСТИЧНО | I2 диапазон не назван CI; local exact rational equality. | Реальная finite-sample uncertainty и main analysis. |
| C15 | ЧАСТИЧНО | 560/576 M7 и 64/64 PMX technical coverage не переопределены. | Main own/common support и not-estimable strata. |
| C16 | ЧАСТИЧНО | I2 доказывает неоднозначность обратного transfer даже при одинаковом полном source observation law. | Прикладной source-only prediction/change error/coverage. |
| C17 | ЧАСТИЧНО | Существующие resource files сохранены, новые source audit расходы не выданы за model cost. | Сопоставимый main cost ledger. |
| C18 | ЧАСТИЧНО | Новое ограничение input roles и дальнейшая correction scope документированы. | Новый projector/поддержанные оценки, пересчёт только затронутых результатов. |
| C19 | ЧАСТИЧНО | Compact source audit сохранён побайтово; published source/provenance и exact I2 command доступны. | Final archive; полные historical runtime/data checks. Локальная generated PCM copy остаётся ignored после отклонённой очистки, см. 011 retention record. |
| C20 | ПРОВЕРЕНО | По-прежнему три приложения, ≤2 deep mechanisms, main=0; только bounded controls/read-only audit. | Соблюдать лимит в дальнейшем. |
| C21 | ЧАСТИЧНО | Уточнены source semantics, privileged-role limits и population/causal distinction. | Final claim audit. |
| C22 | ЧАСТИЧНО | Все 30 критериев обновлены с областью, linked previous evidence и остатком. | Завершение исследования/пакета. |
| F01 | ЧАСТИЧНО | Historical code установлено точнее; отличия описания/реализации не замалчиваются. | Причины опубликованных deviations не назначены без вмешательств. |
| F02 | ЧАСТИЧНО | S1/I1 дополнены I2 composite-observation transfer proof и rational witness. | Формальный вклад для фактических observations и novelty audit. |
| F03 | ЧАСТИЧНО | Bounded graph replay работает; native/source mismatch выявлен до main. | Applied graph extraction→identification→Φ на 3 приложениях. |
| F04 | ЧАСТИЧНО | H-EXEC-01 остаётся кандидатом с альтернативами; data-role audit не назван cause. | Prospective intervention budget/seeds/analysis и результаты. |
| F05 | ЧАСТИЧНО | Privileged Docker states отделены от ordinary probes; A/B/C и synthetic truth роли явны. | Исполнимый primary projection и новые A/B/C. |
| F06 | НЕ ПРОВЕРЕНО | Нет необоснованного назначения refinement или superiority. | ≤2 подтверждённых механизма, versions/ablations/G*. |
| F07 | ЧАСТИЧНО | Исторические selected source bytes теперь привязаны к published ZIP; MODELS status и metrics различаются. | Точное historical execution/data соответствие. |
| F08 | ЧАСТИЧНО | Main admission не снят из-за green CI/source audit; applied graph examples=0/3. | Прикладные цепочки и итог о причинах/границах. |

Прежние доказательства действуют в прежней области. Старые M7 fits/данные не менялись; v3 primary не может наследовать их privileged input contract. Пересчёт потребуется у новых методов после определения допустимых inputs, старые данные остаются development. Ни новые test outcomes, ни main исходы не открывались; их не создавали. Открытые technical summaries остаются development.

Следующее действие: реализовать отдельный remote export обычных calibration probes/native/attempt census для create_visit и проверить поддержку целевой функции при таком observation law. Не включать Docker states или target calibration, чтобы искусственно добиться идентификации; невозможный прогноз публикуется как отсутствие/граница.
