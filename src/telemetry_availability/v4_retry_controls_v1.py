"""Eight prespecified Petclinic requests after the forecasting periods end."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import time

from .petclinic_runtime_v3 import command
from .petclinic_stochastic_preflight_v2 import request
from .petclinic_contract_v2 import finalize_write
from .live_fault_campaign import _service_containers
from .v3_primary_projection import write, sha
from .v4_primary_capture_v1 import capture_sql, health_sampler

RULES='''  stick-table type string len 256 size 100 expire 10m store http_req_cnt
  acl study_retry req.hdr(X-Study-Request-Id) -m sub control-retry
  http-request track-sc0 req.hdr(X-Study-Request-Id) if study_retry
  http-request return status 503 content-type text/plain string study-first-transport-attempt if study_retry { sc_http_req_cnt(0) eq 1 }
'''


def run(config,runtime_config,profile,runtime,identity,path,namespace,fixture,out):
    # The regular calibration/test periods and test SQL snapshot have finished.
    # Only this separate diagnostic phase gets the one-shot proxy response rule.
    time.sleep(70)
    proxy=path.parent/'haproxy.cfg';original=proxy.read_text(encoding='utf-8')
    if original.count('backend study_replicas\n')!=1: raise ValueError('unexpected qualified proxy template')
    write(out/'proxy-before.json',dict(sha256=sha(proxy),text=original))
    proxy.write_text(original.replace('backend study_replicas\n','backend study_replicas\n'+RULES),encoding='utf-8')
    base=['docker','compose','-f',str(path)]
    command([*base,'run','--rm','--no-deps','visits-service','haproxy','-c','-f','/usr/local/etc/haproxy/haproxy.cfg'],log=out/'proxy-syntax.log')
    command([*base,'up','-d','--no-deps','--force-recreate','visits-service'],log=out/'proxy-restart.log')
    time.sleep(5)
    write(out/'proxy-after.json',dict(sha256=sha(proxy),text=proxy.read_text(encoding='utf-8'),
        matching='only control-retry request IDs; first request is answered locally with 503 before receiver forwarding'))
    services=(*profile.replica_services.values(),profile.target_service)
    containers=_service_containers(path,services);health=[];stop=threading.Event();began=time.monotonic()
    sampler=threading.Thread(target=health_sampler,args=(config,profile,identity['placement'],identity['failure_law'],
        identity['repetition'],'control',path,containers,began,stop,health))
    sampler.start();rows=[]
    try:
        for index,kind in enumerate(('normal','retry')*4):
            row=request(config,runtime_config,profile,runtime,identity,'control',index,'create_visit',
                time.monotonic()-began,namespace+'-control-'+kind,fixture)
            row['control_kind']=kind;rows.append(row)
            time.sleep(1)
    finally:
        stop.set();sampler.join(timeout=30)
    if sampler.is_alive(): raise ValueError('control sampler did not terminate')
    persisted=capture_sql(path,out/'sql.json','control')
    for row in rows: finalize_write(row,persisted.get(row['marker'],[]),fixture)
    write(out/'requests.json',rows);write(out/'health.json',health)
    return dict(requests=rows,health=health,sql=out/'sql.json')
