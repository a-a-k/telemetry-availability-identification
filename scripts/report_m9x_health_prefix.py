"""Aggregate-only correction of opened M9X scores; no PMX/model/raw execution."""
from collections import defaultdict
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
from statistics import mean
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'docs/evidence/m9x-34196680992'
SOURCE=ROOT/'docs/evidence/health-prefix-rescore-34220234444'
OUT=ROOT/'docs/evidence/m9x-health-prefix-34220234444'
METHODS=('proposed','B2','B0','endpoint_all','PMX_inclusive','PMX_conditional_local')
FIELDS=('profile','failure_law','repetition','mode','scope','source_placement','target_placement','method','operation')


def key(row):return tuple(str(row[k]) for k in FIELDS)
def cell(row):return row['profile'],row['source_placement'],row['operation']
def finite(row):return row['prediction'] not in ('',None)
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(name,value):(OUT/name).write_bytes((json.dumps(value,indent=2)+'\n').encode())
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])+'\n'


def score(predictions,observations):
    result=[]
    for row in predictions:
        if not finite(row):continue
        for view in ('all_sequence','stable','stable_block_sensitivity'):
            ref=observations[(cell(row),view)]
            p=float(row['prediction']);n=int(ref['test_requests']);s=int(ref['test_successes']);q=s/n
            result.append(dict(**{k:row[k] for k in FIELDS},view=view,prediction=p,test_requests=n,test_successes=s,
                absolute_prediction_error=abs(p-q),signed_prediction_error=p-q,
                brier_score=(s*(1-p)**2+(n-s)*p*p)/n))
    return result


def aggregate(scores):
    groups=defaultdict(list)
    for row in scores:groups[(row['mode'],row['view'],row['method'])].append(row)
    return [dict(mode=mode,view=view,method=method,available_operation_cells=len(values),expected_operation_cells=12,
                 mae_pp=100*mean(r['absolute_prediction_error'] for r in values),
                 bias_pp=100*mean(r['signed_prediction_error'] for r in values),brier=mean(r['brier_score'] for r in values))
            for (mode,view,method),values in sorted(groups.items())]


