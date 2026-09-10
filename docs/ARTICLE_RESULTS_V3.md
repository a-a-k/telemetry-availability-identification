# Article results: audited history, mechanism and implementation evidence

Draft assembled on 10 September 2026. This chapter reports completed evidence for the [v3 methods](ARTICLE_METHODS_V3.md). It does not supply the still-pending independent main comparison. The [claim/evidence table](ARTICLE_CLAIMS_V3.md) limits attribution and generalization. At preparation, the corrected full-duration preflight `34447262633` is running at `e89e7ca91dd474d8cf2b8c4ed7c1ffc052d98569`; main remains 0/240.

## 1. Historical discrepancies survive arithmetic and provenance checks

The historical ICSE and AINA studies motivate the adequacy question, but they use their own endpoint/measurement contracts and failure designs. Their observations are not relabelled as the present ten whole-business-operation outcomes. Reproducing their aggregate arithmetic is also distinct from reconstructing every original runtime condition.

For ICSE, 250 retained job rows and 750 accompanying scalar JSON records agree, and all 40 printed mean/standard-deviation cells reproduce at the published four-decimal precision. The audit preserves the difference between percentage-point and relative error. For example, with replication at scenario p = 0.3 the signed mean difference is approximately -0.00124 percentage points, while mean absolute error across 25 jobs is 0.15884 percentage points. Cancellation of signed differences therefore does not establish equality of individual predictions. When both observed and predicted values are zero, relative error 0/0 remains undefined. The reported 112,500 windows cannot be independently reconstructed from the surviving scalar means: raw window denominators and the exact 250-job execution provenance remain unavailable. A surviving 20-job rerun is not substituted for that source. These results and limits are recorded in the [ICSE aggregate audit](milestones/ORIGINAL_ICSE_AGGREGATE_AUDIT.md).

For AINA, all 250 nested original archives match the retained provider digests. The audit reconciles 25,000 windows and 2.5 million probes, including exact success/attempt counts. The original aggregate calculations reproduce to floating-point precision. Nevertheless, the discrepancy between the original graph estimate and observation changes sign and remains substantial at both extremes of the declared scenario parameter.

| Original scenario p | Original graph estimate, all-block MC | Observed probe frequency | Signed difference, pp |
| --- | ---: | ---: | ---: |
| 0.1 | 0.780945236 | 0.682630 | +9.831524 |
| 0.3 | 0.610407776 | 0.557032 | +5.337578 |
| 0.5 | 0.356400884 | 0.359702 | -0.330112 |
| 0.7 | 0.250870400 | 0.289356 | -3.848560 |
| 0.9 | 0.050005696 | 0.171918 | -12.191230 |

![Historical AINA aggregate estimates, observed probe frequencies and signed differences](figures/aina-audit-v3.svg)

*Figure 1. Recomputed original AINA aggregates from the retained five-scenario summary. The left panel contrasts the original Monte Carlo graph estimate with observed probe frequency; connecting segments guide the eye between the five scenarios. The right panel shows their signed difference in percentage points. These are descriptive historical aggregates, not v3 business-operation validation or a causal decomposition. No inferential error bars are implied. The original fixed-cardinality quantization of p is preserved. The [vector PDF](figures/aina-audit-v3.pdf), [source/provenance and exact values](figures/aina-audit-v3-provenance.json), and [rendering script](../scripts/render_article_aina_figure_v1.py) preserve this figure's derivation without processing raw traces or rerunning a model locally.*

The original global graph estimate gives equal weight to the four endpoint estimates; the separately retained realized-endpoint-mix diagnostic is not substituted here. Signed aggregate differences in this table are not per-window MAE. The [full AINA audit](milestones/ORIGINAL_AINA_FULL_AUDIT.md) additionally checks the original graph simplification exactly. Across 20 distinct graph/replica byte pairs and all 32,768 allowed failure states per pair, the asynchronous and all-block predicates differ on no endpoint state. This is 655,360 pair/state controls under the source's declared failure universe, rather than a nonsignificant comparison of sampled predictions.

