# M9E: Palladio full-path automation feasibility

## Outcome

M9E is complete. A byte-pinned PCM-5.2-compatible Retriever release was run
remotely on both complete, pinned application source trees. The extractor
exited successfully and wrote a repository, system, allocation, and resource
environment for each application. Those files were empty structural shells:
neither application received a usage model, the selected operation or call
behavior, replicas or logical failure domains, or reliability parameters.

Each application therefore passed 5 of 15 predeclared readiness gates and
failed the same remaining 10. The frozen decision is
`partially_manual_PCM_required`. No incomplete model was solved or scored, no
held-out accuracy outcome was read, and no new live collection was authorized.

This is a result about the tested Retriever release, its available rules, and
the two fixed applications. It is not evidence that Palladio is inaccurate and
does not represent every PCM automation route. It closes a provenance question
left open by M9D: a reliability-ready PCM comparator cannot be described as
automatically extracted in this setting. The next comparator must expose and
measure its source-grounded manual completion.

The M7 position remains unchanged. Published calculations show no established
predictive gain and retain discrepancies with observations; their causes are
not diagnosed sufficiently to declare the overall approach successful or
unsuccessful.

## Frozen question and boundary

M9D verified that Palladio solves the supplied M9C/B3 probability realization
correctly, but that bridge inherited both our architecture mapping and fitted
parameters. Before constructing another accuracy table, M9E asked whether a
public PCM extraction route could independently produce all model elements
needed for the two fixed M7 operations.

The protocol, implementation, exact application commits, exact tool product,
information boundary, and 15 gates were committed before the first remote
extractor execution:

