# V3 preflight rejected; LibReDE source diagnosis active

Preflight34447262633 completed all36 GitHub jobs, but independent admission audit34453903136 rejected two failed PMX forecasts from one1800second process timeout. [Exact result](milestones/V3_COMPARISON_PREFLIGHT_V2_FAILURE.md). Main remains0/240; no admitted source tag or main dispatch exists.

Remote diagnostic34455035486 reproduced the timeout on identical saved calibration bytes. Original and replay logs match exactly; the active thread is inside LibReDE resource-demand estimation. [Evidence and next source/time-axis inspection](milestones/V3_PMX_LIBREDE_DIAGNOSIS.md). The underlying defect is not yet established. All323 frozen sources remain unchanged; any repair requires a new version and fresh full preflight.
