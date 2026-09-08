"""Remote causal-diagnostic census; never changes the external success event."""
from collections import Counter, defaultdict
import argparse
import csv
import json
from pathlib import Path
import re
import time

from .h_exec_live_v1 import settings
from .pmx_observed_operations import read_native
from .v3_primary_projection import read, write, sha

ROUTE = re.compile(r'study_route trace=(\S+) backend=(\S+) server=(\S+) status=(-?\d+) total_ms=([+\-]?\d+) termination=(\S+)')
CONTEXT = re.compile(r'00-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}',re.I)


def truth(value):
    return str(value).lower() == 'true'


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))


def routes(text, selected):
    result = defaultdict(list); counts = Counter()
    for line in text.splitlines():
        if 'study_route ' not in line:
            continue
        match = ROUTE.search(line)
        if not match:
            counts['malformed_route_lines'] += 1; continue
        context,backend,server,status,duration,termination = match.groups()
        context_match = CONTEXT.fullmatch(context)
        if not context_match:
            counts['missing_or_invalid_traceparent'] += 1; continue
        trace = context_match.group(1).lower()
        if trace not in selected:
            counts['outside_external_census'] += 1; continue
        result[trace].append(dict(backend=backend,server=server,status=int(status),
                                  total_ms=int(duration),termination=termination))
        counts['joined_routes'] += 1
    return dict(result),dict(counts)


def summarize(source,output,frozen):
    identity = read(source/'identity.json'); acquisition = read(source/'acquisition-summary.json')
    requests = csv_rows(source/'requests.csv'); health = csv_rows(source/'health.csv')
    sentinels = csv_rows(source/'sentinel-requests.csv'); controls = read(source/'static-controls.json')
    boundaries = read(source/'boundaries.json')
    selected = {r['trace_id'] for r in requests}
    routing, route_audit = routes((source/'proxy-routes.log').read_text(),selected)
    tick = time.perf_counter()
    native,parse = read_native(source/'raw-telemetry.log',selected,'otlp_jsonl_v1')
    parse_seconds = time.perf_counter()-tick
    table = []; operations = sorted({r['operation'] for r in requests})
    for request in requests:
        trace = request['trace_id']; records = routing.get(trace,[]); spans = native.get(trace,[])
        table.append(dict(request_id=request['request_id'],trace_id=trace,operation=request['operation'],
            period=request['period'],started_at=request['started_at'],completed_at=request['completed_at'],
            scheduled_offset_seconds=float(request['scheduled_offset_seconds']),
            success=truth(request['semantic_success']),timed_out=truth(request['timed_out']),
            latency_ms=float(request['latency_ms']),route_records=len(records),
            selected_a=sum(r['server']=='replica_a' for r in records),
            selected_b=sum(r['server']=='replica_b' for r in records),
            no_selected_server=sum(r['server'] not in ('replica_a','replica_b') for r in records),
            native_spans=len(spans),native_error_spans=sum(s.error_tag or s.error_status for s in spans)))
    summaries = []
    for period in ('baseline','calibration','test'):
        for operation in operations:
            rows = [r for r in table if r['period']==period and r['operation']==operation]
            successes = sum(r['success'] for r in rows)
            summaries.append(dict(period=period,operation=operation,attempts=len(rows),successes=successes,
                success_fraction=successes/len(rows) if rows else None,
                timeouts=sum(r['timed_out'] for r in rows),native_linked=sum(bool(r['native_spans']) for r in rows),
                route_linked=sum(bool(r['route_records']) for r in rows),
                failures_with_selected_a=sum(not r['success'] and r['selected_a']>0 for r in rows),
                successes_with_only_b=sum(r['success'] and r['selected_b']>0 and r['selected_a']==r['no_selected_server']==0 for r in rows),
                successful_route_coverage=sum(r['success'] and r['route_records']>0 for r in rows)/successes if successes else None,
                failed_route_coverage=sum(not r['success'] and r['route_records']>0 for r in rows)/(len(rows)-successes) if len(rows)!=successes else None))
    grouped = defaultdict(list)
    for row in health:
        if row['period']=='test':
            grouped[row['observed_at']].append(row)
    state_good = 0; proxy_statuses = Counter()
    for rows in grouped.values():
        replicas = {r['replica']:r for r in rows if r['role']=='replica' and not r.get('error')}
        expected_a = identity['arm']!='sham'
        if set(replicas)=={'a','b'} and all(truth(r['running']) for r in replicas.values()) and \
                truth(replicas['a']['paused'])==expected_a and not truth(replicas['b']['paused']):
            state_good += 1
        for name,row in replicas.items():
            proxy_statuses[(name,row['backend_status'],row['backend_check_status'])] += 1
    expected = {(period,op):(80 if period=='baseline' else 40) for period in ('baseline','calibration','test') for op in operations}
    actual = Counter((r['period'],r['operation']) for r in table)
    baseline = [r for r in summaries if r['period']=='baseline']
    checks = dict(exact_census=len(table)==480 and len(selected)==480 and len({r['request_id'] for r in table})==480 and
        len(operations)==3 and dict(actual)==expected,
        acquisition_completed=acquisition['error'] is None,
        normal_contracts=all(r['success_fraction']>=.95 for r in baseline),
        semantic_sentinels=len(sentinels)==3 and all(truth(r['semantic_success']) for r in sentinels),
        complete_static_census=len(controls)==60,
        normal_static_control=all(r['success'] for r in controls if r['period']=='baseline'),
        physical_intervention_qualified=len(grouped)>=27 and state_good/len(grouped)>=.95,
        boundary_b_readiness=len(boundaries)==6 and all(r['b_readiness_returncode']==0 for r in boundaries),
        native_parser_clean=not parse['malformed_json_records'] and not parse['invalid_traces'],
        baseline_native_coverage=all(r['native_linked']>=.95*r['attempts'] for r in baseline),
        baseline_routing_coverage=all(r['route_linked']>=.95*r['attempts'] for r in baseline),
        route_parser_clean=route_audit.get('malformed_route_lines',0)==0)
    if identity['arm']=='repaired':
        stats=csv_rows(source/'repair-admin-stats.csv')
        checks['route_a_disabled']=any(r.get('svname')=='replica_a' and r.get('status','').startswith('MAINT') for r in stats)
    output.mkdir(parents=True,exist_ok=True)
    write(output/'census.json',table)
    write(output/'static-controls.json',controls)
    write(output/'summary.json',dict(identity=identity,qualified=all(checks.values()),checks=checks,
        operation_summaries=summaries,route_audit=route_audit,parse=parse,native_parse_seconds=parse_seconds,
        test_health_ticks=len(grouped),test_matching_state_ticks=state_good,
        test_proxy_statuses=[dict(replica=a,backend=b,check=c,count=n) for (a,b,c),n in sorted(proxy_statuses.items())],
        main_campaigns=0,model_fits=0,pmx_invocations=0,
        candidate_is_confirmatory=identity['phase']=='study',outcome_based_treatment_selection=False,
        source_member_sha256={name:sha(source/name) for name in ('requests.csv','health.csv','raw-telemetry.log','proxy-routes.log','boundaries.json','interventions.json')}))
    for name in ('identity.json','boundaries.json','interventions.json','periods.json','instrumentation-audit.json','acquisition-summary.json'):
        write(output/name,read(source/name))
    return all(checks.values())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();frozen=settings()
    qualified=summarize(args.source,args.output,frozen)
    if read(args.source/'identity.json')['phase']=='qualification':
        assert qualified, 'technical H-EXEC manipulation/log/census qualification failed; reports retained'


if __name__=='__main__':
    main()
