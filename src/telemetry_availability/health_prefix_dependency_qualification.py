"""Qualify a decoder correction by unchanged-input scope, preserving failed replay."""
from collections import Counter
from pathlib import Path

from .health_prefix_reanalysis import pkey, finite
from .isolated_stochastic_fit import read, digest


def qualify(root, historical, census, tolerance=1e-6):
    previous={pkey(row):row for row in historical}
    assert len(previous)==len(historical)==17856
    source_audit={tuple(str(row[k]) for k in ('profile','placement','failure_law','repetition')):row
                  for row in census['records'] if row['period']=='calibration'}
    assert len(source_audit)==168
    accepted=[];decisions=[];counts=Counter();mismatches=[];seals=[]
    for path in sorted(root.rglob('seal.json')):
        seal=read(path);seals.append(seal)
        for item in seal['records']:
            member=path.parent/item['path'];assert digest(member)==item['sha256']
            record=read(member)
            cid=tuple(str(record['identity'][k]) for k in ('profile','placement','failure_law','repetition'))
            audit=source_audit[cid]
            assert record['changed_health_ticks']==audit['changed_ticks']
            assert record['source_seal']['files']['learner/health.csv']==audit['source_sha256']
            assert not record['read_audit']['blocked']
            old={pkey(row):row for row in record['versions']['legacy']}
            new={pkey(row):row for row in record['versions']['prefix_corrected']}
            assert set(old)==set(new)
            for key,row in sorted(old.items()):
                reference=previous[key];corrected=new[key]
                reason=('unchanged_health_file_decoding' if record['changed_health_ticks']==0 else
                        'health_policy_none' if row['mode']=='trace_only' else 'affected_refit')
                error=abs(float(row['prediction'])-float(reference['prediction'])) if finite(row['prediction']) and finite(reference['prediction']) else None
                same_status=row['status']==reference['status']
                same_presence=finite(row['prediction'])==finite(reference['prediction'])
                reproduced=same_status and same_presence and (error is None or error<=tolerance)
                if not reproduced:mismatches.append(dict(identity=key,reason=reason,error=error,status=row['status']))
                if reason!='affected_refit':
                    # Assert every output field, not merely rounded probabilities.
                    assert row==corrected, (key,reason)
                    accepted.append(dict(reference))
                else:
                    assert reproduced, (key,error)
                    accepted.append(dict(corrected))
                counts[reason]+=1
                decisions.append(dict(identity=key,policy=reason,legacy_reproduced=reproduced,legacy_error=error))
    assert len(seals)==3 and len(accepted)==17856 and len({pkey(row) for row in accepted})==17856
    assert all(row['reason']!='affected_refit' for row in mismatches)
    return accepted,dict(qualified_for_decoder_correction=True,strict_legacy_replay_qualified=not mismatches,
            retained_strict_replay_mismatches=mismatches,counts=dict(counts),decisions=decisions,
            rule='carry exact historical rows for every provably unaffected input; retain refits only where decoder inputs changed',
            probability_tolerance=tolerance,threshold_relaxed=False,model_refits_added=0,new_independent_campaigns=0)
