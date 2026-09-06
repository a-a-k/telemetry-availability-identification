# M9D: aligned-input Palladio comparison on preserved M7 evidence

## Outcome

M9D is complete. The first accepted remote run replayed 160 learner-only M7
fits, generated 184 admitted PCM instances, solved every instance twice with
the pinned Palladio reliability analyzer, and joined held-out request outcomes
only in the downstream scoring job. All evidence, mapping, solver, repeat, and
probability-mass gates passed.

Palladio reproduced the direct B3/proposed probability to floating-point
precision. This validates the adapter and the PCM execution of the supplied
parameter realization. It is not independent parameter estimation or
independent architecture discovery, and therefore is not accuracy evidence by
itself.

The exploratory accuracy result establishes no predictive gain. On common
support, the proposed/PCM prediction had essentially the same Brier score as
the direct B3 realization, no descriptive Brier interval against B2 excluded
zero, and the current/all-sequence comparison against B0 was adverse. The
predictions also retained the positive prediction-minus-observation discrepancy
seen in M7. Transfer-change errors were somewhat smaller than B2's
descriptively, but were not subjected to a confirmatory test.

The M7 position therefore remains unchanged: its published calculations show
no established predictive gain and disagree with observations; the causes are
not yet diagnosed well enough to declare the whole approach successful or
unsuccessful.

## Frozen design and execution

The population, role boundaries, fit replay, PCM mapping, held-out boundary,
technical gates, descriptive estimands, and interpretation constraints were
committed before the first workflow result:

