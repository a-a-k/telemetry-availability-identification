"""Label-free realized-state bounds, then independent primary-outcome checks.

This is an adequacy audit. Calibration-to-test forecast errors are calculated
by the separate immutable forecast evaluator, never by re-fitting these bounds.
"""
import argparse
import base64
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

from .v4_primary_capture_v1 import load, seal, SQL, REQUEST_FIELDS
from .v4_confirmation_orchestration_v1 import check_gate, verify_new_locks
from .v4_execution_binding_v1 import fit_operation
from .v3_application_execution_v2 import BindingUnsupported
from .v3_primary_projection import read,write,sha
from .v3_graph_input_inventory import ReadBoundary
from .graph_execution_model_v1 import solve,predicates
from .attempt_compatibility_audit_v1 import compatibility,summarize_attempts
from .primary_verdict_audit_v1 import http_evidence,petclinic_evidence,matches_fixture
from .live_pilot import OTEL_PRODUCT,OTEL_PERSON


def checked_bytes(record):
    raw=base64.b64decode(record['base64'],validate=True)
    if len(raw)!=record['bytes'] or sha256(raw).hexdigest()!=record['sha256']:
        raise ValueError('primary byte digest/length differs')
    return raw


def sql_rows(snapshot,period):
    if snapshot['query']!=SQL or snapshot['returncode']!=0 or snapshot['period']!=period:
        raise ValueError('primary SQL query or phase differs')
    checked_bytes(snapshot['stderr'])
    rows=[json.loads(line) for line in checked_bytes(snapshot['stdout']).splitlines()]
    if len({r['id'] for r in rows})!=len(rows): raise ValueError('duplicate SQL primary identity')
    return rows


def independent_petclinic(request,fixture,persisted):
    raw=checked_bytes(dict(base64=request['response_base64'],sha256=request['response_sha256'],bytes=request['response_bytes']))
    try: payload=json.loads(raw)
    except (ValueError,UnicodeError): payload=None
    if request['status_code'] is not None and 200<=request['status_code']<300 and payload!=request['payload']:
        raise ValueError('stored response projection differs from primary bytes')
    result=petclinic_evidence(dict(request,payload=payload),fixture)
    result['original_response_bytes_retained']=True
    if request['operation']!='create_visit': return result
    marker='study-'+sha256(request['request_id'].encode()).hexdigest()
    if marker!=request['marker']: raise ValueError('write marker does not bind to attempt identity')
    records=[r for r in persisted if r['description']==marker]
    correct=(len(records)==1 and isinstance(payload,dict) and type(payload.get('id')) is int
        and matches_fixture(records[0],dict(id=payload['id'],petId=1,date='2026-09-01',description=marker)))
    result.update(outcome=bool(result['acknowledged_response_valid'] and correct),
        verification='primary_HTTP_bytes_and_independent_raw_SQL_marker_identity_uniqueness',
        persistence_independently_verified=True,persisted_rows_for_marker=len(records),
        correct_unique_persisted_effect=bool(correct))
    return result


def verify_witnesses(model,result):
    checked=0
    for category in result['category_certificates']:
        known=dict(zip(model['signal_ids'],category['values']))
        for functional,extrema in category['extrema'].items():
            for side,endpoint in (('lower','minimum'),('upper','maximum')):
                values=extrema[side+'_witness']
                if values is None: continue
                state=dict(zip(model['signal_ids'],values))
                if any(v is not None and state[k]!=v for k,v in known.items()): raise ValueError('witness violates observation')
                if predicates(model,state)[functional]!=extrema[endpoint]: raise ValueError('witness fails endpoint')
                checked+=1
    return checked


