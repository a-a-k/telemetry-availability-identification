# Original AINA: full artifact and exact semantic audit

Run [34231677146](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34231677146), head e4305a9f1d734108f7785d20eac7a0bd0b1522a7, success. Frozen v2 config SHA256 6cd5d2de75919932bedbc4d43e8baea2de993a46562eb606d1cd0aba04718ea6; unchanged scientific audit v1. Prior run34231434522 failed HTTP403 before data acquisition and remains preserved; v2 corrected authenticated draft visibility only.

## Source identity and reproduction

Original run a-a-k/otel-demo-resilience/19590510289, executed head a8bc5a29a15443ad3a4ef6b88ac710afb97c70c0. All250 original artifact ZIP digests match retained GitHub metadata and the nested byte streams in the author's original 100x100.zip. All ZIP member paths, uniqueness, CRC, hashes and graph seals pass. Exact original source files are retained with Git blob/SHA256 and license. The upstream demo was fetched from main: original application commit/images are not established by this source identity.

Census: five p values,50 chunks/value,100 windows/chunk,100 probes/window =25000 windows and2500000 probes. Every raw status and per-endpoint success/attempt denominator reconciles;401/403 skip count0. The source can count these statuses as success, but that branch has no observed contribution to these data. All25000 window annotations occur in retained controller logs, use the right p and K, and report15 eligible containers, matching model cardinality. No bad-stop anomaly field is present. Cardinality agreement does not prove full runtime universe identity or fault timing throughout measurement.

Every retained per-endpoint and realized-mix report was recomputed; maximum absolute difference4.440892098500626e-16. The author global CSV's window totals, live sums/squared sums/mean/variance, global model means, per-window MAEs and MAE delta reproduce within1.1102230246251565e-16. The original global MC estimator samples endpoints uniformly. Realized-mix forecasts weight separate endpoint estimates by actual finite probe counts and are a distinct report.

| p | Original global MC, all-block | Live | Signed model−live, pp | MC async−block, pp |
| --- | --- | --- | --- | --- |
| 0.1 | 0.780945236 | 0.682630 | +9.831524 | +0.0001220 |
| 0.3 | 0.610407776 | 0.557032 | +5.337578 | +0.0053024 |
| 0.5 | 0.356400884 | 0.359702 | -0.330112 | +0.0030492 |
| 0.7 | 0.250870400 | 0.289356 | -3.848560 | +0.0033496 |
| 0.9 | 0.050005696 | 0.171918 | -12.191230 | -0.0035572 |

Signed aggregate error is not per-window MAE. The author's global CSV delta is MAE(all-block)−MAE(async); original per-window report code uses the opposite orientation. Neither is the forecast difference. Preserve both definitions explicitly.

## Exact source-semantic result

All20 distinct graph/replica byte pairs are supported:16 service nodes,22–30 edges, exactly3 async edges,15 eligible single-replica services. Enumerated all32768 allowed container-failure states per pair =655360 distinct pair×state controls, evaluating all4 endpoints under both modes. Changed endpoint states: **0**. This is exact invariance of these original predicates throughout their allowed failure class, not an empirical nonsignificance statement or a general result about asynchronous systems.

The exact global probabilities are identical across all20 graph variants and both modes: p.1→82/105, p.3→1111/1820, p.5→139/390, p.7→137/546, p.9→1/20. The source fixed-cardinality K values are2,4,8,10,14 of15; p is known scenario input. Python rounding and minimum-one semantics are preserved.

All2500 original MC records declare5000000 samples and the matching graph hash. Maximum absolute MC deviation from the exact source probability is0.000678866666667, below the simultaneous Hoeffding union radius0.001072983013145 at family alpha.05. This diagnostic assumes independent Bernoulli trials within each old MC run; seed absence prevents bitwise MC replay. Exact invariance establishes zero semantic effect in this source class; retained forecast differences are consistent with simulation noise.

The camera-ready text defines delta as a forecast difference and states a maximum0.001pp. Retained global means reach0.0053024pp atp.3, and the largest absolute endpoint mean difference is0.0068896pp (recommendations,p.5). That literal numerical bound is not reproduced by these records. The new manuscript should state exact source-predicate invariance and separately report MC variability, with the precise scope. The published source/text are preserved, not silently rewritten. This does not establish a new modeling contribution.

## Scope, resource and remaining explanation

The historical business event uses sequential requests, per-call6s timeouts and checkout setup+submit; it is not the new whole-operation2s event. The collector accepts a --window argument but does not use it to bound the100 sequential probes. The controller holds failures for60s and the workflow delays15s before starting probes. Original records do not contain per-probe timestamps, so actual overlap with recovery remains to be audited; no causal attribution is assigned from code inspection alone.

All original payload parsing and exact state enumeration ran in GitHub Actions. No new MC draws, applications, fits, independent campaigns or main campaigns. Process44.80s wall/43.44s user, RSS76024KiB. Retained exact compact artifact10058071499:1511261bytes, SHA25609d923a1b4332f17872f703ba25deaa4054b86f5d713d6256104c9cdd706210e. Member hashes include every original source member; topology/full live/model payloads stay remote. See [summary](../evidence/original-aina-audit-34231677146/files/summary.json) and [exact compact archive](../evidence/original-aina-audit-34231677146/compact.zip).
