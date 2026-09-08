"""Exact artificial observation-law witnesses; never an application estimator."""
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path


def observation_law(g, xa, xb, shared):
    names=['g','a','b'] if shared else ['ga','gb','a','b']
    probabilities=[g,xa,xb] if shared else [g,g,xa,xb]
    result={str((a,b)):F(0) for a,b in product((False,True),repeat=2)}
    for bits in product((False,True),repeat=len(names)):
        state=dict(zip(names,bits));weight=F(1)
        for bit,p in zip(bits,probabilities): weight*=p if bit else 1-p
        a=state['g' if shared else 'ga'] and state['a']
        b=state['g' if shared else 'gb'] and state['b']
        result[str((a,b))]+=weight
    return result


def main():
    rows=[]
    for g in (F(4,5),F(9,10)):
        xa=F(3,5)/g;xb=F(2,5)/g
        source=observation_law(g,xa,xb,False)
        target=observation_law(g,xa,xb,True)
        rows.append(dict(g=str(g),xa=str(xa),xb=str(xb),
            source_joint={k:str(v) for k,v in source.items()},
            source_availability=str(1-source[str((False,False))]),
            target_availability=str(1-target[str((False,False))])))
    assert rows[0]['source_joint']==rows[1]['source_joint']
    assert rows[0]['source_availability']==rows[1]['source_availability']=='19/25'
    assert rows[0]['target_availability']=='7/10' and rows[1]['target_availability']=='11/15'
    result=dict(scope='artificial population model, not applied causal effect',
        enumeration='independent exact Fraction enumeration',witnesses=rows,
        same_source_observation_law=True,different_target=True,range_is_confidence_interval=False)
    path=Path('docs/evidence/graph-chain-v3/compound-transfer-controls.json')
    path.write_text(json.dumps(result,indent=2)+'\n')
    print('Same full source law; source 19/25; two target witnesses 7/10 and 11/15.')


if __name__=='__main__': main()
