"""Focused transport-rule regression with the qualified HAProxy image."""
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from telemetry_availability.v4_retry_controls_v2 import inject_rules
from telemetry_availability.petclinic_stochastic_preflight_v2 import config_objects
from telemetry_availability.v3_primary_projection import write


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('native proxy control is remote only')
    _,runtime,_,_,_=config_objects()
    image=runtime['images']['proxy']
    root=Path('workflow-results/proxy-regression').resolve();root.mkdir(parents=True,exist_ok=True)
    config=inject_rules('''global
  maxconn 20
defaults
  mode http
  timeout connect 1s
  timeout client 3s
  timeout server 3s
  retries 0
frontend visits
  bind *:18808
  default_backend study_replicas
backend study_replicas
  server fixture 127.0.0.1:18809
''')
    (root/'haproxy.cfg').write_text(config)
    compose={'services':{'proxy':{'image':image,'network_mode':'host',
        'volumes':[str(root/'haproxy.cfg')+':/usr/local/etc/haproxy/haproxy.cfg:ro']}}}
    write(root/'compose.json',compose)
    base=['docker','compose','-f',str(root/'compose.json')]
    server=subprocess.Popen(['python','-m','http.server','18809','--bind','127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        subprocess.run([*base,'run','--rm','proxy','haproxy','-c','-f','/usr/local/etc/haproxy/haproxy.cfg'],check=True)
        subprocess.run([*base,'up','-d'],check=True)
        time.sleep(2)
        statuses=[]
        for request_id in ('control-retry-a','control-retry-a','control-normal-a','control-retry-b','control-retry-b'):
            request=Request('http://127.0.0.1:18808/',headers={'X-Study-Request-Id':request_id})
            try:
                with urlopen(request,timeout=5) as response:statuses.append(response.status)
            except HTTPError as exc:statuses.append(exc.code)
        write(root/'result.json',dict(image=image,statuses=statuses,expected=[503,200,200,503,200],
            artificial_transport_control=True,application_outcomes_used=False))
        if statuses!=[503,200,200,503,200]:raise ValueError('prespecified first-attempt proxy rule failed')
        print('Qualified proxy: first request 503, second and normal requests forwarded; independent IDs checked.')
    finally:
        subprocess.run([*base,'down'],check=False)
        server.terminate();server.wait(timeout=10)


if __name__=='__main__':main()
