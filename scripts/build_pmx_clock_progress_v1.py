"""Build a disclosed PMX time-step progress guard remotely from pinned source."""
import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

from telemetry_availability.pmx_adapter_conformance import JAR_SHA

BUNDLE = 'jar/org.palladiosimulator.pmx.transformer.internaltracetosystem.otlp.jar'
CLASS = 'org/palladiosimulator/pmx/transformer/internaltracetosystem/otlp/EstimationSpecificationFactory'
SOURCE = 'OSGI-OPT/src/'+CLASS+'.java'
SOURCE_SHA = '75c92344f9e8d43d08a80a89b77a2f236e6ab00d64ab530f46917b3158f3e157'
OLD = '.setStepSize(UnitsFactory.eINSTANCE.createQuantity(range.getValue() / 20, Time.SECONDS));'
NEW = '.setStepSize(UnitsFactory.eINSTANCE.createQuantity(progressStepSeconds(range), Time.SECONDS));'
GUARD = '''
    // A singleton overlap has zero width. Preserve that overlap and all samples,
    // but make the clock advance by at least one nanosecond or one double ULP.
    static double progressStepSeconds(Range range) {
        double width = range.getValue();
        double start = range.getStart();
        double end = range.getEnd();
        if (!Double.isFinite(start) || !Double.isFinite(end) || width < 0) {
            throw new IllegalArgumentException("Invalid LibReDE estimation interval");
        }
        double step = width / 20;
        if (!(step > 0) || !(start + step > start)) {
            step = Math.max(1e-9, Math.ulp(start));
        }
        if (!Double.isFinite(step) || !(start + step > start)) {
            throw new IllegalArgumentException("LibReDE clock cannot advance");
        }
        return step;
    }
'''


def patched_source(raw):
    if sha256(raw).hexdigest() != SOURCE_SHA:
        raise ValueError('PMX factory source differs')
    text=raw.decode('utf-8')
    if text.count(OLD)!=1 or not text.rstrip().endswith('}'):
        raise ValueError('PMX factory patch context differs')
    text=text.replace(OLD,NEW)
    end=text.rfind('}')
    return (text[:end]+GUARD+text[end:]).encode()


def replace_members(raw, changes):
    buffer=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(buffer,'w') as output:
        assert len(original.namelist())==len(set(original.namelist()))
        assert set(changes)<=set(original.namelist())
        for info in original.infolist():
            output.writestr(info, changes.get(info.filename,original.read(info.filename)))
    updated=buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(io.BytesIO(updated)) as result:
        assert original.namelist()==result.namelist()
        assert result.testzip() is None
        actual={name for name in original.namelist() if original.read(name)!=result.read(name)}
        assert actual==set(changes)
    return updated


def build(original_path, out):
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'PMX JAR processing is remote only'
    raw=original_path.read_bytes()
    if sha256(raw).hexdigest()!=JAR_SHA:raise ValueError('Author PMX JAR differs')
    out.mkdir(parents=True,exist_ok=False)
    deps=out/'dependencies';deps.mkdir()
    with zipfile.ZipFile(io.BytesIO(raw)) as outer:
        bundle=outer.read(BUNDLE)
        for name in outer.namelist():
            if name.startswith('jar/') and name.endswith('.jar'):
                (deps/Path(name).name).write_bytes(outer.read(name))
    with zipfile.ZipFile(io.BytesIO(bundle)) as inner:source=inner.read(SOURCE)
    new_source=patched_source(source)
    source_path=out/'source/EstimationSpecificationFactory.java';source_path.parent.mkdir()
    source_path.write_bytes(new_source)
    classes=out/'classes';classes.mkdir()
    command=['javac','--release','11','-cp',str(deps/'*'),'-d',str(classes),str(source_path)]
    subprocess.run(command,check=True,timeout=90)
    class_bytes=(classes/(CLASS+'.class')).read_bytes()
    new_bundle=replace_members(bundle,{CLASS+'.class':class_bytes,SOURCE:new_source})
    derived=replace_members(raw,{BUNDLE:new_bundle});target=out/'main-clock-progress-v1.jar';target.write_bytes(derived)
    result=dict(version='pmx-clock-progress-v1',original_jar_sha256=JAR_SHA,
        derived_jar_sha256=sha256(derived).hexdigest(),derived_jar_bytes=len(derived),
        original_factory_source_sha256=SOURCE_SHA,derived_factory_source_sha256=sha256(new_source).hexdigest(),
        derived_factory_class_sha256=sha256(class_bytes).hexdigest(),
        changed_outer_members=[BUNDLE],changed_bundle_members=[CLASS+'.class',SOURCE],
        compiler=subprocess.check_output(['javac','-version'],text=True).strip(),java_release=11,
        preserved='Every other JAR member; all time intervals, samples, projections, failure estimators and model bridges',
        change='Use width/20 unless it cannot advance the clock; then max(1ns, ulp(start))',
        qualification_required=True)
    (out/'build-provenance.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    return target,result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();_,result=build(args.original,args.out)
    print(json.dumps(result))


if __name__=='__main__':main()
