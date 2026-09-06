# M9H: exact source-declared PMX entrypoint

Status: complete. The accepted first-attempt run is
[34050900275](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34050900275)
at commit `5ec6a33ce51d426ac412006b418632986db4cc9a`.

## Result in one paragraph

M9H resolved the launcher ambiguity left by M9F and M9G. The exact command
derived prospectively from the byte-pinned JAR's Declarative Services
descriptor and embedded Java source, `main:main -of Options.txt`, executed the
authors' unchanged demonstration, terminated cleanly, and reproduced the
historical identifier-insensitive PCM signature in one screen and two
confirmations. The already frozen one-error-in-ten trace control also executed
twice, but both outputs were semantically identical to the unchanged output:
neither contained an internal software-failure occurrence or a nonzero failure
probability. Thus the tested public binary and input are operational, while the
exact error-to-internal-failure semantics remain unresolved. This is a narrow
mechanism diagnostic, not accuracy evidence and not a verdict on PMX or
Palladio. M9I audits the embedded transformation source and the retained M9H
input/log boundary before any new control is specified.

## What was implemented

The protocol was frozen in `docs/M9H_PMX_SOURCE_ENTRYPOINT_PROTOCOL.md`; the
machine-readable contract is `configs/m9h_pmx_source_entrypoint.json`. The
implementation in `telemetry_availability.pmx_source_entrypoint` provides four
audited operations:

1. validate the accepted M9G evidence identities, exact source-to-command
   derivation, runtime limits, and scientific guardrails;
2. classify a raw entrypoint execution independently of process exit, requiring
   the five core PCM models, parseable XML, the six-stage log sequence, and the
   historical semantic signature;
3. compare the two unchanged and two control confirmations and test the frozen
   0.1 mechanism oracle; and
4. issue a diagnostic decision without reading M7 evidence, scoring accuracy,
   authorizing collection, or crediting the manual PCM contingency as PMX.

The workflow has exactly three jobs, each with `timeout-minutes: 360`. The
65,729,095-byte JAR download and all five PMX invocations ran only in GitHub
Actions. Local execution was limited to validation, unit tests, and small
output-classification smokes.

## Accepted run and artifacts

The workflow ran from `2026-09-06T18:11:03Z` through
`2026-09-06T18:14:11Z`. Its source-contract job took 20 seconds, PMX probe job
took 2 minutes 18 seconds, and decision job took 21 seconds. All three
completed successfully on the first attempt.

| Artifact | ID | Stored bytes | GitHub SHA-256 digest |
|---|---:|---:|---|
| `m9h-source-contract-34050900275` | `9994500595` | 2,780 | `84b605233ad691fd8cdf7d909928f4e2622b80fb3fa250d8beb4ba9f3a075c39` |
| `m9h-entrypoint-probe-34050900275` | `9994535318` | 411,214 | `c13842b047d6c9905df772c26f63c898be80afa80f456258184a9f5003f0ba97` |
| `m9h-entrypoint-decision-34050900275` | `9994540981` | 2,134 | `93e099d6c590f883d82d0b52a3b885f075ff8eca746b9ec27aab996a376230f7` |

All three artifacts are retained for 90 days, through 5 December 2026. The
probe artifact includes stdin, stdout, options, trace control, full generated
models and logs, elapsed time, exit code, and resource measurements for every
invocation.

The accepted decision links configuration SHA-256
`936fb53eb6492fda9cdeda9c04b2a70a28b4f77a67f51ad88a829f1a08919240`,
source-contract SHA-256
`8deb3cb33c847728f2fd1940bcaabcb87ba5dbeb9ae73067ab7e9edab10e9f71`,
and probe-manifest SHA-256
`422bf9ec8c09fd5c5c9abb95b29da7af59f996a595f81df7f94998ce789c4bd2`.

## Source contract and launcher correction

The accepted M9G artifacts and their metadata all matched the frozen IDs,
sizes, hashes, run, and commit. The two independent declarations agree on
`osgi.command.scope=main` and `osgi.command.function=main`; the embedded class
exposes `public void main(String[] args)`, consumes `-of/--options-file`, and
contains `System.exit(0)`. M9H neither repeated M9G's four guessed candidates
nor searched for an alternative command.

After the fixed 20-second startup stabilization, every invocation accepted
`main:main -of Options.txt`. None reported command rejection or reached the
180-second internal watchdog. Each exited zero after about 22 seconds of PMX
work. This corrects the scope of the earlier launcher result: M9F truthfully
showed that its direct invocation did not enter the registered command, and
M9G truthfully rejected its four frozen guesses, but neither result was a
failure of the PMX transformation itself.

