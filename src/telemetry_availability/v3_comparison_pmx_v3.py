"""Independent PMX projection, PCM inventory and solver-candidate collection.

This module never consumes ordinary probes, our graph, our parameters, or test.
It reuses the native policies and caller-context bridge. The qualified derived
PMX binary has only a representable-clock-progress correction.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys
import time

from .pmx_observed_operations import NativeSpan
from .pmx_request_adapter import project_campaign
from .pmx_database_client_adapter import project_campaign as db_project_campaign
from .pmx_request_context import contextualize, control as context_control, CONTROL_SUCCESS
from .pmx_database_client_controls import control as database_control, SUCCESS as DATABASE_SUCCESS
from .pmx_context_comparison import save_projection
from .pmx_context_extraction_v3 import extract as qualified_extract
from .pmx_clock_progress_application_v1 import run_application_pmx
from functools import partial
from .pmx_adapter_conformance import OPTIONS_SHA
from .pmx_pmf_bridge import qualify
from .v3_primary_projection import REQUEST_FIELDS, read, sha, write
from .v3_comparison_roles_v1 import load_role, seal_role, ROLE_FILES, campaign_id, digest
from .v3_graph_input_inventory import ReadBoundary
from .v3_resource_summary_v1 import summarize as resource_summary

VERSION = 'v3-independent-pmx-comparison-v3'
LEGACY_CONFIG = Path('configs/m9x_pmx_context_comparison.json')
POLICIES = {'deathstarbench_social_network': 'service_boundary',
    'opentelemetry_demo': 'explicit_server', 'spring_petclinic_microservices': 'server_and_observed_db_client'}


def projection(native, requests, profile, declared_host):
    # The sealed request role has exactly eight fields. Legacy PMX wrappers also
    # require a profile name; derive it solely from the sealed campaign identity.
    if profile not in POLICIES or any(set(row) != set(REQUEST_FIELDS) for row in requests):
        raise ValueError('PMX request field whitelist or declared application differs')
    if native['calibration_only'] is not True or len(native['selected_trace_ids']) != len(set(native['selected_trace_ids'])):
        raise ValueError('invalid native role')
    if set(native['selected_trace_ids']) != {r['trace_id'] for r in requests} or not set(native['spans']) <= set(native['selected_trace_ids']):
        raise ValueError('native/external request census differs')
    if len({r['request_id'] for r in requests}) != len(requests) or len({r['trace_id'] for r in requests}) != len(requests):
        raise ValueError('duplicate calibration request identity')
    if any(r['period'] != 'calibration' for r in requests):
        raise ValueError('PMX received another period')
    grouped = {key: [NativeSpan(**s) for s in spans] for key, spans in native['spans'].items()}
    policy = POLICIES[profile]; result = {}; costs = []
    for operation in sorted({r['operation'] for r in requests}):
        rows = [dict(r, profile=profile) for r in requests if r['operation'] == operation]; tick = time.perf_counter()
        if policy == 'server_and_observed_db_client':
            base = db_project_campaign(grouped, rows, declared_host=declared_host)
        else:
            base = project_campaign(grouped, rows, policy, declared_host)
        result[operation] = contextualize(base)
        costs.append(dict(method='PMX_shared_variants', operation=operation, stage='native_projection', seconds=time.perf_counter()-tick))
    return result, costs


def prepare(source, options, out, settings, controls=False):
    if sha(options) != OPTIONS_SHA:
        raise ValueError('PMX source options differ')
    option_text = options.read_text().replace('traces/jaegercustomers.json', 'traces/observed.json')
    cases = []; stages = []; audit = {}; identity = None; source_hash = None
    if controls:
        results = {name: context_control(name)[1] for name in CONTROL_SUCCESS}
        results.update({name: database_control(name)[0] for name in DATABASE_SUCCESS})
        expected = dict(CONTROL_SUCCESS, **DATABASE_SUCCESS)
        key = 'controls'; expected_requests = {op: 10 for op in results}
    else:
        boundary = ReadBoundary(source.resolve(), out.resolve())
        boundary.allowed = {source.resolve()/name for name in ROLE_FILES['pmx_calibration'] | {'seal.json'}}
        tick = time.perf_counter(); sys.addaudithook(boundary.hook)
        try:
            documents, seal = load_role(source, 'pmx_calibration')
            source_hash = sha(source/'seal.json'); identity = seal['identity']
            manifest = documents['manifest.json']
            if identity != manifest['identity'] or identity['protocol_sha256'] != settings['identity_protocol_sha256']:
                raise ValueError('PMX input outside frozen protocol')
            if manifest['native_quality']['qualified'] is not True:
                raise ValueError('invalid calibration native source; no PMX fit')
            operations = settings['profiles'][identity['application']]['operations']
            expected_requests = {op: spec['expected_attempts'] for op, spec in operations.items()}
            if dict(Counter(r['operation'] for r in documents['requests.json'])) != expected_requests:
                raise ValueError('incomplete planned PMX calibration census')
            results, stages = projection(documents['native.json'], documents['requests.json'],
                identity['application'], manifest['declared_host'])
        finally:
            boundary.active = False
        audit = dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
            physical_input_role='native+external calibration only', health_or_our_model_or_evaluator_inputs=0,
            all_python_input_loading_and_projection_audited=True,
            external_wrapper_profile_source='sealed campaign identity.application; not an extra request field',
            subsequent_java_input_is_separately_prepared_calibration_projection=True)
        if boundary.blocked or boundary.reads != {str(p) for p in boundary.allowed}:
            raise ValueError('PMX native read census differs')
        key = 'campaign-'+digest(identity)[:20]
        sample = dict(key=key, profile=identity['application'], placement=identity['placement'],
            failure_law=identity['law'], repetition=identity['repetition'])
        stages.append(dict(method='PMX_shared_variants', stage='input_and_projection_process_total',
            seconds=time.perf_counter()-tick, overlaps_native_projection=True))
    for operation, result in results.items():
        case_id = key+'--'+operation; root = out/'cases'/case_id
        save_projection(root, result)
        (root/'Options.txt').write_text(option_text)
        case = dict(case_id=case_id, operation=operation, directory='cases/'+case_id,
            summary=result['summary'], expected_requests=expected_requests[operation],
            files={p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()})
        if controls:
            case.update(control=True, expected_success=expected[operation])
        else:
            case['sample'] = sample
        cases.append(case)
    write(out/'application-input-contract.json', dict(head_sha=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
        config_sha256=sha(LEGACY_CONFIG), samples=[] if controls else [dict(sample=sample, cases=cases)],
        context_controls=cases if controls else [], prospective_identity=identity,
        input_seal_sha256=source_hash, sample_key=key, stages=stages, read_audit=audit))
    return key


def collect(extractions, out, profile):
    """Collect only independently extracted PCM files; missing campaigns are filled at freeze."""
    records = []; models = []; keys = set()
    for path in sorted(extractions.rglob('extraction-*.json')):
        record = read(path); identity = record.get('prospective_identity')
        if identity is not None and identity['application'] != profile:
            continue
        if record['head_sha'] != os.environ['GITHUB_SHA'] or record['sample_key'] in keys:
            raise ValueError('duplicate/cross-head PMX extraction')
        keys.add(record['sample_key'])
        for model in record['models']:
            source = path.parent/'models'/model['model_id']
            if {p.name for p in source.iterdir() if p.is_file()} != set(model['files']):
                raise ValueError('PCM model file census differs')
            for name, expected in model['files'].items():
                if sha(source/name) != expected:
                    raise ValueError('PCM model hash differs')
            shutil.copytree(source, out/'models'/model['model_id'])
            models.append(model)
        records.append(record)
    if len({m['model_id'] for m in models}) != len(models):
        raise ValueError('duplicate PMX solver model')
    result = dict(version=VERSION, models=models, extractions=records, model_count=len(models),
        head_sha=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'], profile=profile)
    write(out/'solver-contract.json', result)


def solver_forecasts(prepared, raw):
    builds = [r.get('qualified_pmx_build') for r in prepared['extractions']]
    if not builds or not isinstance(builds[0], dict) or builds[0].get('qualified') is not True or any(b != builds[0] for b in builds):
        raise ValueError('mixed or unqualified PMX binary provenance')
    models = {m['model_id']: m for m in prepared['models']}
    keys = [(r.get('model_id'), r.get('repetition')) for r in raw]
    if len(keys) != len(set(keys)) or not set(keys) <= {(mid, rep) for mid in models for rep in (0, 1)}:
        raise ValueError('duplicate/unplanned solver result')
    expected_controls = dict(CONTROL_SUCCESS, **DATABASE_SUCCESS); controls = []
    for case, variants in expected_controls.items():
        for variant, expected in variants.items():
            mid = 'controls--'+case+'--'+variant
            rows = [r for r in raw if r.get('model_id') == mid]
            controls.append(dict(model_id=mid, expected=expected,
                qualified=len(rows)==2 and all(qualify(r, expected)['software_oracle_pass'] for r in rows), results=rows))
    control_ok = all(c['qualified'] for c in controls)
    candidates = []
    for record in prepared['extractions']:
        if record['sample_key'] == 'controls':
            continue
        forecasts = {}; evidence = []
        for case in record['cases']:
            operation = case['case_id'].split('--', 1)[1]; forecasts[operation] = {}
            for variant, method in (('conditional_local', 'PMX'), ('inclusive', 'PMX_inclusive')):
                mid = case['case_id']+'--'+variant
                rows = [r for r in raw if r.get('model_id') == mid]
                decision = next((v for v in case['variants'] if v['variant']==variant), {})
                valid = (control_ok and len(rows)==2 and all(qualify(r, None)['valid_probability'] for r in rows)
                         and abs(rows[0]['success_probability']-rows[1]['success_probability']) <= 1e-12)
                reason = None if valid else ('known_probability_controls_failed' if not control_ok else
                    decision.get('status', case.get('error', 'extraction_unavailable')))
                if reason == 'prepared':
                    reason = 'no_valid_repeat_consistent_solver_probability'
                status = 'ok' if valid else ('unsupported' if reason=='unsupported_conditional_propagation_or_positivity' else 'failed')
                forecasts[operation][method] = dict(status=status, probability=rows[0]['success_probability'] if valid else None,
                    reason=reason, model_id=mid)
                evidence.append(dict(model_id=mid, extraction=decision, solver_records=rows))
        candidates.append(dict(version=VERSION, identity=record['prospective_identity'], forecasts=forecasts,
            input_seal_sha256=record['input_seal_sha256'], builder_head=prepared['head_sha'],
            stages=record['stages'], read_audit=dict(record['read_audit'], qualified_pmx_build=record['qualified_pmx_build']), solver_evidence=evidence))
    return candidates, dict(qualified=control_ok, expected_two_pass_oracle_records=16, controls=controls, qualified_pmx_build=builds[0])


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Application PMX/PCM work is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['extract', 'controls', 'collect', 'freeze'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--options', type=Path)
    parser.add_argument('--jar', type=Path)
    parser.add_argument('--profile')
    parser.add_argument('--solver', type=Path)
    args = parser.parse_args(); out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True)
    if args.mode in ('extract', 'controls'):
        contract = out/'projection'
        settings = read(args.config)
        pmx_build = settings['pmx_clock_progress']
        if pmx_build['qualified'] is not True or pmx_build['version'] != 'pmx-clock-progress-v1':
            raise ValueError('PMX clock-progress repair is not qualified')
        build_record = read(args.jar.parent/'build-provenance.json')
        if build_record['derived_jar_sha256'] != pmx_build['derived_jar_sha256'] or build_record['original_jar_sha256'] != pmx_build['original_jar_sha256']:
            raise ValueError('PMX build record differs from qualified binary')
        key = prepare(args.source.resolve(), args.options, contract, settings, args.mode=='controls')
        launcher = partial(run_application_pmx, expected_jar_sha256=pmx_build['derived_jar_sha256'])
        qualified_extract(LEGACY_CONFIG, contract, key, args.jar, out, launcher=launcher)
        record_path = out/('extraction-'+key+'.json'); record = read(record_path)
        prepared = read(contract/'application-input-contract.json')
        record['qualified_pmx_build'] = pmx_build
        resources = resource_summary(args.jar.parent)['records']
        if len(resources) != 1 or resources[0]['wall_seconds'] is None:
            raise ValueError('PMX binary-build resource record missing or ambiguous')
        prepared['stages'].append(dict(method='PMX_shared_variants', stage='derived_binary_build',
            seconds=resources[0]['wall_seconds'], resource_record=resources[0],
            once_per_campaign_shared_across_operations_and_variants=True,
            derived_jar_sha256=build_record['derived_jar_sha256'], compiler=build_record['compiler']))
        for field in ('prospective_identity', 'input_seal_sha256', 'stages', 'read_audit'):
            record[field] = prepared[field]
        write(record_path, record)
    elif args.mode == 'collect':
        collect(args.source, out, args.profile)
    else:
        prepared = read(args.source/'solver-contract.json')
        if prepared['head_sha'] != os.environ['GITHUB_SHA']:
            raise ValueError('solver contract from another head')
        for model in prepared['models']:
            for name, expected in model['files'].items():
                if sha(args.source/'models'/model['model_id']/name) != expected:
                    raise ValueError('solver input model hash differs')
        raw = read(args.solver/'raw-result.json')['runs'] if (args.solver/'raw-result.json').exists() else []
        candidates, controls = solver_forecasts(prepared, raw)
        write(out/'controls.json', controls)
        for candidate in candidates:
            identity = candidate['identity']; target = out/('campaign-'+digest(identity)[:20])
            costs = dict(stages=candidate.pop('stages'),
                extraction_and_bridge_records=next(r['cases'] for r in prepared['extractions'] if r.get('prospective_identity')==identity),
                solver_evidence=candidate.pop('solver_evidence'),
                batch_resource_reference=dict(profile=prepared['profile'], run_id=os.environ['GITHUB_RUN_ID'],
                    resources=resource_summary(args.solver), shared_once_across_this_application=True))
            for case in costs['extraction_and_bridge_records']:
                if 'execution' in case:
                    costs['stages'].append(dict(method='PMX_shared_variants', operation=case['case_id'].split('--', 1)[1],
                        stage='independent_pmx_extraction_process', seconds=case['execution']['elapsed_seconds']))
            audit = candidate.pop('read_audit')
            seal_role(target, 'pmx_candidates', identity,
                {'candidates.json': candidate, 'costs.json': costs, 'read-audit.json': audit})


if __name__ == '__main__':
    main()
