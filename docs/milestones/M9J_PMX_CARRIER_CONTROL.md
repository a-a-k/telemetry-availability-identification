# M9J: source-implied PMX surviving-carrier controls

## Outcome

M9J is complete as the final bounded PMX diagnostic in the present sequence.
The first and only accepted workflow attempt completed all three jobs and all
four predeclared PMX invocations. Every invocation exited zero, completed the
six-stage transformation, and produced all five core PCM models.

The matched negative control reproduced the historical model exactly. In both
positive-control repeats, putting string-valued `error="true"` on the span that
survives PMX's same-process merge changed the generated model: PMX recorded one
failure among ten executions, emitted repository failure probability `0.1`,
and created the corresponding internal/software failure structure. The
generated repository resolves that failure to the `VisitResource.read` SEFF.

The frozen machine decision is nevertheless
`pmx_carrier_negative_pass_positive_unresolved`, because the unlabeled stdout
aggregate appeared in slot zero while the protocol had fixed slot one. This
gate is not rewritten after seeing the result. Retained-output inspection shows
that the protocol's positional mapping was underidentified: in the original
output the first two operations both had ten successes, and their unlabeled
aggregate order could not be inferred from first trace occurrence. The PCM
model provides the missing operation identity and supports the intended
mechanism, but only as a transparent post-result clarification rather than a
prospectively passed full oracle.

Together with M9I, this establishes the cause of the silent M9H control for the
tested public binary. The exact detector recognizes the child tag before span
merging; the internal marker is then neither copied to nor recomputed on the
surviving carrier. The same detector input is effective when it is already on
that carrier. This is a scoped merge-propagation/application-adapter issue, not
evidence that PMX lacks a functional-failure path.

## Implementation and execution

