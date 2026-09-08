# Итерация 014: ordinary input квалифицирован, joint observation calculator реализован

Вопрос: проходит ли реальный native input через новую ordinary-only границу и можно ли вычислять графовый функционал без предположения о независимости replica margins? Результат: [run 34212928736](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34212928736), head `b0ddadb83868e4a80b6a4391b9c65e2269012014`, success: два preparation и два consumer jobs. CI 34212906960 прошёл на Python 3.11/3.13.

[Exact compact evidence](../evidence/v3-ordinary-input-34212928736/) включает четыре ZIP с проверенными API size/SHA/CRC/всеми members. Полные ordinary bundles не скачивались локально. По 3600 calibration attempts/901 raw probe ticks в каждом наборе; все четыре операции по 900. Consumer прочитал ровно шесть ordinary files, blocked=[], legacy/evaluator files не получал. Model fits=0, main campaigns=0.

Graph inventory: create_visit — 3 nodes/2 observed edges, owners — 3/2, card — 4/4, vets — 2/1; по 900 missing parents на операцию при нуле missing traces. Эти missing parents требуют проверки внешней client boundary, а не автоматического объявления внутренних span losses. DB nodes помечены observed CLIENT peer, не native SERVER. Vets cached path не содержит DB call; это не означает глобальной независимости Vets от DB.

[Новый вычислитель и I3](../GRAPH_OBSERVATION_LAW_V3.md) используют joint observation law и sharp mask-support bounds. Пять artificial tests проходят: зависимые пути .7 вместо ошибочного independent .91, пропуски/достижимые bounds, target singleton при неизвестном coordinate, structural/equivalence checks, HAProxy in-progress prefix. Прикладной fit ещё не запускался.

Обнаружено exact-string ограничение historical health decoder: UP/`* L7OK` отклоняется. Новый probe parser различает last-result и in-progress flag по официальной документации. Original data/decoder/results не изменены; влияние на historical estimates требует отдельного аудита/пересчёта. Это техническая ошибка reading semantics, не доказанная причина system failures.

