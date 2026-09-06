# M9I: PMX failure-semantics source and boundary diagnostic

Status: frozen before the first M9I remote audit.

## Question

M9H established that the exact source-declared PMX entrypoint is operational:
the authors' unchanged input reproduced the historical PCM output, but an
otherwise identical trace with one frozen `error=true` tag produced the same
stdout aggregates and the same PCM. M9I asks where that distinction disappears
in the tested binary's source-defined transformation chain.

M9I is an observational diagnostic of already accepted evidence. It does not
invoke PMX, try another tag, alter an input, score accuracy, access M7 evidence,
or authorize collection. Its purpose is to recover enough exact implementation
semantics to define a later prospective mechanism test without post-result
guessing.

## Frozen evidence

The diagnostic is anchored to:

- M9H run `34050900275` at commit
  `5ec6a33ce51d426ac412006b418632986db4cc9a`;
- all three M9H artifact IDs, sizes, GitHub SHA-256 digests, and expiry checks;
- the accepted M9H source-contract, probe, and decision manifest byte hashes;
- the public demonstration commit
  `9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2` and its 65,729,095-byte
  `main.jar`, SHA-256
  `befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`;
- the embedded bundle byte identities already established by M9F; and
- four embedded source byte identities covering JSON reading, error detection,
  trace reconstruction/aggregation, and PCM failure-probability insertion.

All Java sources under the pinned reader, trace-to-internal-trace,
internal-trace-to-system, and failure-probability bundles are retained. This is
a complete source census within those four byte-pinned bundles, not selection
of favorable lines after seeing their contents. The four previously hashed
files are mandatory anchors; absence or mismatch fails the audit.

## Retained transformation boundary

The M9H probe artifact is read without re-execution. For both unchanged and
one-error conditions and both confirmation repeats, the audit verifies:

1. options select the retained trace file exactly once;
2. the control trace differs by the one predeclared tag on the unique frozen
   trace/span, while unchanged inputs contain no `error` tag;
3. tag key, declared Jaeger type, JSON value and host-language value type;
4. command entry, complete six-stage log, model inventory, semantic signature,
   and failure-element counts from the accepted manifest/CSV;
5. ordered stdout `Success:` and `Failure:` aggregates and exact equality or
   difference between conditions; and
6. exact hashes for the retained inputs, stdout, log, and core PCM outputs.

This separates four explanations that must not be conflated: a missing raw
mutation, a launcher/transformation failure, loss before the internal operation
aggregate, and loss only in the downstream PCM failure transformer. The audit
may localize the earliest observed boundary, but a unique causal claim requires
an exact source path connecting the input representation to that observation.

## Source evidence and interpretation rule

For every embedded Java source, M9I records path, size, SHA-256, and every line
matching the predeclared case-insensitive vocabulary `error`, `failure`,
`success`, `status`, `getValue`, `setFailureProbability`, `countOfFails`, or
`countOfSuccesses`. Full source snapshots are retained in the workflow artifact
so that neighboring control flow cannot be inferred from isolated strings.

The machine decision reports whether source and boundary evidence were
recovered and the earliest observed collapse boundary. It deliberately does
not choose a new input encoding. The milestone report may explain source logic
that is directly visible in the retained snapshot, but any new positive or
negative dynamic control must be named, frozen, and run only in the following
milestone. This prevents M9I from turning a diagnostic source inspection into
an undisclosed search over controls.

## Decision branches

- If any pinned source, artifact identity, raw mutation, or accepted M9H
  invariant differs, M9I reports an evidence-integrity failure and no dynamic
  continuation is authorized.
- If the raw mutation is present and the command/log/model path completed but
  stdout still contains no failure distinction, the earliest observed collapse
  is between the raw tag and the internal operation-failure aggregate.
- If stdout distinguishes the control but PCM does not, the earliest observed
  collapse is the system-to-PCM failure transformer.
- If both stdout and PCM distinguish it, the retained M9H decision is
  inconsistent and must be corrected transparently before continuation.

Only exact source semantics may motivate the next control. If the source shows
an internal inconsistency that no input can satisfy, that is reported for the
tested binary rather than repaired silently. If it shows a distinct supported
input contract, M9J freezes a minimal positive/negative matrix with an
independent oracle before invoking PMX.

## Anti-straw-man and scope

The audited components are the authors' exact reader and transformation chain,
not a substitute baseline. Both source and behavior come from the same public,
byte-pinned JAR that reproduced the historical output. The diagnostic therefore
addresses the most favorable executable evidence currently available while
remaining scoped to that binary and demonstration.

Application adaptation remains a cost measurement, not a scientific
disqualification. A limitation in this binary is not generalized to all PMX,
Retriever, or Palladio. Conversely, source inspection is not application
accuracy, an extracted M7 model, or evidence of predictive gain.

## Workflow and reporting

The workflow has exactly three jobs:

1. download the pinned public JAR and extract/audit all relevant embedded Java
   sources;
2. download the accepted M9H probe and audit its raw-to-stdout-to-PCM boundary;
3. combine both artifacts under the frozen decision branches.

All three jobs use `timeout-minutes: 360`. Network downloads and the full source
audit run only in GitHub Actions. Local work is limited to config validation,
unit tests, and tiny synthetic ZIP/JSON boundary smokes. The report records the
run, artifact identities, exact source findings, retained behavior, earliest
observed collapse, limitations, and prospective next step.

The M7 position remains unchanged: published calculations show no established
gain and discrepancies with observations; their causes are not sufficiently
resolved to declare the overall approach successful or failed.
