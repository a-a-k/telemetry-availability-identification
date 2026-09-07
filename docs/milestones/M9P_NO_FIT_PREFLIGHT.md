# M9P: separate no-fit temporal-confirmation preflight

Status: preflight complete; main confirmation is a separate pending run.
Accepted run [34115470738](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34115470738)
completed on its first attempt at commit `b9dcd201b8817da310007efe2258734f55d99d3d`. It is the
second preflight dispatch, following a retained configuration-byte failure.

## Accepted result

All four prescribed OpenTelemetry cells (colocated/split by N/ND, repetition
zero) passed fresh acquisition, ordinary quality checks, native evidence
qualification and physical learner/evaluator separation. The final audit reports
`no_fit_preflight_passed`, four cells, zero model fits, zero comparison scores
and zero main-effectiveness observations. These observations are excluded from
confirmation. No predictive accuracy is inferred from this preflight.

Each cell ran the frozen 60-second baseline and two 900-second periods with the
four-request-per-second mixed-operation driver. Each source census was checked
for all 7,440 requests, unique execution-qualified identities and correct period
membership. The namespace was
`m9p-temporal-preflight-v1-run34115470738-a1`, with preflight root 2026090702.
The checker verified every factor-specific calibration/test renewal seed,
workload seed, source/commit and fresh period timestamps. The original pinned
benchmark and image inventories passed their acquisition checks.

| Cell | Learner rows | Calibration health ticks | Qualification seconds | Raw native trace bytes |
|---|---:|---:|---:|---:|
| colocated / N | 3,840 | 900 | 3.978 | 234,311,234 |
| colocated / ND | 3,840 | 900 | 4.933 | 227,890,709 |
| split / N | 3,840 | 900 | 3.732 | 235,223,883 |
| split / ND | 3,840 | 900 | 4.075 | 223,732,165 |

The row counts cover all three driver operations; they are not checkout-only
fit sample sizes. No adequacy-driven change to the main design was made.
Native trace qualification remains an acquisition cost even though the temporal
predictors' sanitized inputs contain no native trace graph.

## Retained initial failure

The first dispatch, [34114926121](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34114926121),
used commit `718267efc34b883e4df2b36a4effdbecf68d91ee`. All four cells stopped
at repository-lock validation before entering the experimental driver. Git's
text normalization had changed the copied M9O campaign CSV from 8,250 CRLF
bytes to an 8,129-byte LF blob. The identity matrix contents and statistical
design were unchanged, but the required byte identity correctly failed.

Commit `0dc4ea1497bb966f71ff52b0a8712404fea46916` added a path-specific
`-text` attribute and earlier validation. Commit
`b9dcd201b8817da310007efe2258734f55d99d3d` forced the original CSV bytes into
the Git index. Every locked file was checked against its actual staged Git
blob before the accepted dispatch. The restored matrix SHA-256 is
`ceb54a1600049e464c2002a71a905c00bb013793fa4494a7a84bdf6b430d685e`,
identical to the accepted M9O artifact.

All four first-dispatch diagnostic archives were retained and downloaded for
preservation. Their inventory contains zero `requests.csv` files, zero campaign
manifests and zero planned schedules. The repaired dispatch uses a new run ID;
no failed-run source or observation is substituted into the accepted four cells.
The failed CI runs and both repair commits remain in public history.

## Run and artifacts

The accepted run began at `2026-09-07T11:12:59Z` and completed by
`2026-09-07T11:48:03Z`. All five jobs have 360-minute limits.

| Job | Conclusion | Elapsed seconds |
|---|---|---:|
| preflight / colocated / N | success | 2055 |
| preflight / split / N | success | 2073 |
| preflight / split / ND | success | 2061 |
| preflight / colocated / ND | success | 2066 |
| Audit four-cell no-fit preflight | success | 23 |

All 17 artifacts were unexpired on verification. The 12 separate learner,
evaluator and acquisition-audit bundles and the final no-fit audit retain
90 days, through 2026-12-06 11:13:01 UTC. The four raw preflight sources retain
seven days. The digests below are GitHub archive metadata; the extracted final
audit was separately byte-hashed.

