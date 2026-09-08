"""Read only author's compact CSV and three scalar summaries per ICSE job."""
import argparse
from collections import defaultdict
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import statistics

OUT = Path('docs/evidence/original-icse-local-aggregate')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2)+'\n').encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    original_csv = (args.source/'results.csv').read_bytes()
    assert len(original_csv) < 100000
    rows = list(csv.DictReader(io.StringIO(original_csv.decode('utf-8-sig'))))
    assert len(rows) == 250
    expected = {(mode, p, seed) for mode in ('norepl','repl') for p in (.1,.3,.5,.7,.9) for seed in range(1,26)}
    assert {(r['mode'],float(r['p_fail']),int(r['seed'])) for r in rows} == expected
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'results.csv').write_bytes(original_csv)
    records, hashes, errors = [], [], []
    groups = defaultdict(list)
    for row in rows:
        mode, p, seed = row['mode'], float(row['p_fail']), int(row['seed'])
        name = f'{mode}-{p:.1f}-seed{seed}'
        assert row['dirname'] == name
        directory = args.source/'gh_results'/name
        names = {f'R_avg_{"base" if mode=="norepl" else "repl"}.json', 'summary.json',f'summary_{mode}.json'}
        assert {f.name for f in directory.iterdir()} == names
        values = {}
        for filename in sorted(names):
            data = (directory/filename).read_bytes()
            assert len(data) < 5000
            obj = json.loads(data)
            if filename.startswith('R_avg'):
                assert set(obj) == {'R_avg','R_ep','samples','p_fail','seed'}
                assert set(obj['R_ep']) == {'home-timeline','user-timeline','compose-post'}
                assert all(isinstance(x,(int,float)) for x in obj['R_ep'].values())
            else:
                assert all(isinstance(x,(int,float)) for x in obj.values())
            values[filename] = obj
            target = OUT/'scalar-summaries'/name/filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            hashes.append({'path':f'gh_results/{name}/{filename}','bytes':len(data),'sha256':sha256(data).hexdigest()})
        model = values[f'R_avg_{"base" if mode=="norepl" else "repl"}.json']
        live = values['summary.json']
        both = values[f'summary_{mode}.json']
        assert model['p_fail'] == p and model['seed'] == seed
        assert model['samples'] == int(row['samples']) == 500000
        assert live['rounds'] == int(row['rounds']) == 450
        assert model['R_avg'] == float(row['R_avg']) == float(row['R_model']) == both[f'R_model_{mode}']
        assert live['R_live'] == float(row['R_live']) == both[f'R_live_{mode}']
        for ep,value in model['R_ep'].items():
            assert value == float(row['R_ep_'+ep.replace('-','_')])
        error = model['R_avg']-live['R_live']
        assert abs(error-float(row['error'])) < 1e-12
        relative = 100*error/live['R_live'] if live['R_live'] else None
        if relative is not None:
            assert abs(relative-float(row['error_pct'])) < 1e-10
        else:
            assert row['error_pct'] == ''
        item = {'mode':mode,'p_fail':p,'seed':seed,'model':model['R_avg'],'live':live['R_live'],
                'signed_error_pp':100*error,'relative_error_pct':relative}
        records.append(item)
        groups[(mode,p)].append(item)
    table = []
    for (mode,p), items in sorted(groups.items()):
        valid = [r['relative_error_pct'] for r in items if r['relative_error_pct'] is not None]
        table.append({'mode':mode,'p_fail':p,'jobs':len(items),
            'model_mean':statistics.mean(r['model'] for r in items),
            'model_sample_sd':statistics.stdev(r['model'] for r in items),
            'live_mean':statistics.mean(r['live'] for r in items),
            'live_sample_sd':statistics.stdev(r['live'] for r in items),
            'mean_signed_error_pp':statistics.mean(r['signed_error_pp'] for r in items),
            'mean_absolute_error_pp':statistics.mean(abs(r['signed_error_pp']) for r in items),
            'median_relative_error_pct':statistics.median(valid) if valid else None,
            'relative_error_defined_jobs':len(valid)})
    save(OUT/'scalar-member-hashes.json',hashes)
    save(OUT/'aggregate-audit.json',{'version':'original-icse-local-aggregate-v1',
        'source_relative':'DONE/Model Discovery and Graph Simulation A Lightweight Gateway to Chaos Engineering',
        'csv_bytes':len(original_csv),'csv_sha256':sha256(original_csv).hexdigest(),
        'jobs':len(records),'scalar_files':len(hashes),'scalar_bytes':sum(r['bytes'] for r in hashes),
        'reported_total_windows':250*450,'new_independent_campaigns':0,'main_campaigns':0,
        'scope':'Exact local CSV versus scalar files; live probe/window denominator reproduction unavailable',
        'provenance_limit':'Original 250-job run/ZIP digest identity not established. Retained run20410544665 has only20 jobs and is excluded as source of these250 jobs.',
        'table':table,'job_census':records})
    (OUT/'.gitattributes').write_bytes(b'* -text whitespace=-trailing-space,-space-before-tab,cr-at-eol\n')
    print(json.dumps({'jobs':len(records),'files':len(hashes),'table':table},indent=2))


if __name__ == '__main__':
    main()
