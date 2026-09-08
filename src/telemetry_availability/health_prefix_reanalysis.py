"""Isolated historical refit of the HAProxy prefix correction; no new acquisition."""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from hashlib import sha256
import io
import csv
import json
import math
import os
from pathlib import Path
import sys
import time

from .health_prefix_audit_v3 import restore, corrected_signal, validate_qualification
from .isolated_stochastic_fit import (read, rows, write, digest, load_analysis, ReadAudit,
                                     health_signal, HealthTick, QualifiedCell, RequestRecord)
from .live_validation_analysis import (_bool, _timestamp, _health_signal, prepare_mode,
    fit_exact_model, predict_cell)
from .live_validation_config import load_frozen_live_validation_config

CONFIG=Path('configs/health_prefix_reanalysis.json')
FIELDS=('learner/requests.csv','learner/health.csv','learner/deployment.json',
        'learner/manifest.json','learner/topology-edges.csv','audit/boundary.json')
KEY=('profile','failure_law','repetition','mode','scope','source_placement',
     'target_placement','method','operation')
PROFILES=('deathstarbench_social_network','opentelemetry_demo','spring_petclinic_microservices')


def validate():
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'historical full refits run only remotely'
    config=read(CONFIG)
    for item in config['repository_locks']:
        assert digest(Path(item['path']))==item['sha256'], item['path']
    return config


def identity(manifest):
    result={k:manifest[k] for k in ('profile','placement','failure_law','repetition')}
    result['repetition']=int(result['repetition'])
    return result


def cell_id(meta):
    return f"{meta['profile']}/{meta['placement']}/{meta['failure_law']}/r{meta['repetition']}"


def prepare(config):
    audits=[]; counts=Counter()
    for lock in config['source_artifacts']:
        archive,metadata=restore(lock)
        audits.append(metadata)
        manifests=([n for n in archive.namelist() if n.startswith('m8-preserved/qualified/')
                    and n.endswith('/learner/manifest.json')] if lock['family']=='M7' else ['learner/manifest.json'])
        assert len(manifests)==(160 if lock['family']=='M7' else 1)
        for member in manifests:
            prefix=member[:-len('learner/manifest.json')]
            manifest=json.loads(archive.read(member))
            boundary=json.loads(archive.read(prefix+'audit/boundary.json'))
            validate_qualification(manifest,boundary,lock['family'])
            meta=identity(manifest)
            dest=Path('workflow-results/learners')/cell_id(meta)
            assert not dest.exists()
            files={}
            for name in FIELDS:
                value=archive.read(prefix+name)
                target=dest/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(value);files[name]=sha256(value).hexdigest()
            write(dest/'seal.json',dict(files=files,metadata=dict(**meta,family=lock['family'],
                  source_artifact_id=lock['id'],source_archive_digest=lock['digest'])))
            counts[meta['profile']]+=1
        archive.close()
    assert counts==dict(zip(PROFILES,(80,80,8)))
    m7=asdict(load_frozen_live_validation_config('configs/m7_frozen_live.yaml').analysis)
    for profile in PROFILES:
        analysis=(read(Path('configs/isolated_stochastic_analysis.json')) if profile==PROFILES[2] else m7)
        write(Path('workflow-results/learners')/profile/'analysis.json',analysis)
    write(Path('workflow-results/preparation/source-artifacts.json'),audits)
    write(Path('workflow-results/preparation/preparation.json'),dict(campaigns=dict(counts),
          output_files_per_cell=7,evaluator_members_parsed=0,native_members_parsed=0,
          downloaded_role='trusted historical archive projection',data_role='privileged historical diagnostic'))


