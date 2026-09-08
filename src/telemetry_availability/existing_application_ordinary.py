"""Remote ordinary export/inventory of preserved whole-operation contract windows."""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from hashlib import sha256
import io
import csv
import json
import os
from pathlib import Path
import sys
import time

from .health_prefix_audit_v3 import restore
from .live_evidence import _pivot_health
from .live_fault_campaign import make_trace_context
from .pmx_observed_operations import read_native
from .v3_primary_projection import project,write,sha,read,VERSION
from .v3_graph_input_inventory import inventory,ReadBoundary

CONFIG=Path('configs/existing_application_ordinary.json')


def config():
    assert os.environ.get('GITHUB_ACTIONS')=='true','application inputs are processed only on GitHub Actions'
    value=read(CONFIG)
    for lock in value['repository_locks']:
        assert sha(Path(lock['path']))==lock['sha256'],lock['path']
    return value


def csv_bytes(value):return list(csv.DictReader(io.StringIO(value.decode('utf-8-sig'))))


def technical_requests(source,profile):
    result=[]
    for row in source:
        if row['period']!='baseline' or row['profile']!=profile:
            raise ValueError('only the declared normal contract window is admitted')
        trace_id,header,value=make_trace_context(profile,row['request_id'])
        if row['trace_id']!=trace_id or row['trace_header']!=header:
            raise ValueError('external request trace context differs from pinned driver')
        result.append(dict(row,period='calibration'))
    if len({r['request_id'] for r in result})!=len(result):raise ValueError('duplicate request identity')
    return result


def prepare(settings,profile):
    selected=settings['profiles'][profile]
    archive,metadata=restore(selected['artifact'])
    summary=json.loads(archive.read('contract-summary.json'))
    assert summary['profile']==profile and summary['qualified'] and summary['attempts']==240
    source_requests=csv_bytes(archive.read('requests.csv'))
    requests=technical_requests(source_requests,profile)
    assert len(requests)==240 and len({r['operation'] for r in requests})==3
    image=json.loads(archive.read('image-lock-audit.json'))['placement_pilot']
    assert image['profile']==profile and image['placement']=='colocated'
    meta=dict(profile=profile,placement='colocated',failure_law='N',repetition=0)
    raw_health=csv_bytes(archive.read('health.csv'))
    for row in raw_health:
        if row['role']=='replica':assert row['service']==image['replica_services'][row['replica']]
    health,malformed=_pivot_health(meta,raw_health,'baseline')
    assert health
    health=[dict(row,period='calibration') for row in health]
    source=Path('workflow-input/native');source.mkdir(parents=True,exist_ok=True)
    native_name=selected['native_name'];value=archive.read(native_name)
    native_path=source/native_name;native_path.write_bytes(value)
    archive.close()
    tick=time.perf_counter()
    grouped,parse=read_native(native_path,{r['trace_id'] for r in requests},selected['native_format'])
    parse_seconds=time.perf_counter()-tick
    assert not parse['malformed_json_records'] and not parse['invalid_traces']
    native=dict(calibration_only=True,selected_trace_ids=[r['trace_id'] for r in requests],
                spans={key:[asdict(span) for span in spans] for key,spans in grouped.items()})
    # These metadata are declarations, never an inferred physical factorization.
    declarations=dict(meta,target_service=image['target_service'],replicas=image['replica_services'],
        placements=image['domain_assignments'],known_non_target_dependencies=[],
        source_declared_dependencies={op:[] for op in sorted({r['operation'] for r in requests})},
        dependency_provenance='not specified in inventory stage: empty lists mean unknown, not no dependencies',
        backend_success_check_statuses=['L4OK'],replica_health_check='HAProxy L4 transport connect only; not service readiness',
        database_shared=None)
    data,audit=project(declarations,requests,health,native)
    data['manifest.json'].update(data_role='retained_contract_normal_window_for_technical_calibration',
        original_source_period='baseline',original_source_run=selected['artifact']['source_run'],
        original_source_head=selected['artifact']['source_head'],new_independent_campaigns=0,
        period_adaptation='same 240 IDs/outcomes/times; baseline window reused as technical calibration only',
        full_operation_contract='whole_operation_contract_v1: complete external operation within 2 seconds',
        source_condition='normal state; no injected fault, no future stability or adequacy claim')
    out=Path('workflow-results/ordinary')
    for name,value in data.items():write(out/name,value)
    write(out/'seal.json',dict(version=VERSION,files={name:sha(out/name) for name in sorted(data)}))
    audit.update(artifact=metadata,normal_requests=len(requests),normal_probe_ticks=len(health),
        composite_collector_malformed_role_rows=malformed,parse=parse,native_parse_seconds=parse_seconds,
        original_native_sha256=sha(native_path),original_native_bytes=native_path.stat().st_size,
        period_adaptation=data['manifest.json']['period_adaptation'],
        ordinary_replica_names_bound_to_declared_proxy_servers=True,
        docker_state_fields_exported=0,sentinel_requests_exported=0,source_semantic_responses_exported=0)
    write(Path('workflow-results/preparation/projection-audit.json'),audit)


def inspect(profile):
    root=Path('workflow-input/ordinary').resolve();out=Path('workflow-results/inventory').resolve();out.mkdir(parents=True,exist_ok=True)
    boundary=ReadBoundary(root,out);sys.addaudithook(boundary.hook);tick=time.perf_counter()
    try:
        result=inventory(root)
        assert result['manifest']['profile']==profile and result['manifest']['external_attempts']==240
        assert len(result['graphs'])==3 and all(r['external_attempts']==80 for r in result['graphs'].values())
        requests=read(root/'requests.json');native=read(root/'native.json')
        roots=defaultdict(Counter);per_attempt=defaultdict(Counter)
        for request in requests:
            trace_id,header,context=make_trace_context(profile,request['request_id'])
            assert request['trace_id']==trace_id
            expected_parent=context.split(':')[1] if header=='uber-trace-id' else context.split('-')[2]
            spans=native['spans'].get(trace_id,[]);ids={s['span_id'] for s in spans}
            root_count=0
            for span in spans:
                if span['parent_id'] in ids:continue
                root_count+=1
                relation='matches_external_parent' if span['parent_id']==expected_parent else 'empty_parent' if not span['parent_id'] else 'other_missing_parent'
                roots[request['operation']][(span['service'],relation,str(span['native_kind']))]+=1
            per_attempt[request['operation']][str(root_count)]+=1
        result['external_boundary_census']={op:[dict(service=s,relation=r,native_kind=k,count=n)
            for (s,r,k),n in sorted(values.items())] for op,values in roots.items()}
        result['roots_per_attempt']={op:dict(values) for op,values in per_attempt.items()}
        assert boundary.reads=={str(p) for p in boundary.allowed} and not boundary.blocked
    finally:boundary.active=False
    result.update(inventory_seconds=time.perf_counter()-tick,main_campaigns=0,new_independent_campaigns=0,
                  application_graph_model_fits=0,technical_graph_replay_qualified=False)
    write(out/'inventory.json',result)
    write(out/'read-audit.json',dict(data_reads=sorted(boundary.reads),blocked=boundary.blocked,
          source_archive_access=False,test_outcomes=0,docker_state_fields=0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('prepare','inspect'))
    parser.add_argument('--profile',required=True)
    args=parser.parse_args();settings=config();assert args.profile in settings['profiles']
    if args.stage=='prepare':prepare(settings,args.profile)
    else:inspect(args.profile)


if __name__=='__main__':main()
