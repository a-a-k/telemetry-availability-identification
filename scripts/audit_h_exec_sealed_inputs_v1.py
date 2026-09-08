"""Audit/replay every H-EXEC cell from immutable final uploaded inputs, remotely."""
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from telemetry_availability.health_prefix_audit_v3 import restore
from telemetry_availability.h_exec_compact_v2 import summarize
from telemetry_availability.h_exec_sealed_analysis_replay_v1 import collect

CONFIG=Path('configs/h_exec_sealed_input_audit_v1.json')
OUT=Path('workflow-results/h-exec-sealed-compact')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','Native payload audit is remote only'
    started=time.perf_counter();config=json.loads(CONFIG.read_bytes())
    for lock in config['repository_locks']:
        assert sha256(Path(lock['path']).read_bytes()).hexdigest()==lock['sha256'],lock['path']
    frozen=json.loads(Path('configs/h_exec_01_v2.json').read_bytes())
    audits=[];census_differences=Counter()
    needed={'identity.json','acquisition-summary.json','requests.csv','health.csv','sentinel-requests.csv',
        'static-controls.json','boundaries.json','raw-telemetry.log','proxy-routes.log','repair-admin-stats.csv',
        'interventions.json','periods.json','instrumentation-audit.json'}
    reports=Path('workflow-results/recomputed-cells')
    for cell in config['cells']:
        label=f"b{cell['block']}-s{cell['slot']}"
        source=Path('workflow-input/h-exec-sealed')/label;source.mkdir(parents=True,exist_ok=True)
        raw,raw_meta=restore(cell['raw'])
        original,compact_meta=restore(cell['compact'])
        prior=json.loads(original.read('summary.json'))
        prior_census=json.loads(original.read('census.json'))
        before={}
        for name in sorted(needed & set(raw.namelist())):
            value=raw.read(name);(source/name).write_bytes(value);before[name]=sha256(value).hexdigest()
        assert set(needed)-{'repair-admin-stats.csv'} <= set(before)
        for key in ('block','slot','arm'):
            assert prior['identity'][key]==cell[key]
        assert prior['identity']['run_id']==str(config['source_run']) and prior['identity']['source_head']==config['source_head']
        identity=json.loads((source/'identity.json').read_bytes());assert identity==prior['identity']
        original_member_hash_comparison={name:{'original_compact_hash':digest,'final_uploaded_hash':before[name],
            'equal':digest==before[name]} for name,digest in prior['source_member_sha256'].items()}
        # All business outcomes, fault/proxy evidence and boundaries must be identical.
        assert all(row['equal'] for name,row in original_member_hash_comparison.items() if name!='raw-telemetry.log')
        dest=reports/f"h-exec-compact-study-{label}-{config['source_run']}";dest.mkdir(parents=True,exist_ok=True)
        qualified=summarize(source,dest,frozen)
        after=json.loads((dest/'summary.json').read_bytes());new_census=json.loads((dest/'census.json').read_bytes())
        assert len(prior_census)==len(new_census)==480
        assert set(after['checks'])==set(prior['checks'])
        allowed_changed_checks={'native_parser_clean','baseline_native_coverage'}
        assert all(after['checks'][key]==prior['checks'][key] for key in prior['checks'] if key not in allowed_changed_checks)
        field_changes=Counter()
        for old,new in zip(prior_census,new_census):
            assert set(old)==set(new)
            for key in old:
                if old[key]!=new[key]:
                    field_changes[key]+=1
                    assert key in {'native_spans','native_error_spans'},key
        census_differences.update(field_changes)
        malformed=[];nonempty=0;offset=0
        with (source/'raw-telemetry.log').open('rb') as stream:
            for number,line in enumerate(stream,1):
                if line.strip():
                    nonempty+=1
                    try:json.loads(line)
                    except (json.JSONDecodeError,UnicodeDecodeError) as exc:
                        malformed.append({'line':number,'byte_offset':offset,'bytes':len(line),
                            'sha256':sha256(line).hexdigest(),'newline_terminated':line.endswith(b'\n'),
                            'error_type':type(exc).__name__,'error':str(exc)})
                offset+=len(line)
        assert len(malformed)==after['parse']['malformed_json_records']
        assert all(sha256((source/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
        audits.append({'block':cell['block'],'slot':cell['slot'],'arm':cell['arm'],
            'raw_artifact':raw_meta,'original_compact_artifact':compact_meta,
            'source_member_comparison':original_member_hash_comparison,
            'original_parse':prior['parse'],'sealed_parse':after['parse'],
            'original_checks':prior['checks'],'sealed_checks':after['checks'],
            'original_qualified':prior['qualified'],'sealed_qualified':qualified,
            'request_census_changed_fields':dict(field_changes),
            'sealed_native_nonempty_records':nonempty,'sealed_malformed_records':malformed,
            'source_bytes_unchanged_during_replay':True})
        raw.close();original.close()
        save(OUT/'cell-audits.json',audits)
        print(f"Replayed immutable H-EXEC {label}: old qualified={prior['qualified']}, final={qualified}",flush=True)
    collect(reports,OUT,frozen,'study',config['source_head'],config['source_run'])
    original_archive,original_meta=restore(config['original_analysis'])
    old=json.loads(original_archive.read('study-analysis.json'));original_archive.close()
    new=json.loads((OUT/'study-analysis.json').read_bytes())
    for name in old['primary_contrasts']:
        for key in ('differences_exact','mean','two_sided_p','percentile_interval','bootstrap_replicates',
                    'bootstrap_seed','percentile_interval_level','predeclared_statistical_support'):
            assert new['primary_contrasts'][name][key]==old['primary_contrasts'][name][key],(name,key)
    for key in ('secondary','static_control','route_evidence','negative_control_tolerance_met','execution_diagnostic_threshold_met'):
        assert new[key]==old[key],key
    save(OUT/'replay-audit-summary.json',{'version':config['version'],'source_run':config['source_run'],
        'source_head':config['source_head'],'replay_run':os.environ['GITHUB_RUN_ID'],'replay_head':os.environ['GITHUB_SHA'],
        'protocol_sha256':sha256(CONFIG.read_bytes()).hexdigest(),'cells':len(audits),
        'original_qualified_cells':sum(a['original_qualified'] for a in audits),
        'sealed_qualified_cells':sum(a['sealed_qualified'] for a in audits),
        'native_hash_changed_cells':sum(not a['source_member_comparison']['raw-telemetry.log']['equal'] for a in audits),
        'changed_census_fields':dict(census_differences),'business_outcomes_routes_states_identical':True,
        'primary_statistics_secondary_controls_exactly_identical':True,
        'original_analysis_artifact':original_meta,'elapsed_seconds':time.perf_counter()-started,
        'new_independent_campaigns':0,'main_campaigns':0,'original_live_read_bytes_available':False,
        'interpretation':'Re-evaluate the unchanged full gate on final immutable uploaded inputs. Original pre-teardown diagnostics and failure remain preserved; concurrent append is investigated, not assumed proven.'})


if __name__=='__main__':
    try:main()
    except Exception as exc:
        save(OUT/'failure.json',{'type':type(exc).__name__,'message':str(exc)})
        raise