def paired(scores):
    result=[]
    for view in ('all_sequence','stable','stable_block_sensitivity'):
        for profile in ('deathstarbench_social_network','opentelemetry_demo'):
            for pmx in ('PMX_inclusive','PMX_conditional_local'):
                for method in ('proposed','B2','B0','endpoint_all'):
                    def select(name):return {cell(r):r for r in scores if r['view']==view and r['mode']=='full' and r['profile']==profile and r['method']==name}
                    a,b=select(method),select(pmx);common=set(a)&set(b)
                    result.append(dict(view=view,profile=profile,pmx=pmx,comparator=method,common_cells=len(common),
                         expected_cells=6,mae_difference_pp=100*mean(a[k]['absolute_prediction_error']-b[k]['absolute_prediction_error'] for k in common) if common else None,
                         brier_difference=mean(a[k]['brier_score']-b[k]['brier_score'] for k in common) if common else None))
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    report=load(SOURCE/'rescore.json');assert report['qualified'] and report['historical_score_max_error']==0
    record=next(x for x in load(SOURCE/'verified-archives.json') if x['role']=='tables')
    raw=(SOURCE/'tables.zip').read_bytes();assert len(raw)==record['bytes'] and sha256(raw).hexdigest()==record['sha256']
    original=load(OLD/'candidate-predictions.json');old_scores=load(OLD/'scores.json')
    manifest=load(OLD/'candidate-manifest.json');assert manifest['prediction_file_sha256']==sha256((OLD/'candidate-predictions.json').read_bytes()).hexdigest()
    old_summary=load(OLD/'development-summary.json');assert old_summary['scores_sha256']==sha256((OLD/'scores.json').read_bytes()).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        def member(name):
            data=z.read(name);assert sha256(data).hexdigest()==report['files'][name]['sha256'];return data
        accepted=json.loads(member('accepted-predictions.json'));lookup={key(r):r for r in accepted}
        corrected=[dict(lookup[key(r)]) if r['method'] in ('proposed','B2','B0') else dict(r) for r in original]
        for row in corrected:
            if finite(row):row['prediction']=float(row['prediction'])
        assert len(corrected)==len(original)==108
        assert [r for r in corrected if r['method'].startswith('PMX_')]==[r for r in original if r['method'].startswith('PMX_')]
        assert [r for r in corrected if r['method']=='endpoint_all']==[r for r in original if r['method']=='endpoint_all']
        windows={}
        for version in ('historical','prefix_corrected'):
            name=f'historical-predictions__{version}-windows/scores.csv'
            rows=csv.DictReader(io.StringIO(member(name).decode('utf-8-sig')))
            selected=[r for r in rows if r['failure_law']=='NCD' and r['repetition']=='0' and r['scope']=='current' and r['mode']=='full' and r['method']=='B0']
            assert len(selected)==36
            windows[version]={(cell(r),r['view']):r for r in selected}
    old_lookup={(key(r),r['view']):r for r in old_scores};assert len(old_lookup)==222
    checks=[];records=[]
    for pv,predictions in (('historical',original),('prefix_corrected',corrected)):
        for wv,observations in windows.items():
            scores=score(predictions,observations)
            if pv==wv=='historical':
                assert len(scores)==222
                for row in scores:
                    previous=old_lookup[(key(row),row['view'])]
                    assert row['test_requests']==previous['test_requests'] and row['test_successes']==previous['test_successes']
                    for field in ('absolute_prediction_error','signed_prediction_error','brier_score'):
                        checks.append(abs(row[field]-previous[field]))
                assert max(checks)<1e-12
            result=dict(prediction_version=pv,window_version=wv,candidate_slots=108,scored_rows=len(scores),
                 all_sequence_attempts=sum(int(r['test_requests']) for (c,v),r in observations.items() if v=='all_sequence'),
                 stable_attempts=sum(int(r['test_requests']) for (c,v),r in observations.items() if v=='stable'),
                 aggregates=aggregate(scores),paired=paired(scores))
            assert result['all_sequence_attempts']==14400
            save(pv+'-predictions__'+wv+'-windows-scores.json',scores);records.append(result)
    save('candidate-predictions.json',corrected)
    save('correction.json',dict(version='m9x-health-prefix-correction-v1',source_rescore_run=34220234444,
         scope='same four opened NCD/r0 campaigns, twelve operation cells',main_campaigns=0,new_independent_campaigns=0,
         new_pmx_invocations=0,new_model_fits=0,pmx_candidate_objects_unchanged=24,endpoint_all_objects_unchanged=12,
         original_score_reproduction_max_error=max(checks),source_tables_sha256=record['sha256'],records=records))
    historical=records[0];final=records[-1]
    output='# M9X: исправление health decoder на прежних четырёх кампаниях\n\n'
    output+='Старые таблицы сохранены. Новая версия использует исправленные M7 forecasts и общий исправленный stable mask. PMX forecasts и endpoint_all неизменны. Это описательное сравнение development data; новых PMX runs, кампаний и доверительных интервалов нет.\n\n'
    old_ag={(r['mode'],r['view'],r['method']):r for r in historical['aggregates']}
    values=[]
    for r in final['aggregates']:
        if r['mode']!='full' or r['view'] not in ('all_sequence','stable'):continue
        a=old_ag[(r['mode'],r['view'],r['method'])]
        values.append([r['view'],r['method'],str(r['available_operation_cells'])+'/12',f"{a['mae_pp']:.6f}",f"{r['mae_pp']:.6f}",f"{r['mae_pp']-a['mae_pp']:+.6f}"])
    output+=table(['View','Метод','Охват','Прежняя MAE, pp','Исправленная MAE, pp','Изменение, pp'],values)
    output+='\nПарные ΔMAE = comparator − PMX на строго общем охвате; отрицательное значение означает меньшую MAE comparator только на этом подмножестве. Пустой охват не оценивается.\n\n'
    output+=table(['View','Приложение','PMX','Comparator','Общий охват','ΔMAE, pp'],[
        [r['view'],r['profile'],r['pmx'],r['comparator'],str(r['common_cells'])+'/6','—' if r['mae_difference_pp'] is None else f"{r['mae_difference_pp']:+.6f}"]
        for r in final['paired'] if r['view'] in ('all_sequence','stable')])
    output+=f"\nВсе test attempts: {final['all_sequence_attempts']}; stable: {historical['stable_attempts']} → {final['stable_attempts']}. PMX inclusive own coverage 12/12, conditional 6/12; причин улучшения и основного преимущества это не устанавливает.\n"
    (OUT/'tables.md').write_bytes(output.encode())
    print(json.dumps(dict(historical_reproduction_error=max(checks),all_attempts=final['all_sequence_attempts'],stable_before=historical['stable_attempts'],stable_after=final['stable_attempts'],full_all_sequence=[r for r in final['aggregates'] if r['mode']=='full' and r['view']=='all_sequence']),indent=2))


if __name__=='__main__':main()
