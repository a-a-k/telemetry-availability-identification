"""Versioned ordinary graph build/replay for two retained normal-state examples."""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from .health_prefix_audit_v3 import restore
from .graph_observation_model import identify, evaluate, probe_verdict
from .live_fault_campaign import make_trace_context
from .v3_primary_projection import FILES, VERSION, read, write, sha, verify_bundle
from .v3_graph_input_inventory import inventory, ReadBoundary

CONFIG = Path('configs/existing_application_graph_observation.json')
METHOD = 'G-OBS-existing-normal-technical-v1'


def configuration():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'application work is GitHub Actions only'
    value = read(CONFIG)
    for item in value['repository_locks']:
        assert sha(Path(item['path'])) == item['sha256'], item['path']
    return value


def bind_database(span, declarations):
    """Complete a partial native CLIENT identity only by a unique declared peer."""
    attrs = span['attributes']
    observed = dict(system=attrs.get('db.system.name', attrs.get('db.system')),
        address=attrs.get('server.address', attrs.get('net.peer.name')),
        port=attrs.get('server.port', attrs.get('net.peer.port')),
        database=attrs.get('db.namespace', attrs.get('db.name')))
    if not observed['system'] or str(span['native_kind']).lower() not in ('3', 'client', 'span_kind_client'):
        raise ValueError('database relation must originate in an actual native DB CLIENT span')
    candidates = [item for item in declarations if item['owner'] == span['service'] and
        all(value is None or str(value) == str(item[key]) for key, value in observed.items())]
    if len(candidates) != 1:
        raise ValueError('native database identity does not uniquely select declared peer: ' +
                         json.dumps(dict(owner=span['service'], observed=observed, matches=len(candidates))))
    peer = candidates[0]
    key = json.dumps([peer[k] for k in ('system', 'address', 'port', 'database')], separators=(',', ':'))
    node = 'declared-db-client-' + hashlib.sha256(key.encode()).hexdigest()[:16]
    return node, dict(owner=span['service'], observed=observed,
        declared={k:peer[k] for k in ('system', 'address', 'port', 'database')},
        completed_fields=sorted(k for k, value in observed.items() if value is None),
        provenance='native DB CLIENT relation with explicit declared endpoint completion; not native DB SERVER')


def prepare(settings, profile):
    spec = settings['profiles'][profile]
    archive, metadata = restore(spec['artifact'])
    names = {n for n in archive.namelist() if not n.endswith('/')}
    assert names == FILES | {'seal.json'}
    source = Path('workflow-input/source-ordinary')
    for name in sorted(names):
        path = source/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(archive.read(name))
    archive.close()
    old_seal = verify_bundle(source)
    data = {name:read(source/name) for name in FILES}
    declarations = data['declarations.json']
    assert declarations['profile'] == profile and declarations['placement'] == 'colocated'
    assert declarations['backend_success_check_statuses'] == ['L4OK']
    declarations['dependency_provenance'] = spec['declared_semantics']
    declarations['known_non_target_dependencies'] = spec['declared_semantics']['fixed_live_native_services']
    operation = spec['declared_semantics']['operation']
    declarations['source_declared_dependencies'][operation] = spec['declared_semantics']['required_native_services']
    data['manifest.json']['declaration_adapter'] = 'explicit-source-semantic-declarations-v1'
    data['manifest.json']['source_ordinary_seal'] = old_seal
    output = Path('workflow-results/ordinary')
    for name, value in data.items():
        write(output/name, value)
    write(output/'seal.json', dict(version=VERSION, files={name:sha(output/name) for name in sorted(FILES)}))
    verify_bundle(output)
    write(Path('workflow-results/source/source-audit.json'), dict(artifact=metadata,
        original_seal=old_seal, enriched_seal=read(output/'seal.json'),
        unchanged_data_files=['requests.json', 'probes.json', 'native.json'],
        declarations=spec['declared_semantics'], estimator_fits=0, main_campaigns=0))
    for name in ('requests.json', 'probes.json', 'native.json'):
        assert sha(output/name) == old_seal['files'][name], name


