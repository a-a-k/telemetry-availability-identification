"""Direct exact-rational DTMC/MDP for the empirical joint observation problem.

States are a finite decision process for one operation, not fitted time dynamics.
Category is drawn by its joint frequency; unknown coordinates are nondeterministic.
Completion-prefix compression preserves the full vector of reported functionals.
"""
from collections import deque
from fractions import Fraction
from time import perf_counter
from .graph_execution_model_v1 import control_ids,validate
from .exact_backend_common_v1 import Circuit,FUNCTIONALS,estimates_from_pairs


def decision_graph(model):
    validate(model);circuit=Circuit(model);controls=sorted(control_ids(model));completion=model['completion_signals']
    known=[dict(zip(model['signal_ids'],r['values'])) for r in model['observation_categories']]
    keys=[('initial',)];mapping={keys[0]:0};actions=[];labels={};initial_columns={}
    def add(key):
        if key not in mapping:mapping[key]=len(keys);keys.append(key)
        return mapping[key]
    index=0
    while index<len(keys):
        key=keys[index];kind=key[0]
        if kind=='initial':
            transitions={}
            for j,row in enumerate(model['observation_categories']):
                column=add(('controls',j,0,0));initial_columns[column]=j
                transitions[column]=Fraction(row['count'],model['sample_count'])
            choices=[transitions]
        elif kind=='controls':
            _,category,depth,bits=key
            if depth==len(controls):
                state={name:bool(bits&(1<<i)) for i,name in enumerate(controls)}
                endpoints=[]
                for c in (False,True):
                    state.update({name:c for name in completion});values=circuit.evaluate(state)
                    endpoints.append(tuple(values[name] for name in FUNCTIONALS))
                choices=[{add(('completion',category,0,tuple(endpoints))):Fraction(1)}]
            else:
                value=known[category][controls[depth]];options=(False,True) if value is None else (value,)
                choices=[{add(('controls',category,depth+1,bits | (int(v)<<depth))):Fraction(1)} for v in options]
        elif kind=='completion':
            _,category,depth,endpoints=key
            if depth==len(completion):choices=[{add(('terminal',endpoints[1])):Fraction(1)}]
            else:
                value=known[category][completion[depth]];options=(False,True) if value is None else (value,)
                choices=[{add(('completion',category,depth+1,endpoints) if v else ('terminal',endpoints[0])):Fraction(1)} for v in options]
        else:
            labels[index]=key[1];choices=[{index:Fraction(1)}]
        actions.append(choices);index+=1
    return actions,labels,initial_columns


class StormExact:
    def __init__(self,model):
        import stormpy
        self.storm=stormpy;self.category_values=None;self.counts=None;self._build(model)

    def _build(self,model):
        storm=self.storm;actions,labels,self.initial_columns=decision_graph(model)
        self.is_mdp=any(len(a)>1 for a in actions)
        builder=storm.ExactSparseMatrixBuilder(rows=0,columns=0,entries=0,force_dimensions=False,
            has_custom_row_grouping=self.is_mdp,row_groups=0)
        row=0
        for choices in actions:
            if self.is_mdp:builder.new_row_group(row)
            for choice in choices:
                for column,value in sorted(choice.items()):builder.add_next_value(row,column,storm.Rational(str(value)))
                row+=1
        labeling=storm.storage.StateLabeling(len(actions));labeling.add_label('init');labeling.add_label_to_state('init',0)
        for name in FUNCTIONALS:labeling.add_label(name)
        for state,values in labels.items():
            for name,value in zip(FUNCTIONALS,values):
                if value:labeling.add_label_to_state(name,state)
        components=storm.SparseExactModelComponents(transition_matrix=builder.build(),state_labeling=labeling,rate_transitions=False)
        self.native=storm.storage.SparseExactMdp(components) if self.is_mdp else storm.storage.SparseExactDtmc(components)
        self.properties={}
        for name in FUNCTIONALS:
            text=';'.join(f'P{direction}=? [F "{name}"]' for direction in ('min','max')) if self.is_mdp else f'P=? [F "{name}"]'
            self.properties[name]=storm.parse_properties(text)
        self.category_values=[list(r['values']) for r in model['observation_categories']]
        self.counts=[r['count'] for r in model['observation_categories']]
        self.stats=dict(model_type='MDP' if self.is_mdp else 'DTMC',states=self.native.nr_states,
                        transitions=self.native.nr_transitions,choices=row,exact_rational=True)

    def query(self,model):
        validate(model);started=perf_counter();values=[r['values'] for r in model['observation_categories']];counts=[r['count'] for r in model['observation_categories']]
        if values!=self.category_values:self._build(model)
        elif counts!=self.counts:
            for entry in self.native.transition_matrix.get_row(0):
                j=self.initial_columns[entry.column]
                entry.set_value(self.storm.Rational(str(Fraction(counts[j],model['sample_count']))))
            self.counts=list(counts)
        self.last_update_seconds=perf_counter()-started
        totals={}
        for name,properties in self.properties.items():
            values=[Fraction(str(self.storm.model_checking(self.native,p,only_initial_states=True).at(0))) for p in properties]
            totals[name]=values if self.is_mdp else values*2
        return estimates_from_pairs(totals)
