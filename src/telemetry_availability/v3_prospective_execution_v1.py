"""Prospective execution binding: frozen v2 numeric path with stage measurements.

Only metadata, expected planned census and timing differ from the technical v2.
Helpers and solver are imported unchanged; no test outcomes enter this function.
"""
from collections import Counter, defaultdict
import time
from .v3_application_execution_v2 import (
    BindingUnsupported, request_evidence, edge_id, declared_probe_layer,
    timestamp_ns, completion_observation, align_probe, identify, solve, digest)

METHOD = 'Gstar-ordinary-joint-execution-prospective-v1'


def fit_operation(data, operation, spec, identity):
    """Same v2 observations and numeric core, prospective identity and stage costs."""
    tick = time.perf_counter()
    declarations = data['declarations.json']; rows = [r for r in data['requests.json'] if r['operation'] == operation]
    if len(rows) != spec['expected_attempts']:
        raise ValueError('unexpected external attempt census')
    native = data['native.json']['spans']; evidence = []
    nodes = {}; edge_counts = Counter(); edge_attempts = Counter(); databases = {}
    for request in rows:
        e = request_evidence(request, native.get(request['trace_id'], []), declarations, spec)
        evidence.append(e); nodes.update(e['nodes']); databases.update(e['db_records'])
        for pair, records in e['calls'].items():
            edge_counts[pair] += len(records); edge_attempts[pair] += 1
    required_db_pairs = {pair for e in evidence for pair, records in e['calls'].items()
        if pair[1] in databases and pair[0] in set(spec['required_native_services']) | {spec['entry']}
        and any(not record['optional_for_completion'] for record in records)}
    required_db = {pair[1] for pair in required_db_pairs}
    required = set(spec['required_native_services']) | required_db
    if spec['entry'] not in nodes or not required <= set(nodes):
        raise BindingUnsupported('required declared service absent from discovered graph')
    unexpected = set(nodes) - set(spec['allowed_native_services']) - set(databases)
    if unexpected:
        raise BindingUnsupported('unclassified native services: ' + str(sorted(unexpected)))
    required_pairs = {tuple(x) for x in spec['required_native_pairs']}
    required_pairs.update(required_db_pairs)
    if not required_pairs <= set(edge_counts):
        raise BindingUnsupported('source-required relation absent from discovered graph')
    edges = [dict(id=edge_id(*pair), source=pair[0], target=pair[1], type='sync', factors=[],
        observation_relation='native_db_client' if pair[1] in databases else 'cross_service_parent',
        supporting_spans=n, supporting_attempts=edge_attempts[pair],
        completion_required=pair in required_pairs) for pair, n in sorted(edge_counts.items())]
    layer = declared_probe_layer(declarations)
    target = declarations['target_service']; controls = []; replicas = {name: [[]] for name in nodes}
    target_active = spec['target_calls'] > 0
    if target_active:
        if target not in required or sorted(declarations['replicas']) != ['a', 'b']:
            raise BindingUnsupported('declared target replica/control mismatch')
        replicas[target] = [['probe_a'], ['probe_b']]
        controls = [dict(service=target, selected_signals=['demand_a', 'demand_b'])]
    bindings = [dict(edge_id=edge_id(*pair), signal='completed:' + edge_id(*pair)) for pair in sorted(required_pairs)]
    probes = sorted(data['probes.json'], key=lambda p: timestamp_ns(p['observed_at']))
    times = [timestamp_ns(p['observed_at']) for p in probes]
    if len(times) != len(set(times)):
        raise ValueError('duplicate probe time')
    observations = []; reasons = defaultdict(Counter); masks = Counter(); missing_probe = 0; max_age = None
    for e in evidence:
        observation = dict(entry_completed=e['root_status'], timely=e['timely'])
        for pair in sorted(required_pairs):
            signal = 'completed:' + edge_id(*pair)
            value, reason = completion_observation(pair, e, spec)
            observation[signal] = value; reasons[signal][reason] += 1
        if target_active:
            state, age = align_probe(e['started_ns'], probes, times, spec['maximum_probe_age_ns'], layer)
            observation.update(state); observation.update({f'demand_{r}': e['demands'][r] for r in ('a', 'b')})
            missing_probe += age is None
            if age is not None:
                max_age = age if max_age is None else max(max_age, age)
        masks.update(k for k, v in observation.items() if v is None)
        observations.append(observation)
    assumptions = dict(spec['assumptions'],
        probe_layer=layer, probe_is_physical_capability=False, probe_alignment='latest completed observation at or before request start; bounded age',
        data_role=identity['data_role'],
        non_target_node_eligibility_fixed_true=sorted(name for name in nodes if name != target or not target_active),
        fixed_node_values_are_scope_assumptions=True, source_declared_contract=spec,
        business_labels_used_for_parameters=False, baseline_residual_q_used=False,
        calibration_duration_used_for_deadline=True, no_error_flag_used_as_success=False,
        graph_completeness='observed workload/source-declared class only; unseen branches are not recovered',
        joint_law='empirical request-weighted law including all attempts; no coordinate/call independence',
        transfer='unsupported without additional identifying assumptions for changed joint law')
    extraction_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    model = identify(dict(services=sorted(nodes), edges=edges), replicas,
        dict(id=operation, entry=spec['entry'], required=sorted(required), semantics='immediate_sync_all_required'),
        observations, controls, bindings, assumptions)
    model['identity'] = dict(identity, method=METHOD, operation=operation, scope='current')
    identification_seconds = time.perf_counter() - tick
    tick = time.perf_counter()
    result = solve(model)
    solve_seconds = time.perf_counter() - tick
    report = dict(identity=model['identity'], status=result['estimates']['execution']['status'],
        estimates=result['estimates'], result_sha256=digest(result), attempts=len(rows),
        native_spans=sum(e['native_spans'] for e in evidence), graph_nodes=nodes, graph_edges=edges,
        database_bindings=databases, missing_coordinate_counts=dict(masks),
        completion_evidence_counts={k: dict(v) for k, v in reasons.items()},
        missing_aligned_probe_attempts=missing_probe, maximum_used_probe_age_ns=max_age,
        observed_categories=len(model['observation_categories']), evaluated_states=result['evaluated_states'],
        assumptions=assumptions, business_adequacy_qualified=False)
    report['stage_seconds'] = dict(extraction=extraction_seconds, identification=identification_seconds, solve=solve_seconds)
    return model, report
