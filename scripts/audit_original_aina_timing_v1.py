"""Remote descriptive timing-feasibility audit; no reconstructed timestamps."""
from collections import Counter
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import time
import zipfile
import audit_original_aina_v1 as original_audit

CONFIG = Path('configs/original_aina_timing_v1.json')
OUT = Path('workflow-results/aina-timing-compact')


def error_category(error):
    if 'Read timed out.' in error and re.search(r'\(read timeout=6(?:\.0)?\)', error):
        return 'read_timeout_declared_6s'
    if re.search(r'\b5\d\d Server Error\b', error):
        return 'http_5xx'
    if re.search(r'\b4\d\d Client Error\b', error):
        return 'http_4xx'
    if 'timed out' in error.lower() or 'timeout' in error.lower():
        return 'other_timeout_unquantified'
    if error == 'empty response':
        return 'empty_response'
    if error == 'checkout missing orderId':
        return 'checkout_missing_order_id'
    return 'other_unquantified'


def window_timing(details, period_seconds=60, startup_delay=15):
    categories = Counter(error_category(row.get('error', '')) for row in details if row['status']=='fail')
    count = categories['read_timeout_declared_6s']
    minimum = 6*count
    return {'error_counts': dict(categories), 'read_timeout_count': count,
            'conditional_duration_lower_bound_s': minimum,
            'exceeds_nominal_45s_remaining': minimum > period_seconds-startup_delay,
            'exceeds_declared_60s_hold': minimum > period_seconds}


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Original payloads are remote only'
    started = time.perf_counter()
    config = json.loads(CONFIG.read_bytes())
    for lock in config['repository_locks']:
        assert sha256(Path(lock['path']).read_bytes()).hexdigest() == lock['sha256'], lock['path']
    manifest = json.loads(Path(config['transfer_manifest']).read_bytes())
    payload = original_audit.fetch_asset(config)
    rows, error_types = [], {}
    grouped = {str(p): {'windows':0,'probes':0,'errors':Counter(),'lower_bound_histogram':Counter(),
        'exceeds_nominal_45s_remaining':0,'exceeds_declared_60s_hold':0,'successes_in_long_windows':0,
        'probes_in_long_windows':0} for p in (.1,.3,.5,.7,.9)}
    with zipfile.ZipFile(io.BytesIO(payload)) as outer:
        outer_members = original_audit.safe_members(outer)
        assert {m.filename for m in outer_members} == {m['member'] for m in manifest['members']}
        for lock in manifest['members']:
            data = outer.read(lock['member'])
            assert len(data)==lock['bytes'] and sha256(data).hexdigest()==lock['sha256']
            match = re.fullmatch(r'100x100/results_p(0\.[13579])_chunk(\d+)\.zip', lock['member'])
            p, chunk = match.groups()
            counters = grouped[p]
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = original_audit.safe_members(archive)
                names = sorted(m.filename for m in members if re.fullmatch(
                    rf'live_p{re.escape(p)}_chunk{chunk}_\d+\.json',m.filename))
                assert len(names)==100
                for name in names:
                    live=json.loads(archive.read(name))
                    details=live['detail']['probe_detail']
                    assert len(details)==live['detail']['probe_total']==100
                    result=window_timing(details)
                    for record in details:
                        if record['status']!='fail':
                            continue
                        error=record['error']
                        digest=sha256(error.encode()).hexdigest()
                        if digest not in error_types:
                            error_types[digest]={'sha256':digest,'characters':len(error),
                                'category':error_category(error),'count':0,
                                'example_prefix':error[:300]}
                        error_types[digest]['count']+=1
                    counters['windows']+=1
                    counters['probes']+=len(details)
                    counters['errors'].update(result['error_counts'])
                    counters['lower_bound_histogram'][str(result['conditional_duration_lower_bound_s'])]+=1
                    for key in ('exceeds_nominal_45s_remaining','exceeds_declared_60s_hold'):
                        counters[key]+=int(result[key])
                    if result['exceeds_declared_60s_hold']:
                        counters['successes_in_long_windows']+=live['detail']['probe_ok']
                        counters['probes_in_long_windows']+=len(details)
                    rows.append({'artifact_id':lock['artifact_id'],'p_fail':float(p),'chunk':int(chunk),
                        'window':int(name.rsplit('_',1)[1][:-5]),'successes':live['detail']['probe_ok'],**result})
    assert len(rows)==25000
    summary={'version':config['version'],'run_id':os.environ['GITHUB_RUN_ID'],'head':os.environ['GITHUB_SHA'],
        'protocol_sha256':sha256(CONFIG.read_bytes()).hexdigest(),'source_run':19590510289,
        'prior_complete_audit_run':34231677146,'windows':len(rows),'probes':2500000,
        'groups':grouped,'elapsed_seconds':time.perf_counter()-started,'new_independent_campaigns':0,
        'main_campaigns':0,'measured_probe_timestamps_available':False,
        'interpretation':'Duration lower bounds are conditional on logged read-timeout=6 matching the requests timeout semantics and sequential execution. They are not observed timestamps.',
        'limitations':['Unknown controller preparation/stop/start overhead shifts actual fault interval',
            'Exceeding the nominal45s remainder or declared60s sleep does not prove the exact number of post-recovery successes',
            'Read-timeout diagnostics cannot identify original causal mediation fractions',
            'Source --window40 argument is not used to bound the probe loop',
            'No H2 causal confirmation or model refinement is assigned by this retrospective audit']}
    original_audit.save(OUT/'summary.json',summary)
    original_audit.save(OUT/'window-timing-census.json',rows)
    original_audit.save(OUT/'error-type-census.json',list(error_types.values()))
    print(json.dumps({'windows':len(rows),'long_windows':sum(g['exceeds_declared_60s_hold'] for g in grouped.values())}))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        original_audit.save(OUT/'failure.json',{'type':type(exc).__name__,'message':str(exc)})
        raise
