"""Finite graph probability from a joint, possibly masked observation law.

No latent physical-cause identification is asserted. The observed coordinates
represent declared effective eligibility states. Model adequacy is separate.
"""
from collections import Counter
from fractions import Fraction
from itertools import product

from .graph_replay_v3 import phi

VERSION='graph-observation-law-v1'


def probe_verdict(status, check, layer='L7'):
    """HAProxy 3.0 management: '* ' marks in-progress, previous result follows."""
    status=str(status).strip().upper();raw=str(check).strip().upper()
    in_progress=raw.startswith('* ')
    last=raw[2:].strip() if in_progress else raw
    if status=='UP' and last==layer+'OK':value=True
    elif status=='DOWN':value=False
    else:value=None
    return dict(value=value,last_completed_check=last,check_in_progress=in_progress,
                raw_status=status,raw_check_status=raw)


def identify(graph, replicas, operation, signal_ids, observations, assumptions):
    """Empirical law of the observed masks/values; no independent replica fit."""
    ids=list(signal_ids)
    if not 0<len(ids)<=16 or len(ids)!=len(set(ids)):raise ValueError('invalid signal dimension')
    counts=Counter()
    for row in observations:
        if set(row)!=set(ids) or any(v is not None and type(v) is not bool for v in row.values()):
            raise ValueError('observations must be bool/null for exactly the declared coordinates')
        counts[tuple(row[name] for name in ids)]+=1
    if not counts:raise ValueError('no observation samples')
    model=dict(version=VERSION,graph=graph,replicas=replicas,operation=operation,signal_ids=ids,
        observation_categories=[dict(values=list(values),count=count) for values,count in
            sorted(counts.items(),key=lambda x:str(x[0]))],sample_count=sum(counts.values()),
        state_law='arbitrary joint effective eligibility states; observed category frequencies',
        observation_law='coordinate masks may depend on state; no MCAR completion',assumptions=assumptions)
    validate(model)
    return model


def validate(model):
    if model['version']!=VERSION:raise ValueError('unsupported graph observation model')
    ids=model['signal_ids'];known=set(ids);services=set(model['graph']['services'])
    if not 0<len(ids)<=16 or len(ids)!=len(known):raise ValueError('invalid signal IDs')
    if services!=set(model['replicas']) or len(services)!=len(model['graph']['services']):raise ValueError('service set mismatch')
    for replicas in model['replicas'].values():
        if not replicas or any(not set(gates)<=known or len(gates)!=len(set(gates)) for gates in replicas):
            raise ValueError('unknown/duplicate replica gate')
    for edge in model['graph']['edges']:
        if edge['source'] not in services or edge['target'] not in services or edge['type'] not in ('sync','async'):
            raise ValueError('unknown edge endpoint/type')
        if not set(edge['factors'])<=known:raise ValueError('unknown edge signal')
    operation=model['operation']
    if operation['semantics']!='immediate_sync_all_required' or operation['entry'] not in services:
        raise ValueError('unsupported operation semantics/entry')
    if not operation['required'] or not set(operation['required'])<=services:raise ValueError('unknown required target')
    categories=model['observation_categories'];seen=set()
    for row in categories:
        values=tuple(row['values'])
        if len(values)!=len(ids) or any(x is not None and type(x) is not bool for x in values):raise ValueError('invalid category')
        if values in seen or type(row['count']) is not int or row['count']<=0:raise ValueError('duplicate/invalid category count')
        seen.add(values)
    if not categories or type(model['sample_count']) is not int or sum(r['count'] for r in categories)!=model['sample_count']:
        raise ValueError('sample census mismatch')


def evaluate(model):
    """Sharp model-probability bounds over every completion of each mask fiber."""
    validate(model);ids=model['signal_ids']
    table={bits:phi(model,dict(zip(ids,bits))) for bits in product((False,True),repeat=len(ids))}
    lower=Fraction(0);upper=Fraction(0);categories=[]
    for row in model['observation_categories']:
        compatible=[bits for bits in table if all(value is None or value==bit for value,bit in zip(row['values'],bits))]
        lo=min(int(table[bits]) for bits in compatible);hi=max(int(table[bits]) for bits in compatible)
        weight=Fraction(row['count'],model['sample_count']);lower+=weight*lo;upper+=weight*hi
        categories.append(dict(values=row['values'],count=row['count'],compatible_states=len(compatible),
            minimum_phi=lo,maximum_phi=hi))
    singleton=lower==upper
    return dict(version=VERSION,event='graph reachability of declared required targets',
        status='estimated_graph_probability' if singleton else 'ambiguous_graph_probability',
        prediction=float(lower) if singleton else None,lower=float(lower),upper=float(upper),
        lower_exact=str(lower),upper_exact=str(upper),states_enumerated=len(table),samples=model['sample_count'],
        categories=categories,singleton_given_empirical_observation_law=singleton,
        population_identification_from_finite_sample_not_asserted=True,
        interval_is_confidence_interval=False,physical_cause_parameters_identified=False,
        parameter_uncertainty='not estimated in technical chain',business_adequacy='requires separate validation')