- frozen implementation and protocol commit:
  [`6ad7679941f7303af81b569736deb5b8fe8b1933`](https://github.com/a-a-k/telemetry-availability-identification/commit/6ad7679941f7303af81b569736deb5b8fe8b1933);
- accepted remote execution:
  [run 34054064325](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34054064325);
- run attempt: first attempt, started `2026-09-06T19:10:47Z` and completed
  `2026-09-06T19:13:39Z`;
- local verification before launch: 181 unit tests, configuration validation,
  workflow parsing, and a control-generation smoke on retained evidence.

All three workflow jobs used `timeout-minutes: 360`. PMX and the 65.7 MB public
JAR ran only in GitHub Actions. Local work did not invoke PMX. The contract job
byte-reverified all three accepted M9I artifacts and manifests, all five exact
source anchors, and the authors' original options and trace before creating the
controls.

The source input was changed in exactly one place per condition: carrier span
`9e0a042aa79207bc` in trace
`af0f0df51dfdfc3ca3e2eae9b00b114e` received a Jaeger `bool` tag with key
`error` and a string value of either `"false"` or `"true"`. The target was fixed
from the M9I source/trace relation before execution; no alternative span, tag,
delay, command, or oracle was tried.

## Accepted artifacts

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m9j-carrier-contract-34054064325` | 9995420894 | 133,230 | `3a1e15ac3cbba41788331ae89e10942a013b22b15c964b063da96c6dc216d8a6` | 2026-12-05 19:10 UTC |
| `m9j-carrier-probe-34054064325` | 9995451062 | 358,873 | `e4e9a259b135701c9734130a15a80817bd06e2f8d4e3e83b4eef8a70b8a86553` | 2026-12-05 19:10 UTC |
| `m9j-carrier-decision-34054064325` | 9995457506 | 2,196 | `eb23b1d27499ccab0f9b2d6091f1905416e8e764e2fea082e2c4c2953c67be03` | 2026-12-05 19:10 UTC |

The uncompressed manifest identities are:

| Manifest | Bytes | SHA-256 |
|---|---:|---|
| `control-contract-manifest.json` | 7,282 | `543b7c29423893ceb998b6be07d731c32cc05cd6dae07d36da6de4eba8b8d28f` |
| `carrier-probe-manifest.json` | 1,597 | `341d724c077c44c5fea3c93987a011abf3eb2432f77bb03b24ed600eae4b2f67` |
| `decision-manifest.json` | 1,924 | `9b7b12533df64b86038828a71a13723e9e9f8fccb64161818ff73024d463f482` |

GitHub reports all artifacts as unexpired and associates them with the frozen
commit and run. The contract records zero dynamic PMX invocations; the probe
records exactly four. Neither artifact accesses M7 outcomes, starts accuracy
scoring, or authorizes collection.

## Frozen gates and observed results

| Condition | Repeat | Seconds | Success aggregates | Failure aggregates | Repository probabilities | Semantic signature | Frozen full oracle |
|---|---:|---:|---|---|---|---|---|
| carrier false | 1 | 23 | `10,10,9,10,1` | all null | none | `4e2f00da...004f695` | pass |
| carrier false | 2 | 22 | `10,10,9,10,1` | all null | none | `4e2f00da...004f695` | pass |
| carrier true | 1 | 21 | `9,10,9,10,1` | `1,null,null,null,null` | `0.1` | `a5158849...21e793` | fail: positional aggregate |
| carrier true | 2 | 22 | `9,10,9,10,1` | `1,null,null,null,null` | `0.1` | `a5158849...21e793` | fail: positional aggregate |

Every row has exit code zero, 14 retained result files, five parseable PCM
models, the complete ordered log sequence, and no major error. Both conditions
are internally repeat-identical. The two negative stdout files have exact
SHA-256 `565ad0099b9b84a955ba21ddb35c165ce7cec9d6ec42dee249f22a9f16722a50`;
the two positive files have exact SHA-256
`ecdbc45385353a0d6c82a612e5469268f17e65721caf6f0ad9c83eec9a93783f`.
The declared non-failure structural projection is identical across all four
runs.

The positive model contains one `SoftwareInducedFailureType` and one actual
internal failure occurrence (the lexical token counter is two because the XML
element has opening and closing names). Its `failureProbability="0.1"` element
is inside the `visits-service` resource-demanding SEFF. That SEFF's
`describedService__SEFF` reference resolves to the operation-signature element
whose `entityName` is `VisitResource.read`. This operation-resolved model
evidence agrees with the source-derived target even though the stdout aggregate
itself has no operation label.

## Interpretation

The strongest defensible conclusions are separated by evidence status:

- prospectively, the negative gate passed, the positive run produced the
  predeclared probability and failure structure twice, but the full positive
  gate failed its positional stdout count oracle;
- post-result, direct reference resolution inside each retained repository
  attributes the `0.1` failure to `VisitResource.read`, revealing that the
  failed slot assumption was an audit-design error rather than absence of the
  downstream PMX mechanism;
- M9H's child-tag silence is explained for this binary by marker loss across
  the audited merge, while carrier placement exercises the expected functional-
  failure transformation;
- using this route on the study applications would still require explicit,
  measured preprocessing or instrumentation work. Scientific priority does not
  imply zero application cost.

M9J does not establish natural application compatibility, predictive accuracy,
or end-to-end cost. It is not generalized to other PMX builds, Retriever, or
the Palladio ecosystem, and it does not alter the M7 result. In particular, the
current evidence still supports correct calculation conditional on the stated
model but demonstrates neither better accuracy nor lower full automation cost
than PMX.

## Next milestone

No further PMX repair run is authorized by M9J. M9K now uses only preserved M7
evidence to localize the proposed model's largest overprediction on the
predeclared OpenTelemetry Demo `checkout` operation. It will distinguish the
clean residual, health/path-state representation, likelihood fit, and temporal
evaluation contributions without changing any M7 prediction or tuning against
the test outcome. The M9J and M9K results together, not either one alone, will
determine any subsequent experiment.

## Completion checks

- The protocol and exact inputs were committed before the first invocation.
- The first attempt completed all three 360-minute-bounded jobs.
- All four allowed PMX runs are retained and technically valid.
- Both controls are repeat-identical and the negative reproduces history.
- The frozen positive gate failure and its exact mismatched field are retained.
- Operation-resolved post-result evidence is explicitly labelled and does not
  overwrite the machine decision.
- No accuracy score, new collection, alternative control, or local PMX run was
  performed.
- The PMX diagnostic is closed and the next work returns to the proposed model.
