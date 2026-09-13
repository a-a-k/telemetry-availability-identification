# Technical continuation of the fixed completion-target experiment

Original run 34750276041, source cd594e65e27dd6661f25faef60401774cf001790,
stopped in all three jobs while preparing the first copied input. The imported
JSON reader accepts Path objects, while two configuration reads in the new
driver supplied strings. No timed subprocess or semantic-model reconstruction
was reached; the full-evidence upload consequently found no files. All three
original compact failure artifacts and original run status are preserved.

The v2 entrypoint adapts the driver's read dependency to Path and selects the
v2 execution config. The v1 driver, timing worker, target algorithms, masks,
declarations, protocol, source data, 81 cost positions and 120 semantic positions
remain byte-identical. The entire first measurement is run with that one path
adaptation. This is not selection among measured timings or a semantic correction.
The producer commit and configuration digest belong to this continuation and
must not be attributed to the original failed run.