def build_period(data,specs,identity,period):
    requests=data['requests.json'];native=data['native.json']
    if (any(set(r)!=set(REQUEST_FIELDS) or r['period']!=period for r in requests)
        or native['external_business_outcomes_present'] is not False or native['period']!=period
        or set(native['selected_trace_ids'])!={r['trace_id'] for r in requests}):
        raise ValueError('realized-state role contains outcomes or another phase')
    if len({r['request_id'] for r in requests})!=len(requests): raise ValueError('duplicate attempt identity')
    models={};attempts={};operations=[]
    for operation,spec in specs.items():
        selected=[r for r in requests if r['operation']==operation]
        if len(selected)!=spec['expected_attempts']: raise ValueError('fixed realized-state attempt census differs')
        parse=data['manifest.json']['native_parse']
        try:
            if parse['malformed_json_records'] or parse['invalid_traces']:
                raise BindingUnsupported('malformed_native_record_or_invalid_verification_trace')
            model,report,diagnostics=fit_operation(data,operation,spec,identity)
        except BindingUnsupported as exc:
            operations.append(dict(operation=operation,status='unsupported',reason=str(exc),attempts=len(selected)));continue
        model['assumptions']['historical_proxy_time_is_sampler_start_not_check_completion']=False
        model['assumptions']['historical_proxy_snapshot_timestamp']='reading_completed; last HAProxy check can still be older'
        result=solve(model);certificates={tuple(c['values']):c['extrema']['execution'] for c in result['category_certificates']}
        records=[]
        for record in diagnostics:
            values=tuple(record['observation'][k] for k in model['signal_ids']);bounds=certificates[values]
            if None not in values and not bounds['minimum']==predicates(model,record['observation'])['execution']==bounds['maximum']:
                raise ValueError('direct complete-state event differs from bounds')
            records.append(dict(record,lower=bounds['minimum'],upper=bounds['maximum'],fully_observed=None not in values))
        if Counter(tuple(r['observation'][k] for k in model['signal_ids']) for r in records)!={
            tuple(c['values']):c['count'] for c in model['observation_categories']}:
            raise ValueError('attempt observations do not reproduce model joint law')
        models[operation]=model;attempts[operation]=records
        operations.append(dict(operation=operation,status='bounded',attempts=len(selected),
            estimates=result['estimates'],checked_witness_endpoints=verify_witnesses(model,result),
            completion_evidence_counts=report['completion_evidence_counts']))
    return dict(models=models,attempts=attempts,operations=operations)


def build_bounds(source,frozen_root,out,config):
    frozen,gate=check_gate(frozen_root)
    identity=frozen['candidates.json']['identity'];receipt=frozen['receipt.json']['acquisition_receipt']
    source=source.resolve();out=out.resolve();boundary=ReadBoundary(source,out)
    boundary.allowed={source/name for name in ('requests.json','native.json','probes.json','declarations.json','manifest.json','seal.json')}
    if identity['application']=='spring_petclinic_microservices': boundary.allowed.add(source/'controls.json')
    sys.addaudithook(boundary.hook)
    try:
        documents,record=load(source,'test_binding',identity,receipt['test_binding_seal_sha256'])
        specs=config['profiles'][identity['application']]['operations']
        result=build_period(documents,specs,identity,'test')
        if 'controls.json' in documents:
            controls=documents['controls.json']
            control_data={'requests.json':controls['requests'],'native.json':controls['native'],'probes.json':controls['probes'],
                'declarations.json':documents['declarations.json'],
                'manifest.json':dict(native_parse=controls['native_parse'])}
            result['controls']=build_period(control_data,{'create_visit':dict(specs['create_visit'],expected_attempts=8)},identity,'control')
    finally: boundary.active=False
    if boundary.blocked or boundary.reads!={str(p) for p in boundary.allowed}: raise ValueError('state-builder read census differs')
    output={'bounds.json':result,'receipt.json':dict(identity=identity,test_binding_seal_sha256=sha(source/'seal.json'),
        frozen_forecast_seal_sha256=gate['frozen_seal_sha256'],primary_closed_seal_sha256=receipt['primary_closed_seal_sha256'],
        head=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],created_at=datetime.now(timezone.utc).isoformat(),
        external_business_outcomes_available=False,forecasts_reestimated=False),
        'read-audit.json':dict(actual_data_reads=sorted(boundary.reads),blocked=boundary.blocked)}
    seal(out/'sealed','realized_bounds',identity,output)
    write(out/'compact.json',dict(identity=identity,operations=result['operations'],
        controls=result.get('controls',{}).get('operations',[]),bound_seal_sha256=sha(out/'sealed/seal.json'),
        head=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],external_business_outcomes_available=False))


