"""User-requested E control and four matched, stage-instrumented cost routes."""
import argparse
import os
from pathlib import Path
import sys
import time

import run_completion_target_v1 as source
from benchmark_v3_pipeline_v1 import read, write, timed, command_ok
from v4_confirmed_source_v3 import require_source, SOURCE_RUN
import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.v3_primary_projection import sha
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
from telemetry_availability.completion_target_v1 import full_identify, project_full, query_full_r, query_reduced
from telemetry_availability.graph_execution_model_v1 import solve
from telemetry_availability.completion_target_profile_v1 import query_e

CONFIG=Path('configs/v5_completion_followup_v1.json')
ROOT=Path('workflow-results/completion-followup')


def qualify(records, baseline, config):
    references={}
    for multiplier in (1,2,4):
        inputs=source.WORK/'volumes'/f'x{multiplier}'
        data={p.name:read(p) for p in (inputs/'ordinary').glob('*.json')}
        meta=read(inputs/'workload.json');specs=read(inputs/'execution.json')['profiles'][baseline['profile']]['operations']
        ref={}
        for op,spec in specs.items():
            full,_=full_identify(data,op,spec,meta['identity']);projected=project_full(full)
            e=solve(full)['estimates']['execution']
            ref[op]=dict(full=full,reduced=projected,R=query_full_r(full),E={k:e[k] for k in ('lower_exact','upper_exact')})
        references[multiplier]=ref
    for row in records:
        if row['status']=='failed':continue
        try:
            root=ROOT/'full/trials'/f"r{row['repetition']}-x{row['multiplier']}"/row['route']
            models=read(root/'models.json');answers=read(root/'answers.json');ref=references[row['multiplier']]
            if set(models)!=set(ref) or set(answers)!=set(ref):raise ValueError('unequal complete target/support census')
            for op,model in models.items():
                expected_model=ref[op]['full' if row['route'] in ('full_e','full_r') else 'reduced']
                if model!=expected_model:raise ValueError('instrumentation changed model construction')
                expected=ref[op][row['target']]
                if any(answers[op][k]!=expected[k] for k in ('lower_exact','upper_exact')):raise ValueError('target differs from independent reference')
            for query in row['warm_queries']:
                if dict(support='supported',**query['answer'])!=answers[query['operation']]:raise ValueError('prepared target changed')
            original=references[1]
            for op in ref:
                if any(ref[op][row['target']][k]!=original[op][row['target']][k] for k in ('lower_exact','upper_exact')):
                    raise ValueError('volume copy changed probability')
            row['status']='qualified'
        except Exception as exc:row.update(status='failed',error=type(exc).__name__+': '+str(exc))
    return records


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',required=True);args=p.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_RUN_ATTEMPT')!='1':raise ValueError('first remote run required')
    config=read(CONFIG)
    for name,digest in config['source_locks'].items():
        if sha(Path(name))!=digest:raise ValueError('fixed followup source changed: '+name)
    original=read('configs/v5_completion_target_v2.json')
    source_status=require_source();_,_,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    baseline=next(c for c in cases if c['profile']==args.profile and c['identity']['law']=='N' and c['identity']['repetition']==0)
    artifacts=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/artifacts','artifacts');by={a['name']:a for a in artifacts}
    for expected in original['source_artifacts']:
        if any(by[expected['name']][k]!=v for k,v in expected.items()):raise ValueError('original input artifact changed')
    source.read=read;source.ROOT=ROOT
    receipts={};source.prepare_cost(baseline,artifacts,receipts)
    write(ROOT/'compact/protocol.json',config)
    write(ROOT/'compact/environment.json',dict(profile=args.profile,run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
        source_status=source_status,cpu_count=os.cpu_count(),cpu_info=Path('/proc/cpuinfo').read_text(),memory_info=Path('/proc/meminfo').read_text(),python=sys.version))
    records=[]
    try:
        for repetition,volumes in enumerate(config['scale_orders']):
            for multiplier in volumes:
                routes=config['routes'];offset=(repetition+(1,2,4).index(multiplier))%4;order=routes[offset:]+routes[:offset]
                for position,route in enumerate(order):
                    inputs=source.WORK/'volumes'/f'x{multiplier}';out=ROOT/'full/trials'/f'r{repetition}-x{multiplier}'/route
                    for file in sorted((inputs/'ordinary').glob('*.json')):
                        with file.open('rb') as stream:
                            while stream.read(1024*1024):pass
                    row=dict(profile=args.profile,repetition=repetition,multiplier=multiplier,route=route,order=order,position=position,
                             status='measured_awaiting_verification')
                    start=time.perf_counter_ns()
                    try:
                        process=timed([sys.executable,'scripts/measure_completion_target_v3.py','--input',inputs,'--output',out,'--route',route],out/'process',dict(os.environ),timeout=600)
                        row['process']=process;command_ok(process);measured=read(out/'measurement.json')
                        elapsed=(measured['first_saved_ns']-start)/1e9
                        if not 0<elapsed<=process['wall_seconds']+1:raise ValueError('first-answer clock differs')
                        row.update(first_answer_seconds=elapsed,**measured)
                    except Exception as exc:row.update(status='failed',error=type(exc).__name__+': '+str(exc))
                    records.append(row);write(ROOT/'compact/timings.json',dict(records=records))
                    print(dict(repetition=repetition,multiplier=multiplier,route=route,status=row['status']),flush=True)
        records=qualify(records,baseline,config)
        write(ROOT/'compact/timings.json',dict(records=records))
        if len(records)!=36 or any(r['status']!='qualified' for r in records):raise ValueError('four-route qualification failed')
        write(ROOT/'compact/receipt.json',dict(run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],profile=args.profile,
            source_artifacts=receipts,config_sha256=sha(CONFIG),processes=36,status='qualified',
            all_extra_verification_after_measurements=True,old_Palladio_ratios_multiplied=False,new_independent_observations=0))
    except Exception as exc:
        write(ROOT/'compact/failure.json',dict(type=type(exc).__name__,message=str(exc),source_artifacts=receipts));raise


if __name__=='__main__':main()
