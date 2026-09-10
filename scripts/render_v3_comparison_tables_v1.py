"""Render existing compact remote comparison metrics; never fit or resample."""
import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path


METHODS = ('Gstar', 'GID', 'Gselected', 'G_without_deadline', 'G_without_selection',
           'G_without_completion', 'G0', 'B0', 'PMX', 'PMX_inclusive')


def fmt(value):
    if value is None:
        return 'not estimable'
    if isinstance(value, float):
        return f'{value:.6g}'
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def safe_cell(value):
    return fmt(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join('---' for _ in headers)+' |'] +
                     ['| '+' | '.join(safe_cell(v) for v in row)+' |' for row in rows])


def csv_bytes(rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    target = io.StringIO(newline='')
    writer = csv.DictWriter(target, fieldnames=keys, lineterminator='\n')
    writer.writeheader()
    for row in rows:
        # Empty CSV cells represent null, never zero. Structured fields stay exact JSON.
        writer.writerow({k: json.dumps(v, sort_keys=True, allow_nan=False) if isinstance(v, (dict, list))
                         else '' if v is None else v for k, v in row.items()})
    return target.getvalue().encode('utf-8')


def render(source, out):
    raw = source.read_bytes(); document = json.loads(raw)
    analysis = document['analysis']
    if analysis['method_slots'] != len(analysis['attempted_census']):
        raise ValueError('attempted method-slot census differs')
    keys = [(r['campaign_id'], r['operation'], r['method']) for r in analysis['attempted_census']]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate attempted cell')
    expected = document['operation_cells_per_method'] * len(METHODS)
    if expected != len(keys):
        raise ValueError('not every planned method slot was retained')
    for r in analysis['attempted_census']:
        if r['forecast']['status'] != 'ok' and r['metrics'] is not None:
            raise ValueError('absence incorrectly carries numerical forecast metrics')
    out.mkdir(parents=True, exist_ok=True)
    own = []; per_operation = []; absent = []
    for app, a in analysis['applications'].items():
        if set(a['methods']) != set(METHODS):
            raise ValueError('method family changed')
        for method in METHODS:
            m = a['methods'][method]; means = m['standardized_mean'] or {}
            own.append(dict(application=app, method=method, status=m['status'], planned_cells=m['planned_cells'],
                scored_cells=m['scored_cells'], attempts=m['attempts'], **{k: means.get(k) for k in ('absolute_error_pp','signed_error_pp','brier')},
                median_absolute_error_pp=m.get('cell_median_absolute_error_pp'), p90_absolute_error_pp=m.get('cell_p90_absolute_error_pp'),
                forecast_status_counts=m['forecast_status_counts'], absence_reasons=m['absence_reasons']))
            for op, item in m['per_operation'].items():
                per_operation.append(dict(application=app, operation=op, method=method, **item))
            for reason, count in m['absence_reasons'].items():
                absent.append(dict(application=app, method=method, reason=reason, cells=count))
    contrast_keys=('application','left','right','estimate_pp','interval_pp','status','common_cells',
        'complete_common_campaigns','planned_cells','planned_conditions','retained_conditions',
        'confidence_level','bootstrap_draws','bootstrap_seed','complete_support_is_conditioned_on_not_imputed',
        'coverage_uncertainty_included','finite_sample_family_coverage_guaranteed')
    contrasts=[{k:r[k] for k in contrast_keys} for r in analysis['primary_contrasts']]
    if len(contrasts)!=6:
        raise ValueError('primary contrast family changed')
    stable=[]
    for app, methods in analysis['stable']['applications'].items():
        for method,m in methods.items():
            stable.append(dict(application=app,method=method,**m))
    files={'own-support.csv':csv_bytes(own),'per-operation.csv':csv_bytes(per_operation),
           'primary-contrasts.csv':csv_bytes(contrasts),'absence-reasons.csv':csv_bytes(absent),
           'stable.csv':csv_bytes(stable),'stage-costs.csv':csv_bytes(analysis['costs']['stage_summaries']),
           'attempted-census.csv':csv_bytes(analysis['attempted_census'])}
    transferred=analysis['transfer']
    files['transfer.csv']=csv_bytes(transferred['census'])
    text = [f"# {'Independent main' if document['mode']=='main' else 'Development preflight'} comparison: retained remote tables",
        f"Source run `{document['run_id']}`, head `{document['head']}`, mode `{document['mode']}`. "
        f"Planned campaigns: {document['campaign_count']}; operation cells per method: {document['operation_cells_per_method']}; "
        f"retained method slots: {analysis['method_slots']}. Source SHA256: `{sha256(raw).hexdigest()}`.",
        'These tables copy metrics already computed by the frozen remote analysis. No local fitting, replay, bootstrap or imputation is performed. '
        'Null estimates remain null. Own-support means cannot be interpreted as paired comparisons when support differs. '
        'This generated export is not a publication-readiness verdict.',
        '## Own support and error',
        table(['Application','Method','Points / planned','MAE (pp)','Signed (pp)','Brier','Median AE (pp)','P90 AE (pp)'],
            [[r['application'],r['method'],f"{r['scored_cells']} / {r['planned_cells']}",r['absolute_error_pp'],r['signed_error_pp'],r['brier'],r['median_absolute_error_pp'],r['p90_absolute_error_pp']] for r in own]),
        '## Prespecified paired contrasts',
        'Negative differences favour Gstar only on the displayed complete common campaign support. '
        'Intervals are the frozen paired campaign bootstrap, conditional on retained support. '
        'Nonsignificance does not establish equivalence and no finite-sample familywise guarantee is asserted.',
        table(['Application','Comparator','MAE difference (pp)','Interval (pp)','Complete campaigns','Common cells','Status'],
            [[r['application'],r['right'],r['estimate_pp'],r['interval_pp'],r['complete_common_campaigns'],r['common_cells'],r['status']] for r in contrasts]),
        '## Coverage limitations',
        table(['Application','Method','Absent cells','Reason'],[[r['application'],r['method'],r['cells'],r['reason']] for r in absent]),
        '## Measured stage costs',
        'Shared acquisition and extraction are counted once. Stage and process totals overlap and must not be summed. '
        'Untimed integration labour, incremental update, monitoring off/on overhead and scaling are unknown, not zero.',
        table(['Method','Stage','Observations','Median seconds','P90 seconds'],
            [[r[k] for k in ('method','stage','observations','median_seconds','p90_seconds')] for r in analysis['costs']['stage_summaries']]),
        '## Stable and source-only transfer views',
        f"The unchanged forecasts on stable attempts are in `stable.csv`; primary results use all qualified attempts. "
        f"Source-only transfer reports {transferred['point_forecasts']} points over {transferred['planned_slots']} planned slots "
        f"(coverage {transferred['point_coverage']}). Unsupported transfer is not replaced by target calibration.",
        '## Reuse and audit scope',
        'CSV files retain all operations, statuses, exact serialized structured fields and missing values. '
        'The source comparison JSON and its separate candidate/evaluator seals remain the authority. '
        'Archive verification proves retention integrity; full run-level scientific qualification must be assessed separately.']
    files['README.md']=('\n\n'.join(text)+'\n').encode()
    for name,data in files.items():
        path=out/name
        if path.exists() and path.read_bytes()!=data:
            raise ValueError('existing generated table differs: '+str(path))
        path.write_bytes(data)
    provenance=dict(version='v3-comparison-publication-tables-v1',source=str(source.as_posix()),
        source_sha256=sha256(raw).hexdigest(),run_id=document['run_id'],head=document['head'],mode=document['mode'],
        local_fit_or_resampling=False,source_metrics_copied_without_recalculation=True,
        planned_method_slots=expected,outputs={name:dict(bytes=len(data),sha256=sha256(data).hexdigest()) for name,data in files.items()})
    (out/'provenance.json').write_bytes((json.dumps(provenance,indent=2)+'\n').encode())
    (out/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    return provenance


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();result=render(args.source,args.out);print(json.dumps({k:v for k,v in result.items() if k!='outputs'}))
