"""Read only the new ordinary role; inventory native graphs, not fitted models."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from .v3_primary_projection import (FILES,REQUEST_FIELDS,PROBE_FIELDS,DECLARATION_FIELDS,
    SPAN_FIELDS,ATTRIBUTE_PREFIXES,RESOURCE_FIELDS,read,write,verify_bundle)


class ReadBoundary:
    def __init__(self,root,output):
        self.allowed={root/name for name in FILES|{'seal.json'}}
        self.output=output
        self.runtime=Path(sys.prefix).resolve()
        self.source=Path(__file__).resolve().parent
        self.reads=set();self.blocked=[];self.active=True

    def hook(self,event,args):
        if not self.active: return
        if event in ('socket.connect','subprocess.Popen','os.system'):
            self.blocked.append(event);raise PermissionError('ordinary-role consumer cannot use '+event)
        if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
        path=Path(os.fsdecode(args[0])).resolve()
        mode=args[1] if isinstance(args[1],str) else ''
        flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
        writing=any(c in mode for c in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        allowed=path.is_relative_to(self.output) if writing else path in self.allowed
        if not writing and not allowed:
            allowed=(path.is_relative_to(self.runtime) or path.is_relative_to(self.source)) and path.suffix in ('.py','.pyc','.so','.pyd','.dll')
        if not allowed:
            self.blocked.append(str(path));raise PermissionError('undeclared ordinary-role access: '+str(path))
        if not writing and path in self.allowed:self.reads.add(str(path))


def inventory(root):
    seal=verify_bundle(root)
    manifest=read(root/'manifest.json');requests=read(root/'requests.json');probes=read(root/'probes.json')
    native=read(root/'native.json');declarations=read(root/'declarations.json')
    if any(set(row)!=set(REQUEST_FIELDS) for row in requests) or any(set(row)!=set(PROBE_FIELDS) for row in probes):
        raise ValueError('ordinary request/probe field schema mismatch')
    if set(declarations)!=set(DECLARATION_FIELDS):raise ValueError('ordinary declaration field schema mismatch')
    if set(native)!={'calibration_only','selected_trace_ids','spans'} or native['calibration_only'] is not True:
        raise ValueError('ordinary native role schema mismatch')
    if set(native['selected_trace_ids'])!={r['trace_id'] for r in requests} or not set(native['spans'])<=set(native['selected_trace_ids']):
        raise ValueError('ordinary native/request identity mismatch')
    for spans in native['spans'].values():
        for span in spans:
            if set(span)!=set(SPAN_FIELDS)|{'attributes','resource_attributes'}:raise ValueError('native span field schema mismatch')
            if not set(span['resource_attributes'])<=RESOURCE_FIELDS:raise ValueError('undeclared native resource field')
            if any(k not in ('error','span.kind') and not k.startswith(ATTRIBUTE_PREFIXES) for k in span['attributes']):
                raise ValueError('undeclared native span attribute')
    if any(row['period']!='calibration' for row in requests):raise ValueError('consumer received closed period')
    graphs={}
    for operation in sorted({r['operation'] for r in requests}):
        rows=[r for r in requests if r['operation']==operation]
        node_roles={};edge_counts=Counter();edge_attempts=defaultdict(set)
        missing_parents=0;missing_traces=0;kind_counts=Counter();span_count=0;repeat_max=Counter()
        observed_instances=defaultdict(set);db_endpoint_keys=set()
        for row in rows:
            spans=native['spans'].get(row['trace_id'],[])
            missing_traces+=not bool(spans);span_count+=len(spans)
            indexed={s['span_id']:s for s in spans};per_request=Counter()
            for span in spans:
                service=span['service'];node_roles[service]='native_service';kind_counts[str(span['native_kind'])]+=1
                instance=span['resource_attributes'].get('service.instance.id')
                if instance:observed_instances[service].add(str(instance))
                parent=indexed.get(span['parent_id'])
                if span['parent_id'] and parent is None:missing_parents+=1
                if parent and parent['service']!=service:
                    edge=(parent['service'],service,'cross_service_parent')
                    edge_counts[edge]+=1;edge_attempts[edge].add(row['request_id']);per_request[edge]+=1
                attrs=span['attributes'];db_system=attrs.get('db.system.name',attrs.get('db.system'))
                if db_system and str(span['native_kind']).lower() in ('3','client','span_kind_client'):
                    address=attrs.get('server.address',attrs.get('net.peer.name'))
                    port=attrs.get('server.port',attrs.get('net.peer.port'))
                    database=attrs.get('db.namespace',attrs.get('db.name'))
                    if address is None or port is None or database is None:
                        node_roles['unresolved-observed-database-peer']='unsupported_peer_identity'
                        continue
                    key=json.dumps([db_system,address,str(port),database],separators=(',',':'))
                    target='observed-db-client-'+hashlib.sha256(key.encode()).hexdigest()[:16]
                    db_endpoint_keys.add(key);node_roles[target]='observed_client_peer_not_native_server'
                    edge=(service,target,'observed_db_client_peer')
                    edge_counts[edge]+=1;edge_attempts[edge].add(row['request_id']);per_request[edge]+=1
            for edge,count in per_request.items():repeat_max[edge]=max(repeat_max[edge],count)
        graphs[operation]=dict(external_attempts=len(rows),spans=span_count,attempts_without_native_trace=missing_traces,
            missing_parent_spans=missing_parents,native_kinds=dict(kind_counts),nodes=node_roles,
            edges=[dict(source=a,target=b,observation_type=k,supporting_spans=n,supporting_attempts=len(edge_attempts[(a,b,k)]),
                        max_occurrences_in_one_attempt=repeat_max[(a,b,k)]) for (a,b,k),n in sorted(edge_counts.items())],
            service_instances={k:sorted(v) for k,v in sorted(observed_instances.items())},
            observed_database_peer_count=len(db_endpoint_keys),
            declared_dependencies=declarations['source_declared_dependencies'].get(operation,[]),
            required_business_predicate_inferred=False,forecast=None,forecast_status='estimator_not_implemented_for_this_observation_law')
    statuses={replica:dict(Counter(str(row[f'replica_{replica}_backend_status'])+' / '+str(row[f'replica_{replica}_backend_check_status']) for row in probes)) for replica in ('a','b')}
    return dict(scope='ordinary_input_and_native_graph_inventory_only',main_campaigns=0,model_fits=0,
        original_input_seal=seal,manifest=manifest,graphs=graphs,probe_status_counts=statuses,
        compound_observation_law_qualified=False,application_prediction_qualified=False)


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','Application native inspection is remote-only'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.input.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    boundary=ReadBoundary(root,output);started=time.perf_counter();sys.addaudithook(boundary.hook)
    try:
        result=inventory(root)
        assert result['manifest']['external_attempts']==3600 and len(result['graphs'])==4
        assert all(row['external_attempts']==900 for row in result['graphs'].values())
    finally:boundary.active=False
    result['inventory_seconds']=time.perf_counter()-started
    write(output/'graph-input-inventory.json',result)
    write(output/'consumer-read-audit.json',dict(actual_data_reads=sorted(boundary.reads),blocked=boundary.blocked,
        physical_input_files=sorted(p.relative_to(root).as_posix() for p in boundary.allowed),
        legacy_learner_files_received=False,evaluator_files_received=False,network_subprocess_allowed=False,
        scope='enforced during seal verification and every input read/inventory calculation; report writes after hook disabled'))
    assert not boundary.blocked and boundary.reads=={str(p) for p in boundary.allowed}
    print(json.dumps(dict(operations=len(result['graphs']),actual_input_files=len(boundary.reads),model_fits=0)))


if __name__=='__main__':main()
