# M9T: external-request and native-span correspondence census

Status: complete as learner-only development evidence. Run
[34188479893](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34188479893)
at `5254790e50822514742da822a32e40933440941c` completed successfully from
2026-09-08T04:51:32Z through 04:52:24Z; corresponding
[CI](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34188480033)
passed. The [frozen protocol](../M9T_PMX_REQUEST_CENSUS_PROTOCOL.md) retains three
descriptive observation policies and all operations in both learner periods.
There are zero PMX calls, fitted models, forecasts, new campaigns or evaluator reads.

All four historical M7 NCD/r0 samples retain 3,840 learner requests each:
240 baseline and 3,600 calibration. Membership exactly matches the native
baseline/calibration trace IDs; test and sentinel IDs are excluded. Each selected
request has a native trace. There are no malformed JSON records or invalid
selected traces under the declared parser. Multiple roots therefore require
semantic explanation; they are not automatically absent request traces.

## Complete calibration request census

Each row contains 1,200 external requests. Error-marked counts mean requests
with at least one native span error; none of those requests is semantically
successful in these four samples. Baseline rows and all three observation
policies remain in the [retained aggregate evidence](../evidence/m9t-34188479893/request-census.json).

| Sample | External operation | Successes | Timeouts | Any span error | Multiple native roots |
|---|---|---:|---:|---:|---:|
| DeathStar colocated | compose_post | 1,017 | 165 | 40 | 2 |
| DeathStar colocated | read_home_timeline | 1,200 | 0 | 0 | 0 |
| DeathStar colocated | read_user_timeline | 975 | 201 | 55 | 382 |
| DeathStar split | compose_post | 1,045 | 140 | 39 | 2 |
| DeathStar split | read_home_timeline | 1,200 | 0 | 0 | 0 |
| DeathStar split | read_user_timeline | 990 | 198 | 44 | 155 |
| OTel colocated | add_to_cart | 1,011 | 187 | 189 | 1,011 |
| OTel colocated | browse_product | 1,016 | 183 | 184 | 0 |
| OTel colocated | checkout | 906 | 292 | 294 | 1,005 |
| OTel split | add_to_cart | 937 | 247 | 263 | 937 |
| OTel split | browse_product | 962 | 222 | 238 | 0 |
| OTel split | checkout | 755 | 426 | 445 | 946 |

DeathStar's error flags cover fewer unsuccessful requests than the external
semantic outcome. For example, colocated compose_post has 183 unsuccessful
requests but only 40 with any span error; colocated read_user_timeline has
225 unsuccessful requests but only 55 with a span error. An estimator using
only those flags does not estimate all observed semantic failures or timeouts.
The gap cannot be repaired by treating a lack of error flags as proven success.

## The operation boundary explains part of the forest

The frozen workload code in `live_pilot.py` defines `_otel_add_cart` as a product
GET followed, on success, by a cart POST. `_otel_request` performs that helper
before the checkout POST. The same supplied trace headers are passed to these
HTTP calls. Consequently, add_to_cart and checkout are compound user operations.
Several HTTP roots with one request identity are expected from this driver.

For colocated checkout, the service-boundary table contains 1,200 frontend-proxy
GET roots and 2,010 POST roots, corresponding to two POSTs after each of 1,005
successful prerequisite GETs. For add_to_cart it contains 1,200 GET roots and
1,011 POST roots. These observed counts and source control flow explain these
particular forests; they do not prove complete instrumentation of every other
missing-parent subtree. Parent relationships, root identity and timestamp order
remain separate properties.

DeathStar's service-boundary view retains an nginx-web-server root for every
request, with endpoint-specific operations. Its absence of explicit SERVER tags
does not imply absence of operation observations. The candidate service-boundary
projection is descriptive; it must not relabel an unmarked span as an observed
SERVER span without disclosure. Extra roots such as post-storage reads remain
in the census instead of being silently attached by temporal proximity.

## Consequences for an independent PMX comparison

The target should be the complete external operation under the frozen semantic
predicate and timeout behavior. A declared external-request wrapper can provide
that root and group the HTTP calls sharing its request/trace identity. Such a
wrapper is an explicit adapter addition, with external request outcomes charged
as information inputs. It is not an original native span or an automatically
recovered semantic predicate. Native timestamps, errors, identities and parent
links need an unchanged audit sidecar, including any inferred attachments.

The census retains inclusive parent errors, errors with and without child errors,
swallowed-child cases, invocation coverage, call edges and repeated-call counts.
These are inputs to the next model contract. They do not yet validate a local
independence assumption or qualify one of the three projections as a comparator.
Model variants will be fixed before new confirmation; the already inspected M7
and M9P data remain development evidence for a revised PMX pipeline.

## Provenance and cost

The source archive and independent file inventory match the M9Q locks, as do
all selected native files and learner request seals. The output ZIP was checked
against its API digest and length before local inspection. Only aggregate
outputs were downloaded locally. Artifact 10041353974,
`m9t-pmx-request-census-34188479893`, is 28,156 compressed bytes with SHA-256
`be4804051839fa6331869e2cc6d29137e86db42ccb7eb6e853e55136abcee920`,
expiring 2026-12-07T04:51:34Z. `request-census.json` is 17,085 bytes with SHA-256
`4b4937aaa71d7e2b5b14b18ccab06fc32fb0d495ac2360a5f54be9df566a63ae`.

The process took 31.04 seconds and peaked at 833,564 KiB RSS. Per-sample processing
times were 2.723512, 2.560782, 10.171881 and 10.560642 seconds for DeathStar
colocated/split and OTel colocated/split, respectively. Their charged native
file sizes were 55,939,259; 56,876,338; 209,683,042; and 208,626,026 bytes.
Two artificial unit tests check missing-request accounting, swallowed-child
errors through contracted ancestors, and rejection of test-period input.
