# Итерация 011: переход к v3, графовая цепочка и перенос доказательств

**Вопрос до изменения:** что именно вычисляли предшественники/M7, и существует ли воспроизводимая новая цепочка, в которой извлечённая структура действительно определяет прогноз? Ожидаемый результат по разделу 12 v3: correspondence table, known-answer example, все C01–C22/F01–F08 с ограничениями.

Авторский файл [SIMPAT_CORRECTION_V3.md](../SIMPAT_CORRECTION_V3.md) перенесён без изменения bytes из `../SIMPAT_CORRECTION_V3.md`. SHA-256 `c1093c520f9aa928d06dcd9eff1d6de217f31623e303e9b035dcbd09e1599aa1`. Он заменяет конфликтующие пункты прежнего плана; старые авторские версии и отчёты не переписаны. [Прежний main draft](../MAIN_COMPARISON_PROTOCOL_DRAFT.md) помечен историческим; [новый проект](../MAIN_COMPARISON_PROTOCOL_V3_DRAFT.md) использует G*/G0/PMX и шесть primary contrasts.

**Результат ближайшего шага:** [карта с формальным классом, доказательствами и кодом](../GRAPH_CHAIN_V3.md); [сохранённая модель](../evidence/graph-chain-v3/model.json); [25 контролей](../evidence/graph-chain-v3/checks.json). Изменение реальной ветви графа меняет .9 на .5; эквивалентное представление сохраняет .9; отдельный process воспроизводит прогноз по model.json. Примитивы с одинаковым observation law могут давать .85/.95 — такой случай возвращает отсутствие прогноза. Неподдерживаемые semantics/masks явно отклоняются.

Параллельно закончилась ранее запущенная PMX qualification. [Petclinic preparation](../milestones/PETCLINIC_V3_PREPARATION.md) переносит точные 8 acquisition/8 isolated M7 fits/64 PMX forecasts и прежний startup failure. Новых main campaigns, fits на локальных application data и новых причинных экспериментов в этой итерации нет. Исторические source files читаются по закреплённым commit, архивная сверка вынесена в отдельный read-only GHA job.