The exact global probabilities agree in both modes: 82/105, 1111/1820, 139/390, 137/546 and 1/20 at the five scenarios. This invariance does not validate the live model, since both equal graph predicates can disagree with measurement. Nor does it reproduce the literal published numerical bound of at most 0.001 percentage points for every retained Monte Carlo difference: the largest retained global difference is approximately 0.0053024 percentage points, and an endpoint difference reaches approximately 0.0068896 percentage points. The exact semantic result and finite Monte Carlo outputs must be distinguished. The retained Monte Carlo errors are compatible with the audit's stated simultaneous numerical bound; no new Monte Carlo draws were added to replace the originals.

A separate [timing-feasibility audit](milestones/ORIGINAL_AINA_TIMING_FEASIBILITY.md) examines the documented controller period, sequential probes and timeout configuration. Conditional duration lower bounds exceed the nominal 60-second controller period in 3,483 of 25,000 windows. These bounds indicate a measurement-alignment concern, but do not reconstruct actual per-probe times or establish exact fault overlap. Original application images/runtime identity are not fully pinned. The discrepancy is reproducible as an observation; its historical cause is not established by these checks.

## 2. One independently controlled routing mechanism

H-EXEC tests a specific mechanism on the declared OpenTelemetry checkout operation. Each of eight blocks contains fresh deployments under sham, transition, settled and repaired conditions. In the settled condition, replica a remains paused while b remains available; the repaired condition retains the pause and removes a from routing. The test concerns execution under that routing policy, rather than using prediction error alone to infer a cause.

The final immutable-input audit qualifies all 32 study cells, retaining 15,360 business attempts across the full recorded periods. The measured test periods contain 3,840 business attempts, including 1,280 checkout attempts, and 480 static controls. All originally retained request rows and statistics remain unchanged.

| Registered co-primary checkout contrast | Mean block difference | Exact two-sided label-swap p | Registered decision |
| --- | ---: | ---: | --- |
| Sham minus settled | +100 pp | 0.0078125 | Passes alpha = 0.025 and the 5 pp minimum-effect condition |
| Repaired minus settled | +100 pp | 0.0078125 | Passes alpha = 0.025 and the 5 pp minimum-effect condition |

Every measured settled checkout attempt fails and selects a: 320/320 across the eight blocks. All 320 repaired attempts and 320 sham attempts succeed. Thus the availability of a live alternative is insufficient for this whole operation under the tested selection policy, and the declared routing intervention restores success within the experiment. Static controls succeed 120/120 in each arm. Their observed stability is not a statistical equivalence claim.

Both primary contrasts have eight identical block differences of one. The registered 10,000-draw paired-block bootstrap therefore returns the degenerate 97.5% display interval [1, 1]. This does not prove an exactly 100-point population effect or guaranteed finite-sample confidence coverage. Browse/cart diagnostics remain secondary and do not replace a primary result. The [H-EXEC confirmation](milestones/H_EXEC_01_SEALED_STUDY_CONFIRMATION.md) supplies complete block, route and static-control evidence.

The initial study gate qualified 31/32 cells because one native-parser cleanliness check failed. A separately versioned replay on the final immutable uploaded inputs qualified the remaining cell while preserving all request outcomes and inferential results. A concurrent append is a plausible explanation for the original parser failure, but the precise bytes observed at that moment were not retained. This repair is evidence about input integrity, not another independent experiment or an extra block. The result supports one scoped mechanism; it neither identifies a mediation fraction nor explains the historical AINA bias.

## 3. Model-derived forecasts are technically reproducible

The ordinary-observation identity qualification links native host identity, external request context and the declared replicas, while preserving the external-attempt denominator. Source inspection declares required and ignored call groups; their runtime graph relations are still extracted from observed native spans. This division matters: source semantics do not license a replacement graph template, and a recorded call does not alone establish that it is mandatory.

The qualified execution binding v2 produces ten saved point models on 4,080 previously opened calibration attempts. Six ordinary inputs are read by each builder, and a separate process reproduces each saved-model calculation. Removing each of 44 bound required edges makes the relevant execution result zero; equivalent edge ordering preserves the complete result. Six operations unaffected by the preceding observation correction retain exactly the same numerical-result hashes. These checks establish that the discovered graph enters the calculation and that the saved model is sufficient for replay. They do not establish independent forecasting accuracy.

