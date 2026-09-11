"""Aggregation controls: pair support, conversion accounting and full CSV census."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from itertools import product
from test_graph_execution_bdd_v1 import tiny_model
from telemetry_availability.graph_execution_model_v1 import solve
from telemetry_availability.exact_comparison_v2 import METHODS,REPRESENTATIONS,PHASES


class TableTests(unittest.TestCase):
    def test_full_tables_keep_missing_pair_and_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);src=root/'input';profile=src/'synthetic';profile.mkdir(parents=True)
            ex=solve(tiny_model())['estimates'];records=[];resources=[]
            for method,representation,rnd in product(METHODS,REPRESENTATIONS,range(3)):
                resources.append(dict(case_id='tiny',method=method,representation=representation,round=rnd,returncode=0,timed_out=False,
                    peak_rss_kib=1024,wall_seconds=1,user_seconds=0.5,system_seconds=0.1))
                for phase in PHASES:
                    row=dict(case_id='tiny',method=method,representation=representation,round=rnd,phase=phase,status='qualified',
                        estimates=deepcopy(ex),total_ns=100,kernel_ns=90,cpu_ns=75,conversion_ns=10,key_check_ns=5,construction_ns=20,
                        update_ns=5,query_including_update_ns=20,reconstructed=phase in ('initial','structure','restore'),
                        stats={},input_coordinates=7,input_categories=3)
                    if (method,representation,rnd,phase)==('cudd_fixed','original',0,'initial'):row.update(status='failed',error='declared synthetic failure')
                    records.append(row)
            config=dict(profiles=['synthetic'],expected_models=[1],expected_original_absences=[0],methods=list(METHODS),
                representations=list(REPRESENTATIONS),phases=list(PHASES),technical_rounds=3)
            data=dict(profile='synthetic',cases=[dict(case_id='tiny',axis='control',parameters={},expected={p:ex for p in PHASES})],absent=[],
                records=records,resources=resources,complete_census=True,qualified=False,verification_order='after_all_profile_streams')
            for name,value in [('protocol.json',config),('results.json',data),('environment.json',dict(cpu_info='model name: control',versions={}))]:
                (profile/name).write_text(json.dumps(value),encoding='utf-8')
            (src/'retention.json').write_text(json.dumps(dict(run_id=1,head='0'*40,artifacts=[dict(profile='synthetic')])))
            script=Path(__file__).resolve().parents[1]/'scripts/summarize_v3_exact_comparison_v2.py'
            for name in ('a','b'):
                subprocess.run([sys.executable,str(script),'--input',str(src),'--out',str(root/name)],check=True,capture_output=True)
            def read(name):
                with (root/'a'/(name+'.csv')).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
            self.assertEqual(len(read('measurements')),336);self.assertEqual(len(read('process_resources')),48)
            self.assertEqual(len(read('paired_ratios')),196);self.assertEqual(len(read('stage_summary')),112)
            self.assertEqual(len(read('failures')),1);self.assertEqual(len(read('projection_ratios')),56)
            pair=next(r for r in read('paired_ratios') if r['method']=='cudd_fixed' and r['baseline']=='ours_direct' and r['representation']=='original' and r['phase']=='initial')
            self.assertEqual(pair['paired_rounds'],'2');self.assertEqual(pair['other_over_ours'],'1.0')
            stage=next(r for r in read('stage_summary') if r['method']=='cudd_fixed' and r['representation']=='original' and r['phase']=='initial')
            self.assertEqual(stage['pairs_ours_direct'],'0');self.assertEqual(stage['qualified'],'2')
            self.assertAlmostEqual(float(stage['total_median_ms'])-float(stage['kernel_median_ms']),float(stage['conversion_median_ms']))
            for path in (root/'a').iterdir():self.assertEqual(path.read_bytes(),(root/'b'/path.name).read_bytes(),path.name)


if __name__=='__main__':unittest.main()
