import csv
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from telemetry_availability.health_prefix_reanalysis import FIELDS, load_learner
from telemetry_availability.live_validation_analysis import load_qualified_cell
from telemetry_availability.isolated_stochastic_fit import load_cell


class HistoricalPrefixLoaderTests(unittest.TestCase):
    def fixture(self,root,family):
        meta=dict(profile='spring_petclinic_microservices' if family=='Petclinic' else 'opentelemetry_demo',
                  placement='colocated',failure_law='NCD',repetition=0)
        manifest=dict(meta)
        if family=='Petclinic':manifest['usable']=True
        deployment=dict(target_service='target',backend_success_check_statuses=['L7OK'])
        for name,value in [('learner/manifest.json',manifest),('audit/boundary.json',dict(usable=True)),
                           ('learner/deployment.json',deployment)]:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
        request=dict(period='calibration',request_id='r1',operation='checkout',started_at='2026-09-08T00:00:00+00:00',
                     semantic_success='true',trace_present='true',span_count='2',services='entry;target',target_replicas='a')
        health=dict(period='calibration',observed_at=request['started_at'],elapsed_seconds='0')
        for rep in ('a','b'):
            for key,value in dict(observed='true',running='true',paused='false',network_count='1',backend_status='UP',
                                  backend_check_status='* L7OK' if family=='Petclinic' else '* L4OK').items():
                health[f'replica_{rep}_{key}']=value
        for name,row in [('learner/requests.csv',request),('learner/health.csv',health)]:
            with (root/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerow(row)
        (root/'learner/topology-edges.csv').write_text('source,target\nentry,target\n')
        seal=dict(metadata=dict(meta,family=family),files={name:sha256((root/name).read_bytes()).hexdigest() for name in FIELDS})
        (root/'seal.json').write_text(json.dumps(seal))
        return request,health

    def test_legacy_loader_equivalence_for_both_schemas(self):
        for family in ('M7','Petclinic'):
            with self.subTest(family=family),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);request,health=self.fixture(root,family)
                legacy,corrected,_=load_learner(root)
                self.assertEqual(legacy.health[0].signals,(1,1,0,0))
                self.assertEqual(corrected.health[0].signals,(1,1,1,1))
                if family=='Petclinic':reference=load_cell(root)
                else:
                    (root/'evaluator').mkdir()
                    (root/'evaluator/test-requests.csv').write_text('operation,started_at,semantic_success\n')
                    (root/'evaluator/test-health.csv').write_text((root/'learner/health.csv').read_text().splitlines()[0]+'\n')
                    reference=load_qualified_cell(root)
                self.assertEqual(legacy,reference)
                self.assertEqual(replace(corrected,health=legacy.health),legacy)

    def test_physical_evaluator_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,'M7')
            (root/'test-requests.csv').write_text('closed\n')
            with self.assertRaises(AssertionError):load_learner(root)


if __name__=='__main__':
    unittest.main()
