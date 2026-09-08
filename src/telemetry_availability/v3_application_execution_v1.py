"""Ten-operation source-declared execution binding; full processing is GHA-only."""
from bisect import bisect_right
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit

from .existing_application_graph_observation import bind_database
from .graph_execution_model_v1 import identify, solve
from .graph_observation_model import probe_verdict
from .health_prefix_audit_v3 import restore
from .v3_execution_observation_audit_v1 import boundary_context, span_interval, timestamp_ns
from .v3_graph_input_inventory import ReadBoundary
from .v3_ordinary_identity_v2 import DS_ENTRIES, load_bundle, replica_identity
from .v3_primary_projection import FILES, read, write, sha

CONFIG = Path('configs/v3_application_execution_v1.json')
METHOD = 'G-EXEC-ordinary-joint-technical-v1'


class BindingUnsupported(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def explicit_status(span):
    """Only an explicit protocol code certifies success; UNSET/error absence cannot."""
    attrs = span['attributes']; success = []; failure = span['error_tag'] or span['error_status']
    for key in ('http.response.status_code', 'http.status_code', 'rpc.grpc.status_code',
                'rpc.response.status_code', 'rpc.status_code'):
        if key not in attrs:
            continue
        value = attrs[key]
        if type(value) is int:
            code = value
        elif isinstance(value, str) and value.isascii() and value.isdecimal():
            code = int(value)
        else:
            continue
        okay = 200 <= code < 300 if key.startswith('http.') else code == 0
        success.append(okay); failure = failure or not okay
    return False if failure else (True if success and all(success) else None)


def conjunction(values):
    values = list(values)
    return False if False in values else (True if values and all(v is True for v in values) else None)


def edge_id(source, target):
    return json.dumps([source, target], separators=(',', ':'))


def db_identity(span, peers):
    attrs = span['attributes']; system = attrs.get('db.system.name', attrs.get('db.system'))
    if not system or str(span['native_kind']).lower() not in ('3', 'client', 'span_kind_client'):
        return None
    observed = dict(system=system, address=attrs.get('server.address', attrs.get('net.peer.name')),
        port=attrs.get('server.port', attrs.get('net.peer.port')),
        database=attrs.get('db.namespace', attrs.get('db.name')))
    if all(v is not None for v in observed.values()):
        # Preserve the same explicit peer binding convention when all fields exist.
        return bind_database(span, [dict(owner=span['service'], **observed)])
    try:
        return bind_database(span, peers)
    except ValueError as exc:
        raise BindingUnsupported(str(exc)) from exc


def ignored_call(span, suffixes):
    names = [span['operation'], str(span['attributes'].get('rpc.method', ''))]
    return any(name == suffix or name.endswith('/' + suffix) or name.endswith('.' + suffix)
               for name in names for suffix in suffixes)


def client_destination(span, declared_names):
    if str(span['native_kind']).lower() not in ('3', 'client', 'span_kind_client'):
        return None
    attrs = span['attributes']; names = set()
    for key in ('server.address', 'net.peer.name', 'peer.service'):
        if key in attrs:
            names.add(str(attrs[key]))
    for key in ('url.full', 'http.url'):
        if key in attrs:
            names.add(urlsplit(str(attrs[key])).hostname)
    matches = names & set(declared_names)
    return next(iter(matches)) if len(matches) == 1 else None


def request_evidence(request, spans, declarations, spec):
    trace, parent_id = boundary_context(declarations['profile'], request['request_id'])
    if request['trace_id'] != trace:
        raise ValueError('request trace context mismatch')
    indexed = {s['span_id']: s for s in spans}
    if len(indexed) != len(spans):
        raise ValueError('duplicate native span identity')
    if any(s['parent_id'] not in indexed and s['parent_id'] != parent_id for s in spans):
        raise BindingUnsupported('unexplained native parent boundary')
    roots = [s for s in spans if s['parent_id'] == parent_id]
    if any(s['service'] != spec['entry'] for s in roots):
        raise BindingUnsupported('unexpected external entry service')
    root_status = conjunction(explicit_status(s) for s in roots)
    if root_status is True and len(roots) != spec['external_roots']:
        root_status = None
    calls = defaultdict(list); db_records = {}; nodes = {s['service']: 'native_service' for s in spans}
    entries = []; unclassified = 0; client_failures = set()
    for span in spans:
        span_interval(span)
        parent = indexed.get(span['parent_id'])
        if parent and parent['service'] != span['service']:
            pair = (parent['service'], span['service'])
            calls[pair].append(dict(span=span, parent=parent, relation='cross_service_parent'))
            if span['service'] == declarations['target_service']:
                if span['server'] or (declarations['profile'] == 'deathstarbench_social_network' and
                        not span['native_kind'] and span['operation'] in DS_ENTRIES):
                    entries.append(span)
                else:
                    unclassified += 1
        db = db_identity(span, spec['database_peers'])
        if db:
            node, provenance = db; nodes[node] = 'native_db_client_with_explicit_peer_binding'
            calls[(span['service'], node)].append(dict(span=span, parent=None, relation='native_db_client'))
            db_records[node] = provenance
        destination = client_destination(span, spec['client_route_names'])
        if destination and explicit_status(span) is False:
            client_failures.add((span['service'], destination))
    labels = [replica_identity(s, declarations)['replica'] for s in entries]
    complete = (len(entries) == spec['target_calls'] and all(x is not None for x in labels) and not unclassified)
    demand = {r: True if r in labels else (False if complete else None) for r in ('a', 'b')}
    started = timestamp_ns(request['started_at']); ended = timestamp_ns(request['completed_at'])
    if ended < started:
        raise ValueError('negative external duration')
    return dict(root_status=root_status, calls=dict(calls), nodes=nodes, db_records=db_records,
        demands=demand, complete_target_identity=complete, client_failures=client_failures,
        timely=ended - started <= spec['deadline_ns'], started_ns=started,
        native_spans=len(spans), external_roots=len(roots))


def completion_observation(pair, evidence, spec):
    records = evidence['calls'].get(pair, [])
    ignored = spec['ignored_rpc_methods_by_pair'].get(edge_id(*pair), [])
    records = [r for r in records if not ignored_call(r['span'], ignored)]
    if pair in evidence['client_failures']:
        return False, 'explicit_required_client_failure'
    statuses = []
    for record in records:
        values = [explicit_status(record['span'])]
        if record['parent'] is not None:
            values.append(explicit_status(record['parent']))
        statuses.append(False if False in values else (True if True in values else None))
    if False in statuses:
        return False, 'explicit_required_call_failure'
    minimum = spec['minimum_calls_by_pair'].get(edge_id(*pair), 1)
    if len(records) < minimum:
        return None, 'required_group_not_fully_observed'
    if statuses and all(x is True for x in statuses):
        return True, 'explicit_native_protocol_success'
    if evidence['root_status'] is True and spec['source_error_propagation_assumed']:
        return True, 'observed_required_group_and_source_propagation_certificate'
    return None, 'no_explicit_completion_certificate'


def align_probe(started, probes, times, maximum_age_ns):
    index = bisect_right(times, started) - 1
    if index < 0 or started - times[index] > maximum_age_ns:
        return dict(probe_a=None, probe_b=None), None
    sample = probes[index]
    return {f'probe_{r}': probe_verdict(sample[f'replica_{r}_backend_status'],
            sample[f'replica_{r}_backend_check_status'], layer='L4')['value'] for r in ('a', 'b')}, started - times[index]


def fit_operation(data, operation, spec):
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
    required = set(spec['required_native_services']) | set(databases)
    if spec['entry'] not in nodes or not required <= set(nodes):
        raise BindingUnsupported('required declared service absent from discovered graph')
    unexpected = set(nodes) - set(spec['allowed_native_services']) - set(databases)
    if unexpected:
        raise BindingUnsupported('unclassified native services: ' + str(sorted(unexpected)))
    required_pairs = {tuple(x) for x in spec['required_native_pairs']}
    required_pairs.update(pair for pair in edge_counts if pair[1] in databases)
    if not required_pairs <= set(edge_counts):
        raise BindingUnsupported('source-required relation absent from discovered graph')
    edges = [dict(id=edge_id(*pair), source=pair[0], target=pair[1], type='sync', factors=[],
        observation_relation='native_db_client' if pair[1] in databases else 'cross_service_parent',
        supporting_spans=n, supporting_attempts=edge_attempts[pair],
        completion_required=pair in required_pairs) for pair, n in sorted(edge_counts.items())]
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
            state, age = align_probe(e['started_ns'], probes, times, spec['maximum_probe_age_ns'])
            observation.update(state); observation.update({f'demand_{r}': e['demands'][r] for r in ('a', 'b')})
            missing_probe += age is None
            if age is not None:
                max_age = age if max_age is None else max(max_age, age)
        masks.update(k for k, v in observation.items() if v is None)
        observations.append(observation)
    assumptions = dict(spec['assumptions'],
        l4_probe_is_physical_capability=False, probe_alignment='latest completed observation at or before request start; bounded age',
        data_role='previously opened development calibration',
        non_target_node_eligibility_fixed_true=sorted(name for name in nodes if name != target or not target_active),
        fixed_node_values_are_scope_assumptions=True, source_declared_contract=spec,
        business_labels_used_for_parameters=False, baseline_residual_q_used=False,
        calibration_duration_used_for_deadline=True, no_error_flag_used_as_success=False,
        graph_completeness='observed workload/source-declared class only; unseen branches are not recovered',
        joint_law='empirical request-weighted law including all attempts; no coordinate/call independence',
        transfer='unsupported without additional identifying assumptions for changed joint law')
    model = identify(dict(services=sorted(nodes), edges=edges), replicas,
        dict(id=operation, entry=spec['entry'], required=sorted(required), semantics='immediate_sync_all_required'),
        observations, controls, bindings, assumptions)
    model['identity'] = dict(method=METHOD, profile=declarations['profile'], operation=operation,
        placement=declarations['placement'], scope='current', main_campaigns=0)
    result = solve(model)
    report = dict(identity=model['identity'], status=result['estimates']['execution']['status'],
        estimates=result['estimates'], result_sha256=digest(result), attempts=len(rows),
        native_spans=sum(e['native_spans'] for e in evidence), graph_nodes=nodes, graph_edges=edges,
        database_bindings=databases, missing_coordinate_counts=dict(masks),
        completion_evidence_counts={k: dict(v) for k, v in reasons.items()},
        missing_aligned_probe_attempts=missing_probe, maximum_used_probe_age_ns=max_age,
        observed_categories=len(model['observation_categories']), evaluated_states=result['evaluated_states'],
        assumptions=assumptions, business_adequacy_qualified=False)
    return model, report


def replay_operation(model):
    result = solve(model); equivalent = deepcopy(model); equivalent['graph']['edges'].reverse()
    assert solve(equivalent) == result
    mutated = 0
    for binding in model['required_edge_completions']:
        altered = deepcopy(model)
        altered['graph']['edges'] = [e for e in altered['graph']['edges'] if e['id'] != binding['edge_id']]
        changed = solve(altered)['estimates']['execution']
        assert changed['lower'] == changed['upper'] == 0
        mutated += 1
    return dict(identity=model['identity'], estimates=result['estimates'], result_sha256=digest(result),
        required_edge_removal_controls=mutated, equivalent_edge_order_preserves_result=True,
        business_adequacy_qualified=False)


def prepare(settings, profile):
    archive, metadata = restore(settings['profiles'][profile]['artifact'])
    assert set(archive.namelist()) == FILES | {'seal.json'}
    root = Path('workflow-results/ordinary'); root.mkdir(parents=True, exist_ok=True)
    for name in sorted(FILES | {'seal.json'}):
        (root/name).write_bytes(archive.read(name))
    archive.close(); _, seal = load_bundle(root)
    write(Path('workflow-results/preparation/source-audit.json'), dict(artifact=metadata,
        seal=seal, main_campaigns=0, full_source_payload_retained_locally=False))


def consume(settings, profile, is_replay):
    root = Path('workflow-input/model' if is_replay else 'workflow-input/ordinary').resolve()
    output = Path('workflow-results/replay' if is_replay else 'workflow-results/fit').resolve()
    output.mkdir(parents=True, exist_ok=True); boundary = ReadBoundary(root, output)
    if is_replay:
        boundary.allowed = {root/'model.json', root/'seal.json'}
    tick = time.perf_counter(); sys.addaudithook(boundary.hook)
    models = {}; reports = {}
    try:
        if is_replay:
            seal = read(root/'seal.json'); saved = read(root/'model.json')
            assert seal['files'] == {'model.json': sha(root/'model.json')}
            assert saved['profile'] == profile and saved['method'] == METHOD
            for op, model in saved['models'].items():
                reports[op] = replay_operation(model)
                assert reports[op]['result_sha256'] == saved['calculation_hashes'][op]
            absences = saved['absences']
        else:
            data, seal = load_bundle(root)
            assert data['declarations.json']['profile'] == profile
            operations = settings['profiles'][profile]['operations']
            assert set(operations) == {r['operation'] for r in data['requests.json']}
            absences = {}
            for op, spec in operations.items():
                try:
                    models[op], reports[op] = fit_operation(data, op, spec)
                except BindingUnsupported as exc:
                    absences[op] = dict(status='unsupported', reason=str(exc), prediction=None,
                        attempts=sum(r['operation'] == op for r in data['requests.json']))
        assert not boundary.blocked and boundary.reads == {str(p) for p in boundary.allowed}
    finally:
        boundary.active = False
        write(output/'read-audit.json', dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
            is_replay=is_replay, physical_ordinary_or_model_role_only=True, test_or_controller_received=False))
    if not is_replay:
        saved = dict(method=METHOD, profile=profile, models=models, absences=absences, input_seal=seal,
            calculation_hashes={op: r['result_sha256'] for op, r in reports.items()},
            protocol_sha256=sha(CONFIG), head=os.environ['GITHUB_SHA'])
        path = Path('workflow-results/models/model.json'); write(path, saved)
        write(path.parent/'seal.json', dict(method=METHOD, files={'model.json': sha(path)}))
    write(output/'results.json', dict(method=METHOD, profile=profile, operations=reports, absences=absences,
        input_seal=seal, main_campaigns=0, head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
        protocol_sha256=sha(CONFIG), elapsed_seconds=time.perf_counter()-tick,
        independent_accuracy_evaluation=False, all_operations_accounted=len(reports)+len(absences)))


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Full application work is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'build', 'replay')); parser.add_argument('--profile', required=True)
    args = parser.parse_args(); settings = read(CONFIG)
    for record in settings['repository_locks']:
        assert sha(Path(record['path'])) == record['sha256'], record['path']
    if args.stage == 'prepare':
        prepare(settings, args.profile)
    else:
        consume(settings, args.profile, args.stage == 'replay')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        stage = {'prepare': 'preparation', 'build': 'fit', 'replay': 'replay'}.get(sys.argv[1], 'failure')
        write(Path('workflow-results')/stage/'failure.json', dict(type=type(exc).__name__, message=str(exc)))
        raise
