"""Reproduce primary bytes -> ordinary telemetry -> discovered graph -> event."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path

from telemetry_availability.v3_primary_projection import read,write,sha,PROBE_FIELDS
from telemetry_availability.v3_comparison_roles_v1 import ordinary_projection,digest
from telemetry_availability.pmx_observed_operations import read_native
from telemetry_availability.live_evidence import _pivot_health
from telemetry_availability.v3_prospective_execution_v1 import fit_operation as old_fit
from telemetry_availability.v4_execution_binding_v1 import fit_operation as revised_fit
from telemetry_availability.primary_verdict_audit_v1 import http_evidence
from telemetry_availability.live_pilot import OTEL_PRODUCT,OTEL_PERSON


def reproduce(source,out):
    seal=read(source/'seal.json')
    if seal['version']!='v4-single-primary-attempt-v1':raise ValueError('wrong primary capsule')
    if {p.name for p in source.iterdir() if p.is_file()}!=set(seal['files'])|{'seal.json'}:raise ValueError('capsule file census differs')
    for name,expected in seal['files'].items():
        if sha(source/name)!=expected:raise ValueError('primary capsule byte hash differs')
    request=read(source/'request.json');identity=read(source/'identity.json');spec=read(source/'spec.json')
    provenance=read(source/'provenance.json');native_source=read(source/'native-jaeger.json');health=read(source/'health.json')
    if (digest(request)!=provenance['request_canonical_sha256'] or
        digest(native_source['data'][0])!=provenance['native_trace_canonical_sha256'] or
        digest(health)!=provenance['health_records_canonical_sha256']):raise ValueError('primary object no longer matches original source pointer')
    grouped,parse=read_native(source/'native-jaeger.json',{request['trace_id']},'jaeger_json_v1')
    if parse['malformed_json_records'] or parse['invalid_traces']:raise ValueError('primary trace parser rejected capsule')
    native=dict(calibration_only=True,selected_trace_ids=[request['trace_id']],
        spans={tid:[asdict(s) for s in spans] for tid,spans in grouped.items()})
    probes,malformed=_pivot_health({},health,'calibration')
    ordinary,audit=ordinary_projection(read(source/'declarations.json'),[request],
        [{k:r[k] for k in PROBE_FIELDS} for r in probes],native,identity,['compose_post'],1)
    ordinary['manifest.json'].update(prospective_comparison=False,
        source_quality_selection='one historical illustrative counterexample; not a validation or estimation sample')
    old,old_report=old_fit(ordinary,'compose_post',spec,identity)
    revised,new_report,diagnostics=revised_fit(ordinary,'compose_post',spec,identity)
    independent=http_evidence(request,OTEL_PRODUCT,OTEL_PERSON['address'])
    result=dict(version=seal['version'],request_id=request['request_id'],trace_id=request['trace_id'],
        capsule_seal_sha256=sha(source/'seal.json'),native_spans=sum(map(len,native['spans'].values())),
        primary_probe_records=len(health),pivoted_probe_ticks=len(probes),malformed_probe_records=malformed,
        discovered_services=revised['graph']['services'],discovered_edges=revised['graph']['edges'],
        old_observation=dict(zip(old['signal_ids'],old['observation_categories'][0]['values'])),
        revised_observation=diagnostics[0],old_event=old_report['estimates']['execution'],
        revised_event=new_report['estimates']['execution'],independently_verified_external_outcome=independent,
        projection_audit=audit,one_attempt_not_population_probability=True,
        source_capsule=provenance['source'],execution_head=os.environ['GITHUB_SHA'],execution_run=os.environ['GITHUB_RUN_ID'])
    write(out,result)
    if (old_report['estimates']['execution']['prediction']!=0
        or new_report['estimates']['execution']['prediction']!=1 or independent['outcome'] is not True):
        raise ValueError('the fixed historical counterexample was not reproduced')
    print('Primary external success = true; original event = 0; revised event = 1. Single-record illustration only.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if os.environ.get('GITHUB_ACTIONS')!='true':raise ValueError('real primary-capsule processing is remote only')
    reproduce(args.input,args.out)


if __name__=='__main__':main()
