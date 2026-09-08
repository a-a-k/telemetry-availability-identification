"""Joint observed eligibility, demand and mandatory-call completion model.

Completion coordinates describe call groups, not static physical capability.
No business labels, independent marginals or fitted residual enter this core.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import product

from .graph_replay_v3 import phi

VERSION = 'graph-observed-execution-joint-v1'
VARIANTS = ('reachability', 'selected', 'without_deadline', 'execution',
            'without_selection', 'without_completion')


def control_ids(model):
    ids = {x for rs in model['replicas'].values() for gates in rs for x in gates}
    ids.update(x for edge in model['graph']['edges'] for x in edge['factors'])
    ids.update(x for row in model['demand_controls'] for x in row['selected_signals'])
    return ids | {model['timely_signal']}


def validate(model):
    if model['version'] != VERSION or model['execution_class'] != 'declared_mandatory_call_groups':
        raise ValueError('unsupported execution model')
    ids = model['signal_ids']; known = set(ids)
    if not 0 < len(ids) <= 64 or len(ids) != len(known):
        raise ValueError('invalid observation coordinates')
    services = set(model['graph']['services'])
    if services != set(model['replicas']) or len(services) != len(model['graph']['services']):
        raise ValueError('invalid services')
    state_ids = set()
    for replicas in model['replicas'].values():
        if not replicas:
            raise ValueError('no replica')
        for gates in replicas:
            if len(gates) != len(set(gates)) or not set(gates) <= known:
                raise ValueError('invalid replica gate')
            state_ids.update(gates)
    edge_ids = set()
    for edge in model['graph']['edges']:
        if (edge['source'] not in services or edge['target'] not in services or
                edge['type'] not in ('sync', 'async') or edge['id'] in edge_ids or
                not set(edge['factors']) <= known):
            raise ValueError('invalid graph edge')
        edge_ids.add(edge['id']); state_ids.update(edge['factors'])
    op = model['operation']
    if (op['semantics'] != 'immediate_sync_all_required' or op['entry'] not in services or
            not op['required'] or not set(op['required']) <= services):
        raise ValueError('invalid operation')
    demands = set(); controlled = set()
    for row in model['demand_controls']:
        service = row['service']; signals = row['selected_signals']
        if (service in controlled or service not in op['required'] or
                len(signals) != len(model['replicas'][service]) or len(signals) != len(set(signals)) or
                not set(signals) <= known or set(signals) & (demands | state_ids)):
            raise ValueError('invalid demand control')
        controlled.add(service); demands.update(signals)
    timely = model['timely_signal']
    if timely not in known or timely in state_ids | demands:
        raise ValueError('aliased deadline')
    completion = model['completion_signals']
    if (not completion or len(completion) != len(set(completion)) or
            not set(completion) <= known or set(completion) & (state_ids | demands | {timely})):
        raise ValueError('invalid completion signals')
    bindings = model['required_edge_completions']
    # A missing required edge is a meaningful structural counterfactual: false.
    if (len(bindings) != len({r['edge_id'] for r in bindings}) or
            any(r['signal'] not in completion for r in bindings)):
        raise ValueError('invalid required-edge completion binding')
    if (model['entry_completion_signal'] not in completion or
            set(completion) != {model['entry_completion_signal']} | {r['signal'] for r in bindings} or
            known != state_ids | demands | {timely} | set(completion) or len(control_ids(model)) > 10):
        raise ValueError('unused coordinate or unsupported control dimension')
    total = 0; categories = set()
    for row in model['observation_categories']:
        values = tuple(row['values'])
        if (len(values) != len(ids) or any(v is not None and type(v) is not bool for v in values) or
                values in categories or type(row['count']) is not int or row['count'] <= 0):
            raise ValueError('invalid observation category')
        categories.add(values); total += row['count']
    if not total or type(model['sample_count']) is not int or total != model['sample_count']:
        raise ValueError('invalid sample census')


def identify(graph, replicas, operation, observations, demand_controls,
             required_edge_completions, assumptions):
    rows = list(observations)
    if not rows:
        raise ValueError('no observations')
    ids = sorted(rows[0]); counts = Counter()
    for row in rows:
        if set(row) != set(ids) or any(v is not None and type(v) is not bool for v in row.values()):
            raise ValueError('invalid observation row')
        counts[tuple(row[x] for x in ids)] += 1
    model = dict(version=VERSION, execution_class='declared_mandatory_call_groups',
        graph=deepcopy(graph), replicas=deepcopy(replicas), operation=deepcopy(operation),
        signal_ids=ids, sample_count=len(rows),
        observation_categories=[dict(values=list(k), count=n) for k, n in sorted(counts.items(), key=lambda x: str(x[0]))],
        demand_controls=deepcopy(demand_controls), timely_signal='timely',
        entry_completion_signal='entry_completed',
        completion_signals=sorted({'entry_completed'} | {r['signal'] for r in required_edge_completions}),
        required_edge_completions=deepcopy(required_edge_completions), assumptions=deepcopy(assumptions),
        observation_law='empirical arbitrary joint category law; potentially informative coordinate masks')
    validate(model)
    return model


def predicates(model, state):
    if set(state) != set(model['signal_ids']) or any(type(v) is not bool for v in state.values()):
        raise ValueError('complete Boolean state required')
    base = phi(model, state)
    selected = base
    for control in model['demand_controls']:
        demands = [state[x] for x in control['selected_signals']]
        selected = selected and any(demands) and all(
            not d or all(state[x] for x in gates)
            for d, gates in zip(demands, model['replicas'][control['service']]))
    edges = {e['id'] for e in model['graph']['edges'] if e['type'] == 'sync'}
    completed = state[model['entry_completion_signal']] and all(
        row['edge_id'] in edges and state[row['signal']] for row in model['required_edge_completions'])
    timely = state[model['timely_signal']]
    result = dict(reachability=bool(base), selected=bool(selected),
        without_deadline=bool(selected and completed), execution=bool(selected and completed and timely),
        without_selection=bool(base and completed and timely), without_completion=bool(selected and timely))
    result.update({name + '_minus_execution': int(result[name]) - int(result['execution'])
                   for name in VARIANTS if name != 'execution'})
    return result


def fiber_states(model, values):
    """Exact extrema candidates: enumerate controls; extremize the completion AND.

    With controls fixed every reported functional is affine in the same Boolean
    completion conjunction. Its minimum/maximum are attained by assigning all
    masked completion bits 0/1. This includes paired gaps, not interval subtraction.
    """
    ids = model['signal_ids']; fixed = dict(zip(ids, values)); controls = control_ids(model)
    unknown_controls = sorted(x for x in controls if fixed[x] is None)
    unknown_completion = sorted(x for x in model['completion_signals'] if fixed[x] is None)
    for bits in product((False, True), repeat=len(unknown_controls)):
        state = dict(fixed); state.update(zip(unknown_controls, bits))
        for extreme in ((False, True) if unknown_completion else (False,)):
            candidate = dict(state); candidate.update({x: extreme for x in unknown_completion})
            yield candidate


def solve(model):
    validate(model); lower = {}; upper = {}; certificates = []; evaluated = 0
    for row in model['observation_categories']:
        candidates = [(s, predicates(model, s)) for s in fiber_states(model, row['values'])]
        evaluated += len(candidates); extrema = {}
        weight = Fraction(row['count'], model['sample_count'])
        for name in candidates[0][1]:
            low = min(candidates, key=lambda item: item[1][name]); high = max(candidates, key=lambda item: item[1][name])
            lo, hi = int(low[1][name]), int(high[1][name])
            lower[name] = lower.get(name, Fraction(0)) + weight * lo
            upper[name] = upper.get(name, Fraction(0)) + weight * hi
            extrema[name] = dict(minimum=lo, maximum=hi,
                lower_witness=[low[0][x] for x in model['signal_ids']] if lo != hi else None,
                upper_witness=[high[0][x] for x in model['signal_ids']] if lo != hi else None)
        certificates.append(dict(values=row['values'], count=row['count'],
            full_fiber_size=2 ** row['values'].count(None), evaluated_candidates=len(candidates), extrema=extrema))
    estimates = {name: dict(lower=float(lower[name]), upper=float(upper[name]),
        lower_exact=str(lower[name]), upper_exact=str(upper[name]),
        prediction=float(lower[name]) if lower[name] == upper[name] else None,
        status='singleton_given_empirical_observation_law' if lower[name] == upper[name] else 'ambiguous') for name in lower}
    return dict(version=VERSION, samples=model['sample_count'], estimates=estimates,
        evaluated_states=evaluated, category_certificates=certificates,
        interval_is_confidence_interval=False, between_coordinate_independence_assumed=False,
        physical_capabilities_identified=False, population_law_identified_from_finite_sample=False,
        business_equivalence='conditional on declared observation, workload and completion assumptions',
        future_forecast='requires invariance of the relevant joint observation/state law')
