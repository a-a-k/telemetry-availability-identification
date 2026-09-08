"""Remote three-application B0 technical binding, using existing calibration only."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from telemetry_availability.health_prefix_audit_v3 import restore

CONFIG=Path('configs/b0_technical_v3.json')


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,indent=2)+'\n').encode())


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('prepare','report'))
    parser.add_argument('--profile',required=True);args=parser.parse_args()
    config=json.loads(CONFIG.read_bytes())
    for lock in config['repository_locks']:
        assert sha256(Path(lock['path']).read_bytes()).hexdigest()==lock['sha256'],lock['path']
    spec=config['profiles'][args.profile]
    out=Path('workflow-results/compact')
    if args.stage=='prepare':
        archive,metadata=restore(spec['artifact'])
        source=Path('workflow-input/b0');source.mkdir(parents=True,exist_ok=True)
        for name in ('requests.json','seal.json'):
            (source/name).write_bytes(archive.read(name))
        archive.close()
        save(out/'source-audit.json',{'artifact':metadata,'profile':args.profile,
            'role_scope':spec['role_scope'],'source_transfer_bytes':spec['artifact']['size_in_bytes'],
            'materialized_files':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha256(p.read_bytes()).hexdigest()} for p in sorted(source.iterdir())],
            'evaluator_files_received':False,'main_campaigns':0,'new_independent_campaigns':0})
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as stream:
            stream.write('operations='+' '.join(spec['operations'])+'\n')
    else:
        model_path=Path('workflow-results/model/b0-model.json');model=json.loads(model_path.read_bytes())
        read_audit=json.loads(Path('workflow-results/model/consumer-read-audit.json').read_bytes())
        assert len(read_audit['actual_data_reads'])==2 and not read_audit['blocked']
        assert set(model['forecasts'])==set(spec['operations'])
        for row in model['forecasts'].values():
            assert row['attempts']==spec['expected_attempts_per_operation'] and row['status']=='ok'
            assert row['probability']==row['successes']/row['attempts']
        shutil.copyfile('workflow-results/model/consumer-read-audit.json',out/'consumer-read-audit.json')
        save(out/'qualification.json',{'profile':args.profile,'run_id':os.environ['GITHUB_RUN_ID'],
            'head':os.environ['GITHUB_SHA'],'protocol_sha256':sha256(CONFIG.read_bytes()).hexdigest(),
            'qualified':True,'operations':len(model['forecasts']),'calibration_attempts':model['external_attempts'],
            'forecast_summary':[{'operation':op,'attempts':r['attempts'],'successes':r['successes'],
                'timeouts':r['timeouts'],'probability':r['probability']} for op,r in model['forecasts'].items()],
            'model_sha256':sha256(model_path.read_bytes()).hexdigest(),'model_bytes':model_path.stat().st_size,
            'main_campaigns':0,'new_independent_campaigns':0,'scope':spec['role_scope']})


if __name__=='__main__':main()
