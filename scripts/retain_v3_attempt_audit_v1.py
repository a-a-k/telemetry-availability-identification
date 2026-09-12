"""Retain allowlisted scalar audit artifacts, including a completed first wave."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path

import retain_v3_comparison_compact_v4 as transport
from audit_v3_attempts_v1 import ROOT, PROTOCOL, read


def table_bytes(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader(); writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True); parser.add_argument('--head', required=True)
    parser.add_argument('--wave', choices=['first', 'all'], required=True)
    args = parser.parse_args(); protocol = read(PROTOCOL)
    run = transport.read_api(f'actions/runs/{args.run}')
    if (run['head_sha'] != args.head or run['path'] != '.github/workflows/v3-attempt-audit-v1.yml'
            or run['run_attempt'] != 1): raise ValueError('audit run provenance differs')
    artifacts = transport.collect_pages(f'actions/runs/{args.run}/artifacts', 'artifacts')
    by_name = {a['name']:a for a in artifacts}
    if len(by_name) != len(artifacts): raise ValueError('duplicate artifact names')
    settings = read(ROOT/'configs/v3_comparison_execution_v3.json')
    root = ROOT/f'docs/evidence/v3-attempt-audit-v1-{args.run}'/args.wave
    selected = []; summaries = []; missing = []
    for app in sorted(settings['profiles']):
        cases = [c for c in protocol['cases'] if c['identity']['application'] == app]
        if args.wave == 'first': cases = cases[:protocol['first_wave_campaigns_per_application']]
        role = 'first' if args.wave == 'first' else 'compact'
        name = f'v3-attempt-audit-v1-{role}-{app}-{args.run}'
        if name not in by_name:
            missing.append(name); continue
        artifact = by_name[name]; allowed = {'wave-first.json', 'wave-all.json'}
        for case in cases:
            key = case['artifact_key']
            allowed.update({f'cases/{key}.json', f'failures/{key}.json'})
            allowed.update(f'examples/{key}/{op}.json' for op in settings['profiles'][app]['operations'])
        blob = transport.api(f"actions/artifacts/{artifact['id']}/zip")
        members = transport.check_archive(blob, artifact, allowed)
        for member, content in members.items():
            transport.persist(root/app/member, content)
            if member.startswith('cases/'):
                case = json.loads(content)
                if case['audit_run'] != str(args.run) or case['audit_head'] != args.head:
                    raise ValueError('inner audit identity differs')
                summaries.append(case)
        selected.append({k:artifact[k] for k in ('id','name','digest','size_in_bytes','created_at','updated_at')})
    # A first-wave artifact is immutable even while the remaining census runs.
    # Provider run status is kept out of that immutable receipt.
    if missing:
        print(json.dumps(dict(retained_profiles=len(selected), pending=missing)))
        return
    receipt = dict(run=args.run, head=args.head, wave=args.wave, url=run['html_url'],
        artifacts=selected, full_primary_artifacts_downloaded=False, compact_cases=len(summaries))
    transport.persist(root/'retention.json', transport.encoded(receipt))
    rows = []; counters = {}
    for case in summaries:
        ident = case['identity']; app = ident['application']; counts = counters.setdefault(app, Counter())
        counts['campaigns'] += 1
        for op in case['operations']:
            counts['operations'] += 1; counts['all_attempts'] += op['attempts']
            row = dict(application=app, placement=ident['placement'], law=ident['law'], repetition=ident['repetition'],
                operation=op['operation'], status=op['status'], attempts=op['attempts'])
            for key in ('successes','lower_exact','upper_exact','b0_exact','success_excluded','failure_excluded',
                        'incompatible_attempts','incompatible_fraction','fully_observed_attempts','fully_observed_mismatches',
                        'ambiguous_attempts','aggregate_excess_above_upper_count','aggregate_deficit_below_lower_count',
                        'aggregate_contains_b0','incompatible_despite_aggregate_containment',
                        'ablation_without_selection_incompatible_attempts'):
                row[key] = op.get(key)
            rows.append(row)
            if op['status'] != 'audited': counts['unsupported_operations'] += 1; continue
            counts['audited_operations'] += 1; counts['audited_attempts'] += op['attempts']
            for key in ('success_excluded','failure_excluded','incompatible_attempts','fully_observed_attempts',
                        'fully_observed_mismatches','ambiguous_attempts','aggregate_excess_above_upper_count',
                        'aggregate_deficit_below_lower_count','incompatible_despite_aggregate_containment'):
                counts[key] += op[key]
            counts['operations_with_incompatible_attempts'] += op['incompatible_attempts'] > 0
            for flag, count in op['incompatible_flag_counts'].items(): counts['flag:'+flag] += count
    rows.sort(key=lambda r: (r['application'],r['placement'],r['law'],r['repetition'],r['operation']))
    tables = ROOT/f'docs/tables/v3-attempt-audit-v1-{args.run}'/args.wave
    if rows: transport.persist(tables/'operation-compatibility.csv', table_bytes(rows))
    summary = dict(run=args.run, head=args.head, wave=args.wave, applications={k:dict(v) for k,v in counters.items()},
        complete_planned_wave=len(summaries)==(12 if args.wave=='first' else 240),
        flags_can_overlap=True, flags_are_not_causal_classification=True)
    transport.persist(tables/'summary.json', transport.encoded(summary))
    print(json.dumps(summary))


if __name__ == '__main__': main()
