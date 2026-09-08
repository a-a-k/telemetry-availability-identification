"""Versioned ordinary host identity and observed demand census; no model fit."""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import argparse
import json
import os
from pathlib import Path
import sys
import time

from .b0_frequency_v3_csv_v2 import decode_outcome
from .health_prefix_audit_v3 import restore
from .pmx_observed_operations import read_native
from .v3_graph_input_inventory import ReadBoundary
from .v3_primary_projection import (FILES, RESOURCE_FIELDS, REQUEST_FIELDS, PROBE_FIELDS,
    DECLARATION_FIELDS, SPAN_FIELDS, ATTRIBUTE_PREFIXES, project, read, write, sha, verify_bundle)

VERSION = 'v3-ordinary-calibration-identity-2'
HOST_FIELDS = frozenset({'hostname', 'host.name'})
DS_ENTRIES = frozenset({'read_user_timeline_server', 'write_user_timeline_server'})
CONFIG = Path('configs/v3_ordinary_identity_v2.json')


def extend_identity(data, full_native=None):
    result = deepcopy(data)
    added = Counter()
    if full_native is not None:
        expected, _ = project(data['declarations.json'], data['requests.json'], data['probes.json'], full_native)
        if expected['native.json'] != data['native.json']:
            raise ValueError('full source does not exactly reproduce the original native projection')
        for trace, spans in result['native.json']['spans'].items():
            source = {s['span_id']: s for s in full_native['spans'][trace]}
            for span in spans:
                for key in HOST_FIELDS:
                    resource = source[span['span_id']]['resource_attributes']
                    if key in resource:
                        if not isinstance(resource[key], str) or not resource[key]:
                            raise ValueError('invalid native host identity')
                        span['resource_attributes'][key] = resource[key]
                        added[key] += 1
    result['manifest.json'].update(version=VERSION, identity_extension='preserve native hostname/host.name as explicit ordinary identity',
        identity_binding='exact declared replica service name or native study.replica; no inferred physical state')
    return result, dict(added_native_identity_counts=dict(added), full_original_native_projection_reproduced=full_native is not None,
        unchanged_objects=['requests.json', 'probes.json', 'declarations.json'], new_independent_campaigns=0,
        injected_state_values_added=0, native_span_kind_rewritten=False)


def replica_identity(span, declarations):
    if span['service'] != declarations['target_service']:
        raise ValueError('replica resolver is scoped to the declared target service')
    resources = span['resource_attributes']; replicas = declarations['replicas']
    candidates = set(); sources = []
    explicit = resources.get('study.replica')
    if explicit is not None:
        if explicit not in replicas:
            return dict(replica=None, reason='undeclared_explicit_replica', sources=[])
        candidates.add(explicit); sources.append('study.replica')
    for key in ('hostname', 'host.name', 'service.instance.id'):
        if key in resources:
            matches = [r for r, name in replicas.items() if resources[key] == name]
            if len(matches) > 1:
                return dict(replica=None, reason='nonunique_declared_name', sources=[])
            candidates.update(matches)
            if matches:
                sources.append(key)
    if len(candidates) != 1:
        return dict(replica=None, reason='conflicting_native_identity' if candidates else 'no_exact_native_binding', sources=sources)
    return dict(replica=next(iter(candidates)), reason=None, sources=sources)


