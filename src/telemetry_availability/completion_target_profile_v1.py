"""Disjoint cost stages around the unchanged binding and direct R algorithm."""
from time import perf_counter
from types import FunctionType, SimpleNamespace

from . import completion_target_v1 as target


def query_e(model):
    """The original specialized completion reduction, restricted to target E.

    No other target estimates or witness/oracle checks are requested.
    """
    lower = upper = 0
    for row in model['observation_categories']:
        values = [int(target.predicates(model, state)['execution'])
                  for state in target.fiber_states(model, row['values'])]
        lower += row['count']*min(values); upper += row['count']*max(values)
    return target.estimate(lower, upper, model['sample_count'])


def identify(data, operation, spec, identity, direct=False):
    times = {'interpretation_seconds': 0.0, 'frequency_identification_seconds': 0.0}; calls = {}
    def timed(name, function, field='interpretation_seconds'):
        def measured(*args, **kwargs):
            start = perf_counter()
            try: return function(*args, **kwargs)
            finally:
                times[field] += perf_counter()-start; calls[name] = calls.get(name, 0)+1
        return measured
    binding = target.binding
    start = perf_counter()
    if direct:
        proxy = SimpleNamespace(**{k:v for k,v in vars(binding).items() if not k.startswith('__')})
        for name in ('request_evidence', 'logical_completion'):
            setattr(proxy, name, timed(name, getattr(binding, name)))
        scope = dict(target.direct_records.__globals__, binding=proxy)
        constructor = FunctionType(target.direct_records.__code__, scope, target.direct_records.__name__)
        rows, signals = constructor(data, operation, spec, identity)
        model = timed('reduced_category_identification', target.reduced_from_rows,
                      'frequency_identification_seconds')(rows, signals, operation)
    else:
        target.check_native_parse(data); data = target.observation_input(data)
        scope = dict(binding.fit_operation.__globals__)
        for name in ('request_evidence', 'logical_completion', 'native_admissions',
                     'align_probe', 'declared_probe_layer', 'timestamp_ns'):
            scope[name] = timed(name, scope[name])
        scope['identify'] = timed('full_category_identification', scope['identify'], 'frequency_identification_seconds')
        scope['solve'] = lambda model: {'estimates': {}}
        constructor = FunctionType(binding.fit_operation.__code__, scope, binding.fit_operation.__name__)
        model, _, rows = constructor(data, operation, spec, identity)
        model['assumptions']['historical_proxy_time_is_sampler_start_not_check_completion'] = False
        model['assumptions']['historical_proxy_snapshot_timestamp'] = 'reading_completed; last HAProxy check can still be older'
    elapsed = perf_counter()-start
    times['representation_seconds'] = elapsed-sum(times.values())
    times['total_identification_seconds'] = elapsed
    return model, rows, times, calls
