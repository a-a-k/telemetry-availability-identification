"""Remote observer-only LibReDE configuration capture on retained calibration."""
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from diagnose_v3_pmx_timeout_v1 import (
    ARTIFACT, ARTIFACT_BYTES, ARTIFACT_NAME, ARTIFACT_SHA, CASE, HEAD, RUN, api, write,
)
from telemetry_availability.pmx_adapter_conformance import JAR_SHA
from run_pmx_derived_diagnostic_v1 import run_derived_pmx

OUT = Path('workflow-results/pmx-step-diagnostic-v2')
BUNDLE = 'jar/org.palladiosimulator.pmx.transformer.internaltracetosystem.otlp.jar'
CLASS = 'org/palladiosimulator/pmx/transformer/internaltracetosystem/otlp/LibReDEAdapter'
SOURCE_SHA = 'd1a010c7bd12906aed1c9d221b3de75c04caa45172242af19811192cc03eb622'


def rewrite_zip(raw, changes):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as old, zipfile.ZipFile(output, 'w') as new:
        assert set(changes) <= set(old.namelist())
        for info in old.infolist():
            new.writestr(info, changes.get(info.filename, old.read(info.filename)))
    return output.getvalue()


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    OUT.mkdir(parents=True, exist_ok=True)
    jar = Path('workflow-input/main.jar').read_bytes()
    assert sha256(jar).hexdigest() == JAR_SHA
    dependencies = OUT/'dependencies'; dependencies.mkdir()
    with zipfile.ZipFile(io.BytesIO(jar)) as outer:
        for name in outer.namelist():
            if name.startswith('jar/') and name.endswith('.jar'):
                (dependencies/Path(name).name).write_bytes(outer.read(name))
        bundle = outer.read(BUNDLE)
    with zipfile.ZipFile(io.BytesIO(bundle)) as inner:
        original_source = inner.read('OSGI-OPT/src/' + CLASS + '.java')
    assert sha256(original_source).hexdigest() == SOURCE_SHA
    source = original_source.decode('utf-8')
    target = 'return Librede.execute(configuration, x);'
    assert source.count(target) == 1
    observer = '''var auditResource = new XMIResourceImpl(URI.createFileURI("librede-config-" + host + ".xmi"));
        auditResource.getContents().add(EcoreUtil.copy(configuration));
        try { auditResource.save(null); } catch (IOException auditError) { throw new IllegalStateException(auditError); }
        return Librede.execute(configuration, x);'''
    source = source.replace(target, observer)
    source_path = OUT/'observer-source/LibReDEAdapter.java'
    source_path.parent.mkdir(); source_path.write_bytes(source.encode())
    classes = OUT/'observer-classes'; classes.mkdir()
    subprocess.run(['javac','--release','11','-cp',str(dependencies/'*'),'-d',str(classes),str(source_path)],check=True,timeout=90)
    class_path = classes/(CLASS+'.class')
    new_bundle = rewrite_zip(bundle,{CLASS+'.class':class_path.read_bytes()})
    observer_jar = OUT/'observer-main.jar'
    observer_jar.write_bytes(rewrite_zip(jar,{BUNDLE:new_bundle}))
    bytecode = {}
    for cls in ('tools.descartes.librede.Librede', 'tools.descartes.librede.util.RepositoryUtil',
                'tools.descartes.librede.util.RepositoryUtil$Range',
                'tools.descartes.librede.algorithm.SimpleApproximation',
                'tools.descartes.librede.repository.TimeSeries',
                'org.palladiosimulator.pmx.reader.otlp.ReaderOpenTelemetry',
                'org.palladiosimulator.pmx.transformer.internaltracetosystem.otlp.LibReDEAdapter'):
        result = subprocess.run(['javap','-cp',str(dependencies/'*'),'-c','-p',cls],capture_output=True,text=True,check=True,timeout=20)
        bytecode[cls] = result.stdout
    with zipfile.ZipFile(io.BytesIO(jar)) as outer:
        extra = {}
        for name in outer.namelist():
            if not name.endswith('.jar'): continue
            with zipfile.ZipFile(io.BytesIO(outer.read(name))) as inner:
                for member in inner.namelist():
                    if member.startswith('OSGI-OPT/src/') and member.endswith('TransformerTraceToInternalTraceBasic.java'):
                        raw = inner.read(member)
                        extra[name+'!'+member] = dict(sha256=sha256(raw).hexdigest(), text=raw.decode())
    observer_bytecode=subprocess.run(['javap','-cp',str(classes)+os.pathsep+str(dependencies/'*'),'-c','-p',CLASS.replace('/','.')],capture_output=True,text=True,check=True,timeout=20).stdout
    write(OUT/'source-bytecode-inspection.json',dict(bytecode=bytecode,additional_sources=extra,observer_class_bytecode=observer_bytecode))
    run = json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha']==HEAD and run['run_attempt']==1 and run['status']=='completed'
    meta = json.loads(api(f'actions/artifacts/{ARTIFACT}'))
    assert meta['name']==ARTIFACT_NAME and meta['size_in_bytes']==ARTIFACT_BYTES
    assert meta['digest']=='sha256:'+ARTIFACT_SHA and not meta['expired']
    data = api(f'actions/artifacts/{ARTIFACT}/zip')
    assert len(data)==ARTIFACT_BYTES and sha256(data).hexdigest()==ARTIFACT_SHA
    projection = OUT/'projection'; input_hashes = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        prefix = 'projection/cases/'+CASE+'/'
        for info in archive.infolist():
            if not info.filename.startswith(prefix) or info.is_dir():continue
            relative = info.filename[len(prefix):]
            assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
            raw = archive.read(info); path = projection/relative
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
            input_hashes[relative] = sha256(raw).hexdigest()
    result = dict(version='v3-pmx-step-diagnostic-v2',source_run=RUN,source_head=HEAD,
        diagnostic_run=os.environ['GITHUB_RUN_ID'], diagnostic_head=os.environ['GITHUB_SHA'],
        original_jar_sha256=JAR_SHA,observer_jar_sha256=sha256(observer_jar.read_bytes()).hexdigest(),
        original_source_sha256=SOURCE_SHA,observer_source_sha256=sha256(source_path.read_bytes()).hexdigest(),
        observer_change='Write EcoreUtil.copy(configuration) to XMI immediately before unchanged Librede.execute',
        projection_sha256=input_hashes,source_bytecode_sha256=sha256((OUT/'source-bytecode-inspection.json').read_bytes()).hexdigest(),
        estimator_watchdog_seconds=120,diagnostic_is_not_qualification=True,evaluator_inputs_read=0,new_independent_campaigns=0)
    write(OUT/'compact.json', result)
    result['execution'] = run_derived_pmx(observer_jar,projection,OUT/'replay',expected_jar_sha256=result['observer_jar_sha256'],limit=120)
    configs=[]
    for path in sorted((OUT/'replay').glob('librede-config-*.xmi')):
        root=ET.fromstring(path.read_bytes())
        estimation=next(e for e in root.iter() if e.tag.split('}')[-1]=='estimation')
        configs.append(dict(file=path.name,sha256=sha256(path.read_bytes()).hexdigest(),
            estimation_attributes=dict(estimation.attrib),
            estimation_elements=[dict(tag=e.tag.split('}')[-1],attributes=dict(e.attrib)) for e in estimation.iter() if e is not estimation]))
    result['captured_configurations']=configs
    result['input_hashes_unchanged']=all(sha256((projection/name).read_bytes()).hexdigest()==digest for name,digest in input_hashes.items())
    assert result['input_hashes_unchanged'] and configs
    write(OUT/'compact.json',result)
    print(json.dumps(dict(configurations=len(configs),exit_code=result['execution']['exit_code'])))


if __name__=='__main__':main()