| ID | Статус | Доказательство и точная область | Что остаётся |
| --- | --- | --- | --- |
| C01 | ЧАСТИЧНО | Новый демонстратор — прямые частоты и exact graph enumeration без ML; M7 no-ML specification сохранена. | G-ID/G* на native compound observations ещё не готовы. |
| C02 | ЧАСТИЧНО | [GRAPH_CHAIN_V3](../GRAPH_CHAIN_V3.md): явные G/R/P/Φ, masks, routing, repeats, источник каждого поля. | Прикладной supported class/observation law и вклад относительно литературы. |
| C03 | ЧАСТИЧНО | [M7 complete census](../milestones/M7_COMPLETE_OPERATION_CENSUS.md) 160/480; отдельные ICSE/AINA source versions. | Полная историческая source/archive/runtime mapping; не называть современные runs репликацией. |
| C04 | ЧАСТИЧНО | [10 contracts](../TEN_EXTERNAL_OPERATION_CONTRACTS.md), [six-operation live qualification](../milestones/TEN_OPERATION_CONTRACT_QUALIFICATION.md), [Petclinic runtime](../milestones/PETCLINIC_RUNTIME_QUALIFICATION.md). | Поддержка каждого события новым графовым методом и сохранение historical success отдельно. |
| C05 | ЧАСТИЧНО | Полный M7 census; Petclinic 59,520 attempts/8 пригодных, 1 startup failure отдельно; compact integrity. | Полный attempted census новой основной серии. |
| C06 | ЧАСТИЧНО | Petclinic 4 contracts, two Visits, shared DB, logical domains, pinned source/image, 8 conditions пригодны. | Прикладной G*/transfer, финальная статистика и стоимость. |
| C07 | ЧАСТИЧНО | Petclinic runtime/fault gates; A-контроли общих причин и связи при живых процессах. | Сопоставить фактический observation law основной модели с faults; причинные H-tests. |
| C08 | ЧАСТИЧНО | 12 exact A controls ≤1e−12, 7 B, 5 expected unsupported и replay; PMX 8 новых oracle passes. MC solver здесь не используется. | Применимые A/B для окончательного G*, его refinements и transfer. |
| C09 | ЧАСТИЧНО | [M9X independent comparison](../milestones/M9X_INDEPENDENT_PMX_DEVELOPMENT_COMPARISON.md) закрыто в development scope; Petclinic 64/64 независимых technical forecasts, 136 solver passes. | Независимые PMX candidates и сравнение со frozen G* на новых main данных. |
| C10 | ЧАСТИЧНО | Новые contracts отделены от старых; PMX source roles проверены; различия ICSE/AINA/M7 и raw B0 явно указаны. | Окончательная G0 adaptation/parameter source map и same-event projection всех методов. |
| C11 | ЧАСТИЧНО | [V3 main draft](../MAIN_COMPARISON_PROTOCOL_V3_DRAFT.md): 240/800, шесть contrasts, 10000 cluster bootstrap, 99.1666667%. | Frozen executable config/analysis, admission и выполнение; бюджет не power guarantee. |
| C12 | ЧАСТИЧНО | Isolated M7: 8 actual read audits, zero test/schedule/target reads; PMX separate role + seal before evaluator. | Аналогичная принудительная граница нового graph builder и будущих main candidates. |
| C13 | ЧАСТИЧНО | Historical 480 current cells и все технические slots; 16 отсутствий B4 transfer сохранены; нет фильтрации удачных случаев. | 800 main cells/method плюс все попытки и причины отсутствия. |
| C14 | ЧАСТИЧНО | Historical complete metrics; B-контроли публикуют parameter/target errors раздельно, missing-parameter range не назван CI. | Полный main metrics/uncertainty analysis и его meaningful artificial controls. |
| C15 | ЧАСТИЧНО | 560/576 M7 technical finite, 16 absence; PMX 64/64; M9X own/common coverage и empty intersection сохранены. | Own/common coverage каждого main contrast, отсутствия по всем strata. |
| C16 | ЧАСТИЧНО | Isolated M7 source-only reads, graph placement control .63→.714; принцип no-target-calibration внесён в v3. | Source-only graph transfer, target error и change error; G0 unsupported без oracle. |
| C17 | ЧАСТИЧНО | M9X costs и Petclinic source/native/fit resource files сохранены; shared/cold/RSS limits указаны. | Автоматический сопоставимый полный cost ledger main; off/on и size curves либо отсутствие соответствующих claims. |
| C18 | ЧАСТИЧНО | История исправлений 001–010 сохранена; v3 меняет роль M7 и admission, original bytes не переписаны. | Коррекции будущих новых методов с пересчётом всех затронутых данных. |
| C19 | ЧАСТИЧНО | 19 compact archives перепроверены size/SHA/CRC/all members; source manifests, pinned refs, replay и commands сохранены. | Полный reproducible paper package, historical archive comparison и долговременный final archive. |
| C20 | ПРОВЕРЕНО | Объём v3 принят: 3 приложения, ≤2 углублённых механизма, одна основная матрица; больших новых запусков нет. | Соблюдать границу в последующих итерациях. |
| C21 | ЧАСТИЧНО | Claim ledger исправлен: M7 не primary graph, PMX development не main, F/I новизна не объявлена выполненной. | Аудит всех утверждений финальной статьи после результатов. |
| C22 | ЧАСТИЧНО | Все 30 критериев заполнены с evidence/scope/remaining; ближайший результат раздела 12 реализован. | Итоговый пакет и достижение остальных условий; этот checklist не закрывает исследование. |
| F01 | ЧАСТИЧНО | V3 мотивация + точное соответствие ICSE/AINA/MODELS/M7/нового кода; M7 checkout discrepancy как development motivation. | Воспроизводимое объяснение опубликованных ICSE/AINA deviations, а не перенос M7 cause. |
| F02 | ЧАСТИЧНО | Полные S1 и I1: условия, утверждения, доказательства, контрпримеры, вычислительные следствия для bounded class. Стандартные свойства атрибутированы. | Доказательства для реальных наблюдений, formal novelty/nearest-literature audit; не считать tuple новым вкладом. |
| F03 | ЧАСТИЧНО | Графовая структура реально вычисляется, отдельный replay, structural/equivalence controls; источники параметров явны. | Native extraction и applied chain на каждом приложении. |
| F04 | ЧАСТИЧНО | H-EXEC-01 имеет мотивирующее отклонение, кандидат механизма, distinguishing signal, уровни/negative controls и альтернативы; статус insufficient. | Полный prospective N/seeds/aggregation/uncertainty/budget record перед H-пакетом и воспроизводимый итог. |
| F05 | ЧАСТИЧНО | A/B/C разделены: A/B только artificial, application C=0 для нового метода; privileged truth не входит в estimator. | Controlled compound observations B и closed-test C нового метода. |
| F06 | НЕ ПРОВЕРЕНО | Уточнение G* по неподтверждённой причине не назначено. | ≤2 mechanism-supported versions, индивидуальные ablations и финальный G*. |
| F07 | ЧАСТИЧНО | Предшественники разделены; исходники показывают all-required/fixed-size failure sets и AINA target filtering; MODELS — manuscript/preprint. | Source/archive audit и точная historical data/runtime доступность; разные success metrics не смешивать. |
| F08 | ЧАСТИЧНО | Новая admission table: прикладных G* примеров 0/3, main запрещён до проверки цепочки. Малое MAE не gate. | Выполнение admission, bounded mechanism tests и выводы о причинах/границах в статье. |

**Действительные прежние доказательства:** exact model-map controls, historical census/metrics, PMX M9S/U/X и новое Petclinic PMX, pinned runtime/contracts/fault checks, source/native read boundaries и архивные hashes сохраняют свою прежнюю узкую область. Они не переименовываются в validation G*.

**Что пересчитать:** новые main прогнозы/сравнения должны использовать реально вычисляемый граф, raw-frequency B0-v3 и шесть contrasts. Старый main draft не исполнялся, поэтому его outcomes не существуют. Переписывать исторические M7/PMX данные под новый метод не требуется; они остаются development. Реальные native chain/parameter fits выполняются только удалённо.

**Проверочные исходы:** исторические и Petclinic technical summary outcomes уже открывались, поэтому это development. Новых main outcomes нет. Artificial known answers доступны checker, но не входят в model build/solve data interface.

**Подтверждено / гипотеза:** подтверждены bounded graph replay/A/B и техническое PMX; адекватность нового метода, причины ICSE/AINA/M7 расхождений и superiority не установлены. H-EXEC-01 пока кандидат, не завершённое причинное объяснение.

**Следующее действие:** завершить побайтовую historical source/archive сверку и построить observation/source map одной реальной операции. Проверяемый результат — объяснимое отображение native/health/declared metadata в G/R/observations, с явным отказом там, где primitive-identification demonstrator неприменим. Массовые main runs этим шагом не заменяются.
