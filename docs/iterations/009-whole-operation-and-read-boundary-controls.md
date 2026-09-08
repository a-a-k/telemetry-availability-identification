# Итерация 009: bounded contract/read-boundary controls

Вопросы заранее заданы в [изолированном interface protocol](../ISOLATED_ORIGINAL_MODEL_INTERFACE_PROTOCOL.md) и [таблице десяти операций](../TEN_EXTERNAL_OPERATION_CONTRACTS.md): можно ли исключить фактическое чтение test/schedule во время fit и выразить общий deadline составной HTTP-операции без per-step reset? Пять unittest controls загрузчика и шесть controls HTTP-контракта прошли. Последний включает маленький локальный искусственный HTTP server, конечное тело и медленную передачу; приложений, native-data parsing или scientific fits локально не запускалось. CI d24951c проверил loader на Python 3.11/3.13; CI 0a288ed проверяет добавленные HTTP controls. Live interfaces запущены отдельно и не объявлены пройденными этой записью.

| ID | Статус | Доказательство | Ограничение / действие |
| --- | --- | --- | --- |
| C01 | ПРОВЕРЕНО | Новый isolated entry point вызывает только original prepare/finite likelihood/predict; шесть старых методов. | Full-data fit qualification ещё выполняется remote. |
| C02 | ПРОВЕРЕНО | Output representation явно хранит graph declaration и scalar q limitation. | General typed graph не реализован новым entry point. |
| C03 | ПРОВЕРЕНО | Frozen M7 source, all 160/480 outcomes и [001](001-m7-complete-census.md) неизменны. | Whole-deadline изменение относится только к будущим данным. |
| C04 | ПРОВЕРЕНО | [10 contracts](../TEN_EXTERNAL_OPERATION_CONTRACTS.md); 3×0.8 s checkout failure, partial/duplicate/wrong-user tests. | Live qualification новых DS/OTel predicates ещё ожидается. |
| C05 | ПРОВЕРЕНО | Один request ID/trace context для трёх HTTP roots в control; все started steps сохраняются. | Реальный live trace census ещё проверяется remote. |
| C06 | ПРОВЕРЕНО | Petclinic v2 contracts и [007](007-petclinic-runtime-qualified.md) сохраняются. | SQL-startup recovery/8 stochastic cases ещё выполняются. |
| C07 | ПРОВЕРЕНО | L7OK decoding учитывает running/paused/backend state; raw status не переписан. | Старый L4 deployment сохраняет свои ограничения. |
| C08 | ПРОВЕРЕНО | 11 новых bounded unittest methods прошли; L4 truth table совпадает с frozen decoder. | Calculator controls M9S/U/X не повторяются без изменения representation. |
| C09 | ПРОВЕРЕНО | Наш fit не читает PMX, future PMX получает native calibration. Primary conditional-local выбран по propagation semantics. | Petclinic DB constructs требуют independent adapter/control qualification. |
| C10 | ПРОВЕРЕНО | Deadline и prerequisite verdict не используют span presence/error; discarded fields не выдают за complete result. | DS silent empty-list omission и late side effects других приложений явно вне oracle claims. |
| C11 | НЕ ПРОВЕРЕНО | Main protocol ещё не заморожен; эти controls не являются новой effectiveness series. | 240-campaign matrix остаётся следующим научным этапом после qualification. |
| C12 | ПРОВЕРЕНО | Реальный sys audit hook блокирует чтение evaluator и generating schedule; file-set seal отвергает лишний test file до чтения. | Actual full fit read audit ещё должен быть получен в Actions. |
| C13 | НЕ ПРОВЕРЕНО | Main campaigns=0. | 800 cells ещё не получены. |
| C14 | Н/П | Нет availability estimates/CI от локальных controls. | Основной paired campaign bootstrap впереди. |
| C15 | ПРОВЕРЕНО | Отсутствующие inputs не заменяются успехом; unusable acquisition даёт explicit absence. | Полный new-case census после remote jobs. |
| C16 | ПРОВЕРЕНО | Transfer выполняется только colocated cell без второго dataset input. | Actual source-only transfer forecasts ещё не получены. |
| C17 | НЕ ПРОВЕРЕНО | Remote fit workflow записывает GNU time/RSS; пока чисел нет. | Waiting/development/job costs не должны исчезнуть из итоговой стоимости. |
| C18 | ПРОВЕРЕНО | Установлены prior per-step deadline и L7 decoder mismatches, введены отдельные modules/configs. | Frozen M7 не переписан; affected new live interfaces проходят отдельную qualification. |
| C19 | ПРОВЕРЕНО | Commit-pinned protocols, source derivation hashes трёх orchestration functions, actual role archive verifier. | До main нужно закрепить финальные acceptance/source locks. |
| C20 | ПРОВЕРЕНО | Получены исполнимые controls и source-only/whole-deadline code; нет бесцельного повторения failed setup. | Далее фактические remote interface results. |
| C21 | ПРОВЕРЕНО | Partial response/read boundary qualification не выдана за forecast superiority. | Claims ограничены конкретными пройденными controls. |
| C22 | ПРОВЕРЕНО | Оба protocols, tests, derivation provenance и все 22 статуса сохранены. | Main comparison/transfer/cost/claim package остаётся открытым. |