- implementation and frozen protocol:
  [`c9efc2aa0b0d805f66d6c60af17bd7cd39f0b243`](https://github.com/a-a-k/telemetry-availability-identification/commit/c9efc2aa0b0d805f66d6c60af17bd7cd39f0b243);
- accepted workflow:
  [run 34032057172](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34032057172), first attempt;
- matching Python 3.11/3.13 CI:
  [run 34031992219](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34031992219).

All full work ran in GitHub Actions. Local work was limited to unit and
configuration checks, static shell validation, and one generated-model XML
smoke. The local suite had 145 passing tests before the remote run. Every one
of the three experiment jobs used `timeout-minutes: 360`:

| Job | Role | Result | Wall duration |
|---|---|---|---:|
| `aligned_input_contract` | evidence audit, learner-only replay, PCM generation | passed | 1 min 51 s |
| `palladio_solver` | clean pinned build, warm-up, two measured passes | passed | 5 min 14 s |
| `acceptance_and_scoring` | byte audit, technical acceptance, held-out scoring | passed | 54 s |

The solver build emitted inherited upstream Javadoc annotations, including
unresolved references. They were non-blocking documentation warnings: the
clean build, harness, raw solver output, and downstream gates all completed.

## Compared quantities and claim boundary

M9D uses the two operations selected in M7B as routing probes, before Palladio
accuracy was observed:

| Application | Operation | Primary mask |
|---|---|---|
| DeathStarBench Social Network | `read_user_timeline` | `sampled_mixed` |
| OpenTelemetry Demo | `browse_product` | `sampled_mixed` |

The 240 opportunities comprise 160 current-placement cells and 80
colocated-to-split transfer evaluations. The methods have deliberately
different roles:

- B0 is the frozen calibration success frequency and always emits;
- B2 is the strengthened frozen moment/frequency comparator;
- `proposed-direct` is the frozen likelihood-based prediction after its
  identifiability rule;
- `PCM-PAR/B3-parameters` solves the same deterministic learner-only B3
  parameter realization in PCM;
- `PCM-PAR/admissible` exposes that solver value only where the frozen proposed
  method emits;
- `B3-direct` is retained as an implementation reference.

No topology-shaped PCM+B2 surrogate was invented. B2's route functional does
not uniquely determine the five individual PCM factors, so such a model would
have required arbitrary extra assumptions and would have been a straw-man
comparator. Conversely, PCM/PAR was not labelled an estimator: it solves a
supplied PCM and does not infer reliability parameters from this telemetry.

The workflow physically separated the stages. The first job staged the
learner and audit material, copied only the frozen prediction table needed for
post-fit matching into a separate directory, deleted evaluator/audit/M9C inputs
before fitting, and completed all fits before opening that table. The model
artifact states `contains_evaluator_data=false`. The final job downloaded the
evaluator only after the raw solver artifact existed and byte-audited 1,446
downstream scoring source files.

This is therefore an aligned-input, post-M7 exploratory debugging comparison.
It is not a full-path comparison of independently extracted architectures and
is not confirmatory evidence from new systems or campaigns.

## Evidence replay and model population

The evidence contract revalidated 1,538 preserved files, 160 qualified cells,
four retained raw samples, the accepted M8A inventory, and the accepted M9C
mapping/solver manifests. Every quality mismatch count was zero. The exact
replay runtime was CPython 3.13.15 with NumPy 2.4.4, SciPy 1.17.1, and PyYAML
6.0.2.

The accepted model population was:

| Quantity | Result |
|---|---:|
| Unique learner-only fits | 160 |
| Colocated fits reused for transfer | 80 |
| Admitted current PCM instances | 119 |
| Admitted transfer PCM instances | 65 |
| Total PCM instances | 184 |
| Four-state / eight-state instances | 153 / 31 |
| Regular / finite-nonconverged fit statuses | 183 / 1 |
| Serialized model files | 920 |
| Raw measured solver records | 368 |

The one finite, nonconverged realization was retained as frozen; it was not
removed after viewing its result. All replayed prediction rows matched the
frozen values. The generated manifest reports `git.dirty=true` because the job
creates inputs and outputs inside its checkout. This is not an uncommitted
source alteration: `GITHUB_SHA` and the recorded commit both equal `c9efc2a`,
and the repository-lock audit found zero mismatches.

## Technical bridge result

Every technical threshold was `1e-12`. Across the 368 measured solver records:

| Gate | Maximum absolute error |
|---|---:|
| Independent oracle versus frozen B3 | 2.220446049250313e-16 |
| Palladio solver versus independent oracle | 2.220446049250313e-16 |
| Palladio solver versus proposed prediction | 3.330669073875470e-16 |
| Physical-state probability mass | 2.220446049250313e-16 |
| Success plus failure | 2.220446049250313e-16 |
| Difference between measured passes | 0 |

All expected physical states were evaluated. The accepted status is
`technical_bridge_passed_accuracy_descriptive_only`.

The direct and PCM Brier contrasts are correspondingly numerical zero. For
example, `PCM-PAR/admissible - proposed-direct` was
`-2.29e-18` with interval `[-6.94e-18, 2.36e-18]` for current/all-sequence and
`1.08e-18` with interval `[-8.10e-18, 1.03e-17]` for
transfer/all-sequence. This means the two paths implement the same prediction;
it does not mean that prediction agrees with reality.

## Applicability

Coverage was evaluated against all fixed opportunities, without converting an
abstention into a numerical prediction:

| Scope | Method | Emitted / opportunities | Coverage | Missing reason |
|---|---|---:|---:|---|
| current | B0 | 160 / 160 | 100.000% | none |
| current | B2 | 119 / 160 | 74.375% | topology-ambiguous target fraction: 41 |
| current | proposed / PCM-admissible | 119 / 160 | 74.375% | same 41 |
| transfer | B0 | 80 / 80 | 100.000% | none |
| transfer | B2 | 65 / 80 | 81.250% | topology-ambiguous target fraction: 15 |
| transfer | proposed / PCM-admissible | 65 / 80 | 81.250% | same 15 |

Across both scopes, B0 emitted 240 predictions and each other scored method
emitted 184. All intended strata are represented, but the comparison rows are
correctly marked incomplete because some strata do not contain all ten planned
campaign pairs. Common-support accuracy is therefore conditional on the
admissible subset and cannot be generalized to all 240 opportunities.

## Accuracy against held-out requests

The following are equal-stratum descriptive means on each method's own emitted
support. Brier and signed/absolute errors are request-level quantities first
reduced to campaign rows; requests and the two technical solver repetitions do
not inflate the independent sample count.

| Scope/view | Method | Campaigns | Brier | Signed error | Absolute error | Interval compatibility |
|---|---|---:|---:|---:|---:|---:|
| current / all sequence | B0 | 160 | 0.127245 | +0.007474 | 0.023522 | 87.50% |
| current / all sequence | B2 | 119 | 0.131525 | +0.070116 | 0.071200 | 19.38% |
| current / all sequence | proposed / PCM | 119 | 0.132391 | +0.080216 | 0.080216 | 5.11% |
| current / stable | B0 | 160 | 0.106052 | -0.022702 | 0.037577 | 70.00% |
| current / stable | B2 | 119 | 0.105450 | +0.038780 | 0.044917 | 36.06% |
| current / stable | proposed / PCM | 119 | 0.105647 | +0.048879 | 0.050302 | 28.45% |
| transfer / all sequence | B0 | 80 | 0.127607 | +0.001056 | 0.031623 | 75.00% |
| transfer / all sequence | B2 | 65 | 0.134686 | +0.081072 | 0.081490 | 10.48% |
| transfer / all sequence | proposed / PCM | 65 | 0.134799 | +0.088661 | 0.088661 | 5.36% |
| transfer / stable | B0 | 80 | 0.106222 | -0.029828 | 0.050207 | 51.25% |
| transfer / stable | B2 | 65 | 0.108960 | +0.050748 | 0.053321 | 27.16% |
| transfer / stable | proposed / PCM | 65 | 0.108494 | +0.058338 | 0.058389 | 18.50% |

Own-support means are not themselves pairwise comparisons because B0 has wider
coverage. The frozen common-support Brier contrasts below use equal-stratum
Welch--Satterthwaite descriptive 95% intervals. Contrasts are first minus
second; negative favors the first method. No p-values, equivalence tests, or
non-inferiority claims were computed.

| Scope/view | Contrast | Paired campaigns | Brier difference | Descriptive 95% interval |
|---|---|---:|---:|---:|
| current / all sequence | proposed/PCM - B2 | 119 | +0.000866 | [-0.000204, +0.001936] |
| current / all sequence | proposed/PCM - B0 | 119 | +0.007945 | [+0.000542, +0.015348] |
| current / stable | proposed/PCM - B2 | 119 | +0.000197 | [-0.000763, +0.001158] |
| current / stable | proposed/PCM - B0 | 119 | +0.003367 | [-0.003428, +0.010162] |
| transfer / all sequence | proposed/PCM - B2 | 65 | +0.000113 | [-0.003985, +0.004211] |
| transfer / all sequence | proposed/PCM - B0 | 65 | +0.011638 | [-0.006440, +0.029717] |
| transfer / stable | proposed/PCM - B2 | 65 | -0.000466 | [-0.004372, +0.003440] |
| transfer / stable | proposed/PCM - B0 | 65 | +0.006446 | [-0.011879, +0.024772] |

Thus no comparison with B2 establishes a Brier advantage. The strongest
current/all-sequence descriptive result is instead adverse to proposed/PCM
relative to B0. Because M9D is exploratory and incomplete outside the common
support, it is reported as a discrepancy, not promoted to a new confirmatory
claim.

The 46-second stable-block sensitivity leaves Brier and errors unchanged and
only changes compatibility fractions. Proposed/PCM compatibility becomes
28.97% for current and 24.33% for transfer, so the alternative fixed block
length does not remove the disagreement.

## Placement-transfer change

For complete colocated/split pairs, M9D also records
`(predicted_split - predicted_colocated) -
(observed_split - observed_colocated)`. The table below is an additional
equal-application/law descriptive aggregation; no interval or hypothesis test
was frozen for this secondary quantity.

| View | Method | Complete pairs | Predicted change | Observed change | Signed change error | Absolute change error |
|---|---|---:|---:|---:|---:|---:|
| all sequence | B0 | 80 | 0.000000 | 0.003333 | -0.003333 | 0.035938 |
| all sequence | B2 | 65 | 0.023870 | 0.005940 | +0.017929 | 0.030323 |
| all sequence | proposed / PCM | 65 | 0.018439 | 0.005940 | +0.012499 | 0.024713 |
| stable | B0 | 80 | 0.000000 | 0.004750 | -0.004750 | 0.036916 |
| stable | B2 | 65 | 0.023870 | 0.006225 | +0.017645 | 0.027586 |
| stable | proposed / PCM | 65 | 0.018439 | 0.006225 | +0.012214 | 0.021906 |

The proposed/PCM transfer-change error is descriptively smaller than B2's on
the same 65 pairs, but both overpredict the mean placement benefit. This is a
useful localization target for later diagnosis, not evidence of an overall
accuracy advantage.

## Computation, reuse, and manual work

The run separates one-time build cost, model preparation, and warm solving:

| Measured command or endpoint | Wall time | Maximum RSS |
|---|---:|---:|
| Preserved-evidence audit | 2.05 s | 113,612 KiB |
| Fit replay, PCM preparation, serialization, audit | 1 min 23.22 s | 1,032,452 KiB |
| Clean pinned Palladio build | 2 min 55.52 s | 1,642,780 KiB |
| Warm-up plus 368 measured solver records | 1 min 42.19 s | 1,841,000 KiB |
| Downstream acceptance and scoring | 20.30 s | 1,164,144 KiB |

Within model preparation, mode preparation took 59.496 s, the 160 likelihood
fits 10.519 s, automatic parameter mapping 0.003 s, serialization 0.216 s, and
XMI audit 0.126 s. The fixed warm-up took 8.259 s and was excluded from the two
measured passes; those passes took 9.112 s and 5.375 s. These technical repeats
measure runtime only.

The same five-file template was reused for all 184 instances. Nine scalar XMI
fields were written automatically per model, no template file was manually
changed per cell, and no per-model manual intervention occurred. Transforming
all admitted colocated fits to the split placement took 0.00113 s. Historical
M7 B0/B2 runtime is explicitly `not_separately_measured`, and initial
integration work is accounted separately from repeated model updates. These
case-specific observations do not establish a universal human-effort advantage.

## Retained artifacts

| Artifact | ID | Compressed bytes | SHA-256 | Retained through |
|---|---:|---:|---|---|
| `m9d-palladio-aligned-contract-34032057172` | 9988958369 | 1,011,981 | `6c26594484dd1e9d3e101d9a0130ba218f16286b7c6b62534bd2b1fea6d48632` | 2026-12-05 |
| `m9d-palladio-solver-34032057172` | 9989040421 | 114,796 | `9e2f01e8471f83ed9752e7b1c79960775f72f29b8de064c0e1ba5dd35533ea3a` | 2026-12-05 |
| `m9d-palladio-acceptance-34032057172` | 9989055135 | 192,824 | `b535d249ac542ed69fd5e6286ffe7a84620879ed447114c7eb587f99723e6dec` | 2026-12-05 |

The contract artifact retains evidence locks, fit replay, the 240-opportunity
ledger, generated XMI, and per-file audits. The solver artifact retains the
pinned target lock, build/solve resource records, and raw results. The
acceptance artifact retains all 3,480 score rows, 96 stratum coverage rows, 36
summaries, 84 comparisons, 810 transfer-change rows, and their hashes.

The accepted run observed the five-row append-only manual-action log at SHA-256
`f40226af645267fc2e56c2f7a41f9d413cfbb68079dea03918ae16688d4145fd`.
Completion rows are appended after acceptance rather than rewriting that
historical snapshot.

## Interpretation and next step

M9D rules out a solver-translation explanation at the precision tested: when
given the same B3 parameter realization and the checked M9C structure, Palladio
and the direct computation agree. It does not rule out errors in the shared
model boundary, the supplied parameter semantics, finite-data estimation, or
the unresolved trace/topology evidence. Exact solver parity cannot adjudicate
those shared assumptions.

The aligned comparison is not a straw-man contest. Palladio is evaluated in
the role its analyzer actually supports; B2 remains the strongest direct
frozen comparator; unsupported replication and double message-transfer
semantics were resolved in M9B/M9C before accuracy was viewed; and abstentions
remain visible. Its limitation is different: it deliberately does not compare
independent end-to-end architecture acquisition.

The next admissible work is to freeze the full-path/new-confirmation decision
from the Palladio continuation plan. Before any new live collection, it must
state each approach's information boundary, identify which architecture and
reliability inputs can actually be produced independently, use M9D only for
planning rather than confirmation, and justify the required independent
campaign count from the precision of the intended paired contrast. If a
suitable PCM extraction route cannot recover reliability semantics for these
applications, the resulting partially manual baseline must be named and its
manual inputs measured rather than concealed.

## Completion checks

- The implementation and interpretation contract preceded the first result.
- The first full workflow attempt passed all three 360-minute jobs.
- All 1,538 evidence files and 1,446 downstream scoring files passed byte audits.
- The learner/evaluator boundary held and every frozen replay row matched.
- All 184 models solved twice and passed oracle, mass, and repeat gates.
- Coverage and missing reasons are reported before common-support accuracy.
- Solver equality is interpreted only as technical bridge validation.
- No Brier advantage over B2 is claimed; the adverse and unresolved results are retained.
- Runtime, memory, reuse, and manual-work boundaries are reported without invented B0/B2 timings.
- The published M7 interpretation is unchanged.
