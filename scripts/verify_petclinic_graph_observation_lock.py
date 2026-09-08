import hashlib
import json
from pathlib import Path

config=json.loads(Path('configs/petclinic_graph_observation_technical.json').read_text())
assert config['main_campaigns']==0 and config['scope']=='retained_development_technical'
for path,digest in config['locked_files'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
print('Petclinic graph observation technical source lock verified')
