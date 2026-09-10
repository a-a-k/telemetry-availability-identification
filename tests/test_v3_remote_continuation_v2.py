"""Artificial admission, duplicate-dispatch and missing-result boundary controls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import continue_v3_comparison_remote_v2 as runner
import render_v3_comparison_tables_v1 as tables


def run_record(run_id,head,path,event='workflow_dispatch'):
    return dict(id=run_id,head_sha=head,path=path,event=event,run_attempt=1,
                head_repository=dict(full_name=runner.REPO),status='completed',conclusion='success')


def qualified():
    a=dict(qualified=True,run_id=runner.PREFLIGHT_RUN,head=runner.PREFLIGHT_HEAD,
        protocol_sha256=runner.retention.DESIGN_SHA,campaigns=6,operation_cells_per_method=20,
        current_method_slots=200,oracle_solver_records=48,qualification_uses_forecast_error=False,
        evidence_manifest_sha256='b'*64,comparison_sha256='c'*64)
    p=run_record(runner.PREFLIGHT_RUN,runner.PREFLIGHT_HEAD,runner.WORKFLOW)
    ci=run_record(runner.PREFLIGHT_CI,runner.PREFLIGHT_HEAD,'.github/workflows/ci.yml','push')
    return a,p,ci


class AdmissionTests(unittest.TestCase):
    def test_all_gates_and_unfavourable_source_provenance_fail_closed(self):
        a,p,c=qualified()
        with patch.object(runner,'sha',return_value='d'*64):
            result=runner.admission_record(a,p,c,'e'*64)
            self.assertTrue(result['full_preflight_qualified'])
            self.assertEqual(result['main_seed'],771601)
            self.assertEqual(result['repository_lock_count'],356)
            self.assertEqual(result['execution_lock_path'],'configs/v3_comparison_execution_v3.json')
            self.assertEqual(result['preflight_run_id'],34460574221)
            for which,key,bad in [('audit','qualified',False),('audit','qualification_uses_forecast_error',True),
                ('audit','current_method_slots',199),('audit','oracle_solver_records',47),
                ('audit','protocol_sha256','f'*64),('preflight','conclusion','failure'),
                ('preflight','run_attempt',2),('preflight','head_sha','0'*40),
                ('preflight','head_repository',{'full_name':'foreign/repo'}),
                ('ci','conclusion','failure'),('ci','head_sha','1'*40),('ci','event','pull_request')]:
                with self.subTest(which=which,key=key):
                    aa,pp,cc=copy.deepcopy((a,p,c))
                    {'audit':aa,'preflight':pp,'ci':cc}[which][key]=bad
                    with self.assertRaises(ValueError):runner.admission_record(aa,pp,cc,'e'*64)

    def test_existing_dispatch_is_reused_without_a_write(self):
        record=run_record(999,'a'*40,runner.WORKFLOW)
        with patch.object(runner,'runs_at',return_value=[record]),patch.object(runner.subprocess,'run') as write:
            self.assertEqual(runner.ensure_dispatch(Path(runner.WORKFLOW).name,runner.MAIN_TAG,'a'*40)['id'],999)
            write.assert_not_called()

    def test_multiple_or_uncertain_dispatch_never_retries_mutation(self):
        with patch.object(runner,'runs_at',return_value=[{},{}]),patch.object(runner.subprocess,'run') as write:
            with self.assertRaises(ValueError):runner.ensure_dispatch('ci.yml',runner.MAIN_TAG,'a'*40)
            write.assert_not_called()
        failure=subprocess.CalledProcessError(1,['gh','workflow','run'])
        with patch.object(runner,'runs_at',return_value=[]),patch.object(runner.subprocess,'run',side_effect=failure) as write:
            with self.assertRaises(subprocess.CalledProcessError):runner.ensure_dispatch('ci.yml',runner.MAIN_TAG,'a'*40)
            self.assertEqual(write.call_count,1)

    def test_failed_compact_audit_cannot_reach_admission_or_dispatch(self):
        _,source,_=qualified()
        with patch.object(runner,'api',return_value=source),patch.object(runner.subprocess,'run'),\
             patch.object(runner.admission_audit,'audit',side_effect=ValueError('candidate seal differs')),\
             patch.object(runner,'commit_paths') as commit,patch.object(runner,'ensure_dispatch') as dispatch:
            with self.assertRaises(ValueError):runner.preflight()
            commit.assert_not_called();dispatch.assert_not_called()

    def test_unrelated_completed_run_is_not_collected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'dispatch.json';path.write_text(json.dumps(dict(run_id=123)))
            with patch.object(runner,'DISPATCH',path),patch.object(runner,'api') as read:
                runner.collect_main(456)
                read.assert_not_called()



if __name__=='__main__':unittest.main()