## Generated-output result

| Phase / condition | Repeat | Exit | Seconds | Files / PCM models | Log stages | Semantic signature equals historical |
|---|---:|---:|---:|---:|---:|---|
| screen / unchanged | 1 | 0 | 23 | 14 / 5 | 6 / 6 | yes |
| confirmation / unchanged | 1 | 0 | 22 | 14 / 5 | 6 / 6 | yes |
| confirmation / unchanged | 2 | 0 | 22 | 14 / 5 | 6 / 6 | yes |
| confirmation / one-error control | 1 | 0 | 22 | 14 / 5 | 6 / 6 | yes |
| confirmation / one-error control | 2 | 0 | 22 | 14 / 5 | 6 / 6 | yes |

Every run produced all five required core model types and parseable XML. All
five full logs contain the ordered reader, three base transformations, failure
transformation, and writer markers. The identifier-insensitive signature is
`4e2f00daefd89ce4ccde30074cbf09deb65a2d44736d6ccf0cacace8f004f695`
in every run, exactly matching historical job 1984. Peak resident memory was
290,116 KiB in the screen and ranged from 320,084 to 339,736 KiB in the four
confirmations.

This establishes reproducibility of the published transformation chain and
its model output under the recovered command. It does not establish that the
model is reliability-ready for either target application or that any
prediction is accurate.

## Failure-control result

The control generation independently reverified the unchanged published trace
hash, the unique target trace/span, the `VisitResource.read` operation, ten
eligible operation occurrences, and zero original `error` tags. It appended
exactly the frozen Jaeger tag `{key: error, type: bool, value: "true"}` and
changed the options input path exactly once. Both retained run directories
contain that changed trace and changed options file.

Nevertheless, each control output has:

- zero `InternalFailureOccurrenceDescription` elements;
- zero `SoftwareInducedFailureType` elements;
- no nonzero repository failure probability; and
- the same semantic signature as both unchanged confirmations.

The raw stdout is also identical between unchanged and control runs. In both
conditions the five printed operation aggregates have success counts
`10, 10, 9, 10, 1`, while every corresponding failure value is `null`. Thus
the downstream failure-probability transformer was reached, but received no
observable failure distinction from the earlier transformation boundary.
The frozen expected probability 0.1 therefore failed in both confirmations.

The evidence does not yet identify whether the tag representation, the
reader's JSON value typing, an earlier eligibility/filter rule, or another
source-level mapping explains that collapse. Choosing among those explanations
from conjecture would create a weak post-result control. M9I instead extracts
and audits the exact embedded reader and transformer sources and aligns their
predicates with the retained M9H input and stdout before freezing any new
dynamic control.

## Decision and interpretation

The frozen decision status is
`pmx_source_entrypoint_reproduced_failure_semantics_unresolved`:

- source contract agrees: true;
- source command entered: true;
- unchanged historical output confirmed twice: true;
- launcher terminates cleanly: true;
- output is repeat-consistent: true for both conditions;
- one-error-in-ten mechanism reproduced: false;
- PMX scientific priority retained: true;
- tested artifacts generalized to all PMX/Palladio: false;
- manual PCM credited as PMX: false;
- M7 evidence accessed or accuracy scored: false.

M9H therefore removes launcher recovery from the list of open causes and
narrows the next question to failure semantics. The negative control outcome
does not justify declaring PMX unsuitable: it is one source-bound mechanism
test on one public binary, and its cause is not yet localized. Conversely, the
successful unchanged reproduction cannot be promoted to application support
or predictive validation. The M9G adapter/information costs remain measured
and separate.

M9I is a static-and-retained-evidence diagnostic. It audits the exact embedded
source predicates and preserved M9H trace/log transformation boundary, without
accuracy scoring or new live collection. Only a subsequently frozen,
source-derived positive/negative control may test a corrected mechanism.

The M7 position is unchanged: published calculations show no established gain
and discrepancies with observations; their causes remain insufficiently
resolved to call the overall approach successful or failed.

## Verification

Before the accepted run, all 170 local tests passed. Each of the three remote
jobs independently validated the frozen configuration. The workflow's green
status means that the diagnostic ran to completion and its negative mechanism
result was retained; it does not mean that the failure-semantics gate passed.
