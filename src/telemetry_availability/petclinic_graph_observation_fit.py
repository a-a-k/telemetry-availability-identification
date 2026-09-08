"""First technical create_visit graph chain, with explicit effective-state assumptions."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from .graph_observation_model import identify,evaluate,probe_verdict
from .v3_graph_input_inventory import inventory,ReadBoundary
from .v3_primary_projection import read,write,sha

METHOD='G-OBS-create-visit-technical-v1'


def fit(root):
    info=inventory(root)
    declarations=read(root/'declarations.json');native=read(root/'native.json')
    requests=read(root/'requests.json');probes=read(root/'probes.json')
    if declarations['profile']!='spring_petclinic_microservices' or declarations['backend_success_check_statuses']!=['L7OK']:
        raise ValueError('unsupported application/probe contract')
    operation='create_visit';selected=[r for r in requests if r['operation']==operation]
    if len(selected)!=900:raise ValueError('unexpected technical operation census')
    graph_info=info['graphs'][operation]
    if graph_info['attempts_without_native_trace']:raise ValueError('unresolved external trace coverage')
    replicas=sorted(declarations['replicas'])
    if replicas!=['a','b']:raise ValueError('this ordinary input schema declares exactly replicas a/b')
    boundary_roots=0;observed_instances=defaultdict(set)
    for request in selected:
        request_id=request['request_id'];trace_id=hashlib.sha256(request_id.encode()).hexdigest()[:32]
        expected_parent=hashlib.sha256(('client:'+request_id).encode()).hexdigest()[:16]
        if request['trace_id']!=trace_id:raise ValueError('external trace context derivation mismatch')
        spans=native['spans'][trace_id];ids={s['span_id'] for s in spans};roots=[]
        for span in spans:
            if span['parent_id'] not in ids:
                if span['parent_id']!=expected_parent or span['service']!='api-gateway' or not span['server']:
                    raise ValueError('missing parent is not the declared external client boundary')
                roots.append(span)
            if span['service']==declarations['target_service']:
                replica=span['resource_attributes'].get('study.replica')
                if replica in replicas:
                    observed_instances[replica].add(span['resource_attributes'].get('service.instance.id',''))
        if len(roots)!=1:raise ValueError('unexpected native boundary-root multiplicity')
        boundary_roots+=1
    if set(observed_instances)!=set(replicas) or any(not names or '' in names for names in observed_instances.values()):
        raise ValueError('replica-to-native instance support missing')
    db_nodes=[name for name,role in graph_info['nodes'].items() if role=='observed_client_peer_not_native_server']
    if len(db_nodes)!=1 or declarations['database_shared'] is not True:raise ValueError('shared observed DB peer unresolved')
    target=declarations['target_service'];entry='api-gateway'
    known=set(declarations['known_non_target_dependencies'])|{target}|set(db_nodes)
    if not set(graph_info['nodes'])<=known:raise ValueError('undeclared non-target state reduction')
    # Business-required targets are source/contract declarations, not span frequency inference.
    required=[target,db_nodes[0]]
    if not set([entry,*required])<=set(graph_info['nodes']):raise ValueError('required target absent from discovery')
    graph=dict(services=sorted(graph_info['nodes']),edges=[
        dict(source=edge['source'],target=edge['target'],type='sync',factors=[],
             observed_relation=edge['observation_type'],supporting_attempts=edge['supporting_attempts'],
             supporting_spans=edge['supporting_spans']) for edge in graph_info['edges']])
    signals=['probe_'+replica for replica in replicas]
    node_gates={name:[[]] for name in graph['services']}
    node_gates[target]=[[signal] for signal in signals]
    observations=[];phases=Counter();unknown=Counter()
    for row in probes:
        observation={}
        for replica,signal in zip(replicas,signals):
            value=probe_verdict(row['replica_'+replica+'_backend_status'],row['replica_'+replica+'_backend_check_status'])
            observation[signal]=value['value'];phases[replica]+=value['check_in_progress'];unknown[replica]+=value['value'] is None
        observations.append(observation)
    assumptions=dict(
        supported_event='ideal static synchronous graph reachability, used as an approximation to the declared external contract',
        business_event='create_visit: correct complete 201 within 2 s and required persisted row',
        signal_meaning='last declared HAProxy L7 eligibility, not latent physical process/domain/communication state',
        state_law='empirical joint observation categories; no replica independence and no MCAR imputation',
        sampling='uniform calibration probe ticks; finite-window approximation, future distribution stability assumed',
        routing='ideal selection of an eligible replica; no delay/retry/queue model',
        repeat_semantics='same effective static state during an operation',
        fixed_live_nodes=[name for name in graph['services'] if name!=target],
        fixed_live_is_declared_unmeasured_reduction=True,
        edge_law='synchronous HTTP/JDBC in this pinned create_visit source; no additional communication variables',
        database='observed shared DB CLIENT peer; not a fabricated native DB server',
        missingness='legacy composite collector may have informative masks; bounds retained',
        baseline_residual_q_used=False,calibration_business_outcomes_used_for_parameters=False,
        physical_cause_parameters_identified=False,main_method_selected=False)
    model=identify(graph,node_gates,dict(id=operation,entry=entry,required=required,semantics='immediate_sync_all_required'),
                   signals,observations,assumptions)
    model['identity']=dict(method=METHOD,profile=declarations['profile'],placement=declarations['placement'],
        failure_law=declarations['failure_law'],data_role='retained_development_technical',scope='current',
        source_ordinary_seal=info['original_input_seal'])
    prediction=evaluate(model)
    report=dict(identity=model['identity'],prediction=prediction,external_attempts=len(selected),probe_ticks=len(probes),
        graph_nodes=len(graph['services']),graph_edges=len(graph['edges']),native_spans=graph_info['spans'],
        verified_external_boundary_roots=boundary_roots,unexpected_missing_parents=0,
        native_instance_mapping={k:sorted(v) for k,v in observed_instances.items()},
        in_progress_counts=dict(phases),unknown_verdict_counts=dict(unknown),
        assumptions=assumptions,main_campaigns=0,
        transfer_status='unsupported: empirical source joint law does not determine changed sharing/routing law')
    return model,report


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','Application graph fitting/replay is remote-only'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--models',type=Path)
    parser.add_argument('--reports',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();root=args.input.resolve();reports=args.reports.resolve();reports.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter();boundary=ReadBoundary(root,reports)
    if args.replay:boundary.allowed={root/'model.json'}
    sys.addaudithook(boundary.hook)
    try:
        if args.replay:
            model=read(root/'model.json');prediction=evaluate(model)
            equivalent=deepcopy(model);equivalent['graph']['edges'].reverse()
            assert evaluate(equivalent)==prediction
            changed=deepcopy(model)
            required_db=next(name for name in changed['operation']['required'] if name.startswith('observed-db-client-'))
            changed['graph']['edges']=[e for e in changed['graph']['edges'] if e['target']!=required_db]
            changed_result=evaluate(changed)
            assert changed_result['lower']==changed_result['upper']==0
            assert prediction['upper']>0
            report=dict(identity=model['identity'],prediction=prediction,model_sha256=sha(root/'model.json'),
                structural_control=dict(remove_incoming_required_db_edges=changed_result,
                    equivalent_edge_order_preserves_prediction=True),main_campaigns=0,
                replay_inputs=['model.json'],application_adequacy_tested=False)
        else:model,report=fit(root)
    finally:boundary.active=False
    report['elapsed_seconds']=time.perf_counter()-started
    if not args.replay:
        if args.models is None:raise ValueError('build requires model output directory')
        write(args.models/'model.json',model)
        report['model_sha256']=sha(args.models/'model.json')
        write(args.models/'seal.json',dict(method=METHOD,files={'model.json':report['model_sha256']}))
    write(reports/('replay.json' if args.replay else 'fit.json'),report)
    write(reports/'read-audit.json',dict(actual_data_reads=sorted(boundary.reads),blocked=boundary.blocked,
        replay=args.replay,legacy_or_evaluator_received=False,enforced_during_all_input_reads_and_computation=True))
    assert not boundary.blocked and boundary.reads=={str(p) for p in boundary.allowed}
    print(json.dumps(dict(method=METHOD,replay=args.replay,prediction=report['prediction']['prediction'],
        status=report['prediction']['status'],actual_input_files=len(boundary.reads))))


if __name__=='__main__':main()
