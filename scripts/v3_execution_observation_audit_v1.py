"""Restore pinned ordinary inputs remotely and retain compact audit provenance."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from telemetry_availability.health_prefix_audit_v3 import restore
from telemetry_availability.v3_primary_projection import FILES, verify_bundle

CONFIG = Path('configs/v3_execution_observation_audit_v1.json')
OUT = Path('workflow-results/compact')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2) + '\n').encode())


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Ordinary application restore is remote only'
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=('prepare', 'report'))
    parser.add_argument('--profile', required=True)
    args = parser.parse_args()
    settings = json.loads(CONFIG.read_bytes())
    for lock in settings['repository_locks']:
        assert sha256(Path(lock['path']).read_bytes()).hexdigest() == lock['sha256'], lock['path']
    spec = settings['profiles'][args.profile]
    if args.stage == 'prepare':
        archive, metadata = restore(spec['artifact'])
        assert {n for n in archive.namelist() if not n.endswith('/')} == FILES | {'seal.json'}
        root = Path('workflow-input/ordinary'); root.mkdir(parents=True, exist_ok=True)
        for name in sorted(FILES | {'seal.json'}):
            (root/name).write_bytes(archive.read(name))
        archive.close()
        seal = verify_bundle(root)
        save(OUT/'source-audit.json', dict(artifact=metadata, ordinary_seal=seal,
            profile=args.profile, role_scope=spec['role_scope'], source_transfer_bytes=spec['artifact']['size_in_bytes'],
            source_run=spec['artifact']['source_run'], source_head=spec['artifact']['source_head'],
            expected_operations=spec['operations'], expected_attempts_per_operation=spec['expected_attempts_per_operation'],
            evaluator_files_received=False, controller_files_received=False, main_campaigns=0,
            actual_input_bytes=sum(p.stat().st_size for p in root.iterdir())))
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
            stream.write('operations=' + ' '.join(spec['operations']) + '\n')
    else:
        audit = json.loads((OUT/'execution-observation-audit.json').read_bytes())
        reads = json.loads((OUT/'consumer-read-audit.json').read_bytes())
        assert len(reads['actual_data_reads']) == 6 and not reads['blocked']
        assert audit['manifest']['profile'] == args.profile
        assert set(audit['operations']) == set(spec['operations'])
        assert all(r['census']['attempts'] == spec['expected_attempts_per_operation'] for r in audit['operations'].values())
        save(OUT/'completion.json', dict(run_id=os.environ['GITHUB_RUN_ID'], head=os.environ['GITHUB_SHA'],
            protocol_sha256=sha256(CONFIG.read_bytes()).hexdigest(), profile=args.profile,
            census_complete=True, operations=len(audit['operations']), external_attempts=audit['external_attempts'],
            interpretation='Observation census complete; this is not estimator or business-adequacy qualification',
            model_fits=0, main_campaigns=0, new_independent_campaigns=0))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        save(OUT/'failure.json', dict(type=type(exc).__name__, message=str(exc)))
        raise
