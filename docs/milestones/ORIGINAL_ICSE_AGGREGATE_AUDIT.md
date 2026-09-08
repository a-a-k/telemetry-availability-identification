# Original ICSE table: compact aggregate reproduction

The author's local results.csv contains250 jobs:2 modes ×5 p values ×25 seeds. All750 accompanying scalar JSON files match the CSV exactly for model, live, per-endpoint values, p, seed,500000 MC samples and450 reported live windows/job. All40 mean/SD cells in the local camera-ready main.tex table reproduce at its printed four-decimal precision. Exact CSV/scalar bytes and SHA256 inventories are retained; no raw traces or application models were loaded.

## Arithmetic and units

| Mode | p | Model mean | Live mean | Signed error, pp | MAE over25 jobs, pp |
| --- | --- | --- | --- | --- | --- |
| norepl | 0.1 | 0.4182172 | 0.5533276 | -13.511040 | 13.511040 |
| norepl | 0.3 | 0.1612600 | 0.1774908 | -1.623080 | 1.623080 |
| norepl | 0.5 | 0.0454168 | 0.0375768 | +0.784000 | 0.784000 |
| norepl | 0.7 | 0.0013616 | 0.0067160 | -0.535440 | 0.535440 |
| norepl | 0.9 | 0.0000000 | 0.0000000 | +0.000000 | 0.000000 |
| repl | 0.1 | 0.6281448 | 0.6969136 | -6.876880 | 6.876880 |
| repl | 0.3 | 0.3053988 | 0.3054112 | -0.001240 | 0.158840 |
| repl | 0.5 | 0.1145196 | 0.0958120 | +1.870760 | 1.870760 |
| repl | 0.7 | 0.0132256 | 0.0155044 | -0.227880 | 0.227880 |
| repl | 0.9 | 0.0000000 | 0.0000000 | +0.000000 | 0.000000 |

Relative percentage error divides by live availability; percentage-point error does not. For example, norepl p.1 signed mean error is−13.51104pp, while its relative error is about−24.4%. With replication p.3 the signed mean is−.00124pp but mean absolute job error is.15884pp; cancellation is not exact equality of every prediction. Atp.9 both values are0 in all50 jobs; relative error0/0 remains undefined in the new audit, preserving the original CSV blanks. The old statistical report's replacement by0 is a separate convention, not new evidence of equivalence.

The summaries report112500 windows, but raw window/probe logs are absent here. Their success/attempt denominators and failure overlap cannot be reproduced from scalar means. Printed SD is across25 job summaries. No new inference treats112500 reported windows as independent observations.

## Provenance limits

Current GitHub metadata retains run20410544665/head77d709d219d7cf72aeb06904ac995bc596b1fc57. Its workflow uses seeds1,2 only and has20 artifacts; it is **not** the source of these250 jobs. The complete available102-run listing and matching artifact-name lookup did not establish the original250-job run. No ZIP digest identity is asserted from unpacked scalar files or similar filenames. The original run remains a historical reproducibility limitation.

Twelve exact source files from the separately retained20-job rerun are saved with Git blob/SHA256 and license. Its resilience.py,chaos.sh,pipeline_norepl.sh,pipeline_repl.sh andLICENSE match the published a4621f55937571173bb5bea098a527cf836913f1 selected bytes; README differs. The bootstrap clones the upstream benchmark without an immutable pin. Code agreement does not identify the original250-job runtime or data archive. Earlier isp ras artifacts are also kept separate.

See [aggregate audit](../evidence/original-icse-local-aggregate/aggregate-audit.json), [camera-ready table check](../evidence/original-icse-local-aggregate/camera-ready-table-check.json), and [scalar byte inventory](../evidence/original-icse-local-aggregate/scalar-member-hashes.json). No new independent/main campaigns, full-model fitting or application execution occurred locally.
