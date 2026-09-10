"""One-shot remote admission and main retention; never changes a research method."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

import audit_v3_preflight_compact_v3 as admission_audit
import retain_v3_comparison_compact_v3 as retention

REPO = retention.REPO
PREFLIGHT_RUN = 34460574221
PREFLIGHT_HEAD = '27db98d32b683b14969f2734f19cf344c95ae1a7'
PREFLIGHT_CI = 34460277709
MAIN_TAG = 'v3-main-771601-v3-admitted'
ADMISSION = Path('configs/v3_main_admission_v1.json')
DISPATCH = Path('docs/evidence/v3-main-dispatch-v3.json')
WORKFLOW = '.github/workflows/v3-prospective-comparison-v3.yml'


def command(*args):
    return subprocess.check_output(list(args), text=True).strip()


def api(path):
    return retention.read_api(path)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    retention.persist(Path(path), retention.encoded(value))


def require(value, message):
    if not value:
        raise ValueError(message)


def trusted_run(run, *, run_id, head, workflow):
    require(run['id'] == run_id and run['head_sha'] == head and run['path'] == workflow,
            'run identity/source/workflow mismatch')
    require(run['head_repository']['full_name'] == REPO and run['event'] == 'workflow_dispatch',
            'run is not the canonical manually dispatched repository workflow')
    require(run['run_attempt'] == 1 and run['status'] == 'completed',
            'only a terminal original attempt is admissible')


def admission_record(audit, preflight, ci, execution_lock_sha):
    trusted_run(preflight, run_id=PREFLIGHT_RUN, head=PREFLIGHT_HEAD, workflow=WORKFLOW)
    require(preflight['conclusion'] == 'success', 'preflight workflow failed')
    trusted_run(ci, run_id=PREFLIGHT_CI, head=PREFLIGHT_HEAD, workflow='.github/workflows/ci.yml') if ci['event'] == 'workflow_dispatch' else None
    require(ci['id'] == PREFLIGHT_CI and ci['head_sha'] == PREFLIGHT_HEAD and
            ci['path'] == '.github/workflows/ci.yml' and ci['conclusion'] == 'success' and
            ci['status'] == 'completed' and ci['head_repository']['full_name'] == REPO and
            ci['run_attempt'] == 1 and ci['event'] in ('push', 'workflow_dispatch'),
            'preflight source CI is not verified')
    require(audit['qualified'] is True and audit['run_id'] == PREFLIGHT_RUN and
            audit['head'] == PREFLIGHT_HEAD and audit['protocol_sha256'] == retention.DESIGN_SHA and
            audit['campaigns'] == 6 and audit['operation_cells_per_method'] == 20 and
            audit['current_method_slots'] == 200 and audit['oracle_solver_records'] == 48 and
            audit['qualification_uses_forecast_error'] is False, 'compact admission audit does not qualify')
    return dict(version='v3-main-admission-v1', protocol_sha256=retention.DESIGN_SHA,
                full_preflight_qualified=True, preflight_run_id=PREFLIGHT_RUN,
                preflight_head=PREFLIGHT_HEAD, preflight_ci_run_id=PREFLIGHT_CI,
                evidence_directory=f'docs/evidence/v3-comparison-preflight-{PREFLIGHT_RUN}',
                evidence_manifest_sha256=audit['evidence_manifest_sha256'],
                comparison_sha256=audit['comparison_sha256'],
                admission_audit_sha256=sha(Path(f'docs/evidence/v3-comparison-preflight-{PREFLIGHT_RUN}')/'admission-audit.json'),
                execution_lock_path='configs/v3_comparison_execution_v3.json',
                execution_lock_sha256=execution_lock_sha, repository_lock_count=356,
                main_seed=771601, main_namespace='v3-main-771601', planned_campaigns=240,
                operation_cells_per_method=800, qualification_uses_forecast_error=False,
                main_source_tag=MAIN_TAG,
                gate_scope='Complete technical preflight; no accuracy, superiority, power or publication-readiness conclusion')


def verify_locks():
    subprocess.run([sys.executable, 'scripts/verify_staged_research_lock.py',
                    'configs/v3_comparison_execution_v3.json'], check=True)


def commit_paths(paths, message):
    require(command('git', 'diff', '--cached', '--name-only') == '', 'index already has unrelated changes')
    subprocess.run(['git', 'add', '--', *[str(p) for p in paths]], check=True)
    changed = command('git', 'diff', '--cached', '--name-only')
    if changed:
        subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
        subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
        subprocess.run(['git', 'commit', '-q', '-m', message], check=True)
        # No force push or automatic merge: concurrent source changes are an explicit stop.
        subprocess.run(['git', 'push', 'origin', 'HEAD:main'], check=True)
    return command('git', 'rev-parse', 'HEAD')


def runs_at(workflow, head):
    data = api(f'actions/workflows/{workflow}/runs?head_sha={head}&per_page=100')
    require(data['total_count'] <= 100, 'unexpected dispatch census needs review')
    return [r for r in data['workflow_runs'] if r['head_sha'] == head]


def ensure_dispatch(workflow, ref, head):
    existing = runs_at(workflow, head)
    require(len(existing) <= 1, 'multiple runs at the admitted head; never add a replicate implicitly')
    if not existing:
        args = ['gh', 'workflow', 'run', workflow, '--ref', ref]
        if workflow == Path(WORKFLOW).name:
            args += ['-f', 'mode=main']
        # Never retry a write after an uncertain response. A fresh coordinator invocation
        # first checks server state before deciding whether any new dispatch is needed.
        subprocess.run(args, check=True)
    for _ in range(24):
        existing = runs_at(workflow, head)
        require(len(existing) <= 1, 'duplicate run detected after dispatch')
        if existing:
            r = existing[0]
            require(r['run_attempt'] == 1 and r['head_repository']['full_name'] == REPO and
                    r['event'] in ('push', 'workflow_dispatch'), 'unexpected run provenance')
            return r
        time.sleep(5)
    raise RuntimeError('dispatch not observed; do not blindly redispatch')


def wait_ci(run_id, head):
    for _ in range(60):
        ci = api(f'actions/runs/{run_id}')
        require(ci['head_sha'] == head and ci['path'] == '.github/workflows/ci.yml' and
                ci['run_attempt'] == 1, 'admission CI identity changed')
        if ci['status'] == 'completed':
            require(ci['conclusion'] == 'success', 'admitted source CI failed; main remains undispatched')
            return ci
        time.sleep(20)
    raise RuntimeError('admission CI has not completed within20minutes')


def checklist(number, title, summary, updates):
    base=Path('docs/iterations/057-admitted-main240-and-preflight-results.md')
    if not base.exists(): base=Path('docs/iterations/055-active-preflight-and-v3-continuation.md')
    source=base.read_text(encoding='utf-8')
    lines=[line for line in source.splitlines() if line.startswith('| ')]
    for key,(status,evidence,remaining) in updates.items():
        lines=[f'| {key} | {status} | {evidence} | {remaining} |' if line.startswith('| '+key+' |') else line for line in lines]
    ids=[line.split('|')[1].strip() for line in lines if re.match(r'^\| [CF]\d\d \|',line)]
    require(ids==[f'C{i:02d}' for i in range(1,23)]+[f'F{i:02d}' for i in range(1,9)], 'full30criterion checklist missing')
    path=Path(f'docs/iterations/{number}-{title}.md')
    text=f'# Iteration {number}: {title.replace("-"," ")}\n\n'+summary+'\n\nUnchanged criteria reuse the current preflight/main status evidence; no publication claim is automatically promoted.\n\n'+'\n'.join(lines)+'\n'
    retention.persist(path,text.encode())
    return path


def preflight():
    root = Path(f'docs/evidence/v3-comparison-preflight-{PREFLIGHT_RUN}')
    source = api(f'actions/runs/{PREFLIGHT_RUN}')
    trusted_run(source, run_id=PREFLIGHT_RUN, head=PREFLIGHT_HEAD, workflow=WORKFLOW)
    subprocess.run([sys.executable, 'scripts/retain_v3_comparison_compact_v3.py', '--run', str(PREFLIGHT_RUN),
                    '--head', PREFLIGHT_HEAD, '--mode', 'preflight'], check=True)
    audit = admission_audit.audit(root, PREFLIGHT_RUN, PREFLIGHT_HEAD)
    write(root/'admission-audit.json', audit)
    verify_locks()
    record = admission_record(audit, source, api(f'actions/runs/{PREFLIGHT_CI}'),
                              sha('configs/v3_comparison_execution_v3.json'))
    write(ADMISSION, record)
    report = Path('docs/milestones/V3_COMPARISON_PREFLIGHT_V3_RESULT.md')
    report_text = ('# Full prospective preflight v3: verified main admission\n\n'
        f'Run `{PREFLIGHT_RUN}` at `{PREFLIGHT_HEAD}` passes the complete compact admission audit. '
        'All6 campaigns,20 operation cells per method,200 method slots and48 known oracle solver records '
        'qualify the declared procedure. Candidate/source seals, saved-model replay, permitted data reads '
        'and freeze-before-evaluator opening are checked. This is technical development evidence, not '
        'independent accuracy or publication readiness.\n\n'
        f'The [full audit](../evidence/v3-comparison-preflight-{PREFLIGHT_RUN}/admission-audit.json), '
        f'[retention manifest](../evidence/v3-comparison-preflight-{PREFLIGHT_RUN}/verified-archives.json) '
        'and [admission configuration](../../configs/v3_main_admission_v1.json) record exact identities and hashes. '
        'The failed v1/v2 series and qualified clock-progress repair remain preserved. No low-error or superiority gate is used.\n\n'
        f'Main uses its fresh seed771601 and240 campaigns. Its single source is tag `{MAIN_TAG}`; '
        'a new source-specific CI must pass before the one-shot dispatcher proceeds.\n')
    retention.persist(report, report_text.encode())
    check=checklist('056','qualified-preflight-and-main-admission',
        f'Preflight{PREFLIGHT_RUN} has passed its complete retained audit; source CI and356locks verified. Main dispatch remains conditional on fresh admitted-source CI.',
        {'C09':('ПРОВЕРЕНО','Complete v3 PMX projection, controls, probability and read chain qualifies.','Scope is development preflight; independent main remains required.'),
         'C11':('ПРОВЕРЕНО','Evidence-backed admission binds exact preflight and protocol hashes.','Main source CI and single tagged dispatch.'),
         'C19':('ЧАСТИЧНО','All28 compact artifacts retained and verified; complete admission audit saved.','Main evidence retention and full main audit.'),
         'C22':('ЧАСТИЧНО','All30 criteria retained at verified preflight admission.','Independent main and final article obligations.'),
         'F08':('ЧАСТИЧНО','The complete preflight qualifies the fixed final method set.','Independent main240 remains required.')})
    head = commit_paths([root, ADMISSION, report, check], 'Retain qualified v3 preflight and admit independent main240')
    admitted_head = command('git', 'log', '-1', '--format=%H', '--', str(ADMISSION))
    require(head == admitted_head, 'main branch advanced after admission; review before dispatch')
    remote_tag = command('git', 'ls-remote', '--tags', 'origin', f'refs/tags/{MAIN_TAG}')
    if remote_tag:
        require(remote_tag.split()[0] == head, 'main tag already points elsewhere')
    else:
        subprocess.run(['git', 'tag', MAIN_TAG, head], check=True)
        subprocess.run(['git', 'push', 'origin', 'refs/tags/'+MAIN_TAG], check=True)
    ci = ensure_dispatch('ci.yml', MAIN_TAG, head)
    ci = wait_ci(ci['id'], head)
    require(command('git', 'ls-remote', '--tags', 'origin', f'refs/tags/{MAIN_TAG}').split()[0] == head,
            'admitted tag changed before main dispatch')
    main = ensure_dispatch(Path(WORKFLOW).name, MAIN_TAG, head)
    record = dict(version='v3-main-dispatch-v3', run_id=main['id'], head=head, source_ref=MAIN_TAG,
                  preflight_run_id=PREFLIGHT_RUN, protocol_sha256=retention.DESIGN_SHA,
                  ci_run_id=ci['id'], ci_conclusion='success', main_seed=771601,
                  planned_campaigns=240, operation_cells_per_method=800,
                  workflow=WORKFLOW, raw_data_remain_remote=True)
    write(DISPATCH, record)
    progress=Path('docs/V3_CURRENT_REMOTE_STATUS.md')
    progress.write_bytes((f'# V3 independent main is running\n\nRun `{main["id"]}` at `{head}` uses admitted tag `{MAIN_TAG}`. '
        f'Source CI `{ci["id"]}` passed; full preflight `{PREFLIGHT_RUN}` is qualified. '
        'All240 campaigns and800 operation cells per method remain planned, not reported as completed. '
        'The main evidence-retention workflow will retain terminal outcomes, including failures.\n').encode())
    commit_paths([DISPATCH,progress], 'Record admitted independent main240 dispatch')
    print(json.dumps(record))


def collect_main(run_id):
    # Other v3 runs may complete. Only the one persisted admitted dispatch is eligible.
    if not DISPATCH.exists():
        print('No admitted main dispatch; no collection or mutation')
        return
    dispatch = json.loads(DISPATCH.read_bytes())
    if run_id != dispatch['run_id']:
        print('Unrelated workflow run; no collection or mutation')
        return
    run = api(f'actions/runs/{run_id}')
    trusted_run(run, run_id=run_id, head=dispatch['head'], workflow=WORKFLOW)
    require(dispatch['protocol_sha256'] == retention.DESIGN_SHA and
            dispatch['source_ref'] == MAIN_TAG, 'main dispatch protocol differs')
    tag = command('git', 'ls-remote', '--tags', 'origin', f'refs/tags/{MAIN_TAG}')
    require(tag and tag.split()[0] == dispatch['head'], 'main source tag differs')
    admitted = json.loads(command('git', 'show', dispatch['head']+':'+str(ADMISSION).replace('\\','/')))
    require(admitted['full_preflight_qualified'] is True and
            admitted['protocol_sha256'] == retention.DESIGN_SHA and
            admitted['preflight_run_id'] == PREFLIGHT_RUN, 'main source lacks verified admission')
    root = Path(f'docs/evidence/v3-comparison-main-{run_id}')
    subprocess.run([sys.executable, 'scripts/retain_v3_comparison_compact_v4.py', '--run', str(run_id),
                    '--head', dispatch['head'], '--mode', 'main'], check=True)
    source = root/'analysis/files/comparison.json'
    tables = Path(f'docs/tables/v3-main-{run_id}')
    paths = [root]
    record = dict(version='v3-main-compact-collection-v2', run_id=run_id, head=dispatch['head'],
                  workflow_conclusion=run['conclusion'], expected_campaigns=240,
                  expected_operation_cells_per_method=800, main_dispatch_verified=True,
                  raw_payloads_downloaded=False, publication_ready=False,
                  full_main_read_audit_completed=False)
    if source.exists():
        report = json.loads(source.read_bytes())
        seal = json.loads((source.parent/'comparison-seal.json').read_bytes())
        require(seal['files'] == {'comparison.json':sha(source)} and
                seal['head'] == dispatch['head'] and str(seal['run_id']) == str(run_id) and
                seal['protocol_sha256'] == retention.DESIGN_SHA, 'main comparison seal differs')
        require(report['mode']=='main' and report['data_role']=='prospective_main' and
                report['campaign_count']==240 and report['operation_cells_per_method']==800 and
                report['head']==dispatch['head'] and str(report['run_id'])==str(run_id) and
                report['protocol_sha256']==retention.DESIGN_SHA and
                report['qualification_uses_forecast_error'] is False, 'main analysis identity/census differs')
        import audit_v3_main_compact_v2 as main_audit
        try:
            integrity=main_audit.audit(root,run_id,dispatch['head'])
        except (ValueError,KeyError,FileNotFoundError) as error:
            # Preserve an explicit failed strict audit; never replace it with a success.
            integrity=dict(version='v3-compact-main-integrity-audit-v2',qualified=False,
                run_id=run_id,head=dispatch['head'],reason=str(error),
                fit_or_replay_executed_locally=False)
        write(root/'main-integrity-audit.json',integrity)
        record['full_main_read_audit_completed']=True
        record['strict_main_integrity_qualified']=integrity['qualified']
        record['main_auditor_sha256']=sha('scripts/audit_v3_main_compact_v2.py')
        from render_v3_comparison_tables_v1 import render
        render(source,tables)
        record.update(analysis_available=True,comparison_sha256=sha(source),
                      remote_candidate_evaluator_integrity=report['candidate_evaluator_integrity'],
                      remote_nonempty_primary_family=report['nonempty_primary_family'],
                      retained_method_slots=report['analysis']['method_slots'],
                      publication_tables=str(tables.as_posix()))
        paths.append(tables)
    else:
        record.update(analysis_available=False, reason='No complete remote analysis artifact; all available absence/provenance records retained')
    write(root/'collection-summary.json',record)
    result = Path('docs/milestones/V3_MAIN_COLLECTION_V2_RESULT.md')
    text = ('# Independent main: remote evidence retained\n\n'
            f"Run `{run_id}` at `{dispatch['head']}` is terminal with workflow conclusion `{run['conclusion']}`. "
            'Its dispatch is bound to the qualified preflight and admitted source tag. '
            'The exact compact artifact allowlist, provider digests, extracted bytes and available final analysis seal are checked. '
            'The separate strict integrity audit records whether every main read/seal/replay/order check qualified. Scientific interpretation remains a separate obligation.\n\n'
            f'[Collection status](../evidence/v3-comparison-main-{run_id}/collection-summary.json) and '
            f'[artifact manifest](../evidence/v3-comparison-main-{run_id}/verified-archives.json) retain all missing cases explicitly.\n')
    if source.exists():
        text+=f'\n[Generated publication tables](../tables/v3-main-{run_id}/README.md) copy all existing remote metrics, statuses and contrasts without refitting or resampling.\n'
    retention.persist(result,text.encode())
    paths.append(result)
    check=checklist('058','independent-main-evidence-retention',
        f'Main run{run_id} is terminal with conclusion{run["conclusion"]}; all available compact evidence retained. Full scientific review remains separate.',
        {'C13':('ЧАСТИЧНО','Main planned240campaign identities retained with explicit artifacts/absences; available remote8000slot analysis exported.','Inspect any missing analysis or failed strict main read-order checks.'),
         'C14':('ЧАСТИЧНО','Remote metric/contrast/coverage tables copied without refit or resampling.','Scientific interpretation of complete common support and uncertainty.'),
         'C19':('ЧАСТИЧНО','Main ZIP/member hashes, dispatch/tag identity and available comparison seal verified.','Strict main audit result and final publication package.'),
         'C22':('ЧАСТИЧНО','All30 criteria carried with explicit main retention scope.','Resolve remaining article and evidence obligations.'),
         'F08':('ЧАСТИЧНО','Independent main has reached its terminal remote state.','Assess valid main support and final claims; failed cases remain visible.')})
    paths.append(check)
    progress=Path('docs/V3_CURRENT_REMOTE_STATUS.md')
    progress.write_bytes((f'# V3 independent main is terminal\n\nRun `{run_id}` at `{dispatch["head"]}` finished with `{run["conclusion"]}`. '
        '[Retained outcome and tables](milestones/V3_MAIN_COLLECTION_V2_RESULT.md) describe the evidence and missing cases. '
        'The strict main audit result and remaining scientific interpretation are explicit; publication readiness is not asserted.\n').encode())
    paths.append(progress)
    head=commit_paths(paths,'Retain independent main evidence and complete planned result tables')
    ci=ensure_dispatch('ci.yml','main',head)
    wait_ci(ci['id'],head)
    print(json.dumps(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['admit', 'collect'])
    parser.add_argument('--run', type=int)
    args = parser.parse_args()
    require(os.environ.get('GITHUB_ACTIONS') == 'true', 'admission coordinator is remote only')
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'wrong repository')
    if args.command == 'admit':
        preflight()
    else:
        require(args.run is not None and args.run>0, 'exact completed main run ID required')
        collect_main(args.run)


if __name__ == '__main__':
    main()
