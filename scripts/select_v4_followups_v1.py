"""Select the first declared followups; never select a faster/successful rerun."""
import json
import os

import retain_v3_comparison_compact_v4 as transport

SOURCE_RUN=34703686592
SOURCE_HEAD='12ddb09369ee6e0b60ca4c7db6fe1e749530b7df'


def main():
    source=transport.read_api(f'actions/runs/{SOURCE_RUN}')
    if source['head_sha']!=SOURCE_HEAD or source['path']!='.github/workflows/v4-confirmation-v2.yml':raise ValueError('wrong confirmation source')
    output=dict(ready='false',missingness_run='',performance_run='')
    if source['status']=='completed' and source['conclusion']=='success':
        chosen={}
        for kind,workflow in [('missingness','v4-missingness-v2.yml'),('performance','v4-confirmed-performance-v2.yml')]:
            if os.environ.get('MANUAL_PAIR')=='true':
                value=os.environ[kind.upper()+'_RUN']
                if not value.isdigit() or int(value)<=0:raise ValueError('exact positive run ID required')
                run=transport.read_api('actions/runs/'+value)
            else:
                runs=transport.collect_pages('actions/workflows/'+workflow+'/runs','workflow_runs')
                candidates=[r for r in runs if r['event']=='workflow_run' and r['run_attempt']==1
                    and r['head_branch']=='main' and r['created_at']>=source['created_at']]
                if not candidates:continue
                # Failed original streams stay selected. A later successful
                # execution cannot silently replace their measurements.
                run=min(candidates,key=lambda r:(r['created_at'],r['id']))
            if run['path']!='.github/workflows/'+workflow or run['run_attempt']!=1:raise ValueError('followup workflow identity differs')
            if run['status']=='completed':chosen[kind]=run['id']
        if set(chosen)=={'missingness','performance'}:
            output.update(ready='true',**{k+'_run':str(v)for k,v in chosen.items()})
    with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:
        for key,value in output.items():stream.write(key+'='+value+'\n')
    print(json.dumps(output))


if __name__=='__main__':main()
