"""Complete deterministic tables from compact v2 evidence; never execute models."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from summarize_v3_exact_backends_v1 import table
from retain_v3_exact_comparison_v2 import validate_compact

METHODS=['ours_direct','ours_prepared','cudd_fixed','cudd_sift','agrum_conditioned','agrum_joint','storm_sparse','storm_compact']
REPRESENTATIONS=['original','completion_projected']
PHASES=['initial','repeat','counts','masks','metadata','structure','restore']
STAGES=['total','kernel','cpu','conversion','key_check','construction','update','query_including_update']


def med(xs):return median(xs) if xs else None
def fmt(x):return '—' if x is None else f'{x:.4f}'
def save(path,rows,empty_fields):
    fields=list(rows[0]) if rows else empty_fields
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();receipt=json.loads((args.input/'retention.json').read_text());args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    raw=[];resources=[];summary=[];ratios=[];bounds=[];failures=[];census=[];grid=[];sizes=[];projection=[];environments={}
    for artifact in receipt['artifacts']:
        profile=artifact['profile'];data=json.loads((args.input/profile/'results.json').read_text())
        config=json.loads((args.input/profile/'protocol.json').read_text());validate_compact(data,config)
        environments[profile]=json.loads((args.input/profile/'environment.json').read_text())
        lookup={(r['case_id'],r['method'],r['representation'],r['round'],r['phase']):r for r in data['records']}
        census.append(dict(profile=profile,models=len(data['cases']),original_absences=len(data['absent']),planned=len(data['records']),
            qualified=sum(r['status']=='qualified' for r in data['records']),failed=sum(r['status']=='failed' for r in data['records'])))
        for row in data['records']:
            ok=row['status']=='qualified';identity={k:row[k] for k in ('case_id','method','representation','round','phase')}
            raw.append(dict(profile=profile,**identity,status=row['status'],**{s+'_ms':row[s+'_ns']/1e6 if ok else None for s in STAGES},
                inference_ms=(row['query_including_update_ns']-row['update_ns'])/1e6 if ok else None,reconstructed=row.get('reconstructed'),error=row.get('error')))
            if not ok:failures.append(dict(profile=profile,**identity,error=row['error']))
            if ok:
                st=row['stats'];sizes.append(dict(profile=profile,**identity,input_coordinates=row['input_coordinates'],input_categories=row['input_categories'],
                    semantic_builds=st.get('semantic_builds'),infrastructure_builds=st.get('infrastructure_builds'),network_builds=st.get('network_builds'),
                    engine_builds=st.get('engine_builds'),space_builds=st.get('space_builds'),states=st.get('states'),
                    states_before_compaction=st.get('states_before_compaction'),transitions=st.get('transitions'),prepared_states=st.get('prepared_states'),
                    bn_nodes=st.get('bn_nodes'),cpt_entries=st.get('cpt_entries'),stats_json=json.dumps(st,sort_keys=True)))
        for row in data['resources']:
            resources.append(dict(profile=profile,**{k:row[k] for k in ('case_id','method','representation','round','returncode','timed_out')},
                wall_seconds=row.get('wall_seconds'),cpu_seconds=row['user_seconds']+row['system_seconds'] if 'user_seconds' in row else None,
                peak_rss_mib=row['peak_rss_kib']/1024 if 'peak_rss_kib' in row else None))
        for case in data['cases']:
            cid=case['case_id']
            for phase,estimates in case['expected'].items():
                for name,ex in estimates.items():bounds.append(dict(profile=profile,case_id=cid,phase=phase,functional=name,
                    lower_exact=ex['lower_exact'],upper_exact=ex['upper_exact'],status=ex['status']))
            for phase in PHASES:
                for representation in REPRESENTATIONS:
                    for method in METHODS:
                        for baseline in ('ours_direct','ours_prepared'):
                            if method==baseline:continue
                            samples=[];kernel=[]
                            for rnd in range(config['technical_rounds']):
                                a=lookup[cid,baseline,representation,rnd,phase];b=lookup[cid,method,representation,rnd,phase]
                                if a['status']=='qualified' and b['status']=='qualified':
                                    samples.append(b['total_ns']/a['total_ns']);kernel.append(b['kernel_ns']/a['kernel_ns'])
                            ratios.append(dict(profile=profile,case_id=cid,phase=phase,representation=representation,method=method,baseline=baseline,
                                paired_rounds=len(samples),other_over_ours=med(samples),kernel_other_over_ours=med(kernel),min_ratio=min(samples) if samples else None,max_ratio=max(samples) if samples else None))
                for method in METHODS:
                    samples=[];kernel=[]
                    for rnd in range(config['technical_rounds']):
                        a=lookup[cid,method,'original',rnd,phase];b=lookup[cid,method,'completion_projected',rnd,phase]
                        if a['status']=='qualified' and b['status']=='qualified':
                            samples.append(a['total_ns']/b['total_ns']);kernel.append(a['kernel_ns']/b['kernel_ns'])
                    projection.append(dict(profile=profile,case_id=cid,phase=phase,method=method,paired_rounds=len(samples),
                        original_over_projected=med(samples),kernel_original_over_projected=med(kernel)))
        for representation in REPRESENTATIONS:
            for phase in PHASES:
                for method in METHODS:
                    selected=[r for r in raw if r['profile']==profile and r['representation']==representation and r['method']==method and r['phase']==phase]
                    ok=[r for r in selected if r['status']=='qualified']
                    row=dict(profile=profile,representation=representation,phase=phase,method=method,planned=len(selected),qualified=len(ok),failed=len(selected)-len(ok),
                        **{s+'_median_ms':med([r[s+'_ms'] for r in ok]) for s in STAGES+['inference']},reconstructed_records=sum(r['reconstructed'] for r in ok))
                    for baseline in ('ours_direct','ours_prepared'):
                        pairs=[r for r in ratios if r['profile']==profile and r['representation']==representation and r['method']==method and r['phase']==phase and r['baseline']==baseline and r['paired_rounds']==config['technical_rounds']]
                        row['over_'+baseline]=med([r['other_over_ours'] for r in pairs]);row['pairs_'+baseline]=len(pairs)
                    summary.append(row)
        if profile=='synthetic':
            for case in data['cases']:
                for representation in REPRESENTATIONS:
                    for phase in PHASES:
                        row=dict(case_id=case['case_id'],axis=case['axis'],parameters=json.dumps(case['parameters'],sort_keys=True),representation=representation,phase=phase)
                        for method in METHODS:
                            xs=[lookup[case['case_id'],method,representation,r,phase] for r in range(config['technical_rounds'])]
                            ys=[x['total_ns']/1e6 for x in xs if x['status']=='qualified']
                            row[method+'_median_ms']=med(ys);row[method+'_qualified_rounds']=len(ys)
                        grid.append(row)
    files=dict(measurements=raw,process_resources=resources,stage_summary=summary,paired_ratios=ratios,exact_bounds=bounds,failures=failures,
        census=census,synthetic_grid=grid,representations=sizes,projection_ratios=projection)
    for name,rows in files.items():save(args.out/(name+'.csv'),rows,['profile','case_id','method','representation','round','phase','error'])
    provenance=dict(run_id=receipt['run_id'],head=receipt['head'],tables={p.name:dict(rows=len(files[p.stem]),sha256=sha256(p.read_bytes()).hexdigest()) for p in sorted(args.out.glob('*.csv'))},
        sources={p.relative_to(args.input).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(args.input.glob('*/*.json'))},local_model_execution=False)
    (args.out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    report=['# Исправленное сравнение точных алгоритмов v2\n',f'Run **{receipt["run_id"]}**, source `{receipt["head"]}`. Все таблицы автоматически построены из проверенных compact artifacts.\n',
        '## Полнота и контракт\n',table(['Набор','Моделей','Исходных отсутствий','План','Совпали точно','Отказ'],[[r[k] for k in ('profile','models','original_absences','planned','qualified','failed')] for r in census]),
        '78 прикладных моделей из исходных repetition=0, 27 искусственных позиций; 8 вариантов, 2 представления, 7 снимков, 3 технических повтора. Неуспешные вычисления сохранены; их время не подставляется равным нулю. Все квалифицированные ответы совпали с исходным точным ядром по 11 парам рациональных границ и статусам. Свидетельства не входят в выход ни одного метода. Проверка выполнена после всех измерительных процессов профиля. Новых кампаний нет.\n',
        '## Среда\n',table(['Набор','CPU','Версии'],[[p,next((s.split(':',1)[1].strip() for s in e['cpu_info'].splitlines() if s.startswith('model name')),'unknown'),json.dumps(e['versions'],sort_keys=True)] for p,e in environments.items()]),
        'Python, ОС, память и полный список пакетов сохранены в environment.json. Один поток, 60 с на поток из семи снимков, 3 GiB адресного пространства; aGrUM — 1 GiB на inference. Импорт выбранной библиотеки исключён из model-to-answer, включён в время и RSS процесса.\n',
        '## Все фазы и представления\n',
        'Время в мс. initial — первое построение; repeat — тот же запрос; counts — новые частоты; masks — скрытие завершения и объединение категорий; metadata — изменение метаданных; structure — добавленная синхронная связь; restore — возврат исходной модели. Один backend сохраняется на все семь снимков; CUDD сохраняет manager, aGrUM контейнер BN, Storm Environment и кэш свойств. Преобразование, проверка ключа и перестроение включены.\n',
        'Kд и Kп = время конкурента / время нашего исходного и подготовленного алгоритма соответственно. K>1 означает меньшее время нашего алгоритма. Сначала медиана парных отношений трёх повторов на модель, затем медиана по полностью общим моделям. Число полных пар показано рядом. Абсолютные времена — медианы успешных измерений; при отказах наборы могут различаться. Варианты не выбираются по скорости отдельно для каждого случая.\n']
    for profile in environments:
        for representation in REPRESENTATIONS:
            rs=[r for r in summary if r['profile']==profile and r['representation']==representation]
            report+=['### '+profile+' / '+representation+'\n',table(['Фаза','Метод','Успешно/план','Всего','Преобр.','Ключ','Постр.','Обнов.','Запрос','Kд (пар)','Kп (пар)'],
                [[r['phase'],r['method'],f'{r["qualified"]}/{r["planned"]}']+[fmt(r[k+'_median_ms']) for k in ('total','conversion','key_check','construction','update','inference')]+
                 [fmt(r['over_'+b])+f' ({r["pairs_"+b]})' for b in ('ours_direct','ours_prepared')] for r in rs])]
    report+=['## Память и время свежего процесса\n','RSS включает весь процесс с семью снимками, импортом и записью результатов; это не память отдельного запроса. Таймауты без RSS не заменяются нулём. CPU модельного расчёта отдельно находится в measurements.csv.\n']
    memory=[]
    for profile in environments:
        for representation in REPRESENTATIONS:
            for method in METHODS:
                rs=[r for r in resources if r['profile']==profile and r['representation']==representation and r['method']==method and r['peak_rss_mib'] is not None]
                memory.append([profile,representation,method,len(rs),fmt(med([r['peak_rss_mib'] for r in rs])),fmt(med([r['cpu_seconds'] for r in rs])),fmt(med([r['wall_seconds'] for r in rs]))])
    report.append(table(['Набор','Вход','Метод','Процессов','RSS МиБ','CPU с','Wall с'],memory))
    report+=['## Полная искусственная сетка\n',table(['Случай','Вход','Фаза']+METHODS,
        [[r['case_id'],r['representation'],r['phase']]+[fmt(r[m+'_median_ms'])+f' ({r[m+"_qualified_rounds"]}/3)' for m in METHODS] for r in grid]),
        '## Область вывода\n',
        'Original и completion_projected решают одну задачу: проекция K=AND(C) сохраняет допустимые совместные законы на наблюдаемых масках и все 11 функционалов. Её стоимость включена в итоговые отношения. В projection_ratios.csv отдельно показаны парные отношения исходного и общего сокращённого входа; kernel-время без преобразования служит дополнительной диагностикой.\n',
        'aGrUM — точный вывод для вспомогательного полного носителя с double-арифметикой и рациональным агрегированием частот. Это специальное сведение задачи границ, не произвольная credal network. Conditioned и joint — заранее заданные расписания одних запросов; дополнительная смесь для проверки удалена. Storm использует точную рациональную DTMC/MDP: sparse и compact различаются точным сокращением графа, окружение сохраняется. Проверены эти конкретные реализации и режимы.\n',
        'Это сравнение вычислительных затрат по сохранённой идентифицированной модели. Совпадение ответов точных решателей не измеряет качество самостоятельного восстановления модели или прогнозов по новым исходам. Распределение структурных изменений задано экспериментом. Полный PMX-конвейер и прежняя когорта CUDD со свидетельствами имеют другие границы измерения и не объединяются с этой таблицей.\n',
        '## Полные машинные таблицы\n','representations.csv содержит размеры структур и счётчики их перестроений на каждом успешном снимке. Пустые значения неприменимы; полные нативные метрики сохранены в stats_json.\n',
        '\n'.join(f'- [{name}.csv]({name}.csv): {len(rows)} строк.' for name,rows in files.items())+'\n']
    (args.out/'REPORT.md').write_text('\n'.join(report),encoding='utf-8',newline='\n')
    print(json.dumps(dict(run_id=receipt['run_id'],tables={n:len(r) for n,r in files.items()},failed=len(failures))))


if __name__=='__main__':main()
