"""LazyPropagation point inference and proven Boolean credal-support bounds.

The uniform missing-bit law is only a full-support oracle, never an identified
law or an imputation forecast. See V3_EXACT_BACKENDS_V1.md for the equivalence.
"""
from itertools import product
import math
from time import perf_counter
from .graph_execution_model_v1 import validate
from .exact_backend_common_v1 import Circuit,estimates_from_extrema


class AgrumExact:
    def __init__(self,model):
        import pyagrum as gum
        validate(model);self.gum=gum;self.circuit=Circuit(model)
        self.bn=gum.BayesNet('joint_observation_support');self.node_names={}
        q=max(2,len(model['observation_categories']))
        self.obs=self.bn.add(gum.LabelizedVariable('observation','observation category',q))
        for i in self.circuit.used:
            op,args,value=self.circuit.nodes[i];name='n'+str(i);self.node_names[i]=name
            self.bn.add(gum.LabelizedVariable(name,name,2))
            parents=['observation'] if op=='input' else [self.node_names[j] for j in args]
            for parent in parents:self.bn.addArc(parent,name)
            if op=='constant':self.bn.cpt(name).fillWith([int(not value),int(value)])
            elif op!='input':
                for values in product((0,1),repeat=len(args)):
                    outcome=not values[0] if op=='not' else all(values) if op=='and' else any(values)
                    self.bn.cpt(name)[dict(zip(parents,values))]=[int(not outcome),int(outcome)]
        self.category_values=None;self.counts=None;self.engine=None;self.update(model)
        self.stats=dict(bn_nodes=self.bn.size(),bn_arcs=self.bn.sizeArcs(),
                        cpt_entries=sum(self.bn.cpt(i).domainSize() for i in self.bn.nodes()),
                        arithmetic='LazyPropagation double precision; zero tested on both posterior entries',
                        interval_algorithm='exact Boolean support reduction, not generic credal-network inference')

    def update(self,model):
        values=[r['values'] for r in model['observation_categories']]
        counts=[r['count'] for r in model['observation_categories']]
        if max(2,len(values))!=self.bn.variable(self.obs).domainSize():
            self.__init__(model);return
        changed=values!=self.category_values or counts!=self.counts
        if values!=self.category_values:
            for i in self.circuit.used:
                op,args,signal=self.circuit.nodes[i]
                if op!='input':continue
                position=model['signal_ids'].index(signal);name=self.node_names[i]
                for j in range(max(2,len(values))):
                    v=values[min(j,len(values)-1)][position]
                    self.bn.cpt(name)[{'observation':j}]=[0.5,0.5] if v is None else [int(not v),int(v)]
        if changed:
            probabilities=[n/model['sample_count'] for n in counts]
            if len(probabilities)==1:probabilities.append(0.0)
            self.bn.cpt(self.obs).fillWith(probabilities)
            # Recreate inference state after any CPT change; its cost is charged.
            self.engine=self.gum.LazyPropagation(self.bn);self.engine.setNumberOfThreads(1)
            self.engine.setMaxMemory(1.0)
            self.engine.setTargets(set(self.node_names[i] for i in self.circuit.roots.values()))
            self.category_values=[list(v) for v in values];self.counts=list(counts)

    def query(self,model):
        validate(model);started=perf_counter();self.update(model);self.last_update_seconds=perf_counter()-started;extrema=[]
        self.engine.eraseAllEvidence();self.engine.makeInference()
        mixture={n:float(self.engine.posterior(self.node_names[i])[1]) for n,i in self.circuit.roots.items()}
        for category in range(len(model['observation_categories'])):
            self.engine.setEvidence({'observation':category});self.engine.makeInference();row={}
            for name,i in self.circuit.roots.items():
                posterior=self.engine.posterior(self.node_names[i]);p0,p1=float(posterior[0]),float(posterior[1])
                if not all(math.isfinite(p) and p>=0 for p in (p0,p1)) or abs(p0+p1-1)>1e-10:
                    raise ValueError('invalid native posterior')
                row[name]=(int(p0==0.0),int(p1>0.0))
            extrema.append(row)
        estimates=estimates_from_extrema(model,extrema)
        for name,ex in estimates.items():
            if ex['prediction'] is not None and abs(mixture[name]-ex['prediction'])>1e-12:
                raise ValueError('native identified point differs from exact aggregation')
        self.last_point_values={n:mixture[n] for n,e in estimates.items() if e['prediction'] is not None}
        return estimates
