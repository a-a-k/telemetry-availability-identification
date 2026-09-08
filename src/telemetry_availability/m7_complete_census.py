"""Descriptive census of immutable M7 tables; no model fitting or raw-data access."""
import csv
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import product
import json
import math
import os
from pathlib import Path
from statistics import fmean

import numpy as np

from .pmx_composition_control import _download, _hash, _read, _remote, _write
from .m7_diagnostic_analysis import _cell_metrics, audit_summary, audit_primary_contrast
from .live_validation_config import load_frozen_live_validation_config

APPS = {
    'deathstarbench_social_network': ('compose_post', 'read_home_timeline', 'read_user_timeline'),
    'opentelemetry_demo': ('browse_product', 'add_to_cart', 'checkout'),
}
MODES = ('full', 'sampled_mixed', 'no_joint_health', 'trace_only')
METHODS = ('B0', 'B1', 'B2', 'B3', 'proposed', 'B4')
LAWS = ('N', 'NC', 'ND', 'NCD')
VIEWS = ('all_sequence', 'stable')
PKEY = ('profile', 'failure_law', 'repetition', 'mode', 'scope',
        'source_placement', 'target_placement', 'method', 'operation')
OKEY = ('profile', 'target_placement', 'failure_law', 'repetition', 'operation', 'view')


def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, values):
    assert values, str(path)
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def key(row, fields):
    return tuple(str(row[f]) for f in fields)


def unique(values, fields):
    result = {}
    for row in values:
        k = key(row, fields)
        if k in result:
            raise ValueError(f'duplicate identity: {k}')
        result[k] = row
    return result


def extract_observations(scores):
    result = {}
    for row in scores:
        k = key(row, OKEY)
        observation = (int(row['test_requests']), int(row['test_successes']))
        if not 0 <= observation[1] <= observation[0] or observation[0] == 0:
            raise ValueError('invalid outcome count')
        if k in result and result[k] != observation:
            raise ValueError(f'contradictory observed outcome: {k}')
        result[k] = observation
    return result


def census_rows(predictions, observations):
    unique(predictions, PKEY)
    result = []
    for pred in predictions:
        value = float(pred['prediction']) if pred['prediction'] != '' else None
        if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError('invalid issued probability')
        if not pred['status']:
            raise ValueError('missing prediction status')
        for view in VIEWS:
            # A transfer's evaluator belongs to target_placement, never source_placement.
            n, s = observations[key(dict(pred, view=view), OKEY)]
            observed = s / n
            row = dict(pred)
            row.update(view=view, issued=value is not None,
                       absence_reason='' if value is not None else pred['status'],
                       test_requests=n, test_successes=s, observed_availability=observed,
                       signed_error_pp='' if value is None else 100 * (value - observed),
                       absolute_error_pp='' if value is None else 100 * abs(value - observed),
                       brier_score='' if value is None else
                       (s * (1 - value)**2 + (n - s) * value**2) / n)
            result.append(row)
    return result


def campaign(row):
    return key(row, ('profile', 'source_placement', 'failure_law', 'repetition'))


def stratum(row):
    return key(row, ('source_placement', 'failure_law'))


def stratified_interval(values, metric, seed_key, draws, seed):
    """One vector per campaign; callers may pass equally averaged operation vectors."""
    groups = defaultdict(list)
    for row in values:
        groups[stratum(row)].append(float(row[metric]))
    if not groups:
        return '', '', '', 0, 0
    digest = sha256((str(seed) + json.dumps(seed_key)).encode()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], 'big'))
    samples = np.zeros(draws)
    for group in groups.values():
        a = np.asarray(group)
        samples += a[rng.integers(0, len(a), size=(draws, len(a)))].mean(axis=1)
    samples /= len(groups)
    lo, hi = np.quantile(samples, [.025, .975])
    return fmean(fmean(v) for v in groups.values()), float(lo), float(hi), len(groups), min(map(len, groups.values()))


def equal_stratum_mean(values, metric):
    groups = defaultdict(list)
    for row in values:
        groups[stratum(row)].append(float(row[metric]))
    return fmean(fmean(v) for v in groups.values()) if groups else ''


def aggregate_operation(values, identity, draws, seed):
    issued = [r for r in values if r['issued']]
    n = len(values)
    result = dict(identity)
    result.update(expected_campaigns=n, issued_campaigns=len(issued), coverage=len(issued)/n,
                  all_test_requests=sum(r['test_requests'] for r in values),
                  issued_test_requests=sum(r['test_requests'] for r in issued),
                  observed_all=equal_stratum_mean(values, 'observed_availability'),
                  observed_issued=equal_stratum_mean(issued, 'observed_availability'),
                  prediction=equal_stratum_mean(issued, 'prediction'))
    for metric in ('signed_error_pp', 'absolute_error_pp', 'brier_score'):
        mean, lo, hi, strata, minimum = stratified_interval(issued, metric, list(identity.values()) + [metric], draws, seed)
        result.update({metric: mean, metric+'_lower95': lo, metric+'_upper95': hi})
    result.update(represented_strata=strata, minimum_issued_campaigns_per_stratum=minimum,
                  absolute_error_median_pp=float(np.median([r['absolute_error_pp'] for r in issued])) if issued else '',
                  absolute_error_p90_pp=float(np.quantile([r['absolute_error_pp'] for r in issued], .9)) if issued else '',
                  absence_reasons=json.dumps(dict(sorted(Counter(r['absence_reason'] for r in values if not r['issued']).items())), sort_keys=True))
    return result


