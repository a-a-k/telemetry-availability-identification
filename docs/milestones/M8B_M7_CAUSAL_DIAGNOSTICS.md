# M8B: M7 discrepancy decomposition

## Outcome

M8B is complete as a post-result diagnostic milestone. The accepted workflow
reconstructed temporal strata for all 576,000 M7 test requests, decomposed the
saved predictions and observations by application, operation, law, and
placement, inspected successful-trace target support, audited semantic outcomes
in the four retained raw samples, and replayed the current normalizer against
those samples.

The tested evidence does not support a health-timestamp alignment error or
current-parser drift in the retained normalized outputs. It does show that the
prediction discrepancy is strongly application- and operation-dependent,
transition-adjacent requests are materially less successful, and mixed target
support is concentrated in the communication-fault laws. These associations do
not yet identify whether the remaining causes are operation semantics,
conditional execution, trace delivery, residual-model invariance, or a
combination of them.

The scientific position therefore remains non-terminal: the published M7
calculations establish no predictive gain and disagree with observations, but
their causes are not understood well enough to declare the overall approach
successful or failed.

## Implementation and execution

- initial diagnostic implementation:
  [`01736675bdfc809256305ab9bb6eb469da486a78`](https://github.com/a-a-k/telemetry-availability-identification/commit/01736675bdfc809256305ab9bb6eb469da486a78);
- CI-only environment-guard correction:
  [`44e4ec86b98194c893cae7e29477596903fe05a1`](https://github.com/a-a-k/telemetry-availability-identification/commit/44e4ec86b98194c893cae7e29477596903fe05a1);
- raw-sample manifest and mandatory replay correction:
  [`234401859880683bf8b0336d0260f94ff42041f0`](https://github.com/a-a-k/telemetry-availability-identification/commit/234401859880683bf8b0336d0260f94ff42041f0);
- separation of normalized-output replay from source-audit metadata:
  [`a8737e9519da2fcfafb7cedd999c4c1867653d5b`](https://github.com/a-a-k/telemetry-availability-identification/commit/a8737e9519da2fcfafb7cedd999c4c1867653d5b);
- accepted remote diagnostic:
  [run 34017401101](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34017401101),
  successful in 79 seconds at the final commit;
- final two-version CI:
  [run 34017250634](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34017250634),
  successful.

The diagnostic job used `timeout-minutes: 360`. It consumed the renewed M8A
copy of source M7 run `33990678586`; no M7 artifact, prediction, score, inclusion
rule, or result was changed. Full diagnostics ran only in GitHub Actions. Local
work was restricted to unit tests, CLI/configuration smokes, and inspection of
downloaded result tables.

Two non-accepted iterations are retained. CI run
[`34016657037`](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34016657037)
failed before any experiment because the local-only guard test did not isolate
GitHub's environment variable. Remote run
[`34016788913`](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34016788913)
was rejected despite a green workflow because it searched for the pilot rather
than the M7 campaign manifest and replayed zero files. Run
[`34016979520`](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34016979520)
successfully replayed all 36 files but initially classified two source-boundary
hash differences as parser differences; it was superseded by the accepted run
after those comparison roles were separated.

## Accepted artifact and output contract

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m8b-m7-causal-diagnostics-34017401101` | 9984348911 | 1,107,059 | `2448a7f5a42e323a4cd41e74fbb3b8c9104d70f89c5e1c5de5ecd250caf42cb6` | 2026-12-05 |

The manifest hashes every generated table and records the final commit, run,
Python environment, source run, fixed transition windows, technical gates, and
interpretation boundary. It contains 160 qualified cells, four raw samples,
1,440 bias-detail rows, 144 bias strata, 480 campaign-operation temporal rows,
8,461 transition-window rows, 1,920 topology diagnostics, 1,120 branch rows,
631 selected topology examples, 36 raw-semantic rows, and 36 replayed files.
All cell-count, raw-sample-count, replay-count, replay-error, and test-alignment
quality gates are zero.

## Prediction discrepancy decomposition

The following are descriptive, unweighted means over operation rows for which
each method emitted a prediction. They are not the M7 primary equal-stratum
contrast and do not repair its incomplete support. Positive signed error means
overprediction of the frozen stable-request success fraction.

| Method | Emitted operation rows | Mean prediction | Mean stable observation | Mean signed error | Mean Brier |
|---|---:|---:|---:|---:|---:|
| B0 endpoint persistence | 480 | 0.855952 | 0.875229 | -0.019278 | 0.097377 |
| B2 | 371 | 0.940114 | 0.898454 | +0.041660 | 0.089995 |
| Proposed | 371 | 0.946411 | 0.898454 | +0.047958 | 0.089950 |

On the same 371-row support used by B2 and proposed, B0 has mean prediction
0.875339, signed error -0.023115, and Brier 0.083917. This is descriptive rather
than a new significance test, but it gives no basis for turning M7 into an
accuracy-gain claim.

The overprediction is concentrated in OpenTelemetry Demo. On emitted rows,
DeathStarBench signed error is -0.000854 for B2 and +0.007053 for proposed,
whereas OpenTelemetry Demo is +0.097113 and +0.101311 respectively. The largest
operation-level discrepancy is checkout: +0.176403 for B2 and +0.178069 for
proposed. Browse and add-to-cart are each about +0.056 to +0.062; the three
DeathStarBench operations remain between -0.014 and +0.031.

OpenTelemetry Demo overprediction also occurs under laws without communication
faults. B2 signed errors are +0.083820 under N and +0.100401 under ND; proposed
errors are +0.086119 and +0.107302. The communication-topology abstentions
therefore cannot be the sole explanation for the prediction discrepancy.
Because clean residual estimates, injected calibration, and predictions are
observationally decomposed rather than experimentally intervened on, M8B does
not assign a unique causal stage.

## Temporal reconstruction

Every one of the 576,000 test requests aligned to saved health evidence within
the frozen tolerance. The original one-second transition guard partitions them
into 435,288 stable and 140,712 guarded requests, with zero unaligned requests.

| Profile | All requests success | Stable success | Guarded success | Stable minus all |
|---|---:|---:|---:|---:|
| Both applications | 0.847618 | 0.877757 | 0.754385 | +0.030139 |
| DeathStarBench | 0.917563 | 0.941835 | 0.842892 | +0.024273 |
| OpenTelemetry Demo | 0.777674 | 0.813852 | 0.665130 | +0.036179 |

Transition proximity is operationally important: after route degradation,
success is 0.388 within one second and 0.376 at one to five seconds, while the
corresponding timeout fractions are 0.598 and 0.598. Recovery windows show the
opposite direction, although small five-to-fifteen-second boundary cells make
some fine bins unstable.

The stable view raises, rather than lowers, observed success. Thus the frozen
guard cannot manufacture B2/proposed overprediction relative to the stable
reference; comparing to all requests would make that discrepancy larger.
Temporal transients remain real behavior that an operational model may need to
represent, but there is no saved-alignment evidence for silently changing the
M7 denominator or guard post hoc.

## Semantic and parser checks

The four retained `NCD/r0` raw samples contain 29,760 external requests. Their
HTTP 2xx count exactly equals their semantic-success count: 24,765. There are
zero HTTP-2xx semantic failures and zero immediate-versus-final semantic
disagreements. This rejects the tested response-classification explanation in
those four samples only; the other 156 campaigns did not retain raw sources and
cannot be generalized to by replay.

Current-code replay produced exact byte matches for all 32 normalized or
derived files across the four samples. The four source-audit boundary files
have two exact matches and two differences. Both differing files are
OpenTelemetry Demo, and each differs at exactly one JSON leaf:
`source_sha256.raw-telemetry.log`. No learner, evaluator, topology, deployment,
manifest, or other boundary value differs.

The original workflow qualified evidence while the OTel collector was still
running, then captured diagnostics and uploaded the later raw directory before
teardown. The two hash changes are therefore consistent with append timing in
the retained source log, not with a change in current normalized outputs. This
is a provenance-ordering limitation to fix for future acquisition. Exact replay
does not establish that all target-absent spans are genuine conditional paths;
it only rejects current-parser drift on the four retained samples.

## Topology support

For the `sampled_mixed` view, every one of the 120 operation-level N rows and
120 ND rows is classified consistently with the frozen operation contract.
Under NC, 55 of 120 rows are ambiguous; under NCD, 54 of 120 are ambiguous.
The same pattern appears in the full and trace-only views, so removing joint
health evidence does not explain it.

Every successful calibration request in the branch table has a trace. For the
two DeathStarBench operations that require the target service, aggregate target
support under communication laws is approximately 0.79--0.84; compose-post's
text-only and with-media branches are nearly identical. For the three
OpenTelemetry operations it is approximately 0.60--0.64. Saved examples show
coherent non-target service sets, but retained evidence cannot distinguish a
genuine conditional/fallback execution from source-time partial span delivery
for all campaigns.

The topology abstention is therefore not a straw-man-only artifact: it is an
empirically exposed applicability boundary of the trace-discovered model under
the actual frozen workload and telemetry path. Equally, M8B does not prove
that the target is semantically optional or that telemetry loss is the cause.
Those alternatives remain explicit inputs to the Palladio mapping and any
minimal new confirmation.

## Interpretation and next milestone

M8B narrows the diagnostic space:

- wrong test-health alignment is not supported;
- current normalization drift is not supported in four retained samples;
- HTTP-success/semantic-success disagreement is not supported in those samples;
- transition effects are large but make stable observed success higher, so they
  do not account for the direction of overprediction;
- mixed target support is specific to communication-law data, while substantial
  OpenTelemetry overprediction also exists under N and ND;
- the remaining discrepancy is localized mainly to OpenTelemetry Demo and most
  strongly to checkout, without a uniquely identified mechanism.

The next milestone must not tune M7. It bootstraps a commit-pinned Palladio
reliability analyzer, validates the PCM-to-analyzer semantics on hand-checkable
controls, and records unsupported mappings as unsupported. Only after those
checks may fixed M7 estimators and Palladio be compared on aligned inputs.

## Completion checks

- The accepted run used the final implementation commit and a 360-minute job
  timeout.
- All 160 qualified cells and four retained raw samples were diagnosed.
- All 576,000 test requests aligned; none was silently dropped as unaligned.
- All 36 expected replay comparisons ran; all 32 normalized/derived files match.
- The two source-audit differences are isolated to exact JSON leaf paths.
- Bias, temporal, semantic, topology, and branch tables are hashed and retained.
- Rejected and superseded attempts remain linked with their reasons.
- No M7 result was overwritten or promoted from exploratory to confirmatory.
- The unresolved-cause and non-terminal overall interpretation are explicit.
