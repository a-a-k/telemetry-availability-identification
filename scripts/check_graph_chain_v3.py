"""Small artificial A/B controls only; no application data or native archives."""
from __future__ import annotations
import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile

from telemetry_availability.graph_replay_v3 import build_model, probability, solve, Unsupported


def fixture(edges, replicas, probabilities, required=('target',), measured=None):
    """Normalized parent links with one trace per path-edge witness, no true p in metadata."""
    # A fixture may have disconnected components, but each trace root is the entry.
    # Obtain witnesses by walking the declared fixture graph, never used by solver.
    adjacency = {}
    for source,target,kind in edges:
        adjacency.setdefault(source, []).append((target,kind))
    spans, counter = [], 0
    def walk(service, parent, seen, kind):
        nonlocal counter
        ident = str(counter)
        counter += 1
        spans.append(dict(trace_id='control', span_id=ident, parent_span_id=parent,
                          service=service, operation_id='op', edge_type=kind))
        for target,edge_kind in adjacency.get(service, []):
            if target not in seen:
                walk(target, ident, seen|{target}, edge_kind)
    walk('entry', None, {'entry'}, 'sync')
    measured = list(probabilities) if measured is None else measured
    metadata = dict(purpose='controlled_demonstrator', trace_coverage='declared_complete_control',
        routing='ideal_static_reachability', repeat_semantics='same_static_state',
        primitive_ids=list(probabilities), replicas=replicas,
        unannotated_edge_law='deterministic_live',
        state_law='independent_bernoulli_primitives',
        operation=dict(id='op', entry='entry', required=list(required), semantics='immediate_sync_all_required'),
        observation_law=dict(version='direct-primitive-mcar-v1', measured_primitives=measured,
            conditional_on_success=False, mask_independent_of_state=True))
    observations = [dict(sample_id=i, values={name:i < round(100*probabilities[name]) for name in measured})
                    for i in range(100)]
    return metadata, spans, observations


def independent_oracle(probabilities, expression):
    """Independent exact rational enumeration of manually supplied Boolean expressions."""
    names = sorted(probabilities)
    total = Fraction(0)
    for bits in product((False,True), repeat=len(names)):
        state, weight = dict(zip(names,bits)), Fraction(1)
        for name,bit in zip(names,bits):
            p = Fraction(str(probabilities[name]))
            weight *= p if bit else 1-p
        if expression(state): total += weight
    return float(total)


