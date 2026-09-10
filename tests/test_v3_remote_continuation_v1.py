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
import continue_v3_comparison_remote_v1 as runner
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


def empty_comparison():
    methods={m:dict(status='not_estimable',planned_cells=1,scored_cells=0,attempts=0,standardized_mean=None,
        forecast_status_counts={'unsupported':1},absence_reasons={'masked':1},per_operation={}) for m in tables.METHODS}
    census=[dict(campaign_id='artificial',operation='op',method=m,forecast={'status':'unsupported'},metrics=None)
            for m in tables.METHODS]
    contrasts=[dict(application='artificial',left='Gstar',right='G0',estimate_pp=None,interval_pp=None,status='not_estimable',
        common_cells=0,complete_common_campaigns=0,planned_cells=1,planned_conditions=1,retained_conditions=0,
        confidence_level=.9916666666666667,bootstrap_draws=10000,bootstrap_seed=771602+i,
        complete_support_is_conditioned_on_not_imputed=True,coverage_uncertainty_included=False,
        finite_sample_family_coverage_guaranteed=False) for i in range(6)]
    return dict(mode='preflight',run_id='1',head='a'*40,campaign_count=1,operation_cells_per_method=1,
        analysis=dict(method_slots=10,attempted_census=census,applications={'artificial':{'methods':methods}},
            primary_contrasts=contrasts,stable={'applications':{}},costs={'stage_summaries':[]},
            transfer=dict(census=[],point_forecasts=0,planned_slots=10,point_coverage=0)))


class PublicationTableTests(unittest.TestCase):
    def test_no_support_is_null_not_zero_and_census_is_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'input.json';source.write_text(json.dumps(empty_comparison()))
            result=tables.render(source,root/'tables')
            text=(root/'tables/README.md').read_text()
            self.assertEqual(result['planned_method_slots'],10)
            self.assertIn('not estimable',text)
            self.assertNotIn('superiority established',text)
            self.assertEqual(len((root/'tables/attempted-census.csv').read_text().splitlines()),11)
            # Reusing the exact source produces identical output bytes.
            self.assertEqual(result,tables.render(source,root/'tables'))

    def test_missing_duplicate_and_fabricated_metrics_are_rejected(self):
        for defect in ('missing','duplicate','metrics'):
            with self.subTest(defect=defect),tempfile.TemporaryDirectory() as d:
                report=empty_comparison()
                if defect=='missing':report['analysis']['attempted_census'].pop()
                elif defect=='duplicate':report['analysis']['attempted_census'][1]=report['analysis']['attempted_census'][0]
                else:report['analysis']['attempted_census'][0]['metrics']={'absolute_error_pp':0}
                source=Path(d)/'input.json';source.write_text(json.dumps(report))
                with self.assertRaises(ValueError):tables.render(source,Path(d)/'tables')


if __name__=='__main__':unittest.main()
