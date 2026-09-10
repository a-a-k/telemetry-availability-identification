"""Render the prospective workflow, reusing the qualified Palladio build steps.

Maintenance-only generator: it performs no experiment, download or tool launch.
"""
from copy import deepcopy
from pathlib import Path
import yaml

RUN = '${{ github.run_id }}'
KEY = '${{ matrix.key }}'
PROFILE = '${{ matrix.profile }}'
MODE = '${{ inputs.mode }}'
PET = 'spring_petclinic_microservices'


def upload(name, path):
    return dict(uses='actions/upload-artifact@v7', **{'if': '${{ always() }}', 'with': {
        'name': name+'-'+RUN, 'path': path, 'retention-days': 90, 'if-no-files-found': 'warn'}})


def download(name, path, pattern=False):
    return dict(uses='actions/download-artifact@v8', **{'with': {
        'pattern' if pattern else 'name': name+'-'+RUN, 'path': path}})


def run(name, command, **extra):
    return dict(name=name, run=command, **extra)


def setup():
    return [dict(uses='actions/checkout@v7', **{'with': {'persist-credentials': False}}),
        dict(uses='actions/setup-python@v7', **{'with': {'python-version': '3.13.15', 'cache': 'pip'}}),
        run('Install pinned Python environment', 'python -m pip install -r requirements.txt\npython -m pip install --no-deps -e .'),
        run('Verify complete frozen comparison implementation', 'python scripts/verify_staged_research_lock.py configs/v3_comparison_execution_v2.json')]


def matrix_job(needs, steps, minutes, parallel=20):
    return dict(needs=needs, **{'if': "${{ always() && needs.plan.result == 'success' }}", 'runs-on': 'ubuntu-latest',
        'timeout-minutes': minutes, 'strategy': {'fail-fast': False, 'max-parallel': parallel,
            'matrix': '${{ fromJSON(needs.plan.outputs.cases) }}'}, 'steps': steps})


workflow = dict(name='V3 prospective comparison v2', on={'workflow_dispatch': {'inputs': {
    'mode': {'description': 'Full-duration development preflight or admitted independent main',
        'type': 'choice', 'options': ['preflight', 'main'], 'default': 'preflight', 'required': True}}}},
    permissions={'contents': 'read', 'actions': 'read'}, jobs={})
jobs = workflow['jobs']
jobs['plan'] = {'runs-on': 'ubuntu-latest', 'timeout-minutes': 10,
    'outputs': {'cases': '${{ steps.matrix.outputs.cases }}', 'profiles': '${{ steps.matrix.outputs.profiles }}'},
    'steps': setup()+[run('Validate planned identities and main admission',
        f'python -m telemetry_availability.v3_comparison_orchestration_v1 --config configs/v3_comparison_design_v2.json matrix --mode {MODE}', id='matrix')]}

acquire = setup()+[dict(uses='actions/checkout@v7', **{'if': f"${{{{ matrix.profile != '{PET}' }}}}", 'with': {
    'repository': '${{ matrix.repository }}', 'ref': '${{ matrix.commit }}', 'path': 'upstream', 'persist-credentials': False}}),
    run('Restore the exact qualified Petclinic image', 'python scripts/restore_petclinic_image.py',
        **{'if': f"${{{{ matrix.profile == '{PET}' }}}}", 'env': {'GH_TOKEN': '${{ github.token }}'}}),
    run('Render and pin existing application deployment', '''out=workflow-results/acquisition
mkdir -p "$out"
if [[ '${{ matrix.profile }}' == 'opentelemetry_demo' ]]; then
  export OTEL_COLLECTOR_CONFIG_EXTRAS="$GITHUB_WORKSPACE/configs/live/otel-pilot-collector-extra.yml"
  docker compose --env-file upstream/.env -f 'upstream/${{ matrix.compose_file }}' config --format json > "$out/rendered-compose.json"
  telemetry_args=(--telemetry-output-directory "$GITHUB_WORKSPACE/$out")
else
  docker compose -f 'upstream/${{ matrix.compose_file }}' config --format json > "$out/rendered-compose.json"
  telemetry_args=()
fi
python -m telemetry_availability pin-live-compose --config configs/m7_runtime_pilot.yaml --profile '${{ matrix.profile }}' --input "$out/rendered-compose.json" --out "$out/base-pinned-compose.json" --audit "$out/base-image-lock-audit.json" "${telemetry_args[@]}"
python -m telemetry_availability prepare-placement-compose --config configs/m7b_placement_pilot.yaml --profile '${{ matrix.profile }}' --placement '${{ matrix.placement }}' --input "$out/base-pinned-compose.json" --base-audit "$out/base-image-lock-audit.json" --out "$out/pinned-compose.json" --audit "$out/image-lock-audit.json" --haproxy "$out/haproxy.cfg"
/usr/bin/time -v -o "$out/pull-resource-usage.txt" docker compose -f "$out/pinned-compose.json" pull
/usr/bin/time -v -o "$out/start-resource-usage.txt" docker compose -f "$out/pinned-compose.json" up -d --no-build --wait --wait-timeout 360''',
        **{'if': f"${{{{ matrix.profile != '{PET}' }}}}", 'env': {'DEMO_VERSION': '3.0.0', 'LOCUST_AUTOSTART': 'false',
            'LOCUST_HEADLESS': 'true', 'LOCUST_BROWSER_TRAFFIC_ENABLED': 'false'}}),
    run('Acquire all attempts and seal physically separate observation roles',
        'mkdir -p workflow-results/acquisition\n/usr/bin/time -v -o workflow-results/acquisition/acquisition-resource-usage.txt '
        'python -m telemetry_availability.v3_comparison_acquisition_v1 --config configs/v3_comparison_design_v2.json --profile "${{ matrix.profile }}" '
        '--placement "${{ matrix.placement }}" --law "${{ matrix.law }}" --repetition "${{ matrix.repetition }}" '
        f'--mode {MODE} --out workflow-results/acquisition'),
    run('Extract compact acquisition CPU wall and memory records',
        'python scripts/report_v3_comparison_costs_v1.py --root workflow-results/acquisition --out workflow-results/acquisition/resource-summary.json',
        **{'if': '${{ always() }}'})]
