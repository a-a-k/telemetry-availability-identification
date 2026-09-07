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
