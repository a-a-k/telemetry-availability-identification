"""Independent PMX/Palladio qualification on the eight Petclinic technical cases."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time

from .isolated_stochastic_fit import rows
from .pmx_adapter_conformance import compare_pcm,inspect_pcm,OPTIONS_SHA
from .pmx_application_comparison import run_application_pmx
from .pmx_composition_control import SUFFIXES,_hash,_read,_remote,_write
from .pmx_context_comparison import save_projection
from .pmx_database_client_adapter import project_campaign,DB_ADAPTER_VERSION
from .pmx_database_client_controls import control,SUCCESS
from .pmx_mixed_loop_bridge import bridge
from .pmx_observed_operations import NativeSpan
from .pmx_pmf_bridge import qualify
from .pmx_request_context import contextualize
from .pmx_retained_request_audit import inventory_variable_hex_ids

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'configs/petclinic_pmx_qualification.json'
CONTEXT_VERSION=DB_ADAPTER_VERSION+'+observed-full-caller-context-v1'
OPERATIONS=('list_owners','owner_details_with_visits','create_visit','list_vets')


def validate(path):
    config=_read(path)
    assert config['adapter_version']==CONTEXT_VERSION
    assert config['expected_controls']==SUCCESS
    for relative,expected in config['repository_locks'].items():
        assert _hash(ROOT/relative)==expected,relative
    return config


def prepare(config_path,source,options,out,sample_key):
    _remote();validate(config_path)
    assert _hash(options)==OPTIONS_SHA
    option_text=options.read_text().replace('traces/jaegercustomers.json','traces/observed.json')
    cases=[];source_provenance=None
    if sample_key=='controls':
        projected=[(name,*control(name)[:2]) for name in SUCCESS]
        expected_requests=10
    else:
        seal=_read(source/'seal.json')
        assert set(seal['files'])=={'requests.csv','native.json','manifest.json','source-artifact-audit.json'}
        assert {p.name for p in source.iterdir() if p.is_file()}==set(seal['files'])|{'seal.json'}
        for name,expected in seal['files'].items():
            assert _hash(source/name)==expected,name
        manifest=_read(source/'manifest.json')
        assert manifest['role']=='pmx_native_calibration' and manifest['usable'] is True
        assert sample_key==manifest['placement']+'-'+manifest['failure_law']
        requests=rows(source/'requests.csv')
        assert len(requests)==3600 and all(r['period']=='calibration' for r in requests)
        assert {r['operation'] for r in requests}==set(OPERATIONS)
        native=_read(source/'native.json')
        assert native['calibration_only'] and set(native['selected_trace_ids'])=={r['trace_id'] for r in requests}
        grouped={key:[NativeSpan(**s) for s in spans] for key,spans in native['spans'].items()}
        assert set(grouped)<=set(native['selected_trace_ids'])
        sample=dict(key=sample_key,profile=manifest['profile'],placement=manifest['placement'],
            failure_law=manifest['failure_law'],repetition=manifest['repetition'],source_run=manifest['source_run'])
        projected=[]
        for operation in OPERATIONS:
            result=contextualize(project_campaign(grouped,[r for r in requests if r['operation']==operation],
                declared_host='declared-physical-runner',invalid=native['parse']['invalid_traces']))
            projected.append((operation,result,None))
        expected_requests=900
        source_provenance=dict(metadata=manifest,seal=seal,source_archive=_read(source/'source-artifact-audit.json'),
            actual_input_files=sorted(seal['files']),health_files_read=0,our_graph_or_parameters_read=0,
            evaluator_files_read=0,baseline_outcomes_read=0,
            database_semantics='Observed JDBC client calls identify peer operations; they do not measure DB server internals or a standalone DB failure probability.')
    for name,result,expected in projected:
        case_id=sample_key+'--'+name
        root=out/'cases'/case_id
        save_projection(root,result)
        (root/'Options.txt').write_text(option_text)
        case=dict(case_id=case_id,operation=name,summary=result['summary'],expected_requests=expected_requests,
            files={p.relative_to(root).as_posix():_hash(p) for p in root.rglob('*') if p.is_file()})
        if expected is not None:
            case.update(control=True,expected_success=expected)
        else:
            case['sample']=sample
        cases.append(case)
    _write(out/'application-input-contract.json',dict(head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
        config_sha256=_hash(config_path),samples=[] if sample_key=='controls' else [dict(sample=sample,cases=cases)],
        context_controls=cases if sample_key=='controls' else [],source_provenance=source_provenance,
        evaluator_rows_read=0,our_estimates_read=0,scope='technical_interface_only'))


def collect(config_path,extractions,out):
    _remote();config=validate(config_path)
    records=[];models=[]
    for path in sorted(extractions.rglob('extraction-*.json')):
        record=_read(path)
        assert record['head_sha']==os.environ['GITHUB_SHA'] and record['config_sha256']==_hash(config_path)
        for model in record['models']:
            source=path.parent/'models'/model['model_id']
            for name,expected in model['files'].items(): assert _hash(source/name)==expected
            shutil.copytree(source,out/'models'/model['model_id'])
            models.append(model)
        records.append(record)
    assert len(records)==9 and {r['sample_key'] for r in records}==set(config['sample_keys'])
    assert sum(len(r['cases']) for r in records)==34
    assert len({m['model_id'] for m in models})==len(models)
    _write(out/'solver-contract.json',dict(models=models,extractions=records,model_count=len(models),
        config_sha256=_hash(config_path),head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID']))


def freeze(config_path,contract,solver,out):
    _remote();validate(config_path)
    prepared=_read(contract/'solver-contract.json')
    assert prepared['head_sha']==os.environ['GITHUB_SHA'] and prepared['config_sha256']==_hash(config_path)
    raw=_read(solver/'raw-result.json')['runs'] if (solver/'raw-result.json').exists() else []
    models={m['model_id']:m for m in prepared['models']}
    keys=[(r.get('model_id'),r.get('repetition')) for r in raw]
    assert len(keys)==len(set(keys)) and set(keys)<={(m,p) for m in models for p in (0,1)}
    for mid,model in models.items():
        for name,expected in model['files'].items(): assert _hash(contract/'models'/mid/name)==expected
    controls=[]
    for case,variants in SUCCESS.items():
        for variant,expected in variants.items():
            mid='controls--'+case+'--'+variant
            results=[r for r in raw if r.get('model_id')==mid]
            valid=len(results)==2 and all(qualify(r,expected)['software_oracle_pass'] for r in results)
            controls.append(dict(model_id=mid,expected=expected,qualified=valid,results=results))
    control_ok=all(r['qualified'] for r in controls)
    predictions=[];coverage=[]
    for record in prepared['extractions']:
        if record['sample_key']=='controls': continue
        placement,law=record['sample_key'].split('-',1)
        for case in record['cases']:
            operation=case['case_id'].split('--',1)[1]
            for variant in ('inclusive','conditional_local'):
                mid=case['case_id']+'--'+variant
                results=[r for r in raw if r.get('model_id')==mid]
                valid=(control_ok and len(results)==2 and all(qualify(r,None)['valid_probability'] for r in results)
                    and abs(results[0]['success_probability']-results[1]['success_probability'])<=1e-12)
                decision=next((d for d in case['variants'] if d['variant']==variant),{})
                status='valid_independent_pmx_forecast' if valid else ('control_gate_failed' if not control_ok else decision.get('status',case.get('error','unavailable')))
                if not valid and status=='prepared': status='no_valid_two_pass_solver_result'
                predictions.append(dict(profile='spring_petclinic_microservices',source_placement=placement,target_placement=placement,
                    failure_law=law,repetition=0,operation=operation,method='PMX_'+variant,mode='full',scope='current',
                    prediction=results[0]['success_probability'] if valid else None,status=status))
                coverage.append(dict(model_id=mid,valid=valid,extraction=case,solver_records=results))
    assert len(predictions)==64
    _write(out/'predictions.json',dict(scope='technical_interface_only',main_campaigns=0,predictions=predictions))
    _write(out/'coverage.json',coverage)
    _write(out/'controls.json',dict(qualified=control_ok,expected_software_oracle_passes=8,controls=controls))
    _write(out/'seal.json',dict(metadata=dict(head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
        config_sha256=_hash(config_path),evaluator_downloads_before_candidate_freeze=0),
        files={p.name:_hash(p) for p in out.iterdir() if p.is_file() and p.name!='seal.json'}))
    if not control_ok: raise ValueError('new database construct control gate failed; no forecasts qualified')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','prepare','extract','collect','freeze'])
    for name in ('source','options','out','contract','jar','extractions','solver'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--sample')
    args=parser.parse_args()
    if args.command=='validate': validate(CONFIG)
    elif args.command=='prepare': prepare(CONFIG,args.source,args.options,args.out,args.sample)
    elif args.command=='extract': extract(CONFIG,args.contract,args.sample,args.jar,args.out)
    elif args.command=='collect': collect(CONFIG,args.extractions,args.out)
    else: freeze(CONFIG,args.contract,args.solver,args.out)


# The versioned extract function below retains M9X extraction/audit/bridge logic.

def extract(config_path, contract, sample_key, jar, out):
    _remote()
    validate(config_path)
    inputs = _read(contract/'application-input-contract.json')
    assert inputs['head_sha']==os.environ['GITHUB_SHA'] and inputs['config_sha256']==_hash(config_path)
    if sample_key=='controls':
        cases = inputs['context_controls']
    else:
        sample = next(r for r in inputs['samples'] if r['sample']['key']==sample_key)
        cases = sample['cases']
    decisions, models = [], []
    for case in cases:
        root = contract/case.get('directory','cases/'+case['case_id'])
        for name,digest in case['files'].items():
            assert _hash(root/name)==digest,name
        row = dict(case_id=case['case_id'],qualified=False,variants=[],control=case.get('control',False))
        raw = out/'raw'/case['case_id']
        try:
            assert case['summary']['rejected_requests']==0
            assert case['summary']['projected_requests']==case['expected_requests']
            row['execution'] = run_application_pmx(jar,root,raw)
            actual = inspect_pcm(raw/'results')
            _write(raw/'resolved-pcm.json',actual)
            row.update(compare_pcm(actual,_read(root/'expected.json')))
            inventory = inventory_variable_hex_ids((raw/'stdout.log').read_text(errors='replace'),_read(root/'traces/observed.json'))
            row['reconstruction'] = inventory
            row['qualified'] = (row['qualified'] and row['execution']['exit_code']==0
                and all(inventory[k] for k in ('exact_trace_span_operation_parent_inventory',
                    'each_trace_reconstructed_once','reconstructed_nanosecond_bounds_match_input_microseconds'))
                and not inventory['unresolved_reconstructed_records'])
            if not row['qualified']:
                raise ValueError('context extraction fidelity differs')
            oracle = _read(root/'operation_oracle.json')
            for variant in (('inclusive',) if case.get('expected_error') else ('inclusive','conditional_local')):
                if variant=='conditional_local' and case['summary']['unsupported_conditional_local_operations']:
                    row['variants'].append(dict(variant=variant,status='unsupported_conditional_propagation_or_positivity'))
                    continue
                try:
                    model_id = case['case_id']+'--'+variant
                    target = out/'models'/model_id
                    target.mkdir(parents=True,exist_ok=False)
                    for suffix in SUFFIXES:
                        shutil.copyfile(raw/'results'/('extracted.'+suffix),target/('extracted.'+suffix))
                    started = time.perf_counter()
                    updated,changes = bridge((target/'extracted.repository').read_text(),oracle,variant)
                    (target/'extracted.repository').write_text(updated)
                    model = dict(model_id=model_id,case_id=case['case_id'],variant=variant,
                                 operation=case['operation'],changes=changes,
                                 bridge_seconds=time.perf_counter()-started,
                                 files={p.name:_hash(p) for p in target.iterdir()},adapter_version=CONTEXT_VERSION)
                    if case.get('expected_error'):
                        model.update(control=True,expected_error=case['expected_error'],
                                     adapter_version='unchanged-native-operation-identity-negative-control')
                    elif case.get('control'):
                        model.update(control=True,expected_success=case['expected_success'][variant])
                    else:
                        model['sample'] = case['sample']
                    models.append(model)
                    row['variants'].append(dict(variant=variant,status='prepared',model_id=model_id))
                except Exception as exc:
                    row['variants'].append(dict(variant=variant,status='bridge_error',error=f'{type(exc).__name__}: {exc}'))
        except Exception as exc:
            row.update(qualified=False,error=f'{type(exc).__name__}: {exc}')
        decisions.append(row)
        _write(out/'decisions'/(case['case_id']+'.json'),row)
    _write(out/('extraction-'+sample_key+'.json'),dict(sample_key=sample_key,cases=decisions,models=models,
        head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],config_sha256=_hash(config_path),evaluator_rows_read=0))

if __name__=="__main__": main()
