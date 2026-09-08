# M9X: independent PMX with observed caller context

Iteration 003 question: does a full observed caller path prevent finite native traces from becoming recursive operation-level SEFFs, while preserving every request/span/time/error and native PMX estimation? Expected result: new structural/numerical controls pass, an unchanged cyclic negative case is explicitly retained, and all 12 historical application operation cells yield qualified probabilities or exact unsupported reasons. This protocol is frozen before this run, on already opened development data.

## Evidence motivating the change

Original M9V run 34191216681 retained 24 abstentions: DeathStar has native 16-hex trace IDs rejected by the old fixed-32 parser; OTel already has valid IntPMF loop expressions rejected by the integer-only bridge. Retained audit 34192089947 proved exact native identities and valid loop encodings. Recovery 34192728551 fixed those representations without re-extraction, but the first OTel model raised an uncaught StackOverflowError, stopping remaining cases and all second passes. Fourteen first-pass records remain; none is promoted as a completed two-pass forecast.

Read-only audit 34193396638 (head 7bd0a1394fd350d0129b3bf244222700364b22e9) found cycles in all six OTel operation graphs and none in six DeathStar graphs. Full observed context counts were 8/13/48 for OTel browse/cart/checkout versus 5/9/22 merged operations. The cycles include repeated frontend operation labels along native ancestor paths. This is a concrete representation hypothesis, not a conclusion about all Palladio capabilities.

## Context version and preserved semantics

`observed-full-caller-context-v1` appends the complete root-to-span sequence of existing M9U operation identities to the operation identity, using a deterministic 24-hex digest. Component/instance identities, all trace/span IDs, parents, timestamps, native and external errors, native audit records, request membership, and external outcomes remain unchanged. A restoration check verifies byte-value equality of all envelope fields except operation names. Original identities and full caller paths remain in mapping records.

Each edge adds exactly one path element, proving the extracted operation graph should be acyclic if PMX preserves the checked identities. Repeated sibling invocations share a context and retain their multiplicity. Different contexts receive their own observed call/error frequencies, so this is an explicit change of aggregation, not a claim that all old probabilities are preserved. No application success function, our inferred graph, or our fitted probability is supplied to PMX.

The original inclusive PMX parameterization remains `PMX_inclusive` with the explicit adapter version. Its inclusive parent/child overlap is disclosed; independence is not established. `PMX_conditional_local` is separate and refuses contexts with swallowed child errors or zero conditioning support. Error flags are never repaired from predicted results. The external wrapper is synthetic, uses an additional observed calibration endpoint outcome, and is charged as such.

M9V's calibration projection is reused exactly as the source. Original comparator predictions and learner inputs remain unchanged, with original source hashes. No new original-method fit, raw native parse, acquisition or evaluator access occurs during preparation/extraction/freezing. Historical evaluation happens in a later job after candidate sealing; these previously opened observations remain development.

## New bounded controls

- Finite native recursion: wrapper succeeds .8, native parent .8 and same-named child .9, sibling 1. Inclusive oracle .576; conditional-local oracle .8. Context splitting must preserve exact input inventory and produce finite operations.
- Cross-trace call ordering: native A calls B in five requests; B calls A in the other five; all succeed. The merged graph is cyclic but each trace is finite. Both parameterizations have oracle 1.
- Negative finite-recursion projection: the original same-named projection is extracted without context splitting and solved first. It must yield two explicit `java.lang.StackOverflowError` records, not zero availability, while later cases and both passes complete.

All 15 PMX invocations (three artificial cases plus 12 application operations) retain reference-resolved structural/error/entry checks and exact trace/span/parent/time inventories. The four positive artificial models are solved twice: eight oracle passes at 1e-12 are required. The unchanged cyclic negative model is solved twice and must reproduce the declared exception. All 16 positive M9S and 44 M9U controls are reused through pinned acceptance, not repeated.

The pinned analyzer code, target platform and numerical settings remain unchanged. A separate `PmxContextBridgeTest` copies the generic harness and adds only per-case StackOverflowError retention plus an exact stack-trace file. Each model receives a fresh load/transform object; no replacement probability is assigned. Successful forecasts need two finite, agreeing [0,1] results, success+failure=1, full physical-state mass 1 and complete state evaluation. All unsupported/error/missing cases remain in the census.

## Freeze, costs and completion

Workflow command: `gh workflow run m9x-pmx-context-comparison.yml --ref <frozen-commit>`. The config locks source files and exact retained artifacts. All jobs use timeout 360 minutes; native inputs, models, failed records and logs are uploaded for 90 days. Locally inspect only compact reports; full application input/model work remains in GitHub Actions.

Report context-adaptation time, source and output sizes, PMX invocation time/peak RSS, cold analyzer build, load/solve timings, and manual integration actions. Unmeasured engineering minutes are unknown, not zero. This is development correction cost, not a fresh monitoring-overhead measurement.

Completion is a 12-operation forecast/absence census, independent errors against historical external outcomes, paired coverage and cost records, plus C01-C22. Green jobs alone are insufficient. Successful control qualification does not complete the new three-application 240-campaign study. Petclinic and that prospective series follow the accepted author correction plan.
