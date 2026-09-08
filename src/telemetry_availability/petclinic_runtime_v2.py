"""Build and qualify the pinned Petclinic runtime in GitHub Actions only."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

from .petclinic_contract_v2 import CONFIG, execute, finalize_write, fixture_from_source, adapt_fixture
from .pmx_observed_operations import read_native


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def command(args, *, cwd=None, log=None):
    started = time.monotonic()
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w') as stream:
            subprocess.run(['/usr/bin/time', '-v', '-o', str(log)+'.resource-usage.txt', *args],
                           cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, check=True)
        return dict(command=args, elapsed_seconds=time.monotonic()-started)
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def build(source, out, config):
    assert command(['git', 'rev-parse', 'HEAD'], cwd=source) == config['source_commit']
    assert not command(['git', 'status', '--porcelain'], cwd=source)
    out.mkdir(parents=True, exist_ok=True)
    context = out/'image-context'
    context.mkdir()
    agent = context/'opentelemetry-javaagent.jar'
    with urllib.request.urlopen(config['java_agent']['url']) as response:
        agent.write_bytes(response.read())
    assert digest(agent) == config['java_agent']['sha256']
    costs = [command(['mvn', '-B', '-ntp', '-DskipTests', '-pl',
        ','.join('spring-petclinic-'+name for name in config['modules']), '-am', 'package'],
        cwd=source, log=out/'logs/maven-build.log')]
    jars = {}
    for name in config['modules']:
        jar = source/f'spring-petclinic-{name}/target/spring-petclinic-{name}-4.0.1.jar'
        assert jar.is_file()
        shutil.copyfile(jar, context/(name+'.jar'))
        jars[name] = dict(sha256=digest(jar), bytes=jar.stat().st_size)
    (context/'Dockerfile').write_text('FROM '+config['images']['java']+'\nWORKDIR /app\nCOPY *.jar /app/\n')
    tag = 'petclinic-study:'+config['source_commit'][:12]
    costs.append(command(['docker', 'build', '--platform', 'linux/amd64', '-t', tag, str(context)],
                         log=out/'logs/image-build.log'))
    # The exact image is reused by subsequent controls/campaigns without rebuilding application jars.
    costs.append(command(['docker', 'save', '-o', str(out/'petclinic-image.tar'), tag], log=out/'logs/image-save.log'))
    fixture = fixture_from_source(source)
    write(out/'fixture.json', fixture)
    sql = out/'sql'
    sql.mkdir()
    for i, service in enumerate(('customers', 'visits', 'vets')):
        for j, kind in enumerate(('schema', 'data')):
            origin = source/f'spring-petclinic-{service}-service/src/main/resources/db/mysql/{kind}.sql'
            shutil.copyfile(origin, sql/f'{i}{j}-{service}-{kind}.sql')
    manifest = dict(stage=config['stage'], source_commit=config['source_commit'],
        study_head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'], config_sha256=digest(CONFIG),
        image_tag=tag, image=json.loads(command(['docker', 'image', 'inspect', tag]))[0], jars=jars,
        java_agent_sha256=digest(agent), costs=costs, files={p.relative_to(out).as_posix():digest(p)
            for p in out.rglob('*') if p.is_file() and 'image-context' not in p.parts})
    write(out/'build-manifest.json', manifest)


def compose(bundle, out, config, placement='colocated'):
    out.mkdir(parents=True, exist_ok=True)
    traces = out/'traces'
    traces.mkdir(exist_ok=True)
    traces.chmod(0o777)
    image = json.loads((bundle/'build-manifest.json').read_text())['image_tag']
    collector = dict(receivers=dict(otlp=dict(protocols=dict(http=dict(endpoint='0.0.0.0:4318')))),
        processors=dict(batch=dict(timeout='1s')),
        exporters=dict(file=dict(path='/output/native.jsonl', format='json')),
        service=dict(pipelines=dict(traces=dict(receivers=['otlp'], processors=['batch'], exporters=['file']))))
    write(out/'collector.json', collector)
    (out/'haproxy.cfg').write_text('''global
  maxconn 1024
defaults
  mode http
  timeout connect 500ms
  timeout client 3s
  timeout server 3s
  retries 0
resolvers docker
  nameserver dns 127.0.0.11:53
  resolve_retries 3
  timeout retry 1s
  hold valid 1s
frontend visits
  bind *:8080
  default_backend study_replicas
frontend stats
  bind *:8404
  stats enable
  stats uri /stats
backend study_replicas
  balance roundrobin
  option http-server-close
  option redispatch
  server replica_a visits-service-replica-a:8080 check inter 500ms fall 1 rise 1 resolvers docker init-addr libc,none
  server replica_b visits-service-replica-b:8080 check inter 500ms fall 1 rise 1 resolvers docker init-addr libc,none
''')
    common = {'server.port': 8080, 'spring.cloud.config.enabled': False,
        'eureka.client.enabled': False, 'spring.sql.init.mode': 'never',
        'spring.jpa.hibernate.ddl-auto': 'none', 'spring.jpa.open-in-view': False,
        'management.tracing.export.enabled': False, 'management.tracing.export.zipkin.enabled': False,
        'spring.autoconfigure.exclude': [
            'org.springframework.boot.micrometer.tracing.brave.autoconfigure.BraveAutoConfiguration',
            'org.springframework.boot.micrometer.tracing.autoconfigure.MicrometerTracingAutoConfiguration'], 'management.endpoints.web.exposure.include': 'health,info',
        'spring.datasource.url': 'jdbc:mysql://database:3306/petclinic?allowPublicKeyRetrieval=true&useSSL=false',
        'spring.datasource.username': 'root', 'spring.datasource.password': 'petclinic-study',
        'spring.datasource.driver-class-name': 'com.mysql.cj.jdbc.Driver',
        'spring.datasource.hikari.maximum-pool-size': 5, 'spring.datasource.hikari.minimum-idle': 1}
    services = {}
    for service in ('customers-service', 'vets-service', 'visits-service-replica-a', 'visits-service-replica-b', 'api-gateway'):
        name = 'visits-service' if service.startswith('visits-service-replica-') else service
        props = dict(common)
        if name == 'api-gateway':
            for target in ('visits', 'customers', 'vets'):
                props[f'spring.cloud.discovery.client.simple.instances.{target}-service[0].uri'] = f'http://{target}-service:8080'
            gateway = 'spring.cloud.gateway.server.webflux.'
            # Keep one POST-on-503 retry; independent route breakers prevent target visits failures
            # from opening the same breaker used by the two declared unaffected controls.
            props[gateway+'default-filters'] = [dict(name='Retry', args=dict(retries=1, statuses='SERVICE_UNAVAILABLE', methods='POST'))]
            props[gateway+'routes'] = [dict(id=target, uri=f'lb://{target}-service',
                predicates=[f'Path=/api/{prefix}/**'], filters=['StripPrefix=2',
                dict(name='CircuitBreaker', args=dict(name=target+'CircuitBreaker', fallbackUri='forward:/fallback'))])
                for target, prefix in (('vets', 'vet'), ('visits', 'visit'), ('customers', 'customer'))]
        replica = service[-1] if name == 'visits-service' else ''
        domain = ('domain_b' if replica == 'b' and placement == 'split' else 'domain_a') if replica else 'unfaulted'
        env = dict(SPRING_APPLICATION_JSON=json.dumps(props), OTEL_SERVICE_NAME=name,
            OTEL_RESOURCE_ATTRIBUTES=f'service.instance.id={service},study.replica={replica},study.domain={domain}',
            OTEL_EXPORTER_OTLP_ENDPOINT='http://collector:4318', OTEL_EXPORTER_OTLP_PROTOCOL='http/protobuf',
            OTEL_TRACES_SAMPLER='always_on', OTEL_METRICS_EXPORTER='none', OTEL_LOGS_EXPORTER='none',
            OTEL_BSP_SCHEDULE_DELAY='1000')
        services[service] = dict(image=image, command=['java', '-Xms64m', '-Xmx320m', '-XX:MaxMetaspaceSize=192m',
            '-javaagent:/app/opentelemetry-javaagent.jar', '-jar', '/app/'+name+'.jar'], environment=env,
            networks=['application', 'telemetry']+([] if name == 'api-gateway' else ['database']),
            depends_on=['database', 'collector'], mem_limit='768m')
    services['api-gateway']['ports'] = ['127.0.0.1:18080:8080']
    services['visits-service'] = dict(image=config['images']['proxy'], networks=['application'],
        volumes=[str((out/'haproxy.cfg').resolve())+':/usr/local/etc/haproxy/haproxy.cfg:ro'],
        ports=['127.0.0.1:18404:8404'])
    services['database'] = dict(image=config['images']['database'], networks=['database'],
        environment=dict(MYSQL_ROOT_PASSWORD='petclinic-study', MYSQL_ROOT_HOST='%', MYSQL_DATABASE='petclinic'),
        command=['--innodb-buffer-pool-size=128M', '--max-connections=64'], mem_limit='768m',
        volumes=[str((bundle/'sql').resolve())+':/docker-entrypoint-initdb.d:ro'])
    services['collector'] = dict(image=config['images']['collector'], networks=['telemetry'],
        command=['--config=/etc/study/collector.json'], user='0:0',
        volumes=[str((out/'collector.json').resolve())+':/etc/study/collector.json:ro', str(traces.resolve())+':/output'])
    path = out/'compose.json'
    write(path, dict(name='petclinic-study', services=services,
                    networks={name: dict(name='petclinic-study-'+name) for name in ('application', 'database', 'telemetry')}))
    return path


def db_records(compose_path):
    sql = "SELECT JSON_OBJECT('id',id,'petId',pet_id,'date',DATE_FORMAT(visit_date,'%Y-%m-%d'),'description',description) FROM visits WHERE description LIKE 'study-%';"
    raw = command(['docker', 'compose', '-f', str(compose_path), 'exec', '-T', '-e', 'MYSQL_PWD=petclinic-study',
        'database', 'mysql', '-uroot', '--batch', '--skip-column-names', 'petclinic', '-e', sql])
    grouped = {}
    for line in raw.splitlines():
        row = json.loads(line)
        grouped.setdefault(row['description'], []).append(row)
    return grouped


def probe(bundle, out, config):
    fixture = adapt_fixture(json.loads((bundle/'fixture.json').read_text()))
    path = compose(bundle, out, config)
    base = ['docker', 'compose', '-f', str(path)]
    rows, controls = [], []
    containers = {}
    try:
        command([*base, 'up', '-d'], log=out/'logs/compose-up.log')
        deadline = time.monotonic()+config['startup_deadline_seconds']
        warmup = []
        while time.monotonic() < deadline:
            trial = [execute('http://localhost:18080', operation, f'bootstrap-warmup-{len(warmup)}-{operation}', fixture)
                     for operation in ('list_owners', 'owner_details_with_visits', 'list_vets')]
            warmup.extend(trial)
            write(out/'warmup.json', warmup)
            if all(r['semantic_success'] for r in trial):
                break
            time.sleep(5)
        else:
            raise ValueError('Petclinic did not satisfy all three seed-derived read contracts before startup deadline')
        containers = {r: command([*base, 'ps', '-q', 'visits-service-replica-'+r]) for r in ('a', 'b')}
        for control in config['controls']:
            if control == 'one_path_a':
                command(['docker', 'pause', containers['b']])
            elif control == 'one_path_b':
                command(['docker', 'unpause', containers['b']])
                command(['docker', 'pause', containers['a']])
            elif control == 'no_replica':
                command(['docker', 'pause', containers['b']])
            elif control == 'live_process_communication_failure':
                for replica in ('a', 'b'):
                    command(['docker', 'unpause', containers[replica]])
                    command(['docker', 'network', 'disconnect', 'petclinic-study-application', containers[replica]])
            elif control == 'recovered':
                for replica in ('a', 'b'):
                    command(['docker', 'network', 'connect', '--alias', 'visits-service-replica-'+replica,
                             'petclinic-study-application', containers[replica]])
                # Default Resilience4j open-state wait is 60 seconds; preserve it and wait for recovery.
                time.sleep(65)
            time.sleep(config['fault_settle_seconds'])
            states = {replica: json.loads(command(['docker', 'inspect', cid]))[0]
                      for replica, cid in containers.items()}
            selected = []
            for repeat in range(config['bootstrap_requests_per_operation_per_control']):
                for operation in config['operations']:
                    row = execute('http://localhost:18080', operation,
                        f"petclinic-bootstrap-{os.environ['GITHUB_RUN_ID']}-{control}-{repeat}-{operation}", fixture)
                    row['control'] = control
                    selected.append(row)
                    time.sleep(.1)
            # This oracle reads the shared DB independently after requests; it does not change any response.
            persisted = db_records(path)
            for row in selected:
                if row['operation'] == 'create_visit':
                    finalize_write(row, persisted.get(row['marker'], []), fixture)
            rows.extend(selected)
            write(out/'requests.json', rows)
            count = {operation: dict(attempts=sum(r['operation'] == operation for r in selected),
                      successes=sum(r['operation'] == operation and r['semantic_success'] for r in selected))
                     for operation in config['operations']}
            unavailable = control in ('no_replica', 'live_process_communication_failure')
            checks = {operation: value['successes'] == (0 if unavailable and operation in
                      ('owner_details_with_visits', 'create_visit') else value['attempts'])
                      for operation, value in count.items()}
            if control == 'live_process_communication_failure':
                checks['processes_alive_with_database_network'] = all(s['State']['Running'] and not s['State']['Paused']
                    and 'petclinic-study-database' in s['NetworkSettings']['Networks']
                    and 'petclinic-study-application' not in s['NetworkSettings']['Networks'] for s in states.values())
            controls.append(dict(control=control, counts=count, checks=checks, container_states=states))
            write(out/'controls.json', controls)
        time.sleep(config['trace_flush_seconds'])
        native = out/'traces/native.jsonl'
        grouped, parse = read_native(native, {r['trace_id'] for r in rows}, 'otlp_jsonl_v1')
        census = []
        for row in rows:
            spans = grouped.get(row['trace_id'], [])
            census.append(dict(request_id=row['request_id'], operation=row['operation'], control=row['control'],
                semantic_success=row['semantic_success'], spans=len(spans), services=sorted({s.service for s in spans}),
                server_spans=sum(s.server for s in spans), native_error_spans=sum(s.error for s in spans),
                replica_ids=sorted({s.resource_attributes.get('service.instance.id', '') for s in spans if s.service == 'visits-service'})))
        write(out/'trace-census.json', dict(rows=census, parse=parse, native_sha256=digest(native),
              native_bytes=native.stat().st_size, attempts=len(rows), unique_request_ids=len({r['request_id'] for r in rows}),
              unique_trace_ids=len({r['trace_id'] for r in rows})))
        expected = len(config['controls'])*len(config['operations'])*config['bootstrap_requests_per_operation_per_control']
        service_log = command([*base, 'logs', '--no-color'])
        checks = dict(all_semantic_controls=all(all(c['checks'].values()) for c in controls),
            no_competing_zipkin_export_errors='AsyncReporter$BoundedAsyncReporter' not in service_log,
            no_competing_micrometer_tracing_scope_errors='io.micrometer.tracing.handler.TracingObservationHandler' not in service_log,
            exact_attempt_census=len(rows) == expected == len({r['request_id'] for r in rows}),
            every_attempt_has_gateway_server_trace=all(r['spans'] and 'api-gateway' in r['services'] for r in census),
            all_successful_required_calls_have_visits=all('visits-service' in r['services'] for r in census
                if r['semantic_success'] and r['operation'] in ('owner_details_with_visits', 'create_visit')),
            both_replica_identities_observed={replica for r in census for replica in r['replica_ids']} ==
                {'visits-service-replica-a', 'visits-service-replica-b'},
            native_parse_clean=not parse['malformed_json_records'] and not parse['invalid_traces'])
        write(out/'bootstrap-summary.json', dict(qualified=all(checks.values()), checks=checks,
            source_commit=config['source_commit'], study_head=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
            config_sha256=digest(CONFIG), main_campaigns=0, model_fits=0, controls=len(controls), attempts=len(rows)))
        if not all(checks.values()):
            raise ValueError('Petclinic bootstrap control gate failed; exact failures retained')
    finally:
        for cid in containers.values():
            state = json.loads(command(['docker', 'inspect', cid]))[0]['State']
            if state['Paused']:
                command(['docker', 'unpause', cid])
        command([*base, 'logs', '--no-color'], log=out/'logs/services.log')
        write(out/'final-containers.json', json.loads(command(['docker', 'inspect', *command([*base, 'ps', '-aq']).splitlines()])))
        command([*base, 'down'], log=out/'logs/compose-down.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'probe'))
    parser.add_argument('--source', type=Path)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Application build/load/native parsing stays in GitHub Actions'
    config = json.loads(CONFIG.read_text())
    if args.action == 'build':
        build(args.source.resolve(), args.out.resolve(), config)
    else:
        probe(args.bundle.resolve(), args.out.resolve(), config)


if __name__ == '__main__':
    main()
