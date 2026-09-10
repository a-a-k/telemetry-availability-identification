"""Audit matched repair qualification without reading business test outcomes."""
from hashlib import sha256
import json
import os
from pathlib import Path

from diagnose_v3_pmx_timeout_v1 import write


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    inputs=Path('workflow-input/qualification')
    extracts=[json.loads(p.read_bytes()) for p in inputs.rglob('compact.json')]
    assert len(extracts)==7 and len({e['key'] for e in extracts})==7
    assert all(e['extraction_qualified'] and e['unaffected_semantics_unchanged'] for e in extracts)
    assert all(e['numeric_controls']['qualified'] and e['numeric_controls']['controls']==5 for e in extracts)
    jars={e['build']['derived_jar_sha256'] for e in extracts};assert len(jars)==1
    assert all(e['diagnostic_run']==os.environ['GITHUB_RUN_ID'] and e['diagnostic_head']==os.environ['GITHUB_SHA'] for e in extracts)
    original=Path('docs/evidence/v3-comparison-preflight-34447262633')
    old={}
    for path in original.glob('pmx-*/files/campaign-*/candidates.json'):
        row=json.loads(path.read_bytes());old[row['identity']['application'],row['identity']['placement']]=row
    assert len(old)==6
    controls=[json.loads(p.read_bytes()) for p in inputs.rglob('controls.json')]
    assert len(controls)==3 and all(c['qualified'] for c in controls)
    solver_oracles=sum(len(c['controls']) for c in controls)
    solver_oracle_records=sum(len(r['results']) for c in controls for r in c['controls'])
    assert solver_oracles==24 and solver_oracle_records==48
    candidates=[json.loads(p.read_bytes()) for p in inputs.rglob('candidates.json')]
    assert len(candidates)==6
    checks=[];seen=set()
    for current in candidates:
        identity=current['identity'];key=identity['application'],identity['placement']
        assert key not in seen;seen.add(key)
        prior=old[key];assert identity==prior['identity']
        assert current['forecasts'].keys()==prior['forecasts'].keys()
        for operation,methods in current['forecasts'].items():
            assert set(methods)=={'PMX','PMX_inclusive'}
            for method,result in methods.items():
                previous=prior['forecasts'][operation][method]
                check=dict(application=key[0],placement=key[1],operation=operation,method=method,
                    original_status=previous['status'],new_status=result['status'],
                    original_probability=previous['probability'],new_probability=result['probability'])
                if previous['status']=='ok':
                    assert result['status']=='ok'
                    check['absolute_probability_delta']=abs(result['probability']-previous['probability'])
                    assert check['absolute_probability_delta']<=1e-12
                elif previous['status']=='unsupported':
                    assert result['status']=='unsupported' and result['probability'] is None
                    assert result['reason']==previous['reason']
                else:
                    assert previous['status']=='failed'
                    assert key==('deathstarbench_social_network','split') and operation=='read_user_timeline'
                    assert result['status']=='ok'
                checks.append(check)
    assert len(checks)==40
    assert sum(r['original_status']=='ok' for r in checks)==32
    assert sum(r['original_status']=='unsupported' for r in checks)==6
    assert sum(r['original_status']=='failed' for r in checks)==2
    appcases=[c for e in extracts if e['key']!='controls' for c in e['cases']]
    assert len(appcases)==20 and sum(c['original_qualified'] for c in appcases)==19
    result=dict(version='pmx-clock-progress-qualification-audit-v1',qualified=True,
        run_id=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
        derived_jar_sha256=next(iter(jars)),application_projection_cases=20,
        preserved_original_complete_projection_cases=19,recovered_projection_cases=1,
        original_point_forecasts_unchanged=32,unsupported_forecasts_preserved=6,recovered_forecast_slots=2,
        known_solver_oracle_records=solver_oracle_records,compiled_java_controls_per_builder=5,
        reproducible_jar_builds=7,forecast_checks=checks,
        evidence_sha256={p.relative_to(inputs).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(inputs.rglob('*.json'))},
        no_test_outcomes_read=True,new_independent_campaigns=0,main_admission=False,
        next_required='Separate versioned full fresh preflight, then strict admission before independent main')
    write(Path('workflow-results/clock-qualification-audit/compact.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('forecast_checks','evidence_sha256')}))


if __name__=='__main__':main()
