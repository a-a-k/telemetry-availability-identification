"""Post-seal historical M7 rescore separating prediction and window changes."""
from collections import defaultdict
from dataclasses import replace
from hashlib import sha256
import csv
import io
import json
import os
from pathlib import Path

from .health_prefix_audit_v3 import restore, corrected_signal
from .health_prefix_reanalysis import pkey, PROFILES, identity, finite
from .health_prefix_dependency_qualification import qualify
from .isolated_stochastic_fit import read, write, digest
from .live_validation_config import load_frozen_live_validation_config
from .live_validation_analysis import (QualifiedCell, HealthTick, EvaluationRequest,
    _bool, _timestamp, _health_signal, score_predictions, _cell_metric_rows,
    _contrast_rows, _apply_holm, _summary_rows)
from .m7_complete_census import (rows, write_csv, census_rows, extract_observations,
    aggregate_operation, paired_rows, key)


def csv_bytes(value):
    return list(csv.DictReader(io.StringIO(value.decode('utf-8-sig'))))


def decode_evaluator(meta,request_rows,health_rows):
    requests=tuple(EvaluationRequest(operation=r['operation'],at=_timestamp(r['started_at']),
                   success=int(_bool(r['semantic_success']))) for r in request_rows)
    old_ticks=[];new_ticks=[]
    for row in health_rows:
        args=dict(at=_timestamp(row['observed_at']),elapsed_seconds=float(row['elapsed_seconds']))
        for values,decoder in ((old_ticks,_health_signal),(new_ticks,corrected_signal)):
            a,b=decoder(row,'a'),decoder(row,'b')
            values.append(HealthTick(**args,signals=(a[0],b[0],a[1],b[1])))
    cell=QualifiedCell(**meta,target_service='unused-by-evaluator',learner_requests=(),health=(),
         test_requests=requests,test_health=tuple(sorted(old_ticks,key=lambda t:t.at)),
         boundary={},directory=Path('evaluator-only'))
    return cell,replace(cell,test_health=tuple(sorted(new_ticks,key=lambda t:t.at)))


def evaluator_cells(archive):
    result={}
    manifests=sorted(n for n in archive.namelist() if n.startswith('m8-preserved/qualified/')
                     and n.endswith('/learner/manifest.json'))
    assert len(manifests)==160
    for member in manifests:
        prefix=member[:-len('learner/manifest.json')]
        meta=identity(json.loads(archive.read(member)))
        cell,corrected=decode_evaluator(meta,
            csv_bytes(archive.read(prefix+'evaluator/test-requests.csv')),
            csv_bytes(archive.read(prefix+'evaluator/test-health.csv')))
        cid=(cell.profile,cell.placement,cell.failure_law,cell.repetition)
        assert cid not in result
        result[cid]=(cell,corrected)
    assert sum(len(v[0].test_requests) for v in result.values())==576000
    return result


