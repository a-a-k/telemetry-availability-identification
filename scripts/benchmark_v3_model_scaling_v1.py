"""Prespecified artificial model-size/mask scaling of the unchanged exact core."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from telemetry_availability.graph_execution_model_v1 import identify,solve


def model(nodes,unknown_controls=0,masked_completion=False):
    names=[f's{i}' for i in range(nodes)]
    graph=dict(services=names,edges=[dict(id=f'e{i}',source=names[i-1],target=names[i],type='sync',factors=[]) for i in range(1,nodes)])
    signals=[f'x{i}' for i in range(9)]
    replicas={name:[[]] for name in names};replicas[names[0]]=[signals]
    bindings=[dict(edge_id=f'e{i}',signal=f'completed_e{i}') for i in range(1,nodes)]
    completion=['entry_completed']+[r['signal'] for r in bindings]
    controls=signals+['timely'];observations=[]
    for category in range(1 if masked_completion else 16):
        row={signal:True for signal in controls+completion}
        for signal in controls[:unknown_controls]:row[signal]=None
        if masked_completion:
            for signal in completion:row[signal]=None
        else:
            for bit,signal in enumerate(completion[:4]):row[signal]=bool(category & (1<<bit))
        observations.append(row)
    return identify(graph,replicas,dict(id='synthetic_chain',entry=names[0],required=names,
                    semantics='immediate_sync_all_required'),observations,[],bindings,
                    dict(scope='artificial computational model-size and missingness controls; not application observations'))


def cases():
    rows=[dict(axis='graph_nodes_complete_observations',nodes=n,unknown_controls=0,masked_completion=False)
          for n in (4,8,16,32,48)]
    rows += [dict(axis='graph_nodes_masked_completion',nodes=n,unknown_controls=10,masked_completion=True)
             for n in (4,8,16,32,48)]
    rows += [dict(axis='unknown_controls',nodes=16,unknown_controls=k,masked_completion=True)
             for k in (0,2,4,6,8,10)]
    return rows


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('performance measurements run remotely')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    result=dict(version='v3-model-scaling-benchmark-v1',run_id=int(os.environ['GITHUB_RUN_ID']),
        head=os.environ['GITHUB_SHA'],scientific_source_sha256=sha256(Path('src/telemetry_availability/graph_execution_model_v1.py').read_bytes()).hexdigest(),
        python=sys.version,platform=platform.platform(),cpu_count=os.cpu_count(),
        cpu_info=Path('/proc/cpuinfo').read_text(),memory_info=Path('/proc/meminfo').read_text(),
        artificial_only=True,real_application_campaigns=0,untimed_warmups=1,measured_repetitions=7,records=[])
    for case in cases():
        m=model(case['nodes'],case['unknown_controls'],case['masked_completion'])
        reference=solve(m)
        expected=('0','1') if case['masked_completion'] else ('1/16','1/16')
        actual=reference['estimates']['execution']
        assert (actual['lower_exact'],actual['upper_exact'])==expected
        predicted_states=2**(case['unknown_controls']+1) if case['masked_completion'] else 16
        assert reference['evaluated_states']==predicted_states
        samples=[]
        for _ in range(7):
            started=time.perf_counter_ns();current=solve(m);samples.append(time.perf_counter_ns()-started)
            assert current==reference
        row=dict(**case,nodes_measured=len(m['graph']['services']),edges=len(m['graph']['edges']),
            coordinates=len(m['signal_ids']),categories=len(m['observation_categories']),
            evaluated_states=reference['evaluated_states'],
            full_fiber_states=sum(c['full_fiber_size'] for c in reference['category_certificates']),
            lower_exact=actual['lower_exact'],upper_exact=actual['upper_exact'],
            solve_nanoseconds=samples,median_seconds=statistics.median(samples)/1e9,
            min_seconds=min(samples)/1e9,max_seconds=max(samples)/1e9,exact_results_verified=True)
        result['records'].append(row)
        print(json.dumps(row),flush=True)
        (args.out/'compact.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())


if __name__=='__main__':main()
