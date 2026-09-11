"""Two predeclared exact support-inference schedules; no verification inference."""
from itertools import product
from time import perf_counter_ns
from .exact_backend_common_v1 import Circuit,estimates_from_extrema


class Agrum:
    def __init__(self,joint=False):
        import pyagrum as gum
        self.gum=gum;self.joint=joint;self.bn=gum.BayesNet('support');self.engine=None
        self.builds=0;self.network_builds=0;self.engine_builds=0;self.values=None;self.stats={}

    def rebuild(self,model):
        self.builds+=1;self.circuit=Circuit(model);self._network(model)

    def _network(self,model):
        self.engine=None;self.bn.clear();gum=self.gum;bn=self.bn;self.names={};self.network_builds+=1
        self.q=len(model['observation_categories']);domain=max(2,self.q)
        bn.add(gum.LabelizedVariable('observation','observation category',domain))
        # Only support is needed. Counts are aggregated exactly outside the BN.
        bn.cpt('observation').fillWith([1/self.q]*self.q+([0.0] if self.q==1 else []))
        for i in self.circuit.used:
            op,args,value=self.circuit.nodes[i];name='n'+str(i);self.names[i]=name
            bn.add(gum.LabelizedVariable(name,name,2))
            parents=['observation'] if op=='input' else [self.names[j] for j in args]
            for parent in parents:bn.addArc(parent,name)
            if op=='constant':bn.cpt(name).fillWith([int(not value),int(value)])
            elif op!='input':
                for bits in product((0,1),repeat=len(args)):
                    v=not bits[0] if op=='not' else all(bits) if op=='and' else any(bits)
                    bn.cpt(name)[dict(zip(parents,bits))]=[int(not v),int(v)]
        self.values=None;self._update(model)

    def _update(self,model):
        values=[r['values'] for r in model['observation_categories']]
        if len(values)!=self.q:self._network(model);return
        if values==self.values:return
        positions={x:i for i,x in enumerate(model['signal_ids'])}
        for i in self.circuit.used:
            op,args,signal=self.circuit.nodes[i]
            if op!='input':continue
            for j in range(max(2,self.q)):
                v=values[min(j,self.q-1)][positions[signal]]
                self.bn.cpt(self.names[i])[{'observation':j}]=[0.5,0.5] if v is None else [int(not v),int(v)]
        self.engine=self.gum.LazyPropagation(self.bn);self.engine_builds+=1
        self.engine.setNumberOfThreads(1);self.engine.setMaxMemory(1)
        self.targets=sorted({self.names[i] for i in self.circuit.roots.values()})
        self.engine.eraseAllTargets()
        for name in self.targets:
            if self.joint:self.engine.addJointTarget({'observation',name})
            else:self.engine.addTarget(name)
        self.values=[list(r) for r in values]

    def query(self,model):
        started=perf_counter_ns();self._update(model);self.last_update_ns=perf_counter_ns()-started
        engine=self.engine;by_name={name:[] for name in self.targets};self.cells=[]
        if self.joint:
            engine.makeInference()
            for name in self.targets:
                posterior=engine.jointPosterior({'observation',name})
                for j in range(self.q):
                    p0=float(posterior[{'observation':j,name:0}]);p1=float(posterior[{'observation':j,name:1}])
                    self.cells.append((p0,p1));by_name[name].append((int(p0==0),int(p1>0)))
        else:
            if not engine.hasEvidence('observation'):engine.addEvidence('observation',0)
            for j in range(self.q):
                engine.chgEvidence('observation',j);engine.makeInference()
                for name in self.targets:
                    posterior=engine.posterior(name);p0=float(posterior[0]);p1=float(posterior[1])
                    self.cells.append((p0,p1));by_name[name].append((int(p0==0),int(p1>0)))
        rows=[{n:by_name[self.names[i]][j] for n,i in self.circuit.roots.items()} for j in range(self.q)]
        self.stats=dict(semantic_builds=self.builds,infrastructure_builds=1,network_builds=self.network_builds,
            engine_builds=self.engine_builds,native_inference_calls=1 if self.joint else self.q)
        return estimates_from_extrema(model,rows)

    def diagnostics(self):
        return dict(bn_nodes=self.bn.size(),bn_arcs=self.bn.sizeArcs(),
            cpt_entries=sum(self.bn.cpt(i).domainSize() for i in self.bn.nodes()))
