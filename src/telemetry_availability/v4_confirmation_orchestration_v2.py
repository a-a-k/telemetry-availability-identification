"""Preserve twelve unopened cohorts; recollect only six technically lost cohorts."""
from datetime import datetime,timezone
import os
from pathlib import Path

from . import v4_confirmation_orchestration_v1 as fixed
from .v3_comparison_roles_v1 import load_role,digest
from .v3_primary_projection import read,write,sha

SOURCE_RUN=34701084950
SOURCE_HEAD='1d43c3d5ec7852b4dbedf30b3c9e3e8cfd7e557b'
original_verify=fixed.verify_new_locks


def verify_new_locks():
    original_verify()
    config=read(Path('configs/v4_confirmation_locks_v2.json'))
    for name,expected in config['files'].items():
        if sha(Path(name))!=expected:raise ValueError('technical amendment source changed: '+name)
    return config


def validate_acquisition(receipt,identity):
    expected=(str(SOURCE_RUN),SOURCE_HEAD) if identity['application']!='spring_petclinic_microservices' else (os.environ['GITHUB_RUN_ID'],os.environ['GITHUB_SHA'])
    if (str(receipt['acquisition_run']),receipt['acquisition_head'])!=expected:
        raise ValueError('acquisition differs from the fixed source map')
    if receipt['identity']!=identity:raise ValueError('restored acquisition identity changed')
    if not all(receipt.get(k) for k in ('test_binding_seal_sha256','primary_closed_seal_sha256')):
        raise ValueError('independent confirmation roles missing')


def freeze(source,out,identity,operations):
    fixed.old.freeze_case(source,out,identity,operations)
    documents,_=load_role(out/'frozen','frozen_candidates',identity)
    fixed.validate_complete(documents['candidates.json'],operations)
    receipt=documents['receipt.json']['acquisition_receipt']
    validate_acquisition(receipt,identity)
    write(out/'gate.json',dict(identity=identity,candidate_digest=digest(documents['candidates.json']),
        frozen_seal_sha256=sha(out/'frozen/seal.json'),all_numerical_forecasts_fixed=True,
        created_at=datetime.now(timezone.utc).isoformat(),run=os.environ['GITHUB_RUN_ID'],head=os.environ['GITHUB_SHA'],
        closed_outcomes_downloaded=False,historical_C12_reclassified=False,
        technical_amendment_sha256=sha(Path('docs/milestones/V4_CONFIRMATION_V2_TECHNICAL_AMENDMENT.md')),
        acquisition_run=receipt['acquisition_run'],acquisition_head=receipt['acquisition_head']))
    fixed.check_gate(out,identity)


def main():
    fixed.verify_new_locks=verify_new_locks
    fixed.freeze=freeze
    fixed.main()


if __name__=='__main__':main()
