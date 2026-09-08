# Complete historical prefix refit: strict replay boundary

[Run 34218526868](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34218526868), head `e6f2c11afe9d4b51b466b4d2ba9f66573d8fbfe9`: preparation and all three application builders succeeded. All **168** cases produced sealed legacy/corrected predictions, **17,856 slots/version** including absences. The final strict parity job failed on **30** probabilities; do not describe the whole run as successful or the refits as an independently validated new study.

All mismatches are nonidentified B3 trace_only DeathStar transfers in 15 campaign×mode cases. The largest mismatch is 4.157058851480666 p.p., while likelihoods differ by at most 2.2737367544323206e-13. The status is `raw_unidentified_optimizer_point` in both versions. All probabilities outside B3/trace_only match their historical values within 2.102008200832728e-8, below the original 1e-6 replay threshold. No status or absence changed.

Across old/corrected refits, 2,667 probability slots differ by more than 1e-12, with zero status changes. None of the trace_only probabilities or other row fields changes. Every row is also identical when the source calibration health decoding is unchanged. This supplies the computational side of the [dependency protocol](../HEALTH_PREFIX_DEPENDENCY_AND_RESCORE_PROTOCOL.md), with a source argument and bounded actual-likelihood control. That protocol preserves exact historical values for all 7,776 unaffected slots and requires strict replay for the 10,080 affected slots; its remote qualification/scoring are pending at this record.

| proposed / full / current | Finite common / slots | Minimum probability change, p.p. | Maximum probability change, p.p. |
| --- | --- | --- | --- |
| DeathStar | 210 / 240 | -0.02746784536 | 0.08559791980 |
| OTel | 160 / 240 | 0 | 0.17086133995 |
| Petclinic | 32 / 32 | 0 | 0.48725175254 |

For proposed/full transfer, maxima are 0.10239829085, 0.20774018010 and 0.51404679795 p.p. respectively. Historical B0 is exactly unchanged. These are forecast differences, not MAE differences or improvements. For fixed all-sequence outcomes/support, the absolute-error change is bounded by the absolute forecast change; consequently this decoder correction alone cannot explain the previously observed large OTel checkout error. Stable-window metrics need an explicit membership rescore.

Exact compact evidence is in [five verified ZIPs](../evidence/health-prefix-refit-34218526868/verified-archives.json); every member is preserved inside its ZIP and separately hashed. Expanded short summaries include [failed qualification](../evidence/health-prefix-refit-34218526868/prefix-comparison/qualification.json) and [all 30 mismatches](../evidence/health-prefix-refit-34218526868/prefix-comparison/parity-mismatches.json). Full learner archives were not downloaded locally. Reproducer `scripts/retain_health_prefix_refit.py` admits only prediction/diagnostic roles and explicit member names.

Source data/config/seeds and the original prediction tables remain unchanged. These are the historical two-path M7/Petclinic models using privileged runtime observations, not the ordinary graph G* candidate. PMX was not reexecuted. No new main/test campaign or accuracy scoring has occurred in this refit stage. All 30 v3 criteria are updated in iteration 018.
