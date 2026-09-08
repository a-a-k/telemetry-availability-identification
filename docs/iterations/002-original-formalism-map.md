# Итерация 002: исходный формализм и путь без ML, 8 сентября 2026

Вопрос: что именно из исходных G/R/P/Φ реализует живой M7-код, откуда взято каждое число и где проходят границы класса? Ожидаемый результат — таблица соответствия, исчерпывающие источники параметров и известные контрольные примеры. Данные: исходная авторская статья/код и искусственные параметры; native/live-файлы не читались. Базовая версия `4c79844`.

Результат: [спецификация](../ORIGINAL_MODEL_NO_ML_SPECIFICATION.md), неизменная копия двух исходных графовых модулей с MIT-лицензией, воспроизводимые 15 проверок, исходные хеши. Замороженный M7 не изменён.

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | [No-ML specification](../ORIGINAL_MODEL_NO_ML_SPECIFICATION.md), prepare_mode → fit_exact_model → predict_cell. | Оцениваются вероятности объявленной модели; M9N–M9P исключены из основного метода. |
| C02 | ПРОВЕРЕНО | [Complete G/R/P/Φ and parameter tables](../ORIGINAL_MODEL_NO_ML_SPECIFICATION.md); original paper and code hashes; preserved original graph API. | Сопоставление выполнено. M7 не использует полный typed graph: ограничение явно раскрыто, эквивалентность всему формализму не заявляется. |
| C03 | ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C03](001-m7-complete-census.md). | Учтены все режимы/методы и пропуски; checkout/M9P не прибавлены к n. Исторические 117 итогов и основной контраст воспроизведены. |
| C04 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C04](001-m7-complete-census.md). | Требуются десять полных контрактов с численными deadlines; Petclinic ещё не реализован. |
| C05 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C05](001-m7-complete-census.md). | Доказательство относится к контролям и четырём сохранённым кампаниям; новых 240 кампаний нет. |
| C06 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C06](001-m7-complete-census.md). | Зафиксировать источник, образы, общую БД и четыре семантических оракула. |
| C07 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C07](001-m7-complete-census.md). | Общий домен, живая коммуникационная ошибка и прикладная деградация ещё не образуют полный набор десяти контрактов. |
| C08 | ПРОВЕРЕНО | [15 bounded known-parameter checks](../evidence/original-formalism-map-2026-09-08/controls-and-source-hashes.json), max error 1.11e−16; [reproduction script](../../scripts/check_original_formalism_map.py). | Это расчёт ограниченных графов/состояний, не live adequacy. M9S/M9U доказательства переиспользованы без повторения. |
| C09 | Н/П | Доказательства без изменений: [итерация 001, C09](001-m7-complete-census.md). | Прикладное сравнение не объявлено завершённым; его следующий ремонт остаётся отдельной задачей. |
| C10 | ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C10](001-m7-complete-census.md). | Проверено для исторического события M7. Десять уточнённых контрактов нового плана ещё не закрыты. |
| C11 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C11](001-m7-complete-census.md). | Исполнимый новый манифест ещё не зафиксирован; прежний черновик 128 кампаний отменён. |
| C12 | НЕ ПРОВЕРЕНО | Source audit: old load_qualified_cell reads evaluator before fitting in the combined M7 process; fit/predict use learner fields. Existing _load_learner_cell leaves test fields empty. | Не заявлять ноль чтений для исторического combined loader. Новая series обязана физически отделить evaluator artifacts и проверить доступ. |
| C13 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C13](001-m7-complete-census.md). | После технического пакета зафиксировать и исполнить всю матрицу, сохраняя незавершённые случаи. |
| C14 | ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C14](001-m7-complete-census.md). | 95% интервалы описательные для M7; будущие три основных 98,333% контраста ещё не исполнялись. |
| C15 | ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C15](001-m7-complete-census.md). | Закрыта полнота старого M7. Полнота десяти новых операций остаётся будущим обязательством. |
| C16 | НЕ ПРОВЕРЕНО | Specification declares split iid new-domain assumption and source-only parameter reuse, with .8→.96 known-parameter oracle. | Новый PMX-transfer и ошибка изменения live availability ещё не опубликованы. |
| C17 | НЕ ПРОВЕРЕНО | Доказательства без изменений: [итерация 001, C17](001-m7-complete-census.md). | Это стоимость сводки. Полные сопоставимые затраты методов и monitoring overhead не измерены. |
| C18 | ПРОВЕРЕНО | No frozen estimator, prediction or historical result changed; original reference files copied without modification and with license. | Выявлены границы fixed two-path, missing τ, replica-path versus logical-edge communication, and preload boundary. Они документированы; прошлые числа не требуют пересчёта. |
| C19 | ПРОВЕРЕНО | [Paper provenance](../evidence/original-formalism-map-2026-09-08/paper-provenance.json), exact source hashes and reproducible script; base head 4c79844. | Original artifact git commit unknown and explicitly marked; exact copied source bytes and MIT license retained. |
| C20 | ПРОВЕРЕНО | Concrete formalism/code distinction and all probability sources documented; 15 small controls passed, no native parsing/fitting/new application series. | Новый класс метода не добавлен; далее исправление PMX по установленной причине. |
| C21 | ПРОВЕРЕНО | Specification separates unrestricted formalism, original product graph API, M7 limited live implementation and temporal regression diagnostics. | Не обещает, что existing M7 predicates model retries/deadline/fallback; new primary variant still needs freeze. |
| C22 | ПРОВЕРЕНО | All 22 statuses recorded here, complete specification and controls linked. | Закрыто сопоставление формализму; основной прикладной pipeline и новая серия ещё не завершены. |

Сохраняют действительность: исходная статья и её ограниченные API, исторические M7/census, M9S/M9T/M9U. Новых прогнозов на открытых тестах нет; никакая повторная диагностика не считается независимым подтверждением. Все известные параметры оракулов заданы до вызова вычислителей; max error 1.11e−16.

Требующих пересчёта исторических таблиц нет. Уточнены утверждения: M7 не восстанавливает весь G/τ/Φ; его численный identification guard не равен глобальной теореме; combined historical loader не удовлетворяет буквальному новому условию нулевых чтений evaluator. Для новой series используется изолированный learner-only путь.

Одно следующее действие: квалифицировать PMX-идентичности по полному наблюдаемому контексту вызова на конечных рекурсивных/переставленных искусственных трассах и затем на тех же четырёх сохранённых кампаниях. Ожидается конечная модель без ложной рекурсии и полный census вероятностей либо точных причин неподдерживаемости.
