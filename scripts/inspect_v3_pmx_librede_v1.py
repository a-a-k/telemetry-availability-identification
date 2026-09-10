"""Remote source inspection and calibration time-axis census; no estimator run."""
from collections import Counter
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import zipfile

from diagnose_v3_pmx_timeout_v1 import (
    ARTIFACT, ARTIFACT_BYTES, ARTIFACT_NAME, ARTIFACT_SHA, HEAD, RUN, api, write,
)
from telemetry_availability.pmx_adapter_conformance import JAR_SHA

OUT = Path('workflow-results/pmx-librede-source')
SELECTED = {
    'LibReDEAdapter.java', 'ResourceDemandEstimationService.java',
    'DataProcessingService.java', 'EstimationSpecificationFactory.java',
    'WorkloadDescriptionFactory.java', 'TransformerInternalTraceToSystemBasic.java',
    'ReaderOpenTelemetry.java', 'SimpleApproximation.java', 'Librede.java',
    'ColtMatrix.java', 'EstimationSpecification.java',
}


def main():
    assert os.environ.get('GITHUB_ACTIONS') == 'true'
    jar = Path('workflow-input/main.jar').read_bytes()
    assert sha256(jar).hexdigest() == JAR_SHA
    sources = {}; inventory = []; class_entries = []
    with zipfile.ZipFile(io.BytesIO(jar)) as outer:
        for bundle_name in outer.namelist():
            if not bundle_name.endswith('.jar'):
                continue
            with zipfile.ZipFile(io.BytesIO(outer.read(bundle_name))) as bundle:
                for name in bundle.namelist():
                    if name.endswith('.java') and ('/pmx/' in name or '/librede/' in name):
                        inventory.append(bundle_name + '!' + name)
                    if Path(name).name in SELECTED:
                        raw = bundle.read(name)
                        assert len(raw) < 150_000
                        sources[bundle_name + '!' + name] = dict(
                            sha256=sha256(raw).hexdigest(), bytes=len(raw),
                            text=raw.decode('utf-8'))
                    if name.endswith('.class') and any(
                        name.endswith(n[:-5] + '.class') for n in SELECTED
                    ):
                        class_entries.append(bundle_name + '!' + name)
    assert any(k.endswith('LibReDEAdapter.java') for k in sources)
    source_result = dict(jar_sha256=JAR_SHA, sources=sources,
                         source_inventory=inventory, selected_class_inventory=class_entries)
    write(OUT / 'source-inspection.json', source_result)
    run = json.loads(api(f'actions/runs/{RUN}'))
    assert run['head_sha'] == HEAD and run['run_attempt'] == 1 and run['status'] == 'completed'
    meta = json.loads(api(f'actions/artifacts/{ARTIFACT}'))
    assert meta['name'] == ARTIFACT_NAME and meta['size_in_bytes'] == ARTIFACT_BYTES
    assert meta['digest'] == 'sha256:' + ARTIFACT_SHA and not meta['expired']
    data = api(f'actions/artifacts/{ARTIFACT}/zip')
    assert len(data) == ARTIFACT_BYTES and sha256(data).hexdigest() == ARTIFACT_SHA
    cases = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in sorted(archive.namelist()):
            if not (name.startswith('projection/cases/') and name.endswith('/traces/observed.json')):
                continue
            raw = archive.read(name); envelope = json.loads(raw)
            traces = envelope['data']; spans = [s for t in traces for s in t['spans']]
            starts = [s['startTime'] for s in spans]
            ends = [s['startTime'] + s['duration'] for s in spans]
            durations = [s['duration'] for s in spans]
            # Aggregate calibration metadata only; never retain trace/span IDs or test inputs.
            case = name.split('/')[2]
            groups = Counter((t['processes'][s['processID']]['serviceName'], s['operationName'])
                             for t in traces for s in t['spans'])
            cases.append(dict(case_id=case, projection_bytes=len(raw), projection_sha256=sha256(raw).hexdigest(),
                traces=len(traces), spans=len(spans), min_start_us=min(starts), max_start_us=max(starts),
                min_duration_us=min(durations), max_duration_us=max(durations),
                span_time_range_seconds=(max(ends)-min(starts))/1e6,
                negative_duration_count=sum(d < 0 for d in durations),
                zero_duration_count=sum(d == 0 for d in durations),
                service_operation_counts=[dict(service=k[0], operation=k[1], spans=v) for k,v in sorted(groups.items())]))
    assert len(cases) == 3
    write(OUT / 'compact.json', dict(version='v3-pmx-librede-source-v1',
        source_run=RUN, source_head=HEAD, diagnostic_run=os.environ['GITHUB_RUN_ID'],
        diagnostic_head=os.environ['GITHUB_SHA'], jar_sha256=JAR_SHA,
        sources={k:{a:v[a] for a in ('sha256','bytes')} for k,v in sources.items()},
        source_inspection_sha256=sha256((OUT/'source-inspection.json').read_bytes()).hexdigest(),
        calibration_projection_time_census=cases, evaluator_inputs_read=0,
        estimator_executions=0, new_independent_campaigns=0, diagnostic_is_not_qualification=True))
    print(json.dumps(dict(source_files=len(sources), cases=len(cases), estimator_executions=0)))


if __name__ == '__main__':
    main()
