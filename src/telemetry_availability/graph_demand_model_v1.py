"""Finite joint graph/selected-replica/deadline model with explicit ambiguity.

This core does not infer that ordinary probes are true execution capabilities.
Application bindings and semantic adequacy require separate qualification.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import product

from .graph_observation_model import VERSION as OBS_VERSION
from .graph_observation_model import identify as identify_observations, validate as validate_observations
from .graph_replay_v3 import phi

VERSION = 'graph-selected-demand-joint-v1'
VARIANTS = ('reachability', 'selected_replicas', 'selected_replicas_and_deadline')


def validate(model):
    if model['version'] != VERSION:
        raise ValueError('unsupported demand model version')
    base = dict(model, version=OBS_VERSION)
    validate_observations(base)
    ids = set(model['signal_ids'])
    used = set()
    services = set()
    state_signals = {signal for replicas in model['replicas'].values() for gates in replicas for signal in gates}
    state_signals.update(signal for edge in model['graph']['edges'] for signal in edge['factors'])
    for control in model['demand_controls']:
        service = control['service']; signals = control['selected_signals']
        if service not in model['operation']['required'] or service in services:
            raise ValueError('demand control must refer once to a declared required service')
        if len(signals) != len(model['replicas'][service]) or len(signals) != len(set(signals)):
            raise ValueError('one distinct demand coordinate per declared replica is required')
        if not set(signals) <= ids or set(signals) & (used | state_signals):
            raise ValueError('unknown or aliased demand coordinate')
        used.update(signals); services.add(service)
    timely = model['timely_signal']
    if timely not in ids or timely in used | state_signals:
        raise ValueError('deadline coordinate must be separate from demands/capabilities')
    if ids != state_signals | used | {timely}:
        raise ValueError('unused state coordinates must be removed explicitly')
    if model['execution_class'] != 'static_capabilities_all_selected_replicas_required':
        raise ValueError('unsupported retry/state-change execution semantics')


def identify(graph, replicas, operation, signal_ids, observations, demand_controls,
             timely_signal, assumptions):
    model = identify_observations(deepcopy(graph), deepcopy(replicas), deepcopy(operation),
                                  signal_ids, observations, deepcopy(assumptions))
    model.update(version=VERSION, demand_controls=deepcopy(demand_controls), timely_signal=timely_signal,
        execution_class='static_capabilities_all_selected_replicas_required',
        state_law='arbitrary joint capabilities, selected-replica demands and timely completion',
        business_equivalence='requires the declared execution and observation assumptions; not inferred from traces')
    validate(model)
    return model


def predicates(model, state):
    """One graph traversal; demand restriction and whole-operation deadline follow."""
    if set(state) != set(model['signal_ids']) or any(type(v) is not bool for v in state.values()):
        raise ValueError('complete Boolean state required')
    reachable = phi(model, state)
    selected = reachable
    for control in model['demand_controls']:
        demands = [state[name] for name in control['selected_signals']]
        replicas = model['replicas'][control['service']]
        selected = selected and any(demands) and all(
            not demand or all(state[name] for name in gates)
            for demand, gates in zip(demands, replicas))
    timely = selected and state[model['timely_signal']]
    return dict(reachability=reachable, selected_replicas=bool(selected),
                selected_replicas_and_deadline=bool(timely))


def solve(model):
    """Sharp ranges from masked observation fibers, including paired ablation gaps."""
    validate(model)
    ids = model['signal_ids']
    table = {}
    for bits in product((False, True), repeat=len(ids)):
        values = predicates(model, dict(zip(ids, bits)))
        assert values['selected_replicas_and_deadline'] <= values['selected_replicas'] <= values['reachability']
        values.update(reachability_minus_execution=int(values['reachability']) - int(values['selected_replicas_and_deadline']),
                      reachability_minus_selected=int(values['reachability']) - int(values['selected_replicas']),
                      selected_minus_execution=int(values['selected_replicas']) - int(values['selected_replicas_and_deadline']))
        table[bits] = values
    names = list(next(iter(table.values())))
    lower = {name: Fraction(0) for name in names}; upper = dict(lower)
    cells = []
    for row in model['observation_categories']:
        compatible = [(bits, values) for bits, values in table.items()
                      if all(v is None or v == b for v, b in zip(row['values'], bits))]
        weight = Fraction(row['count'], model['sample_count'])
        extrema = {}
        for name in names:
            low_bits, low_value = min(compatible, key=lambda item: item[1][name])
            high_bits, high_value = max(compatible, key=lambda item: item[1][name])
            lo, hi = int(low_value[name]), int(high_value[name])
            lower[name] += weight * lo; upper[name] += weight * hi
            extrema[name] = dict(minimum=lo, maximum=hi,
                lower_witness=list(low_bits) if lo != hi else None,
                upper_witness=list(high_bits) if lo != hi else None)
        cells.append(dict(values=row['values'], count=row['count'], compatible_states=len(compatible), extrema=extrema))
    estimates = {name: dict(lower=float(lower[name]), upper=float(upper[name]),
        lower_exact=str(lower[name]), upper_exact=str(upper[name]),
        prediction=float(lower[name]) if lower[name] == upper[name] else None,
        status='singleton_given_empirical_observation_law' if lower[name] == upper[name] else 'ambiguous',
        interval_is_confidence_interval=False) for name in names}
    return dict(version=VERSION, samples=model['sample_count'], states_enumerated=len(table),
        estimates=estimates, category_certificates=cells,
        primary_variant='selected_replicas_and_deadline',
        between_call_or_replica_independence_assumed=False,
        point_imputation_for_ambiguous_target=False,
        physical_cause_parameters_identified=False,
        future_distribution_invariance='required separately for forecast',
        population_identification_from_finite_sample_not_asserted=True,
        business_adequacy='not established by this finite core')
