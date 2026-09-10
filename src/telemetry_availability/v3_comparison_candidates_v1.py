"""Fixed comparison bindings, ordinary-only construction and pre-evaluator seal."""
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from .b0_frequency_v3_csv_v2 import identify as b0_identify
from .g0_aina_ordinary_v1 import identify_from_observed_graph, solve as g0_solve
from .graph_execution_model_v1 import solve
from .v3_prospective_execution_v1 import fit_operation, BindingUnsupported
from .v3_application_execution_v2 import digest
from .v3_comparison_roles_v1 import (campaign_id, validate_identity, load_role, seal_role, ROLE_FILES)
from .v3_graph_input_inventory import ReadBoundary
from .v3_ordinary_identity_v2 import load_bundle
from .v3_primary_projection import read, sha, write
from .v3_campaign_analysis_v1 import valid_probability

VERSION = 'v3-comparison-candidates-v1'
GRAPH_VARIANTS = {'Gstar': 'execution', 'GID': 'reachability', 'Gselected': 'selected',
    'G_without_deadline': 'without_deadline', 'G_without_selection': 'without_selection',
    'G_without_completion': 'without_completion'}
GRAPH_METHODS = tuple(GRAPH_VARIANTS) + ('G0', 'B0')
PMX_METHODS = ('PMX', 'PMX_inclusive')
METHODS = GRAPH_METHODS + PMX_METHODS


def absent(status, reason, **extra):
    if status not in ('unsupported', 'failed', 'missing') or not reason:
        raise ValueError('invalid absence')
    return dict(status=status, probability=None, reason=reason, **extra)


def point_or_bound(estimate):
    if estimate['prediction'] is None:
        return absent('unsupported', 'not_point_identified_under_declared_observation_law',
            identified_lower=estimate['lower'], identified_upper=estimate['upper'],
            lower_exact=estimate['lower_exact'], upper_exact=estimate['upper_exact'])
    return dict(status='ok', probability=estimate['prediction'], reason=None,
        exact_fraction=estimate['lower_exact'])


def validate_forecasts(forecasts, operations, methods):
    if set(forecasts) != set(operations):
        raise ValueError('operation census differs')
    for row in forecasts.values():
        if set(row) != set(methods):
            raise ValueError('method census differs')
        for prediction in row.values():
            if prediction['status'] == 'ok':
                if not valid_probability(prediction['probability']):
                    raise ValueError('invalid candidate probability')
            elif prediction['status'] not in ('unsupported', 'failed', 'missing') or prediction.get('probability') is not None or not prediction.get('reason'):
                raise ValueError('invalid absent candidate')


def build(data, specs, identity):
    validate_identity(identity)
    operations = tuple(specs)
    if set(r['operation'] for r in data['requests.json']) != set(operations):
        raise ValueError('unplanned/missing calibration operation')
    models = dict(execution={}, g0={}, b0=None)
    forecasts = {op: {} for op in operations}; reports = {}; stages = []
    started = time.perf_counter()
    # B0's pure function receives only the external calibration request contract.
    models['b0'] = b0_identify(data['requests.json'], operations)
    stages.append(dict(method='B0', stage='identification', seconds=time.perf_counter()-started))
    for op, spec in specs.items():
        forecasts[op]['B0'] = models['b0']['forecasts'][op]
        if forecasts[op]['B0']['attempts'] != spec['expected_attempts']:
            raise ValueError('calibration census differs from frozen expected attempts')
        quality = data.get('manifest.json', {}).get('calibration_native_quality', {'qualified': True})
        if quality['qualified'] is not True:
            for name in tuple(GRAPH_VARIANTS) + ('G0',):
                forecasts[op][name] = absent('failed', quality.get('reason') or 'invalid_calibration_native_source')
            continue
        try:
            model, report = fit_operation(data, op, spec, identity)
            models['execution'][op] = model; reports[op] = report
            for name, variant in GRAPH_VARIANTS.items():
                forecasts[op][name] = point_or_bound(report['estimates'][variant])
            for stage, seconds in report['stage_seconds'].items():
                stages.append(dict(method='shared_graph_family', operation=op, stage=stage, seconds=seconds))
        except BindingUnsupported as exc:
            for name in GRAPH_VARIANTS:
                forecasts[op][name] = absent('unsupported', str(exc))
            forecasts[op]['G0'] = absent('unsupported', 'shared_graph_extraction_unsupported: ' + str(exc))
            continue
        except (ValueError, AssertionError, KeyError) as exc:
            for name in GRAPH_VARIANTS:
                forecasts[op][name] = absent('failed', type(exc).__name__ + ': ' + str(exc))
            forecasts[op]['G0'] = absent('failed', 'shared_graph_extraction_failed: ' + str(exc))
            continue
        try:
            started = time.perf_counter()
            g0 = identify_from_observed_graph(model)
            stages.append(dict(method='G0', operation=op, stage='identification', seconds=time.perf_counter()-started))
            started = time.perf_counter(); result = g0_solve(g0)
            stages.append(dict(method='G0', operation=op, stage='solve', seconds=time.perf_counter()-started))
            models['g0'][op] = g0; forecasts[op]['G0'] = point_or_bound(result)
        except ValueError as exc:
            forecasts[op]['G0'] = absent('unsupported', 'G0_declared_class: ' + str(exc))
    validate_forecasts(forecasts, operations, GRAPH_METHODS)
    return forecasts, models, reports, dict(stages=stages,
        shared_graph_extraction_charged_once=True, graph_ablation_solve_is_joint=True,
        b0_fields=['requests.json'], graph_fields=['requests.json', 'native.json', 'probes.json', 'declarations.json'],
        update_seconds=None, update_reason='not measured; fresh reconstruction is the reported application path',
        monitoring_overhead=None, scalability_curve=None,
        manual_integration_seconds=None, manual_reason='historical development labor was not timed')


