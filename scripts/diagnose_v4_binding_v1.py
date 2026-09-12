"""Fixed retrospective diagnostic of the evidence-motivated binding candidate."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile

from audit_v3_attempts_v1 import ROOT, PROTOCOL, ARCHIVE, MAIN_RUN, fetch, read, write, digest
import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.v4_execution_binding_v1 import fit_operation
from telemetry_availability.v3_application_execution_v2 import BindingUnsupported
from telemetry_availability.v3_ordinary_identity_v2 import load_bundle
from telemetry_availability.v3_comparison_roles_v1 import load_role
from telemetry_availability.graph_execution_model_v1 import solve, predicates
from telemetry_availability.attempt_compatibility_audit_v1 import compatibility, summarize_attempts
from telemetry_availability.b0_frequency_v3_csv_v2 import decode_outcome
from telemetry_availability.exact_comparison_v2 import METHODS, REPRESENTATIONS, project
from benchmark_v3_exact_comparison_v2 import backend

CONFIG=ROOT/'configs/v4_binding_diagnostic_v1.json'


def prepare():
    protocol=read(PROTOCOL);by_key={c['artifact_key']:c for c in protocol['cases']};keys=[]
    for app in sorted({c['identity']['application'] for c in protocol['cases']}):
        keys.extend([c['artifact_key'] for c in protocol['cases'] if c['identity']['application']==app][:4])
    evidence=ROOT/'docs/evidence/v3-attempt-audit-v1-34694957306/all/spring_petclinic_microservices/cases'
    if len(list(evidence.glob('*.json')))!=80:raise ValueError('complete Petclinic audit required for selection')
    reasons={k:'fixed initial audit wave' for k in keys};selection_sources={}
    for path in sorted(evidence.glob('*.json')):
        case=read(path)
        if any(r.get('incompatible_flag_counts',{}).get('required_completion_false',0) for r in case['operations']):
            key=case['artifact_key'];ident=case['identity']
            control=f"{ident['application']}--{ident['placement']}--N--r{ident['repetition']}"
            keys.extend([key,control]);reasons[key]='observed rescued mandatory-call failure'
            reasons.setdefault(control,'same placement/repetition under N')
            selection_sources[path.relative_to(ROOT).as_posix()]=digest(path)
    keys=list(dict.fromkeys(keys))
    write(CONFIG,dict(version='v4-binding-diagnostic-v1',cases=[by_key[k] for k in keys],
        selection_reasons=reasons,selection_source_sha256=selection_sources,
        source_main_run=MAIN_RUN,source_attempt_audit_run=34694957306,
        data_role='retrospective diagnostic on already-open calibration attempts; not independent confirmation',
        exact_methods=list(METHODS),representations=list(REPRESENTATIONS),
        observed_external_labels_used_by_binding=False,performance_claims=False,
        candidate_selection_by_minimum_MAE=False,all_attempts_retained=True))
    print(json.dumps(dict(campaigns=len(keys),by_application=dict(Counter(by_key[k]['identity']['application'] for k in keys)))))


def check_witnesses(model,result):
    checked=0
    for category in result['category_certificates']:
        known=dict(zip(model['signal_ids'],category['values']))
        for functional,extrema in category['extrema'].items():
            for side,endpoint in [('lower','minimum'),('upper','maximum')]:
                values=extrema[side+'_witness']
                if values is None:continue
                state=dict(zip(model['signal_ids'],values))
                if any(v is not None and state[k]!=v for k,v in known.items()):raise ValueError('witness violates observation')
                if predicates(model,state)[functional]!=extrema[endpoint]:raise ValueError('witness fails its endpoint')
                checked+=1
    return checked


def run(args):
    if (os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=transport.REPO
            or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'):raise ValueError('remote first attempt required')
    config=read(CONFIG);settings=read(ROOT/'configs/v3_comparison_execution_v3.json')
    sources={s['name']:s for part in read(ARCHIVE)['parts'] for s in part['sources']}
    for path,expected in config['selection_source_sha256'].items():
        if digest(ROOT/path)!=expected:raise ValueError('selection evidence changed')
    cases=[c for c in config['cases'] if c['identity']['application']==args.profile]
    for case in cases:
        key=case['artifact_key'];identity=case['identity'];summaries=[];models={};all_diagnostics={}
        with tempfile.TemporaryDirectory(prefix='v4-binding-') as temporary:
            temp=Path(temporary);provenance={}
            for role in ('raw','graph'):provenance[role]=fetch(sources[f'v3-comparison-{role}-{key}-{MAIN_RUN}'],temp/role)
            ordinary_root=next(p.parent for p in (temp/'raw').rglob('seal.json') if p.parent.as_posix().endswith('/roles/ordinary'))
            data,_=load_bundle(ordinary_root)
            graph_root=next((temp/'graph').rglob('models.json')).parent
            legacy,_=load_role(graph_root,'graph_candidates',identity=identity)
            for operation,spec in settings['profiles'][args.profile]['operations'].items():
                try:model,report,diagnostics=fit_operation(data,operation,spec,identity)
                except BindingUnsupported as exc:
                    summaries.append(dict(operation=operation,status='unsupported',reason=str(exc)));continue
                # The candidate's state construction must be invariant to the
                # stored external label. This pass is outside any cost study.
                changed=dict(data,**{'requests.json':[dict(r,semantic_success=not decode_outcome(r['semantic_success'])) for r in data['requests.json']]})
                label_flipped,_,_=fit_operation(changed,operation,spec,identity)
                if label_flipped!=model:raise ValueError('binding depends on external semantic labels')
                result=solve(model);bounds={tuple(c['values']):c['extrema']['execution'] for c in result['category_certificates']}
                outcomes={r['request_id']:decode_outcome(r['semantic_success']) for r in data['requests.json']}
                rows=[]
                for record in diagnostics:
                    values=tuple(record['observation'][k] for k in model['signal_ids']);bound=bounds[values];y=outcomes[record['request_id']]
                    rows.append(dict(request_id=record['request_id'],outcome=y,lower=bound['minimum'],upper=bound['maximum'],
                        compatibility=compatibility(bound['minimum'],y,bound['maximum']),fully_observed=None not in values))
                summary=summarize_attempts(rows);summary.update(operation=operation,status='diagnosed',
                    legacy_forecast=legacy['candidates.json']['forecasts'][operation]['Gstar'],
                    revised_estimate=result['estimates']['execution'],label_flip_invariant=True,
                    checked_witness_endpoints=check_witnesses(model,result),completion_evidence_counts=report['completion_evidence_counts'])
                exact=[]
                for representation in config['representations']:
                    projected=project(model,representation)
                    for method in config['exact_methods']:
                        obj=backend(method);obj.rebuild(projected);actual=obj.query(projected)
                        if actual!=result['estimates']:raise ValueError(f'exact mismatch {key}/{operation}/{method}/{representation}')
                        exact.append(dict(method=method,representation=representation,all_eleven_bounds_exact=True))
                summary['exact_qualification']=exact;summaries.append(summary);models[operation]=model
                all_diagnostics[operation]=dict(binding=diagnostics,compatibility=rows)
            write(args.out/'full'/key/'models.json',models)
            write(args.out/'full'/key/'attempts.json',all_diagnostics)
            output=dict(version=config['version'],identity=identity,run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
                config_sha256=digest(CONFIG),data_role=config['data_role'],sources=provenance,operations=summaries,
                performance_claims=False,independent_confirmation=False)
            write(args.out/'compact'/(key+'.json'),output)
            print(json.dumps(dict(case=key,operations=len(summaries),
                incompatible_attempts=sum(r.get('incompatible_attempts',0) for r in summaries))),flush=True)
    write(args.out/'compact/receipt.json',dict(run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
        profile=args.profile,campaigns=len(cases),config_sha256=digest(CONFIG),independent_confirmation=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True);sub.add_parser('prepare')
    r=sub.add_parser('run');r.add_argument('--profile',required=True);r.add_argument('--out',type=Path,required=True)
    args=p.parse_args();prepare() if args.command=='prepare' else run(args)
