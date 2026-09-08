# Complete historical HAProxy prefix census

[Run 34217614608](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34217614608), head `92f0cdb49ef31c1efe6aebb28b350e100f7e4391`, passed the complete census: 168 campaign identities, 328 health files. All nine archive identities, actual sizes/SHA256 and ZIP CRCs were verified remotely. Every read health member has a recorded exact digest; Petclinic learner seals also passed.

| Scope | Campaigns | Health ticks | Changed ticks | Changed replica observations | Affected campaigns |
| --- | --- | --- | --- | --- | --- |
| M7 calibration | 160 | 144027 | 484 | 484 | 119 |
| M7 test-health | 160 | 144035 | 537 | 547 | 117 |
| Petclinic calibration | 8 | 7208 | 97 | 99 | 8 |

M7 changes occur in 66 DeathStar and 53 OTel calibration campaigns, and 60 DeathStar and 57 OTel test-health campaigns. The union is **143/160** M7 campaigns with a change in either period. The other 17 have identical decoded input for this correction; this does not certify their broader adequacy. The test-health changes can affect stable-window selection even where calibration is unchanged.

| Petclinic placement/law | Changed ticks | Changed observations a / b |
| --- | --- | --- |
| colocated N | 7 | 4 / 4 |
| colocated NC | 14 | 7 / 8 |
| colocated ND | 4 | 1 / 3 |
| colocated NCD | 20 | 12 / 8 |
| split N | 9 | 4 / 5 |
| split NC | 19 | 7 / 12 |
| split ND | 6 | 2 / 4 |
| split NCD | 18 | 9 / 9 |

The versioned correction removes only the documented HAProxy `* ` prefix before calling the historical decoder. Docker/runtime, network, empty-L4-status and declared-layer rules remain unchanged. Instance bits never changed; only previously rejected in-progress successful checks changed path bits from 0 to 1. Consequently the effect is not equal to the total number of `* L7OK` rows in ordinary census: historical runtime/network gates can still reject a path. This is a parser correction in privileged historical diagnostics, not an established cause of the scientific deviations or a new model refinement.

No fitting, business-outcome loading, new acquisition, native parsing or PMX solving occurred. Forecast and metric effect sizes remain unknown. All dependent corrected fits and the complete M7 scoring census must be recomputed before using new corrected results. PMX does not consume this decoder; older PMX-side forecasts remain unchanged, while paired comparisons may change on the M7 side. Other auxiliary series are outside these 168 identities and must be audited if reused.

The first two technical attempts are retained: [v1](../HEALTH_PREFIX_AUDIT_V2_CORRECTION.md) failed on the historical qualification-schema assumption; [v2](../HEALTH_PREFIX_AUDIT_V3_FREEZE_CORRECTION.md) failed on CRLF/LF source hashes before archive loading. Neither produced a complete census or adds an independent campaign. The successful adapter v3 uses an explicit staged-Git-byte freezing gate. Old files/configs/runs remain available.

Exact local evidence: [verified compact archive](../evidence/health-prefix-audit-34217614608/verified-archive.json), [all 328 records](../evidence/health-prefix-audit-34217614608/audit.json), [source members](../evidence/health-prefix-audit-34217614608/source-members.json). Artifact `10052487883`, 80,929 bytes, SHA256 `9ed5c5c3ee20b307837e18608cc85e8005ca9ba95cbb3b36ac628019b0861c70`. All four members are retained exactly, with API metadata and CRC/hash checks. Source archives remain remote. Reproducer: `scripts/retain_health_prefix_audit.py`.