| Artifact | ID | Compressed bytes | GitHub SHA-256 |
|---|---:|---:|---|
| `m9p-no-fit-preflight-34115470738-a1` | 10017208173 | 2,397 | `50e0a4f124cf183e1b934b6fed6a01af20db1cc6ebcf6c44b7f0aa42234b9eb3` |
| `m9p-preflight-audit-colocated-N-34115470738-a1` | 10017173129 | 16,470 | `987668aaedc688ce3f9d8f35500196945ebbaff80ba12aad8d0283569e164535` |
| `m9p-preflight-audit-colocated-ND-34115470738-a1` | 10017177168 | 17,417 | `03efab2181efaebcd4ccea51ae9103d0535ae9d70194c674de0c1865107624aa` |
| `m9p-preflight-audit-split-N-34115470738-a1` | 10017181665 | 16,635 | `bea00aba192e8ce940dd9f54f28853b806047f2e13c08394b1fe32a36406fd93` |
| `m9p-preflight-audit-split-ND-34115470738-a1` | 10017176116 | 18,708 | `22e2e86174c5687baf15eddc18abaaf0342670811ea2d2365b6fdbdadb8fbe5c` |
| `m9p-preflight-evaluator-colocated-N-34115470738-a1` | 10017172640 | 67,986 | `0c4d0419880e02ebb7387a20a6f4a878b02d2f14137231e59cf707bf11141dea` |
| `m9p-preflight-evaluator-colocated-ND-34115470738-a1` | 10017176713 | 68,188 | `4cd2ee8ecb1c758a719b1e9cbf7123fd79f0345555a28944f2d93fac8067cf2a` |
| `m9p-preflight-evaluator-split-N-34115470738-a1` | 10017180974 | 68,257 | `1e95af7b42cdee64f10f85354eeb43f4f346cc495b173f7769b658d14889b031` |
| `m9p-preflight-evaluator-split-ND-34115470738-a1` | 10017175701 | 67,917 | `455182b45484722f3a1b8c502c868a8e9b9672329a302b4bd0c85be4518067a4` |
| `m9p-preflight-learner-colocated-N-34115470738-a1` | 10017172048 | 72,115 | `85a2b8bb849e614ff9ff8bc3fcdd93a166b0213e181050735f99f4e6137ca053` |
| `m9p-preflight-learner-colocated-ND-34115470738-a1` | 10017176258 | 72,760 | `9a0189aaa6e6ed5975e883636eb4ba84e51b2ec2bcc3a8b222f5ffa327ac541e` |
| `m9p-preflight-learner-split-N-34115470738-a1` | 10017180279 | 72,164 | `1ee9bbc5ab9d055d12956c4d71d6c32395e1f6125c5a8b910d0c8d9bf4bad80e` |
| `m9p-preflight-learner-split-ND-34115470738-a1` | 10017175373 | 72,418 | `95259c8addfb3753ef0900719dce3cd10629effcd52585f8f995f4ad89ea0371` |
| `m9p-preflight-raw-colocated-N-34115470738-a1` | 10017171519 | 19,420,484 | `437f2a5e8421ca1fdeee841f70b5e107f525fd5d80836490e3792892d7787d50` |
| `m9p-preflight-raw-colocated-ND-34115470738-a1` | 10017175681 | 18,892,382 | `f4c51bf335991b64809f245d82b0085d30dcd9bdba7fdc94f7a10d3749927776` |
| `m9p-preflight-raw-split-N-34115470738-a1` | 10017179622 | 19,511,513 | `78ad86ee765040c17d0f987766ce577f26ca5a896eb9ae30d33353f1516b917a` |
| `m9p-preflight-raw-split-ND-34115470738-a1` | 10017174918 | 18,524,652 | `4d8a3442064c39818a3b730b0198eaa4eb1683aa414ced46b553f3b6fed643cf` |

The final `preflight-audit.json` has 10,513 bytes and SHA-256
`84a768eb1d831667de2671a380154df9b32df8d4ea7c4cc57466ecfd0bf1ba49`. It links acquisition implementation SHA-256
`9a01133853e0238e3df12bb4248503a9d95c5bd13a5adcc7e326caf50ea529a6` and configuration SHA-256
`b11965da68f02b97fc3dac7c6a162807779a205f4a95efa696a70283422944ec`. The main acceptance file freezes these
identities and the reviewed implementation hashes.

Only the generated no-fit audit and GitHub metadata were opened locally for
acceptance; prospective learner and evaluator bundles were not downloaded.
No live experiment, full data fit or full matrix scoring ran locally.

## Main implementation and next execution

The implementation follows `M9O_TEMPORAL_CONFIRMATION_PROTOCOL.md` and
`M9P_TEMPORAL_CONFIRMATION_PROTOCOL.md`. It freezes 120 fresh campaigns, new
root 2026090701 and analysis root 2026090703; the three Bonferroni-adjusted
quantities and all per-cell adequacy and optimizer gates remain unchanged.
The primary midpoint logit is compared with the matched state-only model;
matched stable endpoint, all-calibration endpoint, 500 ms reference and age
sensitivities remain descriptive controls. Every parameter is refitted on
new learner data before any evaluator download.

Before main collection, 241 tests passed, including a four-cell synthetic
serialization/evaluation check, missing-matrix and evaluator-access rejection,
paired campaign inference, whole-interval decisions, optimizer gates and
artifact retention/identity checks. CI run 34117708184 passed on the final
main-code scheduling revision. The five-job main workflow includes a readiness
gate that rechecks the accepted preflight and exact implementation. Its matrix
interleaves intended stratum submission at at most 20 concurrent acquisitions.
Nominal acquisition cost remains 62 runner-hours, excluding setup and audits.

`M9P_CALIBRATION_IDENTITY.md` records an algebraic explanation of why a temporal
curve can improve conditional predictions without changing the calibration-
weighted marginal mean. This is not a finding about the unobserved new scores.
`PMX_APPLICATION_INPUT_CONTRACT.md` records a read-only inspection of the
already retained PMX source; there was no further PMX execution or new-data fit.

The next action is the frozen main confirmation workflow. Its full native
sources will be preserved for all 120 successful cells for 90 days, and all
three inferential quantities will be reported regardless of sign. A failed
adequacy gate or incomplete campaign matrix prevents a confirmatory claim.
An independently parameterized PMX comparison and article-wide accuracy/cost
claims remain separately unresolved.
