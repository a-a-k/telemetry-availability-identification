"""Attempt-level forensic checks of the frozen observation binding.

This is an audit of already-open calibration evidence, not a new estimator.
Application inputs are processed only by the remote runner. Tiny constructed
records can exercise the two-sided compatibility and cancellation controls.
"""
from bisect import bisect_right
from collections import Counter
from fractions import Fraction
import json

from .b0_frequency_v3_csv_v2 import decode_outcome
from .graph_execution_model_v1 import fiber_states, predicates, solve
from .v3_application_execution_v2 import (
    align_probe, completion_observation, declared_probe_layer, explicit_status,
    request_evidence, timestamp_ns,
)


def compatibility(lower, outcome, upper):
    if not (lower in (0, 1) and upper in (0, 1) and lower <= upper
            and type(outcome) is bool):
        raise ValueError('Boolean attempt bounds and external outcome required')
    return 'success_excluded' if outcome > upper else (
        'failure_excluded' if outcome < lower else 'compatible')


def summarize_attempts(rows):
    rows = list(rows)
    if not rows:
        raise ValueError('empty attempt census')
    counts = Counter(row['compatibility'] for row in rows)
    n = len(rows); successes = sum(row['outcome'] for row in rows)
    lower = sum(row['lower'] for row in rows); upper = sum(row['upper'] for row in rows)
    incompatible = counts['success_excluded'] + counts['failure_excluded']
    return dict(attempts=n, successes=successes, lower_count=lower, upper_count=upper,
        lower_exact=str(Fraction(lower, n)), upper_exact=str(Fraction(upper, n)),
        b0_exact=str(Fraction(successes, n)), success_excluded=counts['success_excluded'],
        failure_excluded=counts['failure_excluded'], incompatible_attempts=incompatible,
        incompatible_fraction=incompatible/n,
        fully_observed_attempts=sum(row['fully_observed'] for row in rows),
        fully_observed_mismatches=sum(row['fully_observed'] and row['compatibility'] != 'compatible' for row in rows),
        ambiguous_attempts=sum(row['lower'] != row['upper'] for row in rows),
        aggregate_excess_above_upper_count=max(0, successes-upper),
        aggregate_deficit_below_lower_count=max(0, lower-successes),
        aggregate_contains_b0=lower <= successes <= upper,
        incompatible_despite_aggregate_containment=bool(incompatible and lower <= successes <= upper),
        signed_b0_minus_lower_pp=100*(successes-lower)/n,
        signed_b0_minus_upper_pp=100*(successes-upper)/n)


