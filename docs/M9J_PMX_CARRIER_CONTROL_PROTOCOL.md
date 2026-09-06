# M9J: source-implied PMX surviving-carrier controls

Status: frozen before the first M9J remote PMX invocation.

## Question

M9I established why the M9H child-tag control was silent in the tested public
binary. Error detection runs before span merging; the marked Spring-WebMVC
child is then collapsed into a same-process Tomcat parent without propagating
the internal `SpanContainsError` attribute, and detection is not rerun. M9J
asks whether placing the exact detector input on that already identified
surviving carrier exercises the downstream operation-failure and PCM
failure-probability path.

This is a mechanism validation, not an accuracy experiment. It does not use an
application outcome as truth, score M7, alter an estimator, or authorize a new
collection.

## Why this is not a straw man

The target is not chosen because it gave a favorable PMX result. Before M9J's
first invocation it is fixed by three independent retained facts:

- the authors' trace says Spring span `b2adec3b558fff51` is a same-process
  `CHILD_OF` span of Tomcat span `9e0a042aa79207bc`;
- the exact `SpanTree` source says that child is merged into that parent; and
- M9H stdout shows the surviving parent ID with the child's
  `VisitResource.read` operation.

The values are the exact source predicate pair, string `"false"` and string
`"true"`, both declared as Jaeger type `bool`. A matched false control tests
whether carrier placement alone changes the model. The already accepted
child-true control remains a third, historical merge-loss witness; it is not
rerun or reclassified. All controls use the authors' byte-pinned input, options,
plugin chain, Java major version, and public JAR.

## Frozen evidence and controls

M9J byte-locks M9I run `34052517285` at commit
`dac1921e86285f1b28db47c7fbc8c49834c69649`, its three artifact identities,
and the source, boundary, and decision manifests. It independently rechecks the
five source files that define tag typing, detection, merge ordering and
propagation, operation aggregation, and PCM probability insertion.

The unchanged demonstration is fixed at commit
`9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2`. The original customer trace and
options retain their published byte identities. They contain no `error` tag.
M9J creates exactly two traces, each differing from the original only by one
tag appended to carrier `9e0a042aa79207bc`:

| Condition | Added value | Source-level expectation |
|---|---|---|
| `carrier_error_false` | string `"false"` | detector predicate false; unchanged operation counts and no PCM failure |
| `carrier_error_true` | string `"true"` | carrier retains `SpanContainsError`; one target success becomes one target failure |

M9I/M9H retained stdout fixes the first-occurrence operation order as
`OwnerResource.findOwner`, `VisitResource.read`, `OwnerResource.createOwner`,
`PetResource.processCreationForm`, `OwnerResource.findAll`, with original
success counts `10, 10, 9, 10, 1` and null failures. Therefore the independent
oracles are:

- false: successes `10, 10, 9, 10, 1`, all failures null, no nonzero PCM
  repository failure probability, historical semantic signature unchanged;
- true: successes `10, 9, 9, 10, 1`, failures null except `1` for
  `VisitResource.read`, exactly one nonzero repository probability equal to
  `1 / (1 + 9) = 0.1`, and at least one internal/software failure element.

The probability is derived before execution from the pinned formula and ten
surviving target executions. It is not fitted to generated output.

## Execution and acceptance

Each condition runs twice through `main:main -of Options.txt` after the same
fixed 20-second launcher stabilization used in M9H. Stdin ends with valid
`exit 0`; each process has a 180-second internal watchdog. No alternative
command, delay, target span, tag key/type/value, expected count, or probability
may be selected after launch.

Every repeat must exit zero, avoid timeout/command rejection, emit all five
parseable core PCM models, and complete the ordered six-stage reader-to-writer
log. Both repeats per condition must agree in their identifier-insensitive
semantic signature, stdout aggregates, and failure probabilities.

The false gate requires its full frozen zero oracle. The true gate requires its
full frozen positive oracle. A green workflow means that evidence was recorded
and classified; the decision manifest separately states whether each gate
passed.

## Interpretation branches

- If both gates pass, the tested binary's positive downstream functional-
  failure path is reproduced, and the M9H result is specifically a merge-
  propagation issue. A learner adapter must attach or propagate error semantics
  to the span representation that survives this transformation if a later
  comparison elects to pay that application cost.
- If false passes but true fails, the source-implied positive path remains
  unverified; no application adapter or accuracy comparison may treat PMX
  failure extraction as operational.
- If false fails, carrier placement has an unanticipated effect and the paired
  mechanism interpretation is invalid.
- Any evidence-integrity or execution failure is reported separately and is not
  interpreted as a PMX scientific result.

M9J is the bounded end of the present external-tool diagnostic, not the start
of an open-ended PMX repair sequence. Every branch proceeds next to M9K, which
localizes the proposed model's largest retained overprediction on the single
predeclared checkout operation. The PMX result and that internal localization
are then considered together before choosing another experiment; an adapter is
not implemented merely because its mechanism is technically possible.

Even a complete pass establishes one synthetic mechanism in one public binary,
not natural application compatibility or predictive accuracy. The M9G raw-data
and instrumentation gaps remain application costs. Neither a pass nor failure
is generalized to all PMX, Retriever, or Palladio.

## Workflow and reporting

The workflow has exactly three jobs:

1. audit accepted M9I artifacts/source and generate the two locked controls;
2. execute both controls twice and record raw/process/model evidence;
3. apply the frozen paired decision.

All three jobs use `timeout-minutes: 360`. The JAR download and four PMX
invocations run only in GitHub Actions. Local work is limited to configuration,
unit tests, and tiny control-generation/classification smokes. The milestone
report records every run, artifact identity, count/probability gate,
repeatability result, limitation, and next decision.

The M7 position remains unchanged: published calculations show no established
gain and discrepancies with observations; their causes are not sufficiently
resolved to declare the overall approach successful or failed.

The preliminary article-level assessment is correspondingly narrower: the
direction remains scientifically substantive, and the retained data support
the correctness of the calculation conditional on the specified model. They do
not yet demonstrate either better predictive accuracy or lower end-to-end cost
of automatically obtaining a prediction than PMX.
