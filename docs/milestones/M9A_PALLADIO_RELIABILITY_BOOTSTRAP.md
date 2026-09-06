# M9A: pinned Palladio reliability bootstrap

## Outcome

M9A is complete as an integration and correctness-bootstrap milestone. The
accepted remote workflow built the official Palladio reliability analyzer
5.2.2 from commit
`a694e570afb705dc9e0470dc321e77b7219dcea4`, audited the corresponding
versioned Palladio Bench product, and executed the official `ReliabilityTest`
model twice through Palladio's own `Pcm2MarkovStrategy` implementation.

Both executions returned success probability `0.375`, failure probability
`0.625`, and total physical-state probability `1.0`. They agreed exactly with
each other and with an independent formula extracted from the pinned PCM XMI.
This establishes a working, commit-pinned Palladio execution boundary for the
next controls. It does not compare Palladio with the telemetry-driven method,
validate an M7 mapping, or change the interpretation of M7.

The current scientific position therefore remains unchanged: the published M7
calculations establish no predictive gain and disagree with observations, but
their causes are not understood well enough to declare the overall approach
successful or failed.

## Frozen inputs and implementation

- analyzer repository: official `Palladio-Analyzer-Reliability`;
- release/tag: `releases/5.2.2`;
- analyzer commit:
  `a694e570afb705dc9e0470dc321e77b7219dcea4`;
- official examples commit:
  `4a8dc455216774435fefd42965b848851f7658ee`;
- example project: `ReliabilityTest`;
- official Linux product: versioned Palladio Bench 5.2.2 archive;
- product size: `290,508,238` bytes;
- product SHA-256:
  `c3a91f0e3a17036d7a7561f9cc49bfa142cbc8f075db5bc6dcb6a439df9749f4`;
- runtime: Temurin Java 17 on GitHub-hosted Ubuntu;
- all three workflow jobs: `timeout-minutes: 360`;
- full Palladio build and execution: GitHub Actions only.

The test harness uses Palladio's normal model-loading jobs, constructs a
`PCMInstance`, and invokes `Pcm2MarkovStrategy`. Python does not reproduce or
replace the DTMC solver. The only analyzer-checkout overlay is the recorded
JUnit harness and its bundle manifest. The independent source-build job has no
harness overlay.

## Historical target-platform reconstruction

The first remote attempt exposed a mutable transitive build input. The
published Maven target
`palladio-target-platforms:0.1.0:palladio-2023-03` refers to MDSD Ecore Workflow
through `releases/latest`. At the Palladio 5.2.2 product cutoff, the latest
MDSD release was 1.0.0 and required JavaSE-17. In September 2026 the same URL
resolved to 1.2.0, which requires JavaSE-21, so the historical Java-17 target
could no longer resolve.

The accepted workflow reconstructs rather than hides that dependency state:

- it downloads the original 5,194-byte Maven target and requires SHA-256
  `2ac99cc862e5142a0fa88294b8c5d474ea19a4e7ed4bf8cb2c634ad37a6c6fd2`;
- it replaces exactly one `releases/latest` URL with
  `releases/1.0.0` in an isolated Maven cache;
- it requires reconstructed-target SHA-256
  `4d4a1b0c3fe1bc37512baab9ca52e7b834f012157ed539f9ec8cace015df105c`;
- it independently hashes the pinned `content.jar`, `artifacts.jar`, feature
  JAR, and bundle JAR before Maven runs;
- it verifies that the analyzer Git checkout remains unmodified.

This is an audited external dependency lock. It is not a change to analyzer
logic and is retained in both Java-job artifacts.

## Diagnostic history

The rejected iterations are retained because each isolates a distinct
integration assumption.

- [Run 34018649576](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34018649576)
  rejected the initial bootstrap. Both Java jobs stopped during target
  resolution because mutable MDSD 1.2.0 required JavaSE-21. The product job
  exposed a separate auditor error: the official product stores its feature as
  an exploded directory, not a feature JAR.
