"""Versioned capture adapters for the independent confirmation series.

The old application drivers and verdict contracts remain frozen. These adapters
retain bytes previously discarded and timestamp a health snapshot when its
reading finishes. They do not infer a new outcome or physical state.
"""
import base64
from collections import defaultdict
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import time

from . import live_stochastic_pilot as health_source
from .v3_primary_projection import (read, write, sha, SPAN_FIELDS,
    ATTRIBUTE_PREFIXES, RESOURCE_FIELDS, PROBE_FIELDS)
from .v3_ordinary_identity_v2 import HOST_FIELDS

SQL = "SELECT JSON_OBJECT('id',id,'petId',pet_id,'date',DATE_FORMAT(visit_date,'%Y-%m-%d'),'description',description) FROM visits WHERE description LIKE 'study-%';"
REQUEST_FIELDS = ('request_id','trace_id','operation','period','started_at','completed_at')


def bytes_record(raw):
    return dict(base64=base64.b64encode(raw).decode('ascii'), sha256=sha256(raw).hexdigest(), bytes=len(raw))


def read_health_snapshot(identifiers, placement, profile, compose_path):
    began = health_source._utc_now()
    try:
        documents = health_source._inspect_containers(identifiers)
        proxy = health_source._proxy_stats(placement, profile, compose_path)
        error = ''
    except Exception as exc:
        documents, proxy, error = {}, {}, f'{type(exc).__name__}: {exc}'
    ended = health_source._utc_now()
    return documents, proxy, dict(sample_started_at=health_source._format_time(began),
        sample_completed_at=health_source._format_time(ended),
        observed_at=health_source._format_time(ended), error=error)


def health_sampler(config, profile, placement, law, repetition, period, compose_path,
                   containers, started_monotonic, stop, output):
    replicas = profile.replica_services
    replica_by_service = {service:key for key,service in replicas.items()}
    services = (*replicas.values(), profile.target_service)
    identifiers = [containers[s] for s in services]
    tick = 0
    while not stop.is_set():
        documents, proxy, timing = read_health_snapshot(identifiers, config.placement, profile, compose_path)
        common = dict(profile=profile.id, placement=placement, failure_law=law,
            repetition=repetition, period=period, **timing,
            elapsed_seconds=time.monotonic()-started_monotonic)
        if timing['error']:
            output.append(dict(common, service='__sampler__', role='auditor', replica='', domain='',
                container_id='', running='', paused='', health='unknown', network_count='',
                backend_status='', backend_check_status='', backend_sessions=''))
        else:
            for service,identifier in zip(services,identifiers,strict=True):
                record=documents[identifier]; state=record.get('State',{})
                replica=replica_by_service.get(service,''); backend=proxy.get(replica,{}) if replica else {}
                output.append(dict(common, service=service, role='replica' if replica else 'proxy',
                    replica=replica, domain=config.placement.placements[placement].get(replica,''),
                    container_id=identifier, running=bool(state.get('Running')), paused=bool(state.get('Paused')),
                    health=state.get('Health',{}).get('Status','not_declared'),
                    network_count=len(record.get('NetworkSettings',{}).get('Networks',{})),
                    backend_status=backend.get('status',''), backend_check_status=backend.get('check_status',''),
                    backend_sessions=backend.get('sessions','')))
        tick+=1
        if stop.wait(max(0,started_monotonic+tick*config.health_poll_seconds-time.monotonic())): return


def capture_sql(compose_path, destination, period):
    began=health_source._format_time(health_source._utc_now())
    completed=subprocess.run(['docker','compose','-f',str(compose_path),'exec','-T','-e',
        'MYSQL_PWD=petclinic-study','database','mysql','-uroot','--batch','--skip-column-names',
        'petclinic','-e',SQL],capture_output=True,check=False)
    ended=health_source._format_time(health_source._utc_now())
    document=dict(period=period,query=SQL,started_at=began,completed_at=ended,
        returncode=completed.returncode,stdout=bytes_record(completed.stdout),stderr=bytes_record(completed.stderr))
    write(destination,document)
    if completed.returncode: raise ValueError('primary persistence SELECT failed; original output retained')
    grouped=defaultdict(list)
    for line in completed.stdout.splitlines():
        row=json.loads(line);grouped[row['description']].append(row)
    return dict(grouped)


