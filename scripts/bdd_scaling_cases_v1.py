"""Finite artificial CUDD comparison grid; no application observations."""
from telemetry_availability.graph_execution_model_v1 import VERSION, validate


def make_model(nodes=8, completions=None, unknown=4, categories=5, structure='chain'):
    services = [f's{i}' for i in range(nodes)]
    pairs = [(i, i+1) for i in range(nodes-1)]
    if structure == 'fanout':
        pairs = [(0, i) for i in range(1, nodes-1)] + [(i, nodes-1) for i in range(1, nodes-1)]
    elif structure == 'diamond':
        pairs += [(i, i+2) for i in range(nodes-2)]
    elif structure == 'cyclic':
        pairs += [(i, i-2) for i in range(2, nodes)]
    elif structure != 'chain':
        raise ValueError('unknown structure')
    if completions is not None:
        if completions < len(pairs)+1:
            raise ValueError('too few completion coordinates')
        base = list(pairs)
        while len(pairs)+1 < completions:
            pairs.append(base[(len(pairs)-len(base)) % len(base)])
    edges = [dict(id=f'e{i}', source=services[a], target=services[b], type='sync', factors=[f'link{i%2}'])
             for i, (a, b) in enumerate(pairs)]
    controls = ['shared', 'ha', 'hb', 'link0', 'link1', 'aux0', 'aux1', 'sel_a', 'sel_b', 'timely']
    replicas = {s: [[f'aux{i%2}']] for i, s in enumerate(services)}
    replicas[services[0]] = [['shared']]
    replicas[services[-1]] = [['shared', 'ha'], ['shared', 'hb']]
    bindings = [dict(edge_id=e['id'], signal='completed_'+e['id']) for e in edges]
    completion = ['entry_completed'] + [b['signal'] for b in bindings]
    ids = sorted(controls+completion)
    good = {x: True for x in ids}; good['sel_b'] = False
    bad = {x: False for x in ids}
    misroute = dict(good, hb=False, sel_a=False, sel_b=True)
    late = dict(good, timely=False)
    m = categories - 4
    if m <= 0 or m > 2**(len(completion)-1):
        raise ValueError('invalid category dimension')
    rows = [(good, 2*m), (bad, 2*m), (misroute, m), (late, m)]
    for i in range(m):
        row = dict(good)
        for x in controls[:unknown]: row[x] = None
        for x in completion: row[x] = None
        for bit, x in enumerate(completion[1:]):
            if i & (1 << bit): row[x] = True
        rows.append((row, 4))
    model = dict(version=VERSION, execution_class='declared_mandatory_call_groups',
        graph=dict(services=services, edges=edges), replicas=replicas,
        operation=dict(id='artificial_'+structure, entry=services[0], required=[services[0], services[-1]],
                       semantics='immediate_sync_all_required'),
        signal_ids=ids, observation_categories=[dict(values=[row[x] for x in ids], count=count) for row, count in rows],
        sample_count=10*m, demand_controls=[dict(service=services[-1], selected_signals=['sel_a', 'sel_b'])],
        timely_signal='timely', entry_completion_signal='entry_completed', completion_signals=completion,
        required_edge_completions=bindings, assumptions=dict(scope='artificial finite computational grid'),
        observation_law='empirical arbitrary joint category law; potentially informative coordinate masks')
    validate(model)
    return model


def cases():
    grid = [('graph_nodes', dict(nodes=n)) for n in (4, 8, 16, 32, 48)]
    grid += [('completions', dict(nodes=4, completions=r)) for r in (4, 8, 16, 32, 48)]
    grid += [('unknown_controls', dict(nodes=8, unknown=k)) for k in (0, 2, 4, 6, 8, 10)]
    grid += [('categories', dict(nodes=4, completions=16, categories=q)) for q in (5, 16, 64, 128)]
    grid += [('graph_structure', dict(nodes=12, structure=s)) for s in ('chain', 'fanout', 'diamond', 'cyclic')]
    result = [dict(case_id=f'{i:02d}-{axis}', axis=axis, parameters=parameters,
                   model=make_model(**parameters), oracle=['1/5', '3/5'])
              for i, (axis, parameters) in enumerate(grid)]
    from benchmark_v3_model_scaling_v1 import model
    for n in (4, 16, 48):
        result.append(dict(case_id=f'{len(result):02d}-fully_observed', axis='fully_observed', parameters=dict(nodes=n),
                           model=model(n), oracle=['1/16', '1/16']))
    return result
