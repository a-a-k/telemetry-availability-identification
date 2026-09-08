# Working claim ledger for the SIMPAT continuation

Status: updated 8 September 2026 after completed M9P confirmation and the M9Q/M9R
censuses. This is not an article verdict or a substitute for the missing
independent PMX comparison. The original SIMPAT design remains a research plan;
its proposed contributions are not automatically established results.

## Separate questions before stating a contribution

1. Does the observation law determine the requested quantity, even if it does
   not determine every primitive parameter?
2. Does an implemented reduction preserve that observation law and likelihood?
3. Do uncertainty procedures include both sampling error and structural
   ambiguity under their stated sampling assumptions?
4. Does the resulting execution model predict independently observed semantic
   request success for the operation, timing regime and deployment of interest?
5. What independent architectural-model extraction and parameterization can
   produce comparable forecasts from the declared information boundary?

An affirmative answer to an earlier question does not establish a later one.
In particular, a correct solver and identified parameters for a static route
model do not establish the adequacy of that route model for checkout requests.
Conversely, the independent confirmation of M9P's explicitly specified temporal
response curve does not validate the original static route law or establish
that the identification compiler automatically discovered that curve.

## Evidence and permitted scope

| Evidence | Statement supported by the current record | Boundary that must accompany it |
|---|---|---|
| [M0](milestones/M0_RANK_AND_MOMENTS.md) | Row-space tests distinguish supported log-parameters and conjunctive targets in the implemented independent primitive-factor model. | Restricted conjunction family and specified observation policies; finite-sample support is separate from structural support. |
| [M1](milestones/M1_EXACT_LIKELIHOOD_REFERENCE.md) | Exact observed likelihood is a matched reference on the small enumerated models; likelihood ridges do not justify reporting unsupported individual parameters. | Standard likelihood/optimization is a comparator and statistical component, not an independent new contribution. |
| [M2](milestones/M2_STRUCTURE_PRESERVING_REDUCTION.md) | The implemented membership-signature product reduction preserves the tested observation laws and matched likelihood objectives; explicit ambiguity witnesses are retained. | Identical signatures are a sufficient reduction rule, not a complete reduction for arbitrary Boolean observation maps. No reduction occurs in the full/staggered negative controls. |
| [M3](milestones/M3_NON_DIRECT_PLACEMENT_TRANSFER.md) | Non-direct targets and placement decisions can remain ambiguous under restricted telemetry, despite an estimable current endpoint; a strengthened B2 matters for a fair comparison. | Synthetic, correctly specified two-domain design. This B2 and the later M7 B2 use different observable contracts. |
| [M4](milestones/M4_SIMULTANEOUS_UNCERTAINTY.md) | Simultaneous observable constraints and conservative parameter-set propagation retain target ambiguity and achieved the reported coverage in the frozen experiment. | Iid, correctly specified generator. Clopper–Pearson intervals and the union bound are standard components; numerical enclosure error is retained conservatively. |
| [M5](milestones/M5_DIRECTED_STRESS_TESTS.md) | Directed violations expose failure modes of both identification assumptions and uncertainty calibration. | Diagnostics can miss violations; a remaining unflagged prediction is not thereby safe. No universal robustness claim. |
| [M7](milestones/M7_FROZEN_LIVE_VALIDATION.md), [M8A](milestones/M8A_M7_EVIDENCE_AND_ARITHMETIC_AUDIT.md) | The preserved live comparison has 160 technical campaign successes, 117 primary pairs and no established superiority over the matched B2; independent arithmetic checks reproduce the scores. | Conditional prediction coverage and semantic adequacy remain essential; arithmetic agreement does not resolve model bias. |
| [M9A–D](milestones/M9D_PALLADIO_ALIGNED_COMPARISON.md) | The pinned Palladio reliability route reproduces hand-checkable controls and aligned fixed-input calculations. | This establishes semantic/solver correspondence under the mapping, not independent architecture extraction, independently identified parameters or predictive gain. |
| [M9E correction](M9E_PMX_PERFORMABILITY_CORRECTION.md), [M9H](milestones/M9H_PMX_SOURCE_ENTRYPOINT.md), [M9J](milestones/M9J_PMX_CARRIER_CONTROL.md) | A specific Retriever result has limited scope; the PMX performability command and a nonzero operation-error mechanism were subsequently recovered. | Application/integration cost does not reduce PMX's scientific relevance. The M9J prospective stdout-slot oracle failed and remains in the record. |
| [M9K–M](milestones/M9M_CHECKOUT_ROUTING_MODEL.md) | Checkout's static-route discrepancy was localized using source, learner telemetry and preserved outcomes; static AND and OR bracket most examined cells. | Reused M7 evidence supports mechanism development. A path-failure association is not an observed backend assignment for every individual call. |
| [M9N](milestones/M9N_CHECKOUT_TEMPORAL_FAILOVER.md) | The temporal mechanism diagnostic improved conditional fit and closed the signed marginal gap on reused data, while state-only and temporal marginal forecasts were nearly identical. | Reused test evidence; no independently confirmed incremental marginal value from age. Conditional held-out health is diagnostic input, not part of a marginal learner-only forecast. |
| [M9O design](milestones/M9O_TEMPORAL_CONFIRMATION_DESIGN.md), [completed M9P](milestones/M9P_INDEPENDENT_TEMPORAL_CONFIRMATION.md) | All 120 independent campaigns and all five gates pass. Conditional temporal information replicates; marginal temporal/state Brier difference is practically equivalent within ±0.002; mean temporal signed error −0.014865 is adequate within ±0.03. | Conditional scoring uses test health. The signed-error interval excludes zero despite passing the mean-bias tolerance. Matched endpoint descriptive scores are retained; neither automatic discovery nor superiority over that endpoint or PMX is established. |
| [M9Q conformance](milestones/M9Q_PMX_OBSERVED_OPERATION_CONFORMANCE.md), [application census](milestones/M9Q_PMX_APPLICATION_CENSUS.md) | After the explicit artificial-oracle repair, the four historical samples yielded two no-SERVER-input cases and two fully retained observed-server inventories with matching operation/error and structural checks, but mismatched usage entries. | Original failures remain; timestamp-based workload entry selection differs from parent-root semantics. No full external-request mapping, calibrated performance model or availability forecast is established. |
| [M9R composition control](milestones/M9R_PMX_INCLUSIVE_ERROR_COMPOSITION.md) | Retained native PMX models fail on uncontained failure types; explicit containment removes that boundary but subsequent loop-PMF errors yield zero evaluated physical mass, including the zero-error control. | Sixteen attempts retained, no valid probability. The inclusive/local error distinction remains analytic, not an observed 0.72-versus-0.8 solver result or evidence against the PMX ecosystem. |
| [M9S PMF bridge](milestones/M9S_PMX_PMF_BRIDGE.md) | Equivalent integer-loop encoding plus the disclosed failure-type containment bridge yields all 16 positive software-oracle passes, including inclusive 0.72 versus conditional-local 0.8; eight unchanged negative records reproduce. | This resolves the demonstrated artificial-model solver boundary. It does not establish local-failure independence or an independently parameterized live availability comparison. |
| [M9T request census](milestones/M9T_PMX_REQUEST_CORRESPONDENCE.md) | All four historical learner samples retain their native request traces; compound OTel requests explain multiple HTTP roots and DeathStar failures may lack span-error flags. | Descriptive development census; external semantic outcomes and inferred operation boundaries must be explicitly charged in the next adapter. |

