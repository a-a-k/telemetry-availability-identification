"""Compact-only confirmation retention and independent temporal-gate audit."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.v3_comparison_roles_v1 import digest

RUN=34703686592
HEAD='12ddb09369ee6e0b60ca4c7db6fe1e749530b7df'


def instant(value):return datetime.fromisoformat(value.replace('Z','+00:00'))


def main():
    run=transport.read_api(f'actions/runs/{RUN}')
    if (run['head_sha']!=HEAD or run['path']!='.github/workflows/v4-confirmation-v2.yml'
        or run['status']!='completed' or run['run_attempt']!=1):raise ValueError('wrong or nonterminal fixed series')
    artifacts=transport.collect_pages(f'actions/runs/{RUN}/artifacts','artifacts')
    jobs=transport.collect_pages(f'actions/runs/{RUN}/jobs','jobs')
    by_name={a['name']:a for a in artifacts}
    if len(by_name)!=len(artifacts):raise ValueError('duplicate artifact names')
    transport.DESIGN=Path('configs/v4_confirmation_design_v1.json')
    transport.DESIGN_SHA=sha256(transport.DESIGN.read_bytes()).hexdigest()
    original,cases=transport.selections(RUN,'main')
    selected={n.replace('v3-comparison-','v4-confirmation-'):s for n,s in original.items()}
    for name,s in selected.items():
        if '-frozen-' in name:s['allowed'].add('gate.json')
        if name==f'v4-confirmation-compact-{RUN}':s['allowed'].update(('confirmation.json','confirmation-seal.json'))
    for case in cases:
        selected[f"v4-confirmation-primary-compact-{case['artifact_key']}-{RUN}"]=dict(
            directory=case['local_case']+'/primary',allowed={'compact.json'})
        selected[f"v4-confirmation-pmx-build-{case['artifact_key']}-{RUN}"]=dict(
            directory=case['local_case']+'/pmx-build',allowed={'build-provenance.json','build-resource-usage.txt'})
    out=Path(f'docs/evidence/v4-confirmation-v2-{RUN}')
    transport.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    transport.persist(out/'run-api.json',transport.encoded(run));transport.persist(out/'jobs-api.json',transport.encoded(jobs))
    transport.persist(out/'all-artifact-metadata.json',transport.encoded(artifacts))
    found=[];absent=[]
    for name,spec in selected.items():
        if name not in by_name:absent.append(name);continue
        a=by_name[name]
        if a['workflow_run']['id']!=RUN or a['workflow_run']['head_sha']!=HEAD:raise ValueError('provider artifact identity differs')
        files=transport.check_archive(transport.api(f"actions/artifacts/{a['id']}/zip"),a,spec['allowed'])
        for member,content in files.items():transport.persist(out/spec['directory']/member,content)
        found.append(dict(name=name,directory=spec['directory'],artifact_id=a['id'],digest=a['digest'],bytes=a['size_in_bytes'],members=sorted(files)))
    groups={phase:[j for j in jobs if j['name'].startswith(phase+' (')] for phase in ('freeze','bounds','evaluate','primary')}
    complete=all(len(js)==18 and all(j['conclusion']=='success'for j in js) for js in groups.values())
    temporal={}
    if complete:
        latest_freeze=max(instant(j['completed_at'])for j in groups['freeze'])
        earliest_bounds=min(instant(j['started_at'])for j in groups['bounds'])
        latest_bounds=max(instant(j['completed_at'])for j in groups['bounds'])
        earliest_outcomes=min(instant(j['started_at'])for j in groups['primary']+groups['evaluate'])
        if latest_freeze>earliest_bounds or latest_bounds>earliest_outcomes:raise ValueError('provider job chronology violates the global barriers')
        temporal=dict(all_18_freezes_finished_at=latest_freeze.isoformat(),first_bounds_job_started_at=earliest_bounds.isoformat(),
            all_18_bounds_finished_at=latest_bounds.isoformat(),first_outcome_job_started_at=earliest_outcomes.isoformat(),
            every_numeric_forecast_precedes_outcome_opening=True,every_realized_bound_precedes_outcome_opening=True)
        for case in cases:
            root=out/case['local_case']/'frozen';gate=json.loads((root/'gate.json').read_bytes())
            seal=json.loads((root/'frozen/seal.json').read_bytes());candidate=json.loads((root/'frozen/candidates.json').read_bytes())
            if (gate['candidate_digest']!=digest(candidate) or gate['frozen_seal_sha256']!=sha256((root/'frozen/seal.json').read_bytes()).hexdigest()
                or gate['all_numerical_forecasts_fixed'] is not True or candidate['failures']
                or any(sha256((root/'frozen'/name).read_bytes()).hexdigest()!=h for name,h in seal['files'].items())):
                raise ValueError('retained strict forecast gate differs')
    receipt=dict(run=RUN,head=HEAD,conclusion=run['conclusion'],artifacts=found,absent_artifacts=absent,
        all_primary_and_freeze_jobs_complete=complete,temporal_gate_audit=temporal,
        full_raw_models_and_closed_roles_downloaded_locally=False,local_model_execution=False)
    transport.persist(out/'retention.json',transport.encoded(receipt))
    print(json.dumps(dict(run=RUN,retained=len(found),absent=len(absent),all_primary_and_freeze_jobs_complete=complete,temporal_gate_audit=temporal)))


if __name__=='__main__':main()
