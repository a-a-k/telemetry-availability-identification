"""Remote diagnostic census of a versioned historical HAProxy decoder fix.

Privileged historical health is diagnostic evidence, never ordinary G* input.
No fitting, live acquisition, PMX, business-outcome loading or source mutation.
"""
from collections import Counter
import csv
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

from .isolated_stochastic_fit import health_signal, write
from .live_validation_analysis import _health_signal

VERSION = 'historical-health-prefix-v1'
ADAPTER_VERSION = 'historical-health-census-adapter-v2'


def corrected_signal(row, replica, success_checks=None):
    """Remove only documented '* ' prefix; preserve every other old rule."""
    field = f'replica_{replica}_backend_check_status'
    value = str(row[field])
    if value.startswith('* '):
        row = dict(row)
        row[field] = value[2:]
    return (_health_signal(row, replica) if success_checks is None else
            health_signal(row, replica, success_checks))


def census(raw, checks=None):
    records = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    assert records
    statuses = Counter()
    transitions = Counter()
    changed = Counter()
    old_joint = Counter()
    new_joint = Counter()
    for row in records:
        before, after = [], []
        for replica in ('a', 'b'):
            old = (_health_signal(row, replica) if checks is None else
                   health_signal(row, replica, checks))
            new = corrected_signal(row, replica, checks)
            assert old[0] == new[0] and new[1] >= old[1]
            before.append(old)
            after.append(new)
            prefix = f'replica_{replica}_'
            statuses[(replica, row[prefix+'backend_status'], row[prefix+'backend_check_status'])] += 1
            changed[replica] += int(old != new)
        # Same order as historical HealthTick: H_a,H_b,P_a,P_b.
        old = (before[0][0], before[1][0], before[0][1], before[1][1])
        new = (after[0][0], after[1][0], after[0][1], after[1][1])
        transitions[(old, new)] += 1
        old_joint[old] += 1
        new_joint[new] += 1
    return dict(ticks=len(records), changed_ticks=sum(n for (a,b),n in transitions.items() if a != b),
                changed_replica_observations=dict(changed),
                old_joint=[dict(signals=k,count=v) for k,v in sorted(old_joint.items())],
                corrected_joint=[dict(signals=k,count=v) for k,v in sorted(new_joint.items())],
                transitions=[dict(before=a,after=b,count=n) for (a,b),n in sorted(transitions.items())],
                statuses=[dict(replica=r,backend=b,check=c,count=n) for (r,b,c),n in sorted(statuses.items())])


def api(path):
    return subprocess.check_output(['gh','api',f'repos/{os.environ["GITHUB_REPOSITORY"]}/'+path])


def restore(lock):
    item = json.loads(api(f'actions/artifacts/{lock["id"]}'))
    for key in ('id','name','size_in_bytes','digest'):
        assert item[key] == lock[key], key
    assert not item['expired']
    assert item['workflow_run']['id'] == lock['source_run']
    assert item['workflow_run']['head_sha'] == lock['source_head']
    data = api(f'actions/artifacts/{lock["id"]}/zip')
    assert len(data) == lock['size_in_bytes']
    assert 'sha256:'+sha256(data).hexdigest() == lock['digest']
    archive = zipfile.ZipFile(io.BytesIO(data))
    names = archive.namelist()
    assert len(names) == len(set(names))
    assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and '\\' not in n for n in names)
    assert archive.testzip() is None
    return archive, item


