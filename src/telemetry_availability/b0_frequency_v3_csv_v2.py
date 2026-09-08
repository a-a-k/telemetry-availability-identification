"""B0-v3: raw calibration S/N, with a minimal enforced input boundary."""
from collections import Counter
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from .v3_primary_projection import VERSION, FILES, REQUEST_FIELDS, write
from .v3_graph_input_inventory import ReadBoundary

METHOD='B0-v3-raw-calibration-frequency-csv-v2'


def decode_outcome(value):
    if type(value) is bool:
        return value
    if isinstance(value,str) and value.lower() in ('true','false'):
        return value.lower()=='true'
    raise ValueError('Outcome must be Boolean or explicit CSV true/false token: '+repr(value))


def identify(requests, operations):
    assert operations and len(operations)==len(set(operations))
    ids=set();attempts=Counter();successes=Counter();timeouts=Counter()
    for row in requests:
        assert set(row)==set(REQUEST_FIELDS), 'Only the declared ordinary request contract is accepted'
        assert row['period']=='calibration', 'Baseline and test outcomes are not calibration input'
        assert row['operation'] in operations
        assert isinstance(row['request_id'],str) and row['request_id'] and row['request_id'] not in ids
        ids.add(row['request_id'])
        success=decode_outcome(row['semantic_success']);timed_out=decode_outcome(row['timed_out'])
        assert not (success and timed_out)
        operation=row['operation'];attempts[operation]+=1
        successes[operation]+=success;timeouts[operation]+=timed_out
    forecasts={}
    for operation in operations:
        n,s=attempts[operation],successes[operation]
        forecasts[operation]={'status':'ok' if n else 'unsupported','probability':s/n if n else None,
            'reason':None if n else 'no_calibration_attempts','attempts':n,'successes':s,
            'timeouts':timeouts[operation],'exact_fraction':f'{s}/{n}' if n else None}
    return {'version':METHOD,'forecasts':forecasts,'external_attempts':len(ids),
            'smoothing':False,'stable_window_filter':False,'health_or_native_inputs_used':False,
            'scope':'Calibration empirical frequency of the full declared business event; no physical parameter identification'}


def fit(root, operations):
    seal=json.loads((root/'seal.json').read_bytes())
    assert seal['version']==VERSION and set(seal['files'])==set(FILES)
    data=(root/'requests.json').read_bytes()
    assert sha256(data).hexdigest()==seal['files']['requests.json']
    model=identify(json.loads(data),operations)
    model['requests_sha256']=sha256(data).hexdigest()
    model['requests_bytes']=len(data)
    return model


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true','Application B0 fitting is remote only'
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--operations',nargs='+',required=True)
    args=parser.parse_args();root=args.input.resolve();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    boundary=ReadBoundary(root,out)
    boundary.allowed={root/'seal.json',root/'requests.json'}
    started=time.perf_counter();sys.addaudithook(boundary.hook)
    try:
        model=fit(root,args.operations)
    finally:
        boundary.active=False
    model['identification_seconds']=time.perf_counter()-started
    write(out/'b0-model.json',model)
    write(out/'consumer-read-audit.json',{'actual_data_reads':sorted(boundary.reads),'blocked':boundary.blocked,
        'data_files_received':sorted(p.name for p in boundary.allowed),'method':METHOD,
        'boundary_covers_seal_loading_and_identification':True})
    assert boundary.reads=={str(p) for p in boundary.allowed} and not boundary.blocked


if __name__=='__main__':main()
