"""Finite-mask identification experiment on one unchanged primary-verified ledger.

Graph and declared predicate are held fixed. These are additional missing state
observations, not a claim to reconstruct an unobserved topology. No outcome is
passed to the exact bound calculator or to information-restoration choices.
"""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import product

from .prepared_exact_v1 import PreparedSpecialized
from .graph_execution_model_v1 import fiber_states,predicates


class Bounds:
    def __init__(self,model):
        self.model=model;self.prepared=PreparedSpecialized(model);self.cache={}
        ids=model['signal_ids'];self.controls=[ids.index(k) for k in self.prepared.controls]
        self.completions=[ids.index(k) for k in self.prepared.completions]

    def __call__(self,values):
        cs=[values[i] for i in self.completions]
        k=False if False in cs else True if all(v is True for v in cs) else None
        key=tuple(values[i] for i in self.controls)+(k,)
        if key not in self.cache:
            p=self.prepared;region=p.universe
            for value,mask in zip(key,p.variable_masks):
                if value is not None:region&=mask if value else p.universe^mask
            truth=p.tables['execution']
            self.cache[key]=(int(not(region&(p.universe^truth))),int(bool(region&truth)))
        return self.cache[key]

    def verify(self):
        # Independently evaluate the frozen formal predicate over every reduced
        # mask actually used. The completion conjunction permits this canonical
        # representative; no distributional independence is introduced.
        for key,expected in self.cache.items():
            values=[None]*len(self.model['signal_ids'])
            for i,v in zip(self.controls,key[:-1]):values[i]=v
            for i in self.completions:values[i]=key[-1]
            outcomes=[predicates(self.model,state)['execution'] for state in fiber_states(self.model,values)]
            if (int(min(outcomes)),int(max(outcomes)))!=expected:raise ValueError('prepared missingness endpoint differs from formal predicate')
        return dict(distinct_reduced_masks_checked=len(self.cache),exact_core_predicate_agreement=True)


def rank(seed,*values):
    return int.from_bytes(sha256(('\0'.join([str(seed),*map(str,values)])).encode()).digest(),'big')


def missing_order(records,ids,timely,mechanism,seed):
    cells=[]
    for index,record in enumerate(records):
        rid=record['request_id']
        for position,name in enumerate(ids):
            if name==timely or record['observation'][name] is None:continue
            number=rank(seed,rid,name)
            if mechanism=='uniform_coordinates':priority=(number,)
            elif mechanism=='failure_associated_coordinates':
                # The label is available to this artificial missingness
                # generator only. False outcomes receive priority U/4.
                priority=(number//(4 if record['outcome'] is False else 1),number)
            elif mechanism=='whole_native_attempt':priority=(rank(seed,rid),number)
            else:raise ValueError('unknown fixed missingness mechanism')
            cells.append((priority,rid,name,index,position))
    cells.sort()
    return [(r[3],r[4]) for r in cells]


def information_groups(model):
    ids=model['signal_ids'];entry=model['entry_completion_signal']
    groups=dict(selection_and_admission=[i for i,k in enumerate(ids) if k.startswith(('admitted_','demand_'))],
        entry_result=[ids.index(entry)],required_completions=[ids.index(k) for k in model['completion_signals'] if k!=entry])
    grouped={i for values in groups.values() for i in values}
    if grouped!={i for i,k in enumerate(ids) if k!=model['timely_signal']}:raise ValueError('unclassified native observation coordinate')
    return groups


def metrics(records,values,calculator):
    counts=Counter();n=len(records)
    for record,observed in zip(records,values,strict=True):
        lo,hi=calculator(observed);y=record['outcome']
        if type(y) is not bool:raise ValueError('independently verified Boolean outcome required')
        counts.update(attempts=1,successes=int(y),lower_count=lo,upper_count=hi,
            ambiguous_attempts=int(lo!=hi),point_identified_attempts=int(lo==hi),
            success_excluded=int(y>hi),failure_excluded=int(y<lo),
            fully_observed_states=int(None not in observed))
    return dict(counts,identified_lower=counts['lower_count']/n,identified_upper=counts['upper_count']/n,
        width=(counts['upper_count']-counts['lower_count'])/n,
        point_identified_fraction=counts['point_identified_attempts']/n,
        compatible_fraction=1-(counts['success_excluded']+counts['failure_excluded'])/n)


def experiment(model,records,levels,mechanisms,seed):
    if not records or len({r['request_id'] for r in records})!=len(records):raise ValueError('missing/duplicate primary attempt')
    if len(records)!=model['sample_count']:raise ValueError('missingness population differs from saved model')
    ids=model['signal_ids'];original=[[r['observation'][k] for k in ids] for r in records]
    if Counter(map(tuple,original))!={tuple(r['values']):r['count'] for r in model['observation_categories']}:
        raise ValueError('primary population does not reproduce sealed joint observation law')
    calculator=Bounds(model);groups=information_groups(model)
    reference=metrics(records,original,calculator)
    for record,values in zip(records,original):
        if calculator(values)!=(record['lower'],record['upper']):raise ValueError('original primary-verified bounds differ')
    results=[]
    for mechanism in mechanisms:
        order=missing_order(records,ids,model['timely_signal'],mechanism,seed)
        previous_width=-1
        for level in levels:
            budget=int(Fraction(str(level))*len(order));masked=[row.copy() for row in original];hidden=order[:budget]
            for i,j in hidden:masked[i][j]=None
            base=metrics(records,masked,calculator)
            if base['width']<previous_width:raise ValueError('nested missingness unexpectedly narrows bounds')
            previous_width=base['width']
            affected=Counter(i for i,j in hidden)
            known=Counter(i for i,j in order)
            partial=sum(0<n<known[i] for i,n in affected.items())
            if mechanism=='whole_native_attempt' and partial>1:raise ValueError('whole-attempt mask has multiple boundary rows')
            prefix=dict(mechanism=mechanism,missing_fraction_requested=level,known_native_coordinates=len(order),
                hidden_native_coordinates=budget,affected_attempts=len(affected),partially_masked_attempts=partial,
                whole_attempt_boundary_partial_row=mechanism=='whole_native_attempt' and partial==1)
            results.append(dict(prefix,information='none',revealed_native_coordinates=0,revealed_attempts=0,
                ambiguities_resolved=0,**base))
            for group,positions in dict(groups,all_native=[i for i,k in enumerate(ids) if k!=model['timely_signal']]).items():
                restored=[row.copy() for row in masked];opened=[]
                for i,j in hidden:
                    if j in positions:restored[i][j]=original[i][j];opened.append((i,j))
                actual=metrics(records,restored,calculator)
                for before,after,origin in zip(masked,restored,original):
                    lo,hi=calculator(before);a,b=calculator(after);x,y=calculator(origin)
                    if not lo<=a<=x<=y<=b<=hi:raise ValueError('additional observations violate interval nesting')
                if group=='all_native' and actual!=reference:raise ValueError('restoration did not recover original partial observation law')
                results.append(dict(prefix,information=group,revealed_native_coordinates=len(opened),
                    revealed_attempts=len({i for i,j in opened}),
                    ambiguities_resolved=base['ambiguous_attempts']-actual['ambiguous_attempts'],**actual))
    return dict(reference=reference,rows=results,qualification=calculator.verify(),
        population_selected_by_E_equals_Y=False,known_graph_and_predicate_fixed=True,
        original_unknowns_filled=False,coordinate_count_is_instrumentation_cost=False,
        identification_bounds_are_confidence_intervals=False)
