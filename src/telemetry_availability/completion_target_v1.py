"""Direct identification of R = timely AND all logical completions.

External business outcomes are not inputs. The historical full binding stays
immutable; its private final-solver dependency can be disabled for cost parity.
"""
from collections import Counter
from fractions import Fraction
from types import FunctionType

from . import v4_execution_binding_v1 as binding
from .graph_execution_model_v1 import fiber_states, predicates, control_ids

VERSION = 'completion-deadline-target-v1'
AGGREGATE = '__logical_completions__'


def conjunction(values):
    values = list(values)
    if any(v is not None and type(v) is not bool for v in values):
        raise ValueError('completion coordinates must be Boolean or unknown')
    return False if False in values else True if all(v is True for v in values) else None


def estimate(lower, upper, count):
    lo, hi = Fraction(lower, count), Fraction(upper, count)
    return dict(lower_exact=str(lo), upper_exact=str(hi), lower=float(lo), upper=float(hi),
                status='point' if lo == hi else 'interval', samples=count)


def reduced_from_rows(rows, completion_signals, operation):
    """Collapse only after applying masks to the individual observations."""
    ids = ['timely', AGGREGATE]
    counts = Counter((r['observation']['timely'], conjunction(r['observation'][k]
                     for k in completion_signals)) for r in rows)
    if not counts:
        raise ValueError('empty observation population')
    return dict(version=VERSION, operation=operation, signal_ids=ids,
                completion_signals=list(completion_signals), sample_count=len(rows),
                observation_categories=[dict(values=list(v), count=n)
                                        for v, n in sorted(counts.items(), key=lambda p: str(p[0]))])


def project_full(model):
    counts = Counter()
    positions = [model['signal_ids'].index(k) for k in model['completion_signals']]
    timely = model['signal_ids'].index(model['timely_signal'])
    for row in model['observation_categories']:
        key = (row['values'][timely], conjunction(row['values'][i] for i in positions))
        counts[key] += row['count']
    return dict(version=VERSION, operation=model['operation']['id'],
                signal_ids=['timely', AGGREGATE], completion_signals=list(model['completion_signals']),
                sample_count=model['sample_count'], observation_categories=[dict(values=list(v), count=n)
                for v, n in sorted(counts.items(), key=lambda p: str(p[0]))])


def query_reduced(model):
    lower = upper = total = 0
    for row in model['observation_categories']:
        value = conjunction(row['values']); n = row['count']
        lower += n * (value is True); upper += n * (value is not False); total += n
    if total != model['sample_count']:
        raise ValueError('reduced count differs')
    return estimate(lower, upper, total)


def query_full_r(model):
    """Use the sufficient coordinates, never enumerate irrelevant controls."""
    positions = [model['signal_ids'].index(k) for k in model['completion_signals']]
    positions.append(model['signal_ids'].index(model['timely_signal']))
    lower = upper = total = 0
    for row in model['observation_categories']:
        value = conjunction(row['values'][i] for i in positions); n = row['count']
        lower += n * (value is True); upper += n * (value is not False); total += n
    if total != model['sample_count']:
        raise ValueError('full count differs')
    return estimate(lower, upper, total)


def full_identify(data, operation, spec, identity):
    check_native_parse(data)
    data = observation_input(data)
    # Private function globals leave both the frozen file and process-wide
    # binding untouched. Only its final all-functional solve is suppressed;
    # the original construction, support checks and auxiliary data are retained.
    scope = dict(binding.fit_operation.__globals__)
    scope['solve'] = lambda model: {'estimates': {}}
    constructor = FunctionType(binding.fit_operation.__code__, scope,
                               binding.fit_operation.__name__, binding.fit_operation.__defaults__)
    model, report, rows = constructor(data, operation, spec, identity)
    for assumptions in (model['assumptions'], report['assumptions']):
        assumptions['historical_proxy_time_is_sampler_start_not_check_completion'] = False
        assumptions['historical_proxy_snapshot_timestamp'] = 'reading_completed; last HAProxy check can still be older'
    return model, rows


def check_native_parse(data):
    parsed = data.get('manifest.json', {}).get('native_parse', {})
    if parsed.get('malformed_records') or parsed.get('invalid_traces'):
        raise binding.BindingUnsupported('malformed_native_record_or_invalid_verification_trace')


def observation_input(data):
    allowed = ('request_id', 'trace_id', 'operation', 'period', 'started_at', 'completed_at')
    return dict(data, **{'requests.json': [{k: r[k] for k in allowed if k in r}
                                         for r in data['requests.json']]})


