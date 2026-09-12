"""Extract one bounded historical primary witness, preserving source pointers."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile

from audit_v3_attempts_v1 import ARCHIVE,MAIN_RUN,fetch,read,write,digest
from telemetry_availability.v3_ordinary_identity_v2 import load_bundle
from telemetry_availability.v3_application_execution_v2 import timestamp_ns
from telemetry_availability.v3_comparison_roles_v1 import digest as object_digest

KEY='deathstarbench_social_network--split--NC--r1'
REQUEST='v3-main-771601-deathstarbench_social_network-split-NC-1-run34465226083-a1-deathstarbench_social_network-split-NC-r1-calibration-000343'


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('primary capsule extraction is remote only')
    sources={s['name']:s for p in read(ARCHIVE)['parts'] for s in p['sources']}
    out=Path('workflow-results/single-attempt/input')
    if out.exists():raise ValueError('capsule output already exists')
    with tempfile.TemporaryDirectory(prefix='single-primary-attempt-') as directory:
        raw=Path(directory)/'raw';source=fetch(sources[f'v3-comparison-raw-{KEY}-{MAIN_RUN}'],raw)
        ordinary,_=load_bundle(raw/'roles/ordinary');all_requests=read(raw/'requests.json')
        found=[(i,r) for i,r in enumerate(all_requests) if r['request_id']==REQUEST]
        if len(found)!=1:raise ValueError('fixed primary example missing')
        request_index,request=found[0];native=read(raw/'raw-telemetry.json')
        traces=[(i,r) for i,r in enumerate(native['data']) if r['traceID'].lower()==request['trace_id']]
        if len(traces)!=1:raise ValueError('fixed primary native trace missing')
        trace_index,trace=traces[0];health=read(raw/'health.json')
        start=timestamp_ns(request['started_at']);end=timestamp_ns(request['completed_at'])
        ticks=[(i,r) for i,r in enumerate(health) if r['period']=='calibration'
            and start-3_000_000_000<=timestamp_ns(r['observed_at'])<=end+500_000_000]
        if not ticks:raise ValueError('primary health window missing')
        identity=read(raw/'identity.json');settings=read(Path('configs/v3_comparison_execution_v3.json'))
        source_spec=settings['profiles'][identity['application']]['operations']['compose_post']
        spec=deepcopy(source_spec);spec['expected_attempts']=1
        documents={'request.json':request,'native-jaeger.json':dict(data=[trace]),
            'health.json':[r for i,r in ticks],'declarations.json':ordinary['declarations.json'],
            'spec.json':spec,'identity.json':identity,
            'provenance.json':dict(source=source,source_identity=identity,
                request_source_file_sha256=digest(raw/'requests.json'),request_JSON_pointer='/'+str(request_index),
                request_canonical_sha256=object_digest(request),
                native_source_file_sha256=digest(raw/'raw-telemetry.json'),native_JSON_pointer='/data/'+str(trace_index),
                native_trace_canonical_sha256=object_digest(trace),
                health_source_file_sha256=digest(raw/'health.json'),health_source_row_indices=[i for i,r in ticks],
                health_records_canonical_sha256=object_digest([r for i,r in ticks]),
                original_ordinary_seal_sha256=digest(raw/'roles/ordinary/seal.json'),
                original_spec=source_spec,only_spec_change='expected_attempts: 1200 -> 1 for this explicit single-record demonstration',
                selected_as_previously_audited_counterexample=True,population_estimation_or_independent_validation=False,
                extraction_head=os.environ['GITHUB_SHA'],extraction_run=os.environ['GITHUB_RUN_ID'])}
        for name,value in documents.items():write(out/name,value)
        write(out/'seal.json',dict(version='v4-single-primary-attempt-v1',files={name:digest(out/name) for name in sorted(documents)}))
    print('One historical request, its original Jaeger trace and nearby health records retained.')


if __name__=='__main__':main()
