"""Strict numerical freeze before any independent confirmation outcome opens."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import json
import os
from pathlib import Path

from . import v3_comparison_orchestration_v1 as old
from .v3_comparison_candidates_v1 import validate_forecasts, METHODS
from .v3_comparison_roles_v1 import load_role, digest
from .v3_primary_projection import read, write, sha

DESIGN=Path('configs/v4_confirmation_design_v1.json')


def verify_new_locks():
    config=read(Path('configs/v4_confirmation_locks_v1.json'))
    for path,expected in config['files'].items():
        if sha(Path(path))!=expected: raise ValueError('confirmation source changed: '+path)
    return config


def validate_complete(candidate, operations):
    """Missing numerical PMX/B0 is a blocking error, never an openable freeze."""
    validate_forecasts(candidate['forecasts'],operations,METHODS)
    if candidate['failures'] or any(candidate['source_candidate_digests'].get(k) is None for k in ('graph','pmx')):
        raise ValueError('a complete independent builder is missing')
    for op,forecasts in candidate['forecasts'].items():
        for method,value in forecasts.items():
            if value['status'] not in ('ok','unsupported'): raise ValueError(f'nonfinal forecast: {op}/{method}')
            if method in ('PMX','PMX_inclusive') and value['status']=='unsupported' and value['reason']!='unsupported_conditional_propagation_or_positivity':
                raise ValueError('PMX technical failure cannot be classified as unsupported')
        b0=forecasts['B0']
        if (b0['status']!='ok' or type(b0['attempts']) is not int or not b0['attempts']
            or type(b0['successes']) is not int or not 0<=b0['successes']<=b0['attempts']
            or float(Fraction(b0['successes'],b0['attempts']))!=b0['probability']):
            raise ValueError('B0 numerical forecast/counts not fixed')
    return True


def check_gate(root,identity=None):
    documents,_=load_role(root/'frozen','frozen_candidates',identity)
    candidate=documents['candidates.json'];receipt=documents['receipt.json'];gate=read(root/'gate.json')
    validate_complete(candidate,tuple(candidate['forecasts']))
    if (digest(candidate)!=receipt['candidate_digest'] or gate['candidate_digest']!=digest(candidate)
        or gate['frozen_seal_sha256']!=sha(root/'frozen/seal.json') or gate['identity']!=candidate['identity']
        or gate['all_numerical_forecasts_fixed'] is not True
        or receipt['frozen_head']!=os.environ['GITHUB_SHA']
        or str(receipt['workflow_run'])!=os.environ['GITHUB_RUN_ID']
        or receipt['evaluator_inputs_available_in_freeze_job'] is not False):
        raise ValueError('strict prospective gate does not match this sealed candidate/run')
    return documents,gate


def freeze(source,out,identity,operations):
    old.freeze_case(source,out,identity,operations)
    documents,_=load_role(out/'frozen','frozen_candidates',identity)
    validate_complete(documents['candidates.json'],operations)
    receipt=documents['receipt.json']['acquisition_receipt']
    if receipt['acquisition_head']!=os.environ['GITHUB_SHA'] or str(receipt['acquisition_run'])!=os.environ['GITHUB_RUN_ID']:
        raise ValueError('acquisition source head/run differs')
    if not all(receipt.get(k) for k in ('test_binding_seal_sha256','primary_closed_seal_sha256')):
        raise ValueError('independent confirmation roles were not sealed at acquisition')
    write(out/'gate.json',dict(identity=identity,candidate_digest=digest(documents['candidates.json']),
        frozen_seal_sha256=sha(out/'frozen/seal.json'),all_numerical_forecasts_fixed=True,
        created_at=datetime.now(timezone.utc).isoformat(),run=os.environ['GITHUB_RUN_ID'],
        head=os.environ['GITHUB_SHA'],closed_outcomes_downloaded=False,historical_C12_reclassified=False))
    check_gate(out,identity)


def summarize(source,out,settings_path,cases):
    old.summarize(source,out,settings_path,'main')
    found={}
    for path in (source/'primary').rglob('compact.json'):
        record=read(path);key=old.campaign_id(record['identity'])
        if (record['head']!=os.environ['GITHUB_SHA'] or record['run']!=os.environ['GITHUB_RUN_ID'] or key in found):
            raise ValueError('primary compact source/identity differs')
        found[key]=record
    expected={old.campaign_id(c['identity']):c for c in cases}
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
    report=dict(version='v4-independent-confirmation-result-v1',run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
        protocol_sha256=sha(settings_path),missing_campaigns=missing,checks=checks,
        qualified_within_declared_conditions=all(checks.values()),attempts=attempted,independently_verified_attempts=verified,
        supported_attempts=supported,unsupported_attempts=attempted-supported,ambiguous_attempts=ambiguous,
        incompatible_attempts=incompatible,primary_label_mismatches=mismatches,
        historical_DOWN_successes=recovery,resolved_retry_groups=retry,operations=rows,controls=controls,
        selection_by_E_equals_Y=False,forecasts_reestimated=False,superiority_required=False,
        statistical_guarantee_for_future_attempts_claimed=False,historical_C12_reclassified=False)
    write(out/'confirmation.json',report)
    write(out/'confirmation-seal.json',dict(files={'confirmation.json':sha(out/'confirmation.json')},
        run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA']))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['matrix','freeze','gate','evaluate','summarize'])
    p.add_argument('--config',type=Path,default=DESIGN);p.add_argument('--mode',choices=['main'],default='main')
    p.add_argument('--key');p.add_argument('--source',type=Path);p.add_argument('--evaluator',type=Path);p.add_argument('--out',type=Path)
    args=p.parse_args();verify_new_locks();settings,design,cases=old.planned_cases(args.config,'main')
    if len(cases)!=18 or sum(len(design['applications'][c['profile']]) for c in cases)!=60:
        raise ValueError('fixed confirmation census changed')
    if args.command=='matrix':
        if os.environ.get('GITHUB_RUN_ATTEMPT','1')!='1': raise ValueError('confirmation reruns need an explicit new protocol')
        values=dict(cases=dict(include=cases),profiles=list(design['applications']))
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as f:
                for k,v in values.items(): f.write(k+'='+json.dumps(v,separators=(',',':'))+'\n')
        print(json.dumps(dict(campaigns=18,operation_cases=60,new_confirmation=True)));return
    if os.environ.get('GITHUB_ACTIONS')!='true': raise ValueError('real confirmation analysis is remote only')
    if args.command=='summarize': summarize(args.source,args.out,args.config,cases);return
    case=next(c for c in cases if c['key']==args.key);identity=case['identity'];operations=design['applications'][case['profile']]
    if args.command=='freeze': freeze(args.source,args.out,identity,operations)
    elif args.command=='gate': check_gate(args.source,identity)
    else:
        check_gate(args.source,identity)
        expected=settings['test_seconds']*settings['request_rate_per_second']//len(operations)
        old.evaluate_case(args.source/'frozen',args.evaluator,args.out,identity,operations,expected)


if __name__=='__main__': main()
