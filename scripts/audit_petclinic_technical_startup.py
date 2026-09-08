"""Remote-only, read-only audit of a retained technical startup failure."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-id', type=int, required=True)
    args = parser.parse_args()
    repo = 'repos/a-a-k/telemetry-availability-identification'
    meta = json.loads(subprocess.check_output(['gh', 'api', f'{repo}/actions/artifacts/{args.artifact_id}']))
    assert meta['workflow_run']['id'] == 34202539028
    assert meta['workflow_run']['head_sha'] == '06e83aad5f65f17365c7715ca3b312938b94f1a9'
    assert meta['name'].startswith('petclinic-technical-raw-')
    raw = subprocess.check_output(['gh', 'api', f'{repo}/actions/artifacts/{args.artifact_id}/zip'])
    sha = hashlib.sha256(raw).hexdigest()
    assert len(raw) == meta['size_in_bytes'] and meta['digest'] == 'sha256:' + sha
    out = Path('workflow-results/startup-audit')
    out.mkdir(parents=True, exist_ok=True)
    archive = Path('workflow-results/source.zip')
    archive.write_bytes(raw)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = set(z.namelist())
        warmup = json.loads(z.read('warmup.json'))
        states = json.loads(z.read('final-containers.json'))
        lines = z.read('logs/services.log').decode(errors='replace').splitlines()
        summary = dict(artifact=meta, actual_sha256=sha, zip_crc_verified=True,
            files={n: dict(bytes=len(z.read(n)), sha256=hashlib.sha256(z.read(n)).hexdigest()) for n in sorted(names)},
            warmup_attempts=len(warmup), warmup_unique_ids=len({r['request_id'] for r in warmup}),
            per_operation=[dict(operation=op, attempts=len(chosen), successes=sum(r['semantic_success'] for r in chosen),
                statuses=dict(Counter(str(r.get('status_code')) for r in chosen)),
                verdicts=dict(Counter(str(r.get('failure_reason',r.get('error'))) for r in chosen)), last_responses=chosen[-2:])
                for op in sorted({r['operation'] for r in warmup}) for chosen in [[r for r in warmup if r['operation']==op]]],
            containers=[dict(name=s['Name'],state=s['State'],restart_count=s['RestartCount']) for s in states],
            acquired_periods=json.loads(z.read('periods.json')) if 'periods.json' in names else {},
            fits=0)
        error_indices=[i for i,line in enumerate(lines) if re.search(r'ERROR|Exception|Caused by:|OutOfMemory|killed|failed to|APPLICATION FAILED',line,re.I)]
        retained=sorted({j for i in error_indices for j in range(max(0,i-2), min(len(lines),i+5))})
        (out/'service-errors.log').write_text('\n'.join(f'{i+1}: {lines[i]}' for i in retained),encoding='utf-8')
        (out/'startup-audit.json').write_text(json.dumps(summary,indent=2,sort_keys=True),encoding='utf-8')
        print(json.dumps(dict(warmup_attempts=len(warmup),containers=summary['containers'],error_lines=len(retained))))


if __name__ == '__main__':
    main()
