"""Remote matched retained-input qualification; no fresh application campaign."""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

from build_pmx_clock_progress_v1 import build, CLASS
from diagnose_v3_pmx_timeout_v1 import HEAD, RUN, api, write
from run_pmx_derived_diagnostic_v1 import run_derived_pmx
from telemetry_availability.pmx_context_extraction_v3 import extract
from telemetry_availability.v3_comparison_pmx_v2 import LEGACY_CONFIG

CONFIG=Path('configs/pmx_clock_progress_qualification_v1.json')


def numeric_controls(build_root):
    # Exercise the compiled Java guard at the observed epoch, zero epoch,
    # a sub-ULP division, an ordinary interval and an invalid interval.
    java='''package org.palladiosimulator.pmx.transformer.internaltracetosystem.otlp;
import tools.descartes.librede.util.RepositoryUtil;
import tools.descartes.librede.util.RepositoryUtil.Range;
public class ClockProgressControls {
  static Range range(double start, double end) throws Exception {
    var constructor=Range.class.getDeclaredConstructor(RepositoryUtil.class,double.class,double.class);
    constructor.setAccessible(true);
    return constructor.newInstance(new RepositoryUtil(),start,end);
  }
  static void check(double start,double end,double expected) throws Exception {
    var r=range(start,end);double step=EstimationSpecificationFactory.progressStepSeconds(r);
    if(step!=expected || !(start+step>start) || r.getStart()!=start || r.getEnd()!=end)
      throw new AssertionError("clock or interval invariant");
  }
  public static void main(String[] args) throws Exception {
    double epoch=1789023783.11267;
    check(epoch,epoch,Math.ulp(epoch));
    check(0,0,1e-9);
    check(epoch,Math.nextUp(epoch),Math.ulp(epoch));
    check(epoch,epoch+20,1);
    boolean rejected=false;
    try {EstimationSpecificationFactory.progressStepSeconds(range(2,1));}
    catch(IllegalArgumentException expected){rejected=true;}
    if(!rejected) throw new AssertionError("negative interval accepted");
    System.out.println("5 compiled Java clock/interval controls passed");
  }
}'''
    path=build_root/'source/ClockProgressControls.java';path.write_bytes(java.encode())
    cp=str(build_root/'classes')+os.pathsep+str(build_root/'dependencies/*')
    subprocess.run(['javac','--release','11','-cp',cp,'-d',str(build_root/'classes'),str(path)],check=True,timeout=45)
    result=subprocess.run(['java','-cp',cp,CLASS.rsplit('/',1)[0].replace('/','.')+'.ClockProgressControls'],capture_output=True,text=True,check=True,timeout=30)
    assert result.stdout.strip()=='5 compiled Java clock/interval controls passed'
    return dict(qualified=True,controls=5,stdout=result.stdout.strip(),source_sha256=sha256(path.read_bytes()).hexdigest())


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    p=argparse.ArgumentParser();p.add_argument('--key',required=True);args=p.parse_args()
    config=json.loads(CONFIG.read_bytes());anchor=next(r for r in config['artifacts'] if r['key']==args.key)
    run=json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha']==HEAD and run['run_attempt']==1 and run['status']=='completed'
    meta=json.loads(api(f"actions/artifacts/{anchor['id']}"))
    assert all(meta[k]==anchor[k] for k in ('name','size_in_bytes','digest')) and not meta['expired']
    data=api(f"actions/artifacts/{anchor['id']}/zip")
    assert len(data)==anchor['size_in_bytes'] and 'sha256:'+sha256(data).hexdigest()==anchor['digest']
    out=Path('workflow-results/clock-qualification');out.mkdir(parents=True,exist_ok=True)
    original=out/'retained';original.mkdir()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.testzip() is None
        names=archive.namelist();assert len(names)==len(set(names))
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        archive.extractall(original)
    contract=original/'projection';prepared=json.loads((contract/'application-input-contract.json').read_bytes())
    old_record_paths=list(original.glob('extraction-*.json'));assert len(old_record_paths)==1
    old_record=json.loads(old_record_paths[0].read_bytes());key=old_record['sample_key']
    jar,build_record=build(Path('workflow-input/main.jar'),out/'build')
    controls=numeric_controls(out/'build')
    prepared['original_head_sha']=prepared['head_sha'];prepared['head_sha']=os.environ['GITHUB_SHA']
    prepared['run_id']=os.environ['GITHUB_RUN_ID']
    write(contract/'application-input-contract.json',prepared)
    output=out/'extraction';output.mkdir()
    launch=lambda j,r,o:run_derived_pmx(j,r,o,expected_jar_sha256=build_record['derived_jar_sha256'],limit=120)
    extract(LEGACY_CONFIG,contract,key,jar,output,launcher=launch)
    record_path=output/('extraction-'+key+'.json');record=json.loads(record_path.read_bytes())
    for field in ('prospective_identity','input_seal_sha256','stages','read_audit'):
        record[field]=prepared[field]
    record['clock_progress_qualification']=dict(original_run=RUN,original_head=HEAD,build=build_record,
        development_diagnostic_only=True,independent_main_campaigns=0)
    write(record_path,record)
    matched=[]
    for case in record['cases']:
        cid=case['case_id'];old=next(r for r in old_record['cases'] if r['case_id']==cid)
        row=dict(case_id=cid,original_qualified=old['qualified'],new_qualified=case['qualified'],
            execution=case.get('execution'),variants=case['variants'],error=case.get('error'),
            reconstruction=case.get('reconstruction'),checks=case.get('checks'))
        if old['qualified'] and case['qualified']:
            before=json.loads((original/'raw'/cid/'resolved-pcm.json').read_bytes())
            after=json.loads((output/'raw'/cid/'resolved-pcm.json').read_bytes())
            row['unchanged_resolved_fields']={k:before[k]==after[k] for k in before if k!='model_files'}
        matched.append(row)
    result=dict(version='pmx-clock-progress-qualification-v1',source_run=RUN,source_head=HEAD,
        diagnostic_run=os.environ['GITHUB_RUN_ID'],diagnostic_head=os.environ['GITHUB_SHA'],key=args.key,
        original_artifact=anchor,build=build_record,numeric_controls=controls,cases=matched,
        extraction_qualified=all(r['new_qualified'] for r in matched),
        unaffected_semantics_unchanged=all(all(r.get('unchanged_resolved_fields',{}).values()) for r in matched),
        evaluator_inputs_read=0,new_independent_campaigns=0,solver_qualification_pending=True)
    write(out/'compact.json',result)
    assert result['extraction_qualified'] and result['unaffected_semantics_unchanged']
    print(json.dumps(dict(key=args.key,qualified=True,cases=len(matched),derived_jar_sha256=build_record['derived_jar_sha256'])))


if __name__=='__main__':main()
