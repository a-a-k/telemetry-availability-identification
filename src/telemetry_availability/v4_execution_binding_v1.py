"""Candidate operation-window admission and logical-call completion binding.

Historical proxy verdicts are retained as auxiliary joint observations. They
are not re-labelled as instantaneous physical health. This candidate is an
explicit semantic revision motivated by primary counterexamples, not a fitted
correction using external semantic_success.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import time

from .graph_execution_model_v1 import identify, solve
from .v3_application_execution_v2 import (
    BindingUnsupported, request_evidence, edge_id, completion_observation,
    explicit_status, client_destination, span_interval, timestamp_ns,
    align_probe, declared_probe_layer,
)
from .v3_ordinary_identity_v2 import replica_identity, DS_ENTRIES

METHOD = 'Gstar-operation-window-admission-logical-completion-v1'


def native_admissions(evidence, declarations, request, spec):
    """Positive receiver evidence establishes reachability during this attempt.

    Failure to observe a receiver does not establish its inability to receive.
    A failed application response can still prove that a receiver was reached.
    """
    start = timestamp_ns(request['started_at'])
    stop = min(timestamp_ns(request['completed_at']), start+spec['deadline_ns'])
    result = {'admitted_a':None, 'admitted_b':None}; witnesses = defaultdict(list)
    for pair, records in evidence['calls'].items():
        if pair[1] != declarations['target_service']: continue
        for record in records:
            span = record['span']
            if record['optional_for_completion']: continue
            accepted_kind = span['server'] or (declarations['profile']=='deathstarbench_social_network'
                and not span['native_kind'] and span['operation'] in DS_ENTRIES)
            if not accepted_kind: continue
            replica = replica_identity(span, declarations)['replica']
            began, _ = span_interval(span)
            if replica in ('a','b') and start <= began <= stop:
                result['admitted_'+replica] = True
                witnesses[replica].append(span['span_id'])
    return result, dict(witnesses)


def logical_completion(pair, evidence, spans, spec, profile, operation):
    value, reason = completion_observation(pair, evidence, spec)
    retry_scope = (profile=='spring_petclinic_microservices' and operation=='create_visit'
                   and pair==('api-gateway','visits-service'))
    if not retry_scope or reason != 'explicit_required_client_failure': return value, reason
    clients = [s for s in spans if s['service']==pair[0]
        and client_destination(s, spec['client_route_names'])==pair[1]]
    clients.sort(key=lambda s: (span_interval(s)[0],s['span_id']))
    def status(s):
        raw = s['attributes'].get('http.response.status_code', s['attributes'].get('http.status_code'))
        return int(raw) if str(raw).isascii() and str(raw).isdecimal() else None
    # The actual source config permits one POST retry on 503. Other failures
    # retain their old meaning; incomplete retry evidence stays unknown.
    retry_failure = any(status(s)==503 and s['operation']=='POST' for s in clients)
    if not retry_failure: return value, reason
    if len(clients)!=2 or [status(s) for s in clients] != [503,201]:
        return None, 'declared_retry_outcome_not_fully_observed'
    first, final = clients
    if (any(s['operation']!='POST' for s in clients) or first['parent_id']!=final['parent_id']
        or span_interval(first)[1] > span_interval(final)[0] or explicit_status(final) is not True):
        return None, 'declared_retry_identity_or_order_not_verified'
    indexed = {s['span_id']:s for s in spans}
    def descends(span, ancestor):
        seen = set(); parent = span['parent_id']
        while parent in indexed and parent not in seen:
            if parent == ancestor: return True
            seen.add(parent); parent = indexed[parent]['parent_id']
        return parent == ancestor
    receivers = [r['span'] for r in evidence['calls'].get(pair, []) if not r['optional_for_completion']]
    if any(descends(s,first['span_id']) for s in receivers):
        return None, 'earlier_retry_receiver_effect_requires_separate_postcondition'
    successful = [s for s in receivers if descends(s,final['span_id']) and explicit_status(s) is True]
    if len(successful)!=1:
        return None, 'final_retry_receiver_not_uniquely_verified'
    adjusted = dict(evidence, client_failures=evidence['client_failures']-{pair})
    result, _ = completion_observation(pair, adjusted, spec)
    if result is not True: return None, 'final_logical_group_completion_not_verified'
    return True, 'declared_single_retry_503_then_201_with_one_observed_receiver'


def fit_operation(data, operation, spec, identity):
    tick = time.perf_counter(); declarations = data['declarations.json']
    requests = [r for r in data['requests.json'] if r['operation']==operation]
    if len(requests)!=spec['expected_attempts']: raise ValueError('unexpected attempt census')
    evidence = []; nodes = {}; databases = {}; edge_counts = Counter(); edge_attempts = Counter()
    for request in requests:
        spans = data['native.json']['spans'].get(request['trace_id'], [])
        e = request_evidence(request, spans, declarations, spec); evidence.append((request,spans,e))
        nodes.update(e['nodes']); databases.update(e['db_records'])
        for pair, records in e['calls'].items(): edge_counts[pair]+=len(records); edge_attempts[pair]+=1
    required_db_pairs = {pair for _,_,e in evidence for pair,records in e['calls'].items()
        if pair[1] in databases and pair[0] in set(spec['required_native_services'])|{spec['entry']}
        and any(not r['optional_for_completion'] for r in records)}
    required = set(spec['required_native_services'])|{pair[1] for pair in required_db_pairs}
    if spec['entry'] not in nodes or not required <= set(nodes):
        raise BindingUnsupported('required declared service absent from discovered graph')
    unexpected = set(nodes)-set(spec['allowed_native_services'])-set(databases)
    if unexpected: raise BindingUnsupported('unclassified native services: '+str(sorted(unexpected)))
    pairs = {tuple(p) for p in spec['required_native_pairs']}|required_db_pairs
    if not pairs <= set(edge_counts): raise BindingUnsupported('source-required relation absent from discovered graph')
    edges = [dict(id=edge_id(*p),source=p[0],target=p[1],type='sync',factors=[],
        observation_relation='native_db_client' if p[1] in databases else 'cross_service_parent',
        supporting_spans=n,supporting_attempts=edge_attempts[p],completion_required=p in pairs)
        for p,n in sorted(edge_counts.items())]
    active = spec['target_calls']>0; replicas = {name:[[]] for name in nodes}; controls=[]
    target = declarations['target_service']
    if active:
        if target not in required or sorted(declarations['replicas'])!=['a','b']:
            raise BindingUnsupported('declared target replica/control mismatch')
        replicas[target]=[['admitted_a'],['admitted_b']]
        controls=[dict(service=target,selected_signals=['demand_a','demand_b'])]
    bindings=[dict(edge_id=edge_id(*p),signal='completed:'+edge_id(*p)) for p in sorted(pairs)]
    observations=[]; diagnostics=[]; reasons=defaultdict(Counter); masks=Counter(); joint=Counter()
    probes=sorted(data['probes.json'],key=lambda p:timestamp_ns(p['observed_at']))
    times=[timestamp_ns(p['observed_at']) for p in probes];layer=declared_probe_layer(declarations)
    if len(times)!=len(set(times)): raise ValueError('duplicate auxiliary probe timestamp')
    for request,spans,e in evidence:
        observation=dict(entry_completed=e['root_status'],timely=e['timely']); row_reasons={}
        for pair in sorted(pairs):
            signal='completed:'+edge_id(*pair)
            observation[signal],why=logical_completion(pair,e,spans,spec,identity['application'],operation)
            reasons[signal][why]+=1;row_reasons[signal]=why
        admission_witnesses={}
        if active:
            admissions,admission_witnesses=native_admissions(e,declarations,request,spec)
            observation.update(admissions);observation.update({'demand_'+r:e['demands'][r] for r in ('a','b')})
        historical,age=align_probe(e['started_ns'],probes,times,spec['maximum_probe_age_ns'],layer)
        masks.update(k for k,v in observation.items() if v is None);observations.append(observation)
        joint[(tuple(sorted(observation.items())),tuple(sorted(historical.items())))]+=1
        diagnostics.append(dict(request_id=request['request_id'],trace_id=request['trace_id'],
            observation=observation,historical_probe_context=historical,legacy_sample_label_age_ns=age,
            native_admission_witnesses=admission_witnesses,completion_reasons=row_reasons))
    assumptions=dict(spec['assumptions'], legacy_source_declared_contract=deepcopy(spec),
        eligibility='operation-window ability to receive a mandatory invocation; native receiver evidence certifies only true',
        historical_proxy_verdict_is_necessary_for_success=False, historical_proxy_values_retained_as_joint_context=True,
        historical_proxy_time_is_sampler_start_not_check_completion=True,
        native_absence_imputed_as_unavailability=False, business_labels_used_for_parameters=False,
        admission_positive_witness_may_have_failed_application_response=True,
        petclinic_create_visit_retry='one POST retry on HTTP 503; logical group outcome, not AND of transport attempts',
        persistence_semantics='not established by HTTP 201 or by missing retry receiver; requires declared postcondition and independent validation',
        future_forecast='requires invariance of relevant joint observation/state law',
        non_target_node_eligibility_fixed_true=sorted(n for n in nodes if n!=target or not active),
        additional_physical_feasibility_constraints_imposed=False,
        sharpness_scope='declared finite mask-fiber law family; no claim of physical realizability of every state')
    if identity['application']=='spring_petclinic_microservices' and operation=='create_visit':
        assumptions['retries']='all logical mandatory groups must complete; one source-declared POST retry on 503 is resolved within its group'
    extraction_seconds=time.perf_counter()-tick;tick=time.perf_counter()
    model=identify(dict(services=sorted(nodes),edges=edges),replicas,
        dict(id=operation,entry=spec['entry'],required=sorted(required),semantics='immediate_sync_all_required'),
        observations,controls,bindings,assumptions)
    model['identity']=dict(identity,method=METHOD,operation=operation,scope='current')
    model['auxiliary_joint_categories']=[dict(observation=dict(obs),historical_probe=dict(h),count=n)
        for (obs,h),n in sorted(joint.items(),key=lambda row:str(row[0]))]
    identification_seconds=time.perf_counter()-tick;tick=time.perf_counter();result=solve(model)
    report=dict(identity=model['identity'],estimates=result['estimates'],attempts=len(requests),
        completion_evidence_counts={k:dict(v) for k,v in reasons.items()},missing_coordinate_counts=dict(masks),
        assumptions=assumptions,independently_confirmed=False,
        stage_seconds=dict(extraction=extraction_seconds,identification=identification_seconds,solve=time.perf_counter()-tick))
    return model,report,diagnostics
