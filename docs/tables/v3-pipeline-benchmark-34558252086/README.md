# Complete verified pipeline timing and telemetry scaling

Run 34558252086; execution head 1e77d94cb3b4ea5f074225f232ce51cd4a0f29f5. All 27 planned timing pairs are retained. These are computational repetitions of three previously observed calibration campaigns, not new independent observations or accuracy experiments.

`pipeline-summary.csv` reports median/min/max of three paired rounds per application/volume. The speedup is the median of individual PMX/graph wall ratios, not a ratio silently reconstructed from unlike stage medians. Raw pairs and every process measurement accompany it. Failure rows remain explicit and do not enter successful ratios.

The complete computational boundary starts with sealed permitted calibration files and installed software, and ends with saved, verified forecasts. Graph timings include all eight methods and exact fresh-process replay. PMX timings include both variants, known-probability controls, two solver passes, all process starts, projection/extraction and serialization. These are implemented verified pipelines; graph time is not an isolated Gstar-only kernel. Acquisition, source transfer, common role projection, workload creation and installation precede this boundary.

The PMX launcher has 20 s per operation, included in the primary measured time. Startup-subtracted values are arithmetic decompositions of that same measurement, not measurements of a rewritten faster implementation. Dependency/compiler setup is separate. Process CPU sums use disjoint child commands; memory is the largest of sequential process/children peaks, not whole-runner or parent-orchestrator RSS.

Volumes 1x/2x/4x preserve structure, masks, values, durations and the empirical state law; only unique observation IDs and multiplicities change. Original point/status/bound equality to 1e-12 is required. Probe rows are shared at the unchanged timestamps. This is scalability with telemetry volume, not with deployed service count, state-space complexity or time dependence. Ratios/exponents are descriptive for these finite workloads, with no asymptotic or statistical superiority claim.

The original-main accounting table sums only separately timed commands over the full 240 campaigns, including the original repeated binary compiles and application-wide analyzer batches. It is an execution-work inventory, not calendar elapsed time or a matched pipeline speedup; setup policy and hardware jobs differ from the new paired benchmark.
