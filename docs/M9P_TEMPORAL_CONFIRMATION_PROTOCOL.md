# M9P: prospective temporal confirmation

This implementation follows the accepted M9O protocol and run 34113304974.
The byte-identical design and 120-cell matrix are retained in
`configs/m9p-design.json` and `configs/m9p-prospective-campaigns.csv`.
M9O's questions, sample size, models, thresholds, periods and seed roots remain
frozen. No M7, M9N, planning or preflight observation enters confirmation.

## Acquisition and separate no-fit preflight

The preflight consists of OpenTelemetry checkout acquisition in colocated/N,
colocated/ND, split/N and split/ND, each at repetition zero, with a 60-second
baseline and 900-second calibration and test periods. The existing driver still
issues four mixed-operation requests per second. Existing pinned images,
benchmark revision, renewal processes, polling, request timeouts, semantic
sentinels and quality criteria are reused without modification. The preflight
namespace is `m9p-temporal-preflight-v1` and seed root is 2026090702.
Main acquisition uses `m9p-temporal-confirm-v1` and root 2026090701.

Before collection, fix the execution suffix
`-run{GITHUB_RUN_ID}-a{GITHUB_RUN_ATTEMPT}` on each namespace. This gives fresh
request and trace identities even for an infrastructure retry, while preserving
the factor-specific renewal seed rule and the prescribed campaign identity.
The suffix also enters the existing per-request cart identifier. Schedules keep
their prescribed seed on an infrastructure retry; each attempt is preserved and
cannot become an additional scientific repetition.

Acquisition validates the pinned source and images, exact request census, fresh
execution provenance, actual period timestamps, seed derivation, semantic
sentinels, telemetry and event-controller quality. The no-fit qualification
uses the existing native-trace normalizer to validate the physical evidence
boundary. It does not estimate model parameters, contrasts, confidence intervals
or effectiveness. Historical collection code retains its ordinary operational
success counters in source manifests; the preflight decision does not inspect
model effects or use them to tune the design.

Each successful cell publishes three separate 90-day artifacts: learner,
evaluator and acquisition audit. The learner contains only calibration health,
baseline/calibration requests, declared deployment, minimal identity and a
sanitized boundary assertion. Trace-derived record fields are inert and no
trace graph or held-out summaries enter this bundle. SHA-256 seals cover every
file, with an exact allowlist. Evaluator data consist only of test requests and
test health with a separate seal. The audit retains original provenance,
schedule, image/runtime inventories, source byte counts and qualification time.
Preflight raw sources and failed acquisition attempts are retained for seven
days. Main compact evidence, predictions, audits and results are retained for
90 days; retention and upload completion are checked through the Actions API.

The preflight's final job requires all four identities, a common fresh run and
commit, no fits or comparison scores, and the same configuration and acquisition
implementation bytes. All jobs have 360-minute timeouts. All live acquisition,
fitting and full analysis run only in GitHub Actions. Local checks are confined
to source/configuration validation and synthetic unit tests.

## Main-run readiness and interpretation

The main workflow and analysis must be committed, tested and audited against
M9O before main dispatch. They must verify the accepted preflight provenance
and artifact retention before acquiring the frozen 120-cell matrix. All
predictions and curve parameters are fitted afresh from learner-only artifacts
and uploaded before the evaluator job can download test evidence.

The three inferential quantities and their Bonferroni intervals are exactly
those in `M9O_TEMPORAL_CONFIRMATION_PROTOCOL.md`. Matched stable endpoint,
all-calibration endpoint, 500 ms reference and lower/upper age views remain
descriptive. Retain all M9N per-cell adequacy and optimizer gates. Publish all
three quantities irrespective of direction; inadequate coverage makes the
confirmation incomplete. No missing campaign is silently discarded. A failed
scientific gate is not an infrastructure retry or a reason to enlarge the
sample. Record and retain infrastructure attempts and reasons separately.

No conditional result constitutes an advance forecast. No single-operation
confirmation settles the independent PMX comparison or an article-wide accuracy,
automation-cost or novelty claim. The endpoint controls and the full-health
input cost must remain visible in interpretation.

## Frozen analysis implementation

The prospective implementation retains state-only, lower/midpoint/upper logit,
source 500 ms, matched stable endpoint and all-calibration endpoint: seven
methods per campaign. PAVA is not included in this confirmation; M9O allowed
sensitivity retention without promotion. The eight-start M9N likelihood and
its bounds, one-path episode representation and marginal averaging are imported
unchanged, with the new analysis seed. The original M9N global calibration
recovery test is descriptive here; M9O fixed three inferential quantities and
retained per-cell adequacy and optimizer gates, not an additional inferential
family. Lower/midpoint/upper mean within-cell prediction span must remain at
most 0.02. A failed adequacy gate suppresses confirmatory claims while all
computed scores and the three intervals remain published.

The main workflow has readiness, acquisition, learner-only candidate freeze,
evaluation and retention/cost audit jobs. Readiness verifies the accepted
preflight run, exact audit artifact and file, source/configuration bytes,
retention and the final implementation hashes. Candidate generation rejects
unexpected files, evaluator directories, historical sources, incomplete
matrices and mixed run attempts. There is no automatic partial rerun or
missing-campaign omission. The candidate artifact is checked through the
Actions API before any evaluator download.

All 120 successful main cells also retain complete raw sources, including
native telemetry, for 90 days. This additional preservation is fixed before
main acquisition and is independent of scores. It prevents loss of the native
input needed for subsequent source/adapter audits. The learner job still
downloads only the sanitized learner bundles. Failed raw attempts retain the
seven-day diagnostic policy; the post-run audit records artifact sizes,
expiry, source bytes and runner time.

The input-cost table separates actual shared request-file bytes, health bytes,
health rows, model fitting time and common parsing/episode construction time.
The all-calibration endpoint also records the minimal CSV projection of its
required outcome counts. Shared parser timing is explicitly not an isolated
endpoint implementation benchmark. Trace bytes are zero for the seven model
inputs, but native-trace qualification and collection costs are charged
separately. No lower end-to-end cost claim is inferred from a zero model-input
trace column or from a shared preprocessing measurement.
