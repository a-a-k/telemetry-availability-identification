# M9Q historical application census: execution freeze

This implements the four-sample continuation in
`M9Q_PMX_OBSERVED_OPERATION_PROTOCOL.md`, subject to the explicit repaired
acceptance in `configs/m9q_application_acceptance.json`. The original failed
conformance decision remains in the record. All application inputs are the
previously designated M7 NCD/r0 raw audit samples; no M9P data is accessed.

A separate preparation job verifies the accepted review artifact and exact
file hash before retrieving M8A's preserved sources and inventory. It verifies
all twelve selected native-stream, campaign-manifest and trace-membership files
against the pinned M8A file inventory. It selects all 3,840 baseline/calibration
trace IDs per sample, computes the unchanged adapter projection, and publishes
the complete four-sample learner contracts before any PMX invocation. No
evaluator table or outcome column is an analytical input. Only the preparation
worker receives the preserved archive; subsequent extractor jobs receive the
published learner projections, their sidecars, oracles and byte manifests.

Each extractor job processes one complete sample once. It uses the exact
conformance binary, Java 11, unchanged author options apart from the trace path,
20-second startup stabilization, and the prospectively accepted 1,800-second
internal watchdog. All preparation, extraction and census jobs have 360-minute
limits. Zero eligible server input produces an explicit coverage result and
zero invocations. Technical or structural failures remain in the final census;
no fit subset is selected for a favorable score and no additional repetitions
are triggered by a mismatch.

The application oracle is the deterministic census of eligible observed
operations, their span-error frequencies, component ownership and call edges.
PCM references must resolve to that projection; a keyed reconstruction inventory
checks all selected span identities and parent relationships. Usage-node counts
follow the recovered minimum-count rounding rule and are checked separately
from observational counts. A collision between first timestamps of different
root operations is reported explicitly and prevents a complete projection-
fidelity claim. Resource-demand estimates are retained without a calibrated
performance claim. The declared physical execution host is one GitHub worker
per historical campaign; native instance keys remain separate.

Coverage reports all original selected trace IDs, absent or invalid inputs,
traces with no server span, missing-parent roots, multiple trees, unresolved
instances, malformed JSON records and discarded non-server errors. Operation
frequencies therefore describe the reported eligible projection; they do not
estimate failure for omitted invocations or external semantic requests. Invalid
trace details remain in the parser/census sidecars. No held-out availability
score, transfer result or uncertainty comparison is produced by this stage.

All four expected sample identities remain in the final aggregate, including
missing outputs. Retain learner contracts, original generated models, stdout,
watchdog/exit records and memory/time measurements for 90 days. Parsing and
projection costs, PMX invocation costs and shared source preparation are reported
separately. Engineering effort and total monitoring overhead are not inferred
from these timers. The result determines what further semantic mapping is needed
for an independent PMX availability comparison; it does not itself provide it.

## Retained pre-extraction technical amendment

Run 34125261493 at `5868cac7503a44d9462559871441821e9327c803` passed the
repaired-acceptance gate and source byte checks, then failed before parsing the
first native stream or invoking PMX. The generic three-period membership reader
rejected the historical `sentinel` label. The frozen M7 collector explicitly
creates those requests in `_semantic_sentinels` and prepends them to
`trace-join.csv`; they are outside baseline/calibration and were excluded by
the earlier M9G selection rule.

The repaired application boundary accepts exactly baseline, calibration, test
and sentinel labels, retains only the first two, and rejects any learner trace
ID also present in test or sentinel. Other labels remain errors. It records
period counts without using outcome columns. The required 3,840 learner IDs,
four samples, native adapter, model oracle, binary and invocation budgets are
unchanged. The original config and code are retained at the tested Git commit;
the new config records this amendment and renewed implementation hashes.

The failed source-preparation artifact 10019825925 (719 compressed bytes,
SHA-256 `170684aa53f895407ce4b39e5e29b3d5ad4a5b6da0be3bd4e1d4468fcde1e018`)
and its empty four-sample census artifact 10019840031 (504 compressed bytes,
SHA-256 `e6a04b1921a498e574d8bbda0b31e2d3314a62b549f9d0b4247199ebcf3aa08b`)
are preserved with 90-day retention. The census records four missing outputs,
zero extractor invocations and zero forecasts. This is a membership-parser
correction before model extraction, not a change selected by model accuracy.
