"""Remote primary-evidence census; locally only compact scalar selection/reporting."""
import argparse
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time
import traceback
import zipfile

import retain_v3_comparison_compact_v4 as transport
from archive_h_exec_evidence_v1 import verify_zip

ROOT = Path(__file__).resolve().parents[1]
AGGREGATE = ROOT/'docs/evidence/v3-main-transport-recovery-34517752889/analysis/files/comparison.json'
ARCHIVE = ROOT/'docs/evidence/v3-main-durable-archive-34516536673/manifest.json'
PROTOCOL = ROOT/'configs/v3_attempt_audit_v1.json'
MAIN_RUN = 34465226083
MAIN_HEAD = 'd857ea65ca9da7fa9ae4ee1198317487475246a7'


def read(path): return json.loads(path.read_bytes())
def digest(path): return sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(transport.encoded(value))


def scalar_census():
    grouped = {}
    for row in read(AGGREGATE)['analysis']['attempted_census']:
        key = (row['application'], row['placement'], row['law'], row['repetition'], row['operation'])
        grouped.setdefault(key, {})[row['method']] = row['forecast']
    rows = []
    for key, methods in sorted(grouped.items()):
        app, placement, law, rep, op = key; g = methods['Gstar']; b0 = methods['B0']
        y = Fraction(b0['exact_fraction'])
        point = g.get('exact_fraction'); lower = point or g.get('lower_exact'); upper = point or g.get('upper_exact')
        row = dict(application=app, placement=placement, law=law, repetition=rep, operation=op,
            artifact_key=f'{app}--{placement}--{law}--r{rep}',
            b0_exact=str(y), calibration_attempts=b0['attempts'], calibration_successes=b0['successes'],
            kind='point' if point else 'interval' if lower else 'unsupported',
            lower_exact=lower, upper_exact=upper)
        if lower is not None:
            lo, hi = Fraction(lower), Fraction(upper)
            excess = max(Fraction(0), y-hi); deficit = max(Fraction(0), lo-y)
            minimum_bad = (excess+deficit)*b0['attempts']
            if minimum_bad.denominator != 1: raise ValueError('noninteger same-sample gap')
            row.update(above_upper=y > hi, below_lower=y < lo,
                minimum_incompatible_attempts=int(minimum_bad), minimum_incompatible_fraction=float(excess+deficit),
                b0_minus_upper_pp=float(100*(y-hi)), b0_minus_lower_pp=float(100*(y-lo)))
        rows.append(row)
    if len(rows) != 800: raise ValueError('historical operation census changed')
    return rows


def prepare():
    rows = scalar_census(); _, cases = transport.selections(MAIN_RUN, 'main')
    ordered = []
    for app in sorted({r['application'] for r in rows}):
        app_rows = [r for r in rows if r['application'] == app]
        priority = []
        # Largest interval exit, its N control, then largest point discrepancy.
        # These affect execution order only; all 80 campaigns remain mandatory.
        for kind in ('interval', 'point'):
            available = [r for r in app_rows if r['kind'] == kind]
            if not available: continue
            worst = sorted(available, key=lambda r: (-r['minimum_incompatible_attempts'], r['artifact_key'], r['operation']))[0]
            priority += [worst['artifact_key'], f"{app}--{worst['placement']}--N--r{worst['repetition']}"]
        by_key = {c['artifact_key']: c for c in cases if c['identity']['application'] == app}
        keys = list(dict.fromkeys(priority + sorted(by_key)))
        ordered.extend(by_key[k] for k in keys)
    value = dict(version='v3-attempt-audit-v1', source_main_run=MAIN_RUN, source_main_head=MAIN_HEAD,
        scalar_source_sha256=digest(AGGREGATE), archive_manifest_sha256=digest(ARCHIVE),
        scope='already-open calibration evidence; forensic census, not independent confirmation',
        expected_campaigns=240, expected_operations=800, expected_calibration_attempts=864000,
        expected_saved_execution_models=761, expected_unbound_operations=39,
        first_wave_campaigns_per_application=4, selection_affects_only_order=True,
        all_attempts_including_external_failures_and_missing_coordinates=True,
        historical_C12_unchanged=True, cases=ordered)
    write(PROTOCOL, value)
    write(ROOT/'docs/evidence/v3-attempt-audit-design/scalar-census.json', dict(
        version=value['version'], source_sha256=value['scalar_source_sha256'],
        reference='B0 calibration counts; attempted_census.metrics are test outcomes and are not used', rows=rows))
    print(json.dumps(dict(campaigns=len(ordered), operations=len(rows),
        interval_above=sum(r.get('above_upper', False) for r in rows if r['kind']=='interval'),
        point_above=sum(r.get('above_upper', False) for r in rows if r['kind']=='point'),
        point_below=sum(r.get('below_lower', False) for r in rows if r['kind']=='point'),
        first_wave={app:[c['artifact_key'] for c in ordered if c['identity']['application']==app][:4]
                    for app in sorted({r['application'] for r in rows})})))