def summaries(census,draws,seed):
    grouped=defaultdict(list)
    fields=('profile','scope','mode','view','method','operation')
    for row in census:grouped[key(row,fields)].append(row)
    operation=[aggregate_operation(v,dict(zip(fields,k)),draws,seed) for k,v in sorted(grouped.items())]
    grouped.clear();fields+=('source_placement','target_placement','failure_law')
    for row in census:grouped[key(row,fields)].append(row)
    condition=[aggregate_operation(v,dict(zip(fields,k)),draws,seed) for k,v in sorted(grouped.items())]
    common,paired=paired_rows(census,draws,seed)
    return dict(operation_summary=operation,condition_summary=condition,common_cells=common,paired_summary=paired)


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    config=read(Path('configs/health_prefix_rescore.json'))
    for item in config['repository_locks']:assert digest(Path(item['path']))==item['sha256'],item['path']
    for lock in config['refit_artifacts']:
        archive,_=restore(lock)
        dest=Path('workflow-input')/lock['role'];dest.mkdir(parents=True,exist_ok=True)
        archive.extractall(dest);archive.close()
    strict_qualification=read(Path('workflow-input/comparison/qualification.json'))
    assert strict_qualification['paired_slots']==17856
    corrected=[];candidate_seals=[]
    for path in Path('workflow-input/candidates').rglob('seal.json'):
        seal=read(path);candidate_seals.append(seal)
        assert seal['head']==config['refit_head'] and str(seal['run'])==str(config['refit_run'])
        if seal['profile']==PROFILES[2]:continue
        for item in seal['records']:
            member=path.parent/item['path'];assert digest(member)==item['sha256']
            corrected.extend(read(member)['versions']['prefix_corrected'])
    assert len(candidate_seals)==3 and len(corrected)==17280
    source,metadata=restore(config['source_m7_artifact'])
    names=[n for n in source.namelist() if n.startswith('m8-preserved/analysis/') and n.endswith('predictions.csv')]
    assert len(names)==1
    original=csv_bytes(source.read(names[0]));assert len(original)==17280
    historical=list(original)
    for item in config['petclinic_historical_predictions']:
        path=Path(item['path']);assert digest(path)==item['sha256']
        historical.extend(read(path)['predictions'])
    audit=read(Path(config['prefix_census_path']))
    accepted,qualification=qualify(Path('workflow-input/candidates'),historical,audit,
                                 config['legacy_probability_tolerance'])
    assert len(qualification['retained_strict_replay_mismatches'])==strict_qualification['legacy_mismatches']
    assert qualification['qualified_for_decoder_correction']
    corrected=[row for row in accepted if row['profile'] in PROFILES[:2]]
    assert len(corrected)==17280
    output=Path('workflow-results/rescore');output.mkdir(parents=True,exist_ok=True)
    compact=Path('workflow-results/compact');compact.mkdir(parents=True,exist_ok=True)
    write(output/'accepted-predictions.json',accepted)
    write(output/'dependency-decisions.json',qualification.pop('decisions'))
    write(compact/'dependency-qualification.json',qualification)
    # Outcome access starts after the separate dependency qualification above.
    cells=evaluator_cells(source)
    names=[n for n in source.namelist() if n.startswith('m8-preserved/analysis/') and n.endswith('scores.csv')]
    assert len(names)==1
    historical_scores=csv_bytes(source.read(names[0]))
    source.close()
    assert {pkey(r) for r in original}=={pkey(r) for r in corrected}
    analysis=load_frozen_live_validation_config('configs/m7_frozen_live.yaml')
    old_observations=extract_observations(historical_scores)
    records=[];historical_score_max_error=None
    for prediction_version,predictions in (('historical',original),('prefix_corrected',corrected)):
        by_target=defaultdict(list)
        for row in predictions:
            cid=(row['profile'],row['target_placement'],row['failure_law'],int(row['repetition']))
            by_target[cid].append(row)
        for window_version,index in (('historical',0),('prefix_corrected',1)):
            role=prediction_version+'-predictions__'+window_version+'-windows'
            out=output/role;out.mkdir()
            scores=[]
            for cid,preds in sorted(by_target.items()):scores.extend(score_predictions(preds,cells[cid][index],analysis.analysis))
            if prediction_version==window_version=='historical':
                previous={(pkey(r),r['view']):r for r in historical_scores}
                assert len(previous)==len(historical_scores)==len(scores)
                assert {(pkey(r),r['view']) for r in scores}==set(previous)
                differences=[]
                for row in scores:
                    reference=previous[(pkey(row),row['view'])]
                    for name in ('test_requests','test_successes'):assert int(reference[name])==row[name]
                    for name in ('prediction','brier_score','signed_prediction_error','absolute_prediction_error',
                                 'test_block_mean_lower','test_block_mean_upper'):
                        differences.append(abs(float(reference[name])-float(row[name])))
                historical_score_max_error=max(differences)
                assert historical_score_max_error<=1e-12
            observations=extract_observations(scores)
            assert len(observations)==len(old_observations)
            for k,(n,s) in observations.items():
                if k[-1]=='all_sequence' or window_version=='historical':
                    assert (n,s)==old_observations[k],k
            census=census_rows(predictions,observations)
            assert len(census)==34560
            stats=summaries(census,config['bootstrap_repetitions'],config['bootstrap_seed'])
            for name,values in stats.items():write_csv(out/(name.replace('_','-')+'.csv'),values)
            write_csv(out/'census.csv',census);write_csv(out/'scores.csv',scores)
            cell_metrics=_cell_metric_rows(scores,{p:3 for p in PROFILES[:2]})
            contrasts=_contrast_rows(cell_metrics,analysis,'current')
            contrasts.extend(_contrast_rows(cell_metrics,analysis,'transfer'));_apply_holm(contrasts)
            write_csv(out/'historical-contrasts.csv',contrasts)
            write_csv(out/'historical-summary.csv',_summary_rows(cell_metrics))
            all_summary=[r for r in stats['operation_summary'] if r['scope']=='current' and r['mode']=='full'
                         and r['view']=='all_sequence' and r['method'] in ('proposed','B2','B0')]
            primary=[r for r in contrasts if r['scope']=='current' and r['mode']=='full']
            records.append(dict(prediction_version=prediction_version,window_version=window_version,
                 census_slots=len(census),scored_rows=len(scores),
                 current_all_sequence_requests=sum(n for k,(n,s) in observations.items() if k[-1]=='all_sequence'),
                 current_stable_requests=sum(n for k,(n,s) in observations.items() if k[-1]=='stable'),
                 all_sequence_operation_summary=all_summary,full_current_contrasts=primary))
            print(json.dumps({k:v for k,v in records[-1].items() if k not in ('all_sequence_operation_summary','full_current_contrasts')}),flush=True)
    files={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in output.rglob('*') if p.is_file()}
    write(compact/'rescore.json',dict(qualified=True,head=os.environ['GITHUB_SHA'],run=os.environ['GITHUB_RUN_ID'],
        refit_head=config['refit_head'],refit_run=config['refit_run'],data_role='opened historical M7 correction',
        main_campaigns=0,new_independent_campaigns=0,records=records,files=files,
        historical_score_max_error=historical_score_max_error,
        source_archive=metadata,reference_prediction_version='exact preserved historical table after refit parity',
        statistical_scope='unchanged historical contrasts plus descriptive 95% campaign bootstrap; not six v3 main contrasts',
        dependency_qualification=qualification,
        remaining='M9X PMX paired-side update and auxiliary-series dependency audit; new graph-method adequacy remains open'))


if __name__=='__main__':main()
