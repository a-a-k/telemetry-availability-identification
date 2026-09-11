"""Retain only three allowlisted scalar CUDD evidence documents per profile."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import retain_v3_comparison_compact_v4 as transport


def require(value, message):
    if not value: raise ValueError(message)


def check_compact(result, config):
    index = config['profiles'].index(result['profile'])
    require(len(result['cases']) == config['expected_models'][index]
            and len(result['cases'])+len(result['absent']) == config['expected_cases'][index], 'compact case census differs')
    ids = {c['case_id'] for c in result['cases']}
    require(len(ids) == len(result['cases']) and not ids & {c['case_id'] for c in result['absent']}, 'duplicate/overlapping case identities')
    expected = {(case_id, method, r) for case_id in ids for method in config['methods'] for r in range(config['technical_rounds'])}
    actual = [(r['case_id'], r['method'], r['round']) for r in result['records']]
    require(len(actual) == len(expected) and set(actual) == expected, 'measurement census differs')
    require(len(result['process_resources']) == 12, 'resource census differs')
    for record in result['records']:
        if record['status'] == 'qualified':
            require(record['cold_ns'] > 0 and len(record['warm_ns']) == config['warm_queries']
                    and all(n > 0 for n in record['warm_ns']) and record['checks']['exact_estimates_verified'] == 11,
                    'invalid qualified measurement')
        else:
            require(record['status'] == 'failed' and record.get('error'), 'undocumented failure')
    if result['qualified']:
        require(all(r['status'] == 'qualified' for r in result['records']), 'failures promoted')
        by_id = {c['case_id']:c for c in result['cases']}
        for case_id in ids:
            records = [r for r in result['records'] if r['case_id'] == case_id]
            exact_hash = sha256((json.dumps(by_id[case_id]['estimates'], sort_keys=True, allow_nan=False)+'\n').encode()).hexdigest()
            require(len({r['category_extrema_sha256'] for r in records}) == 1
                    and {r['exact_estimates_sha256'] for r in records} == {exact_hash}, 'exact solver results differ')
    banned = {'model', 'models', 'graph', 'replicas', 'signal_ids', 'observation_categories', 'category_certificates',
              'lower_witness', 'upper_witness', 'full-inputs.json', 'native_spans'}
    def visit(value):
        if isinstance(value, dict):
            require(not banned & set(value), 'forbidden model/native payload in compact evidence')
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    args = parser.parse_args()
    run = transport.read_api(f'actions/runs/{args.run}')
    require(run['path'] == '.github/workflows/v3-bdd-comparison-v1.yml' and run['run_attempt'] == 1
            and run['status'] == 'completed', 'wrong or unfinished CUDD run')
    protocol_raw = subprocess.check_output(['git', 'show', run['head_sha']+':configs/v3_bdd_comparison_v1.json'])
    config = json.loads(protocol_raw)
    artifacts = transport.collect_pages(f'actions/runs/{args.run}/artifacts', 'artifacts')
    by_name = {item['name']:item for item in artifacts}
    root = Path(f'docs/evidence/v3-bdd-comparison-{args.run}')
    transport.persist(root/'.gitattributes', b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    receipts = []
    for profile in config['profiles']:
        name = f'v3-bdd-compact-{profile}-{args.run}'
        require(name in by_name, 'missing compact profile: '+profile)
        item = by_name[name]
        require(item['workflow_run']['head_sha'] == run['head_sha'] and item['size_in_bytes'] <= 15_000_000, 'wrong/oversized compact artifact')
        raw = transport.api(f'actions/artifacts/{item["id"]}/zip')
        names = {'protocol.json', 'environment.json', 'results.json'}
        members = transport.check_archive(raw, item, names)
        require(set(members) == names and members['protocol.json'] == protocol_raw, 'compact source/member census differs')
        result, env = json.loads(members['results.json']), json.loads(members['environment.json'])
        for document in (result, env):
            require(document['profile'] == profile and document['run_id'] == args.run and document['head'] == run['head_sha']
                    and document['config_sha256'] == sha256(protocol_raw).hexdigest(), 'compact run identity differs')
        check_compact(result, config)
        out = root/profile
        transport.persist(out/'compact.zip', raw)
        for key, value in members.items(): transport.persist(out/key, value)
        transport.persist(out/'artifact-api.json', transport.encoded(item))
        receipts.append(dict(profile=profile, artifact_id=item['id'], bytes=len(raw), sha256=sha256(raw).hexdigest(),
                             qualified=result['qualified'], models=len(result['cases']), absent=len(result['absent']), records=len(result['records'])))
    transport.persist(root/'run-api.json', transport.encoded(run))
    receipt = dict(version='v3-bdd-compact-retention-v1', run_id=args.run, head=run['head_sha'], conclusion=run['conclusion'],
                   artifacts=receipts, full_models_or_certificates_downloaded=False, local_model_execution=False)
    transport.persist(root/'retention.json', transport.encoded(receipt))
    print(json.dumps(receipt))


if __name__ == '__main__': main()
