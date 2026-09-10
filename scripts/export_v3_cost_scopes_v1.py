"""Copy recorded cost observations into separate scope tables; no recalculation.

Reads only the existing compact comparison JSON. The experiment, forecasts,
bootstrap, original cost summaries and null measurements are unchanged.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from render_v3_comparison_tables_v1 import csv_bytes


def export(source, out):
    raw = source.read_bytes()
    document = json.loads(raw)
    if document['version'] != 'v3-prospective-comparison-result-v1':
        raise ValueError('unexpected cost source version')
    costs = document['analysis']['costs']
    stages, processes, models, extractions, inputs = [], [], [], [], []
    seen = set()
    for record in costs['raw_records']:
        identity = {key: record[key] for key in ('campaign_id', 'job_role', 'attempt_id')}
        key = tuple(identity.values())
        if key in seen:
            raise ValueError('duplicate campaign cost role')
        seen.add(key)
        for stage in record.get('stages', []):
            stages.append(dict(**identity, **stage))
        resources = record.get('process_resources', {})
        for resource in resources.get('records', []):
            processes.append(dict(**identity, scope='campaign_process',
                                  rss_scope=resources['rss_scope'], **resource))
        inputs.append(dict(**identity, **{key: record.get(key) for key in (
            'input_bytes', 'native_bytes', 'ordinary_role_bytes', 'pmx_role_bytes',
            'input_loading_seconds', 'combined_process_seconds', 'acquisition_process_seconds',
            'shared_native_extraction_seconds', 'manual_integration_seconds',
            'manual_reason', 'update_seconds', 'update_reason')}))
        for case in record.get('extraction_and_bridge_records', []):
            execution = case.get('execution', {})
            extractions.append(dict(**identity, case_id=case['case_id'], qualified=case['qualified'],
                                    **{key: execution.get(key) for key in (
                                        'elapsed_seconds', 'startup_seconds', 'internal_watchdog_seconds',
                                        'exit_code', 'started_at', 'finished_at', 'jar_sha256')}))
        for model in record.get('solver_evidence', []):
            base = dict(**identity, model_id=model['model_id'],
                        variant=model.get('extraction', {}).get('variant'),
                        extraction_status=model.get('extraction', {}).get('status'))
            observations = model.get('solver_records', [])
            if not observations:
                models.append(dict(**base, status='no_solver_timing', repetition=None,
                                   load_solve_elapsed_nanoseconds=None,
                                   evaluated_physical_states=None, total_physical_states=None))
            for observation in observations:
                models.append(dict(**base, **{key: observation.get(key) for key in (
                    'status', 'repetition', 'load_solve_elapsed_nanoseconds',
                    'evaluated_physical_states', 'total_physical_states')}))
    seen_batches = set()
    for batch in costs['shared_batch_resources']:
        key = (batch['profile'], batch['run_id'])
        if key in seen_batches:
            raise ValueError('duplicate application resource batch')
        seen_batches.add(key)
        for resource in batch['resources']['records']:
            processes.append(dict(scope='application_batch', profile=batch['profile'],
                                  run_id=batch['run_id'], shared_once_across_this_application=True,
                                  rss_scope=batch['resources']['rss_scope'], **resource))
    files = {name: csv_bytes(rows) for name, rows in (
        ('stage-observations.csv', stages), ('process-resources.csv', processes),
        ('pmx-model-timings.csv', models), ('pmx-extraction-timings.csv', extractions),
        ('pipeline-inputs-and-unknowns.csv', inputs))}
    note = '''# Recorded cost scopes

These tables copy existing observations from the compact comparison. They do not rerun a model or introduce another statistical contrast. Empty numeric cells represent missing measurements. The original pooled stage summaries remain unchanged in the parent result tables.

| Table | Observation unit | Interpretation |
| --- | --- | --- |
| stage-observations.csv | Recorded campaign or operation stage; the operation column identifies operation-level timers | Graph-family extraction, identification and functional evaluation are shared across graph variants. B0 identification is timed across the campaign's operations. Observation counts and units must accompany duration comparisons. |
| process-resources.csv | One timed process/children report, or one deduplicated application solver batch | Wall time, user/system CPU and maximum RSS have their recorded process scope. They are not whole-deployment resource measurements. Batch resources include their actual preparation, controls and repeated solves. Overlapping stage/process times and concurrent RSS peaks cannot be summed into a total. |
| pmx-model-timings.csv | One existing model-load/solve invocation, retaining model variant and repetition | Original nanosecond values are preserved. Individual model timers and batch totals have different boundaries. The two verification passes are not independent experimental campaigns. A model without a timing has an explicit row with null measurement. |
| pmx-extraction-timings.csv | One independent PMX extraction process for a campaign operation | The measured duration includes the declared launcher startup. Startup and extraction are not both charged as independent elapsed intervals. |
| pipeline-inputs-and-unknowns.csv | One campaign pipeline role | Role bytes and loading/process durations retain their original boundaries. Shared acquisition observes the combined instrumented experiment; it is not a measurement of the minimum acquisition cost of each method in isolation. |

Graph operation-stage timers are available only where the implementation records them. A missing structural binding can omit these stage observations while its campaign process cost remains measured. Point forecast support, interval support and timing support therefore differ. A fast bound calculation is not automatically an accurate or point-identified forecast.

GNU-time RSS describes the timed process and its accounted children, not the simultaneous sum of application containers or total machine memory. CPU and wall intervals include only their recorded commands. Existing within-process stage timers can omit interpreter/JVM setup included by a surrounding process timer. No speed ratio is inferred by dividing unlike scopes.

Historical integration labor is unmeasured. Incremental updating is unmeasured; fresh reconstruction is a separate application of the implemented method. Monitoring off/on overhead and scalability are unmeasured. None is replaced with zero or inferred from inexpensive solver calls.
'''
    files['README.md'] = note.encode()
    provenance = dict(version='v3-recorded-cost-scopes-v1', source=source.as_posix(),
                      source_sha256=sha256(raw).hexdigest(), run_id=document['run_id'],
                      head=document['head'], mode=document['mode'],
                      exporter_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                      model_execution=False, raw_application_data_read=False,
                      source_observations_copied_without_recalculation=True,
                      stage_observations=len(stages), process_records=len(processes),
                      pmx_model_timing_rows=len(models), pmx_extraction_rows=len(extractions),
                      campaign_role_records=len(inputs), application_batches=len(seen_batches),
                      outputs={name: dict(bytes=len(data), sha256=sha256(data).hexdigest())
                               for name, data in files.items()})
    files['provenance.json'] = (json.dumps(provenance, indent=2) + '\n').encode()
    files['.gitattributes'] = b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n'
    out.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = out / name
        if path.exists() and path.read_bytes() != data:
            raise ValueError('existing cost export differs: ' + str(path))
        path.write_bytes(data)
    return provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.source, args.out)
    print(json.dumps({key: value for key, value in result.items() if key != 'outputs'}))
