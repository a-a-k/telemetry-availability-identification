# H-EXEC-01: complete qualification on final immutable archives

The [final-input audit, run 34238008817](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34238008817), at commit `88b9d0065f064a2fa130d185435e3d34cef2cca8`, qualifies **all 32 original study cells** under the unchanged H-EXEC criteria. Both predeclared primary contrasts and the required diagnostics pass. This supports H-EXEC within the registered application, intervention and operation contract; it does not establish a general model's accuracy.

## Original failure and correction

The acquisition remains [run 34230603338](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34230603338), commit `3477c79c5ca0037979a146346c6b49b6215bac57`. Its [original report](H_EXEC_01_ORIGINAL_STUDY_GATE.md) qualified 31/32 cells and withheld confirmation because repaired block 4 / slot 1 reported one malformed native JSON record. All 34 original compact archives and that failed gate remain preserved.

The collector was still appending during original compact parsing and was stopped before raw artifact upload. The [separately frozen audit](../H_EXEC_SEALED_INPUT_AUDIT_V1.md), configuration SHA256 `0b88f8750c47402c7bc8e256217c1383dc6e58be7d51d68158a052c92d625946`, restores all 32 final raw archives remotely and invokes the unchanged parser, qualification checks and primary statistic routine. It uses the original scientific configuration SHA256 `a78b1070488f80505b368f44d5b7ed5d229b1c29bc4fe685cd00ba35c6b94500`.

Every final native file parses without malformed records or invalid selected traces. All 32 native hashes differ from the hashes recorded after original live parsing. For the failed cell, the recorded native SHA256 changes from `220068fda0759d5ec691c89696cefad5134f2d9628dc0ba8981d31563482c25d` to final archive SHA256 `f67c20b419917762fa5c39be67bf595ebe8ba17dae34aef1fce10d91c222da7d`. This establishes that the earlier analysis and final archive did not share an immutable native snapshot. An incomplete line during concurrent append remains a plausible explanation; the exact bytes seen by the original parser were not retained, so its precise failure cause is not proven.

All originally hashed non-native inputs (requests, health, proxy routes, boundaries and interventions) match the final uploaded bytes exactly. All 15,360 request census rows match field for field, including native span counts. Only the failed cell's `native_parser_clean` check changes from false to true. Every input remains unchanged throughout replay. No attempt, cell, threshold, intervention, seed, statistical method or independent sample size changes. Before any future H acquisition is reused, its separately versioned workflow must stop/snapshot the collector before parsing.

## Registered results

Eight blocks each contain sham, transition, settled and repaired fresh deployments. The final analysis includes all 32 cells, 15,360 business attempts and 1,920 static controls. The measured test periods contain 3,840 business attempts, including 1,280 checkout attempts, and 480 static controls. The earlier four-arm technical qualification is excluded from inference.

| Co-primary checkout contrast | Mean difference | Exact two-sided label-swap p | Registered result |
| --- | --- | --- | --- |
| Sham minus settled | +100 percentage points | 2/256 = 0.0078125 | Passes alpha 0.025 and minimum 5 percentage points |
| Repaired minus settled | +100 percentage points | 2/256 = 0.0078125 | Passes alpha 0.025 and minimum 5 percentage points |

Each contrast has eight identical block differences of 1. The registered 10,000 paired-block bootstrap therefore returns the display interval [1, 1] at 97.5%; that degeneracy does not establish an exactly 100-point population effect or guaranteed finite-sample coverage. All primary differences, p-values, intervals and seeds exactly reproduce the original calculations. The qualification change makes `confirmed_within_design=true` for both contrasts and `scoped_h_exec_support=true`.

The settled arm keeps replica a paused while replica b remains ready. All 320 measured settled checkout attempts fail and have replica a in their recorded routes, in all eight blocks. The repaired arm keeps the same pause but disables routing to a; its 320 checkout attempts succeed, as do all 320 sham attempts. Thus, the retained live alternative alone is insufficient for this operation's timely success under the tested routing policy; the routing intervention restores success within this design. This does not identify a causal mediation fraction or imply independent replica selection on each call.

Static controls succeed 120/120 in each arm, satisfying the predeclared diagnostic tolerances. This is not a statistical equivalence claim. Secondary browse and cart differences remain descriptive: sham/repaired minus settled are 40.9375 and 40 percentage points, respectively; no secondary replaces a primary. The final audit exactly preserves every secondary, static and route diagnostic.

## Scope and retained evidence

The result tests one mechanism on modern OpenTelemetry Demo under the declared whole-operation 2-second contract. It does not establish the cause or explained fraction of historical ICSE/AINA errors, select a second hypothesis or model refinement automatically, prove novelty, or qualify the final G*. Independent PMX/main comparison, final model bindings, transfer and full cost analysis remain separate obligations. Main campaigns, new independent campaigns in this replay, PMX invocations and model fits are all zero.

Two exact compact archives total **1,094,084 bytes**, with 292 member hashes, in [verified archives](../evidence/h-exec-sealed-audit-34238008817/verified-archives.json):

- Audit artifact `10060803278`: 20,088 bytes, SHA256 `8d7ac9731a9bb501dbe124e4cb3cf736e1ab1bb1c2a677042bbc3e00fd2f9872`; four reports expanded for review.
- Recomputed compact artifact `10060804875`: 1,073,996 bytes, SHA256 `87378f24fc03d2002e54667cf61d8de9f6ed2bdb89e9e70a17ceef2692c1d59d`; all 32 cells and 288 compact members retained in the exact ZIP.

Full native/raw archives were interpreted only in GitHub Actions and remain remote. The audit process used 132.41 seconds wall time, 48.03 seconds user CPU, 2.73 seconds system CPU and peak RSS 199,464 KiB. These are audit costs, not prospective model or monitoring-overhead measurements. Remote artifact retention is 90 days; a durable final raw-data archive remains a publication-package obligation.

The [complete audit summary](../evidence/h-exec-sealed-audit-34238008817/audit/files/replay-audit-summary.json), [cell audit](../evidence/h-exec-sealed-audit-34238008817/audit/files/cell-audits.json) and [qualified analysis](../evidence/h-exec-sealed-audit-34238008817/audit/files/study-analysis.json) retain source and replay identities separately. [Iteration 031](../iterations/031-h-exec-sealed-study-confirmation.md) records all 30 v3 criteria.
