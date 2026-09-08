"""Verify compact retained evidence; never open full application/native archives."""
import hashlib
import json
from math import isfinite
from pathlib import Path
import zipfile

E=Path('docs/evidence')
def read(path): return json.loads(path.read_bytes())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def finite(value): return type(value) in (float,int) and isfinite(value)
def seal(root):
    for name,digest in read(root/'seal.json')['files'].items():
        assert sha(root/name)==digest,(root,name)


def main():
    roots=[E/('petclinic-technical-'+str(run)) for run in (34202539028,34204098497,34205318062)]
    roots.append(E/'petclinic-pmx-34206870187')
    archives=[]
    for root in roots:
        for api_path in root.glob('*/artifact-api.json'):
            info=read(api_path);archive_path=api_path.parent/'compact.zip'
            if api_path.parent.name=='solver-contract':
                retention=read(api_path.parent/'retention.json')
                assert sha(api_path.parent/'files/solver-contract.json')==retention['retained_metadata_sha256']
                continue
            assert archive_path.stat().st_size==info['size_in_bytes'] and 'sha256:'+sha(archive_path)==info['digest']
            with zipfile.ZipFile(archive_path) as archive:
                assert archive.testzip() is None
                members=[x for x in archive.infolist() if not x.is_dir()]
                for member in members: assert (api_path.parent/'files'/member.filename).read_bytes()==archive.read(member)
            archives.append(dict(id=info['id'],name=info['name'],size=info['size_in_bytes'],all_members_verified=len(members)))
    assert len(archives)==19
    acquisition=[]
    for root in roots[:2]:
        for path in root.glob('*/files/technical-summary.json'):
            row=read(path)
            if not row.get('usable'): continue
            assert all(row['checks'].values()) and row['main_campaigns']==0
            attempts=sum(x['attempts'] for x in row['operation_summary'])
            assert attempts==7440 and all(x==1 for x in row['baseline_success_fractions'].values())
            acquisition.append(dict(placement=row['placement'],failure_law=row['failure_law'],run=row['source_run'],
                attempts=attempts,calibration_health_ticks=row['calibration_health_ticks'],
                trace_linkage=row['successful_calibration_trace_fraction'],native_bytes=row['native_bytes'],
                native_parse_seconds=row['native_parse_seconds'],successful_replica_assignments=row['successful_replica_assignments']))
    assert len(acquisition)==8 and len({(x['placement'],x['failure_law']) for x in acquisition})==8
    fits=[];fit_rows=[]
    for path in roots[2].glob('*/files/fit'):
        seal(path);audit=read(path/'fit-read-audit.json')
        assert not audit['blocked'] and len(audit['read_paths'])==9
        assert audit['evaluator_reads']==audit['injection_schedule_reads']==audit['target_calibration_reads']==0
        rows=read(path/'predictions.json')['predictions'];fit_rows.extend(rows)
        fits.append(dict(artifact=path.parents[1].name,rows=len(rows),actual_data_reads=9,test_reads=0,schedule_reads=0,target_calibration_reads=0))
    assert len(fits)==8 and len(fit_rows)==576
    fit_coverage=[]
    for method in sorted({x['method'] for x in fit_rows}):
        for scope in ('current','transfer'):
            rows=[x for x in fit_rows if x['method']==method and x['scope']==scope]
            fit_coverage.append(dict(method=method,scope=scope,slots=len(rows),finite_forecasts=sum(finite(x['prediction']) for x in rows)))
    assert sum(finite(x['prediction']) for x in fit_rows)==560
    pmx=roots[3]/'candidates/files';seal(pmx)
    controls=read(pmx/'controls.json')
    assert controls['qualified'] and controls['expected_software_oracle_passes']==8
    solver_passes=0
    def verify_pair(rows, expected=None):
        assert len(rows)==2 and {x['repetition'] for x in rows}=={0,1}
        for row in rows:
            assert row['status']=='solved' and finite(row['success_probability']) and 0<=row['success_probability']<=1
            assert abs(row['physical_state_probability']-1)<1e-12
            assert row['evaluated_physical_states']==row['total_physical_states']
            assert abs(row['failure_probability_sum']+row['success_probability']-1)<1e-12
            if expected is not None: assert abs(row['success_probability']-expected)<1e-12
        assert abs(rows[0]['success_probability']-rows[1]['success_probability'])<1e-12
    for control in controls['controls']: verify_pair(control['results'],control['expected']);solver_passes+=2
    assert solver_passes==8
    coverage=read(pmx/'coverage.json')
    assert len(coverage)==64 and all(x['valid'] for x in coverage)
    for row in coverage: verify_pair(row['solver_records'])
    predictions=read(pmx/'predictions.json')['predictions']
    assert len(predictions)==64 and all(finite(x['prediction']) for x in predictions)
    report=dict(scope='technical_preparation_only',main_campaigns=0,
        verified_compact_archives=archives,acquisition=sorted(acquisition,key=lambda x:(x['placement'],x['failure_law'])),
        usable_attempts=sum(x['attempts'] for x in acquisition),failed_startup_attempts_not_independent_n=1,
        historical_M7_fits=fits,historical_M7_coverage=fit_coverage,
        pmx=dict(run=34206870187,head_sha=read(pmx/'seal.json')['metadata']['head_sha'],
            software_oracle_passes=solver_passes,application_solver_passes=128,independent_forecasts=64,
            coverage_by_variant={method:sum(x['method']==method for x in predictions) for method in ('PMX_inclusive','PMX_conditional_local')},
            evaluator_downloads_before_seal=read(pmx/'seal.json')['metadata']['evaluator_downloads_before_candidate_freeze']),
        graph_main_method_applications=0,accuracy_comparison='not performed in this report')
    (roots[3]/'preparation-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(archives=len(archives),usable_attempts=report['usable_attempts'],M7_finite=560,M7_absent=16,PMX_finite=64,control_passes=8,main_campaigns=0)))


if __name__=='__main__': main()