for label, directory in (('raw', ''), ('ordinary', '/roles/ordinary'), ('pmx-input', '/roles/pmx'),
                         ('closed-evaluator', '/roles/evaluator'), ('receipt', '/public')):
    acquire.append(upload('v3-comparison-'+label+'-'+KEY, 'workflow-results/acquisition'+directory))
jobs['acquire'] = matrix_job(['plan'], acquire, 90)

graph = setup()+[download('v3-comparison-ordinary-'+KEY, 'workflow-input/ordinary'),
    run('Build all graph variants and B0 without evaluator inputs',
        'mkdir -p workflow-results/graph/compact\n/usr/bin/time -v -o workflow-results/graph/compact/build-resource-usage.txt '
        'python -m telemetry_availability.v3_comparison_candidates_v1 build --input workflow-input/ordinary '
        '--output workflow-results/graph --config configs/v3_comparison_execution_v2.json'),
    run('Reproduce all saved-model probabilities in a fresh restricted process',
        '/usr/bin/time -v -o workflow-results/graph/compact/replay-resource-usage.txt '
        'python -m telemetry_availability.v3_comparison_candidates_v1 replay --input workflow-results/graph/candidates '
        '--output workflow-results/graph/compact --config configs/v3_comparison_execution_v2.json'),
    run('Extract compact graph process resource measurements',
        'python scripts/report_v3_comparison_costs_v1.py --root workflow-results/graph/compact --out workflow-results/graph/compact/resource-summary.json',
        **{'if': '${{ always() }}'}),
    upload('v3-comparison-graph-'+KEY, 'workflow-results/graph'),
    upload('v3-comparison-graph-compact-'+KEY, 'workflow-results/graph/compact')]
jobs['graph'] = matrix_job(['plan', 'acquire'], graph, 20)

def pmx_setup():
    return setup()+[dict(uses='actions/setup-java@v5', **{'with': {'distribution': 'temurin', 'java-version': '11'}}),
        run('Obtain exact author PMX binary and source options', '''mkdir -p workflow-input
curl --fail --location --retry 8 --retry-all-errors "$AUTHOR_BASE/main.jar" --output workflow-input/main.jar
curl --fail --location --retry 8 --retry-all-errors "$AUTHOR_BASE/Options.txt" --output workflow-input/Options.txt''',
            env={'AUTHOR_BASE': 'https://se-gitlab-extern.fzi.de/SebastianWeberFZI/ableitung-von-leistungsmodellen-in-ci/-/raw/9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2'})]

pmx_command = ('python -m telemetry_availability.v3_comparison_pmx_v2 {mode} --source workflow-input/pmx-native '
    '--out workflow-results/extraction --config configs/v3_comparison_execution_v2.json '
    '--options workflow-input/Options.txt --jar workflow-input/main.jar')
jobs['pmx'] = matrix_job(['plan', 'acquire'], pmx_setup()+[
    download('v3-comparison-pmx-input-'+KEY, 'workflow-input/pmx-native'),
    run('Independently project, extract and audit complete native operation models',
        'mkdir -p workflow-results/extraction\n/usr/bin/time -v -o workflow-results/extraction/process-resource-usage.txt '+pmx_command.format(mode='extract')),
    upload('v3-comparison-pmx-extraction-'+KEY, 'workflow-results/extraction')], 150)
jobs['pmx_controls'] = {'needs': 'plan', 'runs-on': 'ubuntu-latest', 'timeout-minutes': 150,
    'steps': pmx_setup()+[run('Reconstruct four known-probability context and database cases', pmx_command.format(mode='controls')),
        upload('v3-comparison-pmx-extraction-controls', 'workflow-results/extraction')]}

