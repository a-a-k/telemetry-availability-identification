"""Remote-only prospective H-EXEC intervention acquisition; no model fitting."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

from .h_exec_design_v1 import instrument_haproxy
from .live_validation_config import load_frozen_live_validation_config
from .live_placement_config import select_placement_pilot_profile
from .live_pilot_config import select_runtime_pilot_profile
from .live_fault_campaign import _service_containers, _inspect_containers
from .publication_stochastic_live import (_run_period, _semantic_sentinels, initialize_profile,
    wait_for_frontend, _collect_telemetry, _write_csv, _write_jsonl, REQUEST_FIELDS, HEALTH_FIELDS)
from .whole_operation_contract import http_exchange
from .v3_primary_projection import read, write, sha

CONFIG = Path('configs/h_exec_01_v2.json')


def now():
    return datetime.now(timezone.utc).isoformat()


def settings():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'H-EXEC acquisition is GitHub Actions only'
    value = read(CONFIG)
    for item in value['repository_locks']:
        assert sha(Path(item['path'])) == item['sha256'], item['path']
    return value


def instrument(out):
    source = read(out/'source-pinned-compose.json')
    original = (out/'source-haproxy.cfg').read_text()
    changed = instrument_haproxy(original)
    (out/'haproxy.cfg').write_bytes(changed.encode())
    admin = out/'admin'; admin.mkdir(exist_ok=True); admin.chmod(0o777)
    target = source['services']['product-catalog']
    found = 0
    for volume in target['volumes']:
        if volume.get('target') == '/usr/local/etc/haproxy/haproxy.cfg':
            volume['source'] = str((out/'haproxy.cfg').resolve()); found += 1
    assert found == 1
    target['volumes'].append(dict(type='bind', source=str(admin.resolve()), target='/var/run/study'))
    write(out/'pinned-compose.json', source)
    syntax = changed
    for replica in ('a', 'b'):
        host = 'product-catalog-replica-'+replica
        assert syntax.count(host) == 1
        syntax = syntax.replace(host, '127.0.0.1')
    (out/'syntax-only-haproxy.cfg').write_bytes(syntax.encode())
    write(out/'instrumentation-audit.json', dict(version='H-EXEC-route-log-admin-v1',
        source_compose_sha256=sha(out/'source-pinned-compose.json'), actual_compose_sha256=sha(out/'pinned-compose.json'),
        source_haproxy_sha256=sha(out/'source-haproxy.cfg'), actual_haproxy_sha256=sha(out/'haproxy.cfg'),
        syntax_only_sha256=sha(out/'syntax-only-haproxy.cfg'),
        syntax_control_substitutions='only two backend DNS names replaced with loopback for isolated syntax checking',
        ordinary_policy_changed=False, repair_arm_changes_policy_only_at_declared_intervention=True))


def admin_socket_address(out):
    # Linux sun_path bounds the supplied name, not the resolved inode location.
    # The fixed workflow output is inside cwd; a relative name avoids the long
    # GitHub workspace prefix and never changes process cwd while threads run.
    relative=(out/'admin/admin.sock').resolve().relative_to(Path.cwd().resolve())
    if len(os.fsencode(relative))>=108:
        raise ValueError('relative admin socket address still exceeds Linux sun_path')
    return str(relative)


def admin_command(out, command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
        stream.settimeout(5)
        stream.connect(admin_socket_address(out))
        stream.sendall((command+'\n').encode()); stream.shutdown(socket.SHUT_WR)
        data = bytearray()
        while True:
            block = stream.recv(65536)
            if not block:
                break
            data.extend(block)
        return data.decode()


def static_controls(base_url, period, duration, specification, result):
    started = time.monotonic()
    for index in range(duration//2):
        offset = index*2
        time.sleep(max(0, started+offset-time.monotonic()))
        tick = time.monotonic(); stamp = now(); status = None; value = b''; error = ''
        try:
            status, value = http_exchange(base_url+'/favicon.ico', data=None, content_type=None,
                                         headers={}, deadline=tick+2)
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        blob = hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest()
        result.append(dict(period=period, index=index, scheduled_offset_seconds=offset, started_at=stamp,
            completed_at=now(), latency_ms=(time.monotonic()-tick)*1000, status=status, bytes=len(value),
            git_blob=blob, success=(status==200 and len(value)==specification['bytes'] and
                                  blob==specification['git_blob'] and not error), error=error))


def acquire(out, frozen, phase, block, slot):
    cell = next(r for r in frozen['assignments'][phase] if r['block']==block and r['slot']==slot)
    arm = cell['arm']; profile_id = 'opentelemetry_demo'
    config = load_frozen_live_validation_config('configs/m7_frozen_live.yaml').stochastic
    assert config.request_rate_per_second == 4
    profile = select_placement_pilot_profile(config.placement, profile_id)
    runtime = select_runtime_pilot_profile(config.placement.runtime, profile_id)
    compose = out/'pinned-compose.json'
    requests = []; responses = []; health = []; controls = []; periods = []; events = []; boundaries = []
    started = now(); paused = False; error = None
    identity = dict(hypothesis='H-EXEC-01', version='v2', phase=phase, block=block, slot=slot, arm=arm,
        source_head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'], main_campaigns=0)
    write(out/'identity.json', identity)
    containers = _service_containers(compose, (*profile.replica_services.values(), profile.target_service))
    replica_a = containers[profile.replica_services['a']]
    replica_b = containers[profile.replica_services['b']]
    def boundary(label):
        snapshots = _inspect_containers([replica_a, replica_b])
        probe = subprocess.run(['docker','exec',replica_b,'/bin/grpc_health_probe','-addr=:3550'],
                               capture_output=True, text=True, timeout=5)
        boundaries.append(dict(label=label, observed_at=now(), b_readiness_returncode=probe.returncode,
            b_readiness_stdout=probe.stdout, b_readiness_stderr=probe.stderr,
            replicas={name:dict(running=snapshots[cid]['State']['Running'], paused=snapshots[cid]['State']['Paused'],
                health=snapshots[cid]['State'].get('Health',{}).get('Status')) for name,cid in [('a',replica_a),('b',replica_b)]}))
    def pause():
        nonlocal paused
        record = dict(action='pause_a', started_at=now())
        command = subprocess.run(['docker','pause',replica_a], capture_output=True, text=True, timeout=15)
        record.update(completed_at=now(), returncode=command.returncode, stdout=command.stdout, stderr=command.stderr)
        events.append(record); command.check_returncode(); paused = True
    try:
        wait_for_frontend(runtime, config.placement.runtime.readiness_timeout_seconds)
        time.sleep(config.placement.runtime.post_start_stabilization_seconds)
        initialize_profile(runtime)
        namespace = f'h-exec-v2-{phase}-b{block}-slot{slot}-'+os.environ['GITHUB_RUN_ID']
        sentinels, sent_responses, effect = _semantic_sentinels(config,profile,runtime,'colocated','N',block,namespace)
        _write_csv(out/'sentinel-requests.csv',REQUEST_FIELDS,sentinels)
        _write_jsonl(out/'sentinel-responses.jsonl',sent_responses); write(out/'semantic-effect-audit.json',effect)
        for period,duration in [('baseline',60),('calibration',30),('test',30)]:
            if period=='calibration' and arm in ('settled','repaired'):
                pause()
                if arm=='repaired':
                    event = dict(action='disable_route_a', started_at=now())
                    response = admin_command(out, 'disable server study_replicas/replica_a')
                    event.update(completed_at=now(),response=response); events.append(event)
                    (out/'repair-admin-stats.csv').write_text(admin_command(out,'show stat'))
                    assert not response.strip(), response
            if period=='test' and arm=='transition':
                pause()
            boundary('before_'+period)
            control_thread = threading.Thread(target=static_controls,
                args=(runtime.base_url,period,duration,frozen['static_control'],controls))
            control_thread.start()
            try:
                req, resp, unused_events, ticks, metadata = _run_period(config,profile,runtime,'colocated',
                    'H_EXEC_01',block,period,duration,compose,(),base_seed=frozen['workload_seeds'][phase],request_namespace=namespace)
                assert not unused_events
                requests.extend(req); responses.extend(resp); health.extend(ticks)
                periods.append(dict(period=period,**metadata))
            finally:
                control_thread.join(timeout=duration+5)
                assert not control_thread.is_alive()
            boundary('after_'+period)
        time.sleep(frozen['post_request_drain_seconds'])
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if paused:
            release = subprocess.run(['docker','unpause',replica_a], capture_output=True, text=True, timeout=15)
            events.append(dict(action='release_a', completed_at=now(), returncode=release.returncode,
                               stdout=release.stdout, stderr=release.stderr))
        _write_csv(out/'requests.csv',REQUEST_FIELDS,requests); _write_jsonl(out/'responses.jsonl',responses)
        _write_csv(out/'health.csv',HEALTH_FIELDS,health)
        write(out/'static-controls.json',controls); write(out/'interventions.json',events)
        write(out/'boundaries.json',boundaries); write(out/'periods.json',periods)
        write(out/'acquisition-summary.json',dict(identity=identity,error=error,attempts=len(requests),
            static_controls=len(controls),period_operation_counts=dict(Counter(r['period']+'/'+r['operation'] for r in requests)),
            completed_at=now(),new_main_campaigns=0))
    time.sleep(config.trace_flush_seconds)
    native_count, telemetry_error = _collect_telemetry(runtime,datetime.fromisoformat(started),out)
    logs = subprocess.check_output(['docker','compose','-f',str(compose),'logs','--no-color','--no-log-prefix',profile.target_service])
    (out/'proxy-routes.log').write_bytes(logs)
    write(out/'telemetry-summary.json',dict(native_count=native_count,error=telemetry_error))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('instrument','acquire')); parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--phase',choices=('qualification','study'),default='qualification')
    parser.add_argument('--block',type=int,default=0); parser.add_argument('--slot',type=int,default=0)
    args = parser.parse_args(); frozen = settings(); args.out.mkdir(parents=True,exist_ok=True)
    if args.stage=='instrument':
        instrument(args.out)
    else:
        acquire(args.out,frozen,args.phase,args.block,args.slot)


if __name__=='__main__':
    main()
