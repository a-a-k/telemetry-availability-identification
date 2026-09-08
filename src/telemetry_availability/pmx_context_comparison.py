"""Retained independent PMX comparison with observed caller-context identities."""
import argparse
import os
from pathlib import Path
import shutil
import time

from .pmx_adapter_conformance import compare_pcm, inspect_pcm
from .pmx_application_comparison import (
    accepted_request, run_application_pmx, freeze_candidates, evaluate,
    validate as validate_base,
)
from .pmx_composition_control import SUFFIXES, _download, _hash, _read, _remote, _write
from .pmx_mixed_loop_bridge import bridge
from .pmx_pmf_bridge import qualify
from .pmx_request_context import contextualize, expected_pcm, control, CONTROL_SUCCESS, CONTEXT_VERSION
from .pmx_retained_request_audit import inventory_variable_hex_ids


def validate(path):
    config = validate_base(path)
    assert config['adapter_version'] == CONTEXT_VERSION
    assert config['expected_controls'] == CONTROL_SUCCESS
    return config


def save_projection(root, result):
    for name in ('mapping','native_audit','request_audit','rejected_requests','operation_oracle','edge_oracle','summary'):
        _write(root/(name+'.json'), result[name])
    _write(root/'traces/observed.json',result['envelope'])
    _write(root/'expected.json',expected_pcm(result))


def prepare(config_path, inputs, out):
    _remote()
    config = validate(config_path)
    metadata = _download(config, inputs)
    acceptance = accepted_request(config,inputs/'request-acceptance')
    source = inputs/'application'
    original = _read(source/'application-input-contract.json')
    assert original['head_sha']==config['source_head_sha']
    assert original['run_id']==str(config['source_run_id'])
    for name,digest in original['files'].items():
        assert _hash(source/name)==digest,name
    shutil.copytree(source,out,dirs_exist_ok=True)
    for sample in original['samples']:
        for case in sample['cases']:
            root = out/'cases'/case['case_id']
            base = {name:_read(root/(name+'.json')) for name in
                    ('mapping','native_audit','request_audit','rejected_requests','operation_oracle','edge_oracle','summary')}
            base['envelope'] = _read(root/'traces/observed.json')
            started = time.perf_counter()
            result = contextualize(base)
            save_projection(root,result)
            case.update(summary=result['summary'],context_projection_seconds=time.perf_counter()-started,
                        expected_requests=1200,
                        files={p.relative_to(root).as_posix():_hash(p) for p in root.rglob('*') if p.is_file()})
    options = next((out/'cases').glob('*/Options.txt')).read_text()
    controls = []
    for name,expected in CONTROL_SUCCESS.items():
        base,result,_ = control(name)
        root = out/'controls'/name
        save_projection(root,result)
        _write(root/'base-projection.json',base)
        (root/'Options.txt').write_text(options)
        controls.append(dict(case_id='control--'+name,control=True,directory='controls/'+name,
                             operation=name,expected_success=expected,expected_requests=10,
                             summary=result['summary'],
                             files={p.relative_to(root).as_posix():_hash(p) for p in root.rglob('*') if p.is_file()}))
    # An unchanged operation-name cycle tests the new per-case error census.
    base,_,_ = control('recursive_native_name')
    root=out/'controls/native_cycle_negative'
    save_projection(root,base)
    (root/'Options.txt').write_text(options)
    controls.append(dict(case_id='00-control--native_cycle_negative',control=True,
        directory='controls/native_cycle_negative',operation='native_cycle_negative',
        expected_error='java.lang.StackOverflowError',expected_requests=10,summary=base['summary'],
        files={p.relative_to(root).as_posix():_hash(p) for p in root.rglob('*') if p.is_file()}))
    derived = dict(original,head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
                   config_sha256=_hash(config_path),adapter_version=CONTEXT_VERSION,
                   original_source_head=config['source_head_sha'],original_source_run=config['source_run_id'],
                   original_input_contract_sha256=_hash(source/'application-input-contract.json'),
                   context_controls=controls,context_source_artifacts=metadata,
                   acceptance_artifacts=acceptance,new_comparator_fits=0,evaluator_rows_read=0,
                   files={p.relative_to(out).as_posix():_hash(p) for p in out.rglob('*')
                          if p.is_file() and p.name!='application-input-contract.json'})
    _write(out/'application-input-contract.json',derived)


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