def load_learner(root):
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    assert actual==set(FIELDS)|{'seal.json'}
    seal=read(root/'seal.json')
    assert set(seal['files'])==set(FIELDS)
    for name,value in seal['files'].items(): assert digest(root/name)==value,name
    manifest=read(root/'learner/manifest.json');boundary=read(root/'audit/boundary.json')
    deployment=read(root/'learner/deployment.json')
    family=seal['metadata']['family'];validate_qualification(manifest,boundary,family)
    requests=[]
    for row in rows(root/'learner/requests.csv'):
        assert row['period'] in ('baseline','calibration')
        requests.append(RequestRecord(period=row['period'],request_id=row['request_id'],operation=row['operation'],
             at=_timestamp(row['started_at']),success=int(_bool(row['semantic_success'])),
             trace_present=_bool(row['trace_present']),span_count=int(row['span_count']),
             services=frozenset(filter(None,row['services'].split(';'))),
             target_replicas=frozenset(filter(None,row['target_replicas'].split(';')))))
    checks=deployment['backend_success_check_statuses'] if family=='Petclinic' else None
    if family=='Petclinic': assert checks==['L7OK']
    old_ticks=[];new_ticks=[]
    for row in rows(root/'learner/health.csv'):
        assert row.get('period','calibration')=='calibration'
        old=[_health_signal(row,r) if checks is None else health_signal(row,r,checks) for r in ('a','b')]
        new=[corrected_signal(row,r,checks) for r in ('a','b')]
        args=dict(at=_timestamp(row['observed_at']),elapsed_seconds=float(row['elapsed_seconds']))
        old_ticks.append(HealthTick(**args,signals=(old[0][0],old[1][0],old[0][1],old[1][1])))
        new_ticks.append(HealthTick(**args,signals=(new[0][0],new[1][0],new[0][1],new[1][1])))
    cell=QualifiedCell(**identity(manifest),target_service=deployment['target_service'],
            learner_requests=tuple(requests),health=tuple(sorted(old_ticks,key=lambda t:t.at)),
            test_requests=(),test_health=(),boundary=boundary,directory=root)
    return cell,replace(cell,health=tuple(sorted(new_ticks,key=lambda t:t.at))),seal


def fit_one(root,settings):
    started=time.perf_counter(); audit=ReadAudit(root,settings,Path('workflow-results/candidates').resolve())
    sys.addaudithook(audit)
    try:
        analysis=load_analysis(settings)
        old,new,seal=load_learner(root)
        versions={};diagnostics=[]
        changed=sum(a!=b for a,b in zip(old.health,new.health))
        assert len(old.health)==len(new.health)
        for version,cell in (('legacy',old),('prefix_corrected',new)):
            if version=='prefix_corrected' and changed==0:
                versions[version]=versions['legacy']
                continue
            predictions=[]
            for mode in analysis.modes:
                tick=time.perf_counter()
                prepared=prepare_mode(cell,mode,analysis)
                estimate=fit_exact_model(cell,prepared,analysis)
                for scope in ['current']+(['transfer'] if cell.placement==analysis.source_placement else []):
                    predictions.extend(predict_cell(cell,prepared,estimate,analysis,scope))
                diagnostics.append(dict(version=version,mode=mode.id,seconds=time.perf_counter()-tick,
                    status=estimate.status,rank=estimate.rank,dimension=estimate.dimension,
                    retained_traces=prepared.retained_traces,guarded_calibration=prepared.guarded_calibration,
                    unaligned_calibration=prepared.unaligned_calibration,
                    health_contradictions=prepared.health_signal_contradictions))
            versions[version]=predictions
        assert not old.test_requests and not new.test_health
    finally:
        audit.active=False
    return dict(identity=identity(seal['metadata']),source_seal=seal,changed_health_ticks=changed,
        unchanged_corrected_reused_legacy=(changed==0),versions=versions,diagnostics=diagnostics,
        seconds=time.perf_counter()-started,read_audit=dict(read_paths=sorted(audit.read_paths),
        blocked=audit.blocked,evaluator_reads=0,injection_schedule_reads=0,target_calibration_reads=0))


