"""Bounded V3 graph-chain demonstrator; not an admitted application estimator.

The metadata/observation assumptions are specified in GRAPH_CHAIN_V3.md.
Only direct, independently masked primitive-state observations are supported.
No truth, fault schedule, test outcome, or baseline residual enters this module.
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import product
import json
from math import fsum, prod
from pathlib import Path

VERSION = "graph-replay-v3-control-1"
MAX_FACTORS = 16


class Unsupported(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Unsupported(message)


def build_model(metadata: dict, traces: list[dict], observations: list[dict]) -> dict:
    """Extract edges from parent IDs, estimate marginals, persist their provenance."""
    require(metadata['purpose'] == 'controlled_demonstrator', 'application adapter not qualified')
    require(metadata['trace_coverage'] == 'declared_complete_control', 'unknown graph completeness')
    require(metadata['routing'] == 'ideal_static_reachability', 'unsupported routing')
    require(metadata['repeat_semantics'] == 'same_static_state', 'unsupported repeated execution')
    law = metadata['observation_law']
    require(law['version'] == 'direct-primitive-mcar-v1', 'unsupported observation law')
    require(law['conditional_on_success'] is False, 'success-conditioned observations unsupported')
    require(law['mask_independent_of_state'] is True, 'informative missingness unsupported')
    require(metadata['state_law'] == 'independent_bernoulli_primitives', 'unsupported state law')
    ids = metadata['primitive_ids']
    require(0 < len(ids) <= MAX_FACTORS and len(ids) == len(set(ids)), 'invalid primitive IDs/count')
    known = set(ids)
    measured = set(law['measured_primitives'])
    require(measured <= known, 'unknown measured primitive')
    services = metadata['replicas']
    require(bool(services), 'empty service set')
    for replicas in services.values():
        require(bool(replicas), 'service without replicas')
        for gates in replicas:
            require(len(gates) == len(set(gates)) and set(gates) <= known, 'invalid replica gate')
    operation = metadata['operation']
    require(operation['semantics'] == 'immediate_sync_all_required', 'unsupported predicate')
    require(operation['entry'] in services and bool(operation['required']), 'invalid operation')
    require(set(operation['required']) <= set(services), 'unknown required target')
    seen_services, edges, counts = set(), set(), Counter()
    indexed = {}
    for span in traces:
        key = (span['trace_id'], span['span_id'])
        require(key not in indexed, 'duplicate span ID')
        require(span['service'] in services, 'undeclared service')
        require(span['operation_id'] == operation['id'], 'mixed operation traces')
        indexed[key] = span
        seen_services.add(span['service'])
    for key, span in indexed.items():
        parent_id = span['parent_span_id']
        if parent_id is None:
            require(span['service'] == operation['entry'], 'root differs from declared entry')
            continue
        parent = indexed.get((span['trace_id'], parent_id))
        require(parent is not None, 'missing parent span')
        require(span['edge_type'] in ('sync', 'async'), 'unknown edge type')
        # Parent cycles are malformed traces, even though service cycles are allowed.
        ancestors, cursor = {key}, parent
        while cursor is not None:
            cursor_key = (cursor['trace_id'], cursor['span_id'])
            require(cursor_key not in ancestors, 'cyclic span ancestry')
            ancestors.add(cursor_key)
            cursor = indexed.get((cursor['trace_id'], cursor['parent_span_id']))
        if parent['service'] != span['service']:
            edge = (parent['service'], span['service'], span['edge_type'])
            edges.add(edge)
            counts[edge] += 1
    require(seen_services == set(services), 'declared service missing from control traces')
    annotations = metadata.get('edge_gates', [])
    bindings = {}
    for binding in annotations:
        key = (binding['source'], binding['target'], binding['type'])
        require(key in edges and key not in bindings, 'edge binding absent or duplicated')
        gates = binding['factors']
        require(len(gates) == len(set(gates)) and set(gates) <= known, 'invalid edge gate')
        bindings[key] = gates
    require(metadata['unannotated_edge_law'] == 'deterministic_live', 'unknown edge default')
    sample_ids, successes, totals = set(), Counter(), Counter()
    for row in observations:
        require(row['sample_id'] not in sample_ids, 'duplicate observation sample')
        sample_ids.add(row['sample_id'])
        require(set(row['values']) == measured, 'observation schema differs from declared mask universe')
        for name, value in row['values'].items():
            require(value is None or type(value) is bool, 'primitive observations must be bool/null')
            if value is not None:
                totals[name] += 1
                successes[name] += int(value)
    return dict(
        version=VERSION, scope='controlled_demonstrator_only',
        graph=dict(services=sorted(seen_services), edges=[dict(source=a, target=b, type=t,
            factors=bindings.get((a,b,t), []), observed_span_links=counts[(a,b,t)])
            for a,b,t in sorted(edges)]),
        replicas={s:services[s] for s in sorted(services)}, operation=operation,
        state_law=metadata['state_law'], observation_law=law,
        primitives={name:dict(estimate=successes[name]/totals[name] if totals[name] else None,
            successes=successes[name], observed_count=totals[name],
            source='direct primitive probe values', population_observable=name in measured)
            for name in sorted(ids)},
        extraction=dict(trace_span_count=len(traces), observation_rows=len(observations),
            routing=metadata['routing'], repeat_semantics=metadata['repeat_semantics'],
            graph_coverage=metadata['trace_coverage'], manual_fields=[
                'replica primitive bindings', 'edge primitive bindings/default law',
                'operation required targets', 'observation and state law assumptions']))


def phi(model: dict, state: dict[str, bool]) -> bool:
    """Graph traversal in one state; service live = OR of replica conjunctions."""
    live = {service for service, replicas in model['replicas'].items()
            if any(all(state[name] for name in gates) for gates in replicas)}
    entry = model['operation']['entry']
    if entry not in live:
        return False
    adjacency = {service:[] for service in live}
    for edge in model['graph']['edges']:
        if (edge['type'] == 'sync' and edge['source'] in live and edge['target'] in live
                and all(state[name] for name in edge['factors'])):
            adjacency[edge['source']].append(edge['target'])
    reached, pending = {entry}, [entry]
    while pending:
        for target in adjacency[pending.pop()]:
            if target not in reached:
                reached.add(target)
                pending.append(target)
    return set(model['operation']['required']) <= reached


def validate_model(model):
    require(model['version'] == VERSION, 'unknown persisted model version')
    require(model['scope'] == 'controlled_demonstrator_only', 'unsupported model scope')
    require(model['state_law'] == 'independent_bernoulli_primitives', 'unsupported persisted state law')
    ids = set(model['primitives'])
    require(0 < len(ids) <= MAX_FACTORS, 'exact enumeration bound')
    require(set(model['graph']['services']) == set(model['replicas']), 'graph/replica mismatch')
    require(model['operation']['semantics'] == 'immediate_sync_all_required', 'unsupported persisted predicate')
    require(model['operation']['entry'] in model['replicas'], 'unknown persisted entry')
    require(bool(model['operation']['required']) and set(model['operation']['required']) <= set(model['replicas']), 'unknown/empty targets')
    for service, replicas in model['replicas'].items():
        require(bool(replicas), 'empty replicas')
        for gate in replicas:
            require(set(gate) <= ids and len(gate) == len(set(gate)), 'unknown/duplicate persisted gate')
    for edge in model['graph']['edges']:
        require(edge['source'] in model['replicas'] and edge['target'] in model['replicas'], 'unknown edge endpoint')
        require(edge['type'] in ('sync', 'async') and set(edge['factors']) <= ids, 'unknown edge gate/type')
    law = model['observation_law']
    require(law['version'] == 'direct-primitive-mcar-v1' and law['mask_independent_of_state'] is True
            and law['conditional_on_success'] is False, 'unsupported persisted observation law')
    for name, item in model['primitives'].items():
        n, s = item['observed_count'], item['successes']
        require(type(n) is int and type(s) is int and 0 <= s <= n, 'invalid sufficient statistics')
        require(item['population_observable'] == (name in law['measured_primitives']), 'observation provenance mismatch')
        require(n == 0 or item['population_observable'], 'unobservable factor has observations')
        expected = s/n if n else None
        require(item['estimate'] == expected, 'estimate differs from saved sufficient statistics')


def truth_table(model):
    ids = sorted(model['primitives'])
    return ids, {bits:phi(model, dict(zip(ids,bits))) for bits in product((False,True), repeat=len(ids))}


def probability(model, values):
    ids, table = truth_table(model)
    require(set(values) == set(ids) and all(type(x) in (float,int) and 0 <= x <= 1 for x in values.values()), 'invalid probability vector')
    return fsum(prod(values[name] if bit else 1-values[name] for name,bit in zip(ids,bits))
                for bits,success in table.items() if success)


def solve(model):
    validate_model(model)
    ids, table = truth_table(model)
    essential = [name for i,name in enumerate(ids) if any(
        not bits[i] and success != table[bits[:i]+(True,)+bits[i+1:]]
        for bits,success in table.items())]
    absent = [name for name in essential if model['primitives'][name]['estimate'] is None]
    unobservable = [name for name in essential if not model['primitives'][name]['population_observable']]
    values = {name:item['estimate'] for name,item in model['primitives'].items()}
    lo = probability(model, {name:0.0 if value is None else value for name,value in values.items()})
    hi = probability(model, {name:1.0 if value is None else value for name,value in values.items()})
    return dict(version=VERSION, event='static synchronous reachability of every declared target',
        status='target_not_identifiable' if unobservable else 'insufficient_observations' if absent else 'estimated',
        prediction=None if absent else lo, plug_in_missing_parameter_range=[lo,hi],
        range_is_confidence_interval=False, essential_primitives=essential,
        target_population_identifiable=not unobservable,
        parameters_population_identifiable=all(x['population_observable'] for x in model['primitives'].values()),
        missing_essential_estimates=absent, states_enumerated=len(table),
        parameter_uncertainty='not quantified by this demonstrator',
        application_adequacy='not evaluated')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build')
    build.add_argument('--metadata', type=Path, required=True)
    build.add_argument('--traces', type=Path, required=True)
    build.add_argument('--observations', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True)
    replay = commands.add_parser('solve')
    replay.add_argument('--model', type=Path, required=True)
    replay.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    result = build_model(read(args.metadata), read(args.traces), read(args.observations)) if args.command == 'build' else solve(read(args.model))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