def fetch(source, destination):
    meta = transport.read_api(f"actions/artifacts/{source['artifact_id']}")
    if (meta['expired'] or meta['name'] != source['name'] or
            meta['workflow_run']['id'] != MAIN_RUN or meta['workflow_run']['head_sha'] != MAIN_HEAD or
            meta['size_in_bytes'] != source['bytes'] or meta['digest'] != 'sha256:'+source['sha256']):
        raise ValueError('source artifact provenance differs')
    blob = transport.api(f"actions/artifacts/{source['artifact_id']}/zip")
    archive_path = destination.with_suffix('.zip'); archive_path.write_bytes(blob)
    verified = verify_zip(archive_path, meta)
    if verified['uncompressed_bytes'] != source['uncompressed_bytes'] or verified['uncompressed_bytes'] > 800_000_000:
        raise ValueError('source expanded census differs or exceeds bound')
    with zipfile.ZipFile(archive_path) as archive: archive.extractall(destination)
    archive_path.unlink()
    return dict(artifact_id=meta['id'], name=meta['name'], sha256=source['sha256'], bytes=len(blob), **verified)


def primary_chain(raw_root, data):
    from telemetry_availability.live_evidence import _pivot_health
    from telemetry_availability.pmx_observed_operations import read_native
    from telemetry_availability.v3_comparison_roles_v1 import ordinary_projection
    from telemetry_availability.v3_primary_projection import PROBE_FIELDS, REQUEST_FIELDS
    requests = [r for r in read(raw_root/'requests.json') if r['period'] == 'calibration']
    if [{k:r[k] for k in REQUEST_FIELDS} for r in requests] != data['requests.json']:
        raise ValueError('primary external request projection differs')
    health = read(raw_root/'health.json')
    probes, malformed = _pivot_health({}, health, 'calibration')
    probes = [{k:r[k] for k in PROBE_FIELDS} for r in probes]
    if probes != data['probes.json']: raise ValueError('primary probe projection differs')
    paths = [(raw_root/'raw-telemetry.json', 'jaeger_json_v1'),
             (raw_root/'raw-telemetry.log', 'otlp_jsonl_v1'),
             (raw_root/'traces/native.jsonl', 'otlp_jsonl_v1')]
    existing = [(p, fmt) for p, fmt in paths if p.is_file()]
    if len(existing) != 1: raise ValueError('original native source is not unique')
    native_path, native_format = existing[0]
    native_digest = digest(native_path)
    if native_digest != data['manifest.json']['original_native_sha256']:
        raise ValueError('original native source hash differs from frozen projection')
    grouped, parse = read_native(native_path, {r['trace_id'] for r in requests}, native_format)
    native = dict(calibration_only=True, selected_trace_ids=sorted(r['trace_id'] for r in requests),
        spans={k:[asdict(s) for s in spans] for k, spans in grouped.items()})
    identity = data['manifest.json']['identity']; ops = sorted({r['operation'] for r in requests})
    reproduced, _ = ordinary_projection(data['declarations.json'], requests, probes, native, identity, ops, len(requests)//len(ops))
    for name in ('requests.json', 'probes.json', 'native.json', 'declarations.json'):
        if reproduced[name] != data[name]: raise ValueError('primary projection differs: '+name)
    projection = read(raw_root/'projection-audit.json')
    if parse != projection['native_parse'] or malformed != projection['calibration_probe_malformed_records']:
        raise ValueError('primary parse census differs')
    return dict(primary_request_projection_exact=True, primary_health_projection_exact=True,
        primary_native_projection_exact=True, primary_native_parse_census_exact=True,
        original_native_sha256=native_digest, native_member=native_path.relative_to(raw_root).as_posix(),
        request_source_sha256=digest(raw_root/'requests.json'), health_source_sha256=digest(raw_root/'health.json'),
        independently_verified_business_labels=False,
        distinction='Byte/projection verification does not by itself validate external business semantics'), requests, health


def audit_case(case, sources, out, settings):
    from telemetry_availability.attempt_compatibility_audit_v1 import audit_operation
    from telemetry_availability.v3_ordinary_identity_v2 import load_bundle
    from telemetry_availability.v3_comparison_roles_v1 import load_role
    from telemetry_availability.v3_comparison_candidates_v1 import replay
    from telemetry_availability.v3_prospective_execution_v1 import fit_operation, BindingUnsupported
    key = case['artifact_key']; identity = case['identity']; started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='attempt-audit-') as temporary:
        temp = Path(temporary); provenance = {}
        for role in ('raw', 'graph'):
            name = f'v3-comparison-{role}-{key}-{MAIN_RUN}'
            provenance[role] = fetch(sources[name], temp/role)
        ordinary_roots = [p.parent for p in (temp/'raw').rglob('seal.json') if p.parent.as_posix().endswith('/roles/ordinary')]
        if len(ordinary_roots) != 1: raise ValueError('ordinary role is not unique')
        ordinary_root = ordinary_roots[0]; raw_root = ordinary_root.parent.parent
        data, _ = load_bundle(ordinary_root)
        if data['manifest.json']['identity'] != identity: raise ValueError('ordinary campaign identity differs')
        graph_roots = [p.parent for p in (temp/'graph').rglob('models.json')]
        if len(graph_roots) != 1: raise ValueError('saved graph role is not unique')
        documents, _ = load_role(graph_roots[0], 'graph_candidates', identity=identity)
        candidate = documents['candidates.json']; models = documents['models.json']
        if candidate['input_seal_sha256'] != digest(ordinary_root/'seal.json'):
            raise ValueError('saved graph was built from a different ordinary input')
        replay_result = replay(candidate['forecasts'], models)
        chain, raw_requests, health = primary_chain(raw_root, data)
        raw_by_id = {r['request_id']:r for r in raw_requests}
        responses = read(raw_root/'responses.json')
        summaries = []; full = out/'full'/key; full.mkdir(parents=True, exist_ok=True)
        for operation, spec in settings['profiles'][identity['application']]['operations'].items():
            saved = models['execution'].get(operation)
            try: rebuilt, _ = fit_operation(data, operation, spec, identity)
            except BindingUnsupported as exc:
                if saved is not None or candidate['forecasts'][operation]['Gstar'].get('reason') != str(exc): raise
                summaries.append(dict(operation=operation, status='unsupported', reason=str(exc),
                    attempts=sum(r['operation']==operation for r in raw_requests), binding_absence_reproduced=True))
                continue
            if rebuilt != saved: raise ValueError('frozen primary binding does not reproduce saved model')
            summary, rows, witnesses = audit_operation(data, saved, spec)
            b0 = models['b0']['forecasts'][operation]
            if summary['successes'] != b0['successes'] or summary['attempts'] != b0['attempts']:
                raise ValueError('attempt outcomes do not reproduce frozen B0')
            summary.update(identity=identity, saved_model_exact=True, b0_calibration_counts_exact=True)
            summaries.append(summary)
            with (full/(operation+'-attempts.jsonl')).open('w', encoding='utf-8', newline='\n') as stream:
                for row in rows: stream.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
            for witness in witnesses.values():
                rid = witness['attempt']['request_id']; trace = witness['attempt']['trace_id']
                witness['primary_request'] = raw_by_id[rid]
                witness['primary_response_records'] = [r for r in responses if r.get('request_id') == rid or r.get('trace_id') == trace]
                at = witness['attempt']['probe_observed_at']
                witness['primary_health_records'] = [r for r in health if r['observed_at']==at and r['period']=='calibration']
                witness['provenance'] = chain
            write(full/(operation+'-witnesses.json'), witnesses)
            # Compact diagnostic scalars only; complete request/response/span
            # records remain in the remote full artifact.
            diagnostic = []
            for signature, witness in witnesses.items():
                if witness['attempt']['compatibility'] == 'compatible': continue
                raw_request = witness['primary_request']
                scalar_keys = ('http_status', 'status_code', 'status', 'error', 'semantic_success',
                    'timed_out', 'semantic_error', 'semantic_reason', 'response_status',
                    'duration_seconds', 'elapsed_seconds', 'persistence_verified')
                diagnostic.append(dict(signature=signature, attempt=witness['attempt'],
                    request_field_names=sorted(raw_request),
                    primary_request_scalars={k:raw_request[k] for k in scalar_keys if k in raw_request},
                    response_field_names=[sorted(r) for r in witness['primary_response_records']],
                    span_statuses=[dict(span_id=s['span_id'], service=s['service'], operation=s['operation'],
                        start_ns=s['start_us']*1000+s['start_remainder_ns'],
                        duration_ns=s['duration_us']*1000+s['duration_remainder_ns'],
                        error_tag=s['error_tag'], error_status=s['error_status'],
                        protocol={k:v for k,v in s['attributes'].items() if k in (
                            'http.status_code', 'http.response.status_code', 'rpc.grpc.status_code', 'rpc.method')},
                        replica_resources={k:v for k,v in s['resource_attributes'].items() if k in (
                            'study.replica', 'hostname', 'host.name', 'service.instance.id')})
                        for s in witness['relevant_native_spans']],
                    primary_health_scalars=[{k:r[k] for k in ('observed_at', 'replica', 'backend_status',
                        'backend_check_status', 'running', 'paused') if k in r} for r in witness['primary_health_records']],
                    full_remote_witness_member=f'full/{key}/{operation}-witnesses.json',
                    full_remote_witness_key=signature))
            write(out/'compact/examples'/key/(operation+'.json'), diagnostic)
        result = dict(version='v3-attempt-audit-v1', artifact_key=key, identity=identity,
            audit_run=os.environ['GITHUB_RUN_ID'], audit_head=os.environ['GITHUB_SHA'],
            source_main_run=MAIN_RUN, source_main_head=MAIN_HEAD, sources=provenance,
            primary_chain=chain, saved_forecast_replay=replay_result, operations=summaries,
            elapsed_seconds=time.monotonic()-started)
        write(out/'compact/cases'/(key+'.json'), result)
        print(json.dumps(dict(case=key, operations=len(summaries),
            incompatible_attempts=sum(r.get('incompatible_attempts', 0) for r in summaries),
            seconds=round(result['elapsed_seconds'], 2))), flush=True)


