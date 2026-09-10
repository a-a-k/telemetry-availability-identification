# Основная серия v3: проект, main admission не пройден

[Авторская v3](SIMPAT_CORRECTION_V3.md) имеет приоритет. Прежний [проект](MAIN_COMPARISON_PROTOCOL_DRAFT.md) сохранён только как история. Main campaigns = **0**. Этот документ фиксирует требования и открытые решения; исполнимого frozen main config пока нет.

Текущее обновление043: [окончательные методические привязки](V3_FINAL_COMPARISON_BINDINGS_V1.md) и исполнимая prospective цепочка подготовлены. Конкретные versions, ablations, input seals и stable/transfer/cost правила больше не являются открытым выбором. Допуск полной цепочки проверяется на6 development campaigns с полными окнами; main0/240. Таблица после031 ниже сохраняет историческое состояние, а актуальный полный статус — в [043](iterations/043-final-bindings-and-prospective-pipeline.md).

## Варианты и исходы

Основной объект — восстановленный и действительно вычисляемый графовый G*. Сравнительные варианты: G0 (точная историческая версия и явно именованная адаптация её параметризации), G-ID (идентификация в объявленном классе), максимум два обоснованных уточнения, их отдельные ablations, итоговый G*. Если два варианта совпадают, они не дублируются под разными именами. M7 и B2 — дополнительные исторические узкие сравнения.

**B0-v3** — число успешных calibration attempts / число всех calibration attempts, без сглаживания. Это отдельная версия, не переименование сглаженного M7 B0. Исторические результаты не пересчитываются под новым названием.

PMX строится по физически отдельному native-calibration artifact. Primary PMX variant — **conditional_local**, сохранённый выбор до основной серии по семантике propagated/local failures. Inclusive также публикуется. Для unsupported conditional cases остаётся отсутствие, а не подстановка inclusive или нуля. Просмотренные технические результаты не являются main data. Квалификация Petclinic дала 32/32 каждого варианта; старый M9X OTel conditional имеет 0/6 — это разные версии данных/операций и независимые области доказательства.

Все методы предсказывают одно объявленное внешнее событие по одной шкале и одному calibration pool. Для каждого метода перечисляются фактически использованные поля и ручная работа. Статическая graph reachability не объявляется равной полному ответу за 2 s без соответствующей семантики/проверки. Сохраняются десять [контрактов](TEN_EXTERNAL_OPERATION_CONTRACTS.md); прежние ICSE/AINA HTTP критерии отдельно. Наличие честно неподдерживаемых операций допускается, но пустое сравнение по всей основной семье не отвечает вопросу исследования.

## Рабочий объём и независимость

3 приложения × 2 логических размещения × 4 режима N/NC/ND/NCD × 10 repetitions = **240 campaigns**. Три операции DeathStar, три OTel, четыре Petclinic дают **800 campaign×operation cells на каждый current method**. Одна campaign: baseline 60 s, calibration 900 s, test 900 s, 4 operations/s, равномерный фиксированный mix. Всего 7440 attempts/campaign и 1,785,600 attempts; baseline 57,600, calibration/test по 864,000. Номинальное время этих окон — 124 runner-hours без сборок/recovery/fit/solve. Это ресурсный бюджет, не гарантия мощности.

Предложенные новые seeds из прежнего проекта ещё не использовались в main: acquisition 771601, observation preparation 771401, bootstrap 771602. Окончательные namespace/seed derivation фиксируются в machine config перед main. Renewal acquisition law и квалифицированные contracts могут быть переиспользованы с точными hashes; распределение генератора не передаётся estimators как oracle. Матрица N/NC/ND/NCD не является точной репликацией пяти failure fractions AINA.

G/R/P/Φ, observation law/missingness, supported cases, estimator versions, source-only transfer и preprocessing фиксируются до test. Learner, PMX и evaluator роли физически раздельны. Builders не читают test outcomes/health/schedules; read audit охватывает загрузку, подготовку, identification и solve. Все кандидаты и причины absence sealed до загрузки evaluator. Технические/viewed runs имеют только development роль. Замена неудачной попытки не создаёт дополнительного независимого n.

## Шесть первичных сравнений