def collect(config_path, extractions, out):
    _remote()
    config = validate(config_path)
    records,models = [],[]
    for path in sorted(extractions.rglob('extraction-*.json')):
        record = _read(path)
        assert record['head_sha']==os.environ['GITHUB_SHA'] and record['config_sha256']==_hash(config_path)
        for model in record['models']:
            source = path.parent/'models'/model['model_id']
            for name,digest in model['files'].items():
                assert _hash(source/name)==digest,name
            shutil.copytree(source,out/'models'/model['model_id'])
            models.append(model)
        records.append(record)
    assert len(records)==5 and {r['sample_key'] for r in records}==set(config['sample_keys'])
    assert len({r['model_id'] for r in models})==len(models)
    assert sum(len(r['cases']) for r in records)==15
    _write(out/'solver-contract.json',dict(models=models,extractions=records,model_count=len(models),
        config_sha256=_hash(config_path),head_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID']))


def freeze(config_path,contract,solver,inputs,out):
    _remote()
    config = validate(config_path)
    prepared = _read(contract/'solver-contract.json')
    raw = _read(solver/'raw-result.json')['runs'] if (solver/'raw-result.json').exists() else []
    keys = [(r.get('model_id'),r.get('repetition')) for r in raw]
    if len(keys)!=len(set(keys)):
        raise ValueError('duplicate solver output')
    controls=[]
    for name,variants in config['expected_controls'].items():
        for variant,expected in variants.items():
            model_id='control--'+name+'--'+variant
            model=next((m for m in prepared['models'] if m['model_id']==model_id),None)
            if model:
                for file,digest in model['files'].items():
                    assert _hash(contract/'models'/model_id/file)==digest
            for repetition in (0,1):
                row=dict(next((r for r in raw if r.get('model_id')==model_id and r.get('repetition')==repetition),{'status':'missing'}))
                row.update(model_id=model_id,repetition=repetition,expected_success=expected)
                row.update(qualify(row,expected))
                controls.append(row)
    negative_id='00-control--native_cycle_negative--inclusive'
    negative=[r for r in raw if r.get('model_id')==negative_id]
    negative_ok=(len(negative)==2 and all(r.get('status')=='error' and
        r.get('error_type')=='java.lang.StackOverflowError' and not qualify(r,None)['valid_probability']
        for r in negative))
    accepted=(len(controls)==8 and all(r['software_oracle_pass'] for r in controls) and negative_ok)
    _write(out/'context-control-census.json',dict(qualified=accepted,rows=controls,
        head_sha=os.environ['GITHUB_SHA'],config_sha256=_hash(config_path),expected_records=8,
        oracle_passes=sum(r['software_oracle_pass'] for r in controls),
        negative_cycle_error_records=negative,negative_cycle_error_reproduced=negative_ok))
    if not accepted:
        raise ValueError('observed context numerical controls not qualified')
    freeze_candidates(config_path,contract,solver,inputs,out)
    predictions=_read(out/'candidate-predictions.json')
    for row in predictions:
        if row['method'].startswith('PMX_'):
            row['adapter_version']=CONTEXT_VERSION
    _write(out/'candidate-predictions.json',predictions)
    manifest=_read(out/'candidate-manifest.json')
    manifest.update(adapter_version=CONTEXT_VERSION,context_control_census_sha256=_hash(out/'context-control-census.json'),
                    prediction_file_sha256=_hash(out/'candidate-predictions.json'))
    _write(out/'candidate-manifest.json',manifest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('validate','prepare','extract','collect','freeze','evaluate'))
    parser.add_argument('--config',type=Path,default=Path('configs/m9x_pmx_context_comparison.json'))
    for name in ('inputs','out','contract','jar','extractions','solver','candidates','source-inputs'):
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--sample')
    args=parser.parse_args()
    if args.action=='validate':validate(args.config)
    elif args.action=='prepare':prepare(args.config,args.inputs,args.out)
    elif args.action=='extract':extract(args.config,args.contract,args.sample,args.jar,args.out)
    elif args.action=='collect':collect(args.config,args.extractions,args.out)
    elif args.action=='freeze':freeze(args.config,args.contract,args.solver,args.inputs,args.out)
    else:evaluate(args.config,args.inputs,args.candidates,args.source_inputs,args.out)


if __name__=='__main__':main()
