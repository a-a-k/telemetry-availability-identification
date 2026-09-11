"""Tables from verified compact timing records only; no model execution."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

METHODS = ['specialized', 'controls_first', 'structural', 'sift_once']
LABELS = dict(specialized='Специализированный', controls_first='CUDD: controls first',
              structural='CUDD: structural', sift_once='CUDD: sift once')
APPS = dict(deathstarbench_social_network='DeathStarBench', opentelemetry_demo='OpenTelemetry Demo',
            spring_petclinic_microservices='Petclinic', synthetic='Искусственная сетка')


def write_csv(path, rows):
    if not rows: return
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    args = parser.parse_args()
    if args.run != 34583421491:
        raise ValueError('this scientific readout is scoped to the declared CUDD cohort 34583421491')
    source = Path(f'docs/evidence/v3-bdd-comparison-{args.run}')
    receipt = json.loads((source/'retention.json').read_text())
    out = Path(f'docs/tables/v3-bdd-comparison-{args.run}'); out.mkdir(parents=True, exist_ok=True)
    (out/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    datasets, environments = {}, {}
    measurements, resources, bounds, absences, pairs, summaries, grid = [], [], [], [], [], [], []
    for artifact in receipt['artifacts']:
        profile = artifact['profile']
        data = json.loads((source/profile/'results.json').read_text())
        if not data['qualified']: raise ValueError('unqualified dataset requires explicit failure report')
        datasets[profile] = data
        environments[profile] = json.loads((source/profile/'environment.json').read_text())
        by_id = {c['case_id']:c for c in data['cases']}
        records = {(r['case_id'], r['method'], r['round']):r for r in data['records']}
        for row in data['records']:
            c = by_id[row['case_id']]
            measurements.append(dict(profile=profile, case_id=row['case_id'], method=row['method'], round=row['round'],
                status=row['status'], execution_status=c['estimates']['execution']['status'],
                cold_ms=row['cold_ns']/1e6, cold_cpu_ms=row['cold_cpu_ns']/1e6,
                warm_1_ms=row['warm_ns'][0]/1e6, warm_2_ms=row['warm_ns'][1]/1e6, warm_3_ms=row['warm_ns'][2]/1e6,
                warm_median_ms=median(row['warm_ns'])/1e6, warm_cpu_median_ms=median(row['warm_cpu_ns'])/1e6,
                build_ms=row['build_seconds']*1000, reorder_ms=row['reorder_seconds']*1000,
                evaluated_states=row['evaluated_states'],
                cudd_execution_nodes=None if row['cudd'] is None else row['cudd']['execution_dag_nodes'],
                cudd_manager_bytes=None if row['cudd'] is None else row['cudd']['manager_bytes'],
                witnesses_verified_first_query=row['checks']['witnesses_verified'],
                category_extrema_sha256=row['category_extrema_sha256'], exact_estimates_sha256=row['exact_estimates_sha256']))
        for row in data['process_resources']:
            resources.append(dict(profile=profile, method=row['method'], round=row['round'],
                wall_seconds=row['wall_seconds'], user_seconds=row['user_seconds'], system_seconds=row['system_seconds'],
                peak_rss_mib=row['peak_rss_kib']/1024, returncode=row['returncode']))
        for c in data['cases']:
            for name, ex in c['estimates'].items():
                bounds.append(dict(profile=profile, case_id=c['case_id'], functional=name,
                    lower_exact=ex['lower_exact'], upper_exact=ex['upper_exact'], status=ex['status'], model_sha256=c['model_sha256']))
            for method in METHODS[1:]:
                ours = [records[c['case_id'], 'specialized', r] for r in range(3)]
                theirs = [records[c['case_id'], method, r] for r in range(3)]
                ratios = [a['cold_ns']/b['cold_ns'] for a, b in zip(ours, theirs)]
                warm_ratios = [median(a['warm_ns'])/median(b['warm_ns']) for a, b in zip(ours, theirs)]
                pairs.append(dict(profile=profile, case_id=c['case_id'], method=method,
                    execution_status=c['estimates']['execution']['status'],
                    cold_ratio_specialized_over_bdd_median=median(ratios), cold_ratio_min=min(ratios), cold_ratio_max=max(ratios),
                    warm_ratio_specialized_over_bdd_median=median(warm_ratios), warm_ratio_min=min(warm_ratios), warm_ratio_max=max(warm_ratios),
                    specialized_cold_median_ms=median(r['cold_ns'] for r in ours)/1e6,
                    bdd_cold_median_ms=median(r['cold_ns'] for r in theirs)/1e6,
                    specialized_warm_median_ms=median(median(r['warm_ns']) for r in ours)/1e6,
                    bdd_warm_median_ms=median(median(r['warm_ns']) for r in theirs)/1e6))
        for c in data['absent']:
            absences.append(dict(profile=profile, case_id=c['case_id'], status=c['status'], reason=c['reason']))
        for group in ('all', 'singleton_given_empirical_observation_law', 'ambiguous'):
            ids = {c['case_id'] for c in data['cases'] if group == 'all' or c['estimates']['execution']['status'] == group}
            if not ids: continue
            for method in METHODS:
                measured = [r for r in data['records'] if r['case_id'] in ids and r['method'] == method]
                proc = [r for r in resources if r['profile'] == profile and r['method'] == method]
                all_cold = [sum(r['cold_ns'] for r in measured if r['round'] == i)/1e9 for i in range(3)]
                all_warm = [sum(median(r['warm_ns']) for r in measured if r['round'] == i)/1e9 for i in range(3)]
                paired = [r for r in pairs if r['profile'] == profile and r['method'] == method and r['case_id'] in ids]
                summaries.append(dict(profile=profile, group=group, method=method, cases=len(ids),
                    cold_median_ms=median(r['cold_ns'] for r in measured)/1e6,
                    warm_median_ms=median(median(r['warm_ns']) for r in measured)/1e6,
                    cold_cpu_median_ms=median(r['cold_cpu_ns'] for r in measured)/1e6,
                    warm_cpu_median_ms=median(median(r['warm_cpu_ns']) for r in measured)/1e6,
                    build_median_ms=median(r['build_seconds'] for r in measured)*1000,
                    reorder_median_ms=median(r['reorder_seconds'] for r in measured)*1000,
                    total_cold_median_seconds=median(all_cold), total_warm_median_seconds=median(all_warm),
                    paired_cold_ratio_median=None if not paired else median(r['cold_ratio_specialized_over_bdd_median'] for r in paired),
                    paired_warm_ratio_median=None if not paired else median(r['warm_ratio_specialized_over_bdd_median'] for r in paired),
                    bdd_cold_faster_cases=None if not paired else sum(r['cold_ratio_specialized_over_bdd_median'] > 1 for r in paired),
                    batch_peak_rss_median_mib=median(r['peak_rss_mib'] for r in proc),
                    batch_wall_median_seconds=median(r['wall_seconds'] for r in proc),
                    batch_cpu_median_seconds=median(r['user_seconds']+r['system_seconds'] for r in proc)))
        if profile == 'synthetic':
            for c in data['cases']:
                row = {key:c[key] for key in ('case_id', 'axis', 'nodes', 'edges', 'controls', 'completions', 'coordinates', 'categories', 'max_unknown_controls')}
                row.update(lower_exact=c['estimates']['execution']['lower_exact'], upper_exact=c['estimates']['execution']['upper_exact'])
                for method in METHODS:
                    rs = [records[c['case_id'], method, i] for i in range(3)]
                    row[method+'_cold_ms'] = median(r['cold_ns'] for r in rs)/1e6
                    row[method+'_warm_ms'] = median(median(r['warm_ns']) for r in rs)/1e6
                    row[method+'_build_ms'] = median(r['build_seconds'] for r in rs)*1000
                    row[method+'_reorder_ms'] = median(r['reorder_seconds'] for r in rs)*1000
                    row[method+'_execution_nodes'] = None if method == 'specialized' else median(r['cudd']['execution_dag_nodes'] for r in rs)
                    row[method+'_manager_bytes'] = None if method == 'specialized' else median(r['cudd']['manager_bytes'] for r in rs)
                row['cold_ratio_specialized_over_sift'] = next(p['cold_ratio_specialized_over_bdd_median'] for p in pairs if p['profile'] == profile and p['case_id'] == c['case_id'] and p['method'] == 'sift_once')
                grid.append(row)
    files = dict(all_measurements=measurements, batch_resources=resources, exact_bounds=bounds,
                 structural_absences=absences, paired_case_ratios=pairs, solver_summary=summaries, synthetic_grid=grid)
    for name, rows in files.items(): write_csv(out/(name+'.csv'), rows)
    provenance = dict(run_id=args.run, head=receipt['head'], local_model_execution=False,
        input_files={str(p):sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob('*/*.json'))},
        output_files={p.name:dict(sha256=sha256(p.read_bytes()).hexdigest(), data_rows=len(files[p.stem])) for p in sorted(out.glob('*.csv'))})
    (out/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n', encoding='utf-8')
    (out/'README.md').write_text('# Полные таблицы сравнения CUDD\n\n'+
        '\n'.join(f'- [{name}.csv]({name}.csv): {len(rows)} строк.' for name, rows in files.items())+
        '\n\nОтношение Tспец/TBDD больше единицы означает преимущество BDD. Парные отношения сначала берутся в каждом раунде одного случая, затем медиана трёх; агрегат — медиана этих значений по случаям. Это технические повторы, не новые кампании. CPU и RSS пакета включают загрузку и проверку, время отдельного solve — нет.\n', encoding='utf-8')
    report = ['# CUDD: точная эквивалентность и вычислительная стоимость\n',
        f'11 сентября 2026 года. Дополнение к результату, закреплённому тегом `v1` (`0c83a82`). [Запуск {args.run}](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/{args.run}), источник `{receipt["head"]}`; все четыре задания завершились успешно. [Протокол](../V3_BDD_COMPARISON_V1.md), [компактное подтверждение](../evidence/v3-bdd-comparison-{args.run}/retention.json), [все CSV](../tables/v3-bdd-comparison-{args.run}/README.md).\n',
        'На 761 прикладной модели точные ответы совпали. Специализированный расчёт быстрее построения BDD вместе с первым запросом во всех 761 случаях по медианам технических повторов, для каждой из трёх заранее заданных политик. Относительно основного CUDD с sifting медианное преимущество первого расчёта составляет примерно **10,06 / 4,77 / 8,17 раза** для DeathStarBench / OTel / Petclinic. При повторе тех же запросов с готовой диаграммой CUDD быстрее по медианному парному отношению уже в **1,40 / 1,48 / 1,20 раза**.\n',
        'Это преимущество специализации в режиме небольшого числа неизвестных управляющих координат и разового построения. В приложениях максимум таких неизвестных — 2 / 3 / 2. В искусственной сетке при k=8 и k=10 CUDD с sifting выигрывает также первый расчёт в **1,27 и 5,00 раза**; при k=10 повторный запрос быстрее в **37,84 раза**. Универсального вычислительного превосходства нашего ядра нет. Большая часть затрат первого расчёта CUDD приходится на создание manager и построение; отдельно определять доли этих двух операций по текущему таймеру нельзя. Sifting входит в построение и показан дополнительно, не прибавляется к нему второй раз.\n',
        '## Полнота и точные ответы\n',
        table(['Набор', 'Исходные случаи', 'Модели', 'Точки', 'Интервалы', 'Без модели', 'Первые / повторные расчёты'],
            [[APPS[p],len(d['cases'])+len(d['absent']),len(d['cases']),
              sum(c['estimates']['execution']['prediction'] is not None for c in d['cases']),
              sum(c['estimates']['execution']['prediction'] is None for c in d['cases']),len(d['absent']),
              f'{len(d["records"])} / {len(d["records"])*3}'] for p,d in datasets.items()]),
        'Все 11 функционалов (шесть вариантов и пять совместных контрастов) точно совпали по рациональным границам и статусам с сохранёнными оценками и между решателями. Категориальные экстремумы совпали во всех методах и повторах; каждое неоднозначное свидетельство прошло проверку маски и исходного скалярного предиката. Всего '+str(sum(r['checks']['witnesses_verified'] for d in datasets.values() for r in d['records'])*4)+' проверок свидетельств по измеренным запросам; повторяющиеся проверки не являются независимыми наблюдениями. 39 исходных структурных отсутствий сохранены с причинами. Новых прикладных кампаний — 0.\n',
        '## Первый и повторный расчёт\n',
        'Время — мс, медиана по случаям и трём раундам; повторный запрос сначала представлен медианой трёх запросов с готовой диаграммой. Основной конкурент заранее выбран как sift once. K=Tспец/TBDD: K>1 означает, что BDD быстрее. K — медиана парных отношений, поэтому может отличаться от отношения медиан времени. Все три политики показаны без отбора лучшей.\n',
        table(['Набор','Метод','Моделей','Первый, мс','Повтор, мс','Построение, мс','Sifting, мс','K первый','K повтор'],
            [[APPS[s['profile']],LABELS[s['method']],s['cases'],f'{s["cold_median_ms"]:.4f}',f'{s["warm_median_ms"]:.4f}',
              f'{s["build_median_ms"]:.4f}',f'{s["reorder_median_ms"]:.4f}',
              '—' if s['paired_cold_ratio_median'] is None else f'{s["paired_cold_ratio_median"]:.3f}',
              '—' if s['paired_warm_ratio_median'] is None else f'{s["paired_warm_ratio_median"]:.3f}'] for s in summaries if s['group']=='all']),
        'Для первого расчёта CUDD включены manager, проверка, символическое построение, переупорядочивание, первый запрос и сертификаты. В повторном расчёте включены проверка модели, обработка категорий и сертификаты; разрешён обычный computed cache CUDD, готовые ответы не мемоизируются. Специализированное ядро каждый раз вызывает исходный solve. Загрузка файлов, импорт модулей и независимая проверка результатов находятся вне времени отдельного запроса.\n',
        '## Разделение точек и интервалов\n',
        table(['Набор','Результат E','Моделей','K первый (sift)','K повтор (sift)','Случаев, где BDD быстрее на первом'],
            [[APPS[s['profile']],'Интервал' if s['group']=='ambiguous' else 'Точка',s['cases'],f'{s["paired_cold_ratio_median"]:.3f}',
              f'{s["paired_warm_ratio_median"]:.3f}',s['bdd_cold_faster_cases']] for s in summaries if s['group']!='all' and s['method']=='sift_once']),
        '## CPU, память и полный пакет сохранённых моделей\n',
        'RSS — пик отдельного процесса полного пакета приложения/метода/раунда, медиана трёх процессов. Процесс включает одинаково загруженные входы, импорт нативного модуля также для специализированного метода, все проверки и запись сертификатов. Поэтому эти CPU/wall/RSS нельзя подписывать как ресурсы одной модели или чистого ядра. Сумма первых расчётов ниже включает только измеренные участки всех моделей пакета.\n',
        table(['Набор','Метод','Σ первых, с','Σ повторных, с','Пакет wall, с','Пакет CPU, с','Пик RSS, МиБ'],
            [[APPS[s['profile']],LABELS[s['method']],f'{s["total_cold_median_seconds"]:.4f}',f'{s["total_warm_median_seconds"]:.4f}',
              f'{s["batch_wall_median_seconds"]:.3f}',f'{s["batch_cpu_median_seconds"]:.3f}',f'{s["batch_peak_rss_median_mib"]:.2f}'] for s in summaries if s['group']=='all']),
        'Σ повторных — сумма одной медианы тёплого запроса на каждую модель, а не сумма всех трёх запросов. Для сумм сначала складываются модели одного раунда, затем берётся медиана трёх раундов. Пооперационные wall/CPU, ресурсы всех 48 процессов и точные границы всех функционалов доступны в полных CSV.\n',
        '## Полная искусственная сетка\n',
        'n — узлы, e — связи, r — координаты завершения с входом, k — максимум неизвестных управляющих координат категории, q — категории. Во всех 24 неполных случаях E=[1/5,3/5], в трёх полностью наблюдаемых E=1/16. Время в ячейке: первый / повторный расчёт, мс.\n',
        table(['ID / ось','n/e/r/k/q','Спец.','Controls first','Structural','Sift once','K первый (sift)'],
            [[r['case_id'],f'{r["nodes"]}/{r["edges"]}/{r["completions"]}/{r["max_unknown_controls"]}/{r["categories"]}',
              *[f'{r[m+"_cold_ms"]:.4f} / {r[m+"_warm_ms"]:.4f}' for m in METHODS],f'{r["cold_ratio_specialized_over_sift"]:.3f}'] for r in grid]),
        'Общие gates, две выбираемые реплики, неправильный выбор, нарушение срока, fanout/diamond/cyclic включены согласно протоколу. В строках graph_structure порядок: chain, fanout, diamond, cyclic. Пересечения осей могут повторять модель, но остаются отдельными заранее указанными положениями сетки.\n',
        table(['ID','Построение sift, мс','Sifting, мс','E DAG узлы','Manager, байт'],
            [[r['case_id'],f'{r["sift_once_build_ms"]:.4f}',f'{r["sift_once_reorder_ms"]:.4f}',r['sift_once_execution_nodes'],r['sift_once_manager_bytes']] for r in grid]),
        'Размер DAG — счётчик CUDD с дополненными рёбрами, не число узлов обычной BDD в аналитической оценке B_g+r. Manager bytes — выделенная CUDD память, не пик RSS процесса. Полная таблица всех политик — synthetic_grid.csv.\n',
        '## Среда и пределы вывода\n',
        table(['Набор','CPU','Логических CPU','Python','dd / native'],
            [[APPS[p],next((line.split(':',1)[1].strip() for line in e['cpu_info'].splitlines() if line.startswith('model name')), 'unknown'),
              e['cpu_count'],e['python'].split()[0],str(e['dd_version'])+' / '+str(e['native_version'])] for p,e in environments.items()]),
        'Модели каждого приложения и обе стороны пары измерены на одном runner; разные приложения могут иметь разные CPU. Это конечная инженерная проверка существующих реализаций с Python-обвязкой, а не асимптотическая теорема о всех BDD или всех специализированных алгоритмах. Общий класс ограничен 10 управляющими и 64 всеми координатами; в искусственной сетке максимум 58. Частоты сохранены совместными, в том числе при информативных пропусках. Условия идентификации и критерий события одинаковы.\n',
        'У BDD тоже отсутствует экспоненциальный рост по числу обязательных завершений для данного конъюнктивного предиката. Вывод о преимуществе специализированного сокращения относительно полного перебора сохраняется, но не означает исключительности относительно символических решателей. Основной научный вклад — телеметрия → формальная модель → идентификация и достижимые границы; практическая вычислительная добавка ограничена измеренными режимами.\n',
        'Это сравнение начинается с сохранённой модели. [Полный результат v1 по PMX-конвейеру](V3_PIPELINE_PERFORMANCE_RESULT.md) сохраняет свою отдельную границу «подготовленная телеметрия → проверенные прогнозы». Общий коэффициент ускорения всего конвейера от замены ядра на BDD здесь не измерялся; переносить K из таблицы на весь конвейер нельзя. MAE основной серии не меняется при точном совпадении прогнозов. Исходное отклонение C12 остаётся в силе: этот вычислительный опыт выполнен после открытия исходов и не является новой слепой валидацией.\n']
    path = Path('docs/milestones/V3_BDD_COMPARISON_RESULT.md')
    path.write_text('\n'.join(report), encoding='utf-8')
    print(json.dumps(dict(run_id=args.run, tables={name:len(rows) for name,rows in files.items()}, report=str(path))))


if __name__ == '__main__': main()
