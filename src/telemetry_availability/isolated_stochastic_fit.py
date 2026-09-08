"""Calibration-only original finite-state likelihood; no outcome regression.

The entry point is remote-only. Bounded loader/health controls can run locally.
No acquisition config, injection schedule or evaluator object is loaded here.
"""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

from .live_validation_analysis import (HealthTick, QualifiedCell, RequestRecord,
    _bool, _timestamp, prepare_mode, fit_exact_model, predict_cell)
from .live_validation_config import LiveAnalysisConfig, LiveObservationMode, LiveOperationSpec

ROOT = Path(__file__).resolve().parents[2]
LEARNER_FILES = frozenset({'learner/requests.csv', 'learner/health.csv',
    'learner/deployment.json', 'learner/topology-edges.csv', 'learner/manifest.json',
    'audit/boundary.json', 'native/calibration-native.json'})


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')


def verify_learner_bundle(directory):
    """Enforce the physical role boundary before reading any observation file."""
    directory=directory.resolve()
    actual=set()
    for path in directory.rglob('*'):
        if path.is_symlink():
            raise ValueError('symlink in sealed learner input')
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != LEARNER_FILES | {'seal.json'}:
        raise ValueError('learner bundle has missing or unexpected files: '+str(sorted(actual ^ (LEARNER_FILES|{'seal.json'}))))
    seal=read(directory/'seal.json')
    if set(seal['files']) != LEARNER_FILES:
        raise ValueError('learner seal file set differs')
    for relative,expected in seal['files'].items():
        if digest(directory/relative) != expected:
            raise ValueError('learner input digest differs: '+relative)
    return seal


def health_signal(row, replica, success_checks):
    """Decode the declared proxy health type without changing native observations."""
    if tuple(success_checks) not in (('', 'L4OK'), ('L7OK',)):
        raise ValueError('unsupported declared backend check contract')
    prefix=f'replica_{replica}_'
    if not _bool(row[prefix+'observed']):
        raise ValueError('qualified tick lacks replica observation')
    instance=int(_bool(row[prefix+'running']) and not _bool(row[prefix+'paused']))
    backend=str(row[prefix+'backend_status']).upper()
    check=str(row[prefix+'backend_check_status']).upper()
    if backend == 'UP' and check in ('L4OK','L7OK') and check not in success_checks:
        raise ValueError('observed backend check type differs from deployment declaration')
    path=int(instance and int(float(row[prefix+'network_count']))>0 and backend=='UP' and check in success_checks)
    return instance,path


def load_analysis(path):
    config=read(path)
    config['modes']=tuple(LiveObservationMode(**item) for item in config['modes'])
    config['methods']=tuple(config['methods'])
    config['operations']={key:tuple(LiveOperationSpec(**item) for item in value) for key,value in config['operations'].items()}
    return LiveAnalysisConfig(**config)


def load_cell(directory):
    manifest=read(directory/'learner/manifest.json')
    boundary=read(directory/'audit/boundary.json')
    deployment=read(directory/'learner/deployment.json')
    if boundary.get('usable') is not True or manifest.get('usable') is not True:
        raise ValueError('acquisition qualification failed; no model fit permitted')
    requests=[]
    for row in rows(directory/'learner/requests.csv'):
        if row['period'] not in ('baseline','calibration'):
            raise ValueError('non-learner request period')
        requests.append(RequestRecord(period=row['period'],request_id=row['request_id'],operation=row['operation'],
            at=_timestamp(row['started_at']),success=int(_bool(row['semantic_success'])),
            trace_present=_bool(row['trace_present']),span_count=int(row['span_count']),
            services=frozenset(filter(None,row['services'].split(';'))),
            target_replicas=frozenset(filter(None,row['target_replicas'].split(';')))))
    if len({r.request_id for r in requests})!=len(requests):
        raise ValueError('duplicate external learner request ID')
    checks=deployment.get('backend_success_check_statuses',['','L4OK'])
    if manifest['profile']=='spring_petclinic_microservices' and checks!=['L7OK']:
        raise ValueError('Petclinic requires its qualified HTTP health declaration')
    ticks=[]
    for row in rows(directory/'learner/health.csv'):
        if row.get('period','calibration')!='calibration':
            raise ValueError('non-calibration health tick')
        ha,pa=health_signal(row,'a',checks)
        hb,pb=health_signal(row,'b',checks)
        ticks.append(HealthTick(at=_timestamp(row['observed_at']),elapsed_seconds=float(row['elapsed_seconds']),signals=(ha,hb,pa,pb)))
    return QualifiedCell(profile=manifest['profile'],placement=manifest['placement'],failure_law=manifest['failure_law'],
        repetition=int(manifest['repetition']),target_service=deployment['target_service'],learner_requests=tuple(requests),
        health=tuple(sorted(ticks,key=lambda t:t.at)),test_requests=(),test_health=(),boundary=boundary,directory=directory)