- preregistration and implementation:
  [`ec04a92c4b6446a20701e6636dd259377567c29a`](https://github.com/a-a-k/telemetry-availability-identification/commit/ec04a92c4b6446a20701e6636dd259377567c29a);
- canonical-upstream-byte correction:
  [`17f701c589f871320e560304ccb3c16e3b45191b`](https://github.com/a-a-k/telemetry-availability-identification/commit/17f701c589f871320e560304ccb3c16e3b45191b);
- accepted workflow:
  [run 34036117393](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34036117393),
  first attempt at the corrected commit;
- matching CI:
  [run 34036107197](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34036107197).

The gate was deliberately completed before any partially manual model was
created. Missing fields could not be supplied and then credited to the
extractor. M9E also froze the following constraints:

- accuracy scoring is forbidden;
- a generated file is not sufficient if the required semantic element is
  absent;
- internal failure probability cannot satisfy the separate nonzero-link gate;
- a failed gate is a manual/instrumentation requirement, not an accuracy loss;
- M9D's zero-variance aligned B3/PCM parity cannot size an independent
  full-path comparison;
- confirming repetition count remains unset until an independently
  parameterized baseline exists.

## Tool and application audit

The protocol retained all three automation families named in the continuation
plan rather than selecting a deliberately weak comparator.

| Candidate | Audited scope | M9E disposition |
|---|---|---|
| PMX | Kieker-log extraction of architectural performance models; official page marks it unmaintained | Not executed: M7 has native/OpenTelemetry evidence, and an adapter plus reliability semantics would first have to be invented |
| CIPM | Continuous extraction/calibration of architectural performance models with technology-specific Java and tailored Lua transformations | Not executed: the published route does not provide the required MTTF/MTTR, link-failure, domain, replication, and semantic-residual extraction for these applications |
| Retriever | Static PCM extraction from heterogeneous project artifacts with registered technology rules | Executed: the selected release has directly relevant Docker and ECMAScript rules and emits PCM 5.2 files |

The executed product was Retriever tag `v5.2.0.202408280745`, commit
`6b42ab8438ded3beb3e84b72abd3ea6faef3ce35`, Linux asset ID `188798221`.
The 100,404,945-byte asset was verified before execution against SHA-256
`61e12934a0b1dad3b7814e367dfed81f5ef09769e0e85a976a6c548b0ede464a`.
Five source files independently locked the rule registry, persistence behavior,
and the default zero link-failure placeholder. The contract also re-audited 10
M9C application source witnesses and the accepted M9D artifact identity with
zero mismatches.

| Application | Frozen operation | Source commit | Executed rules | Direct rule coverage of 10 locked witnesses |
|---|---|---|---|---:|
| DeathStarBench Social Network | `read_user_timeline` | `6ecb09706140f8730b5385c08f1386c654c3c526` | Docker | 1 / 4 |
| OpenTelemetry Demo | `browse_product` | `8c47d47c9ac27710d2b2a153bcd53e483bffe66d` | Docker + ECMAScript | 4 / 6 |

The fractions are a source-language coverage diagnostic, not an accuracy
metric. DeathStarBench's fixed path includes unsupported Lua and C++; the
OpenTelemetry path includes unsupported Go and Python, while its modern
TypeScript was given to the closest ECMAScript rule. Both complete checkouts
were used, so source input was not narrowed after observing extraction quality.

## Remote execution and attempts

All full work ran in GitHub Actions. Local checks were limited to configuration
validation, shell syntax, canonical Git-blob locks, and 151 unit tests. Exactly
three workflow jobs were used, each with `timeout-minutes: 360`.

| Job | Role | Accepted result | Wall duration |
|---|---|---|---:|
| `automation_contract` | Audit repository/tool/application/M9C/M9D identities and the information boundary | passed | 21 s |
| `retriever_probe` | Verify the product and execute isolated copies on both full source trees | passed | 42 s |
| `acceptance_and_decision` | Re-hash raw output and independently apply all readiness gates | passed | 19 s |

The original run
[34035959104](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34035959104)
is retained as a failed technical attempt. Its probe job completed and uploaded
raw output, while the contract job rejected Retriever's README byte count. The
cause was Windows checkout CRLF conversion in the preliminary source hashes;
the application, tool version, rules, gates, and decision boundary did not
change. Commit `17f701c` replaced the five worktree hashes with hashes computed
directly from canonical Git blobs. All five byte counts, hashes, required
markers, and forbidden markers then passed on Linux. The first attempt is not
silently discarded and contributes no scientific result.

Accepted artifacts are retained for 90 days:

| Artifact | ID | Compressed bytes | GitHub artifact SHA-256 |
|---|---:|---:|---|
| `m9e-fullpath-contract-34036117393` | 9990215685 | 7,568 | `330b33675aa1485457baca6da9a8107721f79150cf2361a3d3a1d95c62a73e70` |
| `m9e-retriever-probe-34036117393` | 9990221054 | 20,914 | `597b13dd57aa4eacef95c7fbe82e183871a79c4d6fbe36f120826fa4685c1d7d` |
| `m9e-fullpath-acceptance-34036117393` | 9990226460 | 4,662 | `51c2a621f7d95ad2ad4b3b78270d793d70911743bcd62e400c234dd5d60e263b` |

Every hash named inside the contract, probe inventories, and decision manifest
was rechecked after download. The decision manifest is 2,343 bytes with
SHA-256 `f505095d857b7d4334eb4848c40ce55b1d142bcec71b376c740809105c705c93`.

## Extractor output

Retriever exited with code zero for both applications. It emitted exactly four
files each: `.repository`, `.system`, `.allocation`, and
`.resourceenvironment`. It emitted no `.usagemodel`.

| Application | Exit | Model files | Total model bytes | Extractor wall time | Peak RSS |
|---|---:|---:|---:|---:|---:|
| DeathStarBench Social Network | 0 | 4 | 1,135 | 8.47 s | 293,636 KiB |
| OpenTelemetry Demo | 0 | 4 | 1,113 | 4.08 s | 284,420 KiB |

The DeathStarBench repository, system, and resource environment contained only
their root XMI elements; the allocation only linked the empty system and empty
resource environment. The OpenTelemetry files had the same shape. Thus, the
positive file-presence gates do not imply that a component architecture was
recovered.

The DeathStarBench log contained only inherited log4j configuration warnings.
The OpenTelemetry log was 89,303 bytes and included extensive ECMAScript parser
diagnostics on contemporary JavaScript/TypeScript syntax (716 lines containing
`Expected ` and 21 containing `Missing `), while the overall extractor process
still returned zero. Those diagnostics help explain the empty structural
result, but they are not generalized into a claim about all versions or custom
Retriever rules.

Contract and decision audits took 0.19 s / 37,652 KiB and 0.20 s / 38,292 KiB,
respectively. These times are feasibility-accounting evidence, not benchmark
comparisons across tools.

## Readiness-gate result

Both applications produced the same frozen profile.

| Gate group | Gates | DeathStarBench | OpenTelemetry Demo |
|---|---|---:|---:|
| Execution | extractor exit zero | 1 / 1 | 1 / 1 |
| File presence | repository, system, allocation, resource environment | 4 / 4 | 4 / 4 |
| Workload | usage model | 0 / 1 | 0 / 1 |
| Operation structure | selected operation; entry and target; SEFF external call | 0 / 3 | 0 / 3 |
| Deployment semantics | two replicas; logical failure domains | 0 / 2 | 0 / 2 |
| Reliability semantics | failure types; positive MTTF/MTTR; nonzero link failure; semantic residual | 0 / 4 | 0 / 4 |
| **Total** | **15 required gates** | **5 / 15** | **5 / 15** |

The decision artifact contains 20 explicit manual-completion rows: the same 10
missing requirements for each application. Nothing was imputed before this
classification, and the empty models were not sent to Palladio-Analyzer-
Reliability. Scoring them would manufacture a comparator rather than evaluate
one.

## Interpretation and next milestone

M9E answers a narrower and more defensible question than “does Palladio work?”
The answer is that this compatible, publicly released structural extractor,
with its published Docker/ECMAScript rules and the complete pinned sources,
does not automatically yield a model capable of the required reliability
prediction. Its successful exit and four files establish executable plumbing;
the 10 semantic failures establish the completion work still needed.

This result reduces the straw-man risk in the eventual comparison in two ways.
First, it tests the closest executable public structural route rather than an
arbitrary hand-built weak baseline. Second, it prevents the missing operation,
deployment, and reliability information from being added manually and then
described as automatic. The limitation is equally important: custom Retriever
rules, another version, or another PCM tool chain could behave differently.

M9F will therefore implement a **partially manual PCM** development baseline
on preserved learner evidence. Every added operation signature, component,
connector, SEFF, usage scenario, replica/domain mapping, and reliability
parameter must have recorded provenance and active human time where applicable.
Automatic Retriever shells and source diagnostics remain inputs, not credit for
elements they did not generate. The development baseline may be debugged on
M7 material but cannot convert that material into confirmation. Only after it
emits independently parameterized predictions can paired development
differences support a precision calculation and a frozen independent-
confirmation design.

