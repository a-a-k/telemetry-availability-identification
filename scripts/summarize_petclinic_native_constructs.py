"""Remote calibration-only source inventory for the independent PMX interface."""
from collections import Counter, defaultdict
import os
from pathlib import Path

from telemetry_availability.isolated_stochastic_fit import read, rows, write


def main():
    assert os.environ.get('GITHUB_ACTIONS')=='true'
    root=Path('workflow-input/learner')
    native=read(root/'native/calibration-native.json')
    assert native['calibration_only'] is True
    requests=[r for r in rows(root/'learner/requests.csv') if r['period']=='calibration']
    assert set(native['selected_trace_ids'])=={r['trace_id'] for r in requests}
    counts=Counter();examples={};by_operation=defaultdict(Counter)
    for row in requests:
        for span in native['spans'].get(row['trace_id'],[]):
            attrs=span['attributes']
            database={k:v for k,v in attrs.items() if k.startswith(('db.','server.','net.peer.','peer.'))}
            key=(span['service'],span['native_kind'],span['operation'],str(database.get('db.system.name',database.get('db.system',''))))
            counts[key]+=1;by_operation[row['operation']][key]+=1
            if database and key not in examples:
                examples[key]=dict(attributes=database,resource_attributes=span['resource_attributes'],server=span['server'])
    write(Path('workflow-results/native-constructs.json'),dict(calibration_requests=len(requests),
        source=read(root/'learner/manifest.json'),calibration_only=True,
        constructs=[dict(service=k[0],kind=k[1],operation=k[2],db_system=k[3],spans=v,
            operations={op:c[k] for op,c in by_operation.items() if c[k]},example=examples.get(k)) for k,v in sorted(counts.items())]))


if __name__=='__main__':
    main()
