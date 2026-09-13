"""Export complete four-route measurements and already computed forecast metrics."""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from statistics import median

from summarize_completion_target_v1 import read,write,table

ROUTES=('full_e','full_r','projected_r','direct_r')
STAGES=('read_seconds','interpretation_seconds','representation_seconds','frequency_identification_seconds',
        'projection_seconds','first_query_seconds','save_seconds')


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    costs=[];warm=[];operations=[];sources=[];profiles=set();producers=set()
    for file in sorted(args.source.rglob('receipt.json')):
        receipt=read(file);app=receipt['profile'];root=file.parent
        if app in profiles or receipt['status']!='qualified' or receipt['processes']!=36:raise ValueError('profile qualification/census differs')
        profiles.add(app);producers.add((receipt['run'],receipt['head']));config=read(root/'protocol.json')
        timing=read(root/'timings.json')['records']
        expected={(r,m,route)for r,vols in enumerate(config['scale_orders'])for m in vols for route in ROUTES}
        if len(timing)!=36 or {(r['repetition'],r['multiplier'],r['route'])for r in timing}!=expected:raise ValueError('incomplete four-route grid')
        for r in timing:
            if r['status']!='qualified' or r['extra_verification_performed'] is not False:raise ValueError('unqualified timed observation')
            key=dict(application=app,repetition=r['repetition'],multiplier=r['multiplier'],route=r['route'],target=r['target'])
            stages=r['stages'];overhead=r['first_answer_seconds']-sum(stages.values())
            if overhead<0:raise ValueError('stage clocks exceed parent first-answer clock')
            costs.append(dict(key,status=r['status'],position=r['position'],order=r['order'],attempts=r['population'],
                native_span_records=r['native_span_records'],first_answer_seconds=r['first_answer_seconds'],
                first_cpu_seconds=r['first_cpu_seconds'],first_peak_rss_mib=r['first_peak_rss_kib']/1024,
                internal_pipeline_seconds=r['internal_pipeline_seconds'],**stages,startup_dispatch_seconds=overhead,
                source_files_read=r['source_files_read'],models=r['models'],whole_process_seconds=r['process']['wall_seconds'],
                whole_process_resource=r['process']['resource']))
            for op in r['operation_stages']:
                operations.append(dict(key,**op,**r['models'][op['operation']]))
            for q in r['warm_queries']:
                warm.append(dict(key,operation=q['operation'],query_repetition=q['repetition'],nanoseconds=q['nanoseconds']))
        sources.append(dict(run=receipt['run'],head=receipt['head'],profile=app,receipt_sha256=sha256(file.read_bytes()).hexdigest()))
    accuracy_files=list(args.source.rglob('results.json'))
    if len(profiles)!=3 or len(producers)!=1 or len(accuracy_files)!=1:raise ValueError('producer or accuracy census differs')
    accuracy=read(accuracy_files[0])
    if (accuracy['run'],accuracy['head']) not in producers or len(accuracy['census'])!=60:raise ValueError('accuracy source differs')
    summary=[];groups=defaultdict(list)
    for r in costs:groups[r['application'],r['multiplier']].append(r)
    for (app,multiplier),rows in sorted(groups.items()):
        by={(r['route'],r['repetition']):r for r in rows};record=dict(application=app,multiplier=multiplier,attempts=3600*multiplier)
        for route in ROUTES:
            for field in ('first_answer_seconds','first_cpu_seconds','first_peak_rss_mib','native_span_records',*STAGES,'startup_dispatch_seconds'):
                values=[by[route,r][field]for r in range(3)];record[route+'_'+field]=median(values)
                if field=='first_answer_seconds':record.update({route+'_seconds_min':min(values),route+'_seconds_max':max(values)})
            sizes=[v for v in by[route,0]['models'].values()]
            record[route+'_coordinates_total']=sum(v['coordinates']for v in sizes)
            record[route+'_categories_total']=sum(v['categories']for v in sizes)
        for route in ROUTES[:-1]:
            values=[by[route,r]['first_answer_seconds']/by['direct_r',r]['first_answer_seconds']for r in range(3)]
            record.update({route+'_over_direct_r':median(values),route+'_over_direct_r_min':min(values),route+'_over_direct_r_max':max(values)})
        summary.append(record)
    for row in summary:
        base=next(r for r in summary if r['application']==row['application'] and r['multiplier']==1)
        for route in ROUTES:row[route+'_time_growth']=row[route+'_first_answer_seconds']/base[route+'_first_answer_seconds']
    query_groups=defaultdict(list)
    for r in warm:query_groups[r['application'],r['multiplier'],r['route'],r['operation']].append(r['nanoseconds'])
    query_summary=[dict(application=k[0],multiplier=k[1],route=k[2],operation=k[3],queries=len(v),median_ns=median(v),
                        min_ns=min(v),max_ns=max(v))for k,v in sorted(query_groups.items())]
    metrics=[];support=[];contrasts=[]
    for app in accuracy['applications']:
        name=app['application']
        for method in ('E','R'):
            support.append(dict(application=name,method=method,**app['support'][method],common_points=app['common_points'],equal_exact_points=app['equal_exact_points']))
            for scope in ('own','common_point'):
                m=app[scope][method]
                metrics.append(dict(application=name,method=method,scope=scope,status=m['status'],scored_cells=m['scored_cells'],
                    planned_cells=m['planned_cells'],attempts=m['attempts'],**(m['standardized_mean'] or {}),
                    own_support=m['own_support'],per_operation=m['per_operation']))
        contrasts.append(dict(application=name,**app['paired_R_minus_E']))
    for name,rows in [('paired-costs',costs),('cost-summary',summary),('operation-stages',operations),('ready-queries',warm),
        ('ready-query-summary',query_summary),('forecast-pairs',accuracy['census']),('accuracy-summary',metrics),
        ('forecast-support',support),('paired-accuracy',contrasts)]:table(args.out/(name+'.csv'),rows)
    provenance=dict(sources=sources,accuracy_sha256=sha256(accuracy_files[0].read_bytes()).hexdigest(),cost_processes=len(costs),
        ready_queries=len(warm),forecast_pairs=len(accuracy['census']),retrospective=True,new_independent_observations=0,
        local_model_execution=False,Palladio_ratios_multiplied=False)
    write(args.out/'provenance.json',provenance)
    lines=['# Matched E/R identification costs and retrospective forecast accuracy','',
        'All four configurations run on the same runner per application, with warm file cache, fresh processes and paired rounds. First-answer seconds include launch, reading, interpretation, construction, query and saving. Verification occurs after every timed run in a profile. Ratios are paired before taking the median; min/max and all 108 measurements remain in the CSV files. Input copies add no independent observations.','',
        '| Application | Attempts | Full → E, s | Full → R, s | Full → projection → R, s | Direct → R, s | E/direct R | Full R/direct R | Projected R/direct R |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summary:
        fields=[route+'_first_answer_seconds'for route in ROUTES]+[route+'_over_direct_r'for route in ROUTES[:-1]]
        lines.append('| '+' | '.join([r['application'],str(r['attempts']),*[f'{r[k]:.6f}'for k in fields]])+' |')
    lines+=['','The E/direct R column compares different targets. Its interpretation requires the event/bounds and forecast checks. The other two ratios compare routes for exactly the same R. **No ratio here is multiplied by or presented as a new comparison with Palladio.**','',
        '| Application | Attempts | Route | Read, s | Interpret, s | Represent, s | Frequencies, s | Reduce, s | Query, s | Save, s | Startup/dispatch, s | CPU, s | Peak RSS, MiB | Variables | Categories |',
        '| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summary:
        for route in ROUTES:
            fields=(*STAGES,'startup_dispatch_seconds','first_cpu_seconds','first_peak_rss_mib')
            lines.append('| '+' | '.join([r['application'],str(r['attempts']),route,*[f"{r[route+'_'+k]:.6f}"for k in fields],
                str(r[route+'_coordinates_total']),str(r[route+'_categories_total'])])+' |')
    lines+=['','Stage entries are separate medians and need not sum to the median total. Representation is the remainder of instrumented construction, including observation rows and bookkeeping. Ready-model queries are separate in [ready-query-summary.csv](ready-query-summary.csv). All native record counts and per-operation stages are retained.','',
        '| Application | Common points | Equal exact forecasts | E MAE, pp | R MAE, pp | E intervals/refusals | R intervals/refusals |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for app in accuracy['applications']:
        def mae(method):
            m=app['common_point'][method]['standardized_mean'];return f"{m['absolute_error_pp']:.9f}"if m else 'not estimable'
        lines.append('| '+' | '.join([app['application'],str(app['common_points']),str(app['equal_exact_points']),mae('E'),mae('R'),
            *[f"{app['support'][m]['interval']}/{app['support'][m]['refusal']}"for m in ('E','R')]])+' |')
    lines+=['','R probabilities use calibration only; the existing independently checked test success counts are evaluation targets. The original equal-operation/condition aggregation and campaign-cluster contrast routine are unchanged. This is retrospective analysis of already opened test data. Exact equality of forecasts directly preserves their errors on that support; it does not establish equality of E and R on every admissible state or a population equivalence guarantee. Intervals and structural refusals are not replaced by midpoint forecasts.','',
        'Complete tables: [paired costs](paired-costs.csv), [cost summary](cost-summary.csv), [operation stages](operation-stages.csv), [ready queries](ready-queries.csv), [forecast pairs](forecast-pairs.csv), [accuracy](accuracy-summary.csv), [support](forecast-support.csv), [paired accuracy](paired-accuracy.csv), [provenance](provenance.json).','']
    (args.out/'README.md').write_bytes(('\n'.join(lines)).encode())
    print(provenance)


if __name__=='__main__':main()
