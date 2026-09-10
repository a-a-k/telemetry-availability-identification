"""Remote-only compact resource extraction; no native/learner/test parsing."""
import argparse
import os
from pathlib import Path
from telemetry_availability.v3_resource_summary_v1 import summarize
from telemetry_availability.v3_primary_projection import read, write

assert os.environ.get('GITHUB_ACTIONS') == 'true'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
result = summarize(args.root)
write(args.out, result)
public = args.root/'public/costs.json'
if public.is_file():
    costs = read(public); costs['process_resources'] = result; write(public, costs)