| Technical calibration operation | Joint reachability | Execution functional | Scope |
| --- | ---: | ---: | --- |
| DeathStarBench compose/home/user timeline, each | 1 | 1 |80 opened normal attempts per operation |
| OpenTelemetry browse/cart/checkout, each | 1 | 1 |80 opened normal attempts per operation |
| Petclinic list owners / list vets, each | 1 | 1 |900 opened attempts per operation; declared fixture/cache scope |
| Petclinic create visit |781/900 |728/900 |900 opened attempts; declared L7 eligibility and persistence audit |
| Petclinic owner details with visits |17/20 |714/900 |900 opened attempts; full declared fixture |

The [execution qualification report](milestones/V3_APPLICATION_EXECUTION_V2_RESULT.md) retains real masks even where E is point identified. A known failed guard or deadline can fix the event while some entry, demand or database coordinates remain unknown. Accordingly some ablations are ambiguous although the full execution functional is a singleton.

The Petclinic calibration also exposes a semantic-adequacy limit. External semantic frequencies are 741/900 for create visit and 727/900 for owner details, exceeding the execution estimates by 13/900 in each case, approximately 1.4444 percentage points. These aggregate differences are not a count of 26 individually established false-negative requests or a causal attribution to one guard. The no-selection ablation changes the estimates, but does not prove a real-world mechanism for the residual discrepancy. No compensating q was fitted. The theoretical relation between B and E remains exact while its additional equivalence assumption Y=E is unestablished.

G0's separate [source-adapted qualification](milestones/V3_G0_QUALIFICATION_V1_RESULT.md) supplies ten point forecasts, ten exact saved-model replays and 41 structural controls. Its fixed-k quantization and all-attempt eligibility-based parameterization are explicit. The earlier AINA probability law is not silently represented as an unchanged application of the new observation contract.

## 4. Full-duration preflight exposes coverage and an integration defect

The first full prospective-pipeline preflight,run `34442870952`, executes six development campaigns and retains all 200 planned current-method slots. All six acquisition/evaluator gates qualify, covering 21,600 test attempts. Seventeen execution models replay exactly. Gstar is point identified in 10/20 operation cells; seven cells have ambiguous identified ranges and three are unsupported because of an unexplained native parent boundary. GID and G0 have 17/20 points; B0 has 20/20. These coverage findings are retained, including every null point and reason.

All six application PMX projections fail before Java extraction because the new eight-field request role lacks the legacy adapter's per-row `profile` metadata. Both PMX columns therefore have 20 explicit missing forecasts. The independently prepared controls nevertheless yield 48 correct solver records across the three application batches. This separation demonstrates why positive solver controls and successful graph jobs are insufficient to declare the entire comparator integration qualified.

The [full preflight failure report](milestones/V3_COMPARISON_PREFLIGHT_V1_RESULT.md) preserves the artifacts, traceback excerpts, qualified subchain and complete remote descriptive analysis. Graph/replay/evaluator reads are checked against their roles; candidates remain unchanged when all-sequence and stable outcomes are scored; all candidate-freeze jobs finish before the closed evaluator downloads. The global admission gate correctly remains false because application PMX forecasts are absent.

The [v2 correction](V3_COMPARISON_V2_REQUEST_PROFILE_CORRECTION.md) derives the legacy wrapper's profile from the sealed campaign identity, preserves the eight-field input files and rejects extra fields. Exact-schema controls reproduce the original error and show equivalence to the qualified legacy projection with that metadata supplied explicitly. It changes no graph functional, native observation, PMX failure policy or outcome. Its full-duration preflight uses a new registered seed and namespace; v1 is preserved as failed development evidence.

## 5. Independent main results remain a separate obligation

The 240-campaign main series has not yet been admitted. Consequently this chapter makes no Gstar-versus-PMX/G0 superiority claim, no equivalence claim, and no claim that the final model is independently adequate across three applications. Completed mechanisms, arithmetic audits, technical controls and development forecasts cannot substitute for that series.

The final main section must report all 800 planned operation cells per method, support and absence reasons, own/common-support errors, the six prespecified paired contrasts, all-sequence/stable distinctions, source-only transfer coverage, measured stage/process costs and unresolved quantities. The reported source-only transfer procedure currently identifies no target point under an unrestricted changed joint law. That limitation must remain visible alongside current-campaign results, and target-calibrated rebuilding must not be relabelled as transfer.
