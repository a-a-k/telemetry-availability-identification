"""Reproduce aggregate-only M9X report tables; no native parsing or model fitting."""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import mean
import zipfile

ROOT = Path(__file__).resolve().parents[1]
E = ROOT/'docs/evidence/m9x-34196680992'
METHODS = ('proposed', 'B2', 'B0', 'endpoint_all', 'PMX_inclusive', 'PMX_conditional_local')


def read(name):
    return json.loads((E/name).read_text())


def sha(name):
    return hashlib.sha256((E/name).read_bytes()).hexdigest()


def key(row):
    return row['profile'], row['source_placement'], row['operation']


def app(profile):
    return 'DeathStar' if profile == 'deathstarbench_social_network' else 'OTel'


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join('---' for _ in headers)+' |']+
                     ['| '+' | '.join(map(str, row))+' |' for row in rows])+'\n'


def resource(text):
    wall = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:.]+)', text).group(1)
    seconds = 0.0
    for part in wall.split(':'):
        seconds = 60*seconds+float(part)
    return dict(wall_seconds=seconds, peak_rss_kib=int(re.search(r'Maximum resident set size \(kbytes\): (\d+)',text).group(1)))


def main():
    manifest, summary = read('candidate-manifest.json'), read('development-summary.json')
    assert manifest['prediction_file_sha256'] == sha('candidate-predictions.json')
    assert manifest['coverage_file_sha256'] == sha('coverage-census.json')
    assert manifest['context_control_census_sha256'] == sha('context-control-census.json')
    assert summary['candidate_manifest_sha256'] == sha('candidate-manifest.json')
    assert summary['scores_sha256'] == sha('scores.json')
    api = read('artifact-api.json')['artifacts']
    for stem, artifact in [('candidates','candidates'),('evaluation','development-evaluation'),('solver','solver'),('prepare-resources','prepare-resources')]:
        info = next(r for r in api if r['name'] == f'm9x-{artifact}-34196680992')
        assert 'sha256:'+sha(stem+'.zip') == info['digest'] and (E/(stem+'.zip')).stat().st_size == info['size_in_bytes']
        with zipfile.ZipFile(E/(stem+'.zip')) as archive:
            for name in archive.namelist():
                if (E/name).exists(): assert (E/name).read_bytes() == archive.read(name)
    with zipfile.ZipFile(E/'retained-history/m9v-original-candidates.zip') as archive:
        original = json.loads(archive.read('candidate-predictions.json'))
    predictions, scores, coverage, raw = read('candidate-predictions.json'), read('scores.json'), read('coverage-census.json'), read('raw-result.json')['runs']
    assert [r for r in predictions if not r['method'].startswith('PMX_')] == [r for r in original if not r['method'].startswith('PMX_')]
    assert len(predictions) == 108 and len(coverage) == 24 and len(raw) == 46
    assert len({(key(r),r['method'],r['mode']) for r in predictions}) == 108
    assert len({(r['model_id'],r['repetition']) for r in raw}) == 46
    for model_id in {r['model_id'] for r in raw}:
        repeated = [r for r in raw if r['model_id'] == model_id]
        assert {r['repetition'] for r in repeated} == {0,1}
        if model_id.startswith('00-control--'):
            assert all(r['status']=='error' and r['error_type']=='java.lang.StackOverflowError' for r in repeated)
            continue
        for r in repeated:
            p=r['success_probability']
            assert r['status']=='solved' and math.isfinite(p) and 0 <= p <= 1
            assert abs(p+r['failure_probability_sum']-1) < 1e-12
            assert abs(r['physical_state_probability']-1) < 1e-12
            assert r['evaluated_physical_states']==r['total_physical_states']==1
        assert abs(repeated[0]['success_probability']-repeated[1]['success_probability']) < 1e-12
    controls=read('context-control-census.json')
    assert controls['qualified'] and controls['oracle_passes']==8
    assert all(abs(r['success_probability']-r['expected_success']) < 1e-12 for r in controls['rows'])
    for row in scores:
        p, n, successes = row['prediction'], row['test_requests'], row['test_successes']
        q = successes/n
        assert abs(q-row['test_success_fraction']) < 1e-12
        assert abs(p-q-row['signed_prediction_error']) < 1e-12
        assert abs(abs(p-q)-row['absolute_prediction_error']) < 1e-12
        assert abs((successes*(1-p)**2+(n-successes)*p*p)/n-row['brier_score']) < 1e-12
    for aggregate in summary['aggregates']:
        selected=[r for r in scores if all(r[k]==aggregate[k] for k in ('method','mode','view'))]
        assert len(selected)==aggregate['available_operation_cells']
        for field in ('prediction','signed_prediction_error','absolute_prediction_error','brier_score','test_success_fraction'):
            assert abs(mean(r[field] for r in selected)-aggregate[field]) < 1e-12
    full = [r for r in scores if r['view']=='all_sequence' and r['mode']=='full']
    universe = {key(r): r for r in full if r['method']=='B0'}
    assert len(universe) == 12 and all(r['test_requests']==1200 for r in universe.values())
    lookup = {(key(r),r['method']):r for r in predictions if r['mode']=='full'}
    census = []
    for k, observed in sorted(universe.items()):
        row=[app(k[0]), k[1], k[2], f"{observed['test_success_fraction']:.6f}"]
        for method in METHODS:
            p=lookup[(k,method)]['prediction']
            row.append('—' if p=='' else f'{p:.6f}')
        census.append(row)
    output = '# M9X: воспроизводимые численные таблицы\n\n'
    output += 'Только четыре сохранённые M7 NCD/r0 кампании, 12 operation cells, 14 400 test requests. Прогнозы — вероятности; ошибки — процентные пункты. «—» означает сохранённое отсутствие прогноза.\n\n'
    output += table(['Приложение','Placement','Операция','Наблюдение','proposed','B2','B0','endpoint_all','PMX inclusive','PMX conditional'],census)
    output += '\nПолный census текущих случаев: предложенный метод и B2 5/12, B0/endpoint_all/PMX inclusive 12/12, PMX conditional 6/12. Условный PMX не поддерживает все шесть OTel случаев из-за swallowed-child/positivity guards; proposed/B2 имеют семь topology_ambiguous_target_fraction. Все причины присутствуют в candidate-predictions/coverage-census.\n\n'
    output += '## Ошибки и охват\n\nСредние вычислены только на выданных прогнозах данного метода; строки с разным охватом нельзя использовать как общий рейтинг.\n\n'
    aggregates = []
    for row in summary['aggregates']:
        if row['mode'] != 'full' or row['view'] not in ('all_sequence','stable'): continue
        aggregates.append([row['view'],row['method'],f"{row['available_operation_cells']}/12",
            f"{100*row['signed_prediction_error']:+.4f}",f"{100*row['absolute_prediction_error']:.4f}",f"{row['brier_score']:.8f}"])
    output += table(['View','Метод','Охват','Bias, п.п.','MAE, п.п.','Brier'],aggregates)
    output += '\n## Парные сравнения на общем охвате\n\nЗнак — comparator минус PMX. Каждая строка использует строго одни operation cells; это описательные контрасты открытых данных без CI или нового подтверждающего теста. По одному повтору на placement/NCD не даёт оценки вариации между повторами будущей серии.\n\n'
    pairs=[]
    for profile in sorted({k[0] for k in universe}):
        for pmx in ('PMX_inclusive','PMX_conditional_local'):
            for comparator in ('proposed','B2','B0','endpoint_all'):
                a={key(r):r for r in full if r['profile']==profile and r['method']==pmx}
                b={key(r):r for r in full if r['profile']==profile and r['method']==comparator}
                common=sorted(set(a)&set(b))
                delta=mean(b[k]['absolute_prediction_error']-a[k]['absolute_prediction_error'] for k in common) if common else None
                brier=mean(b[k]['brier_score']-a[k]['brier_score'] for k in common) if common else None
                pairs.append(dict(profile=profile,pmx=pmx,comparator=comparator,common_cells=len(common),
                                  expected_cells=6,mae_difference_pp=None if delta is None else 100*delta,brier_difference=brier))
    output += table(['Приложение','PMX','Comparator','Общий охват','ΔMAE, п.п.','ΔBrier'],[
        [app(r['profile']),r['pmx'],r['comparator'],f"{r['common_cells']}/6",'—' if r['mae_difference_pp'] is None else f"{r['mae_difference_pp']:+.4f}",
         '—' if r['brier_difference'] is None else f"{r['brier_difference']:+.8f}"] for r in pairs])
    with zipfile.ZipFile(E/'archive-audit.zip') as archive:
        meta={Path(n).name:json.loads(archive.read(n)) for n in archive.namelist() if n.startswith('metadata/')}
    source = meta['m9x-application-input-34196680992.json']['application-input-contract.json']
    contract = meta['m9x-solver-contract-34196680992.json']['solver-contract.json']
    context=[]
    for sample in source['samples']:
        for case in sample['cases']:
            s=case['summary']
            assert all(s[k] for k in ('all_non_identity_envelope_fields_preserved','context_operation_graph_acyclic','context_edges_strictly_increase_depth'))
            context.append([case['case_id'],s['base_operations'],s['context_operations'],s['projected_requests'],s['projected_spans'],f"{case['context_projection_seconds']:.4f}"])
    output += '\n## Контекст и точная реконструкция\n\n'+table(['Случай','Исходные операции','Контексты','Запросы','Spans с wrapper','Контекст, с'],context)
    pmx_cost=[]
    for record in contract['extractions']:
        filename='m9x-extraction-'+record['sample_key']+'-34196680992.json'
        for case in record['cases']:
            assert case['qualified'] and all(case['checks'].values())
            r=case['reconstruction']
            assert r['exact_trace_span_operation_parent_inventory'] and not r['unresolved_reconstructed_records']
            resources=resource(meta[filename]['raw/'+case['case_id']+'/resource-usage.txt'])
            pmx_cost.append(dict(case_id=case['case_id'],control=case['control'],**resources))
    build=resource(meta['m9x-solver-34196680992.json']['runtime/build-resource-usage.txt'])
    solve=resource(meta['m9x-solver-34196680992.json']['runtime/solve-resource-usage.txt'])
    prepare=resource((E/'m9x-prepare-resources.txt').read_text())
    app_cost=[r for r in pmx_cost if not r['control']]
    controls_cost=[r for r in pmx_cost if r['control']]
    run=read('run-api.json')
    job_seconds={j['name']:(datetime.fromisoformat(j['completedAt'])-datetime.fromisoformat(j['startedAt'])).total_seconds() for j in run['jobs']}
    costs=dict(prepare=prepare,pmx_invocations=pmx_cost,cold_analyzer_build=build,solver_full_process=solve,
        per_model_load_solve_seconds=[dict(model_id=r['model_id'],repetition=r['repetition'],status=r['status'],seconds=r['load_solve_elapsed_nanoseconds']/1e9) for r in raw],
        context_projection_seconds=sum(c['context_projection_seconds'] for s in source['samples'] for c in s['cases']),
        original_m9v_native_parse_seconds=sum(s['native_parse_seconds'] for s in source['samples']),
        original_m9v_native_bytes=sum(s['native_file_bytes'] for s in source['samples']),
        bridge_seconds=sum(m['bridge_seconds'] for m in contract['models']),job_seconds=job_seconds,
        new_original_method_fits=0,original_method_fit_time='not separately exported in compact contract; unknown',
        engineering_person_minutes='not measured',monitoring_overhead='not measured',
        archived_zip_bytes=sum(r['size_in_bytes'] for r in api))
    output += '\n## Стоимость\n\nПолное время wall и peak RSS относятся к явно названному процессу; суммы последовательных стадий не равны времени параллельного workflow. Общий сбор M7 не повторялся и не приписан каждому методу.\n\n'
    output += table(['Стадия','Wall, с','Peak RSS, KiB'],[
        ['M9X prepare, включая проверку/чтение сохранённых входов',f"{prepare['wall_seconds']:.2f}",prepare['peak_rss_kib']],
        ['12 прикладных PMX invocations, сумма / max RSS',f"{sum(r['wall_seconds'] for r in app_cost):.2f}",max(r['peak_rss_kib'] for r in app_cost)],
        ['3 искусственных PMX invocations, сумма / max RSS',f"{sum(r['wall_seconds'] for r in controls_cost):.2f}",max(r['peak_rss_kib'] for r in controls_cost)],
        ['Холодная сборка Palladio',f"{build['wall_seconds']:.2f}",build['peak_rss_kib']],
        ['Solver JVM/Maven, все 46 записей',f"{solve['wall_seconds']:.2f}",solve['peak_rss_kib']]])
    output += f"\nКонтекстная проекция 12 случаев: {costs['context_projection_seconds']:.4f} с. Bridge 23 моделей: {costs['bridge_seconds']:.4f} с. Сумма job wall: {sum(job_seconds.values()):.0f} с. Все 11 ZIP: {costs['archived_zip_bytes']:,} байт.\n"
    output += '\nПоказываются отдельно startup PMX (20 с на вызов), build, process wall и каждый load/solve в costs.json. Новых fits предложенного метода нет, но это не нулевая стоимость его первоначального fit: раздельное время последнего здесь не выгружено. Человеко-минуты интеграции, отдельный monitoring overhead и масштабирование не измерены.\n'
    (E/'tables.md').write_text(output,encoding='utf-8',newline='\n')
    (E/'paired-summary.json').write_text(json.dumps(pairs,indent=2)+'\n',newline='\n')
    (E/'costs.json').write_text(json.dumps(costs,indent=2)+'\n',newline='\n')
    verification=dict(score_arithmetic_rows=len(scores),non_pmx_predictions_unchanged=84,
        candidate_rows=len(predictions),application_pmx_slots=len(coverage),qualified_pmx=sum(r['valid_prediction'] for r in coverage),
        solver_records=len(raw),all_operation_cells=len(universe),all_test_requests=sum(r['test_requests'] for r in universe.values()),
        counts=dict(Counter(r['status'] for r in raw)),source_run=34196680992,
        reports={name:sha(name) for name in ('tables.md','paired-summary.json','costs.json')})
    (E/'report-verification.json').write_text(json.dumps(verification,indent=2)+'\n',newline='\n')
    print(json.dumps(verification,indent=2))


if __name__ == '__main__':
    main()
