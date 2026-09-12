"""Retain every fixed missingness setting and aggregate counts, never models."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from retain_v3_attempt_audit_v1 import table_bytes
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases

SOURCE_RUN=34703686592
SOURCE_HEAD='12ddb09369ee6e0b60ca4c7db6fe1e749530b7df'
INFORMATION=('none','selection_and_admission','entry_result','required_completions','all_native')


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=int,required=True);args=p.parse_args()
    run=transport.read_api(f'actions/runs/{args.run}')
    versions={'.github/workflows/v4-missingness-v2.yml':2,'.github/workflows/v4-missingness-v3.yml':3}
    if run['path'] not in versions or run['status']!='completed' or run['run_attempt']!=1:
        raise ValueError('fixed missingness execution differs')
    config_path=Path(f'configs/v4_missingness_execution_v{versions[run["path"]]}.json')
    config=json.loads(config_path.read_bytes())
    settings,design,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    artifacts=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    out=Path(f'docs/evidence/v4-missingness-v2-{args.run}');tables=Path(f'docs/tables/v4-missingness-v2-{args.run}')
    for root in (out,tables):transport.persist(root/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    rows=[];coverage=[];receipts=[]
    expected_settings={(m,l,i)for m in config['mechanisms']for l in config['levels']for i in INFORMATION}
    for profile in design['applications']:
        cohort=[c for c in cases if c['profile']==profile];allowed={c['key']+'.json'for c in cohort}|{'receipt.json'}
        matching=[a for a in artifacts if a['name']==f'v4-missingness-compact-{profile}-{args.run}']
        if len(matching)!=1:raise ValueError('missing fixed application profile')
        a=matching[0]
        if a['workflow_run']['id']!=args.run or a['workflow_run']['head_sha']!=run['head_sha']:raise ValueError('provider evidence identity differs')
        files=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,allowed)
        if set(files)!=allowed:raise ValueError('incomplete six-campaign missingness census')
        for name,data in files.items():transport.persist(out/profile/name,data)
        for case in cohort:
            data=json.loads(files[case['key']+'.json'])
            if (data['run']!=str(args.run) or data['head']!=run['head_sha'] or data['source_run']!=SOURCE_RUN
                or data['source_head']!=SOURCE_HEAD or data['identity']!=case['identity'] or data['selected_by_E_equals_Y'] is not False
                or data['config_sha256']!=sha256(config_path.read_bytes()).hexdigest()):
                raise ValueError('missingness source/population/config differs')
            expected_n=settings['test_seconds']*settings['request_rate_per_second']//len(design['applications'][profile])
            if {r['operation']for r in data['operations']}!=set(design['applications'][profile]):raise ValueError('operation census differs')
            for operation in data['operations']:
                base=dict(application=profile,placement=case['identity']['placement'],law=case['identity']['law'],
                    repetition=case['identity']['repetition'],operation=operation['operation'])
                if operation['attempts']!=expected_n:raise ValueError('missingness changed primary population')
                coverage.append(dict(base,status=operation['status'],attempts=expected_n,reason=operation.get('reason')))
                if operation['status']=='unsupported':continue
                if (operation['status']!='experimented' or operation['population_selected_by_E_equals_Y'] is not False
                    or operation['qualification']['exact_core_predicate_agreement'] is not True):raise ValueError('unverified missingness output')
                measured=operation['rows']
                if len(measured)!=len(expected_settings) or {(r['mechanism'],r['missing_fraction_requested'],r['information'])for r in measured}!=expected_settings:
                    raise ValueError('missing/duplicated fixed missingness setting')
                for row in measured:
                    n=row['attempts']
                    if (n!=expected_n or row['point_identified_attempts']+row['ambiguous_attempts']!=n
                        or not 0<=row['lower_count']<=row['upper_count']<=n
                        or abs(row['width']-(row['upper_count']-row['lower_count'])/n)>1e-15
                        or abs(row['compatible_fraction']-(1-(row['success_excluded']+row['failure_excluded'])/n))>1e-15):
                        raise ValueError('count-derived missingness metric differs')
                    rows.append(dict(base,**row))
        receipts.append({k:a[k]for k in ('id','name','digest','size_in_bytes')})
    groups=defaultdict(list)
    for r in rows:groups[r['application'],r['mechanism'],r['missing_fraction_requested'],r['information']].append(r)
    summaries=[]
    additive=('attempts','successes','lower_count','upper_count','ambiguous_attempts','point_identified_attempts',
        'success_excluded','failure_excluded','fully_observed_states','known_native_coordinates','hidden_native_coordinates',
        'affected_attempts','revealed_native_coordinates','revealed_attempts','ambiguities_resolved')
    for (app,mechanism,level,information),rs in groups.items():
        totals={k:sum(r[k]for r in rs)for k in additive};n=totals['attempts']
        summaries.append(dict(application=app,mechanism=mechanism,missing_fraction_requested=level,information=information,
            operation_cases=len(rs),**totals,identified_lower=totals['lower_count']/n,identified_upper=totals['upper_count']/n,
            width=(totals['upper_count']-totals['lower_count'])/n,point_identified_fraction=totals['point_identified_attempts']/n,
            compatible_fraction=1-(totals['success_excluded']+totals['failure_excluded'])/n))
    for name,values in [('all-case-settings',rows),('application-summary',summaries),('coverage',coverage)]:
        transport.persist(tables/(name+'.csv'),table_bytes(values))
    receipt=dict(run=args.run,head=run['head_sha'],source_run=SOURCE_RUN,source_head=SOURCE_HEAD,artifacts=receipts,
        operation_cases=len(coverage),supported_operation_cases=sum(r['status']=='experimented'for r in coverage),
        settings=len(rows),local_model_execution=False,full_primary_records_downloaded=False)
    transport.persist(out/'retention.json',transport.encoded(receipt));transport.persist(tables/'summary.json',transport.encoded(receipt))
    print(json.dumps(receipt))


if __name__=='__main__':main()
