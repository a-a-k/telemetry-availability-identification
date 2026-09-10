# V3 PMX timeout: exact-input replay and source inspection

10 September 2026. This is a development diagnostic, not admission or an independent comparison.

Run [34455035486](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34455035486), source `abfca26561acd80e71dd27b826410b30a8ab6304`, reproduced the v2 DeathStarBench split/NCD/r0 `read_user_timeline` timeout using the exact saved calibration projection and unchanged author JAR. The original watchdog was 1800 seconds; the declared diagnostic watchdog was 120 seconds. Both exited 124. Their stdout files are byte-identical: 928500 bytes, SHA256 `061077f8d6545ac7b45119e98d05cb0ae5a440fb482ff7615a42bdfd68dfd0e8`. Diagnostic completion is not PMX success.

Original GNU time records 1801.11 user seconds, 3.37 system seconds, 100% CPU and 878980 kB maximum RSS. A thread snapshot at 55 seconds places the active call chain in Colt matrix copy/setRow, `SimpleApproximation.update`, LibReDE estimation, PMX `ResourceDemandEstimationService.terminate` and `DataProcessingService.calculateResourceDemands`. This localizes the prolonged computation to resource-demand estimation; it does not yet establish the underlying defect. No exception/OOME/StackOverflow marker was found in the bounded log census. No valid PCM repository was produced. Startup failure is not supported by the active estimator stack and sustained CPU use.

[Retained compact evidence](../evidence/v3-pmx-timeout-diagnostic-34455035486/compact.json) has an exact one-member ZIP allowlist, provider byte count/SHA256 and CRC verification. The ZIP is 3771 bytes, SHA256 `86ce34e8b8202df3b3ba45d08c225f9421c0d624c80426c5a39a9846b80a00ac`. Full original/replay inputs and thread dump remain in remote artifacts. No test input or independent campaign was used.

## Prospective source inspection

`scripts/inspect_v3_pmx_librede_v1.py` and `v3-pmx-librede-inspection-v1.yml` inspect the same SHA-pinned JAR remotely, extract a declared list of relevant embedded Java sources, and inventory available sources/classes. They also aggregate counts and time ranges from the three saved operation calibration projections in the same provider-pinned extraction artifact. They execute no estimator and read no evaluator inputs. The compact/source artifact is restricted to `compact.json` and `source-inspection.json`; the JAR and native projection are never downloaded locally.

The next decision must follow source evidence. No stage is disabled, watchdog increased, timestamp changed or forecast reclassified in this diagnostic. A repair requires a separate version, declared semantic controls and a fresh full preflight. The original v1/v2 failures and all323 frozen source hashes remain intact. Main is still0/240.

## Source-inspection result and next discriminating check

Source inspection [34456400717](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34456400717), head `cbe92eec0aacad1f368bc2f92d509b567444e91c`, completed. Its exact two-member artifact is21158 bytes, SHA256 `7a9ee999701264adbd216010b01995c1399ad74c5c6cf0c225ee85bd59d07b48`, id10143663655. Provider length/digest and both members/CRC were verified; source text is kept in the ignored inspection directory and remote artifact, with source hashes and aggregate calibration census retained in [compact evidence](../evidence/v3-pmx-librede-inspection-34456400717/compact.json). No estimator was executed in that inspection.

The OTLP `EstimationSpecificationFactory` chooses the maximum overlapping time interval and sets step size to its width/20. It falls back to the maximum interval only when `NonOverlappingRangeException` is thrown. The failed projection has1200 traces,4746 spans and seven service-operation identities; one identity has exactly one span. The other two operation projections have no singleton identity. The projection's declared microsecond time range is1188.025310 seconds, versus899.255099 and899.500412 seconds for compose/home. Long spans and a singleton are observed; neither alone establishes the timeout's cause.

The concrete next hypothesis is that the singleton creates a zero-width overlap and therefore a nonadvancing LibReDE clock. `diagnose_v3_pmx_step_v1.py` records the actual LibReDE configuration immediately before execution. It recompiles only the byte-pinned embedded `LibReDEAdapter` class with an observer that saves an Ecore copy of the configuration. The original method call, configuration, calibration bytes and120second diagnostic watchdog remain unchanged; both original and observer JAR/source hashes are reported. The observer JAR is explicitly derived and is not credited as the original comparator. The script also obtains bytecode listings of the exact bundled LibReDE clock/range/estimator classes and the embedded time-conversion source. Raw XMI and replay files stay remote; local retention is limited to compact scalar config and source/bytecode inspection.

This diagnostic does not disable resource-demand estimation or change intervals. No repaired comparator is admitted. The time-unit path in the author's reader is also being checked against the adapter's declared microsecond representation; an apparent source-level mismatch is not yet treated as an established runtime error.


### Observer launcher failure preserved; v2 diagnostic correction

Run34457002082 at `b265921a7de326237530e8d5a9edc6b1fee5f2c7` compiled the observer class and retained exact bundled bytecode listings, but did not execute PMX. The unchanged standard launcher correctly rejected the derived JAR with `ValueError: PMX binary differs`. This is a diagnostic integration error; it supplies no runtime configuration or additional timeout observation. The failed attempt and its compact artifact remain retained (id10143906967,24176 bytes,SHA256 `d720c26bbe0552dcd9e05fae3b96fc9d5febed62c94d0b009cc8553168d58d85`).

The separate `diagnose_v3_pmx_step_v2.py` uses `run_pmx_derived_diagnostic_v1.py`, which requires an explicit generated JAR SHA256 and the declared120second bound. It preserves the standard launcher's command/startup/cwd/process behavior but labels the derived binary explicitly. No frozen production source is modified and no original-JAR check is weakened. The new diagnostic also records the original and observer adapter bytecode plus the exact reader bytecode to check source/runtime correspondence. It is another attempt at the same development diagnostic, not a new independent campaign.

The earlier M9Q and current19 qualified operation reconstructions already verify exact microsecond-to-nanosecond bounds at runtime. That evidence argues against changing timestamp units based only on the apparent reader-source conversion. No unit change is proposed without resolving the complete runtime path.


## Actual zero-step configuration recovered

Observer diagnostic34457354601, head `d76331036182e52028cf4391a957a4651ede5880`, completed its diagnostic and timed out its observed PMX process after120.1724seconds. It captured the actual start/end as1789023783.11267 seconds, window60, ResponseTimeApproximationApproach, and zero-valued stepSize (default zero omitted from its serialized Quantity). The observer binary SHA is `90f64c618640be4d6d70a3412fb914f8512a3bf883bbe929f4c38fc5d7173e9d`; the unchanged input hashes were verified. [Compact evidence](../evidence/v3-pmx-step-diagnostic-34457354601/compact.json) and remote source/bytecode artifact have exact provider identity10144127107,36928bytes,SHA256 `b27788ea6a48f1be23f99231fea17cc502f01a4d9b4c334cf06fc8961974a110`.

A minimal representable-clock-progress repair is now specified in the [frozen matched qualification protocol](../PMX_CLOCK_PROGRESS_QUALIFICATION_V1.md). It preserves all interval endpoints and samples. All20 existing operation projections, four controls, seven reproducible builds,48 solver oracle records and32 previously supported point forecasts are prespecified before execution. No source-only symptom is substituted for this matched check, and no main admission is implied.
