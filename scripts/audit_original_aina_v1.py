"""Remote-only census of byte-verified original AINA artifacts; no new fits."""
from collections import Counter, defaultdict
import csv
from fractions import Fraction
from hashlib import sha256
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import statistics
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

CONFIG = Path('configs/original_aina_audit_v1.json')
SOURCE = Path('docs/evidence/aina-execution-source-a8bc5a2')
OUT = Path('workflow-results/aina-compact')
MODES = ('all-block', 'async')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + '\n').encode())


def original_module():
    spec = importlib.util.spec_from_file_location('aina_original_resilience', SOURCE/'scripts/resilience.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_curve(graph, replicas, original, targets, disallow_lines, max_pool=16):
    """Enumerate labelled container subsets, preserving original duplicate-name logic."""
    original.prepare_graph(graph)
    services = graph['services']
    counts = [max(1, int(replicas.get(name, 1))) for name in services]
    disallowed = set()
    for line in disallow_lines:
        line = line.strip()
        if line and not line.startswith('#'):
            idx = graph['_disallowlist_name_to_idx'].get(original.norm_disallowlist_name(line))
            if idx is not None:
                disallowed.add(idx)
    allowed = [idx for idx in range(len(services)) if idx not in disallowed]
    fallback = not allowed
    if fallback:
        allowed = list(range(len(services)))
    pool = [idx for idx in allowed for _ in range(counts[idx])]
    if len(pool) > max_pool:
        return {'supported': False, 'reason': 'enumeration_pool_limit', 'containers': len(pool)}
    totals = Counter()
    successes = {mode: {ep: Counter() for ep in targets} for mode in MODES}
    changed = {ep: Counter() for ep in targets}
    for bits in range(1 << len(pool)):
        killed = Counter(pool[j] for j in range(len(pool)) if bits & (1 << j))
        failed = {services[i] for i, count in killed.items() if count >= counts[i]}
        k = bits.bit_count()
        totals[k] += 1
        for ep, target in targets.items():
            values = [original.endpoint_success(graph, failed, target, mode) for mode in MODES]
            for mode, value in zip(MODES, values):
                successes[mode][ep][k] += int(value)
            changed[ep][k] += values[0] != values[1]
    return {'supported': True, 'containers': len(pool), 'services': len(services),
            'allowed_services': [services[i] for i in allowed], 'fallback': fallback,
            'states': sum(totals.values()), 'totals': dict(totals),
            'successes': {m: {ep: dict(c) for ep, c in rows.items()} for m, rows in successes.items()},
            'changed': {ep: dict(c) for ep, c in changed.items()}}


def kill_count(n, p):
    k = round(n * p)
    if p > 0 and k == 0:
        k = 1
    return min(max(0, k), n)


def probability(curve, endpoint, mode, p):
    k = kill_count(curve['containers'], p)
    return Fraction(curve['successes'][mode][endpoint][k], curve['totals'][k])


def probe_counts(data, endpoints):
    """Reproduce the historical event, including its explicitly recorded skips."""
    detail = data['detail']
    per_ep = {ep: Counter() for ep in endpoints}
    path_map = {ep.split(' ', 1)[1]: ep for ep in endpoints}
    statuses = Counter()
    for record in detail['probe_detail']:
        # On a failed checkout setup, old code can leave method='GET'. URL identifies operation.
        ep = path_map[urlsplit(record['endpoint']).path]
        status = record['status']
        assert status in ('ok', 'fail', 'skip'), status
        if status == 'skip':
            assert record['code'] in (401, 403)
        statuses[status] += 1
        per_ep[ep]['total'] += 1
        per_ep[ep]['ok'] += status in ('ok', 'skip')
    total = sum(statuses.values())
    ok = statuses['ok'] + statuses['skip']
    assert total == detail['probe_total'] and ok == detail['probe_ok']
    assert total - ok == detail['probe_fail']
    assert abs(data['R_live'] - ok / total) <= 1e-12
    assert set(data['per_endpoint']) == set(endpoints)
    for ep in endpoints:
        assert dict(total=per_ep[ep]['total'], ok=per_ep[ep]['ok']) == data['per_endpoint'][ep]
    return total, ok, statuses, per_ep


def safe_members(archive):
    members = [m for m in archive.infolist() if not m.is_dir()]
    assert len(members) == len({m.filename for m in members})
    for member in members:
        p = PurePosixPath(member.filename)
        assert not p.is_absolute() and '..' not in p.parts and '\\' not in member.filename
        assert member.file_size <= 25_000_000
    assert archive.testzip() is None
    return members


def fetch_asset(config):
    # Authentication is sent only to api.github.com; follow asset redirects without it.
    import urllib.request
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    lock = config['asset']
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
               'Accept': 'application/octet-stream', 'X-GitHub-Api-Version': '2022-11-28'}
    url = f"https://api.github.com/repos/{config['repository']}/releases/assets/{lock['id']}"
    try:
        response = urllib.request.build_opener(NoRedirect).open(Request(url, headers=headers), timeout=60)
    except urllib.error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise
        location = exc.headers['Location']
        assert location.startswith('https://')
        response = urlopen(Request(location), timeout=60)
    with response:
        data = response.read(lock['bytes'] + 1)
    assert len(data) == lock['bytes'] and sha256(data).hexdigest() == lock['sha256']
    return data


