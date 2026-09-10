from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import recover_v3_main_transport_v1 as recovery
from telemetry_availability.v3_comparison_candidates_v1 import GRAPH_METHODS, combine
from telemetry_availability.v3_comparison_roles_v1 import digest


def fixture():
    _,cases=recovery.transport.selections(recovery.RUN,'main')
    identity=cases[0]['identity']; ops=['artificial_operation']
    receipt=dict(identity=identity,graph_input_seal_sha256='a'*64,pmx_input_seal_sha256='b'*64,
                 evaluator_seal_sha256='c'*64)
    graph=dict(version='v3-comparison-candidates-v1',identity=identity,
        forecasts={ops[0]:{m:dict(status='ok',probability=.75,reason=None) for m in GRAPH_METHODS}},
        input_seal_sha256='a'*64,builder_head=recovery.HEAD)
    candidate=combine(identity,ops,graph,None,receipt,{'pmx':'pmx_candidate_role_unavailable'})
    original={'candidates.json':candidate,'receipt.json':dict(identity=identity,
        acquisition_receipt=receipt,candidate_digest=digest(candidate),workflow_run=str(recovery.RUN),frozen_head=recovery.HEAD)}
    pmx=dict(identity=identity,input_seal_sha256='b'*64,
             forecasts={ops[0]:{m:dict(status='ok',probability=.625,reason=None) for m in ('PMX','PMX_inclusive')}})
    return identity,ops,original,pmx


class TransportRecoveryControls(unittest.TestCase):
    def test_exact_names_reach_beyond_first_1000_without_outcome_roles(self):
        names=recovery.original_names(recovery.PROFILES[0],'pmx-inputs')
        first=[f'artificial-unrelated-{i}' for i in range(1000)]
        metadata=[{'name':name} for name in first+sorted(names)]
        self.assertEqual([r for r in metadata[:1000] if r['name'] in names],[])
        self.assertEqual(len([r for r in metadata if r['name'] in names]),81)
        self.assertTrue(all('pmx-extraction-' in name for name in names))
        self.assertFalse(any('evaluation' in name or 'closed-evaluator' in name for name in names))

    def test_non_pmx_forecasts_preserved_and_modified_graph_digest_rejected(self):
        identity,ops,original,pmx=fixture(); before=deepcopy(original)
        new=recovery.merge_frozen(original,pmx,identity,ops)
        self.assertEqual(original,before)
        for method in GRAPH_METHODS:
            self.assertEqual(new['forecasts'][ops[0]][method],before['candidates.json']['forecasts'][ops[0]][method])
        self.assertEqual(new['forecasts'][ops[0]]['PMX']['probability'],.625)
        original['candidates.json']['forecasts'][ops[0]]['Gstar']['probability']=.1
        original['receipt.json']['candidate_digest']=digest(original['candidates.json'])
        with self.assertRaisesRegex(ValueError,'graph candidate changed'):
            recovery.merge_frozen(original,pmx,identity,ops)

    def test_cross_campaign_pmx_source_rejected(self):
        identity,ops,original,pmx=fixture();pmx['input_seal_sha256']='f'*64
        with self.assertRaisesRegex(ValueError,'another campaign/input'):
            recovery.merge_frozen(original,pmx,identity,ops)

    def test_both_original_count_views_are_unchanged_and_read_audit_is_scoped(self):
        identity,ops,original,pmx=fixture()
        frozen=recovery.merge_frozen(original,pmx,identity,ops)
        report=dict(identity=identity,workflow_run=str(recovery.RUN),frozen_role_seal_sha256='old',
            read_audit={'artificial_original_audit':True},views={})
        for view,n,s in [('all_sequence',11,7),('stable',5,2)]:
            report['views'][view]=dict(evaluator_status='qualified',operations={ops[0]:dict(attempts=n,
                successes=s,timeouts=1,forecasts=original['candidates.json']['forecasts'][ops[0]])})
        before=deepcopy(report)
        result=recovery.rescore_report(report,frozen,'old','new',999)
        self.assertEqual(report,before)
        for view in ('all_sequence','stable'):
            for field in ('attempts','successes','timeouts'):
                self.assertEqual(result['views'][view]['operations'][ops[0]][field],
                                 before['views'][view]['operations'][ops[0]][field])
        self.assertEqual(result['read_audit'],report['read_audit'])
        self.assertIn('original evaluator',result['read_audit_scope'])
        with self.assertRaisesRegex(ValueError,'association differs'):
            recovery.rescore_report(report,frozen,'wrong','new',999)

    def test_compact_transport_rejects_unlisted_native_member_before_extraction(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr('evaluation.json','{}');archive.writestr('native.json','{}')
        raw=buffer.getvalue()
        item=dict(id=1,size_in_bytes=len(raw),expired=False,digest='sha256:'+sha256(raw).hexdigest())
        with tempfile.TemporaryDirectory() as directory,patch.object(recovery.transport,'api',return_value=raw):
            target=Path(directory)/'input'
            with self.assertRaisesRegex(ValueError,'unlisted'):
                recovery.download(item,target,allowed={'evaluation.json'})
            self.assertFalse((target/'files').exists())

    def test_local_real_recovery_rejected_before_api_or_source_access(self):
        with patch.dict('os.environ',{},clear=True),patch.object(recovery.transport,'read_api') as api:
            with self.assertRaisesRegex(ValueError,'remote recovery'):
                recovery.remote_guard()
            api.assert_not_called()


if __name__=='__main__':
    unittest.main()
