"""Compare candidate/replay compact reports after independent processes completed."""
import json
from pathlib import Path

root=Path('workflow-input/reports');out=Path('workflow-results/qualification');out.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(p.read_text())
records=[]
for profile in ('deathstarbench_social_network','opentelemetry_demo'):
    fit_dir=next(root.glob('existing-graph-fit-'+profile+'-*'))
    replay_dir=next(root.glob('existing-graph-replay-'+profile+'-*'))
    fit=read(fit_dir/'fit.json');replay=read(replay_dir/'replay.json')
    assert fit['identity']==replay['identity'] and fit['model_sha256']==replay['model_sha256']
    assert fit['prediction']==replay['prediction']
    fit_audit=read(fit_dir/'read-audit.json');replay_audit=read(replay_dir/'read-audit.json')
    assert len(fit_audit['actual_data_reads'])==6 and len(replay_audit['actual_data_reads'])==1
    assert not fit_audit['blocked'] and not replay_audit['blocked']
    assert fit['verified_external_boundary_roots']==80 and fit['unexpected_missing_parents']==0
    assert replay['structural_control']['equivalent_edge_order_preserves_prediction']
    assert len(replay['structural_control']['remove_incoming_required_edges'])==2
    assert all(value['upper']==0 for value in replay['structural_control']['remove_incoming_required_edges'].values())
    records.append(dict(profile=profile,identity=fit['identity'],model_sha256=fit['model_sha256'],
        prediction=fit['prediction'],build_data_reads=6,replay_data_reads=1,
        verified_external_boundary_roots=80,graph_nodes=len(fit['graph_nodes']),graph_edges=len(fit['graph_edges']),
        build_seconds=fit['elapsed_seconds'],replay_seconds=replay['elapsed_seconds'],
        assumptions=fit['assumptions'],structural_checks=replay['structural_control']))
report=dict(scope='two retained normal-state DeathStar and OTel graph chains',qualified=True,
    main_campaigns=0,selected_main_method=False,independent_adequacy_test=False,records=records)
(out/'qualification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps(dict(qualified=True,graph_chains=len(records),main_campaigns=0)))
