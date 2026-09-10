"""Prospective comparison role seals; no estimator or evaluator is run here.

Seals establish integrity and campaign association. Physical workflow job inputs,
not a hash alone, enforce separation of calibration and unopened test outcomes.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .v3_primary_projection import project, sha, write
from .v3_ordinary_identity_v2 import extend_identity, VERSION as ORDINARY_VERSION

VERSION = 'v3-comparison-roles-v1'
IDENTITY_FIELDS = {'application', 'placement', 'law', 'repetition', 'namespace', 'data_role', 'protocol_sha256'}
ROLE_FILES = {
    'pmx_calibration': {'native.json', 'requests.json', 'manifest.json'},
    'evaluator': {'requests.json', 'probes.json', 'manifest.json'},
    'graph_candidates': {'candidates.json', 'models.json', 'costs.json', 'read-audit.json'},
    'pmx_candidates': {'candidates.json', 'costs.json', 'read-audit.json'},
    'frozen_candidates': {'candidates.json', 'receipt.json', 'costs.json'},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_identity(identity):
    if set(identity) != IDENTITY_FIELDS:
        raise ValueError('campaign identity schema differs')
    if type(identity['repetition']) is not int or identity['repetition'] < 0:
        raise ValueError('invalid repetition')
    if identity['placement'] not in ('colocated', 'split') or identity['law'] not in ('N', 'NC', 'ND', 'NCD'):
        raise ValueError('unknown campaign condition')
    if identity['data_role'] not in ('development_preflight', 'prospective_main', 'artificial_control'):
        raise ValueError('unknown evidence role')
    for key in IDENTITY_FIELDS - {'repetition'}:
        if not isinstance(identity[key], str) or not identity[key]:
            raise ValueError('empty identity field')
    if len(identity['protocol_sha256']) != 64 or any(c not in '0123456789abcdef' for c in identity['protocol_sha256']):
        raise ValueError('invalid protocol digest')


def campaign_id(identity):
    validate_identity(identity)
    return '/'.join(str(identity[k]) for k in ('namespace', 'application', 'placement', 'law', 'repetition'))


def seal_role(root, role, identity, documents):
    validate_identity(identity)
    if role not in ROLE_FILES or set(documents) != ROLE_FILES[role]:
        raise ValueError('role member schema differs')
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError('role output must be new and empty')
    root.mkdir(parents=True, exist_ok=True)
    for name, document in documents.items():
        write(root/name, document)
    seal = dict(version=VERSION, role=role, identity=deepcopy(identity),
                files={name: sha(root/name) for name in sorted(documents)})
    write(root/'seal.json', seal)
    return seal


def load_role(root, role, identity=None, expected_seal_sha256=None):
    root = Path(root)
    files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if role not in ROLE_FILES or files != ROLE_FILES[role] | {'seal.json'} or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('unexpected/missing physical role member')
    if expected_seal_sha256 is not None and sha(root/'seal.json') != expected_seal_sha256:
        raise ValueError('role seal differs from frozen receipt')
    seal = json.loads((root/'seal.json').read_bytes())
    if set(seal) != {'version', 'role', 'identity', 'files'} or seal['version'] != VERSION or seal['role'] != role:
        raise ValueError('role seal schema differs')
    validate_identity(seal['identity'])
    if identity is not None and seal['identity'] != identity:
        raise ValueError('cross-campaign role substitution')
    if set(seal['files']) != ROLE_FILES[role]:
        raise ValueError('role hash census differs')
    documents = {}
    for name, expected in seal['files'].items():
        raw = (root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('role member hash differs: ' + name)
        documents[name] = json.loads(raw)
    return documents, seal


def ordinary_projection(deployment, requests, probes, native, identity, operations, expected_per_operation):
    """Trusted acquisition export; no post-test quality verdict may select rows."""
    validate_identity(identity)
    if (deployment['profile'], deployment['placement'], deployment['failure_law'], deployment['repetition']) != (
            identity['application'], identity['placement'], identity['law'], identity['repetition']):
        raise ValueError('deployment/campaign mismatch')
    calibration = [r for r in requests if r['period'] == 'calibration']
    if dict(Counter(r['operation'] for r in calibration)) != {op: expected_per_operation for op in operations}:
        raise ValueError('incomplete calibration census')
    raw, audit = project(deployment, calibration, probes, native)
    ordinary, identity_audit = extend_identity(raw, native)
    ordinary['manifest.json'].update(identity=deepcopy(identity), data_role=identity['data_role'],
        source_quality_selection='all planned calibration attempts; no test-derived selection',
        prospective_comparison=True)
    return ordinary, dict(projection=audit, identity=identity_audit,
        technical_projection_metadata_superseded_by=identity['data_role'])


def write_ordinary(root, documents):
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError('ordinary output must be new and empty')
    for name, value in documents.items():
        write(root/name, value)
    write(root/'seal.json', dict(version=ORDINARY_VERSION,
        files={name: sha(root/name) for name in sorted(documents)}))
    return sha(root/'seal.json')