## Mathematical material and its scope

[B2 observable-target notes](B2_OBSERVABLE_TARGET_NOTES.md) separate an observable
route functional from unique identification of all hidden factors, state the
needed independence assumptions, handle zero support separately, and give an
indistinguishable-observation counterexample when those assumptions are relaxed.
The inclusion–exclusion extension is a mathematical observation, not an
implemented scalable estimator for arbitrary graphs or a novelty claim for the
union formula.

[Sharp two-path bounds](B2_SHARP_OBSERVABLE_BOUNDS.md) now give the exact attainable
target intervals under containment alone and under communication-vector/health
independence. They distinguish assumption-driven point identification from
precision supported by the weaker observation contract; the six LP checks use
artificial inputs only. The atom-LP method is established prior work.

[Conjunctive-observation target theorems](CONJUNCTIVE_OBSERVATION_TARGET_THEOREMS.md)
prove equality of masked observation laws from complete supported moments,
give a global criterion for polynomial/Boolean targets under that monomial
observation law, and prove the duplicate-membership product reduction. An
isolated exact rational reference has seven bounded unit tests. This does not
solve arbitrary Boolean observation models, establish computational scalability,
or replace the historical M0/M2/M3 evidence with new empirical results.

[The calibration identity](M9P_CALIBRATION_IDENTITY.md) explains why an age curve
can improve conditional prediction while its calibration-weighted marginal
forecast remains close to a state-only or endpoint estimate. The exact identity
requires its stated intercept, interior-solution, response-factor and target-
weight conditions. It is not a bound for every fit with a response factor near
one, and it does not substitute for the independently measured M9P intervals.
The [target-exposure note](TARGET_EXPOSURE_AND_MEAN_FORECASTS.md) states when
equal calibration means can separate under different target weights, including
sharp two-context ambiguity and a matched reweighted endpoint. Its artificial
example is not a live transport experiment or an extension of M9P's estimand.

For an eventual theorem statement, keep algebraic identification, estimator
consistency, finite-sample coverage and model adequacy separate. The current
source and experiments do not establish all four for an unrestricted live
microservice system. The [focused primary-source comparison](RELATED_WORK_SCOPE.md)
now attributes the network-tomography, algebraic, probability-bound and model-
calibration antecedents. It is not an exhaustive novelty result.

The [methods draft](ARTICLE_METHODS_DRAFT.md) now assembles these definitions,
restricted results, implementation boundaries and validation requirements into
connected article text and links the completed M9P report. The independent PMX
accuracy comparison remains open; the initial design is not thereby fully realized.

## Information and cost accounting

Matched prediction accuracy requires a common operation, semantic outcome,
timeout rule, target population and learner/evaluator boundary. Keep the
parameterization source visible: supplied parameters, trace-derived operation
errors, external outcomes, lifecycle health and deployment declarations are
different information inputs. Extra information supplied to PMX or to the
proposed method must be charged symmetrically.

Keep shared acquisition/qualification, method-specific inputs, extraction,
estimation and solving costs distinct. A method's zero native-trace input bytes
does not imply that the experiment collected no traces. A shared parse timer
does not establish an isolated endpoint implementation's runtime. Agent work
and engineering effort are not measured by a log column for human active
minutes. Monitoring-overhead claims require their own instrumented/uninstrumented
comparison; runner times and artifact sizes do not establish that effect.

## Items to resolve before completing the article argument

- Carry the completed M9P result into the article with all three decisions,
  the small remaining mean bias, the matched endpoint and its limited target scope.
- Use the completed M9Q census and retained failures to define the next semantic
  mapping; no extra launcher or extractor repair is needed to report this stage.
- Specify the remaining independent PMX availability comparison only after
  observed-operation errors, propagated failures, missing requests, replication
  and external semantic outcomes have a defensible correspondence.
- Keep the proved restricted propositions and exact reference distinct from
  novelty and scalability claims; retain the primary-source attributions.
- Form the final article claims from that evidence, retaining unfavorable
  comparators and coverage limitations.
