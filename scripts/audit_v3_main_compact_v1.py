"""Audit all240 compact main campaigns and access order; no fitting or raw reads.

This produces an audit report only. It never creates main admission or dispatches jobs.
"""
import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path

import retain_v3_comparison_compact_v2 as retention


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sealed(root, role, identity, members):
    seal = read(root/'seal.json')
    require(seal['role'] == role and seal['version'] == 'v3-comparison-roles-v1' and seal['identity'] == identity, 'role/version/identity differs')
    require(set(seal['files']) == set(members), 'role member census differs')
    require(all(sha(root/name) == seal['files'][name] for name in members), 'role member hash differs')
    return {name: read(root/name) for name in members}


def read_audit(record, suffixes):
    actual = record['actual_data_reads']
    require(not record['blocked'] and len(actual) == len(suffixes) and len(set(actual)) == len(actual), 'read boundary blocked/duplicate/census differs')
    require(all(sum(path.endswith('/'+suffix) for path in actual) == 1 for suffix in suffixes), 'actual data read path differs')


def probability(row, expected=None):
    values = [row.get(key) for key in ('success_probability', 'failure_probability_sum', 'physical_state_probability')]
    require(row.get('status') == 'solved' and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values), 'invalid solver probability')
    require(abs(values[0]+values[1]-1) <= 1e-12 and abs(values[2]-1) <= 1e-12, 'invalid solver probability mass')
    require(type(row.get('total_physical_states')) is int and row['total_physical_states'] >= 1 and row.get('evaluated_physical_states') == row['total_physical_states'], 'solver state census differs')
    if expected is not None:
        require(abs(values[0]-expected) <= 1e-12, 'known probability not reproduced')


