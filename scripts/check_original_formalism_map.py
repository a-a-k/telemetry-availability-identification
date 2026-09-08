"""Bounded known-parameter checks; no live data or fitting. Run from repo root."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference_models.original_stochconn.model import Edge, EndpointPredicate, ServiceGraph
from reference_models.original_stochconn.estimators import exact_enumeration
from telemetry_availability.live_validation_analysis import route_probability

cases = [
    ('all_up', {'g':1.,'ea':1.,'eb':1.,'ca':1.,'cb':1.}, 1.,1.),
    ('no_replica', {'g':1.,'ea':0.,'eb':0.,'ca':1.,'cb':1.}, 0.,0.),
    ('one_path', {'g':1.,'ea':1.,'eb':0.,'ca':1.,'cb':1.}, 1.,1.),
    ('live_process_broken_communication', {'g':1.,'ea':1.,'eb':1.,'ca':0.,'cb':0.}, 0.,0.),
    ('common_domain', {'g':.8,'ea':1.,'eb':1.,'ca':1.,'cb':1.}, .8,.96),
    ('mixed_known_parameters', {'g':.8,'ea':.9,'eb':.85,'ca':.95,'cb':.9}, .77274,.877392),
]
results = []
for name, params, colocated, split in cases:
    for placement, expected in [('colocated',colocated),('split',split)]:
        actual = route_probability(params, placement)
        assert abs(actual-expected) <= 1e-12
        results.append(dict(control=name, placement=placement, parameters=params,
                            expected=expected, actual=actual, absolute_error=abs(actual-expected)))

edges = (Edge('entry','target'), Edge('target','async_worker','async'))
graph = ServiceGraph(('entry','target','async_worker'), edges,
                     {'entry':1,'target':2,'async_worker':1},
                     {'entry':(1.,),'target':(.9,.9),'async_worker':(1.,)},
                     {edges[0].key:.8, edges[1].key:1.})
for name, async_rho, predicate, expected in [
    ('replicated_logical_edge',1.,EndpointPredicate('read','entry',('target',)),.792),
    ('nonblocking_async_failure',0.,EndpointPredicate('read','entry',('target',)),.792),
    ('eventual_requires_async',0.,EndpointPredicate('eventual','entry',('target','async_worker'),
                                                  success_semantics='eventual_async_explicit'),0.),
]:
    graph.rho[edges[1].key] = async_rho
    actual = exact_enumeration(graph,predicate)
    assert abs(actual-expected) <= 1e-12
    results.append(dict(control=name,engine='original MODELS artifact',async_edge_probability=async_rho,
                        expected=expected,actual=actual,absolute_error=abs(actual-expected)))

paths = ['reference_models/original_stochconn/model.py',
         'reference_models/original_stochconn/estimators.py',
         'reference_models/original_stochconn/LICENSE',
         'src/telemetry_availability/live_validation_analysis.py',
         'src/telemetry_availability/live_evidence.py','configs/m7_frozen_live.yaml',
         'scripts/check_original_formalism_map.py']
record = dict(kind='bounded_artificial_source_mapping_checks',
              data_role='artificial known-parameter controls; not empirical validation',
              inputs=[{'path':name,'sha256':hashlib.sha256(Path(name).read_bytes()).hexdigest()} for name in paths],
              results=results,checks=len(results),
              maximum_absolute_error=max(r['absolute_error'] for r in results),
              model_fits=0,live_data_reads=0,
              original_artifact_git_commit='not established; exact inspected and copied files hashed')
out = Path('docs/evidence/original-formalism-map-2026-09-08/controls-and-source-hashes.json')
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'checks':len(results),'maximum_absolute_error':record['maximum_absolute_error']}))
