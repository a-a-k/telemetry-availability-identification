# M9F: PMX performability reproducibility and semantic-fit audit

## Status

Complete. The accepted recovery run produced a valid diagnostic decision:
the byte-pinned public PMX binary route was not reproduced under the tested
standalone launcher contract. This is not a failure classification for PMX as
a method or for Palladio as an ecosystem.

## Question

M9F tests whether the later headless OpenTelemetry PMX performability route can
be reproduced from its public paper, source lineage, demonstration, embedded
source snapshot, and binary, and which availability-relevant PCM semantics it
actually derives. It does not test Retriever, score accuracy, read M7 evaluator
outcomes, or authorize a new live collection.

Missing application support is classified as integration or application cost.
It does not cancel PMX's scientific priority. Evidence from this pinned binary
does not represent every PMX or Palladio artifact.

## Frozen implementation

- Initial protocol commit: `e1600a63271e9b2c80b73779aa7714685a1c4c0d`.
- Runtime-amendment commit: `e3bfdfb5415d79007cce874181b274a10d62b433`.
- Workflow: `.github/workflows/m9f-pmx-performability-audit.yml`.
- Frozen config: `configs/m9f_pmx_performability_audit.json`.
- Protocol: `docs/M9F_PMX_PERFORMABILITY_AUDIT_PROTOCOL.md`.
- Runtime amendment: `docs/M9F_RUNTIME_AMENDMENT.md`.
- Implementation: `src/telemetry_availability/pmx_performability.py`.
- Local verification before recovery: 156 tests and 12 subtests passed; the
  workflow parsed as YAML, its execution script passed `bash -n`, and exactly
  three jobs had `timeout-minutes: 360`.

The audit byte-pins the 244,692-byte paper; two historical Git commits and eight
canonical blobs; GitLab project 50, commit
`9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2`, historical pipeline 1120, and its
eight published files; and the 65,729,095-byte PMX JAR with SHA-256
`befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`.
The JAR audit checks seven PMX bundles and seven embedded Java-source contracts.

Two conditions run twice: the unchanged authors' customer trace and an otherwise
identical trace with one predeclared `error=true` tag among ten eligible
`VisitResource.read` occurrences. The latter has the hand-computable mechanism
oracle 0.1; it is not an accuracy observation.

## Superseded runtime attempt

Run `34040388551` at the initial protocol commit passed provenance. Its first
direct JAR process did not return during 1,238 observed seconds, so the run was
cancelled before inventory and before any generated PCM result was available for
inspection. It is retained as a launcher/watchdog design failure, not evidence
against PMX or Palladio.

The pre-result runtime amendment retained all scientific inputs and rules, added
the logging selector from the JAR's embedded start script, a 900-second watchdog,
and 30-second progress records for every invocation.

## Accepted remote execution

The accepted candidate is GitHub Actions run
[`34041926658`](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34041926658),
attempt 1, at runtime-amendment commit
`e3bfdfb5415d79007cce874181b274a10d62b433`. It started at
`2026-09-06T15:19:12Z` and completed successfully at
`2026-09-06T16:20:22Z`.

| Job | Start (UTC) | Finish (UTC) | Conclusion |
|---|---:|---:|---:|
| Audit paper, source lineage, demo, and containers | 15:19:16 | 15:19:57 | success |
| Run pinned headless PMX and one-in-ten control | 15:19:16 | 16:19:59 | success |
| Classify reproducibility, semantic fit, and application cost | 16:20:02 | 16:20:21 | success |

The green workflow conclusion means that the predeclared diagnostic completed
and retained a classified negative execution result. It does not mean that PMX
extraction succeeded. All three jobs used `timeout-minutes: 360`; the four PMX
invocations were separately bounded at 900 seconds.

The three 90-day artifacts were downloaded and inspected after completion:

| Artifact | GitHub ID | Compressed bytes | GitHub SHA-256 digest |
|---|---:|---:|---|
| `m9f-pmx-contract-34041926658` | 9991938135 | 7,309 | `1add5b521b4ddb80e69e7c842fb4946906133a6b85fcaa9ebd7eb667670656e1` |
| `m9f-pmx-probe-34041926658` | 9992841811 | 250,869 | `5f14bef49a5e7fd4c81425deb54d8a0714a2dd4b2eee884dcf53801239eef09d` |
| `m9f-pmx-decision-34041926658` | 9992847754 | 5,565 | `40753e982dc2658fe60b474074ec33c70e08cb34d2083288d359fde71ac121ab` |