def validate_qualification(manifest, boundary, family):
    assert boundary['usable'] is True, 'source acquisition boundary is not usable'
    if family == 'Petclinic':
        assert manifest['usable'] is True, 'Petclinic learner is not usable'
    else:
        assert family == 'M7'
        assert 'usable' not in manifest or manifest['usable'] is True


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'historical archives only on GitHub Actions'
    config_path = Path('configs/health_prefix_audit_v2.json')
    config = json.loads(config_path.read_text())
    for lock in config['repository_locks']:
        assert sha256(Path(lock['path']).read_bytes()).hexdigest() == lock['sha256'], lock['path']
    out = Path('workflow-results/health-prefix-audit')
    records, metadata, members = [], [], []
    identities = set()
    for lock in config['artifacts']:
        archive, item = restore(lock)
        metadata.append(item)
        if lock['family'] == 'M7':
            manifests = sorted(n for n in archive.namelist() if
                               n.startswith('m8-preserved/qualified/') and n.endswith('/learner/manifest.json'))
            assert len(manifests) == 160, (len(manifests), archive.namelist()[:8])
        else:
            manifests = ['learner/manifest.json']
        for member in manifests:
            manifest = json.loads(archive.read(member))
            identity = {k:manifest[k] for k in ('profile','placement','failure_law','repetition')}
            identity_key = tuple(str(identity[k]) for k in identity)
            assert identity_key not in identities
            identities.add(identity_key)
            prefix = member[:-len('learner/manifest.json')]
            boundary = json.loads(archive.read(prefix+'audit/boundary.json'))
            validate_qualification(manifest, boundary, lock['family'])
            if lock['family'] == 'Petclinic':
                seal = json.loads(archive.read('seal.json'))
                for relative, digest in seal['files'].items():
                    assert sha256(archive.read(relative)).hexdigest() == digest
                deployment = json.loads(archive.read('learner/deployment.json'))
                checks = deployment['backend_success_check_statuses']
                assert checks == ['L7OK']
                periods = [('calibration','learner/health.csv')]
            else:
                checks = None
                periods = [('calibration','learner/health.csv'), ('test','evaluator/test-health.csv')]
            for period, relative in periods:
                path = prefix+relative
                raw = archive.read(path)
                digest = sha256(raw).hexdigest()
                members.append(dict(artifact_id=item['id'],member=path,bytes=len(raw),sha256=digest))
                record = dict(family=lock['family'], **identity, period=period,
                              source_artifact_id=item['id'], member=path, source_sha256=digest,
                              decoder=VERSION, **census(raw,checks))
                records.append(record)
        archive.close()
    assert len(identities) == 168 and len(records) == 328
    assert Counter(r['family'] for r in records) == {'M7':320,'Petclinic':8}
    expected = {(app,placement,law,str(rep)) for app in
                ('deathstarbench_social_network','opentelemetry_demo') for placement in
                ('colocated','split') for law in ('N','NC','ND','NCD') for rep in range(10)}
    expected |= {('spring_petclinic_microservices',p,l,'0') for p in ('colocated','split') for l in ('N','NC','ND','NCD')}
    assert identities == expected
    totals = []
    for family, period in sorted({(r['family'],r['period']) for r in records}):
        rows = [r for r in records if (r['family'],r['period']) == (family,period)]
        totals.append(dict(family=family,period=period,campaigns=len(rows),
                           ticks=sum(r['ticks'] for r in rows),
                           changed_ticks=sum(r['changed_ticks'] for r in rows),
                           affected_campaigns=sum(r['changed_ticks']>0 for r in rows),
                           changed_replica_observations=sum(sum(r['changed_replica_observations'].values()) for r in rows)))
    report = dict(version=VERSION, adapter_version=ADAPTER_VERSION, head_sha=os.environ['GITHUB_SHA'], run_id=os.environ['GITHUB_RUN_ID'],
                  config_sha256=sha256(config_path.read_bytes()).hexdigest(),
                  role='privileged historical diagnostic', main_campaigns=0, fits=0,
                  outcomes_loaded=0, pmx_reexecutions=0, source_mutations=0,
                  family_scope='160 M7 calibration/test; eight Petclinic calibration; not every historical auxiliary series',
                  decoder_change='remove documented prefix only; preserve legacy empty-status/runtime/network rules',
                  totals=totals, records=records)
    write(out/'audit.json',report)
    write(out/'source-artifacts.json',metadata)
    write(out/'source-members.json',members)
    print(json.dumps(totals))


if __name__ == '__main__':
    main()