- Commit
  [`030cd637a13966dce2f0c8ef8603020963a92019`](https://github.com/a-a-k/telemetry-availability-identification/commit/030cd637a13966dce2f0c8ef8603020963a92019)
  added the historical dependency lock and accepted both Eclipse feature
  packaging forms.
- [Run 34019587324](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34019587324)
  then passed the independent source build and product audit. The example job
  reached test execution but was rejected because the headless runtime did not
  include Palladio's standard `org.palladiosimulator.pcm.resources` bundle;
  consequently `pathmap://PCM_MODELS/PrimitiveTypes.repository` was unresolved.
- Commit
  [`b660de3ecf61659f21ce982fd87bdfebcd183f2c`](https://github.com/a-a-k/telemetry-availability-identification/commit/b660de3ecf61659f21ce982fd87bdfebcd183f2c)
  added that stock resource bundle to the harness runtime without changing a
  model or solver.
- [Run 34020007973](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34020007973)
  was the successful discovery run. It produced the product hash above and
  `0.375` in both solver repetitions; neither value was yet an acceptance
  criterion.
- Commit
  [`28b8b9f168f68edfb441a093009f2a48058eba78`](https://github.com/a-a-k/telemetry-availability-identification/commit/28b8b9f168f68edfb441a093009f2a48058eba78)
  froze the product hash and independently derived example probability.

No rejected run contributes a result to the accepted M9A evidence.

## Accepted execution

The acceptance workflow was
[run 34020529869](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34020529869)
at commit `28b8b9f168f68edfb441a093009f2a48058eba78`. It completed with all
three jobs successful:

| Job | Result | Wall time reported by GitHub |
|---|---|---:|
| Product hash and inventory | Passed | 52 s |
| Pinned source build | Passed | 5 min 0 s |
| Official example, two solver calls, and independent audit | Passed | 5 min 23 s |

The matching two-version repository CI was
[run 34020529506](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34020529506),
also successful. Locally, all 118 unit tests passed; no Palladio build or model
execution was run locally.

The accepted source build produced the 5.2.2 reliability feature and solver
bundle. The solver bundle was 188,575 bytes. The official product contained the
exploded 5.2.2 feature descriptor, the exact 5.2.2 solver bundle, and eleven
inventoried non-source reliability files.

## Official-example result and independent oracle

The official repository model contains a sequential initial internal action,
then a recovery action with one primary behaviour and one failure-handling
alternative. The initial, primary-recovery, and alternative-recovery internal
failure probabilities are each `0.5`. The alternative explicitly handles the
primary behaviour's failure type. Therefore the independently parsed oracle is

`(1 - p_initial) * ((1 - p_primary) + p_primary * (1 - p_alternative))`

or `0.5 * (0.5 + 0.5 * 0.5) = 0.375`.

| Quantity | Repeat 1 | Repeat 2 | Required |
|---|---:|---:|---:|
| Success probability | 0.375 | 0.375 | 0.375 |
| Summed failure probability | 0.625 | 0.625 | 0.625 |
| Success + failure residual | 0 | 0 | at most `1e-12` |
| Physical-state probability | 1.0 | 1.0 | 1.0 |
| Evaluated / total physical states | 1 / 1 | 1 / 1 | complete |

The five PCM inputs were also hashed. In particular,
`default.repository` was 5,394 bytes with SHA-256
`8e28b541a6293dd6bb290b146ba63b0b837f36c4cd46edb31d5cc08e31d093a9`.
The complete five-file inventory is in the retained example manifest.

## Accepted artifacts

| Artifact | ID | Compressed bytes | Artifact digest | Retained through |
|---|---:|---:|---|---|
| `m9a-palladio-product-audit-34020529869` | 9985339179 | 1,466 | `sha256:c2dd604a19710f54774d4aa8557681489cd27998b8b88d914c14a72fdd4aa458` | 2026-12-05 |
| `m9a-palladio-source-build-34020529869` | 9985399751 | 71,604 | `sha256:2e81700f3f187209d03360c7a68edc1f896540d7b1807a5bbd09ee1121deaa34` | 2026-12-05 |
| `m9a-palladio-official-example-34020529869` | 9985402480 | 82,633 | `sha256:20955050246eff09ff208b37d6df3c5bc7c03eba5d44dc9e3cf96b21328fbc04` | 2026-12-05 |

The source build consumed 4:15.02 measured wall time and peaked at 1,673,960
KiB resident memory. The example build and execution consumed 4:36.08 measured
wall time and peaked at 2,763,132 KiB. Both exited with status zero and no swap.

## Interpretation and limitations

M9A establishes four things: the selected released analyzer code builds under
an explicit historical dependency state; the released product is byte-pinned
and contains the expected reliability components; the official model can be
loaded in a headless CI environment; and its solver output matches a simple
independent oracle exactly and repeatably.

It does not establish Palladio correctness in general. The official example has
one physical state and a small recovery tree. It does not exercise replicated
paths, shared failure domains, communication failure, conditional execution, or
the telemetry-to-PCM mapping needed for comparison. Those are M9B controls.

The Tycho-built JAR SHA-256 values differed between otherwise identical
discovery and acceptance builds even though the solver bundle size was stable.
M9A therefore makes no bit-reproducible-source-JAR claim; the accepted-run hashes
identify its artifacts, while the official binary archive has the independent
committed byte pin. The cause of the packaging-level hash variation was not
needed for the semantic bootstrap and is not silently interpreted as a solver
difference.

Most importantly, M9A supplies no evidence for changing M7. The next milestone
must validate Palladio semantics on independently constructed, hand-checkable
controls before any aligned comparison with the telemetry-driven estimators.
