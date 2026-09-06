# M8A: M7 evidence preservation and arithmetic audit

## Outcome

M8A is complete. All 165 still-available artifacts from frozen M7 run
`33990678586` were recovered, inventoried, and republished together with 90-day
retention. The source set contains all 160 qualified campaign bundles, all four
predeclared raw `NCD/r0` audit samples, and the frozen analysis artifact. No
source artifact had expired when the workflow ran.

An independent reconstruction from the sequestered test-request files found
zero campaign-identity, analysis-file-hash, score, summary, or primary-contrast
mismatches. This rejects the tested explanations based on a wrong join,
denominator, Bernoulli Brier calculation, operation weighting, or equal-stratum
aggregation. It does not explain the observed overprediction or mixed topology
support.

The scientific position therefore remains: M7 does not establish a predictive
gain and contains discrepancies with observations, while their causes are not
yet diagnosed sufficiently to declare the overall approach successful or
failed.

## Implementation and execution

- diagnostic protocol and implementation commit:
  [`7a9744f6bf2db69424efc2ae0197714ebee42505`](https://github.com/a-a-k/telemetry-availability-identification/commit/7a9744f6bf2db69424efc2ae0197714ebee42505);
- two-version CI:
  [run 34016097937](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34016097937),
  successful;
- remote preservation and audit:
  [run 34016153918](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34016153918),
  successful in 54 seconds;
- source M7 execution:
  [run 33990678586](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33990678586),
  source commit `b1925736f314da610debd23a586d7b7d00cae7ca`.

The workflow job used `timeout-minutes: 360`. Full hashing and reconstruction
ran only in GitHub Actions. Local work was limited to unit tests and CLI/config
smokes; the complete local suite passed 104 tests before the implementation was
pushed.

## Preserved evidence

The original 165 artifacts total 78,298,896 compressed bytes. Their unpacked
contents comprise 1,538 files and 985,798,545 bytes. The earliest original raw
sample would have expired on 12 September 2026; the renewed combined archive is
retained through 5 December 2026.

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m8-preserved-m7-evidence-33990678586-34016153918` | 9983956440 | 78,577,341 | `978b380bf54be67ec13b2ebbfaac4464ee5653106ee68176fefcf2db4e85e271` | 2026-12-05 06:18 UTC |
| `m8a-m7-integrity-arithmetic-34016153918` | 9983956747 | 737,045 | `eca453e577ccac02f26716660062664355dde046748456b4695caa7480ba3439` | 2026-12-05 06:18 UTC |

The inventory records the original artifact id, name, compressed size, digest,
and expiry, plus the relative path, size, and SHA-256 of every unpacked file.
Re-uploading changes the container archive digest; the file inventory preserves
the link to each recovered source file.

## Identity and immutable-file checks

The expected matrix was reconstructed from the M7 configuration rather than
from the analysis output. It contains exactly 160 distinct identities: two
applications by two placements by four failure laws by ten repetitions. Every
identity had exactly one expected artifact and one qualified cell, and every
evidence boundary named source run `33990678586` and the single source commit
above.

The stored and recomputed SHA-256 values matched for `predictions.csv`,
`scores.csv`, `cell-diagnostics.csv`, `contrasts.csv`, and `summary.csv`. Thus
the tables audited here are byte-for-byte the tables reported in M7, not a later
regeneration.

## Independent arithmetic reconstruction

For each of 36,459 score rows, the audit independently:

1. selected the target campaign from application, target placement, failure
   law, and repetition;
2. reconstructed health-transition times from successive saved test-health
   states;
3. selected the full or one-second-guarded request sequence;
4. counted semantic successes directly in the sequestered test-request file;
5. evaluated
   `s(p-1)^2/n + (n-s)p^2/n`, signed error `p-s/n`, and absolute error;
6. rebuilt equal-operation campaign values, all 117 summary rows, and the
   primary equal-stratum contrast.

All rows agreed within the predeclared `1e-12` tolerance. The largest absolute
per-score Brier difference was `2.22e-16`; the largest summary Brier difference
was `4.16e-17`.

| Primary field | Stored | Independently recomputed |
|---|---:|---:|
| Paired campaigns | 117 | 117 |
| Strata represented | 16 | 16 |
| Proposed minus B2 | +0.000232717380143862 | +0.000232717380143860 |
| Standard error | 0.000507398538578583 | 0.000507398538578584 |
| Degrees of freedom | 2.362920479813454 | 2.362920479813453 |
| 95% lower bound | -0.001658600756341354 | -0.001658600756341361 |
| 95% upper bound | +0.002124035516629078 | +0.002124035516629081 |
| Two-sided p-value | 0.685283075845184 | 0.685283075845186 |

The primary estimand remains incomplete. Arithmetic agreement neither converts
it into a passed test nor supplies evidence of equivalence or non-inferiority.

## Interpretation and next milestone

The checks do not support two candidate explanations: an identity/provenance
join error and a score/aggregation error. Consequently, the reported lack of an
established gain and the signed prediction discrepancy cannot be dismissed as
those simple implementation mistakes.

M8A is deliberately silent on causal alternatives. M8B next decomposes clean
baseline, injected calibration, prediction, and test behavior; audits temporal
alignment, transition-relative outcomes, timeouts, and semantic failures; and
examines topology examples plus current-parser replay on the four retained raw
samples. Those analyses remain post-M7 diagnostics and cannot retroactively
become confirmatory M7 evidence.

## Completion checks

- All 165 M7 artifacts were present and unexpired.
- All 160 expected qualified identities and the four raw samples were retained.
- A new 90-day combined evidence artifact was published.
- All five frozen analysis table hashes matched.
- All 36,459 score rows and 117 summary rows matched independent arithmetic.
- The primary campaign count, weighting, estimate, interval, and p-value matched.
- No M7 prediction, score, inclusion rule, or result was overwritten.
- Unresolved causal explanations remain explicitly unresolved.
