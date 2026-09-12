"""Export every stored forecast, primary-compatibility and stage-cost scalar."""
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from render_v3_comparison_tables_v1 import render,csv_bytes
from export_v3_cost_scopes_v1 import export
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases

RUN=34703686592
HEAD='12ddb09369ee6e0b60ca4c7db6fe1e749530b7df'


def main():
    evidence=Path(f'docs/evidence/v4-confirmation-v2-{RUN}')
    out=Path(f'docs/tables/v4-confirmation-v2-{RUN}')
    retained=json.loads((evidence/'retention.json').read_bytes())
    if retained['run']!=RUN or retained['head']!=HEAD:raise ValueError('confirmation retention differs')
    source=evidence/'analysis/comparison.json'
    render(source,out/'forecasts')
    export(source,out/'recorded-pipeline-costs')
    confirmation_path=evidence/'analysis/confirmation.json'
    confirmation=json.loads(confirmation_path.read_bytes())
    seal=json.loads((evidence/'analysis/confirmation-seal.json').read_bytes())
    if (confirmation['run']!=str(RUN) or confirmation['head']!=HEAD or
        seal['files']['confirmation.json']!=sha256(confirmation_path.read_bytes()).hexdigest()):raise ValueError('primary aggregate provenance differs')
    def flatten(row):
        value=dict(row);identity=value.pop('identity');return dict(identity,**value)
    primary=[flatten(r)for r in confirmation['operations']]
    controls=[flatten(r)for r in confirmation['controls']]
    _,_,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    sources=[]
    for index,case in enumerate(cases,1):
        receipt=json.loads((evidence/f'case-{index:03d}/receipt/receipt.json').read_bytes())
        sources.append(dict(case['identity'],acquisition_run=receipt['acquisition_run'],acquisition_head=receipt['acquisition_head'],
            analysis_run=RUN,analysis_head=HEAD,recollected=case['profile']=='spring_petclinic_microservices',
            graph_input_seal_sha256=receipt['graph_input_seal_sha256'],pmx_input_seal_sha256=receipt['pmx_input_seal_sha256'],
            test_binding_seal_sha256=receipt['test_binding_seal_sha256'],primary_closed_seal_sha256=receipt['primary_closed_seal_sha256']))
    for name,rows in [('primary-compatibility',primary),('directed-controls',controls),('acquisition-source-map',sources)]:
        transport.persist(out/(name+'.csv'),csv_bytes(rows))
    transport.persist(out/'scientific-checks.json',transport.encoded(dict(checks=confirmation['checks'],
        qualified_within_declared_conditions=confirmation['qualified_within_declared_conditions'],
        temporal_gate_audit=retained['temporal_gate_audit'],historical_C12_reclassified=False,
        new_outcomes_opened_only_after_all_forecasts=retained['all_primary_and_freeze_jobs_complete'])))
    transport.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    note='''# Полные результаты независимой серии

Все сохранённые прогнозы, поддержки, ошибки и первичные проверки экспортированы без локального исполнения моделей или повторного статистического расчёта.

- `forecasts/`: все 600 слотов десяти методов, собственная и общая поддержка, ошибки, заранее заданные контрасты и интервалы, отказы и исходные затраты стадий.
- `primary-compatibility.csv`: проверка обоих направлений несовместимости по независимым исходам на исходной совокупности попыток, включая структурные отказы.
- `directed-controls.csv`: отдельные 48 normal/retry-контролей; они не добавлены в прогнозную выборку.
- `acquisition-source-map.csv`: точный источник каждой из 18 кампаний. 12 завершённых кампаний сохранены из исходной серии; только шесть технически потерянных Petclinic собраны вновь.
- `scientific-checks.json`: все критерии и независимый контроль хронологии барьеров. Зелёный workflow не подменяет эти критерии.
- `recorded-pipeline-costs/`: полные временные наблюдения по стадиям, процессы и их ресурсы, загрузка/анализ каждой PMX-модели, извлечение, размеры входов и неизмеренные величины.

Сохранённые затраты приобретения телеметрии для 12 перенесённых кампаний относятся к их первоначальному сбору. Копирование запечатанных ролей не объявляется новым сбором. Время вложенной стадии нельзя прибавлять к охватывающему её процессу; ресурсы общих solver-batch учитываются отдельно. Эти записи описывают выполненный распределённый конвейер и не заменяют парный end-to-end эксперимент. Прежние коэффициенты полного конвейера остаются результатами прежней привязки. Новое симметричное сравнение вычислительных представлений имеет отдельные таблицы всех семи режимов.

Realized-state проверка использует native-состояния тестовых попыток и отвечает на вопрос адекватности события. Прогнозы в `forecasts/` построены по calibration и зафиксированы раньше открытия test; их ошибки не вычислены путём переидентификации по тестовым исходам. Идентификационные границы и статистическая неопределённость прогнозных ошибок имеют разные смыслы.
'''
    transport.persist(out/'README.md',note.encode('utf-8'))
    print(json.dumps(dict(primary_operation_rows=len(primary),control_operation_rows=len(controls),
        qualified_within_declared_conditions=confirmation['qualified_within_declared_conditions'],checks=confirmation['checks'])))


if __name__=='__main__':main()
