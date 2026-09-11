"""CUDD with persistent manager, fixed cache and no timed semantic verification."""
from .graph_execution_model_v1 import control_ids,VARIANTS
from .exact_backend_common_v1 import estimates_from_extrema


class Cudd:
    def __init__(self,sift=False):
        self.sift=sift;self.bdd=None;self.builds=0;self.stats={}

    def rebuild(self,model):
        from dd.cudd import BDD
        if self.bdd is None:
            self.bdd=BDD(memory_estimate=2**30,initial_cache_size=2**14)
        bdd=self.bdd;bdd.configure(reordering=False)
        order=sorted(control_ids(model))+sorted(model['completion_signals'])
        for name in order:
            if name not in bdd.vars:bdd.add_var(name)
        self.roots={}
        def AND(names):
            value=bdd.true
            for name in names:value &= bdd.var(name)
            return value
        live={}
        for service,replicas in model['replicas'].items():
            value=bdd.false
            for gates in replicas:value |= AND(gates)
            live[service]=value
        op=model['operation'];reachable={s:bdd.false for s in live};reachable[op['entry']]=live[op['entry']]
        edges=[(e['source'],e['target'],AND(e['factors'])) for e in model['graph']['edges'] if e['type']=='sync']
        for _ in range(len(live)-1):
            updated=dict(reachable)
            for s,t,g in edges:updated[t] |= reachable[s]&g&live[t]
            if updated==reachable:break
            reachable=updated
        base=bdd.true
        for s in op['required']:base &= reachable[s]
        selected=base
        for row in model['demand_controls']:
            any_selected=bdd.false
            for signal,gates in zip(row['selected_signals'],model['replicas'][row['service']]):
                d=bdd.var(signal);any_selected |= d;selected &= ~d|AND(gates)
            selected &= any_selected
        completed=bdd.var(model['entry_completion_signal']);sync={e['id'] for e in model['graph']['edges'] if e['type']=='sync'}
        for r in model['required_edge_completions']:completed &= bdd.var(r['signal']) if r['edge_id'] in sync else bdd.false
        timely=bdd.var(model['timely_signal'])
        self.roots=dict(reachability=base,selected=selected,without_deadline=selected&completed,execution=selected&completed&timely,
                        without_selection=base&completed&timely,without_completion=selected&timely)
        self.roots.update({n+'_minus_execution':self.roots[n]&~self.roots['execution'] for n in VARIANTS if n!='execution'})
        del live,reachable,edges,base,selected,completed,timely
        if self.sift:bdd.reorder()
        self.builds+=1

    def query(self,model):
        bdd=self.bdd;extrema=[]
        # Cofactor each distinct root: constant false/true encode attainable endpoints.
        unique=list(set(self.roots.values()))
        for row in model['observation_categories']:
            known={x:v for x,v in zip(model['signal_ids'],row['values']) if v is not None}
            restricted={root:bdd.let(known,root) for root in unique}
            extrema.append({n:(int(restricted[root]==bdd.true),int(restricted[root]!=bdd.false)) for n,root in self.roots.items()})
        self.stats=dict(semantic_builds=self.builds,infrastructure_builds=1,variables=len(bdd.vars),initial_cache_entries=2**14)
        return estimates_from_extrema(model,extrema)

    def diagnostics(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');return dict(self.stats,manager=self.bdd.statistics())
