"""Exact sparse Storm with optional acyclic behavioural/stutter compaction.

This is a preprocessing alternative, not Storm's double-only bisimulation API.
Initial weights remain separate so count updates preserve the prepared graph.
"""
from fractions import Fraction
from time import perf_counter_ns
from .storm_exact_v1 import decision_graph
from .exact_backend_common_v1 import FUNCTIONALS,estimates_from_pairs


def compact_graph(actions,labels,initial_columns):
    nodes=[];terminal={};intern={};memo={}
    def visit(state):
        if state in memo:return memo[state]
        if state in labels:
            key=('terminal',tuple(labels[state]));choices=None
        else:
            choices=[]
            for action in actions[state]:
                merged={}
                for target,p in action.items():
                    target=visit(target);merged[target]=merged.get(target,Fraction(0))+p
                choices.append(tuple(sorted(merged.items())))
            choices=tuple(sorted(set(choices)))
            if len(choices)==1 and len(choices[0])==1 and choices[0][0][1]==1:
                memo[state]=choices[0][0][0];return memo[state]
            key=('choices',choices)
        if key not in intern:
            index=len(nodes)+1;intern[key]=index
            nodes.append([{index:Fraction(1)}] if choices is None else [dict(a) for a in choices])
            if choices is None:terminal[index]=labels[state]
        memo[state]=intern[key];return memo[state]
    groups={};initial={}
    for target,p in actions[0][0].items():
        reduced=visit(target);initial[reduced]=initial.get(reduced,Fraction(0))+p
        groups.setdefault(reduced,[]).append(initial_columns[target])
    return [[initial]]+nodes,terminal,groups


class Storm:
    def __init__(self,compact=False):
        import stormpy
        self.storm=stormpy;self.environment=stormpy.Environment();self.compact=compact
        self.builds=0;self.space_builds=0;self.property_cache={};self.stats={}

    def rebuild(self,model):self.builds+=1;self._build(model)

    def _build(self,model):
        storm=self.storm;actions,labels,columns=decision_graph(model);unreduced=len(actions)
        if self.compact:actions,labels,self.groups=compact_graph(actions,labels,columns)
        else:self.groups={i:[j] for i,j in columns.items()}
        self.space_builds+=1;self.is_mdp=any(len(a)>1 for a in actions)
        builder=storm.ExactSparseMatrixBuilder(rows=0,columns=0,entries=0,force_dimensions=False,
            has_custom_row_grouping=self.is_mdp,row_groups=0)
        row=0
        for choices in actions:
            if self.is_mdp:builder.new_row_group(row)
            for action in choices:
                for column,p in sorted(action.items()):builder.add_next_value(row,column,storm.Rational(str(p)))
                row+=1
        labeling=storm.storage.StateLabeling(len(actions));labeling.add_label('init');labeling.add_label_to_state('init',0)
        sets={n:tuple(s for s,v in labels.items() if v[i]) for i,n in enumerate(FUNCTIONALS)}
        unique={};self.alias={}
        for name,states in sets.items():
            canonical=unique.setdefault(states,name);self.alias[name]=canonical
            if canonical==name:
                labeling.add_label(name)
                for state in states:labeling.add_label_to_state(name,state)
        components=storm.SparseExactModelComponents(transition_matrix=builder.build(),state_labeling=labeling,rate_transitions=False)
        self.native=storm.storage.SparseExactMdp(components) if self.is_mdp else storm.storage.SparseExactDtmc(components)
        cache_key=(self.is_mdp,tuple(unique.values()))
        if cache_key not in self.property_cache:
            properties={}
            for name in unique.values():
                text=';'.join(f'P{d}=? [F "{name}"]' for d in ('min','max')) if self.is_mdp else f'P=? [F "{name}"]'
                properties[name]=storm.parse_properties(text)
            self.property_cache[cache_key]=properties
        self.properties=self.property_cache[cache_key]
        self.values=[list(r['values']) for r in model['observation_categories']]
        self.counts=[r['count'] for r in model['observation_categories']]
        self.stats=dict(states=self.native.nr_states,states_before_compaction=unreduced,transitions=self.native.nr_transitions,
            choices=row,model_type='MDP' if self.is_mdp else 'DTMC',semantic_builds=self.builds,
            space_builds=self.space_builds,infrastructure_builds=1,distinct_queries=sum(map(len,self.properties.values())))

    def query(self,model):
        started=perf_counter_ns();values=[r['values'] for r in model['observation_categories']];counts=[r['count'] for r in model['observation_categories']]
        if values!=self.values:self._build(model)
        elif counts!=self.counts:
            for entry in self.native.transition_matrix.get_row(0):
                p=Fraction(sum(counts[j] for j in self.groups[entry.column]),model['sample_count'])
                entry.set_value(self.storm.Rational(str(p)))
            self.counts=list(counts)
        self.last_update_ns=perf_counter_ns()-started;answers={}
        for name,properties in self.properties.items():
            endpoints=[Fraction(str(self.storm.model_checking(self.native,p,only_initial_states=True,environment=self.environment).at(0))) for p in properties]
            answers[name]=endpoints if self.is_mdp else endpoints*2
        return estimates_from_pairs({n:answers[a] for n,a in self.alias.items()})
