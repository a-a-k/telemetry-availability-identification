"""Workflow census, candidate freeze, closed-role evaluation and final analysis."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

from .v3_comparison_roles_v1 import (campaign_id, digest, load_role, seal_role, ROLE_FILES)
from .v3_comparison_candidates_v1 import combine, METHODS
from .v3_comparison_evaluation_v1 import evaluate, missing_campaign, complete_analysis
from .v3_graph_input_inventory import ReadBoundary
from .v3_primary_projection import read, write, sha

UPSTREAM = {
    'deathstarbench_social_network': dict(repository='delimitrou/DeathStarBench',
        commit='6ecb09706140f8730b5385c08f1386c654c3c526', compose_file='socialNetwork/docker-compose.yml'),
    'opentelemetry_demo': dict(repository='open-telemetry/opentelemetry-demo',
        commit='8c47d47c9ac27710d2b2a153bcd53e483bffe66d', compose_file='compose.yaml'),
    'spring_petclinic_microservices': dict(repository='spring-petclinic/spring-petclinic-microservices',
        commit='3858f9c630cf989bb6809a86edf47c2be78dc9f1', compose_file='compose.json'),
}


def planned_cases(settings_path, mode):
    settings = read(settings_path); design = deepcopy(settings['design'])
    if mode == 'preflight':
        design.update(settings['preflight'])
    elif mode != 'main':
        raise ValueError('unknown campaign role')
    cases = []
    for profile in design['applications']:
        for placement in design['placements']:
            for law in design['laws']:
                for repetition in design['repetitions']:
                    identity = dict(application=profile, placement=placement, law=law, repetition=repetition,
                        namespace=settings[mode+'_namespace'], data_role='prospective_main' if mode=='main' else 'development_preflight',
                        protocol_sha256=sha(settings_path))
                    key = profile+'--'+placement+'--'+law+'--r'+str(repetition)
                    cases.append(dict(profile=profile, placement=placement, law=law, repetition=repetition,
                        key=key, identity=identity, **UPSTREAM[profile]))
    return settings, design, cases


def find_role(root, role, identity):
    found = []
    for seal_path in root.rglob('seal.json'):
        seal = read(seal_path)
        if seal.get('role') == role and seal.get('identity') == identity:
            found.append(seal_path.parent)
    if len(found) > 1:
        raise ValueError('duplicate candidate role for one planned campaign')
    return found[0] if found else None


def freeze_case(source, out, identity, operations):
    receipts = [p for p in source.rglob('receipt.json') if read(p).get('identity') == identity
                and 'graph_input_seal_sha256' in read(p)]
    if len(receipts) > 1:
        raise ValueError('duplicate acquisition receipts')
    if not receipts:
        write(out/'absence.json', dict(identity=identity, reason='acquisition_role_receipt_unavailable'))
        return
    receipt = read(receipts[0]); graph = None; pmx = None; failures = {}; costs = {}; source_seals = {}
    acquisition_cost_path = receipts[0].parent/'costs.json'
    if acquisition_cost_path.is_file():
        acquisition_cost = read(acquisition_cost_path)
        if acquisition_cost['identity'] != identity:
            raise ValueError('acquisition cost identity differs')
        acquisition_cost['stages'] = [
            dict(method='shared_acquisition', stage='acquisition_and_export_process_total',
                seconds=acquisition_cost['acquisition_process_seconds'], overlaps_native_parse=True),
            dict(method='shared_native_pool', stage='native_parse', seconds=acquisition_cost['shared_native_extraction_seconds'])]
        costs['acquisition'] = acquisition_cost
    for label, role in (('graph', 'graph_candidates'), ('pmx', 'pmx_candidates')):
        root = find_role(source, role, identity)
        if root is None:
            failures[label] = label+'_candidate_role_unavailable'
            continue
        documents, seal = load_role(root, role, identity)
        source_seals[label] = sha(root/'seal.json')
        if label == 'graph':
            replays = [read(p) for p in source.rglob('replay.json') if read(p).get('candidate_seal_sha256') == source_seals[label]]
            if len(replays) != 1 or replays[0]['result'].get('exact') is not True or replays[0]['read_audit']['blocked']:
                failures[label] = 'graph_fresh_process_replay_missing_or_invalid'
                continue
            graph = documents['candidates.json']
        else:
            pmx = documents['candidates.json']
        costs[label] = documents['costs.json']
        resources = root.parent/'compact/resource-summary.json'
        if label == 'graph' and resources.is_file():
            costs[label]['process_resources'] = read(resources)
    candidate = combine(identity, operations, graph, pmx, receipt, failures)
    freeze_receipt = dict(identity=identity, acquisition_receipt=receipt,
        builder_role_seal_sha256=source_seals, frozen_head=os.environ['GITHUB_SHA'],
        workflow_run=os.environ['GITHUB_RUN_ID'], workflow_attempt=os.environ['GITHUB_RUN_ATTEMPT'],
        candidate_digest=digest(candidate), evaluator_inputs_available_in_freeze_job=False)
    seal_role(out/'frozen', 'frozen_candidates', identity,
        {'candidates.json': candidate, 'receipt.json': freeze_receipt, 'costs.json': costs})


def evaluate_case(frozen_root, evaluator_root, out, identity, operations, expected):
    root = frozen_root.resolve(); evaluator_root = evaluator_root.resolve(); out = out.resolve()
    boundary = ReadBoundary(root, out)
    boundary.allowed = {root/name for name in ROLE_FILES['frozen_candidates'] | {'seal.json'}}
    sys.addaudithook(boundary.hook)
    try:
        frozen, seal = load_role(root, 'frozen_candidates', identity)
        candidate = frozen['candidates.json']
        if digest(candidate) != frozen['receipt.json']['candidate_digest']:
            raise ValueError('candidate digest differs from freeze receipt')
        frozen_hash = sha(root/'seal.json')
        boundary.allowed |= {evaluator_root/name for name in ROLE_FILES['evaluator'] | {'seal.json'}}
        closed, evaluator_seal = load_role(evaluator_root, 'evaluator', identity, candidate['evaluator_seal_sha256'])
        report = evaluate(candidate, closed, identity, operations, expected, closed['manifest.json']['layer'])
        report.update(frozen_role_seal_sha256=frozen_hash, evaluator_role_seal_sha256=sha(evaluator_root/'seal.json'),
            evaluation_head=os.environ['GITHUB_SHA'], workflow_run=os.environ['GITHUB_RUN_ID'])
    finally:
        boundary.active = False
    report['read_audit'] = dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
        fitting_or_recalibration_performed=False, candidate_loaded_before_closed_role=True)
    if boundary.blocked or boundary.reads != {str(p) for p in boundary.allowed}:
        raise ValueError('evaluator read census differs')
    write(out/'evaluation.json', report)
    write(out/'evaluation-seal.json', dict(identity=identity, files={'evaluation.json': sha(out/'evaluation.json')},
        head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID']))


def summarize(source, out, settings_path, mode):
    settings, design, cases = planned_cases(settings_path, mode)
    reports = {}; campaigns = []; costs = []; gates = []
    for path in source.rglob('evaluation-seal.json'):
        seal = read(path)
        if seal['head'] != os.environ['GITHUB_SHA'] or seal['files'] != {'evaluation.json': sha(path.parent/'evaluation.json')}:
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
                costs.append(dict(campaign_id=key, job_role=role, attempt_id=os.environ['GITHUB_RUN_ATTEMPT'], **values))
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
        protocol_sha256=sha(settings_path), head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
        candidate_evaluator_integrity=integrity, nonempty_primary_family=supported_primary,
        qualification_uses_forecast_error=False, admission_candidate=integrity and supported_primary,
        campaign_gates=gates, analysis=analysis)
    write(out/'comparison.json', result)
    write(out/'comparison-seal.json', dict(files={'comparison.json': sha(out/'comparison.json')},
        head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'], protocol_sha256=sha(settings_path)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['matrix', 'freeze', 'evaluate', 'summarize'])
    parser.add_argument('--config', type=Path, default=Path('configs/v3_comparison_design_v1.json'))
    parser.add_argument('--mode', choices=['main', 'preflight'], required=True)
    parser.add_argument('--key')
    parser.add_argument('--source', type=Path)
    parser.add_argument('--evaluator', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args(); settings, design, cases = planned_cases(args.config, args.mode)
    if args.command == 'matrix':
        if args.mode == 'main':
            admission = read(Path('configs/v3_main_admission_v1.json'))
            if admission['protocol_sha256'] != sha(args.config) or admission['full_preflight_qualified'] is not True:
                raise ValueError('main admission has not been established')
        output = dict(cases=dict(include=cases), profiles=list(design['applications']))
        if 'GITHUB_OUTPUT' in os.environ:
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
                for key, value in output.items():
                    stream.write(key+'='+json.dumps(value, separators=(',', ':'))+'\n')
        print(json.dumps(dict(campaigns=len(cases), operation_cells=sum(len(design['applications'][c['profile']]) for c in cases), mode=args.mode)))
        return
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'Real comparison artifact evaluation is remote only'
    if args.command == 'summarize':
        summarize(args.source, args.out, args.config, args.mode)
    else:
        case = next(c for c in cases if c['key']==args.key); operations = design['applications'][case['profile']]
        if args.command == 'freeze':
            freeze_case(args.source, args.out, case['identity'], operations)
        else:
            expected = settings['test_seconds']*settings['request_rate_per_second']//len(operations)
            evaluate_case(args.source, args.evaluator, args.out, case['identity'], operations, expected)


if __name__ == '__main__':
    main()
