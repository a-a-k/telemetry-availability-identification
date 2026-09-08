"""Remote normal-state contract/source interface check, excluded from main data."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import time

from telemetry_availability.live_validation_config import load_frozen_live_validation_config
from telemetry_availability.live_placement_config import select_placement_pilot_profile
from telemetry_availability.live_pilot_config import select_runtime_pilot_profile
from telemetry_availability.publication_stochastic_live import (_run_period,_semantic_sentinels,
    initialize_profile,wait_for_frontend,_collect_telemetry,_utc_now,_write_csv,REQUEST_FIELDS,HEALTH_FIELDS,_write_jsonl)
from telemetry_availability.pmx_observed_operations import read_native
from telemetry_availability.isolated_stochastic_fit import write


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    config=load_frozen_live_validation_config('configs/m7_frozen_live.yaml').stochastic
    profile=select_placement_pilot_profile(config.placement,args.profile)
    runtime=select_runtime_pilot_profile(config.placement.runtime,args.profile)
    out=args.out;compose=out/'pinned-compose.json';started=_utc_now()
    wait_for_frontend(runtime,config.placement.runtime.readiness_timeout_seconds)
    time.sleep(config.placement.runtime.post_start_stabilization_seconds)
    initialize_profile(runtime)
    namespace='ten-contract-qualification-'+os.environ['GITHUB_RUN_ID']
    sentinels,responses,effects=_semantic_sentinels(config,profile,runtime,'colocated','N',0,namespace)
    _write_csv(out/'sentinel-requests.csv',REQUEST_FIELDS,sentinels)
    _write_jsonl(out/'sentinel-responses.jsonl',responses)
    write(out/'semantic-effect-audit.json',effects)
    requests,response_rows,events,health,period=_run_period(config,profile,runtime,'colocated','N',0,'baseline',60,
        compose,(),base_seed=771501,request_namespace=namespace)
    _write_csv(out/'requests.csv',REQUEST_FIELDS,requests)
    _write_jsonl(out/'responses.jsonl',response_rows)
    _write_csv(out/'health.csv',HEALTH_FIELDS,health)
    time.sleep(config.trace_flush_seconds)
    native_count,telemetry_error=_collect_telemetry(runtime,started,out)
    path=out/('raw-telemetry.json' if runtime.telemetry_kind=='jaeger_api' else 'raw-telemetry.log')
    grouped,parse=read_native(path,{r['trace_id'] for r in requests},'jaeger_json_v1' if runtime.telemetry_kind=='jaeger_api' else 'otlp_jsonl_v1')
    successes=[r for r in requests if r['semantic_success']]
    rates={op:sum(r['semantic_success'] for r in requests if r['operation']==op)/80 for op in runtime.operations}
    checks=dict(exact_240_attempts=len(requests)==240,unique_attempt_ids=len({r['request_id'] for r in requests})==240,
        all_normal_contracts=all(v>=.95 for v in rates.values()),
        all_sentinels=all(r['semantic_success'] for r in sentinels),
        successful_trace_fraction_at_least_95=sum(bool(grouped.get(r['trace_id'])) for r in successes)>=.95*len(successes),
        all_timely_successes=all(r['latency_ms']<=2000 for r in successes))
    summary=dict(profile=profile.id,source_commit=runtime.commit,study_head=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],
        scope='new_contract_interface_only',main_campaigns=0,fits=0,checks=checks,qualified=all(checks.values()),
        operation_rates=rates,attempts=len(requests),successes=len(successes),parse=parse,telemetry_error=telemetry_error,
        period=period,sentinel_results=sentinels,
        operation_diagnostics=[dict(operation=op,reasons=dict(Counter(r['semantic_reason'] for r in requests if r['operation']==op)),
            first_failure=next((r for r in requests if r['operation']==op and not r['semantic_success']),None)) for op in runtime.operations])
    write(out/'contract-summary.json',summary)
    if not summary['qualified']:
        raise ValueError('new external operation contract not qualified; full source preserved')


if __name__=='__main__': main()