def build(profile):
    root=Path('workflow-input/learners').resolve()
    settings=root/'analysis.json'
    manifests=sorted(root.rglob('learner/manifest.json'))
    assert len(manifests)==(8 if profile==PROFILES[2] else 80)
    out=Path('workflow-results/candidates');out.mkdir(parents=True,exist_ok=True)
    records=[]
    for manifest in manifests:
        record=fit_one(manifest.parents[1],settings)
        assert record['identity']['profile']==profile
        assert record['read_audit']['blocked']==[]
        record_path=out/f"{record['identity']['placement']}-{record['identity']['failure_law']}-r{record['identity']['repetition']}.json"
        write(record_path,record)
        records.append(dict(identity=record['identity'],path=record_path.name,sha256=digest(record_path),
                            changed_health_ticks=record['changed_health_ticks']))
        print(json.dumps(records[-1]),flush=True)
    write(out/'seal.json',dict(profile=profile,head=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],
         records=records,settings_sha256=digest(settings),data_role='historical_development_refit',
         main_campaigns=0,evaluator_loaded=False))


def pkey(row):
    return tuple(str(row[k]) for k in KEY)


def finite(value):
    return value not in ('',None) and math.isfinite(float(value))


def evaluate(config):
    """Historical parity only, after every candidate has been sealed."""
    candidates={};seals=[]
    for sealpath in Path('workflow-input/candidates').rglob('seal.json'):
        seal=read(sealpath);seals.append(seal)
        for item in seal['records']:
            path=sealpath.parent/item['path'];assert digest(path)==item['sha256']
            record=read(path)
            for row in record['versions']['legacy']:
                key=pkey(row);assert key not in candidates
                candidates[key]=(row,next(n for n in record['versions']['prefix_corrected'] if pkey(n)==key))
    assert len(seals)==3 and len(candidates)==17280+576
    historical=[]
    archive,metadata=restore(config['source_artifacts'][0])
    names=[n for n in archive.namelist() if n.startswith('m8-preserved/analysis/') and n.endswith('predictions.csv')]
    assert len(names)==1,names
    raw=archive.read(names[0]);historical.extend(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    archive.close()
    for item in config['petclinic_historical_predictions']:
        path=Path(item['path']);assert digest(path)==item['sha256']
        historical.extend(read(path)['predictions'])
    assert len(historical)==len(candidates) and len({pkey(r) for r in historical})==len(historical)
    results=[];mismatches=[]
    for previous in historical:
        key=pkey(previous);old,new=candidates[key]
        equivalent=finite(previous['prediction'])==finite(old['prediction']) and previous['status']==old['status']
        error=abs(float(previous['prediction'])-float(old['prediction'])) if finite(previous['prediction']) and finite(old['prediction']) else None
        equivalent=equivalent and (error is None or error<=config['legacy_probability_tolerance'])
        if not equivalent:mismatches.append(dict(identity=dict(zip(KEY,key)),historical=previous,rerun=old))
        results.append(dict(identity=dict(zip(KEY,key)),historical_prediction=previous['prediction'],
             legacy_prediction=old['prediction'],corrected_prediction=new['prediction'],legacy_status=old['status'],
             corrected_status=new['status'],legacy_reproduction_error=error,
             delta=(float(new['prediction'])-float(old['prediction'])) if finite(old['prediction']) and finite(new['prediction']) else None))
    out=Path('workflow-results/comparison')
    write(out/'paired-predictions.json',results)
    write(out/'parity-mismatches.json',mismatches)
    write(out/'qualification.json',dict(qualified=not mismatches,paired_slots=len(results),legacy_mismatches=len(mismatches),
         probability_tolerance=config['legacy_probability_tolerance'],main_campaigns=0,
         changed_probability_slots=sum(r['delta'] is not None and abs(r['delta'])>1e-12 for r in results),
         changed_status_slots=sum(r['legacy_status']!=r['corrected_status'] for r in results),
         independent_campaigns_added=0,accuracy_scoring_performed=False,
         next_required_stage='rescore complete M7 all-sequence/stable census after candidate parity; Petclinic accuracy remains separate',
         source_seals=seals,historical_m7_artifact=metadata))
    assert not mismatches, f'{len(mismatches)} historical reproduction mismatches; no correction attribution qualified'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=('prepare','build','evaluate'))
    parser.add_argument('--profile',choices=PROFILES)
    args=parser.parse_args();config=validate()
    if args.stage=='prepare':prepare(config)
    elif args.stage=='build':build(args.profile)
    else:evaluate(config)


if __name__=='__main__':
    main()
