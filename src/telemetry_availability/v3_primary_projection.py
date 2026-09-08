"""Versioned ordinary-observation export; source preparation is not estimation.

Only artificial dictionaries may be processed locally. Application CLI is GHA-only.
The downstream inspector receives only this physical role, not the legacy learner.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import json
import os
from pathlib import Path

VERSION='v3-ordinary-calibration-1'
REQUEST_FIELDS=('request_id','trace_id','operation','period','started_at','completed_at','semantic_success','timed_out')
PROBE_FIELDS=('observed_at','elapsed_seconds','replica_a_backend_status','replica_a_backend_check_status',
              'replica_b_backend_status','replica_b_backend_check_status')
DECLARATION_FIELDS=('profile','placement','failure_law','repetition','target_service','replicas','placements',
    'known_non_target_dependencies','source_declared_dependencies','dependency_provenance',
    'backend_success_check_statuses','replica_health_check','database_shared')
SPAN_FIELDS=('trace_id','span_id','parent_id','service','operation','server','start_us','duration_us',
    'start_remainder_ns','duration_remainder_ns','error_tag','error_status','native_kind','native_links')
ATTRIBUTE_PREFIXES=('http.','url.','server.','network.','net.','peer.','rpc.','db.','error.',
    'exception.','messaging.','code.','thread.')
RESOURCE_FIELDS=frozenset({'service.name','service.namespace','service.instance.id','service.version',
    'study.replica','study.domain','telemetry.sdk.name','telemetry.sdk.version','telemetry.sdk.language'})
FILES=frozenset({'requests.json','probes.json','native.json','declarations.json','manifest.json'})


def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def project(deployment, requests, health, native):
    """Whitelist projection; inspector states never influence exported values."""
    if any(row['period'] not in ('baseline','calibration') for row in requests):
        raise ValueError('unexpected request period in source role')
    calibration=[{key:row[key] for key in REQUEST_FIELDS} for row in requests if row['period']=='calibration']
    if not calibration or len({row['request_id'] for row in calibration})!=len(calibration):
        raise ValueError('missing/duplicate external attempts')
    selected={row['trace_id'] for row in calibration}
    if len(selected)!=len(calibration) or native['calibration_only'] is not True:
        raise ValueError('trace/attempt identity or native role mismatch')
    if set(native['selected_trace_ids'])!=selected or not set(native['spans'])<=selected:
        raise ValueError('native IDs differ from calibration census')
    probes=[]
    for row in health:
        if row.get('period','calibration')!='calibration': raise ValueError('unexpected probe period')
        probes.append({key:row[key] for key in PROBE_FIELDS})
    if len({row['observed_at'] for row in probes})!=len(probes): raise ValueError('duplicate probe timestamp')
    spans={};dropped_attributes=Counter();dropped_resources=Counter()
    for trace_id,items in native['spans'].items():
        projected=[];ids=set()
        for span in items:
            if span['trace_id']!=trace_id or span['span_id'] in ids: raise ValueError('native span identity mismatch')
            ids.add(span['span_id'])
            row={key:deepcopy(span[key]) for key in SPAN_FIELDS}
            # Preserve link identities, not arbitrary linked metadata or latent state tags.
            row['native_links']=[{k:deepcopy(v) for k,v in link.items()
                if k in ('traceId','spanId','traceState','flags','trace_id','span_id','trace_state')}
                for link in span['native_links']]
            row['attributes']={k:deepcopy(v) for k,v in span['attributes'].items()
                               if k in ('error','span.kind') or k.startswith(ATTRIBUTE_PREFIXES)}
            row['resource_attributes']={k:deepcopy(v) for k,v in span['resource_attributes'].items() if k in RESOURCE_FIELDS}
            dropped_attributes.update(set(span['attributes'])-set(row['attributes']))
            dropped_resources.update(set(span['resource_attributes'])-set(row['resource_attributes']))
            projected.append(row)
        spans[trace_id]=projected
    declarations={key:deepcopy(deployment[key]) for key in DECLARATION_FIELDS}
    manifest=dict(version=VERSION,role='ordinary_calibration',data_role='development_technical',
        profile=declarations['profile'],placement=declarations['placement'],failure_law=declarations['failure_law'],
        repetition=declarations['repetition'],external_attempts=len(calibration),probe_ticks=len(probes),
        operations=dict(sorted(Counter(row['operation'] for row in calibration).items())),
        native_instrumentation='otel-native-calibration with explicit attribute whitelist',
        probe_observation_law='raw HAProxy status/last-check; stateful and possibly delayed; not direct primitive MCAR',
        probe_mask_limitation='legacy collector jointly queried Docker inspection and HAProxy; missingness not assumed independent',
        source_quality_selection='previously acquired development data; no post-test usability fields exported',
        baseline_attempts=0,test_attempts=0,docker_state_fields=0,injection_schedule_fields=0,
        inferred_graph_files=0,estimated_model_files=0)
    data={'requests.json':calibration,'probes.json':probes,
          'native.json':dict(calibration_only=True,selected_trace_ids=sorted(selected),spans=spans),
          'declarations.json':declarations,'manifest.json':manifest}
    audit=dict(version=VERSION,retained_requests=len(calibration),retained_probe_ticks=len(probes),
        discarded_span_attribute_keys=dict(sorted(dropped_attributes.items())),
        discarded_resource_attribute_keys=dict(sorted(dropped_resources.items())),
        retained_request_fields=list(REQUEST_FIELDS),retained_probe_fields=list(PROBE_FIELDS),
        retained_declaration_fields=list(DECLARATION_FIELDS),
        estimator_fits=0,main_campaigns=0,source_preparation_can_read_legacy_privileged_fields=True,
        downstream_primary_receives_legacy_bundle=False)
    return data,audit


def verify_bundle(root):
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if any(p.is_symlink() for p in root.rglob('*')) or actual!=FILES|{'seal.json'}:
        raise ValueError('ordinary input role has unexpected/missing paths')
    seal=read(root/'seal.json')
    if set(seal['files'])!=FILES or seal['version']!=VERSION: raise ValueError('ordinary role seal mismatch')
    for name,digest in seal['files'].items():
        if sha(root/name)!=digest: raise ValueError('ordinary role digest mismatch: '+name)
    return seal


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','Application projection is remote-only'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audit',type=Path,required=True)
    args=parser.parse_args()
    # Integrity/source-role validation runs as a trusted preparation job, not as a fit.
    from .isolated_stochastic_fit import verify_learner_bundle
    source_seal=verify_learner_bundle(args.source)
    def csv_rows(path):
        with path.open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))
    data,audit=project(read(args.source/'learner/deployment.json'),csv_rows(args.source/'learner/requests.csv'),
        csv_rows(args.source/'learner/health.csv'),read(args.source/'native/calibration-native.json'))
    for name,value in data.items(): write(args.output/name,value)
    write(args.output/'seal.json',dict(version=VERSION,files={name:sha(args.output/name) for name in sorted(FILES)}))
    verify_bundle(args.output)
    audit.update(source_seal=source_seal,source_run=source_seal['metadata']['source_run'],
        source_head=source_seal['metadata']['study_head'],projection_head=os.environ['GITHUB_SHA'],
        output_seal=read(args.output/'seal.json'))
    write(args.audit,audit)
    print(json.dumps(dict(version=VERSION,attempts=len(data['requests.json']),probes=len(data['probes.json']),fits=0)))


if __name__=='__main__': main()
