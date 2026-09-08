# Reviewed M9P aggregate evidence

This snapshot accompanies the [completed milestone report](../../milestones/M9P_INDEPENDENT_TEMPORAL_CONFIRMATION.md)
for Actions run 34118845320, attempt 1, commit
`bc03711b3a50daa90be305986dd12769a2d8ef30`.

The `readiness`, `candidates`, `evaluation`, `access` and `audit` directories are
byte-preserving copies of the five verified summary archives. They include
generated campaign-level predictions, scores and cost/adequacy tables; they
contain no request-level learner, test or native-trace bundle. Original candidate
and evaluation seals remain alongside their files.

`completed-summary-audit.json` is the local automatic verification result from
2026-09-07T15:25:34.660235Z. `artifact-locks.json` records all 485 source/summary
artifact identities, byte counts and digests; `run-api.json` preserves the
completed-run API metadata. The remote `audit/artifact-inventory.json` predates
the final audit artifact's publication; the completed inventory includes it.

These 23 evidence files were copied on 8 September 2026 without changes.
`snapshot-files.sha256` records their exact bytes; the directory's `.gitattributes`
disables Git text conversion for this evidence. Original ZIP digest verification
and source-record provenance checks are described in the
[reporting method](../../M9P_REPORTING_METHOD.md). Keeping a summary snapshot does
not extend the original source artifacts' 90-day retention.

The three plotted input files are:

| File | Bytes | SHA-256 |
|---|---:|---|
| candidates/candidate-manifest.json | 1,985 | `e70b79dd19553c16ecdbdd483defed81ad31f91b07f431764e067360326abae8` |
| evaluation/evaluation-manifest.json | 4,669 | `d606dd37e38ab1285037df733ddf72a96b81c7ffe02990007b9fda60f0ec75ce` |
| audit/main-audit.json | 433 | `6fe00f827b270d9e75c81f6c5e57bf4ed0bbf5cdfdd86fac2840a6d73db5dab0` |

The [figure provenance](../../figures/m9p-confirmation/figure-provenance.json)
records the same input digests and the renderer's digest and library versions.
No prediction, interval or classification was recomputed during this reporting.
