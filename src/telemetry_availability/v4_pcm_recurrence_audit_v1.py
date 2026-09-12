"""Transparent audit recurrence for the actually observed linear/loop PCM class.

This is not a replacement comparator or a performance benchmark. It checks the
saved numerical PMX/Palladio answer from its own serialized software model.
Other action kinds are refused, and hardware reliability is not inferred here.
"""
from fractions import Fraction
import re
from xml.etree import ElementTree as ET

XSI='{http://www.w3.org/2001/XMLSchema-instance}type'
PAIR=re.compile(r'\(\s*(0|[1-9][0-9]*)\s*;\s*([0-9.eE+\-]+)\s*\)')


def pmf(text):
    if not text.startswith('IntPMF[') or not text.endswith(']'):raise ValueError('unhandled loop expression')
    body=text[7:-1];pairs=PAIR.findall(body)
    if not pairs or PAIR.sub('',body).strip():raise ValueError('unhandled integer PMF')
    values=[(int(k),Fraction(p)) for k,p in pairs]
    if len({k for k,p in values})!=len(values) or any(p<0 or p>1 for k,p in values) or abs(sum(p for k,p in values)-1)>Fraction(1,10**12):
        raise ValueError('invalid serialized loop law')
    return values


def audit(repository_text,usage_text):
    tree=ET.fromstring(repository_text);usage=ET.fromstring(usage_text)
    names={n.attrib['id']:n.attrib['entityName'] for n in tree.iter() if 'id' in n.attrib and 'entityName' in n.attrib}
    seffs={names[n.attrib['describedService__SEFF']]:n for n in tree.iter() if n.tag=='serviceEffectSpecifications__BasicComponent'}
    calls=list(usage.iter('operationSignature__EntryLevelSystemCall'))
    if len(calls)!=1:raise ValueError('audit requires the observed single usage entry')
    root=names[calls[0].attrib['href'].split('#')[-1]]
    cache={};active=set();traces={}
    def behavior(node):
        steps=[c for c in node if c.tag=='steps_Behaviour']
        indexed={c.attrib['id']:c for c in steps};starts=[c for c in steps if c.get(XSI)=='seff:StartAction']
        if len(indexed)!=len(steps) or len(starts)!=1:raise ValueError('ambiguous SEFF sequence')
        cursor=starts[0];visited=set();value=Fraction(1);factors=[]
        while cursor is not None:
            sid=cursor.attrib['id']
            if sid in visited:raise ValueError('cyclic action sequence')
            visited.add(sid);kind=cursor.get(XSI)
            if kind in ('seff:StartAction','seff:StopAction'):factor=Fraction(1);record=None
            elif kind=='seff:InternalAction':
                failures=[Fraction(c.attrib['failureProbability']) for c in cursor if c.tag=='internalFailureOccurrenceDescriptions__InternalAction']
                if len(failures)>1 or any(p<0 or p>1 for p in failures):raise ValueError('unhandled internal failure representation')
                factor=1-sum(failures);record=dict(kind='internal',success=float(factor),failure_exact=str(1-factor))
            elif kind=='seff:ExternalCallAction':
                called=names[cursor.attrib['calledService_ExternalService']]
                factor=operation(called);record=dict(kind='call',operation=called,success=float(factor))
            elif kind=='seff:LoopAction':
                bodies=[c for c in cursor if c.tag=='bodyBehaviour_Loop'];laws=[c for c in cursor if c.tag=='iterationCount_LoopAction']
                if len(bodies)!=1 or len(laws)!=1:raise ValueError('ambiguous loop body or law')
                inner,nested=behavior(bodies[0]);law=pmf(laws[0].attrib['specification'])
                factor=sum(p*inner**k for k,p in law)
                record=dict(kind='loop',success=float(factor),body_success=float(inner),
                    pmf=[dict(count=k,probability=float(p),serialized_exact=str(p)) for k,p in law],body=nested)
            else:raise ValueError('unhandled action semantics: '+str(kind))
            value*=factor
            if record is not None:factors.append(record)
            successor=cursor.get('successor_AbstractAction')
            if kind=='seff:StopAction' and successor:raise ValueError('stop action has successor')
            cursor=indexed[successor] if successor else None
        if visited!=set(indexed):raise ValueError('disconnected/unvisited SEFF action')
        return value,factors
    def operation(name):
        if name in cache:return cache[name]
        if name in active:raise ValueError('recursive operation graph outside audited class')
        active.add(name);value,factors=behavior(seffs[name]);active.remove(name)
        cache[name]=value;traces[name]=dict(success=float(value),factors=factors)
        return value
    value=operation(root)
    internal=[f for f in traces[root]['factors'] if f['kind']=='internal']
    if len(internal)!=1:raise ValueError('external wrapper has unexpected local-failure representation')
    local=1-Fraction(internal[0]['failure_exact'])
    child=Fraction(1)
    for f in traces[root]['factors']:
        if f['kind'] not in ('internal','loop'):raise ValueError('unexpected wrapper action')
    # Compute the child contribution without dividing by a possibly zero local
    # survival probability: replay only the root's loop subexpressions.
    for node in seffs[root]:
        if node.get(XSI)=='seff:LoopAction':
            inner,_=behavior(next(c for c in node if c.tag=='bodyBehaviour_Loop'))
            law=pmf(next(c for c in node if c.tag=='iterationCount_LoopAction').attrib['specification'])
            child*=sum(p*inner**k for k,p in law)
    if value!=local*child:raise ValueError('wrapper factorization failed')
    return dict(root=root,probability=float(value),serialized_probability_exact=str(value),
        wrapper_local_survival=float(local),modeled_subcalls_survival=float(child),
        operations=traces,operation_count=len(cache),hardware_failure_modeled_by_this_audit=False)
