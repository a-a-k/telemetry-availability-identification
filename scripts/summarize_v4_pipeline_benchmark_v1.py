"""Tabulate recorded matched pipeline times; no native data, model or bootstrap."""
import argparse
import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import statistics


def read(path):return json.loads(Path(path).read_bytes())


def measurement(record):
    stages=list(record['stages'].values())
    resources=[s['resource'] for s in stages]
    known=all(r and all(r.get(k) is not None for k in ('user_seconds','system_seconds','maximum_rss_bytes')) for r in resources)
    return dict(wall_seconds=record['wall_seconds'],
        summed_timed_command_cpu_seconds=sum(r['user_seconds']+r['system_seconds'] for r in resources) if known else None,
        largest_process_peak_rss_mib=max(r['maximum_rss_bytes'] for r in resources)/2**20 if known else None,
        outer_minus_command_wall_seconds=record['wall_seconds']-sum(s['wall_seconds'] for s in stages))


def stats(rows,key):
    values=[r[key] for r in rows if r.get(key) is not None]
    return {f'{key}_{suffix}':fn(values) if values else None
            for suffix,fn in [('median',statistics.median),('min',min),('max',max)]}


def csv_data(rows):
    columns=list(dict.fromkeys(k for row in rows for k in row))
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode()


def export(evidence,out):
    receipt=read(evidence/'retention.json')
    protocol_path=evidence/receipt['artifacts'][0]['profile']/'protocol.json'
    protocol=read(protocol_path)
    paired=[];stage_rows=[];verification_rows=[]
    sources={path.as_posix():sha256(path.read_bytes()).hexdigest()
             for path in (evidence/'retention.json',protocol_path)}
    for artifact in receipt['artifacts']:
        profile=artifact['profile'];path=evidence/profile/'results.json';raw=path.read_bytes()
        sources[path.as_posix()]=sha256(raw).hexdigest()
        result=json.loads(raw)
        if result.get('control_verification'):
            v=result['control_verification'];verification_rows.append(dict(application=profile,stage='known_controls',repetition=None,multiplier=None,outer_command_wall_seconds=v['wall_seconds'],**(v['resource'] or {})))
        for row in result['records']:
            base=dict(application=profile,repetition=row['repetition'],multiplier=row['multiplier'],
                      attempts=row['workload']['attempts'],native_spans=row['workload']['native_spans'],
                      method_order='/'.join(row['method_order']),status=row['status'],error=row.get('error'))
            for role in ('ordinary','pmx'):
                base[role+'_input_bytes']=sum(r['bytes'] for name,r in row['workload']['files'].items() if name.startswith(role+'/'))
            for method in ('graph','pmx'):
                if method not in row:continue
                base.update({method+'_'+k:v for k,v in measurement(row[method]).items()})
                forecasts=row[method].get('forecasts')
                target='Gstar' if method=='graph' else 'PMX'
                base[method+'_point_operations']=sum(f[target]['status']=='ok' for f in forecasts.values()) if forecasts is not None else None
                for stage,value in row[method]['stages'].items():
                    stage_rows.append(dict(application=profile,repetition=row['repetition'],multiplier=row['multiplier'],
                        method=method,stage=stage,outer_command_wall_seconds=value['wall_seconds'],
                        exit_code=value['exit_code'],**(value['resource'] or {})))
            if row['status']=='qualified':
                base['speedup_pmx_over_graph']=row['speedup_pmx_over_graph']
                base['pmx_fixed_launch_seconds']=20*len(row['pmx']['forecasts'])
                base['pmx_wall_minus_declared_launch_seconds']=base['pmx_wall_seconds']-base['pmx_fixed_launch_seconds']
                base['startup_subtracted_ratio_arithmetic_only']=base['pmx_wall_minus_declared_launch_seconds']/base['graph_wall_seconds']
                structure=row['graph']['model_structure']
                base.update(graph_nodes_across_operation_models=sum(m['nodes'] for m in structure.values()),
                    graph_edges_across_operation_models=sum(m['edges'] for m in structure.values()),
                    graph_categories_across_operation_models=sum(m['categories'] for m in structure.values()),
                    pmx_application_models=row['pmx']['models'])
            for name,v in row.get('extra_verification_stages',{}).items():
                verification_rows.append(dict(application=profile,stage=name,repetition=row['repetition'],multiplier=row['multiplier'],outer_command_wall_seconds=v['wall_seconds'],**(v['resource'] or {})))
            paired.append(base)
    summaries=[];scaling=[]
    for profile in protocol['applications']:
        for multiplier in protocol['multipliers']:
            planned=[r for r in paired if r['application']==profile and r['multiplier']==multiplier]
            good=[r for r in planned if r['status']=='qualified']
            summary=dict(application=profile,multiplier=multiplier,attempts=3600*multiplier,
                         planned_pairs=len(planned),qualified_pairs=len(good))
            for key in ('native_spans','ordinary_input_bytes','pmx_input_bytes','graph_point_operations','pmx_point_operations',
                        'graph_nodes_across_operation_models','graph_edges_across_operation_models',
                        'graph_categories_across_operation_models','pmx_application_models'):
                values={r[key] for r in good if key in r}
                summary[key]=next(iter(values)) if len(values)==1 else None
            for key in ('graph_wall_seconds','pmx_wall_seconds','speedup_pmx_over_graph',
                        'graph_summed_timed_command_cpu_seconds','pmx_summed_timed_command_cpu_seconds',
                        'graph_largest_process_peak_rss_mib','pmx_largest_process_peak_rss_mib',
                        'pmx_wall_minus_declared_launch_seconds','startup_subtracted_ratio_arithmetic_only'):
                summary.update(stats(good,key))
            summaries.append(summary)
        base=next(r for r in summaries if r['application']==profile and r['multiplier']==1)
        for summary in [r for r in summaries if r['application']==profile]:
            for method in ('graph','pmx'):
                seconds=summary[method+'_wall_seconds_median'];original=base[method+'_wall_seconds_median']
                memory=summary[method+'_largest_process_peak_rss_mib_median'];base_memory=base[method+'_largest_process_peak_rss_mib_median']
                scaling.append(dict(application=profile,method=method,multiplier=summary['multiplier'],
                    attempts=summary['attempts'],qualified_pairs=summary['qualified_pairs'],
                    median_pipeline_seconds=seconds,attempts_per_second=summary['attempts']/seconds if seconds else None,
                    time_growth_relative_to_1x=seconds/original if seconds and original else None,
                    memory_growth_relative_to_1x=memory/base_memory if memory and base_memory else None,
                    descriptive_log_time_exponent=math.log(seconds/original)/math.log(summary['multiplier'])
                        if seconds and original and summary['multiplier']>1 else None,
                    scope='fixed topology and empirical observation law; replicated telemetry volume; not asymptotic complexity'))
    files={'paired-pipelines.csv':csv_data(paired),'pipeline-summary.csv':csv_data(summaries),
           'stage-processes.csv':csv_data(stage_rows),'telemetry-scaling.csv':csv_data(scaling),
           'verification-processes.csv':csv_data(verification_rows)}
    note=f'''# Revised telemetry-to-first-answer pipeline and Palladio scaling

Run {receipt['run_id']}, measurement source {receipt['head']}. All 27 planned pairs are retained: fixed split/N/0 calibration for each application, volumes 3600/7200/14400 and three technical rounds. Copies are computational workloads, not independent observations.

The primary boundary starts at sealed prepared calibration roles with installed tools and ends at the first saved forecasts. Graph: revised v4 binding, six variants plus G0/B0, one build process. PMX: independent native projection/extraction, conditional_local and inclusive, collection, one application-only Palladio pass, saved first candidates. Interpreter/JVM starts and serialization are included. Acquisition, common role projection, transfer, replication and tool installation precede the boundary.

All additional graph replay, separate PMX second passes, known-probability controls and comparisons to frozen source forecasts follow ALL nine measurement pairs for the application. Their {len(verification_rows)} retained process observations appear separately in verification-processes.csv and are not added to primary times. Qualification is required before a measured pair can become a successful speed ratio. Raw first/second solver files remain separate; the unchanged validator receives them as passes 0/1 after timing.

pipeline-summary.csv has median/min/max over three pairs per application/volume; speed ratios are formed within each pair first. paired-pipelines.csv keeps every original pair; stage-processes.csv keeps every primary command and resource. CPU is the sum of disjoint timed commands; memory is the greatest recorded process/children peak, not total runner RSS. Failure rows remain failures, never zero-time solves.

The original 20-second PMX launcher per operation is included. Startup-subtracted arithmetic is a decomposition of measured time, not a measurement of an optimized implementation. All graph-family results are computed, so graph time is an upper bound on Gstar-only work in this implementation. The PMX model count excludes the eight separate control models.

Scaling preserves empirical observations and topology, with renamed request/trace/span identities and shared probes. It measures input-volume scaling at fixed structure, not asymptotic growth in service count. Forecast points/statuses/bounds must reproduce source values to 1e-12. This is distinct from native exact-solver costs on already identified models and from the older two-pass verified-pipeline boundary.

Protocol: docs/V4_PIPELINE_BENCHMARK_V1.md; all clocks, resource scopes, recorded omissions and source hashes remain explicit.
'''
    labels={'deathstarbench_social_network':'DeathStarBench','opentelemetry_demo':'OpenTelemetry','spring_petclinic_microservices':'Petclinic'}
    def number(value):return '—' if value is None else f'{value:.3f}'
    def interval(row,key):return number(row[key+'_median'])+' ['+number(row[key+'_min'])+'; '+number(row[key+'_max'])+']'
    note+='\n## Полная таблица девяти сочетаний приложения и объёма\n\nВремя и парное ускорение: медиана [минимум; максимум] трёх повторов. CPU и память: медианы. Дополнительные проверки исключены из этих времён у обоих методов.\n\n'
    note+='| Приложение | Попытки | Проверено пар | Наш конвейер, с | PMX/Palladio, с | PMX / наш, × | CPU наш / PMX, с | Память наш / PMX, MiB |\n| --- | ---: | ---: | --- | --- | --- | --- | --- |\n'
    for row in summaries:
        note+='| '+labels[row['application']]+' | '+str(row['attempts'])+' | '+str(row['qualified_pairs'])+'/'+str(row['planned_pairs'])+' | '+interval(row,'graph_wall_seconds')+' | '+interval(row,'pmx_wall_seconds')+' | '+interval(row,'speedup_pmx_over_graph')+' | '+number(row['graph_summed_timed_command_cpu_seconds_median'])+' / '+number(row['pmx_summed_timed_command_cpu_seconds_median'])+' | '+number(row['graph_largest_process_peak_rss_mib_median'])+' / '+number(row['pmx_largest_process_peak_rss_mib_median'])+' |\n'
    note+='\n## Все 27 исходных пар\n\nПовтор — технический, начинается с 0. Порядок методов сохранён. Отказ не превращается в успешный коэффициент ускорения.\n\n| Приложение | Повтор | Попытки | Порядок | Статус | Наш, с | PMX, с | PMX / наш, × |\n| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |\n'
    for row in paired:
        note+='| '+labels[row['application']]+' | '+str(row['repetition'])+' | '+str(row['attempts'])+' | '+row['method_order']+' | '+row['status']+' | '+number(row.get('graph_wall_seconds'))+' | '+number(row.get('pmx_wall_seconds'))+' | '+number(row.get('speedup_pmx_over_graph'))+' |\n'
    note+='\n## Масштабирование по объёму наблюдений\n\nФиксированы структура и эмпирический закон; копирование не увеличивает независимую выборку.\n\n| Приложение | Метод | Попытки | T(N) / T(3600) | Память / память(3600) | Попыток/с |\n| --- | --- | ---: | ---: | ---: | ---: |\n'
    for row in scaling:
        note+='| '+labels[row['application']]+' | '+row['method']+' | '+str(row['attempts'])+' | '+number(row['time_growth_relative_to_1x'])+' | '+number(row['memory_growth_relative_to_1x'])+' | '+number(row['attempts_per_second'])+' |\n'
    note+='\nВсе неперекрывающиеся команды основного таймера и CPU/RSS сохранены в [stage-processes.csv](stage-processes.csv); дополнительные проверки — в [verification-processes.csv](verification-processes.csv). [Полная сводка](pipeline-summary.csv) включает объёмы входов, spans, графы, категории, точечную поддержку, прикладные PCM-модели и арифметическое разложение фиксированного запуска PMX.\n'
    files['README.md']=note.encode()
    files['.gitattributes']=b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n'
    provenance=dict(version='v4-pipeline-benchmark-table-export-v1',run_id=receipt['run_id'],head=receipt['head'],sources=sources,
        exporter_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        local_model_solver_or_bootstrap_execution=False,outputs={name:dict(bytes=len(data),sha256=sha256(data).hexdigest()) for name,data in files.items()})
    files['provenance.json']=(json.dumps(provenance,indent=2)+'\n').encode()
    out.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():(out/name).write_bytes(data)
    print(json.dumps(dict(pairs=len(paired),qualified=sum(r['status']=='qualified'for r in paired),summary_rows=len(summaries),verification_rows=len(verification_rows))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();export(args.evidence,args.out)
