"""Shared output contract and conservative reuse key; no fitted independence."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import json

from .graph_execution_model_v1 import VARIANTS, validate

FUNCTIONALS = VARIANTS + tuple(n+'_minus_execution' for n in VARIANTS if n != 'execution')


def semantic_key(model):
    """Exact bytes, not hash-only equality. Ignore only nonsemantic metadata."""
    data = {k:model[k] for k in ('version','execution_class','signal_ids','replicas','demand_controls',
             'timely_signal','entry_completion_signal','completion_signals','required_edge_completions')}
    data['graph'] = dict(services=model['graph']['services'], edges=[{k:e[k] for k in ('id','source','target','type','factors')}
                        for e in model['graph']['edges']])
    data['operation'] = {k:model['operation'][k] for k in ('entry','required','semantics')}
    return json.dumps(data, sort_keys=True, separators=(',',':')).encode()


def estimates_from_extrema(model, extrema):
    if len(extrema) != len(model['observation_categories']): raise ValueError('category census differs')
    totals = {n:[Fraction(0),Fraction(0)] for n in FUNCTIONALS}
    for row, values in zip(model['observation_categories'],extrema):
        weight = Fraction(row['count'],model['sample_count'])
        for name,(lo,hi) in values.items():
            if lo not in (0,1) or hi not in (0,1) or lo>hi: raise ValueError('invalid Boolean extrema')
            totals[name][0] += weight*lo; totals[name][1] += weight*hi
    return estimates_from_pairs(totals)


def estimates_from_pairs(totals):
    return {name:dict(lower=float(lo),upper=float(hi),lower_exact=str(lo),upper_exact=str(hi),
            prediction=float(lo) if lo==hi else None,
            status='singleton_given_empirical_observation_law' if lo==hi else 'ambiguous')
            for name,(lo,hi) in totals.items()}


def updates(original):
    """Prespecified artificial updates of each saved case; not fresh telemetry."""
    yield 'initial',deepcopy(original)
    yield 'repeat',deepcopy(original)
    counts=deepcopy(original)
    for i,row in enumerate(counts['observation_categories']):row['count']*=1+i%3
    counts['sample_count']=sum(r['count'] for r in counts['observation_categories'])
    yield 'counts',counts
    masked=deepcopy(counts);position=masked['signal_ids'].index(masked['entry_completion_signal']);merged=Counter()
    for row in masked['observation_categories']:
        row['values'][position]=None;merged[tuple(row['values'])]+=row['count']
    masked['observation_categories']=[dict(values=list(k),count=v) for k,v in merged.items()]
    validate(masked);yield 'masks',masked
    metadata=deepcopy(masked);metadata['experiment_metadata']='changed_nonsemantic_metadata'
    yield 'metadata',metadata
    changed=deepcopy(metadata)
    edge_id='absent_required_relation_update_v1'
    if edge_id in {e['id'] for e in changed['graph']['edges']}:raise ValueError('reserved edge identifier')
    changed['required_edge_completions'].append(dict(edge_id=edge_id,signal=changed['entry_completion_signal']))
    validate(changed);yield 'structure',changed
    yield 'restore',deepcopy(original)


class Circuit:
    """Hash-consed Boolean DAG with local identities, built directly from the graph."""
    def __init__(self,model):
        self.nodes=[('constant',(),False),('constant',(),True)]
        self.cache={};self.inputs={x:self._node('input',(),x) for x in model['signal_ids']}
        AND=lambda xs:self.fold('and',xs,1)
        OR=lambda xs:self.fold('or',xs,0)
        gates=lambda names:AND(self.inputs[x] for x in names)
        live={s:OR(gates(g) for g in rs) for s,rs in model['replicas'].items()}
        op=model['operation']; reach={s:0 for s in live};reach[op['entry']]=live[op['entry']]
        edges=[(e['source'],e['target'],gates(e['factors'])) for e in model['graph']['edges'] if e['type']=='sync']
        for _ in range(len(live)-1):
            nxt=dict(reach)
            for s,t,g in edges:nxt[t]=self.binary('or',nxt[t],AND((reach[s],g,live[t])))
            if nxt==reach:break
            reach=nxt
        base=AND(reach[s] for s in op['required']);selected=base
        for row in model['demand_controls']:
            ds=[self.inputs[x] for x in row['selected_signals']]
            selected=AND((selected,OR(ds)))
            for d,gs in zip(ds,model['replicas'][row['service']]):
                selected=AND((selected,self.binary('or',self.negate(d),gates(gs))))
        sync_ids={e['id'] for e in model['graph']['edges'] if e['type']=='sync'}
        completed=AND([self.inputs[model['entry_completion_signal']]]+
                      [self.inputs[r['signal']] if r['edge_id'] in sync_ids else 0 for r in model['required_edge_completions']])
        timely=self.inputs[model['timely_signal']]
        self.roots=dict(reachability=base,selected=selected,without_deadline=AND((selected,completed)),
            execution=AND((selected,completed,timely)),without_selection=AND((base,completed,timely)),
            without_completion=AND((selected,timely)))
        self.roots.update({n+'_minus_execution':AND((self.roots[n],self.negate(self.roots['execution']))) for n in VARIANTS if n!='execution'})
        used=set()
        def visit(i):
            if i in used:return
            used.add(i)
            for j in self.nodes[i][1]:visit(j)
        for i in self.roots.values():visit(i)
        self.used=sorted(used)

    def _node(self,op,args,value=None):
        key=(op,args,value)
        if key not in self.cache:self.cache[key]=len(self.nodes);self.nodes.append(key)
        return self.cache[key]

    def binary(self,op,a,b):
        if a==b:return a
        if op=='and':
            if 0 in (a,b):return 0
            if a==1:return b
            if b==1:return a
        else:
            if 1 in (a,b):return 1
            if a==0:return b
            if b==0:return a
        return self._node(op,tuple(sorted((a,b))))

    def negate(self,a):
        if a in (0,1):return 1-a
        if self.nodes[a][0]=='not':return self.nodes[a][1][0]
        return self._node('not',(a,))

    def fold(self,op,nodes,identity):
        value=identity
        for i in nodes:value=self.binary(op,value,i)
        return value

    def evaluate(self,state):
        values={0:False,1:True}
        for i in self.used:
            op,args,value=self.nodes[i]
            if op=='input':values[i]=state[value]
            elif op=='not':values[i]=not values[args[0]]
            elif op=='and':values[i]=all(values[a] for a in args)
            elif op=='or':values[i]=any(values[a] for a in args)
        return {n:int(values[i]) for n,i in self.roots.items()}
