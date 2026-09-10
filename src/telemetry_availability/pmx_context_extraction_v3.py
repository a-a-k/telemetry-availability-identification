"""Versioned PMX extraction with an explicit, separately qualified launcher.

The extraction/bridge body is copied from frozen pmx_context_comparison.extract;
only the explicit launcher argument is changed. No original module is patched.
"""
import os
import shutil
import time
from .pmx_context_comparison import validate
from .pmx_adapter_conformance import inspect_pcm, compare_pcm
from .pmx_composition_control import SUFFIXES, _hash, _read, _remote, _write
from .pmx_retained_request_audit import inventory_variable_hex_ids
from .pmx_mixed_loop_bridge import bridge
from .pmx_request_context import CONTEXT_VERSION


def extract(config_path, contract, sample_key, jar, out, *, launcher):
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
            row['execution'] = launcher(jar,root,raw)
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
