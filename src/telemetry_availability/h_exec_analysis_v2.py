"""Frozen H-EXEC technical gate and paired prospective compact analysis."""
import argparse
from fractions import Fraction
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

import numpy as np

from .h_exec_live_v2 import CONFIG, settings
from .h_exec_design_v1 import ARMS, exact_paired_test
from .v3_primary_projection import read, write, sha


def api(path):
    return subprocess.check_output(['gh','api','repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path])


def prerequisite(run_id):
    run=json.loads(api(f'actions/runs/{run_id}'))
    assert run['conclusion']=='success' and run['path']=='.github/workflows/h-exec-01-v2.yml'
    artifacts=json.loads(api(f'actions/runs/{run_id}/artifacts'))['artifacts']
    selected=[a for a in artifacts if a['name']==f'h-exec-qualification-{run_id}']
    assert len(selected)==1
    item=selected[0];assert not item['expired'] and item['size_in_bytes']<100000
    data=api(f'actions/artifacts/{item["id"]}/zip')
    assert len(data)==item['size_in_bytes'] and 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist()==['qualification.json'] and archive.testzip() is None
        report=json.loads(archive.read('qualification.json'))
    assert report['qualified'] and report['phase']=='qualification' and report['head']==run['head_sha']
    assert report['protocol_sha256']==sha(CONFIG) and report['cells']==4
    return dict(run=run_id,head=run['head_sha'],artifact=item,protocol_sha256=report['protocol_sha256'])


def paired(differences,seed):
    exact=exact_paired_test(differences)
    values=np.asarray([float(d) for d in differences])
    rng=np.random.default_rng(seed)
    bootstrap=values[rng.integers(0,len(values),size=(10000,len(values)))].mean(axis=1)
    lower,upper=np.quantile(bootstrap,[.0125,.9875])
    return dict(**exact,bootstrap_replicates=10000,bootstrap_seed=seed,
        percentile_interval_level=.975,percentile_interval=[float(lower),float(upper)],
        bootstrap_finite_sample_coverage_guaranteed=False,
        predeclared_statistical_support=exact['mean']>=.05 and exact['two_sided_p']<=.025)


def collect(root,out,frozen,phase):
    expected=frozen['assignments'][phase]
    cells={}; records=[]
    for cell in expected:
        paths=list(root.glob(f'h-exec-compact-{phase}-b{cell["block"]}-s{cell["slot"]}-*'))
        if len(paths)!=1 or not (paths[0]/'summary.json').is_file():
            records.append(dict(**cell,available=False,qualified=False));continue
        summary=read(paths[0]/'summary.json');identity=summary['identity']
        assert all(identity[k]==cell[k] for k in ('block','slot','arm')) and identity['phase']==phase
        assert identity['source_head']==os.environ['GITHUB_SHA'] and identity['run_id']==os.environ['GITHUB_RUN_ID']
        assert (cell['block'],cell['arm']) not in cells
        cells[(cell['block'],cell['arm'])]=dict(summary=summary,controls=read(paths[0]/'static-controls.json'))
        records.append(dict(**cell,available=True,qualified=summary['qualified'],checks=summary['checks']))
    qualified=len(cells)==len(expected) and all(r['qualified'] for r in records)
    report=dict(phase=phase,head=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
        protocol_sha256=sha(CONFIG),cells=len(cells),expected_cells=len(expected),qualified=qualified,
        records=records,main_campaigns=0,pmx_invocations=0,model_fits=0)
    if phase=='qualification':
        write(out/'qualification.json',report)
        assert qualified,'all four technical arms are required; no incomplete gate or outcome-dependent replacement'
        return
    if len(cells)!=32:
        report['primary_status']='not_estimable_as_planned: incomplete 32-cell census'
        write(out/'study-analysis.json',report);return
    def success(block,arm,operation):
        rows=[r for r in cells[(block,arm)]['summary']['operation_summaries'] if r['period']=='test' and r['operation']==operation]
        assert len(rows)==1 and rows[0]['attempts']==40
        return Fraction(rows[0]['successes'],rows[0]['attempts'])
    contrasts={}
    for name,left,right in [('adverse_deficit','sham','settled'),('routing_repair','repaired','settled')]:
        differences=[success(block,left,'checkout')-success(block,right,'checkout') for block in range(8)]
        contrasts[name]=paired(differences,frozen['analysis_seed'])
        contrasts[name].update(left=left,right=right,differences_exact=[str(d) for d in differences],
            planned_design_qualified=qualified,confirmed_within_design=qualified and contrasts[name]['predeclared_statistical_support'])
    secondary=[]
    for operation in ('browse_product','add_to_cart','checkout'):
        for left,right in [('sham','settled'),('repaired','settled'),('settled','transition')]:
            if operation=='checkout' and left in ('sham','repaired'):
                continue
            differences=[success(b,left,operation)-success(b,right,operation) for b in range(8)]
            secondary.append(dict(operation=operation,left=left,right=right,differences_exact=[str(d) for d in differences],
                mean=float(sum(differences)/8),scope='predeclared descriptive secondary; cannot replace a primary'))
    static={}; route_evidence=[]
    for arm in ARMS:
        rows=[r for b in range(8) for r in cells[(b,arm)]['controls'] if r['period']=='test']
        static[arm]=dict(attempts=len(rows),successes=sum(r['success'] for r in rows),
                        success_fraction=sum(r['success'] for r in rows)/len(rows) if rows else None)
    for b in range(8):
        row=next(r for r in cells[(b,'settled')]['summary']['operation_summaries'] if r['period']=='test' and r['operation']=='checkout')
        route_evidence.append(dict(block=b,failures_with_selected_a=row['failures_with_selected_a'],
                                   failed_route_coverage=row['failed_route_coverage']))
    negative_ok=all(r['attempts']==120 and r['success_fraction']>=.97 for r in static.values()) and \
        max(r['success_fraction'] for r in static.values())-min(r['success_fraction'] for r in static.values())<=.03
    diagnostic_ok=sum(r['failures_with_selected_a'] for r in route_evidence)>=10 and \
        sum(r['failures_with_selected_a']>0 for r in route_evidence)>=6
    report.update(primary_status='complete_planned_census' if qualified else 'complete_census_but_design_unqualified',
        primary_contrasts=contrasts,secondary=secondary,static_control=static,route_evidence=route_evidence,
        negative_control_tolerance_met=negative_ok,execution_diagnostic_threshold_met=diagnostic_ok,
        scoped_h_exec_support=qualified and negative_ok and diagnostic_ok and all(r['confirmed_within_design'] for r in contrasts.values()),
        negative_control_statistical_equivalence_not_asserted=True,causal_mediation_fraction_identified=False,
        historical_error_fraction_explained_not_estimated=True,aina_cause_established=False,
        new_refinement_automatically_selected=False)
    write(out/'study-analysis.json',report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('plan','collect'));parser.add_argument('--phase',choices=('qualification','study'),required=True)
    parser.add_argument('--qualification-run',type=int);args=parser.parse_args();frozen=settings()
    if args.stage=='plan':
        gate=prerequisite(args.qualification_run) if args.phase=='study' and args.qualification_run else None
        assert args.phase=='qualification' or gate is not None,'study requires successful same-protocol four-arm technical qualification'
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
            stream.write('matrix='+json.dumps(dict(include=frozen['assignments'][args.phase]))+'\n')
        write(Path('workflow-results/plan/plan.json'),dict(phase=args.phase,assignments=frozen['assignments'][args.phase],gate=gate,
              protocol_sha256=sha(CONFIG),head=os.environ['GITHUB_SHA']))
    else:
        collect(Path('workflow-input/reports'),Path('workflow-results/analysis'),frozen,args.phase)


if __name__=='__main__':
    main()
