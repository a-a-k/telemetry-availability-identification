"""Run the unchanged fair v2 workers on every newly saved calibration model."""
import json
import os
from pathlib import Path
import tempfile

import benchmark_v3_exact_comparison_v2 as fixed
import retain_v3_comparison_compact_v4 as transport
from run_v4_missingness_v2 import fetch,SOURCE_RUN,SOURCE_HEAD
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases
from telemetry_availability.v3_comparison_roles_v1 import load_role,campaign_id
from telemetry_availability.v3_comparison_candidates_v1 import replay
from telemetry_availability.v3_primary_projection import read,sha

CONFIG=Path('configs/v4_confirmed_performance_v2.json')


def prepare(profile,config):
    run=transport.read_api(f'actions/runs/{SOURCE_RUN}')
    if (run['head_sha']!=SOURCE_HEAD or run['path']!='.github/workflows/v4-confirmation-v2.yml'
        or run['run_attempt']!=1 or run['status']!='completed' or run['conclusion']!='success'):
        raise ValueError('new independent source series is incomplete')
    _,_,cases=planned_cases(Path('configs/v4_confirmation_design_v1.json'),'main')
    cases=[c for c in cases if c['profile']==profile]
    artifacts=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/artifacts','artifacts')
    allowed={'candidates/candidates.json','candidates/models.json','candidates/costs.json',
        'candidates/read-audit.json','candidates/seal.json','compact/results.json','compact/replay.json',
        'compact/resource-summary.json','compact/build-resource-usage.txt','compact/replay-resource-usage.txt'}
    selected=[];absent=[];provenance=[]
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='confirmed-model-cost-') as directory:
            root=Path(directory)
            metadata=fetch(artifacts,f"v4-confirmation-graph-{case['key']}-{SOURCE_RUN}",allowed,root)
            data,_=load_role(root/'candidates','graph_candidates',case['identity'])
            models=data['models.json'];forecasts=data['candidates.json']['forecasts']
            replay(forecasts,models)
            provenance.append(dict(identity=case['identity'],artifact=metadata,role_seal_sha256=sha(root/'candidates/seal.json')))
            for operation,values in forecasts.items():
                ident=dict(case['identity'],operation=operation);cid=campaign_id(case['identity'])+'/'+operation
                if operation not in models['execution']:
                    if values['Gstar']['status']!='unsupported':raise ValueError('technical failure cannot be silently omitted')
                    absent.append(dict(case_id=cid,identity=ident,reason=values['Gstar']['reason']));continue
                selected.append(dict(case_id=cid,model=models['execution'][operation],axis='application',
                    parameters=ident,identity=ident))
    expected=config['planned_operation_cases'][profile]
    if len(selected)+len(absent)!=expected:raise ValueError('new complete calibration model census differs')
    selected.sort(key=lambda r:r['case_id'])
    return selected,absent,dict(run_id=SOURCE_RUN,head=SOURCE_HEAD,artifacts=provenance,
        all_supported_models_included=True,selection_uses_performance=False,planned_operation_cases=expected)


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('native benchmarks are remote only')
    config=read(CONFIG)
    for name,expected in config['new_source_locks'].items():
        if sha(Path(name))!=expected:raise ValueError('fixed comparison implementation changed: '+name)
    original=read(fixed.CONFIG)
    for key in ('methods','representations','phases','technical_rounds','stream_timeout_seconds',
        'address_space_limit_bytes','agrum_inference_memory_gib','threads'):
        if config[key]!=original[key]:raise ValueError('unchanged worker settings differ')
    # Only the parent source selector/configuration changes. The subprocess
    # command in fixed.run still executes the exact original v2 worker file;
    # every timing boundary, lifecycle update and verification order is intact.
    fixed.CONFIG=CONFIG.resolve();fixed.source_v1.prepare=prepare
    fixed.main()


if __name__=='__main__':main()
