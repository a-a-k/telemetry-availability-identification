"""Four matched first-answer routes, stage instrumentation and ready queries."""
import argparse
import os
from pathlib import Path
import resource
import time

from telemetry_availability.completion_target_v1 import project_full, query_full_r, query_reduced
from telemetry_availability.completion_target_profile_v1 import identify, query_e
from telemetry_availability.v3_application_execution_v2 import BindingUnsupported
from telemetry_availability.v3_primary_projection import read, write

ROUTES = ('full_e', 'full_r', 'projected_r', 'direct_r')


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true': raise ValueError('real model work is remote only')
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--route',choices=ROUTES,required=True);args=p.parse_args()
    route=args.route;query=query_e if route=='full_e' else query_full_r if route=='full_r' else query_reduced
    tick=time.perf_counter();metadata=read(args.input/'workload.json')
    specs=read(args.input/'execution.json')['profiles'][metadata['profile']]['operations']
    names=['requests.json','native.json','declarations.json']
    if route!='direct_r':names+=['probes.json','manifest.json']
    data={name:read(args.input/'ordinary'/name) for name in names}
    stages={'read_seconds':time.perf_counter()-tick,'interpretation_seconds':0.,'representation_seconds':0.,
            'frequency_identification_seconds':0.,'projection_seconds':0.,'first_query_seconds':0.}
    models={};answers={};operation_stages=[]
    for operation,spec in specs.items():
        try:
            model,_,measured,calls=identify(data,operation,spec,metadata['identity'],direct=route=='direct_r')
            one=dict(operation=operation,**measured,calls=calls,projection_seconds=0.,first_query_seconds=0.)
            for name in ('interpretation_seconds','representation_seconds','frequency_identification_seconds'):stages[name]+=measured[name]
            if route=='projected_r':
                start=time.perf_counter();model=project_full(model);one['projection_seconds']=time.perf_counter()-start
            start=time.perf_counter();answer=query(model);one['first_query_seconds']=time.perf_counter()-start
            stages['projection_seconds']+=one['projection_seconds'];stages['first_query_seconds']+=one['first_query_seconds']
            models[operation]=model;answers[operation]=dict(support='supported',**answer);operation_stages.append(one)
        except BindingUnsupported as exc:answers[operation]=dict(support='unsupported',reason=str(exc))
    start=time.perf_counter();write(args.output/'models.json',models);write(args.output/'answers.json',answers)
    first_saved_ns=time.perf_counter_ns();used=resource.getrusage(resource.RUSAGE_SELF)
    stages['save_seconds']=first_saved_ns/1e9-start
    warm=[]
    for repetition in range(31):
        for operation,model in models.items():
            start=time.perf_counter_ns();answer=query(model)
            warm.append(dict(operation=operation,repetition=repetition,nanoseconds=time.perf_counter_ns()-start,answer=answer))
    write(args.output/'measurement.json',dict(route=route,target='E' if route=='full_e' else 'R',first_saved_ns=first_saved_ns,
        first_cpu_seconds=used.ru_utime+used.ru_stime,first_peak_rss_kib=used.ru_maxrss,
        internal_pipeline_seconds=first_saved_ns/1e9-tick,stages=stages,operation_stages=operation_stages,
        warm_queries=warm,source_files_read=names,population=len(data['requests.json']),
        native_span_records=sum(len(v) for v in data['native.json']['spans'].values()),
        models={op:dict(coordinates=len(m['signal_ids']),categories=len(m['observation_categories']),samples=m['sample_count'])for op,m in models.items()},
        answers=answers,extra_verification_performed=False))


if __name__=='__main__':main()
