"""Unopened-test evaluation of sealed candidates; all-sequence is primary."""
from bisect import bisect_left, bisect_right
from collections import Counter
from copy import deepcopy

from .b0_frequency_v3_csv_v2 import decode_outcome
from .graph_observation_model import probe_verdict
from .v3_execution_observation_audit_v1 import timestamp_ns
from .v3_comparison_candidates_v1 import METHODS, validate_forecasts
from .v3_comparison_roles_v1 import campaign_id, validate_identity
from .v3_campaign_analysis_v1 import analyze, own_metrics, cell_metrics

VERSION = 'v3-comparison-evaluation-v1'
GUARD_NS = 1_000_000_000
MAX_PROBE_GAP_NS = 2_000_000_000


def stable_membership(requests, probes, layer, guard_ns=GUARD_NS, maximum_gap_ns=MAX_PROBE_GAP_NS):
    """Observed eligibility stability, not oracle stationarity or physical health.

    Require known, identical a/b probe states across the whole request expanded
    by the guard. Bracket both ends, with no probe gap above the frozen limit.
    Unknown/missing ticks are excluded only from this additional view.
    """
    if layer not in ('L4', 'L7') or guard_ns < 0 or maximum_gap_ns <= 0:
        raise ValueError('invalid stable-view rule')
    ordered = sorted(probes, key=lambda p: timestamp_ns(p['observed_at']))
    times = [timestamp_ns(p['observed_at']) for p in ordered]
    if len(times) != len(set(times)):
        raise ValueError('duplicate evaluator probe timestamp')
    states = [tuple(probe_verdict(row[f'replica_{r}_backend_status'],
        row[f'replica_{r}_backend_check_status'], layer=layer)['value'] for r in ('a', 'b')) for row in ordered]
    flags = {}; reasons = Counter()
    for request in requests:
        start = timestamp_ns(request['started_at'])-guard_ns
        end = timestamp_ns(request['completed_at'])+guard_ns
        left, right = bisect_right(times, start)-1, bisect_left(times, end)
        reason = None
        if left < 0 or right >= len(times):
            reason = 'unbracketed_expanded_request'
        else:
            segment = states[left:right+1]
            if any(None in state for state in segment):
                reason = 'masked_probe_state'
            elif any(times[i+1]-times[i] > maximum_gap_ns for i in range(left, right)):
                reason = 'excessive_probe_gap'
            elif len(set(segment)) != 1:
                reason = 'observed_eligibility_transition'
        flags[request['request_id']] = reason is None
        reasons[reason or 'retained'] += 1
    return flags, dict(reasons)


def validate_test_requests(requests, operations, expected_per_operation):
    ids = set(); traces = set(); counts = Counter()
    for request in requests:
        if request['period'] != 'test' or request['operation'] not in operations:
            raise ValueError('closed evaluator role contains another period/operation')
        if not request['request_id'] or request['request_id'] in ids or not request['trace_id'] or request['trace_id'] in traces:
            raise ValueError('duplicate/missing evaluator request/trace identity')
        ids.add(request['request_id']); traces.add(request['trace_id']); counts[request['operation']] += 1
        success, timed_out = decode_outcome(request['semantic_success']), decode_outcome(request['timed_out'])
        if success and timed_out:
            raise ValueError('timeout cannot be business success')
        if timestamp_ns(request['completed_at']) < timestamp_ns(request['started_at']):
            raise ValueError('invalid external request interval')
    if dict(counts) != {op: expected_per_operation for op in operations}:
        raise ValueError('incomplete planned test attempt census')


