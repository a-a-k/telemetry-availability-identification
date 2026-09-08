import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

from telemetry_availability.isolated_stochastic_fit import (LEARNER_FILES, ReadAudit,
    health_signal, verify_learner_bundle, load_analysis)
from telemetry_availability.live_validation_analysis import _health_signal


class IsolatedOriginalModelTest(unittest.TestCase):
    def test_http_health_and_failed_or_paused_path(self):
        row={'replica_a_observed':'true','replica_a_running':'true','replica_a_paused':'false',
             'replica_a_network_count':'3','replica_a_backend_status':'UP','replica_a_backend_check_status':'L7OK'}
        self.assertEqual(health_signal(row,'a',['L7OK']),(1,1))
        for change in ({'replica_a_paused':'true'},{'replica_a_backend_status':'DOWN'},
                       {'replica_a_backend_check_status':'L7TOUT'}):
            self.assertEqual(health_signal(row|change,'a',['L7OK'])[1],0)
        with self.assertRaises(ValueError):
            health_signal(row,'a',['','L4OK'])
        self.assertEqual(row['replica_a_backend_check_status'],'L7OK')

    def test_legacy_tcp_decoding_is_preserved(self):
        for running in ('true','false'):
            for paused in ('true','false'):
                for backend,check in [('UP','L4OK'),('DOWN','L4CON'),('UP','')]:
                    row={'replica_a_observed':'true','replica_a_running':running,'replica_a_paused':paused,
                         'replica_a_network_count':'1','replica_a_backend_status':backend,'replica_a_backend_check_status':check}
                    self.assertEqual(health_signal(row,'a',['','L4OK']),_health_signal(row,'a'))

    def test_seal_rejects_unexpected_evaluator_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in LEARNER_FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'{}')
            (root/'seal.json').write_text(json.dumps(dict(metadata={},files={n:hashlib.sha256(b'{}').hexdigest() for n in LEARNER_FILES})))
            verify_learner_bundle(root)
            (root/'test-requests.csv').write_text('never-read')
            with self.assertRaisesRegex(ValueError,'unexpected'):
                verify_learner_bundle(root)

    def test_real_open_hook_blocks_evaluator_and_generation_parameters(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp);learner=parent/'learner-bundle';learner.mkdir()
            settings=parent/'analysis.json';settings.write_text('{}')
            evaluator=parent/'evaluator'/'test-requests.csv';evaluator.parent.mkdir();evaluator.write_text('secret test outcomes')
            generation=parent/'renewal-schedule.json';generation.write_text('secret generating process')
            audit=ReadAudit(learner,settings,parent/'out')
            sys.addaudithook(audit)
            try:
                self.assertEqual(settings.read_text(),'{}')
                for path in (evaluator,generation):
                    with self.assertRaises(PermissionError):
                        path.read_text()
                with self.assertRaises(PermissionError):
                    audit('socket.connect',())
            finally:
                audit.active=False
            self.assertEqual(len(audit.blocked),3)

    def test_analysis_has_ten_operations_and_only_original_methods(self):
        root=Path(__file__).resolve().parents[1]
        analysis=load_analysis(root/'configs/isolated_stochastic_analysis.json')
        self.assertEqual(sum(map(len,analysis.operations.values())),10)
        self.assertEqual(analysis.methods,('B0','B1','B2','B3','proposed','B4'))
        self.assertEqual(analysis.optimizer_starts,8)
        self.assertEqual(analysis.source_placement,'colocated')


if __name__=='__main__':
    unittest.main()