def direct_records(data, operation, spec, identity):
    """Read native attempts without constructing a graph or full state.

    The existing parser checks native parent identity and source-declared
    logical groups. Missing declared nodes/edges do not by themselves prevent
    partial identification of R: their missing completions remain unknown.
    """
    check_native_parse(data)
    data = observation_input(data)
    requests = [r for r in data['requests.json'] if r['operation'] == operation]
    if len(requests) != spec['expected_attempts'] or len({r['request_id'] for r in requests}) != len(requests):
        raise ValueError('unexpected direct attempt census')
    declarations = data['declarations.json']; evidence = []; databases = set(); services = set()
    for request in requests:
        spans = data['native.json']['spans'].get(request['trace_id'], [])
        parsed = binding.request_evidence(request, spans, declarations, spec)
        evidence.append((request, spans, parsed))
        databases.update(parsed['db_records']); services.update(parsed['nodes'])
    unexpected = services - set(spec['allowed_native_services']) - databases
    if unexpected:
        raise binding.BindingUnsupported('unclassified native services: ' + str(sorted(unexpected)))
    required_owners = set(spec['required_native_services']) | {spec['entry']}
    pairs = {tuple(p) for p in spec['required_native_pairs']}
    pairs.update(pair for _, _, e in evidence for pair, records in e['calls'].items()
                 if pair[1] in databases and pair[0] in required_owners
                 and any(not r['optional_for_completion'] for r in records))
    signals = sorted({'entry_completed'} | {'completed:' + binding.edge_id(*p) for p in pairs})
    rows = []
    for request, spans, e in evidence:
        observed = dict(entry_completed=e['root_status'], timely=e['timely']); reasons = {}
        for pair in sorted(pairs):
            signal = 'completed:' + binding.edge_id(*pair)
            observed[signal], reasons[signal] = binding.logical_completion(
                pair, e, spans, spec, identity['application'], operation)
        rows.append(dict(request_id=request['request_id'], trace_id=request['trace_id'],
                         observation=observed, completion_reasons=reasons))
    return rows, signals


def direct_identify(data, operation, spec, identity, hidden=None):
    rows, signals = direct_records(data, operation, spec, identity)
    if hidden:
        rows = mask_rows(rows, hidden)
    return reduced_from_rows(rows, signals, operation), rows


def mask_rows(rows, hidden):
    return [dict(r, observation={k: None if k in hidden.get(r['request_id'], ()) else v
                                for k, v in r['observation'].items()}) for r in rows]


def full_with_rows(model, rows):
    result = dict(model); ids = model['signal_ids']
    counts = Counter(tuple(r['observation'][k] for k in ids) for r in rows)
    result['sample_count'] = len(rows)
    result['observation_categories'] = [dict(values=list(v), count=n)
                                      for v, n in sorted(counts.items(), key=lambda p: str(p[0]))]
    # Auxiliary historical observations do not restrict the declared mask law.
    # Omit their unmasked copies from this new masked model's representation.
    result.pop('auxiliary_joint_categories', None)
    return result


class JointBounds:
    """E, R and R-E over the same Cartesian state fiber; exact truth bitsets."""
    def __init__(self, model):
        from itertools import product
        self.model = model; self.controls = sorted(control_ids(model)); self.cache = {}
        d = len(self.controls) + 1
        self.universe = (1 << (1 << d)) - 1
        self.masks = [0] * d; self.truth = {k: 0 for k in ('E', 'R', 'R_minus_E')}
        for index, bits in enumerate(product((False, True), repeat=d)):
            state = dict(zip(self.controls, bits[:-1]))
            state.update({k: bits[-1] for k in model['completion_signals']})
            e = predicates(model, state)['execution']; r = state[model['timely_signal']] and bits[-1]
            if e and not r:
                raise ValueError('E does not imply R')
            for j, b in enumerate(bits):
                if b: self.masks[j] |= 1 << index
            for name, value in [('E', e), ('R', r), ('R_minus_E', r and not e)]:
                if value: self.truth[name] |= 1 << index

    def __call__(self, observed):
        key = tuple(observed[k] for k in self.controls) + (
            conjunction(observed[k] for k in self.model['completion_signals']),)
        if key not in self.cache:
            region = self.universe
            for value, mask in zip(key, self.masks):
                if value is not None: region &= mask if value else self.universe ^ mask
            self.cache[key] = {name: (int(not (region & (self.universe ^ truth))), int(bool(region & truth)))
                               for name, truth in self.truth.items()}
        return self.cache[key]

    def verify(self):
        witnesses = []
        for key, result in self.cache.items():
            observed = dict(zip(self.controls, key[:-1]))
            observed.update({k: key[-1] for k in self.model['completion_signals']})
            candidates = []
            for state in fiber_states(self.model, [observed[k] for k in self.model['signal_ids']]):
                e = int(predicates(self.model, state)['execution'])
                r = int(state[self.model['timely_signal']] and all(state[k] for k in self.model['completion_signals']))
                candidates.append((state, {'E': e, 'R': r, 'R_minus_E': r-e}))
            for name, bounds in result.items():
                low = min(candidates, key=lambda x: x[1][name]); high = max(candidates, key=lambda x: x[1][name])
                if (low[1][name], high[1][name]) != bounds:
                    raise ValueError('joint exact reference mismatch')
                witnesses.append(dict(mask=list(key), functional=name, lower=bounds[0], upper=bounds[1],
                                      lower_witness=low[0], upper_witness=high[0]))
        return witnesses