def evaluate(frozen, evaluator, identity, operations, expected_per_operation, layer):
    """Pure arithmetic after physical-role digest checks in the consuming job."""
    validate_identity(identity)
    if frozen['identity'] != identity or evaluator['manifest.json']['identity'] != identity:
        raise ValueError('candidate/evaluator campaign mismatch')
    validate_forecasts(frozen['forecasts'], operations, METHODS)
    requests = evaluator['requests.json']
    validate_test_requests(requests, operations, expected_per_operation)
    # Acquisition/runtime admission is recorded independently of forecast error.
    gate = evaluator['manifest.json']['test_quality']
    if type(gate['qualified']) is not bool or (not gate['qualified'] and not gate.get('reason')):
        raise ValueError('invalid evaluator qualification')
    flags, reasons = stable_membership(requests, evaluator['probes.json'], layer)
    common = dict(application=identity['application'], placement=identity['placement'], law=identity['law'],
        repetition=identity['repetition'], campaign_id=campaign_id(identity), identity=deepcopy(identity),
        evaluator_status='qualified' if gate['qualified'] else 'unqualified', evaluator_reason=gate.get('reason'))
    views = {}
    for view in ('all_sequence', 'stable'):
        selected = requests if view == 'all_sequence' else [r for r in requests if flags[r['request_id']]]
        operations_report = {}
        for op in operations:
            rows = [r for r in selected if r['operation'] == op]
            operations_report[op] = dict(attempts=len(rows), successes=sum(decode_outcome(r['semantic_success']) for r in rows),
                timeouts=sum(decode_outcome(r['timed_out']) for r in rows), forecasts=deepcopy(frozen['forecasts'][op]))
        views[view] = dict(common, view=view, operations=operations_report)
    return dict(version=VERSION, identity=identity, views=views,
        stable=dict(rule='known constant observed a/b eligibility over request plus/minus1s; bracketed, gaps<=2s',
            membership_reasons=reasons, retained_attempts=sum(flags.values()), planned_attempts=len(requests),
            retained_fraction=sum(flags.values())/len(requests),
            forecasts_reconditioned_on_stable_membership=False, physical_stationarity_claimed=False))


def missing_campaign(identity, operations, frozen=None, reason='acquisition_or_evaluator_unavailable'):
    from .v3_comparison_candidates_v1 import absent
    forecasts = frozen['forecasts'] if frozen else {op: {m: absent('missing', reason) for m in METHODS} for op in operations}
    return dict(application=identity['application'], placement=identity['placement'], law=identity['law'],
        repetition=identity['repetition'], identity=identity, campaign_id=campaign_id(identity), view='all_sequence',
        evaluator_status='unavailable', evaluator_reason=reason,
        operations={op: dict(attempts=0, successes=0, forecasts=deepcopy(forecasts[op])) for op in operations})


def stable_analysis(campaigns, reports, design):
    strata = [(p, l) for p in design['placements'] for l in design['laws']]
    available = {r['views']['stable']['campaign_id']: r['views']['stable'] for r in reports}
    output = {}
    for app, operations in design['applications'].items():
        rows = []
        for campaign in campaigns:
            if campaign['application'] != app:
                continue
            fallback = missing_campaign(campaign['identity'], operations, reason='stable_evaluator_unavailable')
            rows.append(deepcopy(available.get(campaign['campaign_id'], fallback)))
        # Empty stable operation subsets cannot be divided by zero or filled with failures.
        for row in rows:
            for operation in row['operations'].values():
                if operation['attempts'] == 0:
                    for forecast in operation['forecasts'].values():
                        forecast.update(status='missing', probability=None, reason='no_stable_evaluator_attempts')
        output[app] = {method: own_metrics(rows, operations, method, strata) for method in METHODS}
    return dict(scope='additional conditional view; same calibration forecasts, no refit', applications=output,
        intervals=None, intervals_reason='descriptive point summaries; primary six-contrast inference is all_sequence')


