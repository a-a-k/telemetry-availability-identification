# M9T: learner-only external-request correspondence census

This is preparation for the independent PMX comparison, not an effectiveness
experiment. It uses all four preserved M7 NCD/r0 native audit samples, the same
two applications and placements as M9Q. Each sample's baseline/calibration
request identities and outcomes come from its sealed learner bundle. Test and
sentinel request identities are excluded. Native parsing, including this census,
runs only in GitHub Actions; no extractor, solver or fitting is invoked.

Before reading these new diagnostics, specify the following complete tables.
Keep all operations and both learner periods, without selecting an operation
or observation policy by favorable errors:

1. External request counts, semantic successes, timeouts, missing or invalid
   traces, native root multiplicity, and successful requests with span errors.
2. For every observed operation, invocation/error counts and parent-root counts
   within each external request class. Compare three descriptive projections:
   all observed spans, explicitly marked SERVER spans, and native service-boundary
   spans (root or service different from the recorded parent).
3. Under each projection, contract unselected ancestors and count parent errors,
   child errors, their intersection and child errors with a successful parent.
   Retain denominators with no child error and parent errors within that set.
4. Retain observed call edges, per-request operation coverage and maximum repeated
   calls. Do not convert overlapping marginal errors into independent local
   parameters or call a projected missing-parent root an external request.

These policies are inspected to define a source-grounded operation boundary.
The service-boundary policy is not asserted to recover a SERVER kind absent from
the original instrumentation. No policy is already a qualified PMX comparator.
Cross-tables can expose swallowed/propagated errors and absent-request selection,
but cannot establish counterfactual independence or complete instrumentation.

Download and verify the exact retained M8 source archive and independent M8A
inventory used by M9Q. Recheck every selected native file and each learner
request seal. Retain aggregate JSON tables and provenance, without publishing
new request-level data locally. Jobs have 360-minute limits; artifacts retain
for 90 days. M9S solver qualification proceeds independently, and this census
does not alter any historical gate or count as the final comparison.
