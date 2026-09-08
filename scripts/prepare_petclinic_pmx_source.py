"""Create a distinct PMX role containing native calibration and external calibration outcomes only."""
import os
from pathlib import Path
import shutil

from telemetry_availability.isolated_stochastic_fit import read, rows, write, digest
from telemetry_availability.runner import _write_csv


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    source=Path('workflow-input/learner');out=Path('workflow-results/pmx-source')
    manifest=read(source/'learner/manifest.json')
    assert manifest['usable'] is True
    calibration=[r for r in rows(source/'learner/requests.csv') if r['period']=='calibration']
    fields=('profile','period','operation','request_id','trace_id','started_at','completed_at','semantic_success','timed_out')
    _write_csv(out/'requests.csv',fields,calibration)
    shutil.copyfile(source/'native/calibration-native.json',out/'native.json')
    write(out/'manifest.json',dict(manifest,role='pmx_native_calibration',baseline_rows=0,health_rows=0,
        graph_files=0,our_parameters=0,evaluator_rows=0,external_requests=len(calibration)))
    shutil.copyfile('workflow-results/source-artifact-audit.json',out/'source-artifact-audit.json')
    write(out/'seal.json',dict(metadata=manifest,files={p.name:digest(p) for p in out.iterdir() if p.is_file() and p.name!='seal.json'}))


if __name__=='__main__': main()