| ID | Статус | Доказательство / область | Остаток |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | No-ML control chain и exact I2, регрессия не primary. | Прикладной G-ID/G*. |
| C02 | ЧАСТИЧНО | Добавлен явно сохраняемый joint observation law и mask-support I3; физические причины и effective eligibility не смешаны. | Прикладной supported class/adequacy и novelty audit. |
| C03 | ЧАСТИЧНО | 12/12 selected historical source files совпали с published archives. | Runtime/data replication и связь всех результатов/версий. |
| C04 | ЧАСТИЧНО | Ten-contract evidence 011 сохранено; первый native mapping create_visit. | Графовая поддержка всех десяти событий. |
| C05 | ЧАСТИЧНО | Historical/technical census не изменён, новых attempts нет. | Основной attempted census. |
| C06 | ЧАСТИЧНО | Petclinic runtime/8 conditions/PMX сохраняются; DB role явно ограничена. | Прикладной G*/transfer/cost. |
| C07 | ЧАСТИЧНО | Ordinary vs Docker роли подтверждены remote; HAProxy star-prefix semantics установлена. | Исправленная historical decoding версия/impact и физическая адекватность probe. |
| C08 | ЧАСТИЧНО | Пять projection tests + пять joint-law/parser tests; remote ordinary qualification success, предыдущие A/B/PMX controls сохранены. | Новый applied model/replay и окончательные A/B/C. |
| C09 | ЧАСТИЧНО | M9X development + 64 Petclinic PMX forecasts + remote audit всех 341 contract members. | Независимое main сравнение G*. |
| C10 | ЧАСТИЧНО | Реальный physical ordinary role содержит только разрешённые поля; native/declaration/DB-client роли отдельно. | Same-event graph estimator и G0 adaptation. |
| C11 | ЧАСТИЧНО | V3 draft 240/800, шесть contrasts, 99.1666667%. | Frozen executable main protocol, запуск после admission. |
| C12 | ЧАСТИЧНО | Два consumer process audit: шесть actual ordinary files, zero blocked, legacy/evaluator отсутствуют. | Та же граница у actual estimator/replay/main. |
| C13 | ЧАСТИЧНО | Все historical/technical cells и absences сохранены. | Все main cells и attempted campaigns. |
| C14 | ЧАСТИЧНО | I2 диапазон не назван CI; local exact rational equality. | Реальная finite-sample uncertainty и main analysis. |
| C15 | ЧАСТИЧНО | 560/576 M7 и 64/64 PMX technical coverage не переопределены. | Main own/common support и not-estimable strata. |
| C16 | ЧАСТИЧНО | I2 доказывает неоднозначность обратного transfer даже при одинаковом полном source observation law. | Прикладной source-only prediction/change error/coverage. |
| C17 | ЧАСТИЧНО | Существующие resource files сохранены, новые source audit расходы не выданы за model cost. | Сопоставимый main cost ledger. |
| C18 | ЧАСТИЧНО | Star-prefix decoder defect воспроизведён на raw status census и bounded parser test; старые bytes сохранены. | Определить/пересчитать affected historical fits/metrics отдельной версией. |
| C19 | ЧАСТИЧНО | Frozen head/config, четыре точных compact ZIP, source seals/actual reads доступны; native остается remote. | Final archive и applied model artifacts. |
| C20 | ПРОВЕРЕНО | По-прежнему три приложения, ≤2 deep mechanisms, main=0; только bounded controls/read-only audit. | Соблюдать лимит в дальнейшем. |
| C21 | ЧАСТИЧНО | Уточнены source semantics, privileged-role limits и population/causal distinction. | Final claim audit. |
| C22 | ЧАСТИЧНО | Все 30 критериев обновлены с областью, linked previous evidence и остатком. | Завершение исследования/пакета. |
| F01 | ЧАСТИЧНО | Historical code установлено точнее; отличия описания/реализации не замалчиваются. | Причины опубликованных deviations не назначены без вмешательств. |
| F02 | ЧАСТИЧНО | I3 имеет условия, sharpness proof, вычислительные controls и finite-sample границу. | Новизна/реальная семантическая привязка ко всем приложениям. |
| F03 | ЧАСТИЧНО | Реальные call graphs восстановлены в ordinary-only consumer; generic joint-law solver использует граф. | Соединить обе части actual applied build/replay. |
| F04 | ЧАСТИЧНО | H-EXEC-01 остаётся кандидатом с альтернативами; data-role audit не назван cause. | Prospective intervention budget/seeds/analysis и результаты. |
| F05 | ЧАСТИЧНО | Ordinary physical role и actual read boundaries подтверждены; inference не получает Docker states; неполнота и privileged states не отождествлены. | Applied estimation/adequacy и final method boundaries. |
| F06 | НЕ ПРОВЕРЕНО | Нет необоснованного назначения refinement или superiority. | ≤2 подтверждённых механизма, versions/ablations/G*. |
| F07 | ЧАСТИЧНО | Исторические selected source bytes теперь привязаны к published ZIP; MODELS status и metrics различаются. | Точное historical execution/data соответствие. |
| F08 | ЧАСТИЧНО | Main admission не снят из-за green CI/source audit; applied graph examples=0/3. | Прикладные цепочки и итог о причинах/границах. |

Прежние source/runtime/census/PMX/contract evidence сохраняет прежнюю область. Новые main или test исходы не создавались/не читались, inputs — ранее открытые development acquisitions. Полный graph-model technical fit ещё не выполнен. Historical health-parser correction потребует отдельного versioned reanalysis, не переименования текущих результатов.

Следующее действие: выполнить remote technical create_visit graph identification/replay на ordinary inputs с полным disclosure эффективных состояний/детерминированных предположений и проверкой external trace boundary. Получить численный кандидат либо явную ambiguity; main этим не допускается.