The accepted decision manifest is internally linked to configuration SHA-256
`c7eece0639b5d41e57173595021a23ffeaaca93475adad637a079fdadd992c40`,
contract-manifest SHA-256
`58ddea0631c621ba8c6a7440307f6b3b26cba3eae344cdaf1c1a8daf7d908fdd`,
and probe-manifest SHA-256
`8c806fb05778f173af912ab52c78ab2ea782a3690360ce6d59ecb19555bbbb28`.

## Results

### Provenance and reproducibility strata

The contract job matched the paper's frozen 244,692 bytes and SHA-256, all eight
historical-source records across two exact commits, and all eight files from the
demonstration commit. Public metadata still records pipeline 1120 and its `pmx`,
`palladio`, and `gnuplot` jobs as successful at the expected commit.

The later JAR matched its 65,729,095-byte identity, outer manifest, 147-entry
inventory, seven embedded bundles, seven embedded Java-source contracts, and
PCM 5.1 bundle identity. The audited JAR contains no top-level standalone build
descriptor, so the later source snapshot is inspectable but not rebuildable from
that artifact alone. The historical container references are mutable `latest`
tags with no retained historical digest; the exact historical container chain
is therefore not recoverable from the published metadata. These are separate
reproducibility strata rather than evidence that the historical run did not
occur.

### Headless executions

| Condition | Repeat | Exit | Elapsed (s) | Result files | PCM model files |
|---|---:|---:|---:|---:|---:|
| published original | 1 | 124 | 900 | 0 | 0 |
| published original | 2 | 124 | 900 | 0 | 0 |
| one-error control | 1 | 124 | 901 | 0 | 0 |
| one-error control | 2 | 124 | 900 | 0 | 0 |

Every invocation produced the same 27-byte stdout:
`osgi> gosh: stopping shell`. From 30 seconds through 870 seconds, every
heartbeat retained the same stdout length and zero result files/bytes. Each
process used only 6.93--7.36 seconds of user CPU over 15 minutes, no tool
`log.txt` appeared, and neither exception nor `MAJOR_ERROR` markers were seen.
Peak resident memory ranged from 214,976 to 262,452 KiB. The result is exactly
repeat-consistent, but only because all four runs reached the same inert state.

The frozen binary-extraction gate consequently failed: exit zero, the complete
PCM suffix set, and generated parseable models were all required. The 0.1
one-in-ten operation-failure mechanism was not tested through generated PCM and
both control checks are false. It would be incorrect to treat the absence of an
observed 0.1 parameter as contrary evidence about the transformation when the
transformation was never reached.

### Semantic-fit classification

None of the eight target dimensions is marked demonstrated by this execution.
This includes trace ingestion, operation flow, software operation failure,
host lifecycle, communication failure, replication, common failure domains,
and external-client success. That classification means "not demonstrated by
the generated output of this run", not "absent from all PMX/Palladio tools".

The embedded-source audit remains informative for recovery and application
cost: it exposes the error-tag probability rule, a zero-default network mapping,
and no extraction of MTTF/MTTR in the audited snapshots. Application work would
still be required for the M7 trace adapter, source-grounded operation graph,
host/domain lifecycle, communication failures, interchangeable replicas and
failure domains, and the external-client success contract. Every such row is
classified as application/integration cost and explicitly retains PMX's
scientific priority.

## Interpretation and next milestone

The accepted decision is
`pmx_public_binary_execution_not_reproduced`, with next milestone
`m9g_pmx_recovery_and_application_adapter_dual_track`.

The evidence localizes the immediate problem before trace parsing: the process
enters or tears down an OSGi Gogo shell, becomes almost CPU-idle, emits no PMX
log, and writes no result. The strongest current hypothesis is therefore an
entry-point, launcher-argument, or OSGi application-start contract mismatch in
the standalone invocation. It is a hypothesis to test in M9G, not yet a root
cause. M9G must audit the embedded launcher configuration and authors' start
script, attempt a minimally changed recovery with explicit diagnostics, and
separately measure the M7 application adapter/information delta. A transparent
partially manual PCM route may proceed in parallel, but cannot be relabelled as
automatic PMX.

The finding raises the cost of applying this particular public binary artifact;
it does not demote the later PMX performability work as the closest published
comparator. The tested JAR does not represent every PMX build, extension,
deployment route, or Palladio capability. Likewise, the earlier Retriever result
remains restricted to its tested release and rules.

M9F performs no accuracy scoring and no new live collection. It cannot change
the M7 result: the published calculations establish no predictive gain and
exhibit prediction--observation discrepancies, while their causes remain too
poorly resolved to call the overall approach either successful or failed.
