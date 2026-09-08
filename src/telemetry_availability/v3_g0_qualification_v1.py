"""Isolated source-model-derived G0 qualification; full models stay in GHA."""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
import time

from .g0_aina_ordinary_v1 import VERSION, identify_from_observed_graph, solve
from .health_prefix_audit_v3 import restore
from .v3_application_execution_v1 import digest
from .v3_application_execution_v2 import METHOD as SOURCE_METHOD
from .v3_graph_input_inventory import ReadBoundary
from .v3_primary_projection import read, write, sha

CONFIG = Path('configs/v3_g0_qualification_v1.json')


def prepare(settings, profile):
    archive, metadata = restore(settings['profiles'][profile]['artifact'])
    assert set(archive.namelist()) == {'model.json', 'seal.json'}
    root = Path('workflow-results/source-model'); root.mkdir(parents=True, exist_ok=True)
    for name in ('model.json', 'seal.json'):
        (root/name).write_bytes(archive.read(name))
    archive.close()
    assert read(root/'seal.json')['files'] == {'model.json': sha(root/'model.json')}
    write(Path('workflow-results/preparation/source-audit.json'), dict(artifact=metadata,
        source_model_sha256=sha(root/'model.json'), source_bytes=(root/'model.json').stat().st_size,
        role='previous ordinary-derived graph/model, not independent PMX or evaluator', main_campaigns=0))


def replay(model):
    result = solve(model); equivalent = deepcopy(model); equivalent['graph']['edges'].reverse()
    assert solve(equivalent) == result
    changed = 0
    for target in model['operation']['required']:
        altered = deepcopy(model)
        if target == model['operation']['entry']:
            continue
        altered['graph']['edges'] = [edge for edge in altered['graph']['edges'] if edge['target'] != target]
        assert solve(altered)['lower_exact'] == solve(altered)['upper_exact'] == '0'
        changed += 1
    return dict(forecast=result, calculation_sha256=digest(result),
        required_target_disconnection_controls=changed, equivalent_edge_order_preserved=True)


def consume(settings, profile, is_replay):
    root = Path('workflow-input/g0-model' if is_replay else 'workflow-input/source-model').resolve()
    output = Path('workflow-results/replay' if is_replay else 'workflow-results/fit').resolve()
    output.mkdir(parents=True, exist_ok=True); boundary = ReadBoundary(root, output)
    boundary.allowed = {root/'model.json', root/'seal.json'}
    tick = time.perf_counter(); sys.addaudithook(boundary.hook)
    models = {}; reports = {}
    try:
        seal = read(root/'seal.json'); saved = read(root/'model.json')
        assert seal['files'] == {'model.json': sha(root/'model.json')}
        assert saved['profile'] == profile
        assert set(saved['models']) | set(saved['absences']) == set(settings['profiles'][profile]['operations'])
        if is_replay:
            assert saved['method'] == VERSION
            for op, model in saved['models'].items():
                reports[op] = replay(model)
                assert reports[op]['calculation_sha256'] == saved['calculation_hashes'][op]
        else:
            assert saved['method'] == SOURCE_METHOD
            for op, source in saved['models'].items():
                model = identify_from_observed_graph(source)
                model['identity'] = dict(method=VERSION, profile=profile, operation=op,
                    placement=source['identity']['placement'], data_role='retained_ordinary_derived_development', scope='current')
                started = time.perf_counter(); result = solve(model)
                reports[op] = dict(forecast=result, calculation_sha256=digest(result),
                    calculation_seconds=time.perf_counter()-started, identity=model['identity'],
                    graph_nodes=len(model['graph']['services']), graph_edges=len(model['graph']['edges']),
                    source_method=SOURCE_METHOD, source_calculation_sha256=saved['calculation_hashes'][op],
                    parameters_used='G/R/required targets and request-aligned X columns only',
                    shared_extraction_cost_not_zero=True)
                models[op] = model
        absences = saved['absences']
        assert boundary.reads == {str(p) for p in boundary.allowed} and not boundary.blocked
    finally:
        boundary.active = False
        write(output/'read-audit.json', dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
            source_model_derived_qualification=not is_replay, physical_model_role_only=True,
            native_or_evaluator_received=False, main_end_to_end_input_boundary_not_qualified=True))
    if not is_replay:
        out = Path('workflow-results/models/model.json')
        write(out, dict(method=VERSION, profile=profile, models=models, absences=absences,
            calculation_hashes={op: report['calculation_sha256'] for op, report in reports.items()},
            source_seal=seal, protocol_sha256=sha(CONFIG), head=os.environ['GITHUB_SHA']))
        write(out.parent/'seal.json', dict(method=VERSION, files={'model.json': sha(out)}))
    write(output/'results.json', dict(method=VERSION, profile=profile, operations=reports, absences=absences,
        source_seal=seal, run_id=os.environ['GITHUB_RUN_ID'], head=os.environ['GITHUB_SHA'],
        protocol_sha256=sha(CONFIG), elapsed_seconds=time.perf_counter()-tick,
        main_campaigns=0, independent_accuracy_evaluation=False, all_operations_accounted=len(reports)+len(absences)))


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Application model processing is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'build', 'replay')); parser.add_argument('--profile', required=True)
    args = parser.parse_args(); settings = read(CONFIG)
    for lock in settings['repository_locks']:
        assert sha(Path(lock['path'])) == lock['sha256'], lock['path']
    if args.stage == 'prepare':
        prepare(settings, args.profile)
    else:
        consume(settings, args.profile, args.stage == 'replay')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        stage = {'prepare': 'preparation', 'build': 'fit', 'replay': 'replay'}.get(sys.argv[1], 'failure')
        write(Path('workflow-results')/stage/'failure.json', dict(type=type(exc).__name__, message=str(exc)))
        raise
