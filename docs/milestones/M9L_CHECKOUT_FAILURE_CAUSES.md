# M9L: checkout route-up failure-cause discrimination

## Outcome

M9L is complete. The first and only accepted workflow attempt passed all three
jobs and selected the frozen machine branch
`checkout_residual_localized_to_observed_replica_path_loss`. The result narrows
M9K's aggregate route-up residual to loss on at least one target-replica path
represented in the retained logical-request trace, while the union of the two
paths still says route-up.

The four exact calibration contributions to M9K's mean route-up residual
`+0.177614` are:

| Frozen candidate | Mean contribution | Stratified bootstrap 95% interval | Positive cells |
|---|---:|---:|---:|
| aggregate union lost during request | +0.010597 | [+0.009206, +0.012068] | 40/40 |
| observed replica-path loss while union remains up | +0.171370 | [+0.162659, +0.180537] | 40/40 |
| all trace-observed target paths continuously up | -0.004353 | [-0.004423, -0.004277] | 0/40 |
| evidence unresolved | -0.00000046 | [-0.00000138, 0] | 0/40 |

The replica-path component exceeds the next-largest candidate by `+0.160774`,
with 95% interval `[+0.152034, +0.169875]`. Its dominance therefore does not
depend on a close ranking or one placement/law stratum.

Both missingness gates passed exactly: usable target-replica trace coverage was
1.000 in every cell, and resolution among route-up failures minus resolution
among route-up successes was 0.000 with interval `[0,0]`. Full retained learner
traces are still additional post-result diagnostic evidence, not the original
`sampled_mixed` forecasting input.

The result does not prove a precise HAProxy choice or call timestamp. The
normalized trace field is the set of target replicas represented anywhere in a
logical checkout trace. In fact, 33,534 of 36,562 selected calibration requests
(91.7%) represented both replicas, consistent with a multi-call logical
operation passing through the round-robin target group. M9L therefore supports
a request-level multiplicity/routing-state explanation, not the stronger claim
that a single known request was sent to a known-down backend at the sampled
instant.

## Implementation and execution

