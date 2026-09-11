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


def original_accounting():
    """Disjoint recorded commands in the original full 240-campaign execution."""
    root=Path('docs/tables/v3-main-recovered-34517752889/cost-scopes')
    with (root/'process-resources.csv').open(encoding='utf-8',newline='') as f:processes=list(csv.DictReader(f))
    with (root/'stage-observations.csv').open(encoding='utf-8',newline='') as f:stages=list(csv.DictReader(f))
    with Path('docs/evidence/v3-main-durable-archive-34516536673/pmx-process-resources.csv').open(encoding='utf-8',newline='') as f:pmx=list(csv.DictReader(f))
    output=[]
    profiles=read('configs/v3_pipeline_benchmark_v1.json')['applications']
    for profile in profiles:
        graph=[r for r in processes if r['job_role']=='graph' and r['campaign_id'].split('/')[1]==profile
               and r['path'] in ('build-resource-usage.txt','replay-resource-usage.txt')]
        extracts=[r for r in pmx if r['artifact_name'].startswith('v3-comparison-pmx-extraction-'+profile+'--') and r['measurement_present']=='True']
        compiler=[json.loads(r['resource_record']) for r in stages if r['stage']=='derived_binary_build'
                  and r['campaign_id'].split('/')[1]==profile]
        batch=[r for r in processes if r['scope']=='application_batch' and r['profile']==profile]
        assert len(graph)==160 and len(extracts)==80 and len(compiler)==80
        for name,records,scope in [('graph_build_and_replay',graph,'160 disjoint campaign commands'),
              ('pmx_extraction',extracts,'80 complete extraction commands'),
              ('pmx_binary_compilation',compiler,'80 repeated original compiler commands'),
              ('palladio_setup_and_solver_batches',batch,'original recorded per-application batches; build and solve distinguished by path')]:
            output.append(dict(application=profile,stage_group=name,records=len(records),scope=scope,
                total_command_wall_seconds=sum(float(r['wall_seconds']) for r in records),
                total_command_cpu_seconds=sum(float(r['user_seconds'])+float(r['system_seconds']) for r in records),
                maximum_recorded_process_rss_mib=max(float(r['maximum_rss_bytes']) for r in records)/2**20,
                calendar_latency=False,overlapping_nested_stage_timers_added=False))
    return output


def export(evidence,out):
    receipt=read(evidence/'retention.json')
    protocol_path=evidence/receipt['artifacts'][0]['profile']/'protocol.json'
    protocol=read(protocol_path)
    paired=[];stage_rows=[]
    sources={path.as_posix():sha256(path.read_bytes()).hexdigest()
             for path in (evidence/'retention.json',protocol_path)}
    for artifact in receipt['artifacts']:
        profile=artifact['profile'];path=evidence/profile/'results.json';raw=path.read_bytes()
        sources[path.as_posix()]=sha256(raw).hexdigest()
        result=json.loads(raw)
        for row in result['records']:
            base=dict(application=profile,repetition=row['repetition'],multiplier=row['multiplier'],
                      attempts=row['workload']['attempts'],native_spans=row['workload']['native_spans'],
                      method_order='/'.join(row['method_order']),status=row['status'],error=row.get('error'))
            for role in ('ordinary','pmx'):
                base[role+'_input_bytes']=sum(r['bytes'] for name,r in row['workload']['files'].items() if name.startswith(role+'/'))
            for method in ('graph','pmx'):
                if method not in row:continue
                base.update({method+'_'+k:v for k,v in measurement(row[method]).items()})
                forecasts=row[method]['forecasts']
                target='Gstar' if method=='graph' else 'PMX'
                base[method+'_point_operations']=sum(f[target]['status']=='ok' for f in forecasts.values())
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
                    pmx_models_including_controls=row['pmx']['models'])
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
                        'graph_categories_across_operation_models','pmx_models_including_controls'):
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
    for name in ('docs/tables/v3-main-recovered-34517752889/cost-scopes/process-resources.csv',
                 'docs/tables/v3-main-recovered-34517752889/cost-scopes/stage-observations.csv',
                 'docs/evidence/v3-main-durable-archive-34516536673/pmx-process-resources.csv'):
        sources[name]=sha256(Path(name).read_bytes()).hexdigest()
    files={'paired-pipelines.csv':csv_data(paired),'pipeline-summary.csv':csv_data(summaries),
           'stage-processes.csv':csv_data(stage_rows),'telemetry-scaling.csv':csv_data(scaling),
           'original-main-command-accounting.csv':csv_data(original_accounting())}
    note=f'''# Complete verified pipeline timing and telemetry scaling

Run {receipt['run_id']}; execution head {receipt['head']}. All 27 planned timing pairs are retained. These are computational repetitions of three previously observed calibration campaigns, not new independent observations or accuracy experiments.

`pipeline-summary.csv` reports median/min/max of three paired rounds per application/volume. The speedup is the median of individual PMX/graph wall ratios, not a ratio silently reconstructed from unlike stage medians. Raw pairs and every process measurement accompany it. Failure rows remain explicit and do not enter successful ratios.

The complete computational boundary starts with sealed permitted calibration files and installed software, and ends with saved, verified forecasts. Graph timings include all eight methods and exact fresh-process replay. PMX timings include both variants, known-probability controls, two solver passes, all process starts, projection/extraction and serialization. These are implemented verified pipelines; graph time is not an isolated Gstar-only kernel. Acquisition, source transfer, common role projection, workload creation and installation precede this boundary.

The PMX launcher has 20 s per operation, included in the primary measured time. Startup-subtracted values are arithmetic decompositions of that same measurement, not measurements of a rewritten faster implementation. Dependency/compiler setup is separate. Process CPU sums use disjoint child commands; memory is the largest of sequential process/children peaks, not whole-runner or parent-orchestrator RSS.

Volumes 1x/2x/4x preserve structure, masks, values, durations and the empirical state law; only unique observation IDs and multiplicities change. Original point/status/bound equality to 1e-12 is required. Probe rows are shared at the unchanged timestamps. This is scalability with telemetry volume, not with deployed service count, state-space complexity or time dependence. Ratios/exponents are descriptive for these finite workloads, with no asymptotic or statistical superiority claim.

The original-main accounting table sums only separately timed commands over the full 240 campaigns, including the original repeated binary compiles and application-wide analyzer batches. It is an execution-work inventory, not calendar elapsed time or a matched pipeline speedup; setup policy and hardware jobs differ from the new paired benchmark.
'''
    files['README.md']=note.encode()
    files['.gitattributes']=b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n'
    provenance=dict(version='v3-pipeline-benchmark-table-export-v1',run_id=receipt['run_id'],head=receipt['head'],sources=sources,
        exporter_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        local_model_solver_or_bootstrap_execution=False,outputs={name:dict(bytes=len(data),sha256=sha256(data).hexdigest()) for name,data in files.items()})
    files['provenance.json']=(json.dumps(provenance,indent=2)+'\n').encode()
    out.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():(out/name).write_bytes(data)
    print(json.dumps(dict(pairs=len(paired),qualified=sum(r['status']=='qualified' for r in paired),summaries=summaries),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();export(args.evidence,args.out)
