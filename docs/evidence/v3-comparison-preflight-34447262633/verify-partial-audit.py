"""Diagnose the qualified subchain without promoting the three known failed gates."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_v3_preflight_compact_v2 as strict
root=Path(__file__).resolve().parent
expected=Counter({'remote preflight gate not qualified':1,'unresolved technical forecast failure: PMX':1,'unresolved technical forecast failure: PMX_inclusive':1})
seen=Counter();passed=[0];original=strict.require
def diagnose(condition,reason):
 if condition:passed[0]+=1;return
 if expected[reason]>seen[reason]:seen[reason]+=1;return
 raise ValueError('Unexpected additional audit failure: '+reason)
strict.require=diagnose
try:result=strict.audit(root,34447262633,'e89e7ca91dd474d8cf2b8c4ed7c1ffc052d98569')
finally:strict.require=original
assert seen==expected
result.update(version='v3-preflight-v2-qualified-subchain-diagnostic',qualified=False,
 full_strict_audit_passed=False,main_admission_created=False,
 recorded_failed_checks=dict(seen),other_strict_checks_passed=passed[0],
 source_auditor_sha256=sha256((ROOT/'scripts/audit_v3_preflight_compact_v2.py').read_bytes()).hexdigest(),
 scope='All original strict checks executed. Exactly the declared aggregate availability gate and the two failed PMX statuses are retained as failures; every other check passed. This report cannot admit main.')
assert json.loads((root/'partial-pipeline-audit.json').read_bytes())==result
print('Verified the preserved negative audit and1293other checks; main remains unqualified')