def audit(root, expected_run, expected_head):
    manifest = read(root/'verified-archives.json')
    require(manifest['run_id'] == expected_run and manifest['head'] == expected_head and manifest['mode'] == 'main', 'evidence identity differs')
    require(manifest['protocol_sha256'] == retention.DESIGN_SHA and manifest['planned_campaigns'] == 240, 'main design differs')
    choices, cases = retention.selections(expected_run, 'main')
    require(read(root/'planned-identities.json') == cases, 'retained planned identity census differs')
    require(not manifest['raw_native_ordinary_model_solver_payloads_downloaded'], 'unexpected full payload retention')
    artifacts = read(root/'all-artifact-metadata.json')
    records = manifest['records']; by_name = {a['name']: a for a in artifacts}
    require(len(by_name) == len(artifacts) and len({r['name'] for r in records}) == len(records), 'duplicate evidence records')
    require(not manifest['absent_artifacts'] and {r['name'] for r in records} == set(choices), 'required compact artifact absent')
    for record in records:
        name = record['name']; choice = choices[name]; directory = root/choice['directory']
        require(record['directory'] == choice['directory'], 'retained directory substitution')
        data = (directory/'compact.zip').read_bytes()
        require(sha256(data).hexdigest() == record['sha256'], 'retained archive digest differs')
        members = retention.check_archive(data, by_name[name], choice['allowed'])
        for member, raw in members.items():
            require((directory/'files'/member).read_bytes() == raw, 'retained extracted member differs')
    result_path = root/'analysis/files/comparison.json'
    result = read(result_path); seal = read(root/'analysis/files/comparison-seal.json')
    require(seal == dict(files={'comparison.json':sha(result_path)}, head=expected_head, run_id=str(expected_run), protocol_sha256=retention.DESIGN_SHA), 'comparison seal differs')
    require(result['head'] == expected_head and result['run_id'] == str(expected_run) and result['mode'] == 'main' and result['data_role'] == 'prospective_main', 'analysis provenance differs')
    require(result['main_campaigns'] == 240 and result['campaign_count'] == 240 and result['operation_cells_per_method'] == 800, 'analysis planned census differs')
    require(result['admission_candidate'] is True and result['candidate_evaluator_integrity'] is True and result['nonempty_primary_family'] is True and result['qualification_uses_forecast_error'] is False, 'strict complete main chain not qualified')
    settings = read(retention.DESIGN); methods = settings['methods']; summaries=[]; profiles=list(settings['design']['applications'])
    oracle_count=0
    expected_controls = {'recursive_native_name': {'inclusive': .576, 'conditional_local': .8},
        'cross_trace_call_order': {'inclusive': 1., 'conditional_local': 1.},
        'database_propagated': {'inclusive': .576, 'conditional_local': .8},
        'shared_database_two_callers': {'inclusive': .59049, 'conditional_local': .81}}
    for index, profile in enumerate(profiles,1):
        controls=read(root/f'pmx-{index:02d}/files/controls.json')
        wanted={'controls--'+case+'--'+variant:value for case, variants in expected_controls.items() for variant,value in variants.items()}
        require(controls['qualified'] is True and controls['expected_two_pass_oracle_records']==16, 'PMX oracle batch not qualified')
        require(len(controls['controls'])==8 and {c['model_id'] for c in controls['controls']}==set(wanted), 'PMX oracle model census differs')
        for control in controls['controls']:
            require(control['qualified'] is True and control['expected']==wanted[control['model_id']], 'oracle identity/expectation differs')
            rows=control['results']
            require(len(rows)==2 and {r['repetition'] for r in rows}=={0,1} and all(r['model_id']==control['model_id'] for r in rows), 'oracle repeat census differs')
            for row in rows: probability(row,wanted[control['model_id']]); oracle_count+=1
    for case in cases:
        identity=case['identity']; directory=root/case['local_case']; ops=settings['design']['applications'][identity['application']]
        acquisition=read(directory/'receipt/files/receipt.json')
        require(acquisition['identity']==identity and acquisition['acquisition_head']==expected_head and acquisition['acquisition_run']==str(expected_run), 'acquisition provenance differs')
        frozen_root=directory/'frozen/files/frozen'
        frozen=sealed(frozen_root,'frozen_candidates',identity,('candidates.json','costs.json','receipt.json'))
        candidate=frozen['candidates.json']; receipt=frozen['receipt.json']
        require(receipt['frozen_head']==expected_head and receipt['workflow_run']==str(expected_run) and receipt['workflow_attempt']=='1', 'freeze provenance differs')
        require(receipt['evaluator_inputs_available_in_freeze_job'] is False and receipt['acquisition_receipt']==acquisition, 'freeze input association differs')
        require(receipt['candidate_digest']==digest(candidate) and candidate['evaluator_seal_sha256']==acquisition['evaluator_seal_sha256'], 'candidate/evaluator seal differs')
        graph=read(directory/'graph-compact/files/results.json'); replay=read(directory/'graph-compact/files/replay.json')
        require(graph['identity']==identity and graph['candidate_seal_sha256']==receipt['builder_role_seal_sha256']['graph']==replay['candidate_seal_sha256'], 'graph/replay role association differs')
        require(replay['result']['exact'] is True, 'graph replay not exact')
        read_audit(graph['read_audit'],{'workflow-input/ordinary/'+n for n in ('native.json','requests.json','probes.json','declarations.json','manifest.json','seal.json')})
        read_audit(replay['read_audit'],{'workflow-results/graph/candidates/'+n for n in ('candidates.json','models.json','costs.json','read-audit.json','seal.json')})
        graph_candidate=dict(version='v3-comparison-candidates-v1',identity=identity,forecasts=graph['forecasts'],input_seal_sha256=acquisition['graph_input_seal_sha256'],builder_head=expected_head)
        require(digest(graph_candidate)==candidate['source_candidate_digests']['graph'], 'graph candidate digest differs')
        pmx_index=profiles.index(identity['application'])+1
        pmx_root=root/f'pmx-{pmx_index:02d}/files'/('campaign-'+digest(identity)[:20])
        pmx=sealed(pmx_root,'pmx_candidates',identity,('candidates.json','costs.json','read-audit.json'))
        require(sha(pmx_root/'seal.json')==receipt['builder_role_seal_sha256']['pmx'], 'PMX role association differs')
        require(pmx['candidates.json']['version']=='v3-independent-pmx-comparison-v2', 'PMX bridge version differs')
        require(digest(pmx['candidates.json'])==candidate['source_candidate_digests']['pmx'], 'PMX candidate digest differs')
        require(pmx['candidates.json']['builder_head']==expected_head and pmx['candidates.json']['input_seal_sha256']==acquisition['pmx_input_seal_sha256'], 'PMX source input differs')
        read_audit(pmx['read-audit.json'],{'workflow-input/pmx-native/'+n for n in ('native.json','requests.json','manifest.json','seal.json')})
        require(pmx['read-audit.json']['health_or_our_model_or_evaluator_inputs']==0, 'PMX extra inputs recorded')
        evaluator_path=directory/'evaluation/files/evaluation.json'; evaluator=read(evaluator_path)
        eval_seal=read(directory/'evaluation/files/evaluation-seal.json')
        require(eval_seal==dict(identity=identity,files={'evaluation.json':sha(evaluator_path)},head=expected_head,run_id=str(expected_run)), 'evaluation report seal differs')
        require(evaluator['identity']==identity and evaluator['evaluation_head']==expected_head and evaluator['workflow_run']==str(expected_run), 'evaluation provenance differs')
        require(evaluator['frozen_role_seal_sha256']==sha(frozen_root/'seal.json') and evaluator['evaluator_role_seal_sha256']==acquisition['evaluator_seal_sha256'], 'opened evaluator/frozen hash differs')
        read_audit(evaluator['read_audit'],{'workflow-input/frozen/frozen/'+n for n in ('candidates.json','costs.json','receipt.json','seal.json')} | {'workflow-input/evaluator/'+n for n in ('requests.json','probes.json','manifest.json','seal.json')})
        require(evaluator['read_audit']['fitting_or_recalibration_performed'] is False and evaluator['read_audit']['candidate_loaded_before_closed_role'] is True, 'evaluation refit/order differs')
        status_counts=Counter()
        require(set(candidate['forecasts'])==set(ops), 'operation census differs')
        for op in ops:
            forecasts=candidate['forecasts'][op]
            require(set(forecasts)==set(methods), 'method census differs')
            for method,forecast in forecasts.items():
                status_counts[(method,forecast['status'])]+=1
                require(forecast['status'] in ('ok','unsupported'), 'unresolved technical forecast failure: '+method)
                if forecast['status']=='ok': require(type(forecast['probability']) in (int,float) and math.isfinite(forecast['probability']) and 0<=forecast['probability']<=1,'invalid forecast')
                else: require(forecast['probability'] is None and forecast.get('reason'), 'absence lacks reason/null')
                source=pmx['candidates.json']['forecasts'][op] if method in ('PMX','PMX_inclusive') else graph['forecasts'][op]
                require(forecast==source[method], 'frozen method changed')
            all_rows=evaluator['views']['all_sequence']['operations'][op]
            require(all_rows['attempts']==3600//len(ops) and all_rows['forecasts']==forecasts, 'test census/forecast differs')
            require(evaluator['views']['stable']['operations'][op]['forecasts']==forecasts, 'stable view refitted forecast')
        require(evaluator['views']['all_sequence']['evaluator_status']=='qualified', 'evaluator quality gate failed')
        summaries.append(dict(identity=identity,forecast_statuses=[dict(method=k[0],status=k[1],count=v) for k,v in sorted(status_counts.items())],actual_data_read_counts=dict(graph=6,replay=5,pmx=4,evaluator=8)))
    jobs=read(root/'jobs-api.json')
    freeze_jobs=[j for j in jobs if j['name'].startswith('freeze (')]
    evaluation_jobs=[j for j in jobs if j['name'].startswith('evaluate (')]
    require(len(freeze_jobs)==240 and len(evaluation_jobs)==240 and all(j['conclusion']=='success' for j in freeze_jobs+evaluation_jobs), 'freeze/evaluator job census differs')
    last_freeze=max(datetime.fromisoformat(j['completed_at']) for j in freeze_jobs)
    order=[]
    for job in evaluation_jobs:
        require(last_freeze<=datetime.fromisoformat(job['started_at']), 'evaluator started before all freezes completed')
        steps=job['steps']; guards=[s for s in steps if s['name']=='Require a complete frozen candidate role before downloading closed outcomes']
        require(len(guards)==1 and guards[0]['conclusion']=='success','pre-download guard missing')
        guard=guards[0]; following=[s for s in steps if s['number']==guard['number']+1]
        require(len(following)==1 and 'download-artifact' in following[0]['name'] and following[0]['conclusion']=='success','closed download not immediately after guard')
        require(datetime.fromisoformat(guard['completed_at'])<=datetime.fromisoformat(following[0]['started_at']), 'closed download precedes guard')
        order.append(dict(job_id=job['id'],guard_completed_at=guard['completed_at'],closed_download_started_at=following[0]['started_at']))
    return dict(version='v3-compact-main-integrity-audit-v1',qualified=True,run_id=expected_run,head=expected_head,protocol_sha256=retention.DESIGN_SHA,
        evidence_manifest_sha256=sha(root/'verified-archives.json'),comparison_sha256=sha(result_path),campaigns=240,operation_cells_per_method=800,
        oracle_solver_records=oracle_count,current_method_slots=8000,qualification_uses_forecast_error=False,
        main_admission_created=False,main_campaigns=240,fit_or_replay_executed_locally=False,
        actual_read_audits=summaries,evaluator_opening_order=order)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--run',type=int,required=True)
    parser.add_argument('--head',required=True)
    args=parser.parse_args(); report=audit(args.evidence,args.run,args.head)
    retention.persist(args.evidence/'main-integrity-audit.json',retention.encoded(report))
    print(json.dumps({k:v for k,v in report.items() if k not in ('actual_read_audits','evaluator_opening_order')}))


if __name__=='__main__':
    main()
