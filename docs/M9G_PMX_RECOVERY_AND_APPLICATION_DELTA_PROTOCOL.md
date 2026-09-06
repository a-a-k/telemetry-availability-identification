# M9G: PMX launcher recovery and application-information delta

Status: frozen before the first remote M9G launcher probe or application audit.

## Question

M9G follows the accepted M9F finding that the byte-pinned JAR did not execute
PMX when invoked as a conventional standalone `java -jar ... -of ...`
application. It asks three separate questions:

1. can the authors' historical PMX output be recovered and audited directly;
2. can the same byte-pinned JAR be driven through its actual embedded OSGi/Gogo
   command contract without relying on the unavailable mutable container image;
3. which schema, instrumentation, and architecture information required by that
   route is present in the preserved M7 learner evidence for the two applications.

The answers are not collapsed. Historical output recovery does not prove that
the current launcher works. A recovered launcher does not imply application
compatibility. Missing application support is cost, not a reason to demote PMX's
scientific priority. No result is generalized to every PMX build, Retriever
version, or Palladio facility.

M9G is diagnostic. It performs no Brier scoring, reads no M7 evaluator file,
changes no M7 estimator, and authorizes no new live collection. The M7 position
remains: no predictive gain is established and discrepancies with observations
remain insufficiently explained for a verdict on the overall approach.

## Frozen evidence

- M9F accepted run `34041926658`, commit
  `e3bfdfb5415d79007cce874181b274a10d62b433`, and its three artifact identities;
- demonstration project 50 at commit
  `9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2`;
- 65,729,095-byte `main.jar`, SHA-256
  `befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`;
- historical successful pipeline 1120 and PMX job 1984;
- the public 13,676-byte job-1984 artifact, SHA-256
  `4ae91b639ceeb8ec7c1403bfeabb2b0b5af3a3bf8a6676d6dd94a3662ad8bdb0`,
  including exact hashes for all fourteen retained files;
- M8A's preserved M7 evidence artifact `9983956440`, containing all 160
  qualified bundles and all four predeclared raw `NCD/r0` audit samples.

The historical CI file invokes `/entrypoint.sh` inside a mutable `pmx:latest`
image and does not publish the script. Registry access and historical image
digests are absent. The job artifact is therefore evidence of generated output,
not a reconstruction of the exact container filesystem.

## Track A: historical output and launcher recovery

The first job byte-checks the JAR and historical ZIP, parses all five historical
PCM files, checks the historical log sequence (reader, trace transformers,
system-to-PCM transformer, failure transformer, writer), and records the
semantic signature without random XMI identifiers.

It separately extracts and retains the outer manifest, `launcher.properties`,
the embedded core `Main.java`, relevant bundle manifests, Declarative Services
descriptors, and all command-scope/function markers. These observations explain
the launch contract but cannot retroactively alter the frozen candidate order.

M9F's failed direct-argument invocation is not repeated. Four Gogo input
commands are tried once on the unchanged authors' trace, in this order:

1. `pmx -of Options.txt`;
2. `pmx:execute -of Options.txt`;
3. `pmx:main -of Options.txt`;
4. `pmx:pmx -of Options.txt`.

Each command and `exit` are supplied through standard input to the same
byte-pinned JAR on Temurin 11. Each screen is isolated and bounded at 120
seconds. A candidate is eligible only if it writes all five parseable PCM model
types, its log contains the full expected transformation sequence without a
major error, and its identifier-insensitive semantic signature equals the
historical job output. Exit zero is recorded separately: a complete model from
a non-terminating launcher is an output recovery with additional runtime cost,
not a clean launcher recovery. The first eligible candidate in frozen order is
selected; stdout or timing cannot change the order.

If a candidate is selected, it is confirmed twice on the unchanged published
trace and twice on M9F's predeclared one-error-in-ten control. The original runs
must match the historical semantic signature. The control must contain an
internal software failure occurrence with probability 0.1 in both repeats.
Random IDs are ignored, while entity names, element counts, failure values,
required files, parseability, log stages, and repeat consistency are retained.

## Track B: application and information delta

The application job downloads only the already preserved M7 artifact. It audits
all 160 `learner/` directories and never opens `evaluator/`, test-request, or
test-health content. For every campaign it records whether the following are
available: a raw PMX-readable trace envelope; span IDs, parent IDs, timestamps,
operations, service and instance identity, instrumentation scope, error/status
semantics; derived topology; deployment/replica/domain metadata; lifecycle and
network observations; and the external semantic-success contract.

The qualified learner population contains derived tables but is expected to
contain no raw telemetry file. This is tested rather than filled from evaluator
data. The four raw audit samples are analyzed as a separate, explicitly
non-representative schema subset. Learner-period trace IDs are selected from the
saved join table before span inspection; sentinel and test periods are excluded.
The audit counts native Jaeger versus OTLP JSONL shape, selected unique spans,
service/instance/host fields, Spring-WebMVC instrumentation markers used by the
audited PMX transformer, direct `error=true` tags, and OTLP error statuses that
would require an explicit adapter rule.

No application PMX prediction is scored in M9G. The four raw samples may support
adapter development, but they cannot stand in for the 160-campaign accuracy
population. Any future conversion must preserve a zero-overlap trace-ID proof
against the test period and must label inferred tags, deployment additions, and
manual completion separately.

## Decision rules

The final job publishes independent booleans for:

- historical output recovered and semantically audited;
- byte-pinned Gogo output recovered;
- launcher terminates cleanly;
- one-in-ten software-failure mechanism reproduced;
- all-160 direct raw-input coverage;
- four-sample schema adaptability;
- direct instrumentation-semantic coverage;
- additional deployment/lifecycle/communication information required.

The next milestone is selected from these facts, not from an accuracy outcome.
If the launcher and mechanism are recovered, the next step implements a
learner-only application adapter and evaluates its coverage before accuracy. If
only historical output is recoverable, source/container recovery and the manual
PCM route remain parallel and explicitly named. If raw input is unavailable for
the historical M7 population, new collection may be proposed only in a later
preregistered milestone; M9G does not authorize it.

## Execution and reporting

The workflow has exactly three jobs: launcher/evidence recovery, application
information audit, and joint decision. All three use `timeout-minutes: 360`.
Heavy downloads, full evidence scans, and every PMX invocation run only in
GitHub Actions. Local work is limited to unit tests, configuration validation,
public-metadata inspection, and small schema smokes.

The accepted run is the first complete run at the frozen implementation commit.
Technical corrections remain visible and cannot silently replace evidence. A
milestone report records implementation, exact run and artifacts, all candidate
outcomes, historical-output semantics, application coverage, costs,
limitations, next decision, and the unchanged M7 interpretation.
