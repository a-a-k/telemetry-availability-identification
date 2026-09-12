"""Select the first declared followups; never select a faster/successful rerun."""
import json
import os

import retain_v3_comparison_compact_v4 as transport
from v4_confirmed_source_v3 import require_source

SUMMARY_RUN=34707482231
FIRST_FOLLOWUPS={'missingness':34707544832,'performance':34707544825}


def main():
    require_source()
    source=transport.read_api(f'actions/runs/{SUMMARY_RUN}')
    if (source['path']!='.github/workflows/v4-confirmation-summary-v3.yml' or source['run_attempt']!=1
        or source['head_sha']!='a19fef0b998eb1f995ebd06acdde10acd819ff19'):
        raise ValueError('wrong separate aggregate producer')
    output=dict(ready='false',summary_run=str(SUMMARY_RUN),missingness_run='',performance_run='')
    if source['status']=='completed' and source['conclusion']=='success':
        chosen={}
        for kind,workflow in [('missingness','v4-missingness-v3.yml'),('performance','v4-confirmed-performance-v3.yml')]:
            if os.environ.get('MANUAL_PAIR')=='true':
                value=os.environ[kind.upper()+'_RUN']
                if not value.isdigit() or int(value)<=0:raise ValueError('exact positive run ID required')
                if int(value)!=FIRST_FOLLOWUPS[kind]:raise ValueError('a replacement execution cannot substitute for the first measurement')
                run=transport.read_api('actions/runs/'+value)
            else:
                runs=transport.collect_pages('actions/workflows/'+workflow+'/runs','workflow_runs')
                candidates=[r for r in runs if r['event']=='workflow_run' and r['run_attempt']==1
                    and r['head_branch']=='main' and r['created_at']>=source['created_at']]
                if not candidates:raise ValueError('declared first measurement is missing')
                # Failed original streams stay selected. A later successful
                # execution cannot silently replace their measurements.
                run=min(candidates,key=lambda r:(r['created_at'],r['id']))
            if run['id']!=FIRST_FOLLOWUPS[kind]:raise ValueError('first measurement identity differs')
            if run['path']!='.github/workflows/'+workflow or run['run_attempt']!=1:raise ValueError('followup workflow identity differs')
            if run['status']=='completed':chosen[kind]=run['id']
        if set(chosen)=={'missingness','performance'}:
            output.update(ready='true',**{k+'_run':str(v)for k,v in chosen.items()})
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:
        for key,value in output.items():stream.write(key+'='+value+'\n')
    print(json.dumps(output))


if __name__=='__main__':main()
