# Historical decoder correction: complete M7 and opened PMX comparison

[Run 34220234444](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34220234444), head `38f5e01c7f5003a3cde84afc647fe4d2f3ae1180`, passed the frozen [dependency qualification and rescore protocol](../HEALTH_PREFIX_DEPENDENCY_AND_RESCORE_PROTOCOL.md). The earlier strict refit replay remains failed for its 30 nonidentified trace_only/B3 transfer points. No tolerance was relaxed and no extra fitting was performed to make those points match.

The new correction qualifier verified **10,080 affected-input slots** against the original replay criterion, and retained exact historical rows for **7,776 unaffected slots**. In its mutually exclusive bookkeeping, 4,608 slots have unchanged full-file decoding and another 3,168 have health_policy none. Equivalently, all 4,320 trace_only slots are unchanged, with another 3×1,152 unchanged-file slots in other modes. Every carried row had exact old/corrected equality inside the paired refit. All source health hashes and changed-tick counts matched the complete census.

## Complete M7 rescore

Every historical score identity, attempt/success count and checked numerical score field was reproduced with maximum absolute error **0.0** using the exact original prediction table. Each of the four prediction/window combinations has **34,560 complete census slots**, including all absences, and **36,459 scored rows** over the three historical views. All 160 campaigns and all **576,000** all-sequence attempts remain. Corrected stable selection contains **435,761** attempts versus historical **435,288**; these are membership changes, not newly acquired observations.

| M7 proposed / full / current / all_sequence | Finite campaign cells | Historical MAE, p.p. | Corrected MAE, p.p. |
| --- | --- | --- | --- |
| DeathStar compose_post | 65/80 | 3.586739097 | 3.606463625 |
| DeathStar read_home_timeline | 80/80 | 0.617283951 | 0.617283951 |
| DeathStar read_user_timeline | 65/80 | 6.689702321 | 6.709870862 |
| OTel add_to_cart | 51/80 | 7.832805851 | 7.846966285 |
| OTel browse_product | 54/80 | 9.181432010 | 9.200266692 |
| OTel checkout | 55/80 | 24.462231878 | 24.486352506 |

Prediction coverage/status is unchanged. This small correction does not explain the large checkout discrepancy and does not improve all-sequence MAE. M7 is still the historical fixed-two-path model, not the main graph G*.

The **original M7 primary contrast is sampled_mixed/stable**, proposed−B2 in Brier score, not the full-mode tables above. It still has 117 paired campaigns out of the 160-cell design. Its four-corner audit is:

| Predictions | Stable mask | ΔBrier | Historical 95% interval | Two-sided p |
| --- | --- | --- | --- | --- |
| Historical | Historical | 0.000232717380 | [-0.001658600756, 0.002124035517] | 0.685283076 |
| Historical | Corrected | 0.000234721636 | [-0.001669113332, 0.002138556604] | 0.684838201 |
| Corrected | Historical | 0.000210291887 | [-0.001692128728, 0.002112712501] | 0.715952635 |
| Corrected | Corrected | 0.000212313797 | [-0.001702533318, 0.002127160911] | 0.715273182 |

No superiority is established; nonsignificance is not equivalence. These remain the original historical contrast definitions, not the six prospective v3 primary contrasts. Corrected full/current all-sequence complete-campaign MAE contrasts proposed−B0 are **+2.311261507 p.p.** for DeathStar (65 complete paired campaigns, descriptive 95% [2.013719060, 2.601982684]) and **+9.521964217 p.p.** for OTel (51, [8.617186174, 10.411668002]). The overall common operation-cell counts are 210 and 160 respectively; application contrasts use only complete campaigns, i.e. 195 and 153 operation cells. Partial common campaigns are retained in operation-level tables.

## Opened M9X comparison updated

The same four NCD/r0 campaigns, twelve operation cells and 14,400 all-sequence attempts were rescored. All 108 candidate slots are retained. The **24 PMX candidate objects and 12 endpoint_all objects are unchanged**; the 72 M7 mode/method slots use the accepted corrected version. Old M9X arithmetic reproduces to 8.326672684688674e-17. All three views and both M7 modes are included in machine-readable evidence, with four prediction/window combinations.

For full/all_sequence, proposed own MAE changes **6.120840643→6.143609626 p.p.** on 5/12 cells and B2 **4.960446323→5.016333519** on 5/12. B0 remains 2.901453650 on 12/12; PMX inclusive remains 9.152744114 on 12/12 and conditional_local 2.444444444 on 6/12. Unequal own coverage does not support a global ranking.

Corrected proposed−PMX paired ΔMAE: DeathStar inclusive **+4.676166963 p.p.**, conditional_local **+3.212364880**, each on 4/6 common cells; OTel inclusive **−0.989247206** on only 1/6; OTel conditional_local common coverage is 0/6, **not estimable**. No CI/new confirmation is attached to four opened campaigns. The corrected common stable selection is 10,132 attempts versus 10,204 historical; PMX stable scores can therefore change even though PMX forecasts do not.

Exact [updated M9X tables](../evidence/m9x-health-prefix-34220234444/tables.md), [four-corner aggregates](../evidence/m9x-health-prefix-34220234444/correction.json) and per-corner scores are reproduced by `scripts/report_m9x_health_prefix.py` from compact aggregate evidence only. The original [M9X report](M9X_INDEPENDENT_PMX_DEVELOPMENT_COMPARISON.md) and all its sealed evidence remain unchanged in historical decoder-v0 scope.

## Evidence, cost and remaining scope

[Compact rescore report](../evidence/health-prefix-rescore-34220234444/rescore.json), [dependency qualification](../evidence/health-prefix-rescore-34220234444/dependency-qualification.json), and [two exact archives](../evidence/health-prefix-rescore-34220234444/verified-archives.json) retain every aggregate table member/hash. Compact artifact `10053518290`: 19,299 bytes, SHA256 `83677fd4f9b71137992264c6ac46f85c93dc5d266c029fdd6e6eb1df69c95c83`. Compressed tables artifact `10053519476`: 7,006,299 bytes, SHA256 `b8d144b68495060fe093803a13eeacc8df5bf80cdc4920738fe4c746d407c61b`. Sizes, API hashes, CRC and every table/member digest passed; large aggregate members stay compressed locally. Raw/native/learner archives were not downloaded locally.

This rescore process took 159.35 s wall, 156.51 s user CPU, 0.89 s system CPU, peak RSS 555,888 KiB. These are audit/reporting costs, not estimator acquisition/build/solve cost or evidence of speed over PMX.

The correction is complete for the **160 M7 historical campaigns, eight Petclinic technical fits and their opened M9X comparison**. Auxiliary historical localization/routing/failover and temporal-confirmation consumers still use decoder v0; the [static callsite audit](../evidence/health-prefix-callsite-audit.json) identifies direct consumers but is not an exhaustive runtime effect audit. Their old versioned results are not imported as corrected v3 evidence. If used again, they require explicit scope and reanalysis. New graph-method adequacy, three-app technical admission, causal mechanisms and the main series remain open. Main campaigns added: **0**.
