"""Frozen H-EXEC statistics replay with separate acquisition/replay identities."""
import os
from fractions import Fraction
from .h_exec_analysis_v2 import paired, ARMS, CONFIG
from .v3_primary_projection import read, write, sha


def collect(root,out,frozen,phase,source_head,source_run):
    expected=frozen['assignments'][phase]
    cells={}; records=[]
    for cell in expected:
        paths=list(root.glob(f'h-exec-compact-{phase}-b{cell["block"]}-s{cell["slot"]}-*'))
        if len(paths)!=1 or not (paths[0]/'summary.json').is_file():
            records.append(dict(**cell,available=False,qualified=False));continue
        summary=read(paths[0]/'summary.json');identity=summary['identity']
        assert all(identity[k]==cell[k] for k in ('block','slot','arm')) and identity['phase']==phase
        assert identity['source_head']==source_head and identity['run_id']==str(source_run)
        assert (cell['block'],cell['arm']) not in cells
        cells[(cell['block'],cell['arm'])]=dict(summary=summary,controls=read(paths[0]/'static-controls.json'))
        records.append(dict(**cell,available=True,qualified=summary['qualified'],checks=summary['checks']))
    qualified=len(cells)==len(expected) and all(r['qualified'] for r in records)
    report=dict(phase=phase,head=source_head,run_id=str(source_run),
        replay_head=os.environ['GITHUB_SHA'],replay_run_id=os.environ['GITHUB_RUN_ID'],
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