# The exact previously qualified Palladio source/target/build/harness route is
# reused. Only artifact routing, collection and result freeze become prospective.
old = yaml.safe_load(Path('.github/workflows/petclinic-pmx-qualification.yml').read_text())
solver = deepcopy(old['jobs']['palladio_solver'])
solver.update(name='Solve independent PMX models and known controls twice', needs=['plan', 'pmx', 'pmx_controls'],
    strategy={'fail-fast': False, 'matrix': {'profile': '${{ fromJSON(needs.plan.outputs.profiles) }}'}})
solver['if'] = "${{ always() && needs.plan.result == 'success' }}"
steps = []
for step in solver['steps']:
    if step.get('name') == 'Download the retained artificial PCM contract':
        steps.extend([download('v3-comparison-pmx-extraction-'+PROFILE+'--*', 'workflow-input/extractions', True),
            download('v3-comparison-pmx-extraction-controls', 'workflow-input/extractions/controls'),
            run('Census independently extracted models for this application',
                f'python -m telemetry_availability.v3_comparison_pmx_v2 collect --source workflow-input/extractions --profile "{PROFILE}" --out workflow-input/petclinic-pmx-contract')])
    elif step.get('name') == 'Retain raw untuned solver output and timing':
        steps.append(upload('v3-comparison-pmx-solver-'+PROFILE, 'workflow-results/petclinic-pmx-solver'))
    else:
        steps.append(step)
steps.extend([run('Freeze every independent PMX forecast or absence after known-probability controls',
    'python -m telemetry_availability.v3_comparison_pmx_v2 freeze --source workflow-input/petclinic-pmx-contract '
    '--solver workflow-results/petclinic-pmx-solver --out workflow-results/pmx-candidates', **{'if': '${{ always() }}'}),
    upload('v3-comparison-pmx-candidates-'+PROFILE, 'workflow-results/pmx-candidates'),
    upload('v3-comparison-pmx-solver-contract-'+PROFILE, 'workflow-input/petclinic-pmx-contract')])
solver['steps'] = steps
jobs['palladio_solver'] = solver

freeze = setup()+[download('v3-comparison-receipt-'+KEY, 'workflow-input/receipt'),
    download('v3-comparison-graph-'+KEY, 'workflow-input/graph'),
    download('v3-comparison-pmx-candidates-'+PROFILE, 'workflow-input/pmx'),
    run('Seal all ten-method slots before any evaluator download',
        f'python -m telemetry_availability.v3_comparison_orchestration_v1 --config configs/v3_comparison_design_v2.json freeze --mode {MODE} --key "{KEY}" --source workflow-input --out workflow-results/frozen'),
    upload('v3-comparison-frozen-'+KEY, 'workflow-results/frozen')]
# Failed downloads must not suppress the explicit missing-builder census.
for step in freeze:
    if step.get('uses') == 'actions/download-artifact@v8':
        step['continue-on-error'] = True
jobs['freeze'] = matrix_job(['plan', 'graph', 'palladio_solver'], freeze, 15)

evaluation = setup()+[download('v3-comparison-frozen-'+KEY, 'workflow-input/frozen'),
    run('Require a complete frozen candidate role before downloading closed outcomes',
        "python - <<'PY'\nfrom pathlib import Path\nfrom telemetry_availability.v3_comparison_roles_v1 import load_role, digest\n"
        "documents, seal = load_role(Path('workflow-input/frozen/frozen'), 'frozen_candidates')\n"
        "assert digest(documents['candidates.json']) == documents['receipt.json']['candidate_digest']\nPY"),
    download('v3-comparison-closed-evaluator-'+KEY, 'workflow-input/evaluator'),
    run('Open exact sealed evaluator and score immutable forecasts',
        f'python -m telemetry_availability.v3_comparison_orchestration_v1 --config configs/v3_comparison_design_v2.json evaluate --mode {MODE} --key "{KEY}" '
        '--source workflow-input/frozen/frozen --evaluator workflow-input/evaluator --out workflow-results/evaluation'),
    upload('v3-comparison-evaluation-'+KEY, 'workflow-results/evaluation')]
jobs['evaluate'] = matrix_job(['plan', 'freeze'], evaluation, 15)
jobs['analysis'] = {'needs': ['plan', 'evaluate'], 'if': "${{ always() && needs.plan.result == 'success' }}",
    'runs-on': 'ubuntu-latest', 'timeout-minutes': 30, 'steps': setup()+[
        download('v3-comparison-evaluation-*', 'workflow-input/evaluations', True),
        download('v3-comparison-frozen-*', 'workflow-input/frozen', True),
        run('Reconcile every planned identity, primary/stable/transfer coverage and costs',
            f'python -m telemetry_availability.v3_comparison_orchestration_v1 --config configs/v3_comparison_design_v2.json summarize --mode {MODE} --source workflow-input --out workflow-results/comparison'),
        upload('v3-comparison-compact', 'workflow-results/comparison')]}


class Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def represent_string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)


Dumper.add_representer(str, represent_string)
Path('.github/workflows/v3-prospective-comparison-v2.yml').write_bytes(
    yaml.dump(workflow, Dumper=Dumper, sort_keys=False, allow_unicode=True, width=120).encode())