def seal(root, role, identity, documents):
    if root.exists(): raise ValueError('refusing to replace sealed confirmation role')
    for name,value in documents.items(): write(root/name,value)
    write(root/'seal.json',dict(version='v4-confirmation-role-v1',role=role,identity=identity,
        files={name:sha(root/name) for name in sorted(documents)}))
    return sha(root/'seal.json')


def load(root, role, identity=None, expected=None):
    if expected is not None and sha(root/'seal.json')!=expected: raise ValueError('confirmation source seal differs')
    record=read(root/'seal.json')
    if (record['version']!='v4-confirmation-role-v1' or record['role']!=role
        or identity is not None and record['identity']!=identity): raise ValueError('confirmation identity/role differs')
    files={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if files!=set(record['files'])|{'seal.json'} or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('unexpected confirmation paths')
    for name,digest in record['files'].items():
        if sha(root/name)!=digest: raise ValueError('confirmation document digest differs')
    return {name:read(root/name) for name in record['files']},record


def project_test_native(grouped, requests, period='test'):
    selected={r['trace_id'] for r in requests}
    if (len(selected)!=len(requests) or len({r['request_id'] for r in requests})!=len(requests)
        or any(r['period']!=period for r in requests) or not set(grouped)<=selected):
        raise ValueError('test trace/attempt identity differs')
    result={}
    for trace,spans in grouped.items():
        rows=[]
        for source in spans:
            s=asdict(source) if not isinstance(source,dict) else source
            row={k:s[k] for k in SPAN_FIELDS}
            row['native_links']=[{k:v for k,v in link.items() if k in
                ('traceId','spanId','traceState','flags','trace_id','span_id','trace_state')} for link in s['native_links']]
            row['attributes']={k:v for k,v in s['attributes'].items() if k in ('error','span.kind') or k.startswith(ATTRIBUTE_PREFIXES)}
            row['resource_attributes']={k:v for k,v in s['resource_attributes'].items() if k in RESOURCE_FIELDS|HOST_FIELDS}
            rows.append(row)
        result[trace]=rows
    return dict(period=period,external_business_outcomes_present=False,selected_trace_ids=sorted(selected),spans=result)


def install(out, bundle):
    """Explicitly select the new capture implementation in this new entrypoint."""
    from . import v3_comparison_acquisition_v1 as old
    from . import publication_stochastic_live as whole
    from . import petclinic_stochastic_preflight_v2 as pet
    from .v4_petclinic_capture_v1 import execute
    from .petclinic_contract_v2 import adapt_fixture
    from .live_evidence import _pivot_health
    from .pmx_observed_operations import read_native
    old._health_sampler=whole._health_sampler=health_sampler
    old.execute=pet.execute=execute
    original_period=old.petclinic_period; original_export=old.export_roles
    phase={'value':None};controls={}
    def period(*args,**kwargs):
        phase['value']=args[5] if len(args)>5 else kwargs['period']
        result=original_period(*args,**kwargs)
        if phase['value']=='test':
            from .v4_retry_controls_v1 import run
            config,runtime_config,profile,runtime,identity,_,_,path,_,namespace,fixture=args
            controls.update(run(config,runtime_config,profile,runtime,identity,path,namespace,fixture,out/'retry-controls'))
        return result
    def database(path):
        if phase['value'] not in ('baseline','calibration','test'): raise ValueError('unplanned SQL capture phase')
        return capture_sql(path,out/'primary-sql'/(phase['value']+'.json'),phase['value'])
    old.petclinic_period=period; old.db_records=database
    def export(out,identity,selected,config,profile,runtime,periods,requests,health,native_path,native_format,readiness):
        costs=original_export(out,identity,selected,config,profile,runtime,periods,requests,health,native_path,native_format,readiness)
        test=[r for r in requests if r['period']=='test']
        tick=time.perf_counter();source_hash=sha(native_path)
        grouped,parse=read_native(native_path,{r['trace_id'] for r in test},native_format)
        if sha(native_path)!=source_hash: raise ValueError('test native source changed during parsing')
        meta=dict(profile=profile.id,placement=identity['placement'],failure_law=identity['law'],repetition=identity['repetition'])
        probes,malformed=_pivot_health(meta,health,'test')
        documents={'requests.json':[{k:r[k] for k in REQUEST_FIELDS} for r in test],
            'native.json':project_test_native(grouped,test),
            'probes.json':[{k:p[k] for k in PROBE_FIELDS} for p in probes],
            'declarations.json':read(out/'roles/ordinary/declarations.json'),
            'manifest.json':dict(identity=identity,period='test',external_attempts=len(test),
                original_native_sha256=source_hash,native_parse=parse,malformed_probes=malformed,
                health_snapshot_timestamp='reading_completed',external_business_outcomes_present=False)}
        primary={'requests.json':test,'health.json':[h for h in health if h['period']=='test'],
            'events.json':[e for e in read(out/'events.json') if e['period']=='test'],
            'manifest.json':dict(identity=identity,period='test',outcome_selection=False,
                native_source_sha256=source_hash,expected_attempts=len(test))}
        if profile.id==old.PETCLINIC:
            primary['fixture.json']=adapt_fixture(read(bundle/'fixture.json'))
            primary['sql.json']=read(out/'primary-sql/test.json')
            if len(controls.get('requests',[]))!=8: raise ValueError('fixed retry-control census missing')
            grouped_control,control_parse=read_native(native_path,{r['trace_id'] for r in controls['requests']},native_format)
            control_probes,control_bad=_pivot_health(meta,controls['health'],'control')
            documents['controls.json']=dict(
                requests=[{k:r[k] for k in REQUEST_FIELDS} for r in controls['requests']],
                native=project_test_native(grouped_control,controls['requests'],'control'),
                probes=[{k:p[k] for k in PROBE_FIELDS} for p in control_probes],
                native_parse=control_parse,malformed_probes=control_bad)
            primary['controls.json']=dict(requests=controls['requests'],health=controls['health'],
                sql=read(controls['sql']),proxy_before=read(out/'retry-controls/proxy-before.json'),
                proxy_after=read(out/'retry-controls/proxy-after.json'))
        if sha(native_path)!=source_hash: raise ValueError('native bytes changed during all verification exports')
        test_hash=seal(out/'roles/test-binding','test_binding',identity,documents)
        primary_hash=seal(out/'roles/primary-closed','primary_closed',identity,primary)
        receipt=read(out/'public/receipt.json')
        receipt.update(test_binding_seal_sha256=test_hash,primary_closed_seal_sha256=primary_hash,
            health_snapshot_timestamp='reading_completed')
        write(out/'public/receipt.json',receipt)
        costs['test_verification_export_seconds']=time.perf_counter()-tick
        return costs
    old.export_roles=export


def main():
    import os,sys
    from . import v3_comparison_acquisition_v1 as old
    if os.environ.get('GITHUB_ACTIONS')!='true': raise ValueError('real capture is remote only')
    out=Path(sys.argv[sys.argv.index('--out')+1]).resolve()
    bundle=Path(sys.argv[sys.argv.index('--bundle')+1]).resolve() if '--bundle' in sys.argv else Path('workflow-input/petclinic-build').resolve()
    install(out,bundle);old.main()


if __name__=='__main__': main()
