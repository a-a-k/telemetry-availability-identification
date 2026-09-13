"""Export complete compact scalar results; never run a model or fit a law."""
import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median


def read(path): return json.loads(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True)+'\n').encode())


def table(path, rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8', newline='') as stream:
        out=csv.DictWriter(stream, fieldnames=fields, lineterminator='\n'); out.writeheader()
        out.writerows({k:json.dumps(v, sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--source', type=Path, required=True); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    coverage=[]; settings=[]; costs=[]; warm=[]; sources=[]; profiles=set(); seen=set()
    for file in sorted(args.source.rglob('receipt.json')):
        receipt=read(file); profile=receipt['profile']; root=file.parent
        if profile in profiles or receipt['status']!='qualified' or receipt['new_independent_observations']!=0:
            raise ValueError('unqualified or duplicate source profile')
        profiles.add(profile); config=read(root/'protocol.json')
        results=read(root/'semantics.json')['cases']; timing=read(root/'timings.json')['records']
        if receipt['cost_processes']!=27 or len(timing)!=27: raise ValueError('timing census differs')
        expected={(r,m,route) for r,vols in enumerate(config['scale_orders']) for m in vols for route in config['routes']}
        if {(r['repetition'],r['multiplier'],r['route']) for r in timing}!=expected: raise ValueError('missing cost position')
        for r in timing:
            if r['status']!='qualified' or r['extra_verification_performed'] is not False: raise ValueError('unqualified measurement')
            key=dict(application=profile, repetition=r['repetition'], multiplier=r['multiplier'], route=r['route'])
            costs.append(dict(key, position=r['position'], order=r['order'], status=r['status'],
                attempts=r['population'], first_answer_seconds=r['first_answer_seconds'], first_cpu_seconds=r['first_cpu_seconds'],
                first_peak_rss_mib=r['first_peak_rss_kib']/1024, internal_pipeline_seconds=r['internal_pipeline_seconds'],
                **r['stages'], whole_process_seconds=r['process']['wall_seconds'], whole_process_resource=r['process']['resource'],
                source_files_read=r['source_files_read'], models=r['models']))
            for q in r['warm_queries']: warm.append(dict(key, operation=q['operation'], query_repetition=q['repetition'], nanoseconds=q['nanoseconds']))
        for case in results:
            identity=case['identity']; phase=case['period']
            for op in case['operations']:
                key=dict(application=profile, law=identity['law'], repetition=identity['repetition'], period=phase, operation=op['operation'])
                unique=tuple(key.values())
                if unique in seen: raise ValueError('duplicate semantic position')
                seen.add(unique)
                coverage.append(dict(key, full_support=op['full_support'], direct_support=op['direct_support'],
                    full_reason=op['full_reason'], direct_reason=op['direct_reason'], full_original_reproduced=op['full_original_reproduced'],
                    same_R_routes_qualified=op.get('same_R_routes_qualified'), **op.get('baseline', {'attempts':op['attempts']})))
                if op['direct_support']:
                    if not op['same_R_routes_qualified']: raise ValueError('unqualified equivalent route')
                    expected_settings={(m,l,i) for m in config['mechanisms'] for l in config['levels'] for i in
                        ('none','selection_and_admission','entry_result','required_completions','all_native')}
                    if phase=='test' and (len(op['settings'])!=90 or {(r['mechanism'],r['missing_fraction'],r['information']) for r in op['settings']}!=expected_settings):
                        raise ValueError('incomplete mask census')
                    settings.extend(dict(key, full_support=op['full_support'], **r) for r in op['settings'])
        sources.append(dict(run=receipt['run'],head=receipt['head'],profile=profile,
                            receipt_sha256=sha256(file.read_bytes()).hexdigest()))
    if len(profiles)!=3 or len(coverage)!=120 or len(costs)!=81: raise ValueError('incomplete application/period census')
    summary=[]; grouped=defaultdict(list)
    for r in costs: grouped[r['application'],r['multiplier']].append(r)
    for (app,multiplier), rows in sorted(grouped.items()):
        by={(r['route'],r['repetition']):r for r in rows}
        record=dict(application=app,multiplier=multiplier,attempts=3600*multiplier)
        for route in ('full','projected','direct'):
            for field in ('first_answer_seconds','first_cpu_seconds','first_peak_rss_mib','internal_pipeline_seconds','build_seconds','projection_seconds','first_query_seconds','read_seconds','save_seconds'):
                values=[by[route,r][field] for r in range(3)]
                record[route+'_'+field]=median(values)
                if field=='first_answer_seconds':
                    record[route+'_seconds_min']=min(values); record[route+'_seconds_max']=max(values)
        for route in ('full','projected'):
            ratios=[by[route,r]['first_answer_seconds']/by['direct',r]['first_answer_seconds'] for r in range(3)]
            record[route+'_over_direct']=median(ratios)
            record[route+'_over_direct_min']=min(ratios);record[route+'_over_direct_max']=max(ratios)
        summary.append(record)
    for row in summary:
        base=next(r for r in summary if r['application']==row['application'] and r['multiplier']==1)
        for route in ('full','projected','direct'):
            row[route+'_time_growth']=row[route+'_first_answer_seconds']/base[route+'_first_answer_seconds']
            row[route+'_memory_growth']=row[route+'_first_peak_rss_mib']/base[route+'_first_peak_rss_mib']
    query_groups=defaultdict(list)
    for r in warm: query_groups[r['application'],r['multiplier'],r['route'],r['operation']].append(r['nanoseconds'])
    query_summary=[dict(application=k[0],multiplier=k[1],route=k[2],operation=k[3],queries=len(v),
                        median_ns=median(v),min_ns=min(v),max_ns=max(v)) for k,v in sorted(query_groups.items())]
    baseline=[]
    for app in sorted(profiles):
        for period in ('calibration','test'):
            rows=[r for r in coverage if r['application']==app and r['period']==period]
            both=[r for r in rows if r['full_support'] and r['direct_support']]
            direct=[r for r in rows if r['direct_support']]
            out=dict(application=app,period=period,positions=len(rows),full_supported=len(both),direct_supported=len(direct),
                     attempts=sum(r['attempts'] for r in rows), common_attempts=sum(r['attempts'] for r in both),
                     direct_attempts=sum(r['attempts'] for r in direct))
            fields={k for r in both for k in r if k.endswith(('_count','_attempts','_excluded')) or k in
                    ('equivalent_for_all_states','different_for_all_states','event_difference_undecided','same_marginal_bounds_but_possible_difference')}
            for name in sorted(fields): out['common_'+name]=sum(r.get(name,0) for r in both)
            for name in ('R_lower_count','R_upper_count','R_point_attempts','R_success_excluded','R_failure_excluded'):
                out['direct_'+name]=sum(r.get(name,0) for r in direct) if direct and (period=='test' or not name.endswith('excluded')) else None
            baseline.append(out)
    for name, rows in [('operation-baseline',coverage),('all-mask-settings',settings),('paired-costs',costs),
                       ('cost-summary',summary),('ready-queries',warm),('ready-query-summary',query_summary),('application-baseline',baseline)]:
        table(args.out/(name+'.csv'),rows)
    provenance=dict(sources=sources,operation_positions=len(coverage),mask_settings=len(settings),cost_processes=len(costs),
                    ready_queries=len(warm),local_model_execution=False)
    write(args.out/'provenance.json',provenance)
    lines=['# Completion/deadline target: identification, joint differences and costs','',
           'All 120 planned calibration/test positions are retained. E versus R tests sufficiency; the three R routes must agree on common support. See operation-baseline.csv and all-mask-settings.csv for all bounds, support and external checks.', '',
           'Costs below are median first-answer seconds over three paired rounds. Full/direct ratios are formed within each round before aggregation. All routes compute R with relevant-coordinate optimization; process start, input decoding, construction and saved first answers are included. Repeated ready-model queries are separate. Source telemetry export and archive verification are outside the boundary. Copies add no independent observations.', '',
           '| Application | Attempts | Full → R, s | Full → projection → R, s | Direct → R, s | Full/direct | Projected/direct |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for r in summary:
        lines.append('| '+ ' | '.join([r['application'],str(r['attempts']),*[f"{r[k]:.6f}" for k in
            ('full_first_answer_seconds','projected_first_answer_seconds','direct_first_answer_seconds','full_over_direct','projected_over_direct')]])+' |')
    lines+=['','Every one of the 81 process observations, all stages and first-answer CPU/RSS are in [paired-costs.csv](paired-costs.csv). [cost-summary.csv](cost-summary.csv) includes ranges and volume growth; [ready-query-summary.csv](ready-query-summary.csv) reports every operation and route.', '',
            'Masking uses identical attempt/primitive-coordinate keys for both routes, before completion aggregation. The native-failure-associated mask uses observed completion failures, not external Y; it is explicitly distinct from the earlier Y-associated mechanism. State masks keep the declared group vocabulary and deadline observations fixed. Additional topology discovery from deleted traces is outside this experiment.','']
    (args.out/'README.md').write_bytes(('\n'.join(lines)).encode())
    print(json.dumps(provenance))


if __name__=='__main__':main()
