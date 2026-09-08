"""Pre-main analysis component: paired campaign clusters, explicit common support."""
from collections import Counter
import math
import numpy as np

PRIMARY_COMPARATORS = ('G0', 'PMX')
FAMILY_SIZE = 6
BOOTSTRAP_DRAWS = 10000
FAMILY_ALPHA = .05
SEED = 771602


def valid_probability(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1


def validate(campaigns, design, methods):
    """No absent identity/operation/method can silently disappear from the census."""
    assert len(design['applications']) == 3
    for dimension in ('placements','laws','repetitions'):
        assert design[dimension] and len(design[dimension])==len(set(design[dimension]))
    for operations in design['applications'].values():
        assert operations and len(operations)==len(set(operations))
    assert len(methods) == len(set(methods)) and {'Gstar','G0','PMX','B0'} <= set(methods)
    expected = {(app, placement, law, rep) for app in design['applications']
                for placement in design['placements'] for law in design['laws']
                for rep in design['repetitions']}
    found = set()
    ids = set()
    for row in campaigns:
        key = (row['application'], row['placement'], row['law'], row['repetition'])
        assert key in expected and key not in found
        assert isinstance(row['campaign_id'], str) and row['campaign_id'] not in ids
        ids.add(row['campaign_id'])
        found.add(key)
        assert row['view'] == 'all_sequence', 'Stable data cannot replace the primary event'
        assert row['evaluator_status'] in ('qualified','unavailable','unqualified')
        if row['evaluator_status'] != 'qualified':
            assert row.get('evaluator_reason')
        assert set(row['operations']) == set(design['applications'][row['application']])
        for op in row['operations'].values():
            assert isinstance(op['attempts'], int) and not isinstance(op['attempts'], bool) and op['attempts'] >= 0
            assert isinstance(op['successes'], int) and not isinstance(op['successes'], bool)
            assert 0 <= op['successes'] <= op['attempts']
            if row['evaluator_status'] == 'qualified':
                assert op['attempts'] > 0
            assert set(op['forecasts']) == set(methods)
            for forecast in op['forecasts'].values():
                assert forecast['status'] in ('ok','unsupported','failed','missing')
                if forecast['status'] == 'ok':
                    assert valid_probability(forecast['probability'])
                else:
                    assert forecast.get('probability') is None and forecast.get('reason')
    assert found == expected, f'Missing {len(expected-found)} planned campaigns'


def cell_metrics(probability, successes, attempts):
    observed = successes / attempts
    error = probability-observed
    # Mean request-level Brier from the exact Bernoulli sufficient counts.
    brier = (successes*(1-probability)**2 + (attempts-successes)*probability**2)/attempts
    return {'observed':observed,'forecast':probability,'signed_error_pp':100*error,
            'absolute_error_pp':100*abs(error),'brier':brier,'attempts':attempts,'successes':successes}


def scored(row, operation, method):
    op = row['operations'][operation]
    forecast = op['forecasts'][method]
    if row['evaluator_status'] != 'qualified' or forecast['status'] != 'ok':
        return None
    return cell_metrics(forecast['probability'],op['successes'],op['attempts'])


def own_metrics(rows, operations, method, strata):
    records, buckets = [], {}
    for placement, law in strata:
        for operation in operations:
            values = [scored(r,operation,method) for r in rows if (r['placement'],r['law'])==(placement,law)]
            values = [v for v in values if v is not None]
            buckets[(placement,law,operation)] = values
            records.extend(values)
    active = {key:values for key,values in buckets.items() if values}
    if not active:
        return {'status':'not_estimable','scored_cells':0,'planned_cells':len(rows)*len(operations),
            'attempts':0,'standardized_mean':None,
            'own_support':[{'placement':p,'law':l,'operation':o,'campaigns':0} for p,l,o in buckets],
            'per_operation':{op:{'campaigns':0,'planned_campaigns':len(rows),'attempts':0,
                'retained_conditions':0,'standardized_mean':None,'median_absolute_error_pp':None,
                'p90_absolute_error_pp':None} for op in operations}}
    # Equal operation weights within each retained condition, equal retained condition weights.
    by_stratum = {}
    for stratum in strata:
        available_ops = [buckets[(*stratum,op)] for op in operations if buckets[(*stratum,op)]]
        if available_ops:
            by_stratum[stratum] = {key:float(np.mean([np.mean([r[key] for r in values])
                for values in available_ops])) for key in ('signed_error_pp','absolute_error_pp','brier')}
    absolute = [r['absolute_error_pp'] for r in records]
    by_operation = {}
    for operation in operations:
        values_by_condition = [buckets[(*stratum,operation)] for stratum in strata
                               if buckets[(*stratum,operation)]]
        available = [v for group in values_by_condition for v in group]
        by_operation[operation] = {'campaigns':len(available),'planned_campaigns':len(rows),
            'attempts':sum(r['attempts'] for r in available),
            'retained_conditions':len(values_by_condition),
            'standardized_mean':{key:float(np.mean([np.mean([r[key] for r in group])
                for group in values_by_condition])) for key in
                ('forecast','observed','signed_error_pp','absolute_error_pp','brier')} if available else None,
            'median_absolute_error_pp':float(np.median([r['absolute_error_pp'] for r in available])) if available else None,
            'p90_absolute_error_pp':float(np.quantile([r['absolute_error_pp'] for r in available],.9)) if available else None}
    return {'status':'estimable_on_reported_own_support','scored_cells':len(records),
        'planned_cells':len(rows)*len(operations),'attempts':sum(r['attempts'] for r in records),
        'per_operation':by_operation,
        'own_support':[{'placement':p,'law':l,'operation':o,'campaigns':len(v)} for (p,l,o),v in buckets.items()],
        'standardized_mean':{key:float(np.mean([v[key] for v in by_stratum.values()]))
                            for key in ('signed_error_pp','absolute_error_pp','brier')},
        'cell_median_absolute_error_pp':float(np.quantile(absolute,.5)),
        'cell_p90_absolute_error_pp':float(np.quantile(absolute,.9)),
        'quantile_scope':'unweighted available campaign-operation cell errors; same estimator for every method'}


def paired_primary(rows, operations, comparator, strata, seed, draws=BOOTSTRAP_DRAWS):
    """Conditional common support; resample whole paired campaigns in each condition."""
    complete, support, common_cells = {}, [], []
    for placement, law in strata:
        group = sorted([r for r in rows if (r['placement'],r['law'])==(placement,law)],
                       key=lambda r:r['campaign_id'])
        retained = []
        for row in group:
            differences = []
            for operation in operations:
                left, right = scored(row,operation,'Gstar'), scored(row,operation,comparator)
                if left is not None and right is not None:
                    difference = left['absolute_error_pp']-right['absolute_error_pp']
                    differences.append(difference)
                    common_cells.append({'campaign_id':row['campaign_id'],'operation':operation,
                        'difference_pp':difference,'left_absolute_error_pp':left['absolute_error_pp'],
                        'right_absolute_error_pp':right['absolute_error_pp']})
            if len(differences)==len(operations):
                # Averaging operations here preserves all within-campaign dependencies.
                retained.append({'campaign_id':row['campaign_id'],'difference_pp':float(np.mean(differences))})
        support.append({'placement':placement,'law':law,'planned_campaigns':len(group),
                        'complete_common_campaigns':len(retained),
                        'campaign_ids':[r['campaign_id'] for r in retained]})
        if retained:
            complete[(placement,law)] = retained
    report = {'left':'Gstar','right':comparator,'common_cell_census':common_cells,
        'common_cells':len(common_cells),'planned_cells':len(rows)*len(operations),
        'support':support,'complete_common_campaigns':sum(len(v) for v in complete.values()),
        'retained_conditions':len(complete),'planned_conditions':len(strata),
        'estimand':'Equal-condition mean of equal-operation campaign MAE differences, conditional on complete common campaign support',
        'bootstrap_draws':draws,'bootstrap_seed':seed,'family_size':FAMILY_SIZE,
        'contrast_alpha':FAMILY_ALPHA/FAMILY_SIZE,'confidence_level':1-FAMILY_ALPHA/FAMILY_SIZE,
        'finite_sample_family_coverage_guaranteed':False,
        'coverage_uncertainty_included':False,
        'complete_support_is_conditioned_on_not_imputed':True}
    if not complete:
        report.update(status='not_estimable_no_complete_common_campaign',estimate_pp=None,interval_pp=None)
        return report
    point = float(np.mean([np.mean([r['difference_pp'] for r in group]) for group in complete.values()]))
    report['estimate_pp'] = point
    if any(len(group)<2 for group in complete.values()):
        report.update(status='point_only_insufficient_independent_common_campaigns',interval_pp=None)
        return report
    rng = np.random.Generator(np.random.PCG64(seed))
    estimates = np.zeros(draws)
    for stratum in strata:
        if stratum not in complete:
            continue
        values = np.asarray([r['difference_pp'] for r in complete[stratum]])
        samples = rng.integers(0,len(values),size=(draws,len(values)))
        estimates += values[samples].mean(axis=1)/len(complete)
    tail = FAMILY_ALPHA/FAMILY_SIZE/2
    interval = np.quantile(estimates,[tail,1-tail],method='linear')
    report.update(status='estimable_on_reported_complete_common_support',interval_pp=interval.tolist(),
        bootstrap_sd_pp=float(np.std(estimates,ddof=1)),
        interval_below_zero=bool(interval[1]<0),interval_above_zero=bool(interval[0]>0))
    return report


def analyze(campaigns, design, methods):
    validate(campaigns,design,methods)
    strata = [(p,l) for p in design['placements'] for l in design['laws']]
    applications = {}
    primary = []
    census = []
    for app_index,(application,operations) in enumerate(design['applications'].items()):
        rows = [r for r in campaigns if r['application']==application]
        application_report = {'campaigns':len(rows),'operation_cells_per_method':len(rows)*len(operations),'methods':{}}
        for method in methods:
            status_counts = Counter(op['forecasts'][method]['status'] for r in rows for op in r['operations'].values())
            absence_reasons = Counter(op['forecasts'][method].get('reason') for r in rows for op in r['operations'].values()
                                      if op['forecasts'][method]['status']!='ok')
            result = own_metrics(rows,operations,method,strata)
            result.update(forecast_status_counts=dict(status_counts),absence_reasons=dict(absence_reasons))
            application_report['methods'][method] = result
        applications[application] = application_report
        for i,comparator in enumerate(PRIMARY_COMPARATORS):
            contrast = paired_primary(rows,operations,comparator,strata,SEED+2*app_index+i)
            contrast['application'] = application
            primary.append(contrast)
        for row in rows:
            for operation,op in row['operations'].items():
                for method in methods:
                    census.append({'campaign_id':row['campaign_id'],'application':application,
                        'placement':row['placement'],'law':row['law'],'repetition':row['repetition'],
                        'operation':operation,'method':method,'evaluator_status':row['evaluator_status'],
                        'evaluator_reason':row.get('evaluator_reason'), 'forecast':op['forecasts'][method],
                        'metrics':scored(row,operation,method)})
    assert len(primary)==6
    return {'version':'v3-campaign-analysis-v1','primary_view':'all_sequence',
        'campaigns':len(campaigns),'method_slots':len(census),'applications':applications,
        'primary_contrasts':primary,'attempted_census':census,
        'stable_view_required_separately':True,'transfer_and_stage_costs_not_implemented_here':True,
        'low_error_or_superiority_is_not_a_qualification_gate':True}
