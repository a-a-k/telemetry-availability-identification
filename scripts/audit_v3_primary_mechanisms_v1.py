"""Independent external-verdict and state-transition audit on the fixed first wave."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import urllib.request

from audit_v3_attempts_v1 import ROOT, ARCHIVE, PROTOCOL, MAIN_RUN, fetch, read, write, digest
import retain_v3_comparison_compact_v4 as transport
from telemetry_availability.attempt_compatibility_audit_v1 import audit_operation
from telemetry_availability.b0_frequency_v3_csv_v2 import decode_outcome
from telemetry_availability.live_pilot import OTEL_PRODUCT, OTEL_PERSON
from telemetry_availability.primary_verdict_audit_v1 import http_evidence, petclinic_evidence
from telemetry_availability.v3_application_execution_v2 import timestamp_ns, span_interval, optional_ancestor
from telemetry_availability.v3_ordinary_identity_v2 import load_bundle, replica_identity, DS_ENTRIES
from telemetry_availability.v3_comparison_roles_v1 import load_role

PRIOR_RUN = 34694957306
PRIOR_HEAD = '02f31dc45efb05006117793fcd0fe770f49e9d1e'


def load_fixture(directory):
    # Source-derived fixture construction is reused; the response comparison is
    # independently implemented in primary_verdict_audit_v1.
    from telemetry_availability.petclinic_contract_v2 import fixture_from_source, adapt_fixture
    config = read(ROOT/'configs/petclinic_runtime_v3.json'); hashes = {}
    for service in ('customers','visits','vets'):
        relative = f'spring-petclinic-{service}-service/src/main/resources/db/mysql/data.sql'
        url = f"https://raw.githubusercontent.com/{config['source_repository']}/{config['source_commit']}/{relative}"
        with urllib.request.urlopen(url, timeout=60) as response: content = response.read()
        path = directory/relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
        hashes[relative] = sha256(content).hexdigest()
    return adapt_fixture(fixture_from_source(directory)), dict(source_commit=config['source_commit'], SQL_sha256=hashes)


def transitions(row, request, spans, declarations, spec, health, events):
    observation = row['observation']; selected = [r for r in ('a','b')
        if observation.get('demand_'+r) is True and observation.get('probe_'+r) is False]
    if not selected:
        return dict(classification='selected_identity_unresolved', replica_evidence=[])
    sampled = timestamp_ns(row['probe_observed_at']); started = timestamp_ns(request['started_at'])
    ended = timestamp_ns(request['completed_at']); indexed = {s['span_id']:s for s in spans}
    replica_rows = []
    for replica in selected:
        service = declarations['replicas'][replica]
        entries = []
        for span in spans:
            parent = indexed.get(span['parent_id'])
            if (span['service'] != declarations['target_service'] or parent is None or parent['service']==span['service']
                    or optional_ancestor(span, indexed, spec)): continue
            if not (span['server'] or declarations['profile']=='deathstarbench_social_network'
                    and not span['native_kind'] and span['operation'] in DS_ENTRIES): continue
            if replica_identity(span, declarations)['replica'] == replica:
                start, end = span_interval(span); entries.append(dict(span_id=span['span_id'], start_ns=start, end_ns=end))
        relevant = []
        for event in events:
            if (event['period'] != 'calibration' or service not in event['targets'].split(';')
                    or not event['release_confirmed'] or event['error'] or not event['released_at']
                    or service in event['expected_affected_after_release'].split(';')): continue
            released = timestamp_ns(event['released_at'])
            if sampled-2_000_000_000 <= released <= ended:
                relevant.append(dict(event_id=event['event_id'], effect=event['effect'],
                    applied_at=event['applied_at'], released_at=event['released_at'], released_ns=released,
                    release_after_sample=released>sampled, release_before_request_start=released<=started,
                    release_before_any_target_entry=any(released<=e['start_ns'] for e in entries),
                    release_before_any_target_end=any(released<=e['end_ns'] for e in entries),
                    expected_affected_after_release=event['expected_affected_after_release']))
        snapshots = [{k:h[k] for k in ('observed_at','service','replica','running','paused','network_count',
            'backend_status','backend_check_status') if k in h} for h in health
            if h['period']=='calibration' and h['observed_at']==row['probe_observed_at'] and h.get('replica')==replica]
        releases = [e for e in relevant if e['release_after_sample'] and e['release_before_any_target_end']]
        classification = ('confirmed_release_between_sample_and_target_execution' if releases else
            'recent_release_precedes_negative_sample' if relevant else 'transition_not_localized_in_window')
        replica_rows.append(dict(replica=replica, classification=classification, target_entries=entries,
            health_snapshots=snapshots, nearby_confirmed_releases=relevant))
    classes = sorted({r['classification'] for r in replica_rows})
    return dict(classification='+'.join(classes), replica_evidence=replica_rows,
        independent_overlapping_faults_not_excluded=True, existing_connections_not_individually_observed=True)


def run(args):
    if (os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('GITHUB_REPOSITORY')!=transport.REPO
            or os.environ.get('GITHUB_RUN_ATTEMPT')!='1'): raise ValueError('remote first attempt required')
    protocol = read(PROTOCOL); sources = {s['name']:s for part in read(ARCHIVE)['parts'] for s in part['sources']}
    cases = [c for c in protocol['cases'] if c['identity']['application']==args.profile][:4]
    settings = read(ROOT/'configs/v3_comparison_execution_v3.json'); results = []
    with tempfile.TemporaryDirectory(prefix='primary-verdict-fixture-') as fixture_directory:
        fixture, fixture_source = load_fixture(Path(fixture_directory)) if args.profile=='spring_petclinic_microservices' else (None,None)
        for case in cases:
            key = case['artifact_key']; identity=case['identity']
            previous = read(ROOT/f'docs/evidence/v3-attempt-audit-v1-{PRIOR_RUN}/first'/args.profile/'cases'/(key+'.json'))
            if previous['audit_head'] != PRIOR_HEAD: raise ValueError('prior audit head differs')
            with tempfile.TemporaryDirectory(prefix='primary-mechanisms-') as temp_dir:
                temp=Path(temp_dir); provenance={}
                for role in ('raw','graph'):
                    provenance[role]=fetch(sources[f'v3-comparison-{role}-{key}-{MAIN_RUN}'],temp/role)
                    if provenance[role] != previous['sources'][role]: raise ValueError('prior primary artifact differs')
                ordinary_root=next(p.parent for p in (temp/'raw').rglob('seal.json') if p.parent.as_posix().endswith('/roles/ordinary'))
                raw_root=ordinary_root.parent.parent; data,_=load_bundle(ordinary_root)
                graph_root=next((temp/'graph').rglob('models.json')).parent
                documents,_=load_role(graph_root,'graph_candidates',identity=identity)
                raw={r['request_id']:r for r in read(raw_root/'requests.json') if r['period']=='calibration'}
                health=read(raw_root/'health.json'); events=read(raw_root/'events.json')
                summaries=[]; examples=[]; full_rows=[]
                for op,spec in settings['profiles'][args.profile]['operations'].items():
                    model=documents['models.json']['execution'].get(op); attempt_by_id={}
                    if model is not None:
                        audit,attempts,_=audit_operation(data,model,spec)
                        earlier=next(r for r in previous['operations'] if r['operation']==op)
                        for field in ('success_excluded','failure_excluded','attempts','successes','lower_exact','upper_exact'):
                            if audit[field]!=earlier[field]: raise ValueError('prior attempt census differs')
                        attempt_by_id={r['request_id']:r for r in attempts}
                    counts=Counter(); seen=set()
                    for request in raw.values():
                        if request['operation']!=op: continue
                        verdict=petclinic_evidence(request,fixture) if fixture is not None else http_evidence(request,OTEL_PRODUCT,OTEL_PERSON['address'])
                        y=decode_outcome(request['semantic_success']); counts['attempts']+=1
                        counts['verification:'+verdict['verification']]+=1
                        if verdict['outcome'] is None: counts['outcome_not_independently_determined']+=1
                        else:
                            counts['outcome_independently_determined']+=1
                            counts['outcome_mismatches']+=verdict['outcome']!=y
                        attempt=attempt_by_id.get(request['request_id']); mechanism=None
                        incompatible=attempt is not None and attempt['compatibility']!='compatible'
                        if incompatible:
                            counts['incompatible_attempts']+=1
                            counts['incompatible_with_independently_determined_outcome']+=verdict['outcome'] is not None
                            mechanism=transitions(attempt,request,data['native.json']['spans'].get(request['trace_id'],[]),
                                data['declarations.json'],spec,health,events)
                            counts['mechanism:'+mechanism['classification']]+=1
                        record=dict(request_id=request['request_id'],trace_id=request['trace_id'],operation=op,
                            stored_outcome=y,independent_verdict=verdict,incompatible=incompatible,mechanism=mechanism)
                        full_rows.append(record)
                        signature=(verdict['verification'], str(verdict['outcome']!=y if verdict['outcome'] is not None else None),
                            mechanism['classification'] if mechanism else 'compatible_or_unsupported')
                        if signature not in seen:
                            seen.add(signature); examples.append(record)
                    summaries.append(dict(operation=op,counts=dict(counts)))
                result=dict(version='v3-primary-mechanisms-v1', identity=identity, source_audit_run=PRIOR_RUN,
                    run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],sources=provenance,
                    fixture_source=fixture_source, event_source_sha256=digest(raw_root/'events.json'),
                    operations=summaries, examples=examples,
                    selection='all calibration attempts in fixed first four campaigns; no selection by E=Y')
                write(args.out/'compact'/(key+'.json'),result)
                write(args.out/'full'/(key+'.json'),full_rows)
                results.append(result)
                print(json.dumps(dict(case=key,operations=summaries)),flush=True)
        write(args.out/'compact/receipt.json',dict(run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
            profile=args.profile,campaigns=len(results),source_audit_run=PRIOR_RUN,
            verifier_does_not_read_model_or_stored_semantic_label=True, primary_bytes_remain_remote=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',required=True)
    p.add_argument('--out',type=Path,required=True);run(p.parse_args())
