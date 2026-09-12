"""Retain the fixed candidate-binding diagnostic, without raw models or traces."""
import argparse
from collections import Counter
import json

import retain_v3_comparison_compact_v4 as transport
from audit_v3_attempts_v1 import ROOT, read
from retain_v3_attempt_audit_v1 import table_bytes


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=int,required=True);p.add_argument('--head',required=True)
    args=p.parse_args();run=transport.read_api(f'actions/runs/{args.run}')
    if (run['head_sha']!=args.head or run['path']!='.github/workflows/v4-binding-diagnostic-v1.yml'
            or run['run_attempt']!=1 or run['status']!='completed'):raise ValueError('diagnostic provenance differs')
    config=read(ROOT/'configs/v4_binding_diagnostic_v1.json');sources=transport.collect_pages(f'actions/runs/{args.run}/artifacts','artifacts')
    by_name={a['name']:a for a in sources};root=ROOT/f'docs/evidence/v4-binding-diagnostic-v1-{args.run}'
    settings=read(ROOT/'configs/v3_comparison_execution_v3.json');selected=[];profiles={};rows=[];queries=[]
    for app in sorted({c['identity']['application'] for c in config['cases']}):
        cases=[c for c in config['cases'] if c['identity']['application']==app]
        allowed={c['artifact_key']+'.json' for c in cases}|{'receipt.json'}
        artifact=by_name[f'v4-binding-diagnostic-v1-compact-{app}-{args.run}']
        members=transport.check_archive(transport.api(f"actions/artifacts/{artifact['id']}/zip"),artifact,allowed)
        if set(members)!=allowed:raise ValueError('incomplete diagnostic census')
        counts=Counter()
        for member,content in members.items():
            data=json.loads(content)
            if data['run']!=str(args.run) or data['head']!=args.head:raise ValueError('inner diagnostic identity differs')
            transport.persist(root/app/member,content)
            if member=='receipt.json':continue
            counts['campaigns']+=1;ident=data['identity']
            for r in data['operations']:
                counts['operations']+=1
                planned=settings['profiles'][app]['operations'][r['operation']]['expected_attempts'];counts['planned_attempts']+=planned
                prefix=dict(application=app,placement=ident['placement'],law=ident['law'],repetition=ident['repetition'],operation=r['operation'])
                row=dict(prefix,status=r['status'],planned_attempts=planned)
                for key in ('attempts','successes','lower_exact','upper_exact','b0_exact','success_excluded','failure_excluded',
                    'incompatible_attempts','incompatible_fraction','fully_observed_attempts','fully_observed_mismatches',
                    'ambiguous_attempts','checked_witness_endpoints'):
                    row[key]=r.get(key)
                rows.append(row)
                if r['status']=='unsupported':counts['unsupported_operations']+=1;continue
                counts['supported_operations']+=1
                for key in ('attempts','success_excluded','failure_excluded','incompatible_attempts','fully_observed_attempts',
                    'fully_observed_mismatches','ambiguous_attempts','checked_witness_endpoints'):counts[key]+=r[key]
                counts['point_models']+=r['lower_exact']==r['upper_exact'];counts['interval_models']+=r['lower_exact']!=r['upper_exact']
                for verdict in r['exact_qualification']:
                    queries.append(dict(prefix,**verdict));counts['exact_backend_queries']+=1
                for reasons in r['completion_evidence_counts'].values():
                    for reason,n in reasons.items():
                        if 'retry' in reason:counts['completion:'+reason]+=n
        profiles[app]=dict(counts);selected.append({k:artifact[k] for k in ('id','name','digest','size_in_bytes')})
    transport.persist(root/'retention.json',transport.encoded(dict(run=args.run,head=args.head,artifacts=selected,full_primary_artifacts_downloaded=False)))
    tables=ROOT/f'docs/tables/v4-binding-diagnostic-v1-{args.run}'
    transport.persist(tables/'attempt-compatibility.csv',table_bytes(rows))
    transport.persist(tables/'exact-qualification.csv',table_bytes(queries))
    summary=dict(run=args.run,head=args.head,applications=profiles,independent_confirmation=False,performance_comparison=False)
    transport.persist(tables/'summary.json',transport.encoded(summary));print(json.dumps(summary))


if __name__=='__main__':main()