def audit_operation(data, model, spec):
    """Reconstruct every row; require exact agreement with saved category law."""
    declarations = data['declarations.json']; operation = model['operation']['id']
    requests = [r for r in data['requests.json'] if r['operation'] == operation]
    probes = sorted(data['probes.json'], key=lambda r: timestamp_ns(r['observed_at']))
    times = [timestamp_ns(r['observed_at']) for r in probes]
    layer = declared_probe_layer(declarations)
    pairs = [(tuple(json.loads(row['edge_id'])), row['signal']) for row in model['required_edge_completions']]
    saved = {tuple(row['values']): row['count'] for row in model['observation_categories']}
    certificates = solve(model)['category_certificates']
    extrema = {tuple(row['values']): row['extrema'] for row in certificates}
    rebuilt = Counter(); rows = []; witnesses = {}; reason_counts = Counter(); flag_counts = Counter()
    for request in requests:
        spans = data['native.json']['spans'].get(request['trace_id'], [])
        e = request_evidence(request, spans, declarations, spec)
        observation = dict(entry_completed=e['root_status'], timely=e['timely'])
        reasons = {}
        for pair, signal in pairs:
            observation[signal], reasons[signal] = completion_observation(pair, e, spec)
        age = None; probe_index = None
        if model['demand_controls']:
            state, age = align_probe(e['started_ns'], probes, times, spec['maximum_probe_age_ns'], layer)
            observation.update(state)
            observation.update({f'demand_{r}': e['demands'][r] for r in ('a', 'b')})
            if age is not None:
                probe_index = bisect_right(times, e['started_ns'])-1
        if set(observation) != set(model['signal_ids']):
            raise ValueError('reconstructed coordinate census differs')
        values = tuple(observation[x] for x in model['signal_ids']); rebuilt[values] += 1
        bounds = extrema[values]['execution']; lo = bounds['minimum']; hi = bounds['maximum']
        outcome = decode_outcome(request['semantic_success'])
        direction = compatibility(lo, outcome, hi); full = None not in values
        if full:
            direct = int(predicates(model, observation)['execution'])
            if lo != direct or hi != direct:
                raise ValueError('complete-state evaluation disagrees with fiber bounds')
        flags = []
        if any(observation.get('demand_'+r) is True and observation.get('probe_'+r) is False for r in ('a', 'b')):
            flags.append('selected_replica_probe_false')
        if all(observation.get('probe_'+r) is False for r in ('a', 'b')):
            flags.append('both_replica_probes_false')
        if observation['entry_completed'] is False: flags.append('entry_explicit_failure')
        false_completions = [signal for _, signal in pairs if observation[signal] is False]
        if false_completions: flags.append('required_completion_false')
        if observation['timely'] is False: flags.append('external_duration_exceeds_deadline')
        if outcome is False and lo == 1: flags.append('external_failure_with_all_necessary_conditions_true')
        row = dict(request_id=request['request_id'], trace_id=request['trace_id'], operation=operation,
            outcome=outcome, lower=lo, upper=hi, compatibility=direction, fully_observed=full,
            observation=observation, completion_reasons=reasons, flags=flags,
            probe_age_ns=age, probe_observed_at=probes[probe_index]['observed_at'] if probe_index is not None else None,
            external_duration_ns=timestamp_ns(request['completed_at'])-e['started_ns'],
            ablation_without_selection_lower=extrema[values]['without_selection']['minimum'],
            ablation_without_selection_upper=extrema[values]['without_selection']['maximum'])
        rows.append(row)
        if direction != 'compatible':
            reason_counts.update(signal+'|'+reasons[signal] for signal in false_completions)
            flag_counts.update(flags or ['other_or_joint_constraint'])
        # First chronological record per diagnostic pattern and a compatible
        # control. These examples are illustrative, never an evaluation subset.
        signature = direction+'|'+','.join(flags)+'|'+str(full)
        if signature not in witnesses:
            relevant = [s for s in spans if s['service'] == declarations['target_service']
                        or explicit_status(s) is False or s['service'] == spec['entry']]
            witnesses[signature] = dict(attempt=row, projected_request=request,
                selected_probe=probes[probe_index] if probe_index is not None else None,
                neighboring_probes=probes[max(0, probe_index-1):probe_index+3] if probe_index is not None else [],
                relevant_native_spans=relevant,
                false_completion_records={signal: e['calls'].get(pair, []) for pair, signal in pairs if signal in false_completions})
    if dict(rebuilt) != saved or len(rows) != model['sample_count']:
        raise ValueError('attempt reconstruction does not reproduce saved joint category law')
    summary = summarize_attempts(rows)
    estimate = solve(model)['estimates']['execution']
    if any(summary[k] != estimate[k] for k in ('lower_exact', 'upper_exact')):
        raise ValueError('attempt extrema do not reproduce saved aggregate estimate')
    summary.update(status='audited', operation=operation, saved_categories_exact=True,
        incompatible_flag_counts=dict(flag_counts), incompatible_completion_reason_counts=dict(reason_counts),
        flags_can_overlap=True, flags_are_not_causal_classification=True,
        ablation_without_selection_incompatible_attempts=sum(
            compatibility(r['ablation_without_selection_lower'], r['outcome'], r['ablation_without_selection_upper']) != 'compatible' for r in rows))
    return summary, rows, witnesses
