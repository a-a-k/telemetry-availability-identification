"""Bounded source checks: retain failure, reject missing cohorts or wrong heads."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import archive_v3_performance_evidence_v1 as source


def cohort(run_id):
    head, workflow, conclusion = source.SOURCES[run_id]
    run = dict(id=run_id, head_sha=head, path='.github/workflows/' + workflow,
               conclusion=conclusion, status='completed', run_attempt=1,
               head_repository={'full_name': source.transport.REPO})
    artifacts = [dict(id=i, name=name, size_in_bytes=100, expired=False,
                      workflow_run={'id': run_id, 'head_sha': head})
                 for i, name in enumerate(sorted(source.expected_names(run_id)))]
    return run, artifacts


def test_declared_original_failure_is_preserved_and_success_not_assumed():
    for run_id in source.SOURCES:
        run, artifacts = cohort(run_id)
        source.checked_source(run, artifacts)
        changed = deepcopy(run)
        changed['conclusion'] = 'success' if run['conclusion'] == 'failure' else 'failure'
        with pytest.raises(ValueError, match='cohort'):
            source.checked_source(changed, artifacts)


def test_missing_artifact_and_changed_source_are_rejected():
    for run_id in source.SOURCES:
        run, artifacts = cohort(run_id)
        with pytest.raises(ValueError, match='census'):
            source.checked_source(run, artifacts[:-1])
        changed = deepcopy(artifacts)
        changed[0]['workflow_run']['head_sha'] = '0' * 40
        with pytest.raises(ValueError, match='source/size'):
            source.checked_source(run, changed)