def transfer_census(campaigns, design):
    """Source-only non-identification is explicit; no hidden target-law imputation.

    The current empirical joint laws do not identify a changed-placement law.
    Target outcomes are opened here only to report observed target/change. They
    never construct a transfer forecast. Unrestricted business-event bounds are
    [0,1]; corresponding change bounds are relative to a source point, if any.
    """
    by_key = {(r['application'], r['placement'], r['law'], r['repetition']): r for r in campaigns}
    result = []
    for source in campaigns:
        target_placement = 'split' if source['placement'] == 'colocated' else 'colocated'
        target = by_key[(source['application'], target_placement, source['law'], source['repetition'])]
        for op in design['applications'][source['application']]:
            source_op, target_op = source['operations'][op], target['operations'][op]
            source_y = source_op['successes']/source_op['attempts'] if source['evaluator_status'] == 'qualified' and source_op['attempts'] else None
            target_y = target_op['successes']/target_op['attempts'] if target['evaluator_status'] == 'qualified' and target_op['attempts'] else None
            for method in METHODS:
                forecast = source_op['forecasts'][method]
                point = forecast['probability'] if forecast['status'] == 'ok' else None
                result.append(dict(source_campaign_id=source['campaign_id'], target_campaign_id=target['campaign_id'],
                    operation=op, method=method, status='unsupported', probability=None,
                    reason='changed_placement_joint_law_not_identified_from_source_calibration',
                    target_lower=0, target_upper=1, bound_scope='unrestricted target business-event law; not a confidence interval',
                    source_current_probability=point,
                    predicted_change_lower=-point if point is not None else None,
                    predicted_change_upper=1-point if point is not None else None,
                    observed_target=target_y, observed_change=target_y-source_y if target_y is not None and source_y is not None else None,
                    target_error_pp=None, predicted_change=None, change_error_pp=None,
                    target_inputs_used_for_forecast=False))
    return dict(status='all_planned_transfers_explicitly_accounted_without_point_identification',
        planned_slots=len(result), point_forecasts=0, point_coverage=0, census=result)


def cost_analysis(records, campaign_ids):
    """Retain exclusive stage costs separately from overlapping process totals."""
    import numpy as np
    from collections import defaultdict
    seen = set(); stages = defaultdict(list); processes = []; batches = {}
    for record in records:
        key = (record['campaign_id'], record['job_role'], record['attempt_id'])
        if key in seen or key[0] not in campaign_ids:
            raise ValueError('duplicate or unplanned cost record')
        seen.add(key)
        batch = record.get('batch_resource_reference')
        if batch is not None:
            batch_key = (batch['profile'], batch['run_id'])
            if batch_key in batches and batches[batch_key] != batch:
                raise ValueError('inconsistent shared batch resource record')
            batches[batch_key] = deepcopy(batch)
        for row in record.get('stages', []):
            value = row.get('seconds')
            if value is not None:
                if type(value) not in (int, float) or not np.isfinite(value) or value < 0:
                    raise ValueError('invalid measured stage duration')
                stages[(row['method'], row['stage'])].append(value)
        processes.append(deepcopy(record))
    return dict(measured_campaigns=len({r['campaign_id'] for r in records}),
        planned_campaigns=len(campaign_ids), raw_records=processes, shared_batch_resources=list(batches.values()),
        stage_summaries=[dict(method=method, stage=stage, observations=len(values),
            sum_seconds=float(sum(values)), median_seconds=float(np.median(values)),
            p90_seconds=float(np.quantile(values, .9))) for (method, stage), values in sorted(stages.items())],
        stage_and_process_totals_are_overlapping_not_summed=True,
        shared_acquisition_and_graph_extraction_charged_once=True,
        cold_integration_labor_seconds=None, cold_integration_reason='historical labor not timed; manual action inventory reported separately',
        monitoring_off_on_overhead=None, scalability_curve=None,
        omitted_measurements_are_unknown_not_zero=True)


def complete_analysis(campaigns, reports, design, costs):
    primary = analyze(campaigns, design, METHODS)
    if len({campaign_id(r['identity']) for r in reports}) != len(reports):
        raise ValueError('duplicate evaluated report')
    primary.update(version=VERSION, stable_view_required_separately=False,
        transfer_and_stage_costs_not_implemented_here=False,
        stable=stable_analysis(campaigns, reports, design), transfer=transfer_census(campaigns, design),
        costs=cost_analysis(costs, {r['campaign_id'] for r in campaigns}))
    return primary