def replay(forecasts, models):
    """Fresh-process arithmetic checks from saved models, without ordinary inputs."""
    for op, model in models['execution'].items():
        result = solve(model)
        for name, variant in GRAPH_VARIANTS.items():
            if forecasts[op][name] != point_or_bound(result['estimates'][variant]):
                raise ValueError('saved graph forecast does not reproduce')
    for op, model in models['g0'].items():
        if forecasts[op]['G0'] != point_or_bound(g0_solve(model)):
            raise ValueError('saved G0 forecast does not reproduce')
    for op, result in models['b0']['forecasts'].items():
        if forecasts[op]['B0'] != result or result['probability'] != result['successes']/result['attempts']:
            raise ValueError('saved B0 counts do not reproduce')
    for op, values in forecasts.items():
        if any(values[name]['status'] == 'ok' for name in GRAPH_VARIANTS) and op not in models['execution']:
            raise ValueError('graph point lacks a saved model')
        if values['G0']['status'] == 'ok' and op not in models['g0']:
            raise ValueError('G0 point lacks a saved model')
    return dict(execution_models=len(models['execution']), g0_models=len(models['g0']),
        b0_operations=len(models['b0']['forecasts']), exact=True)


def combine(identity, operations, graph, pmx, receipt, failures=None):
    """Called before any evaluator artifact is downloaded; absent jobs stay absent."""
    validate_identity(identity)
    if receipt['identity'] != identity or not receipt.get('evaluator_seal_sha256'):
        raise ValueError('acquisition receipt/campaign mismatch')
    forecasts = {op: {} for op in operations}; failures = failures or {}
    for role, candidate, methods in (('graph', graph, GRAPH_METHODS), ('pmx', pmx, PMX_METHODS)):
        if candidate is None:
            if role not in failures:
                raise ValueError('missing builder requires an explicit technical reason')
            for op in operations:
                forecasts[op].update({name: absent('missing', failures[role]) for name in methods})
            continue
        if candidate['identity'] != identity or candidate['input_seal_sha256'] != receipt[role + '_input_seal_sha256']:
            raise ValueError('candidate was fitted from another campaign/input')
        validate_forecasts(candidate['forecasts'], operations, methods)
        for op in operations:
            forecasts[op].update(deepcopy(candidate['forecasts'][op]))
    validate_forecasts(forecasts, operations, METHODS)
    return dict(version=VERSION, identity=deepcopy(identity), campaign_id=campaign_id(identity),
        methods=list(METHODS), forecasts=forecasts, evaluator_seal_sha256=receipt['evaluator_seal_sha256'],
        source_candidate_digests={role: digest(value) if value is not None else None
            for role, value in (('graph', graph), ('pmx', pmx))}, failures=failures)


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Real application fitting/replay is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['build', 'replay'])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args(); settings = read(args.config)
    root = args.input.resolve(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    boundary = ReadBoundary(root, out)
    if args.mode == 'replay':
        boundary.allowed = {root/name for name in ROLE_FILES['graph_candidates'] | {'seal.json'}}
    started = time.perf_counter(); sys.addaudithook(boundary.hook)
    try:
        if args.mode == 'build':
            data, seal = load_bundle(root); input_hash = sha(root/'seal.json')
            load_seconds = time.perf_counter()-started
            identity = data['manifest.json']['identity']; validate_identity(identity)
            if identity['protocol_sha256'] != settings['identity_protocol_sha256']:
                raise ValueError('ordinary input is outside frozen protocol')
            specs = settings['profiles'][identity['application']]['operations']
            forecasts, models, reports, costs = build(data, specs, identity)
            costs['input_loading_seconds'] = load_seconds
            costs['input_bytes'] = sum((root/name).stat().st_size for name in seal['files'])
            candidate = dict(version=VERSION, identity=identity, forecasts=forecasts,
                input_seal_sha256=input_hash, builder_head=os.environ['GITHUB_SHA'])
        else:
            documents, seal = load_role(root, 'graph_candidates')
            result = replay(documents['candidates.json']['forecasts'], documents['models.json'])
    finally:
        boundary.active = False
    audit = dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
        physical_evaluator_inputs_received=False, includes_loading_and_model_construction=True)
    if boundary.blocked or boundary.reads != {str(p) for p in boundary.allowed}:
        raise ValueError('role read census differs')
    if args.mode == 'build':
        costs['combined_process_seconds'] = time.perf_counter()-started
        seal_role(out/'candidates', 'graph_candidates', identity,
            {'candidates.json': candidate, 'models.json': models, 'costs.json': costs, 'read-audit.json': audit})
        write(out/'compact/results.json', dict(identity=identity, forecasts=forecasts,
            operation_diagnostics=reports, costs=costs, read_audit=audit,
            candidate_seal_sha256=sha(out/'candidates/seal.json')))
    else:
        write(out/'replay.json', dict(result=result, read_audit=audit, candidate_seal_sha256=sha(root/'seal.json')))


if __name__ == '__main__':
    main()
