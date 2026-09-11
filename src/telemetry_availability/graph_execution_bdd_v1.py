"""Exact joint-category bounds using symbolic CUDD ROBDDs, without marginals.

The injected factory is for bounded semantic tests only. Production uses dd.cudd.
"""
from fractions import Fraction
from time import perf_counter
import warnings

from .graph_execution_model_v1 import VARIANTS, control_ids, predicates, validate

POLICIES = ('controls_first', 'structural', 'sift_once')


def variable_order(model, policy):
    if policy not in POLICIES:
        raise ValueError('unknown BDD policy')
    if policy != 'structural':
        return sorted(control_ids(model)) + sorted(model['completion_signals'])
    sequence = []
    for service in model['graph']['services']:
        sequence.extend(x for gates in model['replicas'][service] for x in gates)
        sequence.extend(x for row in model['demand_controls'] if row['service'] == service
                        for x in row['selected_signals'])
        for edge in model['graph']['edges']:
            if edge['source'] == service:
                sequence.extend(edge['factors'])
                sequence.extend(row['signal'] for row in model['required_edge_completions']
                                if row['edge_id'] == edge['id'])
    sequence += model['completion_signals'] + [model['timely_signal']]
    return list(dict.fromkeys(sequence))


class CompiledModel:
    def __init__(self, model, policy='sift_once', bdd_factory=None):
        started = perf_counter()
        validate(model)
        if bdd_factory is None:
            from dd.cudd import BDD
            bdd_factory = BDD
        self.model = model
        self.policy = policy
        self.bdd = bdd_factory(memory_estimate=2**30)
        bdd = self.bdd
        bdd.configure(reordering=False)
        order = variable_order(model, policy)
        if len(order) != len(model['signal_ids']) or set(order) != set(model['signal_ids']):
            raise ValueError('variable order is not a permutation')
        bdd.declare(*order)

        def conjunction(names):
            value = bdd.true
            for name in names:
                value &= bdd.var(name)
            return value

        live = {}
        for service, replicas in model['replicas'].items():
            live[service] = bdd.false
            for gates in replicas:
                live[service] |= conjunction(gates)
        op = model['operation']
        reachable = {s: bdd.false for s in live}
        reachable[op['entry']] = live[op['entry']]
        edges = [(edge['source'], edge['target'], conjunction(edge['factors']))
                 for edge in model['graph']['edges'] if edge['type'] == 'sync']
        # All simple paths have at most |V|-1 edges, also for a cyclic graph.
        for _ in range(len(live) - 1):
            updated = dict(reachable)
            for source, target, enabled in edges:
                updated[target] |= reachable[source] & enabled & live[target]
            if updated == reachable:
                break
            reachable = updated
        base = bdd.true
        for service in op['required']:
            base &= reachable[service]
        selected = base
        for row in model['demand_controls']:
            any_selected = bdd.false
            for signal, gates in zip(row['selected_signals'], model['replicas'][row['service']]):
                demand = bdd.var(signal)
                any_selected |= demand
                selected &= ~demand | conjunction(gates)
            selected &= any_selected
        completed = bdd.var(model['entry_completion_signal'])
        sync_ids = {edge['id'] for edge in model['graph']['edges'] if edge['type'] == 'sync'}
        for row in model['required_edge_completions']:
            completed &= bdd.var(row['signal']) if row['edge_id'] in sync_ids else bdd.false
        timely = bdd.var(model['timely_signal'])
        roots = dict(reachability=base, selected=selected,
                     without_deadline=selected & completed,
                     execution=selected & completed & timely,
                     without_selection=base & completed & timely,
                     without_completion=selected & timely)
        for name in VARIANTS:
            if name != 'execution':
                if roots['execution'] & ~roots[name] != bdd.false:
                    raise ValueError('execution implication failed')
                roots[name + '_minus_execution'] = roots[name] & ~roots['execution']
        self.roots = roots
        # Drop the large transient containers before the prescribed sifting pass.
        del live, reachable, edges, base, selected, completed, timely
        reorder_started = perf_counter()
        if policy == 'sift_once':
            bdd.reorder()
        self.reorder_seconds = perf_counter() - reorder_started if policy == 'sift_once' else 0.0
        self.build_seconds = perf_counter() - started

    def solve(self):
        model, bdd = self.model, self.bdd
        validate(model)
        lower = {name: Fraction(0) for name in self.roots}
        upper = dict(lower)
        certificates = []
        for row in model['observation_categories']:
            known = {x: value for x, value in zip(model['signal_ids'], row['values']) if value is not None}
            cube = bdd.cube(known)
            weight = Fraction(row['count'], model['sample_count'])
            extrema = {}
            for name, root in self.roots.items():
                positive, negative = cube & root, cube & ~root
                lo, hi = int(negative == bdd.false), int(positive != bdd.false)
                if lo > hi:
                    raise ValueError('empty observation fiber')
                lower[name] += weight * lo
                upper[name] += weight * hi
                witnesses = [None, None]
                if lo != hi:
                    for i, region in enumerate((negative, positive)):
                        assignment = bdd.pick(region, care_vars=set(model['signal_ids']))
                        witnesses[i] = [assignment[x] for x in model['signal_ids']]
                extrema[name] = dict(minimum=lo, maximum=hi,
                                     lower_witness=witnesses[0], upper_witness=witnesses[1])
            certificates.append(dict(values=row['values'], count=row['count'],
                                     full_fiber_size=2**row['values'].count(None), extrema=extrema))
        estimates = {name: dict(lower=float(lower[name]), upper=float(upper[name]),
                     lower_exact=str(lower[name]), upper_exact=str(upper[name]),
                     prediction=float(lower[name]) if lower[name] == upper[name] else None,
                     status='singleton_given_empirical_observation_law' if lower[name] == upper[name] else 'ambiguous')
                     for name in self.roots}
        return dict(version='graph-execution-cudd-v1', samples=model['sample_count'], estimates=estimates,
                    category_certificates=certificates, between_coordinate_independence_assumed=False,
                    interval_is_confidence_interval=False)

    def statistics(self):
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Changed in `dd` version.*')
            stats = self.bdd.statistics()
        return dict(manager=stats, root_dag_nodes={name: root.dag_size for name, root in self.roots.items()},
                    final_order=sorted(self.model['signal_ids'], key=self.bdd.level_of_var))


