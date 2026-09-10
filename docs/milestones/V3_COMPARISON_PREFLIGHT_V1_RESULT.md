# Full-duration comparison preflight v1: preserved PMX interface failure

Run **34442870952**, source **28eb21c78b2ade594fd493d0fc656fa2fa6dda79**, 10 September 2026. Workflow conclusion: failure (six application PMX projection jobs failed; the other30 jobs succeeded). This is development/preflight evidence and **does not admit main**. Main remains0/240.

The full six-campaign acquisition, graph replay, candidate freezing and evaluator sequence ran. All six acquisition/evaluator quality gates qualified. The closed evaluators scored all **21,600 test attempts**, with all **200 planned current-method slots** retained. There are17 saved execution models and six exact graph replay jobs. Three application solver batches reproduce all **48 known-probability control solves**. There are no application PMX forecasts: both PMX columns contain20 explicit missing slots each.

## Cause and correction boundary

All six PMX projection jobs stop at `KeyError: 'profile'`. The sealed request role deliberately contains only the eight `REQUEST_FIELDS`. The qualified legacy PMX request adapters additionally expect `request['profile']` to name the synthetic external wrapper. The v1 bridge forwarded the eight-field records without deriving this metadata from the sealed campaign identity. Its original bounded fixture tests had supplied the richer legacy records and therefore missed the physical-interface mismatch.

This is an integration defect before Java PMX extraction of the application models. The controls use independently prepared source-known fixtures, explaining why their extraction/solver stages still pass. Neither green graph jobs nor those positive controls establish a working application PMX comparison. Six bounded traceback excerpts, each associated with the completed job/log hash, are retained in the evidence directory.

The separately versioned [v2 correction](../V3_COMPARISON_V2_REQUEST_PROFILE_CORRECTION.md) derives only the wrapper profile from `identity.application`, preserves the eight-field input files and rejects extra fields. It does not change the calibration outcomes, graph estimator, PMX failure policies, source options, PCM solver or statistical analysis. v1 is not edited or retrospectively marked successful.

## Supported and unsupported graph outputs

| Method | Point /20 | Ambiguous masked law | Unexplained native parent boundary | Missing PMX builder |
| --- | ---: | ---: | ---: | ---: |
| Gstar | 10 | 7 | 3 | 0 |
| GID | 17 | 0 | 3 | 0 |
| Gselected | 6 | 11 | 3 | 0 |
| G_without_deadline | 6 | 11 | 3 | 0 |
| G_without_selection | 10 | 7 | 3 | 0 |
| G_without_completion | 6 | 11 | 3 | 0 |
| G0 | 17 | 0 | 3 | 0 |
| B0 | 20 | 0 | 0 | 0 |
| PMX | 0 | 0 | 0 | 20 |
| PMX_inclusive | 0 | 0 | 0 | 20 |

Both Petclinic campaigns yield all four Gstar points. DeathStarBench yields the home-timeline point in both placements; split compose is ambiguous, and colocated compose/both user-timeline graphs are unsupported because of a native parent boundary. All six OpenTelemetry operation cells have ambiguous Gstar functionals. The corresponding exact bounds and diagnostic reasons are retained. These are coverage/identification findings on development data, not technical exceptions to hide or a reason to insert midpoint/zero forecasts. The v2 metadata repair does not alter them.

## Integrity and retention

[Compact evidence](../evidence/v3-comparison-preflight-34442870952/verified-archives.json) retains **28 exact allowlisted ZIPs,114,798 bytes,83 members**, together with complete provider artifact/job metadata, member hashes and six compact failure excerpts. Every archive passed provider byte-count/SHA256 and ZIP CRC/member checks. Raw/native/ordinary/closed request/model/PCM/raw-solver payloads remain remote; they were not downloaded locally.

The [partial pipeline audit](../evidence/v3-comparison-preflight-34442870952/partial-pipeline-audit.json) independently checks the completed subchain: graph/replay/evaluator read counts6/5/8, zero blocked reads, matching candidate/evaluator/source hashes, unchanged forecasts in all-sequence and stable views, and all six freeze jobs completed before evaluator jobs with a successful guard before closed download. This does not supply a missing PMX actual-input audit or override the failed global admission gate.

Evidence-manifest SHA256: `e53794af3d1b85b566e481167ccab8bafc263998033b5f7d372ca1e296461d84`.
Remote comparison-report SHA256: `a4e8ebd6bc2deb4cef22f8162ecd661a645fbb1a2f8c2272ba228580eb2a424f`.
The complete remote analysis, including its descriptive errors, stable/transfer/cost records and empty contrasts, is retained with that hash. No error ranking was used to choose the interface repair. A full new preflight is required before main admission.