- frozen implementation and protocol commit:
  [`3dbf8b104faae562b789f5c86966b359f8bd08f2`](https://github.com/a-a-k/telemetry-availability-identification/commit/3dbf8b104faae562b789f5c86966b359f8bd08f2);
- accepted remote execution:
  [run 34085244404](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34085244404);
- run attempt: first attempt, started `2026-09-07T05:01:38Z` and completed
  `2026-09-07T05:03:44Z`;
- local verification before launch: 197 unit tests, repository/configuration
  validation, Python compilation, workflow parsing, and synthetic taxonomy,
  exact-allocation, missingness, dominance, and decision smokes.

The workflow used exactly three jobs, each with `timeout-minutes: 360`:

1. the M9K/evidence identity contract completed in 20 seconds;
2. the retained request classification completed in 78 seconds;
3. the frozen decision completed in 19 seconds.

The full 78.6 MB preservation download, 360-file audit, classification of
96,000 checkout request rows, and 10,000-resample campaign bootstrap ran only
in GitHub Actions. M9L invoked PMX zero times and performed no live collection.

## Accepted artifacts

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m9l-failure-cause-contract-34085244404` | 10004980006 | 3,009 | `976c64a4fbd22241edb19030a5be409e2ba6e522ed634ad348940a9397d5555f` | 2026-12-06 05:01 UTC |
| `m9l-failure-cause-discrimination-34085244404` | 10005005030 | 4,499,420 | `927961672fe5ffb2d04b134659275b42f5a2cd041b701cf12def0a379e5770d7` | 2026-12-06 05:01 UTC |
| `m9l-failure-cause-decision-34085244404` | 10005011688 | 2,461 | `ed5cbe05f58fe02453fd951e1995fde1f3ca7b125e52f5cee7e8155bfbbda3df` | 2026-12-06 05:01 UTC |

GitHub reports all artifacts as unexpired and associates them with the frozen
commit and run. Principal uncompressed identities are:

| File | Bytes | SHA-256 |
|---|---:|---|
| `contract-manifest.json` | 6,250 | `6df4a4e83cc2f21a834cf0f459b38c3f3bbc6a0df3a5f477864f8e4e24638195` |
| `discrimination-manifest.json` | 7,459 | `30e43d03f533169e669bb64f3b46579f48ffe25dbead21948c09712ecc0a59c6` |
| `request-classification.csv` | 28,927,047 | `b4c8c30bdd1309dee1e2762144e8bd9ca1d8e76c26e91d638c7dab84ebb749b2` |
| `class-summary.csv` | 39,694 | `d2f235585c9681f1d9d8fcb04fe035611b5b6d7cc0d3063c1e8b660e2d93cceb` |
| `cell-candidates.csv` | 11,470 | `81474ee83f930c4fcf0138a26953f00af8fd0561fae5d0a2506967791bc218d9` |
| `bootstrap-summary.csv` | 2,608 | `7035a7195f7adcb72306fd849727388665daefdd1d111327645f4c749bb8ae2e` |
| `selected-file-audit.csv` | 56,541 | `daa78b1ee9d0b55731984c5a9f1f9bdf73d83bd398e22496515783c79b283a43` |
| `decision-manifest.json` | 2,662 | `a24aad3f8bddb8d9b2f121b6b0b873ef366ec39434dcd7bd806570425f1d0b75` |

## Integrity and exact reconstruction

The contract reverified the accepted M8A preservation/audit and both M9K
artifacts, including run commits, compressed digests, expiry, locked tables,
M9K's integrity pass, calibration corroboration, and exact next branch. The
discrimination job then recorded:

| Check | Result |
|---|---:|
| qualified-manifest census | 160 |
| selected N/ND checkout cells | 40 |
| selected files checked against M8A | 360 |
| file mismatches | 0 |
| M9K request/count mismatches | 0 |
| calibration class rows | 240 |
| test class rows | 120 |
| minimum selected route-up requests per cell-period | 805 |
| minimum completion alignment | 0.996970 |
| maximum residual reconstruction error | 1.39e-16 |

The 38,343 stable calibration checkout requests contained 36,562 route-up
requests and 6,990 route-up failures. Every one of those failures was recorded
as a timeout. The exhaustive primary classes were:

| Calibration class | Requests | Failures | Failure rate | Timeouts |
|---|---:|---:|---:|---:|
| aggregate union lost during request | 424 | 405 | 95.5% | 405 |
| target path down at start while union continuous | 8,814 | 6,561 | 74.4% | 6,561 |
| target path lost later while union continuous | 49 | 23 | 46.9% | 23 |
| all trace-observed target paths continuously up | 27,272 | 1 | 0.0037% | 1 |
| completion health unresolved | 3 | 0 | 0% | 0 |
| trace target unresolved while union continuous | 0 | 0 | -- | 0 |

The exact class allocation subtracts the frozen baseline failure allowance in
each class, so these contributions sum to the M9K residual rather than merely
partitioning raw failures. All 40 per-cell identities matched to `1e-12`.

The replica-path component also dominated within every fixed stratum: its mean
was `+0.156286` for colocated/N, `+0.134536` for colocated/ND, `+0.160840` for
split/N, and `+0.233820` for split/ND. No stratum was selected or dropped after
seeing these values.

## Test-only aggregate corroboration

Held-out test traces remained inaccessible by construction. The permitted
aggregate interval check reconstructed M9K's test route-up residual
`+0.180031` exactly:

- union lost during the request: `+0.010381`, interval
  `[+0.008729,+0.012090]`;
- union remained continuously up: `+0.169650`, interval
  `[+0.162021,+0.177402]`;
- completion unresolved: approximately zero.

Thus the aggregate interval-loss candidate did not receive its required test
corroboration: most test discrepancy remains while at least one path is
continuously up. This agrees with, but cannot independently verify, the
calibration trace finding that the union hides replica-level/multi-call state.

## Interpretation

M9L rejects two explanations for the dominant retained calibration discrepancy:

- it is not mainly an average route-exposure error, as M9K already showed; and
- it is not mainly the aggregate union becoming down after request start.

Instead, the logical checkout request almost always contains target calls
represented on both replicas. When one of those represented paths is down even
though the other keeps the union up, timeout failures are common. When all
represented paths remain up, failures are virtually absent. This is strong
evidence that the operation cannot be represented as one instantaneous
`at-least-one-replica-up` demand without modeling request-level call
multiplicity/routing behavior.

The evidence remains observational and discretely sampled. A trace replica set
does not timestamp each product-catalog call, and the one-second health record
does not contain HAProxy's per-request decision log. Consequently M9L does not
claim a unique physical mechanism such as stale backend state. It localizes the
next structural test: whether a predeclared request-level route representation
accounts for the checkout discrepancy without outcome tuning.

The result neither revises M7 nor establishes improved accuracy. It diagnoses a
failure of the specified operation/route abstraction using richer retained
learner evidence. That extra evidence has an acquisition and processing cost
and cannot be counted as free automation. M9J's scoped PMX preprocessing result
and PMX's scientific priority remain unchanged. The article still has no
established better-accuracy or lower-end-to-end-cost advantage and no overall
success/failure verdict.

## Next milestone

The frozen next branch is `m9m_checkout_request_level_routing_model_test`. M9M
must distinguish, before using outcomes, at least the existing OR group route
from a request-level multi-replica demand derived from calibration trace
structure and declared round-robin deployment. It must preserve an explicit
information ledger: a trace-conditioned diagnostic can test mechanism, whereas
a deployable held-out prediction may use only features available before the
test request. It must not simply substitute the favorable observed trace class
into held-out predictions.

## Completion checks

- The taxonomy, candidate aggregation, missingness margins, bootstrap, and
  branches were committed before the first full trace scan.
- The first attempt completed all three 360-minute-bounded jobs.
- All retained identities, 360 files, M9K counts, and exact residual allocations
  passed.
- Trace coverage/equivalence gates passed without imputation.
- Replica-path loss uniquely dominated under the frozen four-way rule.
- The absent test trace graph was not reconstructed or inferred.
- No PMX invocation, live collection, refit, revised prediction, or article-level
  claim was made.