def compare_csv(archive, path, expected, columns):
    rows = list(csv.DictReader(io.StringIO(archive.read(path).decode('utf-8-sig'))))
    assert len(rows) == len(expected), path
    worst = {name: 0.0 for name in columns}
    for row, values in zip(rows, expected):
        for name in columns:
            worst[name] = max(worst[name], abs(float(row[name]) - values[name]))
    return worst


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Original payload parsing is GitHub Actions only'
    started = time.perf_counter()
    config = json.loads(CONFIG.read_bytes())
    for lock in config['repository_locks']:
        assert sha256(Path(lock['path']).read_bytes()).hexdigest() == lock['sha256'], lock['path']
    manifest = json.loads(Path(config['transfer_manifest']).read_bytes())
    data = fetch_asset(config)
    original = original_module()
    targets_raw = original.load_targets(str(SOURCE/'config/targets.json'))
    targets = {ep: original.get_endpoint_spec(targets_raw, ep) for ep in targets_raw}
    disallow = (SOURCE/'config/services_disallowlist.txt').read_text().splitlines()
    original_csv = list(csv.DictReader(io.StringIO(Path(config['original_aggregate']).read_text())))
    curves, graph_inventory, chunks, member_hashes = {}, {}, [], []
    grouped = defaultdict(list)
    all_mc_checks = []
    with zipfile.ZipFile(io.BytesIO(data)) as outer:
        members = safe_members(outer)
        assert {m.filename for m in members} == {m['member'] for m in manifest['members']}
        for index, lock in enumerate(manifest['members']):
            payload = outer.read(lock['member'])
            assert len(payload) == lock['bytes'] and sha256(payload).hexdigest() == lock['sha256']
            match = re.fullmatch(r'100x100/results_p(0\.[13579])_chunk(\d+)\.zip', lock['member'])
            assert match, lock['member']
            p_label, chunk_label = match.groups()
            p, chunk = float(p_label), int(chunk_label)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = safe_members(archive)
                member_hashes.append({'artifact_id': lock['artifact_id'], 'members': [
                    {'name': m.filename, 'bytes': m.file_size, 'sha256': sha256(archive.read(m)).hexdigest()}
                    for m in members]})
                graph_bytes = archive.read('graph.json')
                graph_hash = sha256(graph_bytes).hexdigest()
                assert archive.read('graph.sha256').decode().split()[0] == graph_hash
                replicas_bytes = archive.read('replicas.json')
                key = graph_hash + ':' + sha256(replicas_bytes).hexdigest()
                if key not in curves:
                    graph = json.loads(graph_bytes)
                    curves[key] = exact_curve(graph, json.loads(replicas_bytes), original, targets, disallow,
                                              max_pool=config['max_enumerated_containers'])
                    graph_inventory[key] = {'graph_sha256': graph_hash,
                        'replicas_sha256': sha256(replicas_bytes).hexdigest(),
                        'nodes': len(graph['services']), 'edges': len(graph['edges']),
                        'async_edges': len(graph.get('async_edges', [])),
                        'exact_control': curves[key]}
                curve = curves[key]
                models, model_docs = {}, {}
                for mode in MODES:
                    models[mode], model_docs[mode] = {}, {}
                    for ep in [None] + list(targets):
                        suffix = f'_e{original.safe_endpoint_label(ep)}' if ep else ''
                        tail = f'_chunk{chunk_label}' if ep else ''
                        name = f'model_mode{mode}{suffix}_p{p_label}{tail}.json'
                        doc = json.loads(archive.read(name))
                        assert doc['mode'] == mode and doc['p_fail'] == p
                        assert doc['samples'] == config['original_mc_samples']
                        assert doc['graph_hash'] == graph_hash
                        models[mode][ep], model_docs[mode][ep] = doc['R_model'], doc
                        if curve['supported']:
                            exact = (sum((probability(curve, target, mode, p) for target in targets), Fraction())
                                     / len(targets) if ep is None else probability(curve, ep, mode, p))
                            all_mc_checks.append({'artifact_id': lock['artifact_id'], 'mode': mode,
                                'endpoint': ep or 'uniform_random_endpoint',
                                'samples': doc['samples'], 'model': doc['R_model'],
                                'exact_numerator': exact.numerator, 'exact_denominator': exact.denominator,
                                'absolute_error': abs(doc['R_model'] - float(exact))})
                live_names = sorted(m.filename for m in members if re.fullmatch(
                    rf'live_p{re.escape(p_label)}_chunk{chunk_label}_\d+\.json', m.filename))
                assert len(live_names) == config['windows_per_chunk']
                assert {int(n.rsplit('_', 1)[1][:-5]) for n in live_names} == set(range(1, 101))
                logs = [json.loads(line) for line in archive.read(
                    f'window_log_p{p_label}_chunk{chunk_label}.jsonl').splitlines() if line.strip()]
                assert logs
                log_keys = {json.dumps(log, sort_keys=True) for log in logs}
                statuses, eligible, killed_n, killed_names, log_anomalies = Counter(), Counter(), Counter(), Counter(), Counter()
                annotation_checks = Counter()
                ep_totals = {ep: Counter() for ep in targets}
                values, mix_rows = [], []
                endpoint_rows = {ep: [] for ep in targets}
                for name in live_names:
                    live = json.loads(archive.read(name))
                    total, ok, status, endpoint_counts = probe_counts(live, targets)
                    assert total == config['probes_per_window']
                    statuses.update(status)
                    for ep, counts in endpoint_counts.items():
                        ep_totals[ep].update(counts)
                    log = live['window_log']
                    eligible[str(log.get('eligible'))] += 1
                    killed_n[str(log.get('killed'))] += 1
                    killed_names.update(log.get('services', []))
                    log_anomalies.update(list(log.get('anomaly', {})))
                    annotation_checks['present_in_window_log'] += json.dumps(log, sort_keys=True) in log_keys
                    annotation_checks['correct_p'] += log.get('p_fail') == p
                    annotation_checks['k_matches_declared_runtime_law'] += (
                        isinstance(log.get('eligible'), int) and
                        log.get('killed') == kill_count(log['eligible'], p))
                    if curve['supported']:
                        annotation_checks['runtime_eligible_count_matches_model'] += log.get('eligible') == curve['containers']
                    values.append(ok / total)
                    weighted = {mode: sum(endpoint_counts[ep]['total'] * models[mode][ep]
                                          for ep in targets) / total for mode in MODES}
                    rb, ra, rl = weighted['all-block'], weighted['async'], ok / total
                    mix_rows.append({'R_live': rl, 'R_model_all_block': rb, 'R_model_async': ra,
                        'bias_all_block': abs(rb - rl), 'bias_async': abs(ra - rl),
                        'delta_bias': abs(ra - rl) - abs(rb - rl), 'weight': total})
                    for ep in targets:
                        n, s = endpoint_counts[ep]['total'], endpoint_counts[ep]['ok']
                        if n:
                            rb, ra, rl = models['all-block'][ep], models['async'][ep], s/n
                            endpoint_rows[ep].append({'R_live': rl, 'R_model_all_block': rb,
                                'R_model_async': ra, 'bias_all_block': abs(rb-rl),
                                'bias_async': abs(ra-rl), 'delta_bias': abs(ra-rl)-abs(rb-rl), 'weight': n})
                columns = tuple(mix_rows[0])
                report_diffs = {'mix': compare_csv(archive,
                    f'reports/rows_p{p_label}_chunk{chunk_label}_mix.csv', mix_rows, columns)}
                for ep, rows in endpoint_rows.items():
                    report_diffs[ep] = compare_csv(archive,
                        f'reports/rows_p{p_label}_chunk{chunk_label}_e{original.safe_endpoint_label(ep)}.csv', rows, columns)
                rb, ra = models['all-block'][None], models['async'][None]
                result = {'artifact_id': lock['artifact_id'], 'p_fail': p, 'chunk': chunk,
                    'graph_key': key, 'windows': len(values), 'probes': sum(statuses.values()),
                    'status_counts': dict(statuses), 'per_endpoint': {ep: dict(c) for ep, c in ep_totals.items()},
                    'sum_live': sum(values), 'sum_sq_live': sum(v*v for v in values),
                    'model_block': rb, 'model_async': ra,
                    'global_window_mae_block': statistics.mean(abs(rb-v) for v in values),
                    'global_window_mae_async': statistics.mean(abs(ra-v) for v in values),
                    'mix_mean': {name: statistics.mean(row[name] for row in mix_rows) for name in columns},
                    'eligible_counts': dict(eligible), 'killed_counts': dict(killed_n),
                    'observed_killed_service_counts': dict(killed_names),
                    'window_log_records': len(logs), 'log_anomaly_fields': dict(log_anomalies),
                    'annotation_checks': dict(annotation_checks), 'report_max_abs_difference': report_diffs}
                chunks.append(result)
                grouped[p].append(result)
            if (index + 1) % 25 == 0:
                print(f'Verified and audited {index+1}/250 original chunks', flush=True)
                save(OUT/'progress.json', {'chunks': index+1, 'elapsed_seconds': time.perf_counter()-started})
    assert len(chunks) == 250 and len({(r['p_fail'], r['chunk']) for r in chunks}) == 250
    aggregate = []
    for old in original_csv:
        p = float(old['p_fail'])
        rows = grouped[p]
        assert len(rows) == 50
        windows = sum(r['windows'] for r in rows)
        sums = sum(r['sum_live'] for r in rows)
        sums_sq = sum(r['sum_sq_live'] for r in rows)
        rb = statistics.mean(r['model_block'] for r in rows)
        ra = statistics.mean(r['model_async'] for r in rows)
        mb = statistics.mean(r['global_window_mae_block'] for r in rows)
        ma = statistics.mean(r['global_window_mae_async'] for r in rows)
        recomputed = {'windows_total': windows, 'sum_R_live': sums, 'sum_sq_R_live': sums_sq,
            'R_live_mean': sums/windows, 'R_live_var': sums_sq/windows-(sums/windows)**2,
            'R_model_all_block_mean': rb, 'R_model_async_mean': ra,
            'mean_bias_all_block_mean': mb, 'mean_bias_async_mean': ma,
            'mean_delta_bias_mean': mb-ma}
        differences = {name: abs(float(old[name])-value) for name, value in recomputed.items()}
        status = Counter()
        checks = Counter()
        eps = {ep: Counter() for ep in targets}
        for row in rows:
            status.update(row['status_counts'])
            checks.update(row['annotation_checks'])
            for ep in targets:
                eps[ep].update(row['per_endpoint'][ep])
        aggregate.append({'p_fail': p, 'recomputed_original_global': recomputed,
            'original_csv_max_abs_differences': differences,
            'delta_orientation': 'global CSV all-block MAE minus async MAE; source row delta has opposite sign',
            'forecast_async_minus_block_pp': 100*(ra-rb), 'signed_model_minus_live_pp': 100*(rb-sums/windows),
            'mix_recomputed_mean': {name: statistics.mean(r['mix_mean'][name] for r in rows) for name in columns},
            'status_counts': dict(status), 'annotation_checks': dict(checks),
            'per_endpoint': {ep: dict(counts) for ep, counts in eps.items()}})
    family_size = config['expected_mc_records']
    assert len(all_mc_checks) == family_size or any(not c['supported'] for c in curves.values())
    for check in all_mc_checks:
        # Union bound, independent Bernoulli trials within each original simulation assumed.
        check['family_hoeffding_radius'] = math.sqrt(math.log(2*family_size/config['mc_family_alpha']) / (2*check['samples']))
        check['within_family_bound'] = check['absolute_error'] <= check['family_hoeffding_radius']
    summary = {'version': config['version'], 'source_run': manifest['original_run'],
        'audit_run': os.environ['GITHUB_RUN_ID'], 'head': os.environ['GITHUB_SHA'],
        'protocol_sha256': sha256(CONFIG.read_bytes()).hexdigest(),
        'outer_bytes': len(data), 'outer_sha256': sha256(data).hexdigest(),
        'chunks': len(chunks), 'windows': sum(r['windows'] for r in chunks),
        'probes': sum(r['probes'] for r in chunks), 'unique_graph_replica_pairs': len(curves),
        'enumeration_supported_pairs': sum(c['supported'] for c in curves.values()),
        'distinct_enumerated_states': sum(c.get('states', 0) for c in curves.values()),
        'changed_endpoint_states': sum(sum(sum(counts.values()) for counts in c['changed'].values())
                                       for c in curves.values() if c['supported']),
        'mc_records': len(all_mc_checks), 'mc_outside_family_bound': sum(not c['within_family_bound'] for c in all_mc_checks),
        'largest_mc_absolute_error': max((c['absolute_error'] for c in all_mc_checks), default=None),
        'report_largest_absolute_difference': max(v for r in chunks for d in r['report_max_abs_difference'].values() for v in d.values()),
        'elapsed_seconds': time.perf_counter()-started, 'aggregate': aggregate,
        'main_campaigns': 0, 'new_independent_campaigns': 0, 'new_mc_draws': 0,
        'scope': 'Exact historical payload audit; old event and fixed-cardinality source law, not modern two-second SLO',
        'limitations': ['Upstream runtime was fetched from main without immutable pin',
            'Original Monte Carlo seeds absent; exact distribution check is not bitwise MC replay',
            'Window-log annotations do not prove failure state throughout sequential probes',
            'Observed source predicates and graph law do not establish business adequacy or causal attribution',
            'No prospective mechanism selected or refined from this descriptive audit']}
    save(OUT/'summary.json', summary)
    save(OUT/'chunk-census.json', chunks)
    save(OUT/'graph-control-inventory.json', graph_inventory)
    save(OUT/'original-mc-controls.json', all_mc_checks)
    save(OUT/'original-member-hashes.json', member_hashes)
    save(OUT/'input-provenance.json', {'asset': config['asset'], 'transfer_manifest_sha256': sha256(Path(config['transfer_manifest']).read_bytes()).hexdigest(), 'repository_locks': config['repository_locks']})
    print(json.dumps({k: summary[k] for k in ('chunks','windows','probes','unique_graph_replica_pairs','changed_endpoint_states','report_largest_absolute_difference')}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        save(OUT/'failure.json', {'type': type(exc).__name__, 'message': str(exc)})
        raise
