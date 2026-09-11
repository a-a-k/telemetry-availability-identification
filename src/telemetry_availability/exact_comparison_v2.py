"""Shared input projection and two endpoint-only forms of our exact algorithm."""
from collections import Counter
from copy import deepcopy
from itertools import product
from . import graph_execution_model_v1 as core
from .exact_backend_common_v1 import Circuit,FUNCTIONALS,semantic_key,estimates_from_extrema
from .prepared_exact_v1 import PreparedSpecialized

REPRESENTATIONS=('original','completion_projected')
PHASES=('initial','repeat','counts','masks','metadata','structure','restore')
METHODS=('ours_direct','ours_prepared','cudd_fixed','cudd_sift','agrum_conditioned','agrum_joint','storm_sparse','storm_compact')


def project(model,representation):
    if representation=='original':return model
    if representation!='completion_projected':raise ValueError('unknown representation')
    aggregate='__all_completions_v2__'
    if aggregate in model['signal_ids']:raise ValueError('reserved coordinate')
    result=deepcopy(model);controls=sorted(core.control_ids(model));ids=controls+[aggregate]
    rows=Counter()
    for row in model['observation_categories']:
        fixed=dict(zip(model['signal_ids'],row['values']));cs=[fixed[x] for x in model['completion_signals']]
        k=False if False in cs else True if all(v is True for v in cs) else None
        rows[tuple(fixed[x] for x in controls)+(k,)]+=row['count']
    result['signal_ids']=ids;result['entry_completion_signal']=aggregate;result['completion_signals']=[aggregate]
    result['required_edge_completions']=[dict(r,signal=aggregate) for r in result['required_edge_completions']]
    result['observation_categories']=[dict(values=list(k),count=v) for k,v in rows.items()]
    return result


def snapshots(original):
    yield 'initial',deepcopy(original)
    yield 'repeat',deepcopy(original)
    changed=deepcopy(original)
    for i,r in enumerate(changed['observation_categories']):r['count']*=1+i%3
    changed['sample_count']=sum(r['count'] for r in changed['observation_categories'])
    yield 'counts',changed
    masked=deepcopy(changed);pos=masked['signal_ids'].index(masked['entry_completion_signal']);rows=Counter()
    for r in masked['observation_categories']:
        r['values'][pos]=None;rows[tuple(r['values'])]+=r['count']
    masked['observation_categories']=[dict(values=list(k),count=n) for k,n in rows.items()]
    yield 'masks',masked
    metadata=deepcopy(masked);metadata['experiment_metadata']='nonsemantic change v2'
    yield 'metadata',metadata
    structural=deepcopy(metadata);op=structural['operation'];target=next((s for s in op['required'] if s!=op['entry']),op['entry'])
    edge_id='__additional_sync_relation_v2__'
    if any(e['id']==edge_id for e in structural['graph']['edges']):raise ValueError('reserved relation')
    structural['graph']['edges'].append(dict(id=edge_id,source=op['entry'],target=target,type='sync',factors=[]))
    yield 'structure',structural
    yield 'restore',deepcopy(original)


class Direct:
    def __init__(self):self.stats={};self.builds=0
    def rebuild(self,model):self.builds+=1
    def query(self,model):
        extrema=[];evaluated=0
        for row in model['observation_categories']:
            # Same candidates and predicates as frozen solve; no witness output.
            values=[core.predicates(model,s) for s in core.fiber_states(model,row['values'])]
            evaluated+=len(values)
            extrema.append({n:(int(min(v[n] for v in values)),int(max(v[n] for v in values))) for n in FUNCTIONALS})
        self.stats=dict(evaluated_states=evaluated,semantic_builds=self.builds,infrastructure_builds=0)
        return estimates_from_extrema(model,extrema)


class Prepared:
    def __init__(self):self.prepared=None;self.builds=0
    def rebuild(self,model):self.prepared=PreparedSpecialized(model);self.builds+=1
    def query(self,model):
        result=self.prepared.query(model)
        self.stats=dict(self.prepared.stats,semantic_builds=self.builds,infrastructure_builds=0)
        return result
