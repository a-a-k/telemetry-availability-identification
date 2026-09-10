# PMX clock-progress repair: frozen matched qualification v1

Frozen before dispatch. This is a development repair qualification using the six existing v2 calibration projections and four existing artificial PMX controls. It creates zero independent application campaigns, reads no business test outcomes, and cannot admit main. Original failures and frozen v1/v2 remain unchanged.

## Diagnosis and intervention

Original preflight34447262633 timed out after1800seconds on DeathStarBench split read_user_timeline. Exact-input diagnostic34455035486 repeated the same busy estimator. Source inspection34456400717 found the overlap-width/20 rule and a singleton series. The observer-only derived-JAR diagnostic34457354601 captured equal start/end1789023783.11267 seconds and a zero step, then timed out after120seconds. Original `RepositoryUtil` bytecode allows zero-width intersections; its exception only covers negative width. The intermediate observer-launcher rejection34457002082 occurred before any PMX execution and is retained separately.

The intervention changes only `EstimationSpecificationFactory` in the pinned author JAR. Keep the original width/20 step whenever it advances the representable clock. Otherwise use max(one nanosecond, one double ULP at the unchanged start). One nanosecond is the observation-interval unit already declared by the author adapter; ULP follows machine precision, not a fitted threshold. Invalid/nonfinite intervals or an unrepresentable advancing step are rejected. Preserve original start/end, all observations, window60, estimator choice, resource configuration, topology, operation names, failure estimators and bridges. No filtering, duplication, unit conversion, deadline, q or probability change is permitted. A guarded derived binary is labelled explicitly and never presented as an unchanged author binary.

The remote builder verifies the exact original JAR SHA and embedded factory source SHA, changes only the factory class and matching embedded source inside one original bundle, verifies every other member byte-for-byte, and records source/class/JAR SHA, Java compiler and release. Seven independently executed builds must yield one identical JAR hash.

## Prespecified checks

- Five compiled Java controls: observed zero-width epoch, zero epoch, positive interval whose width/20 cannot advance a double, ordinary positive interval, and rejected negative interval. Accepted cases preserve interval endpoints and advance time; ordinary width/20 stays unchanged.
- All20 saved application projections and four existing known-probability control projections pass the existing PCM component/operation/ownership/edge/allocation/probability checks and exact trace/span/parent/time reconstruction.
- All19 previously complete application projections and all four controls preserve every resolved field, including resource-demand literals, relative to the original output. The one originally incomplete projection must now complete. Each extractor uses the declared120second bound; no retries or larger bound can be selected from results.
- Both PMX variants retain their distinctions. Six conditional unsupported slots stay unsupported with null points; the two slots absent because of the timeout must become supported. No failed slot becomes an unsupported convenience case.
- The unchanged pinned Palladio solver executes every prepared model twice on all three application batches, including48 known-oracle solver records. Repeats agree within1e-12. All32 previously supported application forecasts remain within1e-12 of their original values. All40 variant slots are reconciled:32 unchanged points,6 unchanged unsupported slots,2 recovered points.

This uses saved projections and previous compact model forecasts, not newly sealed native roles. Historical projection/read records retain their original scope and cannot be used as proof of fresh independent isolation. Real inputs/models/solver payloads and the derived JAR remain in GitHub Actions. Only exact allowlisted compact reports are retained locally. Setup/build/extraction/solver stages and derived-binary use are disclosed; this is not a method-speed comparison.

Passing all checks only qualifies a candidate correction. It then requires a separate v3 comparison design/source freeze, a fresh full-duration preflight using a new development seed and namespace, full provenance/role/forecast audit, and explicit evidence-backed admission before main240. No accuracy or coverage target is used to select this repair.
