"""Verify and tabulate the one compact artificial model-scaling result."""
import argparse
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess

from archive_h_exec_evidence_v1 import require
import retain_v3_comparison_compact_v4 as transport


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',type=int,required=True)
    args=parser.parse_args();run=transport.read_api(f'actions/runs/{args.run}')
    require(run['path']=='.github/workflows/v3-model-scaling-benchmark-v1.yml'
            and run['run_attempt']==1 and run['status']=='completed' and run['conclusion']=='success', 'wrong or incomplete source run')
    artifacts=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    require(len(artifacts)==1 and artifacts[0]['name']==f'v3-model-scaling-compact-{args.run}'
            and artifacts[0]['workflow_run']['head_sha']==run['head_sha'] and artifacts[0]['size_in_bytes']<=1_000_000,
            'compact artifact census/identity differs')
    artifact=artifacts[0];raw=transport.api(f'actions/artifacts/{artifact["id"]}/zip')
    members=transport.check_archive(raw,artifact,{'compact.json'})
    require(set(members)=={'compact.json'},'compact member census differs')
    result=json.loads(members['compact.json'])
    source=subprocess.check_output(['git','show',run['head_sha']+':src/telemetry_availability/graph_execution_model_v1.py'])
    require(result['head']==run['head_sha'] and result['run_id']==args.run and result['artificial_only']
            and result['scientific_source_sha256']==sha256(source).hexdigest()
            and len(result['records'])==16,'result source/scope differs')
    expected=[('graph_nodes_complete_observations',n,0,False) for n in (4,8,16,32,48)]
    expected += [('graph_nodes_masked_completion',n,10,True) for n in (4,8,16,32,48)]
    expected += [('unknown_controls',16,k,True) for k in (0,2,4,6,8,10)]
    require([(r['axis'],r['nodes'],r['unknown_controls'],r['masked_completion']) for r in result['records']]==expected,'planned size/mask grid differs')
    for row in result['records']:
        require(row['exact_results_verified'] and len(row['solve_nanoseconds'])==7,'unverified or incomplete solve repetitions')
        require(row['evaluated_states']==(2**(row['unknown_controls']+1) if row['masked_completion'] else 16), 'reduced state count differs')
        require(row['full_fiber_states']==(2**(row['unknown_controls']+row['nodes']) if row['masked_completion'] else 16), 'full fiber count differs')
        require((row['lower_exact'],row['upper_exact'])==(('0','1') if row['masked_completion'] else ('1/16','1/16')), 'analytic oracle differs')
    out=Path(f'docs/evidence/v3-model-scaling-{args.run}')
    transport.persist(out/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    for name,data in {'compact.zip':raw,'compact.json':members['compact.json'],'run-api.json':transport.encoded(run),'artifact-api.json':transport.encoded(artifact)}.items():
        transport.persist(out/name,data)
    rows=[]
    for row in result['records']:
        rows.append({k:v for k,v in row.items() if k!='solve_nanoseconds'})
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    table=Path(f'docs/tables/v3-model-scaling-{args.run}');table.mkdir(parents=True,exist_ok=True)
    transport.persist(table/'.gitattributes',b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    transport.persist(table/'model-scaling.csv',stream.getvalue().encode())
    note='''# Finite exact-model size and mask measurements

All16 artificial cases, one untimed warmup and seven measured solves each. Raw nanoseconds and exact-result checks are in the compact source. Nodes/edges, observation categories and unknown controls are explicit. Full-fiber counts are combinatorial counts, not measured brute-force runtimes. The 64-coordinate and 10-control implementation caps remain. These measurements do not compare PMX on artificial structures or establish a universal asymptotic law.
'''
    transport.persist(table/'README.md',note.encode())
    record=dict(run_id=args.run,head=run['head_sha'],artifact_id=artifact['id'],compact_zip_sha256=sha256(raw).hexdigest(),
                compact_source_sha256=sha256(members['compact.json']).hexdigest(),table_sha256=sha256(stream.getvalue().encode()).hexdigest(),
                grid=16,measured_solves=112,local_solver_execution=False,analytic_oracles_and_state_counts_verified=True)
    transport.persist(out/'retention.json',transport.encoded(record))
    transport.persist(table/'provenance.json',transport.encoded(record))
    print(json.dumps(record));print(json.dumps(rows,indent=2))


if __name__=='__main__':main()