**G*−G0 и G*−PMX × 3 приложения = 6 primary MAE contrasts.** Отрицательная разность означает меньшую MAE у G*. Family α=.05, на сравнение α/6=.008333333333; центральный интервал **99.1666666667%**, tail quantiles 0.004166666667 и 0.995833333333. Прежняя тройка сравнений и 98.333% заменены.

10000 paired campaign bootstrap resamples внутри application×placement×failure-law strata. Campaign — кластер: методы и операции сохраняются вместе, нельзя независимо ресэмплировать requests/операции/методы. Предварительно фиксируются равные веса операций/условий, алгоритм missingness/common support и правило неоценимости пустой stratum. Каждый контраст приводится на общем покрытии; рядом собственное покрытие каждого метода и полный attempted census. Пустое общее покрытие → not estimable. Эта bootstrap процедура не обещает точное конечновыборочное семейное покрытие.

Primary analysis component v1 и [правила weights/common support](V3_CAMPAIGN_ANALYSIS_COMPONENT_V1.md) теперь реализованы:8 artificial controls, paired whole-campaign resampling, complete common campaign support и явное отсутствие оценок. Partial common cells сохраняются рядом с primary subset; empty conditions меняют явно указанную область, не подставляются нулями. Окончательные method bindings, evaluator seals/loading, stable/transfer/cost analysis и full main protocol остаются незавершёнными. Это ещё не main admission.

Primary view — вся последовательность test attempts, включая переходы/timeout. Stable view дополнительна с retained fraction. Публикуются forecast, observed success, signed error, MAE pp, median/p90 absolute error, Brier, campaigns/attempts/coverage и все причины отсутствия. Ни малая ошибка, ни превосходство над PMX/B0 не являются admission gate.

Transfer: только source calibration + объявленное изменение конфигурации, без target calibration/health. Отдельно target error, ошибка предсказанного изменения и coverage. Известные generating states не заменяют отсутствующие параметры G0. Неподдерживаемый перенос публикуется как отсутствие.

Стоимость: acquisition, extraction, identification, solve, update, RSS/bytes/manual work, cold/reuse, общие расходы один раз. Неизмеренное не равно нулю. Monitoring overhead требует off/on, scalability — размерной кривой; без них claims отсутствуют.

## Условия допуска и ближайшая работа

| Условие | Состояние после итерации 031 |
| --- | --- |
| Конкретный G/R/P/Φ и observation law основной модели | Есть exact demonstrator и applied joint-law candidates create_visit/read_user_timeline/browse_product; окончательный основной класс не выбран. |
| Семантическая и идентификационная линии | S1/I1, I2 transfer ambiguity и I3 joint/masked sharp bounds с controls; соответствие business event и новизна F/I не закрыты. |
| Граф реально влияет на прогноз, replay, A/B и unsupported | 25 исходных controls + пять joint-law/parser controls; applied build/replay и structural/equivalence checks прошли (run 34215477704). |
| Контракты десяти операций / поддержка новым методом | Прикладные contracts технически квалифицированы; поддержка G* отдельно не установлена. |
| Технический пример нового метода для каждого из трёх приложений | Технические graph candidates для3/3 apps прошли isolated build/replay (34215477704,34224526327); source/observation assumptions ограничены. Окончательный G* ещё не выбран. |
| Frozen G0/G-ID/G*, refinements/ablations, H-records, analysis/missingness | H-EXEC final-input replay32/32 qualified, обе primary подтверждены в8 блоках; original31/32 gate сохранён. B0-v3 raw S/N10/10 qualified; primary analysis/missingness component v1 frozen/tested. Final method bindings, refinements и остальные анализы не завершены. |
| Изоляция future evaluator и seals | Квалифицированы ordinary-only graph builder и model-only replay (6/1 actual data reads); полная future candidate→evaluator цепочка остаётся. |

Технические graph chains для каждой app выполнены в явно ограниченной области. H-EXEC study32 завершён: [неизменённый анализ окончательных архивов](milestones/H_EXEC_01_SEALED_STUDY_CONFIRMATION.md) проходит полный допуск. Следующий результат — semantic/identification class и обоснованные versions/ablations с собственным бюджетом; максимум два deep mechanisms сохраняется. Основная матрица запускается только после выполнения всей таблицы, независимо от ожидаемого знака результатов.
