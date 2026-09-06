# M9F: PMX performability reproducibility and semantic-fit protocol

Status: frozen before the first remote execution of the PMX performability
binary.

## Question and scientific role

M9F asks whether the later headless OpenTelemetry PMX route can be reproduced
from its public artifacts and which parts of the required availability model it
actually derives. The tested method is the performability extension described
by Weber, Weber, and Henß, not the legacy Kieker-only PMX distribution and not
Retriever.

PMX remains the scientifically prioritized comparator because it is the
closest published data-to-PCM-to-Palladio route. Missing application support,
adapters, instrumentation, or model elements are recorded as application cost;
they do not disqualify the method by definition. Conversely, successful
execution on the authors' example does not establish readiness or accuracy for
the two M7 systems.

This milestone is a reproducibility and semantic-mechanism audit. It reads no
M7 evaluator outcome, computes no prediction score, changes no historical
estimator, and authorizes no new live collection. The M7 position remains that
published calculations establish no predictive gain and disagree with some
observations, while the causes remain insufficiently diagnosed for a verdict
on the overall approach.

## Frozen public artifacts

The artifact set is selected before execution:

- the primary performability paper, 244,692 bytes, SHA-256
  `5d45195448d2a12c502a202721215c93d0623c1e02c7e6c9565338eff54c9a8f`;
- historical OpenTracing PMX source at
  `ptreyer/org.palladiosimulator.pmxupgrade`, commit
  `9ee8b8745c0c0bb3dfc1b529906fc001525a7ce5`;
- historical PCM companion source at
  `ptreyer/org.palladiosimulator.pmxupgrade-pcm`, commit
  `6ec1cb7387efc236c0e55f44ed5c79acb5fd9d33`;
- the authors' public CI/CD demonstration, GitLab project 50, commit
  `9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2`, and historical successful
  pipeline 1120;
- that commit's 65,729,095-byte `main.jar`, Git blob
  `cd46b43e3632b242bd670d898c597cd7772f5e2c`, SHA-256
  `befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`;
- all four public trace exports, the options file, and the pipeline file at the
  same demonstration commit.

Repository commit and Git-blob identities are checked independently of working
tree line-ending conversion. Downloaded binary and trace bytes are checked with
SHA-256. External API responses, registry tag lists, Java version, logs,
resource usage, and every generated file are retained.

The historical source repositories provide lineage and integration context;
they are not silently equated with the later binary. The later JAR is separately
audited for its outer launcher, embedded bundles, embedded `OSGI-OPT/src`
snapshots, build descriptors, and license material. Source-reproducible,
binary-reproducible, and container-reproducible stages are reported separately.

## Frozen executions

The public binary declares JavaSE 11 and an embedded bnd/OSGi launcher. M9F uses
Temurin 11 and the JAR's `Main-Class`, invoking its documented options-file
interface as:

```text
java -jar main.jar -of Options.txt
```

Two conditions are run twice in isolated directories:

1. `published_original`: the authors' unchanged `jaegercustomers.json` and
   unchanged `Options.txt`;
2. `single_error_control`: the same trace export with exactly one added tag
   `{key: error, type: bool, value: "true"}` on trace
   `af0f0df51dfdfc3ca3e2eae9b00b114e`, span `b2adec3b558fff51`, operation
   `VisitResource.read`. The options file differs only in its input filename.

The selected operation has ten eligible Spring MVC span occurrences in the
unmodified input and none has an `error` tag. If the published error-counting
semantics are active, the control therefore has a hand-checkable expected
operation failure probability of 1/10. This is a mechanism control, not an
accuracy datum and not an M7-like fault campaign.

Exit code alone is insufficient because the embedded orchestrator does not
propagate every plugin status. Acceptance consequently audits logs, required
model files, parseability, semantic elements, and repeat consistency. Random
PCM identifiers need not be byte-identical; repeat consistency is evaluated on
file sets, element counts, stable entity names, and reliability values after ID
removal.

## Semantic-fit dimensions

The decision job reports evidence for each dimension without treating all
dimensions as claims made by PMX:

| Dimension | Evidence sought |
|---|---|
| Trace ingestion | accepted public schema, reader requirements, and adapter delta from the stored M7 evidence |
| Architecture and operation flow | components, operations, SEFFs, calls, usage, allocation, and resource environment in generated PCM |
| Software operation failure | error-tag detection, success/failure aggregation, internal failure occurrence, failure type, and the 1/10 control |
| Host lifecycle | automatically derived MTTF/MTTR or an explicit absence/required source |
| Communication failure | automatically derived nonzero link failure or an explicit absence/required source |
| Replication | recovery of multiple interchangeable instances rather than mere component multiplicity |
| Common failure domains | a shared logical-domain representation or required completion |
| External-client success | representation of the article's client-observed target, including semantic failures not marked as span errors |

An observed absence is scoped to this pinned artifact and input. It becomes an
adapter, instrumentation, or completion row; it is not generalized to all PMX,
Retriever, or Palladio versions.

## Reproducibility classifications

The milestone may produce any combination of the following independently:

- historical source lineage accessible or inaccessible;
- later embedded source snapshot present or absent;
- later source build complete or incomplete from public files;
- headless binary invocation reproduced or not reproduced;
- published PMX extraction stage reproduced or not reproduced;
- original full PMX-to-Palladio container pipeline exactly recoverable or not
  recoverable;
- operation-failure mechanism demonstrated or not demonstrated;
- each M7 semantic dimension demonstrated, partial, not demonstrated, or
  outside the published claim.

None of these classifications removes PMX's scientific priority merely because
integration is costly. If the binary route runs but requires application
adapters, the next milestone implements and measures those adapters. If a
required public artifact is unavailable, the exact gap is retained and a
source-recovery/manual route may proceed alongside the published method rather
than being mislabeled as automatic PMX.

## Workflow and acceptance

The three GitHub Actions jobs are:

1. `provenance_contract`: validate the frozen contract, audit the paper,
   historical source commits and Git blobs, demonstration metadata and tree,
   historical pipeline, and current registry observations;
2. `headless_probe`: byte-verify the public JAR and traces, audit embedded
   bundles/source, generate the one-tag control, and perform the four remote
   runs while retaining raw outputs;
3. `semantic_decision`: independently re-hash upstream artifacts and generated
   files, compare repeats and the 1/10 control, and emit scoped reproducibility,
   semantic-fit, and required-work tables.

All three jobs use `timeout-minutes: 360`; each PMX invocation also has a
separate internal timeout. The workflow is accepted when the evidence chain
and classifications are complete, even if an upstream program fails or a
semantic feature is absent. A hash mismatch, unrecorded execution, missing
classification, accidental accuracy input, or claim that one tool represents
the ecosystem fails acceptance.

The final manifest must state explicitly that accuracy scoring was not started,
new live collection was not authorized, PMX retains scientific priority, the
tested binary does not represent the complete ecosystem, and M7 interpretation
did not change.
