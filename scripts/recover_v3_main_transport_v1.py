"""Remote completion of saved main PMX models after the 1000-artifact listing loss.

Original observations, graph forecasts, PMX extraction and analysis code are
immutable. This is a separately identified computational recovery, not a new
campaign or a claim that PMX was frozen before the original evaluator opened.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import retain_v3_comparison_compact_v4 as transport
from archive_h_exec_evidence_v1 import require, verify_zip

RUN = 34465226083
HEAD = 'd857ea65ca9da7fa9ae4ee1198317487475246a7'
CONFIG = Path('configs/v3_main_transport_recovery_v1.json')
WORKFLOW = '.github/workflows/v3-main-transport-recovery-v1.yml'
PROFILES = ('deathstarbench_social_network', 'opentelemetry_demo', 'spring_petclinic_microservices')
ROOT = Path('workflow-recovery')


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    transport.persist(Path(path), transport.encoded(value))


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def original_names(profile, phase):
    require(profile in PROFILES, 'unknown application')
    _, cases = transport.selections(RUN, 'main')
    role = {'pmx-inputs': 'pmx-extraction', 'freeze': 'frozen', 'rescore': 'evaluation'}[phase]
    names = {f'v3-comparison-{role}-{c["artifact_key"]}-{RUN}' for c in cases
             if c['identity']['application'] == profile}
    if phase == 'pmx-inputs':
        names.add(f'v3-comparison-pmx-extraction-controls-{RUN}')
    require(len(names) == (81 if phase == 'pmx-inputs' else 80), 'source role census differs')
    return names


def source_index(config):
    rows = config['source_artifacts']
    expected = set().union(*(original_names(p, phase) for p in PROFILES
                            for phase in ('pmx-inputs', 'freeze', 'rescore')))
    require(len(rows) == 721 and len({r['id'] for r in rows}) == 721
            and {r['name'] for r in rows} == expected, 'incomplete or duplicate recovery source census')
    for row in rows:
        require(row['expired'] is False and row['workflow_run'] == dict(id=RUN, head_sha=HEAD)
                and 0 < row['size_in_bytes'] <= 100_000_000,
                'wrong original artifact identity/size')
    return {r['name']: r for r in rows}


def remote_guard():
    require(os.environ.get('GITHUB_ACTIONS') == 'true'
            and os.environ.get('GITHUB_REPOSITORY') == transport.REPO
            and os.environ.get('GITHUB_RUN_ATTEMPT') == '1', 'original remote recovery attempt required')
    config = read(CONFIG)
    require(config['source_run'] == RUN and config['source_head'] == HEAD
            and config['protocol_sha256'] == transport.DESIGN_SHA
            and config['new_campaigns'] == 0 and config['reextract_or_refit'] is False,
            'recovery scope differs')
    source_index(config)
    subprocess.run([sys.executable, 'scripts/verify_staged_research_lock.py',
                    'configs/v3_comparison_execution_v3.json'], check=True)
    run = transport.read_api(f'actions/runs/{RUN}')
    require(run['head_sha'] == HEAD and run['status'] == 'completed'
            and run['run_attempt'] == 1 and run['path'] == transport.WORKFLOW,
            'original main is not the exact terminal source')
    # These are the source identity fields expected by the unchanged scientific
    # code. The actual execution head and recovery run are recorded separately.
    actual_head = os.environ['GITHUB_SHA']
    os.environ['GITHUB_SHA'] = HEAD
    ROOT.mkdir(exist_ok=True)
    receipt = dict(version='v3-main-transport-recovery-v1', source_run=RUN, source_head=HEAD,
                   recovery_run=int(os.environ['GITHUB_RUN_ID']), recovery_workflow_head=actual_head,
                   scientific_implementation_head=HEAD, config_sha256=sha(CONFIG),
                   new_campaigns=0, refitting=False, pmx_reextraction=False,
                   original_strict_chain_qualified=False,
                   original_outcomes_already_opened=True,
                   pmx_solver_and_freeze_jobs_receive_evaluator_inputs=False)
    write(ROOT/'execution.json', receipt)
    return config, receipt


def download(item, target, *, allowed=None):
    """Exact provider identity, digest, CRC and safe paths before any extraction."""
    target = Path(target)
    require(not target.exists(), 'source destination already exists')
    data = transport.api(f'actions/artifacts/{item["id"]}/zip')
    target.mkdir(parents=True)
    archive_path = target/'source.zip'
    transport.persist(archive_path, data)
    if allowed is not None:
        members = transport.check_archive(data, item, allowed)
        for name, raw in members.items():
            transport.persist(target/'files'/name, raw)
    else:
        require(len(data) <= 100_000_000, 'oversized remote model artifact')
        info = verify_zip(archive_path, item)
        require(info['uncompressed_bytes'] <= 500_000_000, 'expanded remote model artifact too large')
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target/'files')
    write(target/'artifact-api.json', item)
    return target/'files'


def current_artifact(name):
    run_id = int(os.environ['GITHUB_RUN_ID'])
    items = transport.collect_pages(f'actions/runs/{run_id}/artifacts', 'artifacts')
    found = [r for r in items if r['name'] == name]
    require(len(found) == 1 and found[0]['expired'] is False
            and found[0]['workflow_run']['id'] == run_id
            and found[0]['workflow_run']['head_sha'] == read(ROOT/'execution.json')['recovery_workflow_head'],
            'missing/duplicate recovery artifact')
    return found[0]


def pmx_inputs(config, profile):
    by_name = source_index(config)
    for name in sorted(original_names(profile, 'pmx-inputs')):
        download(by_name[name], ROOT/'extractions'/name)
        print(json.dumps(dict(stage='saved_pmx_extraction_verified', name=name)), flush=True)
    from telemetry_availability.v3_comparison_pmx_v3 import collect
    collect(ROOT/'extractions', Path('workflow-input/petclinic-pmx-contract'), profile)
    prepared = read('workflow-input/petclinic-pmx-contract/solver-contract.json')
    require(len(prepared['extractions']) == 81
            and sum(r.get('prospective_identity') is not None for r in prepared['extractions']) == 80,
            'PMX collector omitted a planned campaign')
    print(json.dumps(dict(stage='saved_pmx_census', campaigns=80, models=prepared['model_count'])), flush=True)


def merge_frozen(original, pmx, identity, operations):
    """Only PMX slots change. Original graph candidate digest must reproduce."""
    from telemetry_availability.v3_comparison_candidates_v1 import GRAPH_METHODS, combine
    from telemetry_availability.v3_comparison_roles_v1 import digest
    old = original['candidates.json']; receipt = original['receipt.json']
    acquisition = receipt['acquisition_receipt']
    require(old['identity'] == identity and receipt['identity'] == identity
            and receipt['candidate_digest'] == digest(old)
            and receipt['workflow_run'] == str(RUN) and receipt['frozen_head'] == HEAD,
            'original frozen identity/digest differs')
    graph = dict(version='v3-comparison-candidates-v1', identity=identity,
                 forecasts={op: {m: old['forecasts'][op][m] for m in GRAPH_METHODS} for op in operations},
                 input_seal_sha256=acquisition['graph_input_seal_sha256'], builder_head=HEAD)
    require(digest(graph) == old['source_candidate_digests']['graph'], 'original graph candidate changed')
    candidate = combine(identity, operations, graph, pmx, acquisition)
    require(all(candidate['forecasts'][op][m] == old['forecasts'][op][m]
                for op in operations for m in GRAPH_METHODS), 'non-PMX forecast changed')
    return candidate


def freeze(config, execution, profile):
    from telemetry_availability.v3_comparison_roles_v1 import load_role, seal_role, digest
    from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
    settings, design, cases = planned_cases(transport.DESIGN, 'main')
    by_name = source_index(config); selections, _ = transport.selections(RUN, 'main')
    root = Path('workflow-results/recovery-frozen')
    records = []
    for case in cases:
        if case['profile'] != profile:
            continue
        identity = case['identity']; key = case['key']; ops = design['applications'][profile]
        name = f'v3-comparison-frozen-{key}-{RUN}'
        original_root = download(by_name[name], root/'original'/key, allowed=selections[name]['allowed'])/'frozen'
        original, _ = load_role(original_root, 'frozen_candidates', identity)
        pmx_root = Path('workflow-results/pmx-candidates')/('campaign-'+digest(identity)[:20])
        pmx, _ = load_role(pmx_root, 'pmx_candidates', identity)
        candidate = merge_frozen(original, pmx['candidates.json'], identity, ops)
        receipt = deepcopy(original['receipt.json'])
        receipt.update(frozen_head=HEAD, workflow_run=str(execution['recovery_run']),
                       workflow_attempt='1', candidate_digest=digest(candidate),
                       evaluator_inputs_available_in_freeze_job=False,
                       original_frozen_seal_sha256=sha(original_root/'seal.json'),
                       recovery_workflow_head=execution['recovery_workflow_head'])
        receipt['builder_role_seal_sha256']['pmx'] = sha(pmx_root/'seal.json')
        costs = deepcopy(original['costs.json']); costs['pmx'] = pmx['costs.json']
        seal_role(root/'current'/key, 'frozen_candidates', identity,
                  {'candidates.json':candidate, 'receipt.json':receipt, 'costs.json':costs})
        records.append(dict(identity=identity, original_artifact=by_name[name],
                            original_frozen_seal_sha256=sha(original_root/'seal.json'),
                            recovered_frozen_seal_sha256=sha(root/'current'/key/'seal.json'),
                            non_pmx_forecasts_unchanged=True, pmx_role_seal_sha256=sha(pmx_root/'seal.json')))
    require(len(records) == 80, 'freeze must cover every planned application campaign')
    write(root/'recovery-freeze.json', dict(execution, profile=profile, campaigns=records))


def rescore_report(original, frozen, original_frozen_sha, recovered_frozen_sha, recovery_run):
    """Reuse exactly the original all/stable sufficient counts; no test-data fit."""
    from telemetry_availability.v3_comparison_candidates_v1 import GRAPH_METHODS
    require(original['frozen_role_seal_sha256'] == original_frozen_sha
            and original['identity'] == frozen['identity'] and original['workflow_run'] == str(RUN),
            'original evaluation/freeze association differs')
    result = deepcopy(original)
    for view in ('all_sequence', 'stable'):
        for op, row in result['views'][view]['operations'].items():
            require(all(row['forecasts'][m] == frozen['forecasts'][op][m] for m in GRAPH_METHODS),
                    'original non-PMX forecast changed during recovery')
            row['forecasts'] = deepcopy(frozen['forecasts'][op])
    result.update(workflow_run=str(recovery_run), frozen_role_seal_sha256=recovered_frozen_sha,
                  original_evaluation_workflow_run=str(RUN),
                  recovery_evaluation_kind='unchanged_original_all_and_stable_sufficient_counts',
                  read_audit_scope='original evaluator read audit retained verbatim; recovery uses sealed counts')
    return result


def rescore(config, execution, profile):
    from telemetry_availability.v3_comparison_roles_v1 import load_role
    from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
    _, _, cases = planned_cases(transport.DESIGN, 'main')
    frozen_name=f'v3-main-recovery-frozen-{profile}-{execution["recovery_run"]}'
    frozen_root=download(current_artifact(frozen_name), ROOT/'frozen-input')
    manifest=read(frozen_root/'recovery-freeze.json')
    require(manifest['recovery_run'] == execution['recovery_run'] and len(manifest['campaigns']) == 80,
            'recovered freeze census differs')
    by_name=source_index(config); selections,_=transport.selections(RUN,'main')
    root=Path('workflow-results/recovery-evaluation'); records=[]
    for case in cases:
        if case['profile'] != profile:
            continue
        key=case['key']; identity=case['identity']
        frozen_path=frozen_root/'current'/key
        frozen,_=load_role(frozen_path,'frozen_candidates',identity)
        name=f'v3-comparison-evaluation-{key}-{RUN}'
        original_path=download(by_name[name],root/'original'/key,allowed=selections[name]['allowed'])
        original=read(original_path/'evaluation.json'); seal=read(original_path/'evaluation-seal.json')
        require(seal == dict(identity=identity,files={'evaluation.json':sha(original_path/'evaluation.json')},
                             head=HEAD,run_id=str(RUN)), 'original evaluation seal differs')
        report=rescore_report(original,frozen['candidates.json'],
            frozen['receipt.json']['original_frozen_seal_sha256'],sha(frozen_path/'seal.json'),execution['recovery_run'])
        write(root/'current'/key/'evaluation.json',report)
        write(root/'current'/key/'evaluation-seal.json',dict(identity=identity,
            files={'evaluation.json':sha(root/'current'/key/'evaluation.json')},head=HEAD,run_id=str(execution['recovery_run'])))
        records.append(dict(identity=identity,original_artifact=by_name[name],
            original_evaluation_sha256=sha(original_path/'evaluation.json'),
            recovered_evaluation_sha256=sha(root/'current'/key/'evaluation.json'),
            all_sequence_and_stable_counts_unchanged=True))
    require(len(records)==80,'rescore campaign census differs')
    write(root/'recovery-rescore.json',dict(execution,profile=profile,campaigns=records,
        raw_evaluator_payloads_downloaded=False, fitting_performed=False))


def summarize(execution):
    from telemetry_availability.v3_comparison_orchestration_v1 import summarize as original_summarize
    inputs=ROOT/'analysis-input'; certificates=[]
    for profile in PROFILES:
        for role,subtree,certificate in [('frozen','frozen','recovery-freeze.json'),
                                        ('evaluation','evaluations','recovery-rescore.json')]:
            name=f'v3-main-recovery-{role}-{profile}-{execution["recovery_run"]}'
            root=download(current_artifact(name),ROOT/'analysis-downloads'/name)
            # Only current roles enter the unchanged summarizer. Historical
            # originals remain in their separate retained artifacts.
            import shutil
            shutil.copytree(root/'current',inputs/subtree/profile)
            certificates.append(read(root/certificate))
    require(sum(len(c['campaigns']) for c in certificates)==480, 'recovery certificate census differs')
    out=Path('workflow-results/recovery-analysis')
    original_summarize(inputs,out,transport.DESIGN,'main')
    result=read(out/'comparison.json')
    require(len(result['campaign_gates'])==240
            and all(g['frozen_candidates'] and g['all_ten_method_slots_per_operation']
                    for g in result['campaign_gates']), 'recovery aggregation omitted a campaign')
    write(out/'recovery.json',dict(execution,
        original_empty_comparison_sha256=read(CONFIG)['original_empty_comparison_sha256'],
        recovered_comparison_sha256=sha(out/'comparison.json'),
        original_strict_main_audit_replaced=False, changed_scientific_source_files=0,
        source_campaigns=240,operation_cells_per_method=800,method_slots=8000,
        source_only_pmx_solver=True,original_graph_forecasts_preserved=True,
        original_all_sequence_and_stable_counts_preserved=True,
        candidate_evaluator_integrity=result['candidate_evaluator_integrity'],
        recovery_certificates=certificates))
    print(json.dumps({k:v for k,v in read(out/'recovery.json').items() if k!='recovery_certificates'}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['pmx-inputs','pmx-freeze','rescore','summarize'])
    parser.add_argument('--profile',choices=PROFILES)
    args=parser.parse_args()
    config,execution=remote_guard()
    if args.phase=='pmx-inputs':
        pmx_inputs(config,args.profile)
    elif args.phase=='pmx-freeze':
        subprocess.run([sys.executable,'-m','telemetry_availability.v3_comparison_pmx_v3','freeze',
            '--source','workflow-input/petclinic-pmx-contract','--solver','workflow-results/petclinic-pmx-solver',
            '--out','workflow-results/pmx-candidates'],check=True)
        freeze(config,execution,args.profile)
    elif args.phase=='rescore':
        rescore(config,execution,args.profile)
    else:
        summarize(execution)


if __name__=='__main__':
    main()
