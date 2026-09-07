# M9M: checkout request-level routing-model test

## Outcome

M9M is complete. Accepted run 34089829138 passed all three jobs and selected
the frozen machine branch `checkout_trace_requirement_model_overshoots`.
M9M confirms that checkout's M7 Boolean-OR abstraction is too optimistic, but
the primary request-footprint model overcorrects and is also incompatible with
the retained observations. No tested routing law closes the signed gap under
the frozen rule.

The equal-campaign means across the 40 fixed N/ND cells are:

| Frozen method | Mean prediction | Mean signed error | Bootstrap 95% interval | Mean absolute error | Mean Brier |
|---|---:|---:|---:|---:|---:|
| M7 single-demand OR | 0.947019 | +0.173061 | [+0.164769, +0.180987] | 0.173061 | 0.204104 |
| strict round-robin AND | 0.705532 | -0.068427 | [-0.078708, -0.058269] | 0.069149 | 0.178383 |
| three independent calls | 0.705947 | -0.068012 | [-0.078166, -0.058145] | 0.068279 | 0.178190 |
| two client affinities | 0.735340 | -0.038619 | [-0.048365, -0.029161] | 0.042417 | 0.174978 |
| learner trace-requirement mixture (primary) | 0.705532 | -0.068427 | [-0.078708, -0.058269] | 0.069149 | 0.178383 |
| frozen M7 B2 marginal reference | 0.942419 | +0.168461 | [+0.158742, +0.178090] | 0.168461 | 0.202757 |

The retained mean test rate implied by every row is 0.773959. Strict AND and
OR bracket that observation in 39 of 40 cells. The exception is colocated/ND
repetition 7, where the observed 0.734164 is below the AND prediction 0.748616;
the corresponding OR prediction is 0.913235.

The primary model improved paired Brier versus OR by -0.025722, with 95%
interval [-0.029698, -0.021635], and paired absolute error by -0.103911, with
interval [-0.120590, -0.086572]. Those improvements are not sufficient for the
registered support rule: the primary signed-error interval excludes zero and
lies wholly below the -0.03 closure margin. The two-client sensitivity has the
smallest descriptive Brier, but it also underpredicts, its interval excludes
zero, and the protocol forbids promoting a sensitivity by its test score.

## What was implemented

The experiment retained the source-grounded three-call checkout contract and
evaluated six predictions in every cell:

- the unchanged M7 OR and B2 predictions;
- strict two-replica requirement;
- three independent call assignments;
- two persistent client-pool assignments; and
- the primary mixture weighted by clean-baseline request trace footprints.

All non-checkout calibration likelihood terms retained M7 OR. The four
structural alternatives were refitted separately from calibration health and
outcomes. The primary weights used only deterministically sampled clean
baseline trace footprints and never inspected their semantic outcomes.

The workflow enforced a physical learner/evaluator boundary. Candidate fitting
received six learner/boundary files per cell and an 80-row predictor-only
reference sanitized from the SHA-256-locked M7 `predictions.csv`. The reference
contains no test outcome, empirical error, or score. The combined preservation
archive was deleted before fitting, all 240 candidate predictions were uploaded,
and only then did the evaluator job download test requests and ordinary test
health.

## Execution and retained failures

