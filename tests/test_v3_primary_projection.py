from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from telemetry_availability.v3_primary_projection import project,DECLARATION_FIELDS,SPAN_FIELDS,write,sha,VERSION


class OrdinaryProjectionTests(unittest.TestCase):
    def fixture(self):
        deployment={key:None for key in DECLARATION_FIELDS}
        deployment.update(profile='tiny-artificial',placement='colocated',failure_law='N',repetition=0)
        deployment['source_declared_dependencies']={'create':[]}
        request=dict(request_id='r',trace_id='t',operation='create',period='calibration',started_at='1',
                     completed_at='2',semantic_success=True,timed_out=False)
        health=dict(observed_at='1',elapsed_seconds=0,period='calibration',
            replica_a_backend_status='UP',replica_a_backend_check_status='L7OK',
            replica_b_backend_status='DOWN',replica_b_backend_check_status='L7TOUT',
            replica_a_running=True,replica_a_paused=False,replica_a_network_count=3)
        native=dict(calibration_only=True,selected_trace_ids=['t'],spans={'t':[]})
        return deployment,[request],[health],native

    def test_privileged_state_changes_cannot_change_primary_data(self):
        original=self.fixture();changed=deepcopy(original)
        changed[0].update(usable=False,test_health_ticks=0,test_success_rate=.99)
        changed[2][0].update(replica_a_running=False,replica_a_paused=True,replica_a_network_count=0,
                             proxy_running=False,proxy_paused=True,injection_schedule=[1,2,3])
        self.assertEqual(project(*original)[0],project(*changed)[0])

    def test_ordinary_probe_and_outcome_changes_remain_visible(self):
        original=self.fixture();changed=deepcopy(original)
        changed[1][0]['semantic_success']=False
        changed[2][0]['replica_a_backend_status']='DOWN'
        self.assertNotEqual(project(*original)[0],project(*changed)[0])

    def test_closed_period_and_foreign_native_ids_are_rejected(self):
        for kind in ('request','health','native'):
            data=self.fixture()
            if kind=='request':data[1][0]['period']='test'
            elif kind=='health':data[2][0]['period']='test'
            else:data[3]['spans']['closed-test-trace']=[]
            with self.assertRaises(ValueError):project(*data)

    def test_native_privileged_tags_are_removed_but_db_peer_survives(self):
        original=self.fixture()
        span={key:None for key in SPAN_FIELDS}
        span.update(trace_id='t',span_id='s',parent_id='',service='visits',native_kind='3',native_links=[],
                    attributes={'db.system':'mysql','server.address':'database','study.fault':'secret'},
                    resource_attributes={'service.instance.id':'visits-a','study.replica':'a','docker.paused':True})
        original[3]['spans']['t']=[span]
        changed=deepcopy(original)
        changed[3]['spans']['t'][0]['attributes']['study.fault']='different'
        changed[3]['spans']['t'][0]['resource_attributes']['docker.paused']=False
        left=project(*original)[0];right=project(*changed)[0]
        self.assertEqual(left,right)
        self.assertEqual(left['native.json']['spans']['t'][0]['attributes']['db.system'],'mysql')

    def test_actual_consumer_read_boundary_blocks_legacy_and_closed_data(self):
        data,_=project(*self.fixture())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'ordinary';output=Path(directory)/'output';output.mkdir()
            for name,value in data.items():write(root/name,value)
            write(root/'seal.json',dict(version=VERSION,files={name:sha(root/name) for name in data}))
            forbidden=Path(directory)/'test-outcomes.json';forbidden.write_text('closed')
            program='''
import sys
from pathlib import Path
from telemetry_availability.v3_graph_input_inventory import ReadBoundary,inventory
root,output,closed=map(lambda x:Path(x).resolve(),sys.argv[1:])
boundary=ReadBoundary(root,output);sys.addaudithook(boundary.hook)
try:
    result=inventory(root)
    assert len(boundary.reads)==6 and result['model_fits']==0
    try:closed.read_text()
    except PermissionError:pass
    else:raise AssertionError('closed file read was allowed')
finally:boundary.active=False
assert boundary.blocked==[str(closed)]
'''
            result=subprocess.run([sys.executable,'-c',program,str(root),str(output),str(forbidden)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__': unittest.main()