def verify_period(primary,bounds,identity,period):
    requests=primary['requests.json'];persisted=sql_rows(primary['sql.json'],period) if 'sql.json' in primary else None
    by_id={r['request_id']:r for r in requests}
    if len(by_id)!=len(requests) or any(r['period']!=period for r in requests): raise ValueError('primary attempt census/phase differs')
    verified={};label_mismatches=0
    for request in requests:
        label_free={k:v for k,v in request.items() if k not in ('semantic_success','semantic_reason','semantic_rule','persisted_marker_count')}
        verdict=(independent_petclinic(label_free,primary['fixture.json'],persisted) if persisted is not None
            else http_evidence(label_free,OTEL_PRODUCT,OTEL_PERSON['address']))
        if type(verdict['outcome']) is not bool: raise ValueError('new primary outcome could not be independently determined')
        verdict['stored_label_matches']=verdict['outcome']==request['semantic_success']
        label_mismatches+=not verdict['stored_label_matches'];verified[request['request_id']]=verdict
    rows=[];operations=[]
    for operation in bounds['operations']:
        op=operation['operation'];selected=[r for r in requests if r['operation']==op]
        if len(selected)!=operation['attempts']: raise ValueError('bounded and primary attempt census differ')
        summary=dict(operation,primary_verified_attempts=len(selected),primary_label_mismatches=sum(not verified[r['request_id']]['stored_label_matches'] for r in selected))
        if operation['status']=='unsupported': operations.append(summary);continue
        records=bounds['attempts'][op]
        if {r['request_id'] for r in records}!={r['request_id'] for r in selected}: raise ValueError('bound identity does not reproduce primary ledger')
        local=[];mechanisms=Counter()
        for record in records:
            outcome=verified[record['request_id']]['outcome'];observation=record['observation']
            row=dict(record,operation=op,outcome=outcome,primary_verification=verified[record['request_id']],
                compatibility=compatibility(record['lower'],outcome,record['upper']))
            request=by_id[record['request_id']]
            if period=='control': row['control_kind']=request['control_kind']
            if outcome and any(observation.get('demand_'+r) is True and record['historical_probe_context'].get('probe_'+r) is False for r in ('a','b')):
                mechanisms['successful_invocation_with_selected_historical_DOWN']+=1
            for reason in record['completion_reasons'].values():
                if 'retry' in reason: mechanisms[reason]+=1
            local.append(row)
        summary.update(summarize_attempts(local),mechanism_counts=dict(mechanisms))
        if period=='control':
            summary['by_control_kind']={kind:summarize_attempts([r for r in local if r['control_kind']==kind]) for kind in ('normal','retry')}
        operations.append(summary);rows.extend(local)
    if sum(r['attempts'] for r in operations)!=len(requests): raise ValueError('operation census omits primary attempts')
    return dict(operations=operations,attempts=rows,primary_attempts=len(requests),
        independently_verified_attempts=len(verified),primary_label_mismatches=label_mismatches,
        primary_verdicts=verified,selected_by_E_equals_Y=False)


def verify_primary(source,bounds_root,frozen_root,out):
    frozen,gate=check_gate(frozen_root);identity=frozen['candidates.json']['identity']
    bounded,_=load(bounds_root,'realized_bounds',identity)
    receipt=bounded['receipt.json']
    if (receipt['head']!=os.environ['GITHUB_SHA'] or receipt['run']!=os.environ['GITHUB_RUN_ID']
        or receipt['frozen_forecast_seal_sha256']!=gate['frozen_seal_sha256']
        or receipt['external_business_outcomes_available'] is not False): raise ValueError('bounds not fixed before outcome opening')
    primary,_=load(source,'primary_closed',identity,receipt['primary_closed_seal_sha256'])
    result=verify_period(primary,bounded['bounds.json'],identity,'test')
    controls=None
    if 'controls.json' in primary:
        c=primary['controls.json']
        controls=verify_period({'requests.json':c['requests'],'sql.json':c['sql'],'fixture.json':primary['fixture.json']},
            bounded['bounds.json']['controls'],identity,'control')
    for label,value in (('test',result),('controls',controls)):
        if value is not None: write(out/'full'/(label+'.json'),value)
    compact=lambda v:{k:value for k,value in v.items() if k not in ('attempts','primary_verdicts')}
    report=dict(identity=identity,head=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],
        test=compact(result),controls=compact(controls) if controls else None,
        frozen_forecast_seal_sha256=gate['frozen_seal_sha256'],bound_seal_sha256=sha(bounds_root/'seal.json'),
        primary_closed_seal_sha256=sha(source/'seal.json'),forecasts_reestimated=False,
        historical_C12_reclassified=False,created_at=datetime.now(timezone.utc).isoformat())
    write(out/'compact.json',report)
    print(json.dumps(dict(primary_attempts=result['primary_attempts'],primary_label_mismatches=result['primary_label_mismatches'],
        incompatible_attempts=sum(r.get('incompatible_attempts',0) for r in result['operations']))))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['bounds','primary'])
    p.add_argument('--source',type=Path,required=True);p.add_argument('--frozen',type=Path,required=True)
    p.add_argument('--bounds',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();verify_new_locks()
    if os.environ.get('GITHUB_ACTIONS')!='true': raise ValueError('real confirmation verification is remote only')
    if args.command=='bounds': build_bounds(args.source,args.frozen,args.out,read(Path('configs/v4_confirmation_execution_v1.json')))
    else: verify_primary(args.source,args.bounds,args.frozen,args.out)


if __name__=='__main__':main()
