"""Verify a research lock against exact Git index bytes before commit/dispatch."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('config',type=Path)
args=parser.parse_args()
config=json.loads(args.config.read_text())
for item in config['repository_locks']:
    data=subprocess.check_output(['git','show',':'+item['path']])
    assert sha256(data).hexdigest()==item['sha256'], item['path']
print(f"Verified {len(config['repository_locks'])} exact staged repository locks")