class ReadAudit:
    """Block undeclared data reads/network/subprocesses in the fit process itself."""
    def __init__(self, directory, settings, output):
        self.directory=directory.resolve();self.settings=settings.resolve();self.output=output.resolve()
        self.read_paths=set();self.blocked=[];self.active=True

    def __call__(self,event,args):
        if not self.active:
            return
        if event in ('subprocess.Popen','os.system','socket.connect','socket.getaddrinfo'):
            self.blocked.append(event)
            raise PermissionError('fit process cannot launch processes or access network')
        if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):
            return
        path=Path(os.fsdecode(args[0])).resolve()
        mode=args[1] or ''
        flags=args[2] if len(args)>2 else 0
        reading=('r' in mode or '+' in mode or (not mode and not(flags & os.O_WRONLY)))
        if not reading:
            return
        self.read_paths.add(str(path))
        if path.is_relative_to(self.directory):
            allowed=path.relative_to(self.directory).as_posix() in LEARNER_FILES|{'seal.json'}
        elif path==self.settings:
            allowed=True
        elif path.is_relative_to(ROOT/'src') or path.is_relative_to(Path(sys.prefix)):
            allowed=path.suffix in ('.py','.pyc','.pyd','.so','.dll')
        else:
            allowed=path in (Path('/dev/null'),Path('/proc/cpuinfo'))
        if not allowed:
            self.blocked.append(str(path))
            raise PermissionError('undeclared data read during fit: '+str(path))


def fit(directory, settings, output):
    assert os.environ.get('GITHUB_ACTIONS')=='true','Full data fits belong to GitHub Actions'
    audit=ReadAudit(directory,settings,output)
    sys.addaudithook(audit)
    started=time.perf_counter()
    try:
        seal=verify_learner_bundle(directory)
        analysis=load_analysis(settings)
        cell=load_cell(directory)
        predictions=[];diagnostics=[];representations=[]
        deployment=read(directory/'learner/deployment.json')
        for mode in analysis.modes:
            tick=time.perf_counter()
            prepared=prepare_mode(cell,mode,analysis)
            estimate=fit_exact_model(cell,prepared,analysis)
            scopes=['current']+(['transfer'] if cell.placement==analysis.source_placement else [])
            for scope in scopes:
                predictions.extend(predict_cell(cell,prepared,estimate,analysis,scope))
            diagnostics.append(dict(mode=mode.id,seconds=time.perf_counter()-tick,status=estimate.status,
                current_identified=estimate.current_identified,transfer_identified=estimate.transfer_identified,
                parameter_names=estimate.parameter_names,rank=estimate.rank,dimension=estimate.dimension,
                current_prediction_range=estimate.current_prediction_range,transfer_prediction_range=estimate.transfer_prediction_range,
                retained_traces=prepared.retained_traces,unaligned=prepared.unaligned_calibration,
                guarded=prepared.guarded_calibration,health_contradictions=prepared.health_signal_contradictions))
            representations.append(dict(mode=mode.id,q_by_operation=prepared.q_by_operation,
                topology={key:asdict(value) for key,value in prepared.topology.items()},
                declared_dependency_graph=deployment.get('source_declared_dependencies',{}),
                known_non_target_dependencies=deployment.get('known_non_target_dependencies',[]),
                implementation='Fixed two-path original stochastic specialization; non-target dependencies are jointly absorbed in baseline q, not individually estimated.',
                limitations=['No typed general-graph solver','No explicit failover/retry/deadline/circuit-breaker dynamics',
                    'Scalar baseline residual assumes independence from target route',
                    'Split transfer assumes independent new logical domain with same estimated marginal g']))
        write(output/'predictions.json',dict(scope='technical_interface_qualification',source=seal['metadata'],
            analysis_sha256=digest(settings),predictions=predictions))
        write(output/'fit-diagnostics.json',dict(seconds=time.perf_counter()-started,modes=diagnostics))
        write(output/'model-representation.json',representations)
        assert not cell.test_requests and not cell.test_health
    finally:
        audit.active=False
        write(output/'fit-read-audit.json',dict(read_paths=sorted(audit.read_paths),blocked=audit.blocked,
            evaluator_reads=0,target_calibration_reads=0,injection_schedule_reads=0,
            enforcement='Physical single learner bundle + process open/network/subprocess audit during verification, loading, preparation and fitting',
            estimator_sources=['live_validation_analysis.py','isolated_stochastic_fit.py']))
    files={p.relative_to(output).as_posix():digest(p) for p in output.rglob('*') if p.is_file() and p.name!='seal.json'}
    write(output/'seal.json',dict(metadata=seal['metadata'],files=files))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--learner',type=Path,required=True)
    parser.add_argument('--analysis',type=Path,default=ROOT/'configs/isolated_stochastic_analysis.json')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    fit(args.learner.resolve(),args.analysis.resolve(),args.out.resolve())


if __name__=='__main__':
    main()
