"""Symmetric prepared specialized table and CUDD, returning the same endpoints."""
from itertools import product
from .graph_execution_model_v1 import control_ids,validate
from .graph_execution_bdd_v1 import CompiledModel
from .exact_backend_common_v1 import Circuit,FUNCTIONALS,estimates_from_extrema


class PreparedSpecialized:
    def __init__(self,model):
        validate(model);self.controls=sorted(control_ids(model));self.completions=model['completion_signals']
        circuit=Circuit(model);self.tables={n:0 for n in FUNCTIONALS}
        dimension=len(self.controls)+1;self.universe=(1<<(1<<dimension))-1
        self.variable_masks=[0]*dimension
        for index,bits in enumerate(product((False,True),repeat=dimension)):
            state=dict(zip(self.controls,bits[:-1]));state.update({x:bits[-1] for x in self.completions})
            for j,b in enumerate(bits):
                if b:self.variable_masks[j]|=1<<index
            for name,value in circuit.evaluate(state).items():
                if value:self.tables[name]|=1<<index
        self.stats=dict(prepared_states=1<<dimension,circuit_nodes=len(circuit.used),table_bytes=sum((v.bit_length()+7)//8 for v in self.tables.values()))

    def query(self,model):
        validate(model);extrema=[]
        for row in model['observation_categories']:
            fixed=dict(zip(model['signal_ids'],row['values']));region=self.universe
            values=[fixed[x] for x in self.controls]
            cs=[fixed[x] for x in self.completions]
            values.append(False if False in cs else True if all(v is True for v in cs) else None)
            for value,mask in zip(values,self.variable_masks):
                if value is not None:region &= mask if value else self.universe^mask
            extrema.append({n:(int(not(region & (self.universe^v))),int(bool(region&v))) for n,v in self.tables.items()})
        return estimates_from_extrema(model,extrema)


class PreparedCUDD:
    def __init__(self,model,policy='sift_once'):
        self.compiled=CompiledModel(model,policy)
        self.stats=dict(reorder_seconds=self.compiled.reorder_seconds)

    def query(self,model):
        validate(model);bdd=self.compiled.bdd;extrema=[]
        for row in model['observation_categories']:
            cube=bdd.cube({x:v for x,v in zip(model['signal_ids'],row['values']) if v is not None})
            extrema.append({n:(int(cube&~root==bdd.false),int(cube&root!=bdd.false)) for n,root in self.compiled.roots.items()})
        return estimates_from_extrema(model,extrema)
