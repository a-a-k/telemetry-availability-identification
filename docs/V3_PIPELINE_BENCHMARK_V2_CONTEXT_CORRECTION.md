# Computational workload-copy context correction v2

Original run34555933526 and its data remain unchanged. Its1x trials pass the
complete forecast and solver checks. Its2x/4x graph trials are rejected with
`request trace context mismatch`: the benchmark's copy helper renamed trace IDs
independently of request IDs. The actual observation contract derives trace and
external-parent IDs from application and request ID. The original helper's
unit controls covered parent edges and unique IDs but missed that contract.

The correction uses the unchanged `boundary_context` function to derive both
copied trace IDs and the external parent boundary. Internal span IDs and parent
links are mapped bijectively; values, durations, failures, masks, probes, source
campaigns, multipliers, method order and timing boundaries remain unchanged.
No graph observation contract, PMX model algorithm or solver is changed. All356
scientific source locks remain.

An added artificial integration control executes the real observation binding
under all three application context contracts at1x/2x/4x and requires exact
equality of all estimates. Five helper controls pass. The original wrong-copy
results are retained as failed computational trials, never promoted to fast
successful forecasts or a scientific scalability failure.

Repeat the full27-pair grid with the corrected copy generator so each
application's three volumes share a coherent fresh runner and balanced order.
Do not combine favorable old1x times with corrected2x/4x times from another
runner. This is a technical benchmark correction after seeing the declared
context-check failure; no main accuracy results or independent n change.
