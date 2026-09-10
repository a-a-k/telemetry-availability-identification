"""Retain only sealed compact recovery forecasts/counts; never PCM/native payloads."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import retain_v3_comparison_compact_v4 as transport
import recover_v3_main_transport_v1 as recovery
import audit_v3_main_compact_v2 as audit


def choices(run_id):
    original,cases=transport.selections(recovery.RUN,'main')
    selected={}
    for index,profile in enumerate(recovery.PROFILES,1):
        pmx=original[f'v3-comparison-pmx-candidates-{profile}-{recovery.RUN}']['allowed']
        frozen={'recovery-freeze.json'};evaluation={'recovery-rescore.json'}
        for case in cases:
            if case['identity']['application']!=profile:continue
            key=case['artifact_key']
            frozen.update(f'current/{key}/{name}' for name in ('candidates.json','costs.json','receipt.json','seal.json'))
            frozen.update(f'original/{key}/files/frozen/{name}' for name in ('candidates.json','costs.json','receipt.json','seal.json'))
            frozen.update(f'original/{key}/{name}' for name in ('source.zip','artifact-api.json'))
            evaluation.update(f'current/{key}/{name}' for name in ('evaluation.json','evaluation-seal.json'))
            evaluation.update(f'original/{key}/files/{name}' for name in ('evaluation.json','evaluation-seal.json'))
            evaluation.update(f'original/{key}/{name}' for name in ('source.zip','artifact-api.json'))
        for role,allowed,directory in [('pmx-candidates',pmx,f'pmx-{index:02d}'),('frozen',frozen,f'frozen-{index:02d}'),
                                        ('evaluation',evaluation,f'evaluation-{index:02d}')]:
            selected[f'v3-main-recovery-{role}-{profile}-{run_id}']=dict(directory=directory,allowed=allowed)
    selected[f'v3-main-recovery-analysis-{run_id}']=dict(directory='analysis',allowed={'comparison.json','comparison-seal.json','recovery.json'})
    return selected,cases


def run_guard(run,run_id):
    audit.require(run['id']==run_id and run['path']==recovery.WORKFLOW
        and run['head_repository']['full_name']==transport.REPO and run['event']=='workflow_dispatch'
        and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']=='success',
        'exact successful original recovery execution required')


def continuity(root,run,cases):
    read=audit.read;sha=audit.sha;require=audit.require
    source=Path(f'docs/evidence/v3-comparison-main-{recovery.RUN}')
    config=recovery.read(recovery.CONFIG); source_items=recovery.source_index(config)
    comparison=read(root/'analysis/files/comparison.json')
    certificate=read(root/'analysis/files/recovery.json')
    require(certificate['source_run']==recovery.RUN and certificate['source_head']==recovery.HEAD
        and certificate['recovery_run']==run['id'] and certificate['recovery_workflow_head']==run['head_sha']
        and certificate['original_strict_main_audit_replaced'] is False
        and certificate['original_outcomes_already_opened'] is True,'recovery identity/disclosure differs')
    require(certificate['original_empty_comparison_sha256']==sha(source/'analysis/files/comparison.json')
        and certificate['recovered_comparison_sha256']==sha(root/'analysis/files/comparison.json'),
        'original/recovered comparison association differs')
    require(read(root/'analysis/files/comparison-seal.json')==dict(files={'comparison.json':sha(root/'analysis/files/comparison.json')},
        head=recovery.HEAD,run_id=str(run['id']),protocol_sha256=transport.DESIGN_SHA),'recovery comparison seal differs')
    require(comparison['campaign_count']==240 and comparison['operation_cells_per_method']==800
            and comparison['analysis']['method_slots']==8000,'recovery result census differs')
    expected_build=read(Path('configs/v3_comparison_execution_v3.json'))['pmx_clock_progress']
    problems=[];rows=[];oracles=0;attempts=0
    original_selections,_=transport.selections(recovery.RUN,'main')
    for index,profile in enumerate(recovery.PROFILES,1):
        controls=read(root/f'pmx-{index:02d}/files/controls.json')
        require(controls['qualified_pmx_build']==expected_build,'recovery PMX binary differs')
        if controls['qualified'] is not True:problems.append(profile+': known PMX control gate failed')
        wanted={'controls--'+case+'--'+variant:expected for case,variants in {
            'recursive_native_name':{'inclusive':.576,'conditional_local':.8},
            'cross_trace_call_order':{'inclusive':1.,'conditional_local':1.},
            'database_propagated':{'inclusive':.576,'conditional_local':.8},
            'shared_database_two_callers':{'inclusive':.59049,'conditional_local':.81}}.items()
            for variant,expected in variants.items()}
        require(len(controls['controls'])==8 and {c['model_id'] for c in controls['controls']}==set(wanted),'oracle census differs')
        for control in controls['controls']:
            require(control['expected']==wanted[control['model_id']],'oracle expectation changed')
            require(len(control['results'])==2 and {r['repetition'] for r in control['results']}=={0,1},'oracle repeats differ')
            for row in control['results']:audit.probability(row,control['expected']);oracles+=1
    for case in cases:
        identity=case['identity'];key=case['artifact_key'];index=recovery.PROFILES.index(identity['application'])+1
        original_base=source/case['local_case'];fbase=root/f'frozen-{index:02d}/files';ebase=root/f'evaluation-{index:02d}/files'
        for role,base in [('frozen',fbase),('evaluation',ebase)]:
            name=f'v3-comparison-{role}-{key}-{recovery.RUN}'
            retained=base/'original'/key
            require((retained/'source.zip').read_bytes()==(original_base/role/'compact.zip').read_bytes(),'original compact ZIP changed')
            metadata=read(retained/'artifact-api.json')
            require(all(metadata[k]==v for k,v in source_items[name].items()),'original provider identity changed')
            members=transport.check_archive((retained/'source.zip').read_bytes(),metadata,original_selections[name]['allowed'])
            require(all((retained/'files'/n).read_bytes()==b for n,b in members.items()),'original extracted compact member changed')
        old=read(original_base/'frozen/files/frozen/candidates.json')
        old_receipt=read(original_base/'frozen/files/frozen/receipt.json')
        frozen_root=fbase/'current'/key
        frozen=audit.sealed(frozen_root,'frozen_candidates',identity,('candidates.json','costs.json','receipt.json'))
        receipt=frozen['receipt.json'];candidate=frozen['candidates.json']
        require(receipt['candidate_digest']==audit.digest(candidate)
            and receipt['original_frozen_seal_sha256']==sha(original_base/'frozen/files/frozen/seal.json')
            and receipt['workflow_run']==str(run['id']) and receipt['frozen_head']==recovery.HEAD
            and receipt['evaluator_inputs_available_in_freeze_job'] is False
            and receipt['acquisition_receipt']==old_receipt['acquisition_receipt'],'freeze/source chain differs')
        pmx_root=root/f'pmx-{index:02d}/files'/('campaign-'+audit.digest(identity)[:20])
        pmx=audit.sealed(pmx_root,'pmx_candidates',identity,('candidates.json','costs.json','read-audit.json'))
        require(sha(pmx_root/'seal.json')==receipt['builder_role_seal_sha256']['pmx']
            and candidate['source_candidate_digests']['pmx']==audit.digest(pmx['candidates.json']), 'PMX role association differs')
        require(pmx['candidates.json']['builder_head']==recovery.HEAD
            and pmx['candidates.json']['input_seal_sha256']==receipt['acquisition_receipt']['pmx_input_seal_sha256'],
            'PMX original calibration association differs')
        ops=list(old['forecasts'])
        audit.pmx_binary_provenance(pmx,identity,ops,expected_build)
        audit.read_audit(pmx['read-audit.json'],{'workflow-input/pmx-native/'+n for n in ('native.json','requests.json','manifest.json','seal.json')})
        require(pmx['read-audit.json']['health_or_our_model_or_evaluator_inputs']==0,'PMX received forbidden source input')
        require(frozen['costs.json']['pmx']==pmx['costs.json'],'PMX cost evidence differs')
        solver_evidence=pmx['costs.json']['solver_evidence']
        require(len(solver_evidence)==2*len(ops) and len({r['model_id'] for r in solver_evidence})==len(solver_evidence),
                'PMX application solver evidence census differs')
        solver_by_id={r['model_id']:r for r in solver_evidence}
        for op in ops:
            for method in ('PMX','PMX_inclusive'):
                forecast=pmx['candidates.json']['forecasts'][op][method]
                evidence=solver_by_id[forecast['model_id']]
                if forecast['status']=='ok':
                    values=evidence['solver_records']
                    require(len(values)==2 and {r['repetition'] for r in values}=={0,1}
                        and all(r['model_id']==forecast['model_id'] for r in values),'application solver repeat census differs')
                    for row in values:audit.probability(row)
                    require(abs(values[0]['success_probability']-values[1]['success_probability'])<=1e-12
                        and forecast['probability']==values[0]['success_probability'],'PMX forecast differs from repeated solve')
        original_costs=read(original_base/'frozen/files/frozen/costs.json')
        require({k:v for k,v in frozen['costs.json'].items() if k!='pmx'}==
                {k:v for k,v in original_costs.items() if k!='pmx'},'non-PMX costs changed')
        graph=read(original_base/'graph-compact/files/results.json');replay=read(original_base/'graph-compact/files/replay.json')
        require(graph['candidate_seal_sha256']==receipt['builder_role_seal_sha256']['graph']==replay['candidate_seal_sha256']
            and replay['result']['exact'] is True,'original graph replay association differs')
        graph_candidate=dict(version='v3-comparison-candidates-v1',identity=identity,forecasts=graph['forecasts'],
            input_seal_sha256=receipt['acquisition_receipt']['graph_input_seal_sha256'],builder_head=recovery.HEAD)
        require(graph['identity']==identity and audit.digest(graph_candidate)==old['source_candidate_digests']['graph']
                ==candidate['source_candidate_digests']['graph'],'graph candidate digest continuity differs')
        audit.read_audit(graph['read_audit'],{'workflow-input/ordinary/'+n for n in ('native.json','requests.json','probes.json','declarations.json','manifest.json','seal.json')})
        audit.read_audit(replay['read_audit'],{'workflow-results/graph/candidates/'+n for n in ('candidates.json','models.json','costs.json','read-audit.json','seal.json')})
        for op in ops:
            for method,forecast in candidate['forecasts'][op].items():
                expected=pmx['candidates.json']['forecasts'][op][method] if method in ('PMX','PMX_inclusive') else old['forecasts'][op][method]
                require(forecast==expected,'frozen forecast changed')
                if forecast['status'] not in ('ok','unsupported'):problems.append(key+': '+method+': '+str(forecast.get('reason')))
        original_eval=read(original_base/'evaluation/files/evaluation.json')
        report_path=ebase/'current'/key/'evaluation.json';report=read(report_path)
        require(read(report_path.parent/'evaluation-seal.json')==dict(identity=identity,files={'evaluation.json':sha(report_path)},
            head=recovery.HEAD,run_id=str(run['id'])),'recovered evaluation seal differs')
        # Verify the exact permitted substitution, including every nested count,
        # qualifier and original read-audit field. No statistical/model execution.
        expected=deepcopy(original_eval)
        for view in ('all_sequence','stable'):
            for op,row in expected['views'][view]['operations'].items():row['forecasts']=candidate['forecasts'][op]
        expected.update(workflow_run=str(run['id']),frozen_role_seal_sha256=sha(frozen_root/'seal.json'),
            original_evaluation_workflow_run=str(recovery.RUN),
            recovery_evaluation_kind='unchanged_original_all_and_stable_sufficient_counts',
            read_audit_scope='original evaluator read audit retained verbatim; recovery uses sealed counts')
        require(report==expected,'original sufficient counts or unapproved evaluation fields changed')
        attempts+=sum(r['attempts'] for r in report['views']['all_sequence']['operations'].values())
        if report['views']['all_sequence']['evaluator_status']!='qualified':problems.append(key+': evaluator unqualified')
        rows.append(dict(identity=identity,non_pmx_forecasts_unchanged=True,original_counts_unchanged=True))
    jobs=read(root/'jobs-api.json');pmx_jobs=[j for j in jobs if j['name'].startswith('Recover saved PMX')]
    rescore_jobs=[j for j in jobs if j['name'].startswith('rescore (')]
    require(len(pmx_jobs)==3 and len(rescore_jobs)==3 and all(j['conclusion']=='success' for j in pmx_jobs+rescore_jobs),'recovery job census differs')
    from datetime import datetime
    last=max(datetime.fromisoformat(j['completed_at']) for j in pmx_jobs)
    require(all(datetime.fromisoformat(j['started_at'])>=last for j in rescore_jobs),'recovered counts opened before all forecasts frozen')
    original_jobs=read(source/'jobs-api.json')
    original_freezes=[j for j in original_jobs if j['name'].startswith('freeze (')]
    original_evaluators=[j for j in original_jobs if j['name'].startswith('evaluate (')]
    require(len(original_freezes)==240 and len(original_evaluators)==240,'original freeze/evaluator job census differs')
    original_last=max(datetime.fromisoformat(j['completed_at']) for j in original_freezes)
    require(all(j['conclusion']=='success' for j in original_freezes+original_evaluators)
        and all(datetime.fromisoformat(j['started_at'])>=original_last for j in original_evaluators),
        'original graph freeze/evaluator chronology differs')
    require(attempts==864000 and oracles==48,'main attempt/oracle census differs')
    return dict(version='v3-main-transport-recovery-continuity-v1',source_run=recovery.RUN,recovery_run=run['id'],
        byte_and_count_continuity_verified=True,all_technical_forecast_and_evaluator_gates_pass=not problems,
        problems=problems,original_strict_prospective_chain_restored=False,
        original_outcomes_opened_before_recovered_pmx=True,isolated_recovery_freeze_before_count_access=True,
        original_graph_forecasts_frozen_before_original_evaluation=True,
        source_campaigns=240,new_campaigns=0,test_attempts=attempts,oracle_records=oracles,
        fit_or_solver_or_bootstrap_executed_locally=False,campaigns=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=int,required=True);args=parser.parse_args()
    run=transport.read_api(f'actions/runs/{args.run}');run_guard(run,args.run)
    for name in (str(recovery.CONFIG),'scripts/recover_v3_main_transport_v1.py',recovery.WORKFLOW):
        committed=subprocess.check_output(['git','show',run['head_sha']+':'+name.replace('\\','/')])
        same=(json.loads(committed)==recovery.read(name)) if name==str(recovery.CONFIG) else committed==Path(name).read_bytes()
        audit.require(same,'recovery checkout content differs: '+name)
    root=Path(f'docs/evidence/v3-main-transport-recovery-{args.run}')
    selected,cases=choices(args.run)
    artifacts=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts');by_name={a['name']:a for a in artifacts}
    audit.require(len(by_name)==len(artifacts) and set(selected)<=set(by_name),'recovery compact census missing/duplicated')
    transport.persist(root/'run-api.json',transport.encoded(run))
    transport.persist(root/'jobs-api.json',transport.encoded(transport.collect_pages(f'actions/runs/{args.run}/jobs','jobs')))
    records=[]
    for name,choice in selected.items():
        item=by_name[name];audit.require(item['workflow_run']['id']==args.run and item['workflow_run']['head_sha']==run['head_sha'],'foreign recovery artifact')
        data=transport.api(f'actions/artifacts/{item["id"]}/zip')
        members=transport.check_archive(data,item,choice['allowed'])
        audit.require(set(members)==choice['allowed'],'incomplete compact recovery artifact')
        target=root/choice['directory'];transport.persist(target/'compact.zip',data)
        transport.persist(target/'artifact-api.json',transport.encoded(item))
        for member,content in members.items():transport.persist(target/'files'/member,content)
        records.append(dict(name=name,id=item['id'],directory=choice['directory'],bytes=len(data),sha256=sha256(data).hexdigest(),members=len(members)))
    transport.persist(root/'retention.json',transport.encoded(dict(version='v3-main-transport-recovery-retention-v1',
        run_id=args.run,head=run['head_sha'],records=records,source_run=recovery.RUN,
        raw_native_pcm_solver_payloads_downloaded=False)))
    report=continuity(root,run,cases)
    transport.persist(root/'continuity-audit.json',transport.encoded(report))
    print(json.dumps({k:v for k,v in report.items() if k not in ('campaigns','problems')}))


if __name__=='__main__':main()
