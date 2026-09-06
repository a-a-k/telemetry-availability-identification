# M9I: PMX failure-semantics source and boundary diagnostic

Status: complete. The accepted first-attempt run is
[34052517285](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34052517285)
at commit `dac1921e86285f1b28db47c7fbc8c49834c69649`.

## Result in one paragraph

M9I recovered all 25 Java sources in the four exact embedded bundles that span
JSON reading through PCM failure insertion, then joined them to the four
retained M9H confirmation runs without executing PMX again. The M9H tag was
correctly encoded for this reader: `TagOTLP.value` is a Java `String`, and the
exact `error`/`true` detector sees that representation. The failure distinction
is lost during span-tree merging. The marked Spring-WebMVC child is merged into
its non-Spring Tomcat parent; operation and tags are copied, but the internal
`SpanContainsError` marker is not, and error detection is not rerun. The
surviving parent is consequently counted as a success, so the downstream
failure transformer receives a null failure count and emits no failure
occurrence. This establishes the source-level cause of the frozen M9H control
outcome for the tested binary. It does not establish that PMX cannot represent
failures: M9J prospectively tests the source-implied surviving-carrier contract
with matched true and false controls.

## What was implemented

The protocol is `docs/M9I_PMX_FAILURE_SEMANTICS_PROTOCOL.md` and the executable
contract is `configs/m9i_pmx_failure_semantics.json`. The implementation in
`telemetry_availability.pmx_failure_semantics`:

1. locks the accepted M9H run, commit, three artifacts, manifests, public JAR,
   embedded bundles, and four previously hashed source anchors;
2. extracts every Java source from the reader, trace-to-internal,
   internal-to-system, and failure-probability bundles and records a complete
   byte inventory plus predeclared vocabulary lines;
3. verifies the two unchanged and two control inputs, options, stdout, logs,
   PCM files, semantic summaries, and the exact one-tag mutation; and
4. classifies the earliest observed collapse boundary without trying another
   tag or invoking PMX.

The workflow contains exactly three jobs and all use `timeout-minutes: 360`.
The public JAR download and full embedded-source census ran only in GitHub
Actions. Local work was limited to unit/config validation and a retained-
artifact boundary smoke; there was no local experiment.

## Accepted run and artifacts

The workflow ran from `2026-09-06T18:41:24Z` through
`2026-09-06T18:42:40Z`. The source job took 23 seconds, boundary job 21 seconds,
and decision job 24 seconds. All completed successfully on the first attempt.

| Artifact | ID | Stored bytes | GitHub SHA-256 digest |
|---|---:|---:|---|
| `m9i-embedded-source-34052517285` | `9994975626` | 39,200 | `26d16c1e9ad2a7606729143b50a306d9eed7f948dfd64b8cfe8b93cbcff7d4f6` |
| `m9i-retained-boundary-34052517285` | `9994981969` | 4,751 | `d609af730b1112127554b9130870c7c69edd32a9cdda7cb0469ba88ce6788132` |
| `m9i-failure-semantics-decision-34052517285` | `9994988574` | 2,202 | `17925309d2c6d60bfe3f7dbf9ef403acbb75d0f4d6a639bfb67ff6254968ff3d` |

All are retained for 90 days, through 5 December 2026. The accepted decision
links configuration SHA-256
`b5d22dc23ba303f0011ddb7cee08311741acb8f597ac9bdf3880b085f74ba62a`,
source-manifest SHA-256
`865789aedcfab3c62d77def985ed81187bbd57f946d2f4b32e902943457a0a1e`,
and boundary-manifest SHA-256
`0883aa3dcfa0f47b0effacce79d00ccf535e5b12ed97e2428649ed2d50e641ee`.
The measured audit commands each took at most 0.31 seconds and at most 55,888
KiB resident memory; setup and downloads account for nearly all job time.

## Exact source census

The outer JAR again matched 65,729,095 bytes and SHA-256
`befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`.

| Embedded bundle | Bytes | Java sources | Byte identity |
|---|---:|---:|---|
| reader OTLP | 23,779 | 8 | matched |
| trace to internal trace | 33,631 | 6 | matched |
| internal trace to system | 47,709 | 10 | matched |
| system to PCM failure probabilities | 7,938 | 1 | matched |

All four prior source anchors matched their exact sizes, hashes, and markers.
The artifact retains full source context for 25 files and a 105-row
predeclared-vocabulary index. The causal path is visible across five of those
files and the retained trace:

1. `TagOTLP` declares `key`, `type`, and `value` as strings. Jackson therefore
   maps the retained JSON value `"true"` to the exact representation used by
   the detector; the control did not fail because a JSON Boolean was required.
