"""Artificial240case census and last-case defects for compact main provenance."""
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import audit_v3_main_compact_v1 as audit
import retain_v3_comparison_compact_v2 as retention

HEAD = 'a'*40
RUN = 123456


def fixture(root, defect=None):
    choices,cases=retention.selections(RUN,'main')
    settings=audit.read(retention.DESIGN); profiles=list(settings['design']['applications'])
    files={choice['directory']:{} for choice in choices.values()}
    def put(directory,name,value):
        files[directory][name]=retention.encoded(value)
    def seal(directory,prefix,role,identity,documents):
        for name,value in documents.items():put(directory,prefix+name,value)
        value=dict(version='v3-comparison-roles-v1',role=role,identity=identity,
            files={name:sha256(files[directory][prefix+name]).hexdigest() for name in documents})
        put(directory,prefix+'seal.json',value)
        return sha256(files[directory][prefix+'seal.json']).hexdigest()
    def reads(prefix,names):
        return dict(blocked=[],actual_data_reads=['/artificial/'+prefix+'/'+n for n in names])
    expected={'recursive_native_name':{'inclusive':.576,'conditional_local':.8},
        'cross_trace_call_order':{'inclusive':1.,'conditional_local':1.},
        'database_propagated':{'inclusive':.576,'conditional_local':.8},
        'shared_database_two_callers':{'inclusive':.59049,'conditional_local':.81}}
    for index,profile in enumerate(profiles,1):
        controls=[]
        for name,variants in expected.items():
            for variant,value in variants.items():
                mid='controls--'+name+'--'+variant
                prediction=.7 if defect=='oracle' and mid=='controls--recursive_native_name--conditional_local' else value
                records=[dict(model_id=mid,repetition=rep,status='solved',success_probability=prediction,
                    failure_probability_sum=1-prediction,physical_state_probability=1.,total_physical_states=1,evaluated_physical_states=1) for rep in (0,1)]
                controls.append(dict(model_id=mid,expected=value,qualified=True,results=records))
        put(f'pmx-{index:02d}','controls.json',dict(qualified=True,expected_two_pass_oracle_records=16,controls=controls))
    for case in cases:
        identity=case['identity']; base=case['local_case']; ops=settings['design']['applications'][identity['application']]
        acquisition=dict(identity=identity,campaign_id='/'.join(str(identity[k]) for k in ('namespace','application','placement','law','repetition')),
            graph_input_seal_sha256='1'*64,pmx_input_seal_sha256='2'*64,evaluator_seal_sha256='3'*64,acquisition_head=HEAD,acquisition_run=str(RUN))
        put(base+'/receipt','receipt.json',acquisition);put(base+'/receipt','costs.json',{})
        graph_forecasts={op:{m:dict(status='ok',probability=1.) for m in settings['methods'][:-2]} for op in ops}
        graph_candidate=dict(version='v3-comparison-candidates-v1',identity=identity,forecasts=graph_forecasts,input_seal_sha256='1'*64,builder_head=HEAD)
        graph_hash='4'*64
        graph_audit=reads('workflow-input/ordinary',('native.json','requests.json','probes.json','declarations.json','manifest.json','seal.json'))
        if defect=='read' and case==cases[-1]:graph_audit['actual_data_reads'][0]='/artificial/workflow-input/evaluator/native.json'
        put(base+'/graph-compact','results.json',dict(identity=identity,candidate_seal_sha256=graph_hash,forecasts=graph_forecasts,read_audit=graph_audit))
        put(base+'/graph-compact','replay.json',dict(candidate_seal_sha256=graph_hash,result=dict(exact=not(defect=='replay' and case==cases[-1])),
            read_audit=reads('workflow-results/graph/candidates',('candidates.json','models.json','costs.json','read-audit.json','seal.json'))))
        pmx_candidate=dict(version='v3-independent-pmx-comparison-v2',identity=identity,forecasts={op:{m:dict(status='ok',probability=1.) for m in ('PMX','PMX_inclusive')} for op in ops},
            builder_head=HEAD,input_seal_sha256='2'*64)
        pmx_audit=reads('workflow-input/pmx-native',('native.json','requests.json','manifest.json','seal.json'))
        pmx_audit['health_or_our_model_or_evaluator_inputs']=0
        pmx_directory=f'pmx-{profiles.index(identity["application"])+1:02d}'
        pmx_hash=seal(pmx_directory,'campaign-'+audit.digest(identity)[:20]+'/', 'pmx_candidates',identity,
            {'candidates.json':pmx_candidate,'costs.json':{},'read-audit.json':pmx_audit})
        forecasts={op:dict(graph_forecasts[op],**pmx_candidate['forecasts'][op]) for op in ops}
        candidate=dict(identity=identity,forecasts=forecasts,evaluator_seal_sha256='3'*64,
            source_candidate_digests=dict(graph=audit.digest(graph_candidate),pmx=audit.digest(pmx_candidate)))
        receipt=dict(frozen_head=HEAD,workflow_run=str(RUN),workflow_attempt='1',evaluator_inputs_available_in_freeze_job=False,
            acquisition_receipt=acquisition,candidate_digest=audit.digest(candidate),builder_role_seal_sha256=dict(graph=graph_hash,pmx=pmx_hash))
        frozen_hash=seal(base+'/frozen','frozen/','frozen_candidates',identity,{'candidates.json':candidate,'costs.json':{},'receipt.json':receipt})
        evaluator_audit=reads('workflow-input/frozen/frozen',('candidates.json','costs.json','receipt.json','seal.json'))
        evaluator_audit['actual_data_reads']+=reads('workflow-input/evaluator',('requests.json','probes.json','manifest.json','seal.json'))['actual_data_reads']
        evaluator_audit.update(fitting_or_recalibration_performed=False,candidate_loaded_before_closed_role=True)
        view=dict(evaluator_status='qualified',operations={op:dict(attempts=3600//len(ops),forecasts=forecasts[op]) for op in ops})
        evaluator=dict(identity=identity,evaluation_head=HEAD,workflow_run=str(RUN),frozen_role_seal_sha256=frozen_hash,evaluator_role_seal_sha256='3'*64,
            read_audit=evaluator_audit,views=dict(all_sequence=view,stable=view))
        put(base+'/evaluation','evaluation.json',evaluator)
        put(base+'/evaluation','evaluation-seal.json',dict(identity=identity,files={'evaluation.json':sha256(files[base+'/evaluation']['evaluation.json']).hexdigest()},head=HEAD,run_id=str(RUN)))
    result=dict(head=HEAD,run_id=str(RUN),mode='main',data_role='prospective_main',main_campaigns=240,campaign_count=240,operation_cells_per_method=800,
        admission_candidate=True,candidate_evaluator_integrity=True,nonempty_primary_family=True,qualification_uses_forecast_error=False)
    put('analysis','comparison.json',result)
    put('analysis','comparison-seal.json',dict(files={'comparison.json':sha256(files['analysis']['comparison.json']).hexdigest()},head=HEAD,run_id=str(RUN),protocol_sha256=retention.DESIGN_SHA))
    records=[];artifacts=[]
    for ordinal,(name,choice) in enumerate(choices.items(),1):
        directory=choice['directory'];buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as archive:
            for member,data in files[directory].items():archive.writestr(member,data)
        raw=buf.getvalue();digest=sha256(raw).hexdigest()
        metadata=dict(id=ordinal,name=name,size_in_bytes=len(raw),digest='sha256:'+digest,expired=False)
        artifacts.append(metadata);records.append(dict(name=name,directory=directory,sha256=digest))
        retention.persist(root/directory/'compact.zip',raw)
        for member,data in files[directory].items():retention.persist(root/directory/'files'/member,data)
    jobs=[]
    for index in range(240):
        jobs.append(dict(id=index,name=f'freeze (artificial-{index})',conclusion='success',completed_at='2026-09-10T00:01:00Z'))
        jobs.append(dict(id=index+240,name=f'evaluate (artificial-{index})',conclusion='success',
            started_at='2026-09-10T00:00:00Z' if defect=='order' else '2026-09-10T00:02:00Z',
            steps=[dict(number=7,name='Require a complete frozen candidate role before downloading closed outcomes',conclusion='success',completed_at='2026-09-10T00:03:00Z'),
                dict(number=8,name='Run actions/download-artifact@v8',conclusion='success',started_at='2026-09-10T00:03:00Z')]))
    manifest=dict(run_id=RUN,head=HEAD,mode='main',protocol_sha256=retention.DESIGN_SHA,planned_campaigns=240,
        raw_native_ordinary_model_solver_payloads_downloaded=False,records=records,absent_artifacts=[])
    for name,value in [('verified-archives.json',manifest),('all-artifact-metadata.json',artifacts),('jobs-api.json',jobs),('planned-identities.json',cases)]:
        retention.persist(root/name,retention.encoded(value))


class CompactMainAuditTests(unittest.TestCase):
    def test_complete_artificial_compact_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            result=audit.audit(root,RUN,HEAD)
            self.assertTrue(result['qualified']);self.assertEqual(result['oracle_solver_records'],48)
            self.assertEqual(result['current_method_slots'],8000)
            self.assertFalse(result['fit_or_replay_executed_locally'])

    def test_authenticated_remote_reports_cannot_hide_role_replay_oracle_or_order_fault(self):
        for defect,reason in [('read','actual data read path differs'),('replay','graph replay not exact'),('order','evaluator started before all freezes completed')]:
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);fixture(root,defect)
                with self.assertRaisesRegex(ValueError,reason):audit.audit(root,RUN,HEAD)

    def test_local_member_or_run_substitution_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fixture(root)
            with self.assertRaisesRegex(ValueError,'evidence identity differs'):audit.audit(root,RUN+1,HEAD)
            (root/'analysis/files/comparison.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'retained extracted member differs'):audit.audit(root,RUN,HEAD)


if __name__=='__main__':unittest.main()