def paired_rows(census, draws, seed):
    """Keep every common operation case; application contrasts require complete pairs."""
    groups = defaultdict(dict)
    for row in census:
        k = key(row, tuple(f for f in PKEY if f != 'method') + ('view',))
        groups[k][row['method']] = row
    common = []
    for methods in groups.values():
        a = methods['proposed']
        for name in METHODS:
            if name == 'proposed':
                continue
            b = methods[name]
            row = {f: a[f] for f in PKEY if f != 'method'}
            row.update(view=a['view'], comparator=name,
                       proposed_issued=a['issued'], comparator_issued=b['issued'],
                       common=a['issued'] and b['issued'],
                       proposed_absence_reason=a['absence_reason'], comparator_absence_reason=b['absence_reason'])
            for metric in ('absolute_error_pp', 'brier_score', 'signed_error_pp'):
                row[metric+'_difference'] = a[metric] - b[metric] if row['common'] else ''
            common.append(row)
    summaries = []
    for level in ('operation', 'application_complete_campaigns'):
        fields = ('profile', 'scope', 'mode', 'view', 'comparator') + (('operation',) if level == 'operation' else ())
        grouped = defaultdict(list)
        for row in common:
            grouped[key(row, fields)].append(row)
        for k, values in sorted(grouped.items()):
            paired = [r for r in values if r['common']]
            by_campaign = defaultdict(list)
            for row in paired:
                by_campaign[campaign(row)].append(row)
            if level == 'operation':
                units = paired
            else:
                units = []
                for cg in by_campaign.values():
                    if len(cg) == len(APPS[cg[0]['profile']]):
                        unit = dict(cg[0])
                        for metric in ('absolute_error_pp', 'brier_score', 'signed_error_pp'):
                            name = metric+'_difference'
                            unit[name] = fmean(r[name] for r in cg)
                        units.append(unit)
            result = {'level': level, **dict(zip(fields, k))}
            # Use a common schema for both levels.
            result.setdefault('operation', 'ALL_COMPLETE')
            result.update(expected_operation_cells=len(values), common_operation_cells=len(paired),
                          expected_campaigns=len({campaign(r) for r in values}), paired_campaigns=len(units),
                          proposed_issued_cells=sum(r['proposed_issued'] for r in values),
                          comparator_issued_cells=sum(r['comparator_issued'] for r in values))
            for metric in ('absolute_error_pp', 'brier_score', 'signed_error_pp'):
                name = metric+'_difference'
                mean, lo, hi, strata, minimum = stratified_interval(units, name, [level, *k, name], draws, seed)
                result.update({name: mean, name+'_lower95': lo, name+'_upper95': hi})
            result.update(represented_strata=strata, minimum_pairs_per_stratum=minimum)
            summaries.append(result)
    return common, summaries


def validate_source(predictions, scores, manifest):
    observed_keys = unique(predictions, PKEY)
    expected = set()
    for app, ops in APPS.items():
        for law, rep, mode, method, op in product(LAWS, range(10), MODES, METHODS, ops):
            for scope, source, target in (('current','colocated','colocated'), ('current','split','split'), ('transfer','colocated','split')):
                expected.add((app,law,str(rep),mode,scope,source,target,method,op))
    assert set(observed_keys) == expected, 'prediction universe mismatch'
    assert len(expected) == 17280
    unique(scores, PKEY + ('view',))
    assert len(scores) == manifest['row_counts']['scores'] == 36459
    audit = []
    for row in scores:
        pred = observed_keys[key(row, PKEY)]
        assert pred['prediction'] != '' and float(pred['prediction']) == float(row['prediction'])
        n, s, p = int(row['test_requests']), int(row['test_successes']), float(row['prediction'])
        recomputed = {'brier_score': (s*(1-p)**2 + (n-s)*p**2)/n,
                      'signed_prediction_error': p-s/n, 'absolute_prediction_error': abs(p-s/n)}
        assert abs(float(row['test_success_fraction']) - s/n) <= 1e-12
        for field, value in recomputed.items():
            assert abs(float(row[field])-value) <= 1e-12, (key(row, PKEY),field)
        audited = dict(row, prediction_in_test_block_interval=row['prediction_in_test_block_interval']=='true')
        audited.update({'recomputed_'+f:v for f,v in recomputed.items()})
        audit.append(audited)
    return audit