def fit(root):
    info = inventory(root)
    declarations = read(root/'declarations.json'); native = read(root/'native.json')
    requests = read(root/'requests.json'); probes = read(root/'probes.json')
    spec = declarations['dependency_provenance']; profile = declarations['profile']
    operation = spec['operation']; selected = [r for r in requests if r['operation'] == operation]
    assert len(selected) == 80 and declarations['backend_success_check_statuses'] == ['L4OK']
    graph_info = info['graphs'][operation]
    assert not graph_info['attempts_without_native_trace']
    target = declarations['target_service']; replicas = sorted(declarations['replicas'])
    assert replicas == ['a', 'b']
    nodes = {name:role for name, role in graph_info['nodes'].items() if role == 'native_service'}
    assert set(nodes) <= set(spec['fixed_live_native_services']) | {target}
    edges = [dict(source=e['source'], target=e['target'], type='sync', factors=[],
                  observed_relation=e['observation_type'], supporting_attempts=e['supporting_attempts'],
                  supporting_spans=e['supporting_spans'])
             for e in graph_info['edges'] if e['observation_type'] == 'cross_service_parent']
    db_records = {}; db_attempts = defaultdict(set); db_counts = Counter(); roots = 0
    for request in selected:
        trace, header, context = make_trace_context(profile, request['request_id'])
        assert request['trace_id'] == trace
        expected = context.split(':')[1] if header == 'uber-trace-id' else context.split('-')[2]
        spans = native['spans'][trace]; ids = {s['span_id'] for s in spans}; found = []
        for span in spans:
            if span['parent_id'] not in ids:
                if span['parent_id'] != expected or span['service'] != spec['entry']:
                    raise ValueError('unexplained external boundary or missing native parent')
                found.append(span)
            attrs = span['attributes']
            if attrs.get('db.system.name', attrs.get('db.system')) and str(span['native_kind']).lower() in ('3', 'client', 'span_kind_client'):
                node, record = bind_database(span, spec['database_peers'])
                nodes[node] = 'native_client_relation_with_declared_endpoint'
                key = (span['service'], node)
                db_attempts[key].add(request['request_id']); db_counts[key] += 1
                signature = json.dumps(record, sort_keys=True)
                db_records[signature] = record
        if len(found) != 1:
            raise ValueError('selected single-call technical event has unexpected root multiplicity')
        roots += 1
    for (owner, node), count in sorted(db_counts.items()):
        edges.append(dict(source=owner, target=node, type='sync', factors=[],
            observed_relation='native_db_client_with_declared_endpoint', supporting_spans=count,
            supporting_attempts=len(db_attempts[(owner, node)])))
    if spec['database_peers'] and not db_records:
        raise ValueError('declared database dependency lacks observed native CLIENT relation')
    required = sorted(set(spec['required_native_services']) | {node for _, node in db_counts})
    assert set([spec['entry'], *required]) <= set(nodes)
    assert target in required and all(name != spec['entry'] for name in required)
    signals = ['probe_'+r for r in replicas]
    gates = {name:[[]] for name in nodes}; gates[target] = [[signal] for signal in signals]
    observations = []; unknown = Counter(); phases = Counter()
    for row in probes:
        observation = {}
        for replica, signal in zip(replicas, signals):
            verdict = probe_verdict(row['replica_'+replica+'_backend_status'],
                                    row['replica_'+replica+'_backend_check_status'], layer='L4')
            observation[signal] = verdict['value']; unknown[replica] += verdict['value'] is None
            phases[replica] += verdict['check_in_progress']
        observations.append(observation)
    assumptions = dict(supported_event='ideal static synchronous reachability of explicitly required targets',
        business_event=spec['business_event'], signal_meaning='last HAProxy L4 transport eligibility, not application readiness',
        routing='ideal eligible-replica choice; no delay, queue, retry or recovery process',
        state_law='empirical joint masked probe categories; no independence or MCAR imputation',
        sampling='uniform probe ticks in a 60-second normal development window; not future population identification',
        fixed_live_nodes=sorted(name for name in nodes if name != target),
        unmeasured_dependency_conditions=spec['unmeasured_dependency_conditions'],
        fixed_live_and_successful_dependencies_are_assumptions=True,
        edge_law='source-declared synchronous completion; cross-service parent graph plus explicit DB CLIENT binding',
        missingness='composite legacy collector; informative masks possible',
        future_stationarity_assumed_for_forecast=True, state_static_during_operation_assumed=True,
        native_replica_instance_identity='unavailable; R uses declared replica names bound to ordinary proxy server labels',
        baseline_residual_q_used=False, calibration_business_outcomes_used_for_parameters=False,
        business_adequacy_tested=False, main_method_selected=False)
    model = identify(dict(services=sorted(nodes), edges=edges), gates,
        dict(id=operation, entry=spec['entry'], required=required, semantics='immediate_sync_all_required'),
        signals, observations, assumptions)
    model['identity'] = dict(method=METHOD, profile=profile, operation=operation,
        placement=declarations['placement'], data_role='retained_normal_technical', scope='current',
        source_ordinary_seal=info['original_input_seal'])
    report = dict(identity=model['identity'], prediction=evaluate(model), external_attempts=len(selected),
        probe_ticks=len(probes), native_spans=graph_info['spans'], graph_nodes=nodes, graph_edges=edges,
        verified_external_boundary_roots=roots, unexpected_missing_parents=0,
        database_identity_bindings=list(db_records.values()),
        unknown_verdict_counts=dict(unknown), in_progress_counts=dict(phases), assumptions=assumptions,
        transfer_status='unsupported without assumptions identifying the changed target law', main_campaigns=0)
    return model, report


