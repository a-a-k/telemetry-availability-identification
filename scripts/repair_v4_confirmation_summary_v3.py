"""Reaggregate saved compact results; no traffic, fitting or solver execution."""
import os
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from run_v4_missingness_v2 import fetch
from v4_confirmed_source_v3 import require_source,SOURCE_RUN,SOURCE_HEAD
import v4_confirmation_summary_v3 as summary
from telemetry_availability.v4_confirmation_orchestration_v2 import verify_new_locks
from telemetry_availability.v3_primary_projection import write,sha


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_RUN_ATTEMPT')!='1':raise ValueError('original remote aggregate execution required')
    verify_new_locks();source_status=require_source()
    config=Path('configs/v4_confirmation_design_v1.json');_,_,cases=summary.planned_cases(config,'main')
    artifacts=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/artifacts','artifacts')
    root=Path('workflow-input/summary-source');out=Path('workflow-results/summary');sources=[]
    for case in cases:
        key=case['key'];row=dict(identity=case['identity'])
        for role,relative,allowed in [
            ('frozen','frozen',{'gate.json','frozen/candidates.json','frozen/receipt.json','frozen/costs.json','frozen/seal.json'}),
            ('evaluation','evaluations',{'evaluation.json','evaluation-seal.json'}),
            ('primary-compact','primary',{'compact.json'})]:
            row[role]=fetch(artifacts,f'v4-confirmation-{role}-{key}-{SOURCE_RUN}',allowed,root/relative/key)
        sources.append(row)
    summary.install();summary.summarize(root,out,config,cases)
    write(out/'aggregation-provenance.json',dict(source_status=source_status,sources=sources,
        source_run=SOURCE_RUN,source_head=SOURCE_HEAD,analysis_run=os.environ['GITHUB_RUN_ID'],analysis_head=os.environ['GITHUB_SHA'],
        changed_numeric_forecasts=False,new_observations=False,model_execution=False,
        change='unplanned placement transfer returns not_planned; original forecast and primary summary arithmetic',
        summary_source_sha256=sha(Path('scripts/v4_confirmation_summary_v3.py'))))


if __name__=='__main__':main()
