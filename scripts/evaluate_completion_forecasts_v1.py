"""Retrospective R/E forecast errors on the unchanged calibration/test split."""
from copy import deepcopy
import csv
from fractions import Fraction
import json
import os
from pathlib import Path
from types import FunctionType

import retain_v3_comparison_compact_v4 as transport
from benchmark_v3_pipeline_v1 import read,write
from telemetry_availability import v3_campaign_analysis_v1 as original
from telemetry_availability.v3_primary_projection import sha

CONFIG=Path('configs/v5_completion_followup_v1.json')
OUT=Path('workflow-results/completion-accuracy')


def forecast(lo,hi,supported,reason=None):
    if not supported:return dict(status='unsupported',reason=reason or 'structural_refusal',probability=None,kind='refusal')
    lo,hi=Fraction(lo),Fraction(hi)
    return dict(status='ok' if lo==hi else 'unsupported',kind='point' if lo==hi else 'interval',
                reason=None if lo==hi else 'not_point_identified_under_declared_observation_law',
                probability=float(lo) if lo==hi else None,lower_exact=str(lo),upper_exact=str(hi),
                identified_lower=float(lo),identified_upper=float(hi))


def paired(rows,operations,strata,seed):
    # Explicit parameter adapter for the original fixed left name, without
    # inventing G0/PMX slots or changing any original stored forecast.
    scope=dict(original.paired_primary.__globals__)
    scope['scored']=lambda row,op,method: original.scored(row,op,'R' if method=='Gstar' else method)
    routine=FunctionType(original.paired_primary.__code__,scope,original.paired_primary.__name__,original.paired_primary.__defaults__)
    result=routine(rows,operations,'E',strata,seed)
    result['left']='R';result['left_target_adapter']='original Gstar parameter name maps only to R in this separate comparison'
    return result


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('statistical reanalysis is remote only')
    config=read(CONFIG)
    for name,digest in config['source_locks'].items():
        if sha(Path(name))!=digest:raise ValueError('fixed accuracy source changed: '+name)
    src=config['R_source'];run=transport.read_api(f"actions/runs/{src['run']}")
    if run['head_sha']!=src['head'] or run['status']!='completed' or run['conclusion']!='success' or run['run_attempt']!=1:
        raise ValueError('qualified R source differs')
    artifacts=transport.collect_pages(f"actions/runs/{src['run']}/artifacts",'artifacts');by={a['name']:a for a in artifacts}
    input_rows=[];source_records=[]
    for profile in config['applications']:
        expected=next(a for a in src['artifacts'] if a['name']==f"v5-completion-compact-{profile}-{src['run']}")
        a=by[expected['name']]
        if any(a[k]!=v for k,v in expected.items()):raise ValueError('R compact digest changed')
        files=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,
            {'protocol.json','environment.json','timings.json','semantics.json','receipt.json'})
        receipt=json.loads(files['receipt.json'])
        if receipt['status']!='qualified' or receipt['head']!=src['head'] or receipt['profile']!=profile:raise ValueError('R calibration unqualified')
        input_rows.extend(json.loads(files['semantics.json'])['cases']);source_records.append(expected)
    with Path(config['forecast_census']).open(encoding='utf-8',newline='') as stream:old=list(csv.DictReader(stream))
    index={}
    for r in old:
        if r['method'] not in ('B0','Gstar'):continue
        key=(r['application'],r['law'],int(r['repetition']),r['operation'],r['method'])
        if key in index or r['placement']!='split' or r['evaluator_status']!='qualified':raise ValueError('forecast source identity differs')
        index[key]=r
    if len(index)!=120:raise ValueError('original 60-cell pair census differs')
    campaigns=[];census=[]
    for case in input_rows:
        if case['period']!='calibration':continue
        identity=case['identity'];app=identity['application'];law=identity['law'];rep=identity['repetition']
        cid='/'.join(str(identity[k]) for k in ('namespace','application','placement','law','repetition'))
        row=dict(application=app,placement='split',law=law,repetition=rep,campaign_id=cid,
                 evaluator_status='qualified',view='all_sequence',operations={})
        for op in case['operations']:
            name=op['operation'];key=(app,law,rep,name)
            original_e=json.loads(index[(*key,'Gstar')]['forecast'])
            test=json.loads(index[(*key,'B0')]['metrics'])
            if test['attempts']!=op['attempts'] or not 0<=test['successes']<=test['attempts']:raise ValueError('original test count differs')
            r=op.get('R',{})
            R=forecast(r.get('lower_exact'),r.get('upper_exact'),op['direct_support'],op['direct_reason'])
            b=op.get('baseline',{})
            E=forecast(b.get('E_lower_exact'),b.get('E_upper_exact'),op['full_support'],op['full_reason'])
            if E['status']!=original_e['status']:raise ValueError('frozen E point support changed')
            if E['kind']=='point':
                if Fraction(E['lower_exact'])!=Fraction(original_e['exact_fraction']):raise ValueError('frozen E forecast changed')
            elif E['kind']=='interval':
                if (E['lower_exact'],E['upper_exact'])!=(original_e['lower_exact'],original_e['upper_exact']):raise ValueError('frozen E bounds changed')
            row['operations'][name]=dict(attempts=test['attempts'],successes=test['successes'],forecasts={'E':E,'R':R})
            common=E['kind']==R['kind']=='point'
            census.append(dict(application=app,law=law,repetition=rep,campaign_id=cid,operation=name,
                test_attempts=test['attempts'],test_successes=test['successes'],E=E,R=R,common_point=common,
                equal_exact_point_forecasts=Fraction(E['lower_exact'])==Fraction(R['lower_exact']) if common else None,
                E_metrics=original.scored(row,name,'E'),R_metrics=original.scored(row,name,'R')))
        campaigns.append(row)
    if len(campaigns)!=18 or len(census)!=60:raise ValueError('new forecast comparison census incomplete')
    strata=[('split','N'),('split','NC')];applications=[]
    for i,(app,operations) in enumerate(config['applications'].items()):
        rows=[r for r in campaigns if r['application']==app]
        common=deepcopy(rows)
        for r in common:
            for op in r['operations'].values():
                if any(f['kind']!='point' for f in op['forecasts'].values()):
                    for method in ('E','R'):op['forecasts'][method]=dict(status='unsupported',probability=None,reason='outside_common_point_support')
        slots=[r for r in census if r['application']==app]
        applications.append(dict(application=app,own={m:original.own_metrics(rows,operations,m,strata) for m in ('E','R')},
            common_point={m:original.own_metrics(common,operations,m,strata)for m in ('E','R')},
            support={m:{kind:sum(r[m]['kind']==kind for r in slots)for kind in ('point','interval','refusal')}for m in ('E','R')},
            paired_R_minus_E=paired(rows,operations,strata,config['bootstrap_seeds'][i]),
            common_points=sum(r['common_point']for r in slots),equal_exact_points=sum(r['equal_exact_point_forecasts'] is True for r in slots)))
    write(OUT/'results.json',dict(version='v5-completion-retrospective-forecast-comparison-v1',applications=applications,
        census=census,retrospective=True,new_independent_observations=0,R_rules_changed_after_error_computation=False,
        input_campaigns=campaigns,source_artifacts=source_records,source_forecast_census_sha256=sha(Path(config['forecast_census'])),
        R_source=src,run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],config_sha256=sha(CONFIG)))
    print('Retained all 60 retrospective E/R forecast pairs.')


if __name__=='__main__':main()
