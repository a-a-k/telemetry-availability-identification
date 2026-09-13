"""One fresh process, one R target; exact replays are external to all timings."""
import argparse
import json
import os
from pathlib import Path
import resource
import time

from telemetry_availability.completion_target_v1 import (full_identify, direct_identify, project_full,
                                                         query_full_r, query_reduced)
from telemetry_availability.v3_application_execution_v2 import BindingUnsupported
from telemetry_availability.v3_primary_projection import read, write


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true': raise ValueError('real model work is remote only')
    p = argparse.ArgumentParser(); p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--route', required=True)
    args = p.parse_args(); route = args.route
    if route not in ('full', 'projected', 'direct'): raise ValueError('unplanned route')
    tick = time.perf_counter(); metadata = read(args.input/'workload.json')
    spec = read(args.input/'execution.json')['profiles'][metadata['profile']]['operations']
    names = ['requests.json', 'native.json', 'declarations.json']
    if route != 'direct': names += ['probes.json', 'manifest.json']
    data = {name: read(args.input/'ordinary'/name) for name in names}
    loaded = time.perf_counter(); stages = {'read_seconds': loaded-tick}
    models = {}; answers = {}; build = projection = query = 0
    for operation, setting in spec.items():
        try:
            start = time.perf_counter()
            if route == 'direct': model, _ = direct_identify(data, operation, setting, metadata['identity'])
            else: model, _ = full_identify(data, operation, setting, metadata['identity'])
            build += time.perf_counter()-start
            if route == 'projected':
                start = time.perf_counter(); model = project_full(model); projection += time.perf_counter()-start
            start = time.perf_counter()
            answer = query_full_r(model) if route == 'full' else query_reduced(model)
            query += time.perf_counter()-start
            models[operation] = model; answers[operation] = dict(support='supported', **answer)
        except BindingUnsupported as exc:
            answers[operation] = dict(support='unsupported', reason=str(exc))
    stages.update(build_seconds=build, projection_seconds=projection, first_query_seconds=query)
    start = time.perf_counter(); write(args.output/'models.json', models); write(args.output/'answers.json', answers)
    first_saved_ns = time.perf_counter_ns(); used = resource.getrusage(resource.RUSAGE_SELF)
    stages['save_seconds'] = first_saved_ns/1e9-start
    # Only repeated target queries follow this timestamp; there is no oracle.
    warm = []
    for repetition in range(31):
        for operation, model in models.items():
            start = time.perf_counter_ns()
            result = query_full_r(model) if route == 'full' else query_reduced(model)
            warm.append(dict(operation=operation, repetition=repetition,
                             nanoseconds=time.perf_counter_ns()-start, answer=result))
    write(args.output/'measurement.json', dict(route=route, first_saved_ns=first_saved_ns,
        first_cpu_seconds=used.ru_utime+used.ru_stime, first_peak_rss_kib=used.ru_maxrss,
        internal_pipeline_seconds=first_saved_ns/1e9-tick, stages=stages, warm_queries=warm,
        source_files_read=names, population=len(data['requests.json']),
        models={op: dict(coordinates=len(m['signal_ids']), categories=len(m['observation_categories']),
                         samples=m['sample_count']) for op, m in models.items()},
        answers=answers, extra_verification_performed=False))


if __name__ == '__main__': main()
