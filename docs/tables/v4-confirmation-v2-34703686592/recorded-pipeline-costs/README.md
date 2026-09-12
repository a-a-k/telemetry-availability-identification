# Recorded cost scopes

These tables copy existing observations from the compact comparison. They do not rerun a model or introduce another statistical contrast. Empty numeric cells represent missing measurements. The original pooled stage summaries remain unchanged in the parent result tables.

| Table | Observation unit | Interpretation |
| --- | --- | --- |
| stage-observations.csv | Recorded campaign or operation stage; the operation column identifies operation-level timers | Graph-family extraction, identification and functional evaluation are shared across graph variants. B0 identification is timed across the campaign's operations. Observation counts and units must accompany duration comparisons. |
| process-resources.csv | One timed process/children report, or one deduplicated application solver batch | Wall time, user/system CPU and maximum RSS have their recorded process scope. They are not whole-deployment resource measurements. Batch resources include their actual preparation, controls and repeated solves. Overlapping stage/process times and concurrent RSS peaks cannot be summed into a total. |
| pmx-model-timings.csv | One existing model-load/solve invocation, retaining model variant and repetition | Original nanosecond values are preserved. Individual model timers and batch totals have different boundaries. The two verification passes are not independent experimental campaigns. A model without a timing has an explicit row with null measurement. |
| pmx-extraction-timings.csv | One independent PMX extraction process for a campaign operation | The measured duration includes the declared launcher startup. Startup and extraction are not both charged as independent elapsed intervals. |
| pipeline-inputs-and-unknowns.csv | One campaign pipeline role | Role bytes and loading/process durations retain their original boundaries. Shared acquisition observes the combined instrumented experiment; it is not a measurement of the minimum acquisition cost of each method in isolation. |

Graph operation-stage timers are available only where the implementation records them. A missing structural binding can omit these stage observations while its campaign process cost remains measured. Point forecast support, interval support and timing support therefore differ. A fast bound calculation is not automatically an accurate or point-identified forecast.

GNU-time RSS describes the timed process and its accounted children, not the simultaneous sum of application containers or total machine memory. CPU and wall intervals include only their recorded commands. Existing within-process stage timers can omit interpreter/JVM setup included by a surrounding process timer. No speed ratio is inferred by dividing unlike scopes.

Historical integration labor is unmeasured. Incremental updating is unmeasured; fresh reconstruction is a separate application of the implemented method. Monitoring off/on overhead and scalability are unmeasured. None is replaced with zero or inferred from inexpensive solver calls.
