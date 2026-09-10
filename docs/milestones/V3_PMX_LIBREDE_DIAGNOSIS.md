# V3 PMX timeout: exact-input replay and source inspection

10 September 2026. This is a development diagnostic, not admission or an independent comparison.

Run [34455035486](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34455035486), source `abfca26561acd80e71dd27b826410b30a8ab6304`, reproduced the v2 DeathStarBench split/NCD/r0 `read_user_timeline` timeout using the exact saved calibration projection and unchanged author JAR. The original watchdog was 1800 seconds; the declared diagnostic watchdog was 120 seconds. Both exited 124. Their stdout files are byte-identical: 928500 bytes, SHA256 `061077f8d6545ac7b45119e98d05cb0ae5a440fb482ff7615a42bdfd68dfd0e8`. Diagnostic completion is not PMX success.

Original GNU time records 1801.11 user seconds, 3.37 system seconds, 100% CPU and 878980 kB maximum RSS. A thread snapshot at 55 seconds places the active call chain in Colt matrix copy/setRow, `SimpleApproximation.update`, LibReDE estimation, PMX `ResourceDemandEstimationService.terminate` and `DataProcessingService.calculateResourceDemands`. This localizes the prolonged computation to resource-demand estimation; it does not yet establish the underlying defect. No exception/OOME/StackOverflow marker was found in the bounded log census. No valid PCM repository was produced. Startup failure is not supported by the active estimator stack and sustained CPU use.

[Retained compact evidence](../evidence/v3-pmx-timeout-diagnostic-34455035486/compact.json) has an exact one-member ZIP allowlist, provider byte count/SHA256 and CRC verification. The ZIP is 3771 bytes, SHA256 `86ce34e8b8202df3b3ba45d08c225f9421c0d624c80426c5a39a9846b80a00ac`. Full original/replay inputs and thread dump remain in remote artifacts. No test input or independent campaign was used.

## Prospective source inspection

`scripts/inspect_v3_pmx_librede_v1.py` and `v3-pmx-librede-inspection-v1.yml` inspect the same SHA-pinned JAR remotely, extract a declared list of relevant embedded Java sources, and inventory available sources/classes. They also aggregate counts and time ranges from the three saved operation calibration projections in the same provider-pinned extraction artifact. They execute no estimator and read no evaluator inputs. The compact/source artifact is restricted to `compact.json` and `source-inspection.json`; the JAR and native projection are never downloaded locally.

The next decision must follow source evidence. No stage is disabled, watchdog increased, timestamp changed or forecast reclassified in this diagnostic. A repair requires a separate version, declared semantic controls and a fresh full preflight. The original v1/v2 failures and all323 frozen source hashes remain intact. Main is still0/240.
