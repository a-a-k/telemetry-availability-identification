"""Matched primitive masks and joint event differences; Y is validation-only."""
from collections import Counter
from fractions import Fraction

from .completion_target_v1 import (JointBounds, conjunction, reduced_from_rows, project_full,
                                  query_reduced, query_full_r, full_with_rows, mask_rows)
from .v4_missingness_v1 import rank

INFORMATION = ('none', 'selection_and_admission', 'entry_result', 'required_completions', 'all_native')


def order_cells(records, ids, mechanism, seed, completions):
    cells = []
    for i, row in enumerate(records):
        failure = any(row['observation'][k] is False for k in completions)
        for j, name in enumerate(ids):
            if name == 'timely' or row['observation'][name] is None: continue
            number = rank(seed, row['request_id'], name)
            if mechanism == 'uniform_coordinates': key = (number,)
            elif mechanism == 'native_failure_associated_coordinates':
                key = (number // (4 if failure else 1), number)
            elif mechanism == 'whole_native_attempt': key = (rank(seed, row['request_id']), number)
            else: raise ValueError('unplanned mask mechanism')
            cells.append((key, row['request_id'], name, i, j))
    cells.sort()
    return [(r[3], r[4]) for r in cells]


def restored(name, information):
    return (information == 'all_native'
            or information == 'selection_and_admission' and name.startswith(('admitted_', 'demand_'))
            or information == 'entry_result' and name == 'entry_completed'
            or information == 'required_completions' and name.startswith('completed:'))


def check_routes(model, full_rows, direct_rows, signals, operation):
    direct = reduced_from_rows(direct_rows, signals, operation)
    answer = query_reduced(direct)
    if model is not None:
        full = full_with_rows(model, full_rows); projected = project_full(full)
        if projected != direct or query_full_r(full) != answer or query_reduced(projected) != answer:
            raise ValueError('same-R route or observation-law mismatch')
    return direct, answer


def metrics(full_rows, direct_rows, signals, joint, outcomes):
    counts = Counter(); patterns = Counter(); n = len(direct_rows)
    for i, row in enumerate(direct_rows):
        r_value = conjunction(row['observation'].values())
        r_bounds = (int(r_value is True), int(r_value is not False))
        bounds = {'R': r_bounds}
        if joint is not None:
            bounds = joint(full_rows[i]['observation'])
            if bounds['R'] != r_bounds: raise ValueError('primitive direct R differs from joint R')
            d = bounds['R_minus_E']
            counts['equivalent_for_all_states' if d[1] == 0 else
                   'different_for_all_states' if d[0] == 1 else 'event_difference_undecided'] += 1
            counts['same_marginal_bounds_but_possible_difference'] += int(bounds['E'] == bounds['R'] and d[1] > 0)
            if d[1]:
                label = 'R_fixed_true_K_unknown' if r_bounds == (1, 1) and d == (0, 1) else (
                    'R_fixed_true_K_excludes_success' if d == (1, 1) else 'R_and_K_difference_not_determined')
                counts[label] += 1
        for name, (lo, hi) in bounds.items():
            counts[name+'_lower_count'] += lo; counts[name+'_upper_count'] += hi
            counts[name+'_point_attempts'] += lo == hi
            if outcomes is not None and name != 'R_minus_E':
                y = outcomes[row['request_id']]
                counts[name+'_success_excluded'] += int(y > hi)
                counts[name+'_failure_excluded'] += int(y < lo)
        patterns[tuple((name, *value) for name, value in sorted(bounds.items()))] += 1
    result = dict(attempts=n, **counts)
    for name in ('R', 'E', 'R_minus_E') if joint is not None else ('R',):
        lo, hi = counts[name+'_lower_count'], counts[name+'_upper_count']
        result.update({name+'_lower_exact': str(Fraction(lo, n)), name+'_upper_exact': str(Fraction(hi, n)),
                       name+'_width': (hi-lo)/n, name+'_point_fraction': counts[name+'_point_attempts']/n})
    return result, [dict(bounds={name: [lo, hi] for name, lo, hi in key}, count=value)
                    for key, value in sorted(patterns.items())]


def analyze(model, full_rows, direct_rows, signals, operation, outcomes, config):
    if len({r['request_id'] for r in direct_rows}) != len(direct_rows): raise ValueError('duplicate direct attempt')
    if model is not None:
        if [r['request_id'] for r in full_rows] != [r['request_id'] for r in direct_rows]:
            raise ValueError('route attempt populations differ')
        for full, direct in zip(full_rows, direct_rows, strict=True):
            if any(full['observation'][k] != v for k, v in direct['observation'].items()):
                raise ValueError('primitive observation or interpretation differs')
    if outcomes is not None and (set(outcomes) != {r['request_id'] for r in direct_rows}
                                or any(type(y) is not bool for y in outcomes.values())):
        raise ValueError('primary outcome population differs')
    joint = JointBounds(model) if model is not None else None
    reference, answer = check_routes(model, full_rows, direct_rows, signals, operation)
    baseline, baseline_patterns = metrics(full_rows, direct_rows, signals, joint, outcomes)
    rows = []; masks = []; pattern_rows = []
    master = full_rows if model is not None else direct_rows
    ids = sorted(master[0]['observation'])
    # Outcomes are never passed to order_cells, masks, construction or solvers.
    for mechanism in config['mechanisms']:
        order = order_cells(master, ids, mechanism, config['seed'], signals)
        masks.append(dict(mechanism=mechanism, signal_ids=ids, order=order,
                          request_ids=[r['request_id'] for r in master]))
        for level in config['levels']:
            budget = int(Fraction(str(level))*len(order)); hidden_cells = order[:budget]
            for information in INFORMATION:
                hidden = {}; revealed = 0
                for i, j in hidden_cells:
                    name = ids[j]
                    if restored(name, information): revealed += 1; continue
                    hidden.setdefault(master[i]['request_id'], set()).add(name)
                dr = mask_rows(direct_rows, hidden)
                fr = mask_rows(full_rows, hidden) if model is not None else None
                reduced, r_answer = check_routes(model, fr, dr, signals, operation)
                if information == 'all_native' and reduced != reference:
                    raise ValueError('all-restoration did not reproduce original joint law')
                measured, patterns = metrics(fr, dr, signals, joint, outcomes)
                key = dict(mechanism=mechanism, missing_fraction=level, information=information)
                if (measured['R_lower_exact'], measured['R_upper_exact']) != (
                        r_answer['lower_exact'], r_answer['upper_exact']):
                    raise ValueError('per-attempt and aggregate R differ')
                rows.append(dict(key, known_native_coordinates=len(order), hidden_native_coordinates=budget,
                                 revealed_native_coordinates=revealed, same_R_routes_qualified=True, **measured))
                pattern_rows.extend(dict(key, **p) for p in patterns)
    witnesses = joint.verify() if joint is not None else []
    return dict(baseline=baseline, R=answer, settings=rows, patterns=pattern_rows,
                baseline_patterns=baseline_patterns, masks=masks, witnesses=witnesses,
                distinct_joint_masks=len(joint.cache) if joint is not None else 0,
                same_R_routes_qualified=True, primitive_observations_agree=model is not None)