def run(config_path=Path('configs/m7_complete_census.json')):
    _remote()
    config = _read(config_path)
    for lock in config['repository_locks']:
        assert _hash(Path(lock['path'])) == lock['sha256'], lock['path']
    out = Path('workflow-results/m7-census'); out.mkdir(parents=True, exist_ok=True)
    source = Path('workflow-results/m7-census-source')
    metadata = _download(config, source)
    source /= 'analysis'
    manifest = _read(source/'manifest.json')
    assert _hash(source/'manifest.json') == config['manifest_sha256']
    for name in ('predictions','scores','summary','contrasts','cell-diagnostics'):
        assert _hash(source/(name+'.csv')) == manifest['files'][name.replace('-','_')+'_sha256']
    assert _hash(Path('configs/m7_frozen_live.yaml')) == manifest['files']['config_sha256']
    predictions, scores = rows(source/'predictions.csv'), rows(source/'scores.csv')
    audited = validate_source(predictions, scores, manifest)
    observations = extract_observations(scores)
    census = census_rows(predictions, observations)
    assert len(census) == 34560
    write_csv(out/'forecast-census.csv', census)
    counts = {app: len(ops) for app,ops in APPS.items()}
    metrics = _cell_metrics(audited, counts)
    summary_audit = audit_summary(rows(source/'summary.csv'), metrics)
    assert len(summary_audit) == 117 and all(r['matches'] for r in summary_audit)
    frozen_config = load_frozen_live_validation_config('configs/m7_frozen_live.yaml')
    primary_audit = audit_primary_contrast(frozen_config, metrics, rows(source/'contrasts.csv'))
    assert primary_audit['matches']
    _write(out/'historical-reproduction.json', {'scores_checked':len(scores), 'summary_rows':summary_audit, 'primary':primary_audit})
    universe, campaigns, pmx = [], {}, []
    for app, ops in APPS.items():
        for placement, law, rep in product(('colocated','split'), LAWS, range(10)):
            cid = f'{app}--{placement}--{law}--r{rep}'
            campaigns[cid] = dict(campaign_id=cid,profile=app,placement=placement,failure_law=law,repetition=rep,operations=len(ops),source_run_id=config['source_run_id'])
            for op in ops:
                row = dict(campaigns[cid], operation=op)
                del row['operations']
                for view in VIEWS:
                    n,s = observations[(app,placement,law,str(rep),op,view)]
                    row.update({view+'_requests':n,view+'_successes':s,view+'_availability':s/n})
                universe.append(row)
                pmx.append(dict(campaign_id=cid,profile=app,placement=placement,failure_law=law,repetition=rep,operation=op,method='PMX',status='not_part_of_frozen_M7',prediction='',retained_native_development_sample=law=='NCD' and rep==0,reason='No independent PMX forecast in the immutable M7 analysis; later M9V development is separate.'))
    assert len(campaigns)==160 and len(universe)==480
    assert sum(r['all_sequence_requests'] for r in universe)==576000
    assert sum(r['stable_requests'] for r in universe)==435288
    write_csv(out/'campaigns.csv', list(campaigns.values()))
    write_csv(out/'operation-universe.csv', universe)
    write_csv(out/'pmx-scope.csv', pmx)
    grouped = defaultdict(list)
    fields = ('profile','scope','mode','view','method','operation')
    for row in census:
        grouped[key(row,fields)].append(row)
    operation_stats = [aggregate_operation(v,dict(zip(fields,k)),config['bootstrap_repetitions'],config['bootstrap_seed']) for k,v in sorted(grouped.items())]
    write_csv(out/'operation-summary.csv', operation_stats)
    grouped.clear()
    fields += ('source_placement','target_placement','failure_law')
    for row in census:
        grouped[key(row,fields)].append(row)
    condition_stats = [aggregate_operation(v,dict(zip(fields,k)),config['bootstrap_repetitions'],config['bootstrap_seed']) for k,v in sorted(grouped.items())]
    write_csv(out/'condition-summary.csv', condition_stats)
    common, comparisons = paired_rows(census,config['bootstrap_repetitions'],config['bootstrap_seed'])
    write_csv(out/'paired-case-census.csv', common)
    write_csv(out/'paired-summary.csv', comparisons)
    # Publish the exact original source tables too; no modified historical table.
    import shutil
    shutil.copytree(source, out/'historical', dirs_exist_ok=True)
    result = {'kind':'descriptive_reaggregation_of_opened_M7','source_run_id':config['source_run_id'],
              'source_head_sha':config['source_head_sha'],'head_sha':os.environ['GITHUB_SHA'],
              'config_sha256':_hash(config_path),'artifact_metadata':metadata,
              'campaigns':len(campaigns),'current_operation_cells':len(universe),
              'forecast_rows_all_modes_scopes_two_views':len(census),
              'all_test_requests':576000,'stable_test_requests':435288,
              'historical_score_mismatches':0,'historical_summary_mismatches':0,'primary_reproduced':True,
              'new_campaigns':0,'fits':0,'raw_native_reads':0,'raw_test_reads':0,
              'bootstrap_repetitions':config['bootstrap_repetitions'],'bootstrap_seed':config['bootstrap_seed'],
              'files':{p.relative_to(out).as_posix():_hash(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    _write(out/'manifest.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','artifact_metadata')}))


if __name__ == '__main__':
    run()