def demand_census(requests, native, declarations, expected_calls):
    result = {}
    for operation, expected in expected_calls.items():
        rows = [r for r in requests if r['operation'] == operation]
        census = Counter(); patterns = Counter(); words = Counter(); bindings = Counter(); entry_kinds = Counter()
        for request in rows:
            spans = native['spans'].get(request['trace_id'], [])
            indexed = {s['span_id']: s for s in spans}; entries = []; unclassified = 0
            for span in spans:
                parent = indexed.get(span['parent_id'])
                if span['service'] != declarations['target_service'] or parent is None or parent['service'] == span['service']:
                    continue
                kind = 'native_server' if span['server'] else (
                    'source_declared_unlabelled_entry' if declarations['profile'] == 'deathstarbench_social_network'
                    and not span['native_kind'] and span['operation'] in DS_ENTRIES else None)
                if kind is None:
                    unclassified += 1; continue
                entry_kinds[kind] += 1; entries.append(span)
            entries.sort(key=lambda s: (s['start_us'], s['start_remainder_ns'], s['span_id']))
            identities = [replica_identity(s, declarations) for s in entries]
            labels = tuple(value['replica'] or '?' for value in identities)
            unknown = labels.count('?')
            complete = len(entries) == expected and unknown == 0 and not unclassified
            for value in identities:
                bindings.update(value['sources'] if value['replica'] is not None else [value['reason']])
            outcome = 'timeout' if decode_outcome(request['timed_out']) else (
                'success' if decode_outcome(request['semantic_success']) else 'other_failure')
            census.update(dict(attempts=1, native_missing=int(not spans), observed_entries=len(entries),
                unclassified_target_boundaries=unclassified, unresolved_entry_labels=unknown,
                exact_declared_entry_count=int(len(entries) == expected),
                observed_entries_and_identities_complete=int(complete)))
            patterns[(outcome, len(entries), unknown, ''.join(sorted(set(labels) - {'?'})) or '<none>', unclassified)] += 1
            words[(outcome, ','.join(labels) or '<none>')] += 1
        result[operation] = dict(declared_calls_for_complete_contract=expected, census=dict(census),
            entry_kinds=dict(entry_kinds), binding_evidence_counts=dict(bindings),
            footprint_census=[dict(outcome=k[0], observed_entries=k[1], unknown_labels=k[2], known_replicas=k[3],
                unclassified_target_boundaries=k[4], attempts=n) for k, n in sorted(patterns.items())],
            observed_route_words=[dict(outcome=k[0], word=k[1], attempts=n) for k, n in sorted(words.items())],
            word_order='native start timestamp with span-ID tie break; not proof of causal call order',
            observed_count_equality_does_not_prove_unobserved_call_absence=True,
            missing_calls_or_labels_imputed=False, forecast=None)
    return result


def load_bundle(root):
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != FILES | {'seal.json'} or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('ordinary identity role paths differ')
    seal = read(root/'seal.json')
    if seal['version'] != VERSION or set(seal['files']) != FILES:
        raise ValueError('ordinary identity seal schema mismatch')
    for name, digest in seal['files'].items():
        if sha(root/name) != digest:
            raise ValueError('ordinary identity digest mismatch')
    data = {name: read(root/name) for name in FILES}
    requests = data['requests.json']; native = data['native.json']
    if data['manifest.json']['version'] != VERSION or data['manifest.json']['external_attempts'] != len(requests):
        raise ValueError('ordinary identity manifest mismatch')
    if any(set(r) != set(REQUEST_FIELDS) or r['period'] != 'calibration' for r in requests):
        raise ValueError('ordinary request schema/role mismatch')
    if len({r['request_id'] for r in requests}) != len(requests) or len({r['trace_id'] for r in requests}) != len(requests):
        raise ValueError('duplicate external identity')
    if any(set(p) != set(PROBE_FIELDS) for p in data['probes.json']) or set(data['declarations.json']) != set(DECLARATION_FIELDS):
        raise ValueError('ordinary probe/declaration schema mismatch')
    if (set(native) != {'calibration_only', 'selected_trace_ids', 'spans'} or native['calibration_only'] is not True or
            set(native['selected_trace_ids']) != {r['trace_id'] for r in requests} or
            len(native['selected_trace_ids']) != len(requests) or not set(native['spans']) <= set(native['selected_trace_ids'])):
        raise ValueError('native role/census mismatch')
    for trace, spans in native['spans'].items():
        if len({s['span_id'] for s in spans}) != len(spans):
            raise ValueError('duplicate native span identity')
        for span in spans:
            if set(span) != set(SPAN_FIELDS) | {'attributes', 'resource_attributes'} or span['trace_id'] != trace:
                raise ValueError('native span schema/identity mismatch')
            if any(type(span[key]) is not bool for key in ('server', 'error_tag', 'error_status')):
                raise ValueError('invalid normalized span flags')
            if not set(span['resource_attributes']) <= RESOURCE_FIELDS | HOST_FIELDS:
                raise ValueError('undeclared native resource metadata')
            if any(k not in ('error', 'span.kind') and not k.startswith(ATTRIBUTE_PREFIXES) for k in span['attributes']):
                raise ValueError('undeclared native span attribute')
    return data, seal