- initial preregistration commit:
  [`4493851`](https://github.com/a-a-k/telemetry-availability-identification/commit/4493851);
- final technical-amendment commit:
  [`718bf3b`](https://github.com/a-a-k/telemetry-availability-identification/commit/718bf3b1145be2c918980603039e6c784bf76d96);
- accepted execution:
  [run 34089829138](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34089829138),
  started `2026-09-07T06:12:51Z` and completed `2026-09-07T06:15:30Z`.

Three earlier technical failures remain public and are not counted as
scientific outcomes:

| Run | Last reached boundary | Reason | Outcome exposure before correction |
|---:|---|---|---|
| 34087983967 | source contract | mistyped digest for the retained 711-byte M9L decision matrix | no fit; no evaluator |
| 34088196716 | learner-only fit | generalized likelihood omitted M7's per-route-class probability floor | no evaluator |
| 34088472223 | evaluator's first integrity check | fresh OR optimizer solution differed from the frozen predictor by at most 7.724e-9, above the 1e-10 exact carry-forward threshold | evaluator files downloaded; no held-out score constructed |

The first correction changed only an evidence lock. The second restored the
already specified M7 numerical convention and added a contradictory-signal
regression. The third retained both registered tolerances: frozen OR/B2 values
are now carried through the predictor-only reference, while the fresh OR audit
must remain within the existing 1e-4 equivalent-fit tolerance. No correction
changed a model, candidate order, probability, metric, threshold, branch, or
test outcome.

The accepted workflow used exactly three jobs with `timeout-minutes: 360`:

1. source/evidence contract: 23 seconds;
2. learner staging, fitting, and immutable candidate upload: 87 seconds;
3. retained evaluator audit, 10,000-resample bootstrap, and decision: 40
   seconds.

Measured analysis-process resource use was 1.01 seconds and 108,284 KiB maximum
RSS for the contract, 56.92 seconds and 144,208 KiB for fitting, and 18.32
seconds and 135,972 KiB for evaluation. Local verification before the accepted
run comprised Python compilation, config validation, workflow parsing, and all
205 unit tests. Full fitting and scoring ran only in GitHub Actions. M9M invoked
PMX zero times and made no new live collection.

## Accepted artifacts

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m9m-checkout-routing-contract-34089829138` | 10006434761 | 4,256 | `be8dd8390d5ebd527bb944856c8912888e4ac37cfa566a3f7a2a0a77c8ebbb78` | 2026-12-06 06:12 UTC |
| `m9m-checkout-routing-candidates-34089829138` | 10006468922 | 37,059 | `8607a709c45e203179107e9cc4d90a90f2cb8793150c292dcc5315581ad25f4a` | 2026-12-06 06:12 UTC |
| `m9m-checkout-routing-evaluation-34089829138` | 10006485419 | 29,548 | `14564b687003a22d951c40e6c891c51a5528527f80c91db19b20b7185b198cc3` | 2026-12-06 06:12 UTC |

GitHub reports all three artifacts unexpired. Principal uncompressed identities
are:

| File | Bytes | SHA-256 |
|---|---:|---|
| `contract-manifest.json` | 7,667 | `42926e9250ee4bbfcd1ff0daa4e9634bd313d1e20ce81ad068fffac89fb4e64b` |
| `candidate-manifest.json` | 2,459 | `c6d1b34f77a4c9c8071e0727b6f98768b2512f4e5b7aa6e154f8d94ea8e9a7a6` |
| `candidate-predictions.csv` | 48,996 | `b9031c4707cf4e2b6f04aad941957b5680edce35c31f62798b17388115a3cbdb` |
| `fit-audit.csv` | 46,466 | `32cc3f7b3bb1ef3bdaadd733d30dc2583185f4104cd0d02b092e8e925ca9b99c` |
| `footprint-audit.csv` | 3,196 | `9d647f9127fb8b86a0ce6d006e29ec4ae770b063eb601d8b8cf8e4588aab963c` |
| `frozen-m7-predictor-reference.csv` | 11,548 | `16170ef96c537e5500698a027a56183be36ab6e77ba8e387946508bf44ac1276` |
| `evaluation-manifest.json` | 8,751 | `8b0eb6125fd936441d1c21b467f18193bf3d71698207cc3b80e9dac43e30cff2` |
| `heldout-scores.csv` | 39,994 | `ef54a8abb3db1d1b1e6998977d773ea585b380f556c24c6f25ad5735e1e148fa` |
| `bootstrap-summary.csv` | 3,625 | `3d284dbc5fc91c9f8374d0e0dacbf0962739e51779f9cebae265a26516a137da` |
| `decision-matrix.csv` | 1,166 | `f01e998d3db0916ddec3eee2e13291354a4b181d2cc0e17f27e48520cb96fe71` |
| `selected-file-audit.csv` | 56,541 | `daa78b1ee9d0b55731984c5a9f1f9bdf73d83bd398e22496515783c79b283a43` |

## Integrity and information cost

The accepted manifests report:

| Check | Result |
|---|---:|
| qualified-manifest census | 160 |
| selected N/ND cells | 40 |
| selected retained files audited | 360 |
| frozen M7 prediction mismatches | 0 |
| candidate rows frozen before evaluator | 240 |
| fit rows | 200 |
| minimum stable test requests per cell | 908 |
| minimum retained baseline footprints per cell | 50 |
| minimum footprint resolution | 1.000 |
| minimum both-replica footprint fraction | 1.000 |
| maximum equivalent-fit prediction range | 2.210e-7 |
| maximum fresh-OR versus frozen difference | 7.724e-9 |

Every baseline footprint in every cell represented both replicas, so the
primary weights were exactly `w_a=0`, `w_b=0`, and `w_ab=1`. The primary model
therefore coincided with strict AND. This is a real diagnostic result, not a
failed gate: successful clean-baseline logical requests contain three target
calls behind a two-backend round-robin group.

It is also why the extra trace structure cannot simply be declared a deployable
win. The footprint graph is richer input than M7's Boolean topology edge and
has acquisition and processing cost. Moreover, conditioning the footprint on a
successful clean request describes call coverage when both replicas are
available; it does not reveal how HAProxy reroutes calls after a backend-state
change.

## Interpretation

M9M rejects both extreme static interpretations for checkout. One
instantaneous OR is much too optimistic. Treating the three-call request as a
persistent requirement that both replicas remain usable is too pessimistic.
The source-grounded intermediate laws move between those extremes, but none
matches the observations under the registered closure rule.

The pattern is consistent with time-dependent failover. HAProxy's health-aware
round-robin can temporarily expose a call to a recently unusable backend and
then remove that backend, allowing later requests to use the survivor. A static
OR credits immediate failover for all one-path-up time; static AND credits none.
The retained result says the effective behavior is between them. It does not
yet identify detection lag, connection reuse, assignment, retry, or another
temporal mechanism, because no per-call backend decision was retained.

M9M therefore does not establish a replacement predictive model. Its lower
Brier values show that request-level structure matters for this reused checkout
test, but the primary model's systematic underprediction prevents a support
claim, and test-based promotion of the closest sensitivity is forbidden. The
single operation and reused evaluator cannot establish overall accuracy.

The preliminary article position is unchanged: the direction remains
substantive and the calculation of the specified model remains supported, but
neither superior predictive accuracy nor lower end-to-end automatic cost than
PMX has been demonstrated. PMX's scientific priority and the scoped Palladio
conclusions are unaffected. M9M neither proves the article successful nor
proves the approach failed.

## Next milestone

The frozen branch requires `m9n_checkout_temporal_failover_model`. M9N must
separate persistent physical path state from time since a one-path-up episode
began, using calibration-only request/health timing and the pinned 500 ms
HAProxy check contract. Candidate parameters and any health-age bins must be
frozen before evaluator access, with the candidate matrix uploaded first.

M9N must retain static OR, static AND, M9M primary, and B2 as fixed references;
must not select a temporal curve from its test score; and must treat
one-second health sampling as interval-censored rather than a per-call routing
log. If retained learner timing cannot identify a useful temporal prediction,
the correct branch is minimal assignment instrumentation under a separately
preregistered collection, not silent use of test outcomes.

## Completion checks

- All three accepted jobs completed with six-hour timeouts.
- The candidate artifact preceded evaluator access.
- Source, artifact, file, row, fit, trace, and frozen-prediction gates passed.
- The 10,000-resample stratified bootstrap and all frozen branches ran.
- The closest sensitivity was not promoted.
- All three superseded failures and their information boundaries remain logged.
- No local full experiment, PMX invocation, new collection, revised M7 result,
  or article-level verdict was made.
