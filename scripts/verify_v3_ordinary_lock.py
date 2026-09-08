import hashlib
import json
from pathlib import Path

config=json.loads(Path('configs/v3_ordinary_input_qualification.json').read_text())
assert config['main_campaigns']==0 and config['model_fits']==0
for path,digest in config['locked_files'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest,path
print('V3 ordinary input source lock verified')
