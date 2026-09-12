"""Same forecast and primary summaries, with no unplanned placement transfer.

Functions below retain the original arithmetic. Measurement provenance points
to the fixed source; actual aggregation provenance is separately explicit.
"""
import os
from pathlib import Path
from telemetry_availability.v3_comparison_orchestration_v1 import (
    planned_cases,read,write,sha,campaign_id,find_role,load_role,missing_campaign,METHODS)
from telemetry_availability.v3_comparison_evaluation_v1 import complete_analysis
from telemetry_availability import v3_comparison_evaluation_v1 as evaluation
from v4_confirmed_source_v3 import SOURCE_RUN,SOURCE_HEAD


def no_unplanned_transfer(campaigns,design):
    if design['placements']!=['split']:raise ValueError('this repair is only for the prespecified split-only cohort')
    return dict(status='not_planned',reason='colocated is not part of the fixed independent confirmation design',
        planned_slots=0,point_forecasts=0,point_coverage=0,census=[])


def install():
    evaluation.transfer_census=no_unplanned_transfer


def summarize_forecasts(source, out, settings_path, mode):
    settings, design, cases = planned_cases(settings_path, mode)
    reports = {}; campaigns = []; costs = []; gates = []
    for path in source.rglob('evaluation-seal.json'):
        seal = read(path)
        if seal['head'] != SOURCE_HEAD or seal['files'] != {'evaluation.json': sha(path.parent/'evaluation.json')}:
            raise ValueError('evaluation report provenance differs')
        report = read(path.parent/'evaluation.json'); key = campaign_id(report['identity'])
        if report['identity'] != seal['identity'] or key in reports:
            raise ValueError('duplicate/cross-campaign evaluation')
        reports[key] = report
    expected_ids = {campaign_id(case['identity']) for case in cases}
    if not set(reports) <= expected_ids:
        raise ValueError('unplanned evaluation report')
    for case in cases:
        identity = case['identity']; key = campaign_id(identity)
        operations = design['applications'][case['profile']]
        frozen_root = find_role(source, 'frozen_candidates', identity)
        frozen = None
        if frozen_root:
            documents, _ = load_role(frozen_root, 'frozen_candidates', identity)
            frozen = documents['candidates.json']
            for role, values in documents['costs.json'].items():
                costs.append(dict(campaign_id=key, job_role=role, attempt_id='1', **values))
        report = reports.get(key)
        if report:
            if not frozen_root or report['frozen_role_seal_sha256'] != sha(frozen_root/'seal.json'):
                raise ValueError('evaluated candidate differs from final frozen census')
            if report['identity'] != identity:
                raise ValueError('evaluation outside planned identity/protocol')
            campaigns.append(report['views']['all_sequence'])
        else:
            campaigns.append(missing_campaign(identity, operations, frozen))
        gates.append(dict(campaign_id=key, frozen_candidates=frozen is not None,
            evaluator_qualified=bool(report and report['views']['all_sequence']['evaluator_status']=='qualified'),
            all_ten_method_slots_per_operation=bool(frozen and all(set(row)==set(METHODS) for row in frozen['forecasts'].values())),
            pmx_pipeline_accounted=bool(frozen and all(frozen['forecasts'][op][method]['status'] in ('ok', 'unsupported')
                for op in operations for method in ('PMX', 'PMX_inclusive'))),
            graph_construction_available=bool(frozen and all(frozen['forecasts'][op]['Gstar']['status'] in ('ok', 'unsupported') for op in operations))))
    analysis = complete_analysis(campaigns, list(reports.values()), design, costs)
    # Preflight is a pipeline/semantic integrity check, not an accuracy threshold.
    integrity = all(all(value for key, value in gate.items() if key!='campaign_id') for gate in gates)
    supported_primary = sum(c['common_cells'] for c in analysis['primary_contrasts']) > 0
    result = dict(version='v3-prospective-comparison-result-v1', mode=mode,
        data_role='prospective_main' if mode=='main' else 'development_preflight',
        main_campaigns=len(cases) if mode=='main' else 0, campaign_count=len(cases),
        operation_cells_per_method=sum(len(row['operations']) for row in campaigns),
        protocol_sha256=sha(settings_path), head=SOURCE_HEAD, run_id=str(SOURCE_RUN),
        candidate_evaluator_integrity=integrity, nonempty_primary_family=supported_primary,
        qualification_uses_forecast_error=False, admission_candidate=integrity and supported_primary,
        campaign_gates=gates, analysis=analysis)
    result.update(aggregation_version='v4-summary-repair-v3',analysis_run=os.environ['GITHUB_RUN_ID'],analysis_head=os.environ['GITHUB_SHA'])
    write(out/'comparison.json', result)
    write(out/'comparison-seal.json', dict(files={'comparison.json': sha(out/'comparison.json')},
        head=SOURCE_HEAD, run_id=str(SOURCE_RUN), protocol_sha256=sha(settings_path)))