2. `ReaderOpenTelemetry` copies each tag's key, declared type, and string value
   into the core trace model without dropping the inserted tag.
3. `SpanTree.mergeSpans()` calls `detectErrors()` before either merge pass.
   `Util.detectError()` marks a span with internal attribute
   `SpanContainsError` when key equals `error` and value equals `true`.
4. In the frozen trace, marked span `b2adec3b558fff51`
   (`VisitResource.read`, Spring-WebMVC, process `p2`) is a same-process child
   of span `9e0a042aa79207bc` (`GET /pets/visits`, Tomcat). The latter is not a
   `checkSpan` match.
5. The per-process merge therefore calls `setSpanAttributes` from the child to
   the parent and removes the child. It copies operation and tags. Its `ERRORS`
   branch tests that the source has `SpanContainsError`, but copies only the
   configured auxiliary attribute `http.status_code`; it never copies
   `SpanContainsError` itself.
6. There is no second `detectErrors()` call after merging. The surviving parent
   is printed with ID `9e0a042aa79207bc` and operation
   `VisitResource.read`, but `mapSpanTreeToExecution` sees no internal marker
   and increments `Constants.SUCCESS`.
7. The final transformer computes failures divided by failures plus successes,
   returns zero when the failure count is null, and adds a PCM internal failure
   only for a nonzero result. It therefore behaves consistently with the null
   input it receives; M9H never exercised its positive branch.

This is a concrete merge-propagation defect/constraint in the tested binary's
functional-failure path. It is narrower than saying that the error detector is
absent, that the downstream formula is wrong, or that PMX/Palladio lacks
performability support.

## Retained behavioral boundary

All three M9H artifact identities and manifest locks passed. The audit found
the exact original trace in both unchanged repeats and the exact generated
control trace in both control repeats. Removing its single target `error` tag
makes the parsed control payload equal to the original payload. The options
select the corresponding file exactly once.

| Condition | Repeats | Error tags | Java-side JSON value type | Success aggregates | Failure aggregates | PCM failure elements |
|---|---:|---:|---|---|---|---:|
| unchanged | 2 | 0 | n/a | `10, 10, 9, 10, 1` | all null | 0 |
| marked Spring child | 2 | 1 | string | `10, 10, 9, 10, 1` | all null | 0 |

The four stdout files have one identical SHA-256,
`565ad0099b9b84a955ba21ddb35c165ce7cec9d6ec42dee249f22a9f16722a50`.
Every command entered, all six stages completed, and every PCM matched the
historical semantic signature. Thus neither a missing mutation nor a launcher,
reader-file, downstream-stage, or repeatability failure explains the M9H
outcome. The earliest observed behavioral collapse is correctly classified as
between the raw tag and the internal operation-failure aggregate; the source
census identifies the merge step inside that interval.

## Decision and interpretation

The frozen machine status is
`pmx_exact_failure_sources_and_collapse_boundary_recovered`:

- exact four-bundle source census recovered: true;
- four prior source anchors matched: true;
- exact raw control mutation present: true;
- command/log/model path complete: true;
- stdout distinguishes control: false;
- PCM distinguishes control: false;
- dynamic PMX invocations in M9I: zero;
- PMX scientific priority retained: true;
- accuracy, M7 access, or new collection started: false.

The machine rule intentionally stopped at the observable boundary and made no
unique-cause claim. Inspection of its complete, byte-pinned source artifact
then supplies the causal link above. This sequencing matters: M9I did not
change an input after seeing a run.

M9J now freezes two controls on the exact parent span that survives the merge:
`error="false"` is the predicate-negative control and `error="true"` is the
source-implied positive control. The already retained child-true case is the
merge-loss witness. The original output contains ten surviving
`VisitResource.read` executions, so the positive oracle is nine successes, one
failure, and probability 0.1; the negative oracle remains ten successes, no
failure, and no PCM failure occurrence. Both new conditions require two remote
repeats. This is a mechanism test, not application accuracy.

If that matrix passes, it shows that the tested binary can exercise its
downstream functional-failure path when preprocessing attaches error semantics
to the surviving carrier; the required propagation/preprocessing becomes an
explicit adapter cost. If it fails, the source-implied path is not executable
as read and the positive branch remains unverified. Neither branch is
generalized beyond this binary.

The M7 position remains unchanged: published calculations show no established
gain and discrepancies with observations; their causes remain insufficiently
resolved to call the overall approach successful or failed.

## Verification

Before launch, 175 local tests passed and a bounded audit against the downloaded
M9H artifacts reproduced the exact retained boundary. Each remote job then
validated the frozen configuration independently. The accepted workflow made
zero dynamic PMX invocations.