def prepare(settings, profile):
    spec = settings['profiles'][profile]
    archive, ordinary_meta = restore(spec['artifact'])
    assert set(archive.namelist()) == FILES | {'seal.json'}
    root = Path('workflow-input/ordinary-v1'); root.mkdir(parents=True, exist_ok=True)
    for name in sorted(FILES | {'seal.json'}):
        (root/name).write_bytes(archive.read(name))
    archive.close(); old_seal = verify_bundle(root)
    data = {name: read(root/name) for name in FILES}
    full_native = None; native_meta = None
    if spec.get('native_source'):
        source = spec['native_source']; archive, native_meta = restore(source['artifact'])
        path = Path('workflow-input/native')/source['native_name']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(archive.read(source['native_name'])); archive.close()
        grouped, parse = read_native(path, {r['trace_id'] for r in data['requests.json']}, source['native_format'])
        assert not parse['malformed_json_records'] and not parse['invalid_traces']
        full_native = dict(calibration_only=True, selected_trace_ids=data['native.json']['selected_trace_ids'],
                           spans={k: [asdict(s) for s in v] for k, v in grouped.items()})
    extended, audit = extend_identity(data, full_native)
    out = Path('workflow-results/ordinary')
    for name, value in extended.items():
        write(out/name, value)
    for name in ('requests.json', 'probes.json', 'declarations.json'):
        assert sha(out/name) == old_seal['files'][name], name
    write(out/'seal.json', dict(version=VERSION, files={name: sha(out/name) for name in sorted(FILES)}))
    load_bundle(out)
    write(Path('workflow-results/preparation/source-audit.json'), dict(**audit, ordinary_artifact=ordinary_meta,
        native_source_artifact=native_meta, original_seal=old_seal, extended_seal=read(out/'seal.json'),
        run_id=os.environ['GITHUB_RUN_ID'], head=os.environ['GITHUB_SHA'], main_campaigns=0, model_fits=0))


def inspect(settings, profile):
    root = Path('workflow-input/ordinary').resolve(); out = Path('workflow-results/inspection').resolve()
    out.mkdir(parents=True, exist_ok=True); boundary = ReadBoundary(root, out)
    started = time.perf_counter(); sys.addaudithook(boundary.hook)
    try:
        data, seal = load_bundle(root)
        assert data['declarations.json']['profile'] == profile
        assert {r['operation'] for r in data['requests.json']} == set(settings['profiles'][profile]['declared_calls'])
        report = demand_census(data['requests.json'], data['native.json'], data['declarations.json'],
                               settings['profiles'][profile]['declared_calls'])
        assert all(r['census']['attempts'] == settings['profiles'][profile]['expected_attempts_per_operation'] for r in report.values())
        assert sum(r['census']['attempts'] for r in report.values()) == len(data['requests.json'])
        assert not boundary.blocked and boundary.reads == {str(p) for p in boundary.allowed}
    finally:
        boundary.active = False
        write(out/'consumer-read-audit.json', dict(actual_data_reads=sorted(boundary.reads), blocked=boundary.blocked,
            separate_job_from_raw_preparation=True, ordinary_files_only=True))
    write(out/'demand-census.json', dict(version=VERSION, operations=report, input_seal=seal,
        profile=profile, run_id=os.environ['GITHUB_RUN_ID'], head=os.environ['GITHUB_SHA'],
        protocol_sha256=sha(CONFIG), elapsed_seconds=time.perf_counter()-started, main_campaigns=0,
        model_fits=0, application_adequacy_qualified=False))


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Full application work is remote only'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'inspect')); parser.add_argument('--profile', required=True)
    args = parser.parse_args(); settings = read(CONFIG)
    for lock in settings['repository_locks']:
        assert sha(Path(lock['path'])) == lock['sha256'], lock['path']
    (prepare if args.stage == 'prepare' else inspect)(settings, args.profile)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        stage = 'inspection' if len(sys.argv) > 1 and sys.argv[1] == 'inspect' else 'preparation'
        write(Path('workflow-results')/stage/'failure.json', dict(type=type(exc).__name__, message=str(exc)))
        raise