def run(args):
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('GITHUB_REPOSITORY') != transport.REPO
            or os.environ.get('GITHUB_RUN_ATTEMPT') != '1'):
        raise ValueError('Real primary/model audit runs only in the declared first-attempt remote workflow')
    protocol = read(PROTOCOL)
    if digest(AGGREGATE) != protocol['scalar_source_sha256'] or digest(ARCHIVE) != protocol['archive_manifest_sha256']:
        raise ValueError('fixed scalar/archive sources changed')
    sources = {s['name']:s for part in read(ARCHIVE)['parts'] for s in part['sources']}
    cases = [c for c in protocol['cases'] if c['identity']['application'] == args.profile]
    if len(cases) != 80: raise ValueError('profile census differs')
    if args.wave == 'first': cases = cases[:protocol['first_wave_campaigns_per_application']]
    settings = read(ROOT/'configs/v3_comparison_execution_v3.json')
    for case in cases:
        existing = args.out/'compact/cases'/(case['artifact_key']+'.json')
        if existing.is_file():
            previous = read(existing)
            if previous['identity'] != case['identity'] or previous['audit_run'] != os.environ['GITHUB_RUN_ID'] or previous['audit_head'] != os.environ['GITHUB_SHA']:
                raise ValueError('resume evidence identity differs')
            continue
        try: audit_case(case, sources, args.out, settings)
        except Exception as exc:
            write(args.out/'compact/failures'/(case['artifact_key']+'.json'),
                dict(identity=case['identity'], error=type(exc).__name__+': '+str(exc), traceback=traceback.format_exc()))
            raise
    write(args.out/'compact'/('wave-'+args.wave+'.json'), dict(profile=args.profile, wave=args.wave,
        expected_cases=len(cases), completed_cases=len(list((args.out/'compact/cases').glob('*.json'))),
        audit_run=os.environ['GITHUB_RUN_ID'], audit_head=os.environ['GITHUB_SHA'],
        protocol_sha256=digest(PROTOCOL), primary_evidence_remains_remote=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare')
    p = sub.add_parser('run'); p.add_argument('--profile', required=True)
    p.add_argument('--wave', choices=['first', 'all'], required=True)
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare': prepare()
    else: run(args)
