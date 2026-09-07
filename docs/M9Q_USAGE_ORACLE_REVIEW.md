# M9Q usage-oracle review after the retained conformance failure

The original M9Q run 34122721945 at
`bd68c984c632318f5c15194a2f59143a52216da6` completed all six PMX invocations
with exit zero. Every operation-set, ownership, component, allocation,
call-edge and error-probability check passed on both repeats. All three
identifier-independent semantic outputs were repeat-consistent. The overall
preregistered decision is nevertheless **unqualified**, because the additional
entry-node-count oracle failed in every case. That decision is preserved.

The oracle incorrectly required the number of static EntryLevelSystemCall
nodes to equal the number of observed root invocations. The two single-root
fixtures have one such node rather than ten; the forest fixture has one node
for each root operation rather than ten each. The retained usage model declares
a closed workload with population ten. These are distinct quantities. The
preserved reconstruction log includes all ten trace identities and all thirty
selected operation records for the first fixture. No new extraction is needed
to investigate the mismatch.

A separate static source audit now retrieves complete embedded Java sources
from the unchanged binary's core and system-to-PCM bundles. It executes no
Java/PMX process. This will determine the actual workload aggregation rule
before defining a corrected verification of the retained outputs. The original
protocol, config, adapter, conformance code, artifacts and failed decision
remain unchanged; a correction must be explicitly labelled as a post-result
oracle repair, not a successful prospective original gate.

Any repaired check must preserve the substantive conservation requirement:
compare the complete reconstructed trace/operation inventory with the frozen
adapted input, retain all six structural/error oracles, and verify the resolved
usage aggregation according to source. It must not merely remove the failed
entry-node check. The four historical application extractions remain gated
until that evidence is reviewed and a separate acceptance record is frozen.

The resolved resource-demand literals are also retained: the artificial 0.005-
second leaf duration yielded approximately 0.002105263 seconds in the extracted
resource-demand field. This is not a demonstrated unit-conversion error; PMX
estimates resource demand using its performance pipeline and author defaults.
The original protocol already treats this as a separate timing diagnostic,
outside the structural/error qualification and outside a calibrated performance
claim. The raw envelope units and reconstructed execution timestamps remain
independently auditable.

This review does not change M9P, inspect its outcomes, or lower PMX's scientific
priority. It also does not convert the adapter controls into an availability
prediction comparison.

## Source finding and explicit repaired check

Static source run 34123438744 at
`de1c2ebbbb82965baf5126c4616c63c82c0723d6` succeeded without a dynamic
PMX invocation. Artifact 10019108592 contains 120 hash-verified Java files.
Its archive digest is
`1de0aec1eda328444b6f11436e47a7ea97822806f3483d7b97e556ad7739541e`;
the source manifest hashes to
`cdbd3b040000577aa1dea97e79d2c0f7677be5406a2a747782aabd69c0d3de59`.

`TransformerSystemToPCMBasic` constructs `PCMBuilder`, whose workload overload
calls `PCMUsageModelFactory2.createWorkload`. That method computes the minimum
positive invocation count `callsMin`, then emits `Math.round(calls/callsMin)`
entry nodes for each admitted operation. It finally hardcodes a closed workload
population of ten and zero think time. Thus the population is not an estimate
of the fixture's ten observations. For these fixtures, the source-implied entry
count is one for each root operation. The original ten-node oracle confused
observational multiplicity with the generated model's workload representation.

The repaired audit preserves every original structural/error check, requires
the source-implied entry counts and declared workload defaults, and adds exact
agreement between all frozen adapted `(trace ID, span ID, operation, parent)`
records and the labelled reconstruction blocks in the retained logs. It checks
each trace exactly once and matches reconstructed nanosecond bounds to the
microsecond input. This is a keyed inventory comparison, independent of stdout
operation-slot order. The core `Span` getters explicitly convert stored
microseconds back to nanoseconds, completing the reader-to-execution unit path.

The source also stores root-operation keys in a map indexed by first timestamp:
equal first timestamps can overwrite a key. These synthetic fixtures have
distinct first timestamps across root operations. The later application audit
must expose such collisions instead of interpreting a missing root as no
observed operation. Rounded relative usage counts and fixed population are not
a faithful replay of arbitrary observed traffic and cannot establish workload
or performance fidelity.

The repaired decision is explicitly post-result and runs only on the retained
six attempts. A positive repaired decision can support a separate acceptance
record for the bounded application-development census. It cannot rewrite the
original run as prospectively qualified or substitute for availability validation.
