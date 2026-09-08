"""Explicit ordinary-input adaptation of AINA's uniform fixed-count graph law.

The original scenario p is replaced by the all-attempt mean failed eligibility
fraction of the declared, observed replica pool. This is an adaptation, not an
unchanged published algorithm or a reconstruction of the injection schedule.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations

VERSION = 'G0-AINA-fixed-count-ordinary-v1'


def source_k(size, p):
    """Preserve draw_alive_fixed's Python float/round/minimum-positive rule."""
    value = float(p)
    if type(size) is not int or not 0 <= size <= 16 or not 0 <= value <= 1:
        raise ValueError('invalid fixed-count parameters')
    count = int(round(size * value))
    if value > 0 and count == 0:
        count = 1
    return min(max(0, count), size)


def graph_success(model, failed):
    alive = {service for service, replicas in model['replicas'].items()
             if any(not gates or gates[0] not in failed for gates in replicas)}
    entry = model['operation']['entry']
    reached = {entry} if entry in alive else set()
    changed = True
    while changed:
        before = len(reached)
        reached.update(edge['target'] for edge in model['graph']['edges']
                       if edge['source'] in reached and edge['target'] in alive)
        changed = len(reached) != before
    return set(model['operation']['required']) <= reached


def validate(model):
    if model['version'] != VERSION:
        raise ValueError('unsupported G0 adaptation')
    graph = model['graph']; services = set(graph['services'])
    if services != set(model['replicas']) or len(services) != len(graph['services']):
        raise ValueError('invalid service set')
    gates = []
    for replicas in model['replicas'].values():
        if not replicas:
            raise ValueError('no replica')
        for row in replicas:
            if len(row) > 1:
                raise ValueError('G0 adaptation supports one eligibility coordinate per eligible replica')
            gates.extend(row)
    if len(gates) != len(set(gates)) or sorted(gates) != model['eligible_replicas'] or len(gates) > 16:
        raise ValueError('invalid/aliased eligible replica pool')
    for edge in graph['edges']:
        if (edge['source'] not in services or edge['target'] not in services or
                edge['type'] not in ('sync', 'async') or edge['factors']):
            raise ValueError('invalid G0 graph edge; communication is observed in eligibility, not an extra source factor')
    op = model['operation']
    if op['entry'] not in services or not op['required'] or not set(op['required']) <= services:
        raise ValueError('invalid operation')
    law = model['eligibility_observation_counts']
    if any(type(law[k]) is not int or law[k] < 0 for k in ('known_failed', 'masked', 'slots', 'attempts')):
        raise ValueError('invalid eligibility census')
    if (not law['attempts'] or law['slots'] != law['attempts'] * len(gates) or
            law['known_failed'] + law['masked'] > law['slots']):
        raise ValueError('inconsistent eligibility census')


def identify_from_observed_graph(observed):
    """Use only extracted G/R, X columns and all-attempt category multiplicities.

    All completion, demand, timing and semantic outcome columns are ignored.
    The preceding graph builder may be shared; PMX uses its own independent path.
    """
    ids = observed['signal_ids']; replicas = deepcopy(observed['replicas'])
    pool = sorted(x for rs in replicas.values() for gates in rs for x in gates)
    indices = [ids.index(x) for x in pool]
    failed = masked = attempts = 0
    for category in observed['observation_categories']:
        if (type(category['count']) is not int or category['count'] <= 0 or len(category['values']) != len(ids)):
            raise ValueError('invalid source observation category')
        count = category['count']; attempts += count
        for index in indices:
            value = category['values'][index]
            if value is not None and type(value) is not bool:
                raise ValueError('invalid eligibility observation')
            failed += count * (value is False); masked += count * (value is None)
    if attempts != observed['sample_count']:
        raise ValueError('source attempt census mismatch')
    model = dict(version=VERSION, graph=deepcopy(observed['graph']), replicas=replicas,
        operation=deepcopy(observed['operation']), eligible_replicas=pool,
        eligibility_observation_counts=dict(known_failed=failed, masked=masked, slots=len(pool)*attempts, attempts=attempts),
        predecessor=dict(repository='a-a-k/otel-demo-resilience',
            commit='a8bc5a29a15443ad3a4ef6b88ac710afb97c70c0', path='scripts/resilience.py',
            functions=['draw_alive_fixed', 'endpoint_success'], endpoint_mode='all-block', rule='all_of'),
        adaptation=dict(parameter='mean failed ordinary eligibility fraction over all request-aligned eligible slots',
            fault_pool='only declared measured target replicas; other dependencies explicitly excluded from this failure pool',
            observation_masks='sharp mean-fraction interval, no state imputation or observed-only denominator',
            law='uniform subset with k=source_k(N,p); joint empirical dependence is discarded by this predecessor law',
            calculation='exact integration over finite source-law subsets replaces Monte Carlo; zero simulation error',
            empty_pool='deterministic no-eligible-failure graph; no source fallback to killing unrelated services',
            contract='static all-required reachability used as a business-availability forecast under ideal execution assumptions',
            transport_health_is_physical_capability=False, original_scenario_p_or_truth_used=False,
            deadline_and_call_completion_estimated=False, unchanged_published_algorithm=False,
            source_only_transfer='unsupported without an identified changed eligibility law'))
    validate(model)
    return model


def solve(model):
    validate(model); pool = model['eligible_replicas']; law = model['eligibility_observation_counts']
    if pool:
        low = Fraction(law['known_failed'], law['slots'])
        high = Fraction(law['known_failed'] + law['masked'], law['slots'])
        # The source rounding map is monotone and crosses every intermediate integer.
        counts = range(source_k(len(pool), low), source_k(len(pool), high) + 1)
    else:
        low = high = None; counts = (0,)
    by_count = {}; states = 0
    for count in counts:
        outcomes = [int(graph_success(model, set(failed))) for failed in combinations(pool, count)]
        value = Fraction(sum(outcomes), len(outcomes)); states += len(outcomes)
        by_count[str(count)] = dict(probability=float(value), probability_exact=str(value), states=len(outcomes))
    values = [Fraction(r['probability_exact']) for r in by_count.values()]
    lower, upper = min(values), max(values)
    return dict(version=VERSION, prediction=float(lower) if lower == upper else None,
        lower=float(lower), upper=float(upper), lower_exact=str(lower), upper_exact=str(upper),
        status='singleton_given_adapted_source_law' if lower == upper else 'ambiguous_adapted_source_law',
        calibration_attempts=law['attempts'], eligible_replica_count=len(pool), eligible_slots=law['slots'],
        p_lower_exact=str(low) if low is not None else None, p_upper_exact=str(high) if high is not None else None,
        point_p_identified=low == high, possible_fixed_counts=list(map(int, by_count)), by_fixed_count=by_count,
        states_evaluated=states, interval_is_confidence_interval=False,
        simulation_error=0, business_adequacy_qualified=False,
        continuous_forecast_in_p=False, scenario_generator_reconstructed=False)