def replay(model):
    prediction = evaluate(model)
    equivalent = deepcopy(model); equivalent['graph']['edges'].reverse()
    assert evaluate(equivalent) == prediction
    controls = {}
    for target in model['operation']['required']:
        changed = deepcopy(model)
        changed['graph']['edges'] = [e for e in changed['graph']['edges'] if e['target'] != target]
        result = evaluate(changed)
        assert result['lower'] == result['upper'] == 0 and prediction['upper'] > 0
        controls[target] = result
    return dict(identity=model['identity'], prediction=prediction, main_campaigns=0,
        structural_control=dict(remove_incoming_required_edges=controls, equivalent_edge_order_preserves_prediction=True),
        replay_inputs=['model.json'], application_adequacy_tested=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'build', 'replay')); parser.add_argument('--profile', required=True)
    args = parser.parse_args(); settings = configuration(); assert args.profile in settings['profiles']
    if args.stage == 'prepare':
        prepare(settings, args.profile); return
    is_replay = args.stage == 'replay'
    root = Path('workflow-input/model' if is_replay else 'workflow-input/ordinary').resolve()
    reports = Path('workflow-results/replay' if is_replay else 'workflow-results/fit').resolve()
    reports.mkdir(parents=True, exist_ok=True); boundary = ReadBoundary(root, reports)
    if is_replay:
        boundary.allowed = {root/'model.json'}
    tick = time.perf_counter(); sys.addaudithook(boundary.hook)
    try:
        if is_replay:
            model = read(root/'model.json'); report = replay(model); report['model_sha256'] = sha(root/'model.json')
        else:
            model, report = fit(root)
        assert model['identity']['profile'] == args.profile
        assert not boundary.blocked and boundary.reads == {str(p) for p in boundary.allowed}
    finally:
        boundary.active = False
    report['elapsed_seconds'] = time.perf_counter()-tick
    if not is_replay:
        path = Path('workflow-results/models/model.json'); write(path, model)
        report['model_sha256'] = sha(path)
        write(path.parent/'seal.json', dict(method=METHOD, files={'model.json':sha(path)}))
    write(reports/('replay.json' if is_replay else 'fit.json'), report)
    write(reports/'read-audit.json', dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
        replay=is_replay, legacy_or_evaluator_received=False, enforced_during_all_input_reads_and_computation=True))


if __name__ == '__main__':
    main()
