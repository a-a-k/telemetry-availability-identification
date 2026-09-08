# Итерация 008: причина отсутствующей technical acquisition установлена

Вопрос перед read-only audit: почему colocated/NCD job 101984436169 завершился до окончания warmup, тогда как семь остальных условий run 34202539028 продолжали работу? Audit run [34203827517](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34203827517), head a5116086e9bd3da76c80d4a0be42151bc094dc18 проверил исходный archive и извлёк ограниченный диагностический отчёт. Установлен startup race: Java JPA metadata initialization до SQL readiness. Полный результат и конкретный корректирующий запуск описаны в [protocol](../PETCLINIC_TECHNICAL_STARTUP_CORRECTION.md).

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | Audit не выполняет fits, temporal ML не используется. | Исходная спецификация [002](002-original-formalism-map.md) действует. |
| C02 | ПРОВЕРЕНО | Ошибка shared database initialization объяснена JDBC logs и Compose service_started dependency. | Dependency нельзя скрывать из model representation. |
| C03 | ПРОВЕРЕНО | M7 census [001](001-m7-complete-census.md) неизменен. | Этот audit не создаёт новых scientific observations. |
| C04 | ПРОВЕРЕНО | Исходные 162 warmup verdicts не заменены; numeric deadline и fixtures сохранены. | Готовность не была достигнута, baseline не начался. |
| C05 | ПРОВЕРЕНО | 162 unique warmup IDs сохранены; список actual archive members/bytes/hashes в audit. | Qualification trace census stochastic данных отсутствующего условия ещё невозможен. |
| C06 | ОТКЛОНЕНИЕ | Customers, Vets, Visits a/b exited 1, OOMKilled=false, restart_count=0. | Явное SQL readiness gate перед Java startup; тот же image. |
| C07 | Н/П | До fault injection дело не дошло. | Семь других stochastic jobs и прежние v3 fault controls не переоцениваются этим audit. |
| C08 | ПРОВЕРЕНО | [007](007-petclinic-runtime-qualified.md) 192 runtime controls сохраняют действие. | Startup scheduling correction ещё должна дать полную acquisition. |
| C09 | ПРОВЕРЕНО | M9S/U/X PMX qualification не менялась. | PMX Petclinic interface ещё впереди. |
| C10 | ПРОВЕРЕНО | Connection refused и HTTP failures оставлены исходными. | Warmup failures не подменяют calibration availability. |
| C11 | ОТКЛОНЕНИЕ | В восьмиусловном пакете одно условие не собрано. | Исправляется только оно с тем же seed; семь остальных сохраняют первоначальный provenance. |
| C12 | ПРОВЕРЕНО | Audit читает retained source вне fit; model fits=0. | Mixed raw archive не передаётся будущим fit jobs. |
| C13 | НЕ ПРОВЕРЕНО | Main campaigns=0. | Ни failed warmup, ни technical package не включаются в 240/800. |
| C14 | Н/П | Нет predictions/accuracy tests. | Повтор не выбирается по error magnitude или advantage. |
| C15 | ПРОВЕРЕНО | Failed original job, raw artifact 10046679072 и compact audit сохранены. | Отсутствующая campaign остаётся отсутствующей до фактического сбора v2. |
| C16 | Н/П | Transfer не выполняется. | Source-only transfer contract остаётся открытым до моделирования. |
| C17 | ПРОВЕРЕНО | Actual raw bytes 465113, SHA/CRC, run metadata и CLI costs retained. | Failed preparation costs должны входить в development cost; не равны full pipeline cost. |
| C18 | ПРОВЕРЕНО | Логи показывают точную причину; отдельный v2 source/config/workflow добавляет SQL gate. | Нет повторной сборки image или изменения научных thresholds/seed. |
| C19 | ПРОВЕРЕНО | [Exact audit archive/API](../evidence/petclinic-startup-audit-34203827517/artifact-api.json), source SHA/head и member inventory. | Full application archive проанализирован только remote. |
| C20 | ПРОВЕРЕНО | Получена новая конкретная причина, подход меняется с HTTP polling к dependency readiness. | Повторные бессодержательные warmup retries не добавляются. |
| C21 | ПРОВЕРЕНО | Ошибка bootstrap не объявлена estimator error или availability=0. | Эффективность метода здесь не проверялась. |
| C22 | ПРОВЕРЕНО | Audit evidence, correction protocol и все 22 статуса сохранены. | Полный technical package и публикационный пакет ещё не завершены. |
