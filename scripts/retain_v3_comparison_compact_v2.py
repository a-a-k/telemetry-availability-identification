"""Retain allowlisted compact v3 comparison evidence; never fetch native/model roles.

This performs provenance/ZIP checks only, not application parsing, fitting or replay.
Run after the workflow is terminal; failed and absent artifacts remain explicit.
"""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import zipfile

REPO = 'a-a-k/telemetry-availability-identification'
WORKFLOW = '.github/workflows/v3-prospective-comparison-v2.yml'
DESIGN = Path('configs/v3_comparison_design_v2.json')
DESIGN_SHA = '7a627ed1241a3247b558fcb3ede26279f800f566ca2a2720d85f90fb2bbf6aef'
MAX_ARCHIVE = 100_000_000
MAX_MEMBER = 150_000_000
MAX_EXPANDED = 200_000_000


def api(path):
    return subprocess.check_output(['gh', 'api', 'repos/' + REPO + '/' + path])


def read_api(path):
    return json.loads(api(path))


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def persist(path, content):
    """A repeat can only verify identical bytes, never replace retained evidence."""
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('retained evidence differs: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def collect_pages(path, key):
    rows = []; page = 1; total = None
    while True:
        data = read_api(path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
        total = data['total_count'] if total is None else total
        if data['total_count'] != total:
            raise ValueError('provider census changed during retention')
        rows.extend(data[key])
        if len(rows) >= total:
            break
        if not data[key]:
            raise ValueError('incomplete provider pagination')
        page += 1
    if len(rows) != total or len({r['id'] for r in rows}) != total:
        raise ValueError('provider census duplicated/incomplete')
    return rows


def selections(run_id, mode):
    raw = DESIGN.read_bytes()
    if sha256(raw).hexdigest() != DESIGN_SHA:
        raise ValueError('retainer design version differs')
    settings = json.loads(raw); design = dict(settings['design'])
    if mode == 'preflight':
        design.update(settings['preflight'])
    elif mode != 'main':
        raise ValueError('unsupported comparison mode')
    selected = {}; cases = []; profile_members = {}
    for profile in design['applications']:
        profile_members[profile] = {'controls.json'}
        for placement in design['placements']:
            for law in design['laws']:
                for repetition in design['repetitions']:
                    identity = dict(application=profile, placement=placement, law=law, repetition=repetition,
                        namespace=settings[mode+'_namespace'],
                        data_role='prospective_main' if mode=='main' else 'development_preflight',
                        protocol_sha256=DESIGN_SHA)
                    key = profile+'--'+placement+'--'+law+'--r'+str(repetition)
                    ident_hash = sha256(json.dumps(identity, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                    prefix = 'campaign-' + ident_hash[:20] + '/'
                    profile_members[profile].update(prefix + name for name in ('candidates.json', 'costs.json', 'read-audit.json', 'seal.json'))
                    ordinal = len(cases) + 1
                    cases.append(dict(identity=identity, artifact_key=key, local_case=f'case-{ordinal:03d}'))
                    roles = {
                        'receipt': {'receipt.json', 'costs.json'},
                        'graph-compact': {'results.json', 'replay.json', 'build-resource-usage.txt', 'replay-resource-usage.txt', 'resource-summary.json'},
                        'frozen': {'absence.json', 'frozen/candidates.json', 'frozen/receipt.json', 'frozen/costs.json', 'frozen/seal.json'},
                        'evaluation': {'evaluation.json', 'evaluation-seal.json'},
                    }
                    for role, members in roles.items():
                        selected[f'v3-comparison-{role}-{key}-{run_id}'] = dict(
                            directory=f'case-{ordinal:03d}/{role}', allowed=members)
    for index, (profile, members) in enumerate(profile_members.items(), 1):
        selected[f'v3-comparison-pmx-candidates-{profile}-{run_id}'] = dict(
            directory=f'pmx-{index:02d}', allowed=members)
    selected[f'v3-comparison-compact-{run_id}'] = dict(directory='analysis', allowed={'comparison.json', 'comparison-seal.json'})
    return selected, cases


def check_archive(data, artifact, allowed):
    if artifact['expired'] or not 0 < artifact['size_in_bytes'] <= MAX_ARCHIVE:
        raise ValueError('expired/oversized/empty compact archive')
    if len(data) != artifact['size_in_bytes'] or 'sha256:' + sha256(data).hexdigest() != artifact['digest']:
        raise ValueError('provider ZIP size/digest differs')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist(); names = [r.filename for r in infos]
        if not names or len(names) != len(set(names)) or not set(names) <= allowed:
            raise ValueError('unlisted/duplicate/empty compact ZIP members')
        if any(r.is_dir() or r.file_size > MAX_MEMBER or (r.external_attr >> 16) & 0o170000 == 0o120000 for r in infos):
            raise ValueError('directory/symlink/oversized compact member')
        if sum(r.file_size for r in infos) > MAX_EXPANDED:
            raise ValueError('expanded compact archive exceeds bound')
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC mismatch')
        return {name: archive.read(name) for name in sorted(names)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--mode', choices=['preflight', 'main'], required=True)
    args = parser.parse_args()
    if args.run <= 0 or len(args.head) != 40 or any(c not in '0123456789abcdef' for c in args.head):
        raise ValueError('exact positive run ID and full commit SHA required')
    selected, cases = selections(args.run, args.mode)
    run = read_api(f'actions/runs/{args.run}')
    if (run['id'] != args.run or run['head_sha'] != args.head or run['path'] != WORKFLOW or
            run['status'] != 'completed' or run['run_attempt'] != 1):
        raise ValueError('run identity/version/terminal state differs; reruns need a separate policy')
    artifacts = collect_pages(f'actions/runs/{args.run}/artifacts', 'artifacts')
    jobs = collect_pages(f'actions/runs/{args.run}/jobs', 'jobs')
    names = [a['name'] for a in artifacts]
    if len(names) != len(set(names)):
        raise ValueError('duplicate artifact names')
    root = Path(f'docs/evidence/v3-comparison-{args.mode}-{args.run}')
    persist(root/'run-api.json', encoded({k: run[k] for k in (
        'id', 'head_sha', 'status', 'conclusion', 'html_url', 'created_at', 'updated_at', 'run_attempt', 'path')}))
    persist(root/'jobs-api.json', encoded(jobs))
    persist(root/'all-artifact-metadata.json', encoded(artifacts))
    persist(root/'planned-identities.json', encoded(cases))
    persist(root/'retention-allowlist.json', encoded({k: dict(directory=v['directory'], allowed=sorted(v['allowed'])) for k, v in selected.items()}))
    records = []
    for artifact in sorted(artifacts, key=lambda a: a['name']):
        if artifact['name'] not in selected:
            continue
        choice = selected[artifact['name']]
        if artifact['expired'] or not 0 < artifact['size_in_bytes'] <= MAX_ARCHIVE:
            raise ValueError('compact archive unavailable/oversized before download')
        # This is the only content-fetch endpoint; its exact name is allowlisted.
        data = api(f"actions/artifacts/{artifact['id']}/zip")
        members = check_archive(data, artifact, choice['allowed'])
        destination = root/choice['directory']
        persist(destination/'compact.zip', data)
        persist(destination/'artifact-api.json', encoded(artifact))
        hashes = []
        for name, content in members.items():
            persist(destination/'files'/name, content)
            hashes.append(dict(name=name, bytes=len(content), sha256=sha256(content).hexdigest()))
        persist(destination/'member-hashes.json', encoded(hashes))
        records.append(dict(artifact_id=artifact['id'], name=artifact['name'], directory=choice['directory'],
            bytes=len(data), sha256=sha256(data).hexdigest(), members=len(members),
            absent_allowed_members=sorted(choice['allowed'] - set(members))))
    absent = sorted(set(selected) - set(names))
    manifest = dict(run_id=args.run, head=args.head, mode=args.mode, protocol_sha256=DESIGN_SHA,
        workflow_conclusion=run['conclusion'], planned_campaigns=len(cases),
        selected_artifacts=len(selected), retained_artifacts=len(records), absent_artifacts=absent,
        retained_bytes=sum(r['bytes'] for r in records), retained_members=sum(r['members'] for r in records),
        raw_native_ordinary_model_solver_payloads_downloaded=False, records=records)
    persist(root/'verified-archives.json', encoded(manifest))
    persist(root/'.gitattributes', b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'records'}))


if __name__ == '__main__':
    main()