def summarize(source,out,settings_path,cases):
    summarize_forecasts(source,out,settings_path,'main')
    found={}
    for path in (source/'primary').rglob('compact.json'):
        record=read(path);key=campaign_id(record['identity'])
        if (record['head']!=SOURCE_HEAD or record['run']!=str(SOURCE_RUN) or key in found):
            raise ValueError('primary compact source/identity differs')
        found[key]=record
    expected={campaign_id(c['identity']):c for c in cases}
    if not set(found)<=set(expected): raise ValueError('unplanned primary campaign')
    rows=[];controls=[];missing=[]
    for key,case in expected.items():
        if key not in found: missing.append(case['identity']);continue
        record=found[key]
        for value in record['test']['operations']: rows.append(dict(identity=case['identity'],**value))
        if record['controls']:
            for value in record['controls']['operations']:controls.append(dict(identity=case['identity'],**value))
    attempted=sum(r['attempts'] for r in rows)
    verified=sum(r['primary_verified_attempts'] for r in rows)
    mismatches=sum(r['primary_label_mismatches'] for r in rows)
    incompatible=sum(r.get('incompatible_attempts',0) for r in rows)
    supported=sum(r['attempts'] for r in rows if r['status']=='bounded')
    ambiguous=sum(r.get('ambiguous_attempts',0) for r in rows)
    recovery={app:sum(r.get('mechanism_counts',{}).get('successful_invocation_with_selected_historical_DOWN',0)
        for r in rows if r['identity']['application']==app) for app in read(settings_path)['design']['applications']}
    retry=sum(r.get('mechanism_counts',{}).get('declared_single_retry_503_then_201_with_one_observed_receiver',0) for r in rows+controls)
    normal_point_successes=sum(r.get('by_control_kind',{}).get('normal',{}).get('lower_count',0) for r in controls)
    checks=dict(all_18_campaigns_primary_verified=not missing and attempted==verified==64800,
        registered_verdicts_match_primary=mismatches==0,
        both_sided_compatibility_on_supported_attempts=supported>0 and incompatible==0,
        historical_DOWN_success_mechanism_in_each_application=all(recovery.values()),
        declared_retry_resolved_from_native_evidence=retry>0,
        all_48_directed_controls_verified=sum(r['primary_verified_attempts'] for r in controls)==48,
        directed_controls_compatible=all(r.get('incompatible_attempts')==0 for r in controls),
        ordinary_control_point_successes_present=normal_point_successes>0)
    report=dict(version='v4-independent-confirmation-result-v1',run=str(SOURCE_RUN),head=SOURCE_HEAD,
        protocol_sha256=sha(settings_path),missing_campaigns=missing,checks=checks,
        qualified_within_declared_conditions=all(checks.values()),attempts=attempted,independently_verified_attempts=verified,
        supported_attempts=supported,unsupported_attempts=attempted-supported,ambiguous_attempts=ambiguous,
        incompatible_attempts=incompatible,primary_label_mismatches=mismatches,
        historical_DOWN_successes=recovery,resolved_retry_groups=retry,operations=rows,controls=controls,
        selection_by_E_equals_Y=False,forecasts_reestimated=False,superiority_required=False,
        statistical_guarantee_for_future_attempts_claimed=False,historical_C12_reclassified=False)
    report.update(aggregation_version='v4-summary-repair-v3',analysis_run=os.environ['GITHUB_RUN_ID'],analysis_head=os.environ['GITHUB_SHA'])
    write(out/'confirmation.json',report)
    write(out/'confirmation-seal.json',dict(files={'confirmation.json':sha(out/'confirmation.json')},
        run=str(SOURCE_RUN),head=SOURCE_HEAD))
