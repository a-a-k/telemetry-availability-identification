"""Validate successful scientific stages despite the unrelated transfer-table bug."""
import retain_v3_comparison_compact_v4 as transport

SOURCE_RUN=34703686592
SOURCE_HEAD='12ddb09369ee6e0b60ca4c7db6fe1e749530b7df'


def validate(run,jobs):
    if (run['id']!=SOURCE_RUN or run['head_sha']!=SOURCE_HEAD or run['path']!='.github/workflows/v4-confirmation-v2.yml'
        or run['status']!='completed' or run['run_attempt']!=1 or run['conclusion']!='failure'):
        raise ValueError('fixed confirmation source differs')
    failed=[j for j in jobs if j['conclusion']!='success']
    if len(failed)!=1 or failed[0]['name']!='analysis' or failed[0]['conclusion']!='failure':
        raise ValueError('a scientific stage failed; the summary exception cannot admit it')
    for phase in ('acquire','graph','pmx','freeze','bounds','evaluate','primary'):
        selected=[j for j in jobs if j['name'].startswith(phase+' (')]
        if len(selected)!=18 or any(j['conclusion']!='success'for j in selected):raise ValueError('incomplete scientific stage: '+phase)
    return dict(source_run=SOURCE_RUN,source_head=SOURCE_HEAD,all_scientific_jobs_succeeded=True,
        original_overall_conclusion='failure',sole_failed_job='analysis',
        explanation='legacy placement-transfer table requested colocated outside the prespecified split-only design')


def require_source():
    run=transport.read_api(f'actions/runs/{SOURCE_RUN}')
    jobs=transport.collect_pages(f'actions/runs/{SOURCE_RUN}/jobs','jobs')
    return validate(run,jobs)
