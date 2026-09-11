"""Generate complete comparison tables and Markdown inside GitHub Actions too."""
import argparse
from collections import Counter,defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

METHODS=['prepared_specialized','cudd_controls_first','cudd_sift_once','agrum_lazy','storm_exact']
PHASES=['initial','repeat','counts','masks','metadata','structure','restore']


def save_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();receipt=json.loads((args.input/'retention.json').read_text());args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    raw,resources,summary,ratios,bounds,failures,census,grid,sizes=[],[],[],[],[],[],[],[],[]
    datasets={};environments={}
    for artifact in receipt['artifacts']:
        profile=artifact['profile'];data=json.loads((args.input/profile/'results.json').read_text());datasets[profile]=data
        environments[profile]=json.loads((args.input/profile/'environment.json').read_text())
        by_id={c['case_id']:c for c in data['cases']};lookup={(r['case_id'],r['method'],r['round'],r['phase']):r for r in data['records']}
        census.append(dict(profile=profile,models=len(data['cases']),original_absences=len(data['absent']),
            planned=len(data['records']),qualified=sum(r['status']=='qualified' for r in data['records']),failed=sum(r['status']=='failed' for r in data['records'])))
        for row in data['records']:
            ok=row['status']=='qualified'
            if ok:
                stats=row['stats'];manager=stats.get('native',{}).get('manager',{})
                sizes.append(dict(profile=profile,case_id=row['case_id'],method=row['method'],round=row['round'],phase=row['phase'],
                    circuit_nodes=stats.get('circuit_nodes'),prepared_states=stats.get('prepared_states'),table_bytes=stats.get('table_bytes'),
                    bn_nodes=stats.get('bn_nodes'),bn_arcs=stats.get('bn_arcs'),cpt_entries=stats.get('cpt_entries'),
                    storm_model_type=stats.get('model_type'),storm_states=stats.get('states'),storm_transitions=stats.get('transitions'),storm_choices=stats.get('choices'),
                    cudd_nodes=manager.get('n_nodes'),cudd_peak_nodes=manager.get('peak_nodes'),cudd_memory_bytes=manager.get('mem'),
                    cudd_variables=manager.get('n_vars'),cudd_reorderings=manager.get('n_reorderings')))
            raw.append(dict(profile=profile,case_id=row['case_id'],method=row['method'],round=row['round'],phase=row['phase'],status=row['status'],
                total_ms=row['total_ns']/1e6 if ok else None,cpu_ms=row['cpu_ns']/1e6 if ok else None,
                key_check_ms=row['key_check_ns']/1e6 if ok else None,construction_ms=row['construction_ns']/1e6 if ok else None,
                data_update_ms=row['update_ns']/1e6 if ok else None,
                inference_and_validation_ms=(row['query_including_update_ns']-row['update_ns'])/1e6 if ok else None,
                reconstructed=row.get('reconstructed'),error=row.get('error')))
            if not ok:failures.append(dict(profile=profile,case_id=row['case_id'],method=row['method'],round=row['round'],phase=row['phase'],error=row['error']))
        for row in data['resources']:
            resources.append(dict(profile=profile,case_id=row['case_id'],method=row['method'],round=row['round'],
                returncode=row['returncode'],timed_out=row['timed_out'],wall_seconds=row.get('wall_seconds'),
                cpu_seconds=row['user_seconds']+row['system_seconds'] if 'user_seconds' in row else None,
                peak_rss_mib=row['peak_rss_kib']/1024 if 'peak_rss_kib' in row else None))
        for case in data['cases']:
            for phase,estimates in case['expected'].items():
                for name,ex in estimates.items():bounds.append(dict(profile=profile,case_id=case['case_id'],phase=phase,functional=name,
                    lower_exact=ex['lower_exact'],upper_exact=ex['upper_exact'],status=ex['status']))
            for phase in PHASES:
                for method in METHODS[1:]:
                    samples=[]
                    for rep in range(3):
                        a=lookup[case['case_id'],'prepared_specialized',rep,phase];b=lookup[case['case_id'],method,rep,phase]
                        if a['status']=='qualified' and b['status']=='qualified':samples.append(b['total_ns']/a['total_ns'])
                    ratios.append(dict(profile=profile,case_id=case['case_id'],phase=phase,method=method,paired_rounds=len(samples),
                        other_over_prepared_median=median(samples) if samples else None,
                        min_ratio=min(samples) if samples else None,max_ratio=max(samples) if samples else None))
        for phase in PHASES:
            for method in METHODS:
                selected=[r for r in raw if r['profile']==profile and r['method']==method and r['phase']==phase]
                ok=[r for r in selected if r['status']=='qualified'];paired=[r for r in ratios if r['profile']==profile and r['method']==method and r['phase']==phase and r['paired_rounds']==3]
                summary.append(dict(profile=profile,phase=phase,method=method,planned=len(selected),qualified=len(ok),failed=len(selected)-len(ok),
                    total_median_ms=median(r['total_ms'] for r in ok) if ok else None,
                    cpu_median_ms=median(r['cpu_ms'] for r in ok) if ok else None,
                    key_check_median_ms=median(r['key_check_ms'] for r in ok) if ok else None,
                    construction_median_ms=median(r['construction_ms'] for r in ok) if ok else None,
                    data_update_median_ms=median(r['data_update_ms'] for r in ok) if ok else None,
                    inference_median_ms=median(r['inference_and_validation_ms'] for r in ok) if ok else None,
                    reconstructed_records=sum(r['reconstructed'] for r in ok),fully_paired_cases=len(paired),
                    other_over_prepared_median=median(r['other_over_prepared_median'] for r in paired) if paired else None))
        if profile=='synthetic':
            for case in data['cases']:
                for phase in PHASES:
                    row=dict(case_id=case['case_id'],axis=case['axis'],parameters=json.dumps(case['parameters'],sort_keys=True),phase=phase)
                    for method in METHODS:
                        xs=[lookup[case['case_id'],method,rep,phase] for rep in range(3)];ys=[x['total_ns']/1e6 for x in xs if x['status']=='qualified']
                        row[method+'_median_ms']=median(ys) if ys else None;row[method+'_qualified_rounds']=len(ys)
                    grid.append(row)
    files=dict(measurements=raw,process_resources=resources,stage_summary=summary,paired_ratios=ratios,exact_bounds=bounds,
               failures=failures,census=census,synthetic_grid=grid,representations=sizes)
    for name,rows in files.items():save_csv(args.out/(name+'.csv'),rows)
    provenance=dict(run_id=receipt['run_id'],head=receipt['head'],tables={p.name:dict(rows=len(files[p.stem]),sha256=sha256(p.read_bytes()).hexdigest()) for p in sorted(args.out.glob('*.csv'))},
        sources={p.relative_to(args.input).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(args.input.glob('*/*.json'))},local_model_execution=False)
    (args.out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    fmt=lambda x:'—' if x is None else f'{x:.4f}'
    report=['# Подготовленные ядра, байесовский вывод и прямой Storm\n',
        f'Вычислительный run **{receipt["run_id"]}**, источник `{receipt["head"]}`. Отчёт сформирован из проверенных compact artifacts, без локального исполнения моделей.\n',
        '## Полнота\n',table(['Набор','Моделей','Исходных отсутствий','Запланировано','Успешно','Отказ/таймаут'],
            [[r[k] for k in ('profile','models','original_absences','planned','qualified','failed')] for r in census]),
        'Панель: все исходные repetition=0 по приложениям/размещениям/законам/операциям — 24 кампании и 80 случаев, 78 моделей (12 исходных интервалов OTel), 2 структурных отсутствия. Все 27 искусственных позиций включены отдельно. Семь изменений — искусственные контроли, не новые наблюдения. Все успешные ответы совпали с исходным точным ядром по 11 парам рациональных границ и статусам. Отказы не включаются во время успешных решений и сохраняются в failures.csv.\n',
        '## Вычислительная среда\n',
        table(['Набор','CPU','Логических CPU','Версии'],
              [[p,next((s.split(':',1)[1].strip() for s in e['cpu_info'].splitlines() if s.startswith('model name')),'unknown'),
                e['cpu_count'],', '.join(k+'='+str(v) for k,v in e['versions'].items())] for p,e in environments.items()]),
        'Python, ОС, память runner и полный pip freeze сохранены в environment.json каждого профиля. Импорт выбранной библиотеки выполнен до таймера model-to-answer; он включён в отдельное время всего процесса.\n',
        '## Полные таблицы по фазам\n',
        'Время в мс. initial — построение и первый запрос; repeat — тот же вход; counts — новые частоты; masks — новые маски; metadata — только несемантические метаданные; structure — обязательная отсутствующая связь; restore — возврат к исходной модели. Ключ и его сравнение включены во всех фазах. Выход одинаковый: границы и статусы без свидетельств. Сохранённые готовые ответы/категориальные экстремумы не используются.\n',
        'K=Tдругого/Tподготовленного специализированного ядра; K>1 означает преимущество подготовленного специализированного ядра. Это медиана трёх парных отношений на случай, затем медиана по полностью общим случаям. Абсолютные времена — медианы успешных записей; при отказах их поддержка может различаться.\n']
    for profile in datasets:
        report+=['### '+profile+'\n',table(['Фаза','Метод','Успешно/план','Всего','Ключ','Построение','Обновление','Вывод','K / полных пар'],
            [[r['phase'],r['method'],f'{r["qualified"]}/{r["planned"]}',fmt(r['total_median_ms']),fmt(r['key_check_median_ms']),
              fmt(r['construction_median_ms']),fmt(r['data_update_median_ms']),fmt(r['inference_median_ms']),
              fmt(r['other_over_prepared_median'])+' / '+str(r['fully_paired_cases'])] for r in summary if r['profile']==profile])]
    report+=['## CPU и память процесса\n','Пик RSS — весь отдельный процесс case/method/round с семью снимками, импортом, загрузкой и проверкой; не память одного запроса. Таблица содержит медианы процессов с доступными resource records. При таймауте отсутствующий RSS не подставляется равным нулю. CPU каждого вычислительного участка находится в measurements.csv.\n']
    memory=[]
    for profile in datasets:
        for method in METHODS:
            rs=[r for r in resources if r['profile']==profile and r['method']==method and r['peak_rss_mib'] is not None]
            memory.append([profile,method,len(rs),fmt(median(r['peak_rss_mib'] for r in rs) if rs else None),
                           fmt(median(r['cpu_seconds'] for r in rs) if rs else None),fmt(median(r['wall_seconds'] for r in rs) if rs else None)])
    report.append(table(['Набор','Метод','Процессов','Пик RSS, МиБ','CPU, с','Wall, с'],memory))
    report+=['## Все искусственные случаи\n',table(['Случай','Фаза']+METHODS,
        [[r['case_id'],r['phase']]+[fmt(r[m+'_median_ms'])+f' ({r[m+"_qualified_rounds"]}/3)' for m in METHODS] for r in grid]),
        '## Интерпретация и область\n',
        'Время начинается с сохранённой модели; извлечение телеметрии и самостоятельная идентификация вероятностных параметров конкурентами здесь не сравниваются. Общий коэффициент всего телеметрического конвейера из этих чисел не следует. Симметричное переиспользование включает консервативную проверку всех полей предиката, без доказательства эквивалентности разных формул. Частота реальных изменений структуры не измерена: распределение фаз задано экспериментатором.\n',
        'aGrUM LazyPropagation рассчитывает точечные posterior и, для интервалов, возможные исходы вспомогательного закона полного носителя. Равномерность неизвестных битов относится только к вспомогательной проверке возможности, не к целевому семейству законов и не к прогнозу. Это доказанная специальная редукция булевых границ, не общий нативный credal-network solver. Нативная арифметика BN — double; рациональные границы агрегируются отдельно, а все успешные результаты проверены.\n',
        'Storm использует точные рациональные DTMC/MDP и рассчитывает минимальную/максимальную вероятность достижения меток. Пространство состояний отражает один совместный наблюдаемый эксперимент и допустимые заполнения масок; интенсивности CTMC и динамическая марковская идентификация не вводились. Проекция по конъюнкции завершений сохраняет все 11 функционалов. Первое сравнение CUDD на 761 модели со свидетельствами и PMX-конвейер остаются отдельными когортами.\n',
        '## Все машинные таблицы\n',
        'representations.csv сохраняет размеры подготовленных таблиц, BN/CPT, CUDD и пространства состояний Storm по каждому успешному расчёту. Нативная память manager CUDD отличается от пика RSS всего процесса. Пустое поле означает неприменимость показателя, а не ноль.\n',
        '\n'.join(f'- [{name}.csv]({name}.csv): {len(rows)} строк.' for name,rows in files.items() if rows)+'\n']
    (args.out/'REPORT.md').write_text('\n'.join(report),encoding='utf-8',newline='\n')
    print(json.dumps(dict(run_id=receipt['run_id'],tables={n:len(r) for n,r in files.items()},failed=len(failures))))


if __name__=='__main__':main()
