# Petclinic: перенесённое техническое доказательство для v3

Восемь пригодных условий собраны; historical M7 изолированно обработал разрешённые learner inputs; независимый PMX/Palladio выдал 64/64 технических прогнозов. Это подготовка и development, **не проверка прикладного G* и не основная серия**. Все точные компактные ZIP и их члены сохранены; полный native/runtime архив остаётся в GitHub Actions.

| Этап | Run / frozen source | Результат |
| --- | --- | --- |
| Первая восьмиусловная acquisition | [34202539028](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34202539028), `06e83aad5f65f17365c7715ca3b312938b94f1a9` | Семь пригодных; colocated-NCD не прошёл startup, сохранён и не увеличивает scientific n. |
| Исправление только SQL readiness | [34204098497](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34204098497), `68bf0b86acab9072d0d8abfabb7c2d64d4a69546` | Недостающее colocated-NCD пригодно. Изменена только последовательность запуска; образ, сценарий/seed, измерение и contracts сохранены. |
| Isolated historical M7 | [34205318062](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34205318062), `cc9db24ff9012a2a7d93f0e10cef2e90ee603984` | Восемь fits, каждый прочитал ровно девять разрешённых файлов; test/schedule/target-calibration reads = 0. |
| PMX DB CLIENT + shared database | [34206870187](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34206870187), `3a916932bbce78fcb270b5710e90dead8cd00723` | 32 operation cells × 2 PMX variants × 2 solver passes = 128 прикладных проходов; восемь проходов независимых малых оракулов. |

Суммарно **59,520** baseline/calibration/test attempts восьми пригодных campaigns; 32 operation cells, по 7440 attempts/campaign. Во всех восьми baseline success четырёх операций = 1, calibration health 901 ticks, successful calibration native linkage = 1, обе Visits replicas наблюдаются; все fault actions подтверждены и сняты. Все nine acquisition gates true. [Startup audit](PETCLINIC_RUNTIME_QUALIFICATION.md) и отдельная correction history сохраняют прежние неудачи. Реальные fault domains логические, один физический runner; общая MySQL не объявляется независимыми БД.

Historical M7 output: **576 slots** (full/sampled_mixed, current/transfer), из них 560 конечных прогнозов и **16 отсутствий B4 transfer**. Пустая строка в сохранённой старой схеме означает отсутствие; проверка `value is not None` ошибочно дала бы полный coverage. [Новый агрегатный проверяющий скрипт](../../scripts/report_petclinic_v3_preparation.py) проверяет численный тип и конечность, не меняя старых bytes. Current: 64/64 у каждого из шести методов с учётом двух modes. Transfer: 32/32 у пяти, 16/32 у B4. Два modes не удваивают число независимых campaigns. Граф рёбер M7 solver не потребляет.

PMX: inclusive **32/32**, conditional_local **32/32**. Каждый forecast имеет две согласованные конечные оценки, full physical mass=1, success+failure=1, все состояния вычислены. Контроли database_propagated: .576/.8; shared_database_two_callers: .59049/.81, каждый в двух проходах. Это оракулы PCM parameterization, не эмпирическое доказательство независимости DB/call errors. `db.*` и peer-native атрибуты задают один наблюдаемый DB-client endpoint, общий для callers; серверный DB span не выдумывается. Отсутствие SQL span у cached Vets не означает отсутствие зависимости от MySQL.

Физический PMX источник содержит native calibration + внешний calibration request census и provenance; наш graph/health/parameters/predictions туда не входят. Candidate seal сообщает evaluator downloads before freeze=0. Квалификация даёт численную готовность comparator в этих технических случаях; accuracy в этом отчёте не сравнивалась.

[preparation-report.json](../evidence/petclinic-pmx-34206870187/preparation-report.json) воспроизводится командой:

```powershell
.venv/Scripts/python.exe scripts/report_petclinic_v3_preparation.py
```

Он повторно проверяет **19** compact ZIP: 17 acquisition/failed-startup/fit и 2 PMX solver/candidates, API byte sizes/SHA/CRC/каждый распакованный member, 8 fit seals и PMX candidate seal, фактические read audits и все 136 solver pass records. Отчёт не скачивает приложение и не запускает fit.

Время native parsing в восьми acquisitions 2.580953–3.373684 s; точные значения находятся в aggregate JSON (минимум/максимум следует брать из него, не интерпретировать как model solve). Ресурсные файлы acquisition/fit сохранены. Полная стоимость Docker-системы, monitoring off/on и масштабирование здесь не измерены; эти claims остаются открытыми. Main campaigns=0, технических прикладных цепочек **нового графового метода**=0.


Первоначально полученный solver-contract ZIP (441,236 bytes) оказался архивом с полными PCM model files. SHA/CRC/member equality были проверены при получении. Автоматическая проверка отклонила удаление созданной локальной копии (`blocked by policy`); копия остаётся локально ignored и не включена в Git. В Git сохраняются только contract JSON, API и [retention record](../evidence/petclinic-pmx-34206870187/solver-contract/retention.json). Повторный полный аудит этого архива выполняется удалённо, локальный воспроизводимый отчёт проверяет 19 компактных ZIP и hash оставленных contract metadata. Это ограничение сохранено в журнале, а не скрыто как успешно выполненная очистка.