def verify_result(model, result, reference):
    """Exact endpoint/status equality and scalar checks of every nontrivial witness."""
    if result['estimates'] != reference['estimates']:
        raise ValueError('estimates differ from frozen core or saved model result')
    certs = result['category_certificates']
    if len(certs) != len(model['observation_categories']):
        raise ValueError('certificate census mismatch')
    totals = {name: [Fraction(0), Fraction(0)] for name in result['estimates']}
    witnessed = 0
    for row, cert in zip(model['observation_categories'], certs):
        if cert['values'] != row['values'] or cert['count'] != row['count']:
            raise ValueError('certificate category differs')
        if set(cert['extrema']) != set(totals):
            raise ValueError('certificate functional census mismatch')
        for name, ex in cert['extrema'].items():
            lo, hi = ex['minimum'], ex['maximum']
            if lo not in (0, 1) or hi not in (0, 1) or lo > hi:
                raise ValueError('invalid extrema')
            for side, endpoint in enumerate((lo, hi)):
                totals[name][side] += Fraction(row['count'], model['sample_count']) * endpoint
                witness = ex['lower_witness' if side == 0 else 'upper_witness']
                if lo == hi:
                    if witness is not None:
                        raise ValueError('unexpected singleton witness')
                    continue
                if witness is None or len(witness) != len(model['signal_ids']):
                    raise ValueError('missing witness')
                if any(v is not None and v != w for v, w in zip(row['values'], witness)):
                    raise ValueError('witness violates observed mask')
                if predicates(model, dict(zip(model['signal_ids'], witness)))[name] != endpoint:
                    raise ValueError('witness fails scalar predicate')
                witnessed += 1
    for name, pair in totals.items():
        if [str(x) for x in pair] != [result['estimates'][name]['lower_exact'], result['estimates'][name]['upper_exact']]:
            raise ValueError('category extrema do not aggregate to estimate')
    return dict(exact_estimates_verified=len(totals), witnesses_verified=witnessed,
                categories_verified=len(certs))