def run_checks(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    records = []
    def check(name, data, p, expression):
        model = build_model(*data)
        actual = solve(model)
        expected = independent_oracle(p, expression)
        error = abs(actual['prediction']-expected)
        assert actual['status'] == 'estimated' and error <= 1e-12, (name,actual,expected)
        records.append(dict(name=name, level='A', actual=actual['prediction'], expected=expected,
                            absolute_error=error, states=actual['states_enumerated']))
        return model
    two = [('entry','a','sync'), ('a','target','sync'), ('entry','b','sync'), ('b','target','sync')]
    replicas = {'entry':[[]], 'a':[['a']], 'b':[['b']], 'target':[[]]}
    p = {'a':.8, 'b':.5}
    base = fixture(two, replicas, p)
    model = check('alternative_paths', base, p, lambda x:x['a'] or x['b'])
    serial = fixture([('entry','a','sync'),('a','b','sync')], {k:v for k,v in replicas.items() if k!='target'}, p, ('b',))
    check('serial_required', serial, p, lambda x:x['a'] and x['b'])
    common_replicas = deepcopy(replicas)
    common_replicas.update(a=[['g','a']], b=[['g','b']])
    common_p = dict(p,g=.7)
    check('shared_domain', fixture(two,common_replicas,common_p),common_p,lambda x:x['g'] and (x['a'] or x['b']))
    split_replicas = deepcopy(replicas)
    split_replicas.update(a=[['ga','a']],b=[['gb','b']])
    split_p = dict(p,ga=.7,gb=.7)
    check('placement_changes_law_bindings',fixture(two,split_replicas,split_p),split_p,
          lambda x:(x['ga'] and x['a']) or (x['gb'] and x['b']))
    # A different number of replicas, no fixed two-path template.
    three_p = dict(a=.8,b=.5,c=.25)
    three = fixture([('entry','target','sync')], {'entry':[[]],'target':[['a'],['b'],['c']]}, three_p)
    check('three_replicas',three,three_p,lambda x:x['a'] or x['b'] or x['c'])
    communication = fixture([('entry','target','sync')], {'entry':[[]],'target':[[]]}, {'c':.25})
    communication[0]['edge_gates']=[dict(source='entry',target='target',type='sync',factors=['c'])]
    check('live_process_failed_communication',communication,{'c':.25},lambda x:x['c'])
    optional = fixture([('entry','a','sync'),('a','b','async')], {k:v for k,v in replicas.items() if k!='target'}, p, ('a',))
    check('optional_async',optional,p,lambda x:x['a'])
    required_async = deepcopy(optional)
    required_async[0]['operation']['required']=['b']
    check('async_is_only_required_path_counterexample',required_async,p,lambda x:False)
    repeat = fixture([('entry','a','sync'),('entry','a','sync')], {'entry':[[]],'a':[['a']]}, {'a':.8}, ('a',))
    check('repeat_same_static_state',repeat,{'a':.8},lambda x:x['a'])
    changed = fixture([('entry','a','sync'),('entry','b','sync'),('b','target','sync')],replicas,p)
    check('remove_only_one_effective_path',changed,p,lambda x:x['b'])
    equivalent = fixture([('entry','bridge','sync'),('bridge','a','sync'),*two[1:]],dict(replicas,bridge=[[]]),p)
    check('deterministic_edge_subdivision_equivalence',equivalent,p,lambda x:x['a'] or x['b'])
    reversed_data = (deepcopy(base[0]),list(reversed(base[1])),list(reversed(base[2])))
    check('input_order_equivalence',reversed_data,p,lambda x:x['a'] or x['b'])
    # B: identical observation laws, different target, versus unidentified irrelevant p.
    ambiguous = fixture(two,replicas,p,measured=['a'])
    ambiguous_model = build_model(*ambiguous)
    result = solve(ambiguous_model)
    assert result['prediction'] is None and result['status']=='target_not_identifiable'
    assert all(abs(a-b)<1e-12 for a,b in zip(result['plug_in_missing_parameter_range'],[.8,1.]))
    witnesses = [probability(ambiguous_model,dict(a=.8,b=b)) for b in (.25,.75)]
    assert abs(witnesses[0]-.85)<1e-12 and abs(witnesses[1]-.95)<1e-12
    records.append(dict(name='same_observation_law_different_target',level='B',result=result,
        indistinguishable_parameters=[dict(a=.8,b=.25),dict(a=.8,b=.75)],target_witnesses=witnesses))
    irrelevant = deepcopy(optional)
    irrelevant[0]['observation_law']['measured_primitives']=['a']
    irrelevant = (irrelevant[0],irrelevant[1],[dict(sample_id=i,values={'a':i<80}) for i in range(100)])
    result = solve(build_model(*irrelevant))
    assert result['prediction']==.8 and result['target_population_identifiable'] and not result['parameters_population_identifiable']
    records.append(dict(name='nonunique_parameters_unique_target',level='B',result=result))
    insufficient = deepcopy(base)
    insufficient[2].clear()
    result = solve(build_model(*insufficient))
    assert result['status']=='insufficient_observations' and result['target_population_identifiable']
    records.append(dict(name='observable_but_no_samples',level='B',result=result))
    # Fixed small-sample design, no selection on accuracy: seed, N, masks enumerated below.
    for n in (20,200):
        for missing_rate in (0.,.5):
            rng = random.Random(771703+n+int(100*missing_rate))
            data = deepcopy(base)
            data[2].clear()
            for i in range(n):
                values = {}
                for name,value in p.items():
                    state = rng.random()<value
                    values[name] = None if rng.random()<missing_rate else state
                data[2].append(dict(sample_id=i,values=values))
            fitted = build_model(*data)
            prediction = solve(fitted)
            records.append(dict(name=f'mcar_n{n}_mask{missing_rate}',level='B',seed=771703+n+int(100*missing_rate),
                n=n,missing_rate=missing_rate, estimates=fitted['primitives'],
                parameter_errors={key:value['estimate']-p[key] for key,value in fitted['primitives'].items()},
                target_error=prediction['prediction']-.9, result=prediction,
                accuracy_gate='none; finite sample errors reported separately'))
    for name,key,value in [('eventual','operation',dict(base[0]['operation'],semantics='eventual')),
                           ('success_conditioning','observation_law',dict(base[0]['observation_law'],conditional_on_success=True)),
                           ('informative_mask','observation_law',dict(base[0]['observation_law'],mask_independent_of_state=False)),
                           ('execution_repeats','repeat_semantics','independent_per_call'),
                           ('incomplete_graph','trace_coverage','unknown')]:
        bad = deepcopy(base)
        bad[0][key] = value
        try: build_model(*bad)
        except Unsupported as error: records.append(dict(name=name,level='expected_unsupported',reason=str(error)))
        else: raise AssertionError(name)
    # Persist exactly allowed inputs. Builder and replay are separate OS processes.
    def write(path, value): path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for name,value in zip(('metadata','traces','observations'),base): write(out/(name+'.json'),value)
    build_cmd = [sys.executable,'-m','telemetry_availability.graph_replay_v3','build',
        '--metadata',str(out/'metadata.json'),'--traces',str(out/'traces.json'),
        '--observations',str(out/'observations.json'),'--output',str(out/'model.json')]
    subprocess.run(build_cmd,check=True,capture_output=True)
    # A fresh cwd contains only the saved model. Replay receives no input-data paths.
    with tempfile.TemporaryDirectory() as directory:
        replay_dir = Path(directory)
        (replay_dir/'model.json').write_bytes((out/'model.json').read_bytes())
        subprocess.run([sys.executable,'-m','telemetry_availability.graph_replay_v3','solve',
            '--model','model.json','--output','prediction.json'],cwd=replay_dir,check=True,capture_output=True)
        result=json.loads((replay_dir/'prediction.json').read_text())
        assert abs(result['prediction']-.9)<1e-12
        write(out/'prediction.json',result)
    records.append(dict(name='saved_model_separate_process',level='chain',prediction=result['prediction'],
        replay_input_files=['model.json'],original_observation_paths_passed=False,
        process_read_audit=False,scope='fresh working directory and explicit interface; not an OS sandbox'))
    report=dict(scope='artificial_controls_only',main_campaigns=0,checks=records,
        deterministic_absolute_tolerance=1e-12,monte_carlo_solver=False,
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            Path(__file__).resolve(), Path(__file__).resolve().parents[1]/'src/telemetry_availability/graph_replay_v3.py']},
        input_sha256={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in
            ('metadata.json','traces.json','observations.json','model.json','prediction.json')})
    # Source paths are portable, while preserving exact source-byte hashes.
    report['source_sha256']={Path(k).name:v for k,v in report['source_sha256'].items()}
    write(out/'checks.json',report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    result=run_checks(parser.parse_args().output)
    print(json.dumps(dict(checks=len(result['checks']),max_A_error=max(r['absolute_error'] for r in result['checks'] if r['level']=='A'),main_campaigns=0)))
