# Telemetry-driven availability identification

This repository is the experimental implementation for the planned SIMPAT study
Telemetry-Driven Identification of Stochastic Availability Models for
Microservice Systems.

It is a new research line built on the earlier stochastic-connectivity model. It
is not a one-to-one implementation of MODELS reviewer requests. The venue-level
claim here is about constructing, identifying, validating, and using a simulation
input model from heterogeneous telemetry.

## Current vertical slice

The first executable slice covers the conjunctive primitive-factor submodel used
by the planned T1 identifiability result. Independent Bernoulli primitives denote
known failure-domain state, residual instance health, and residual communication
health. Each observable is a conjunction of primitives. For observable moments,
the implementation builds

~~~text
log(m) = H log(p)
~~~

and reports:

- structural and finite-sample rank;
- individual parameter identifiability;
- conjunctive target identifiability;
- singular values and condition number;
- estimates only for identified parameters or identified target functionals;
- false-confident estimates as an explicit failure metric.

The estimator in this slice is a weighted log-moment estimator. It is a
transparent baseline and executable check of the rank argument, not yet the
article's proposed observed-likelihood or EM implementation.

Milestone M1 adds a matched exact observed-likelihood reference for the same
small models and masked episode records. It enumerates latent states independently
of the simulator's sampling path and uses a bounded, analytic-gradient,
multistart optimizer. This is the article-design B3 correctness reference; the
log-moment implementation is labeled B2 and is not presented as the proposed
full method.

Milestone M2 adds the first identification-aware compilation rule. Primitive
factors that have identical nonzero signatures across every supported observable
are replaced by one explicitly named product factor; structurally inactive
factors are removed. The compiler attaches identifiability certificates or
counterexample witnesses and tests the reduced likelihood against the unreduced
B3 objective on every campaign.

Milestone M3 extends the executable model to OR-of-conjunction Boolean
observables and evaluates two outcomes that are absent from calibration: moving
a replica across known domains and adding a same-type replica in its current
domain. It uses B0--B4, a strengthened analytic moment baseline, the matched B3
likelihood, explicit ambiguity witnesses, change error, choice accuracy, regret,
and identification-aware abstention.

Milestone M4 constructs simultaneous exact-binomial constraints on the
observable probabilities and propagates them through a conservative numerical
outer enclosure of the two-domain parameter set. Coverage is reported together
with width and decision abstention, against likelihood-Wald, direct endpoint,
and fixed-input simulation-only alternatives.

The completed M4 experiment found 0.955--1.000 simultaneous target coverage
across its 45 scenario/mode/size cells, monotone width contraction with sample
size, and no incorrect identification-aware placement decision. Full results,
including conservative width and node-budget limitations, are recorded in
`docs/milestones/M4_SIMULTANEOUS_UNCERTAINTY.md`.

Milestone M5 implements five separate assumption-boundary generators with
paired neutral controls: domain-coupled exporter loss at fixed marginal
retention, persistent Markov episodes at fixed stationary marginals, a hidden
merged failure domain, rare/unseen conditional branches, and readiness delay.
The unchanged M4 procedure and matched B3 are retained, diagnostics gate a
separate guarded output, and mechanism-aware references are explicitly labelled
as such.

The completed M5 run found the intended non-universal boundary behavior.
Informative exporter loss made the assumed B3 placement choice wrong in every
n=2,000 campaign; a hidden merged domain made both raw proposed and B3 choices
wrong in every campaign. The corresponding selection-aware and corrected-map
references chose correctly, while the predeclared guards abstained after their
diagnostics fired. Persistent episodes reduced raw split/choice interval coverage
to 0.860/0.760; a fixed moving-block reference improved this to 0.945/0.900 but
did not universally restore 95%. Rare/unseen branch and readiness results expose
support and semantic incompatibility rather than filling missing evidence. Full
results and limitations are recorded in
`docs/milestones/M5_DIRECTED_STRESS_TESTS.md`.

Completed milestone M6 adds the versioned `taid.live_bundle/v1` ingestion boundary. It
normalizes Jaeger and OTLP JSON alongside an independent external-request census,
deployment/domain metadata, distinct liveness/readiness records, mesh attempts,
verified injection intervals, and manual operation semantics. Its integration
workflow checks exact upstream revisions of DeathStarBench and OpenTelemetry Demo
and exercises deliberately tiny contract fixtures. These fixtures are not live
measurements and provide no effectiveness result.

The configured RQ1 matrix has four small factor-graph families, three observation
modes, three nested sample sizes, and 200 independently generated campaigns. It
therefore produces 7,200 family/mode/size rows. Prefixes of sizes 100, 500, and
2,000 within one campaign are nested and are not counted as independent
replications.

## Execution policy

Full and diagnostic experiment matrices run only in GitHub Actions. The heavy
workflow is manual and uploads immutable result artifacts. Local execution is
limited in code to at most 50 dataset fits, enough for unit tests and a basic
smoke run.

Local smoke on Windows:

~~~powershell
./scripts/smoke.ps1
~~~

Equivalent commands without installing the package:

~~~powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m telemetry_availability validate-config --config configs/rq1_synthetic.yaml
python -m telemetry_availability run --config configs/rq1_synthetic.yaml --out .smoke --family same_domain_replicas --mode full --mode no_joint_health --repetitions 3 --sample-sizes 100
~~~

Do not use a smoke output as a paper result. The full workflow records the Git
revision, configuration digest, dependency versions, seeds, and GitHub run
identifiers in its manifest.

## Workflows

- CI runs unit tests, validates the experiment contract, and executes only the
  bounded smoke case.
- RQ1 Synthetic Identification is started manually. The diagnostic tier runs 20
  campaigns at sizes 100 and 500; the full tier uses the frozen values from the
  experiment configuration. Each family is an independent workflow shard, and a
  final job aggregates the raw tables.
- M1 Exact Likelihood Reference is started manually and compares B2 and B3 on
  paired campaign prefixes. Its aggregate includes the compressed observation
  patterns needed to reconstruct the exact conditional likelihood.
- M2 Structure-Preserving Reduction is started manually and requires objective
  equivalence between the original and reduced likelihood before publishing its
  aggregate artifact.
- M3 Non-Direct Placement Transfer is started manually, shards by common-cause
  scenario, and requires matched B3 predictions, valid ambiguity witnesses, and
  zero unsupported proposed decisions before publishing its aggregate artifact.
- M4 Simultaneous Uncertainty is started manually, shards by scenario, and
  requires valid outer enclosures without treating random empirical coverage as
  a CI build gate.
- M5 Directed Stress Tests is predeclared in `docs/M5_STRESS_PROTOCOL.md`. It
  uses paired controls for five named assumption violations and treats
  diagnostics and guarded abstention separately from mechanism-aware oracle
  references.
- M6 Live Ingestion Harness checks two exact public benchmark revisions,
  operation-specific workload evidence, both trace adapters, deterministic
  normalization, and preservation of external failures without exported traces.
  It is an integration milestone, not a live-system experiment.
- M7P Runtime Feasibility Pilot is a remote-only deployment and telemetry-path
  check. All container images are digest-locked, and pilot outcomes may change
  infrastructure implementation but cannot enter the main M7 analysis.
- M7A Fault and Trace-Linkage Diagnostic applies verified container, network,
  and grouped logical-domain interventions across the four planned law labels.
  It tests deterministic external-census/native-trace linkage and period cleanup;
  its short, forced-sampling records are excluded from effectiveness analysis.
  This milestone is complete.
- M7B Replicated Placement and Semantics Pilot replaces one pinned key service
  with two real containers behind a pinned, auditable proxy. It verifies that
  both backends serve traffic, freezes content-aware success predicates, and
  exercises co-located versus split logical-domain targets without treating the
  pilot as effectiveness evidence.
- M7C Stochastic Schedule and Budget Freeze Pilot runs independent alternating
  renewal processes for individual, communication, and domain factors. Its
  predeclared rule selects only the M7 duration, campaign-pair count, and
  transition guard; no method outcome can affect that selection.
- M7C-R records the original no-candidate stopping condition and the
  protocol-permitted narrowing from per-cell precision to the equal-weight
  16-stratum macro contrast. It retains the 0.015 threshold and selects 10
  independent campaigns per stratum.
- M7D Learner Evidence Boundary Qualification streams both native trace formats,
  normalizes calibration-only trace graphs and health evidence, physically
  sequesters test outcomes, and rejects controller/event fields in learner
  schemas. It is a diagnostic adapter check, not an effectiveness experiment.
- M7E freezes the complete main acquisition and analysis implementation before
  any M7 request. The primary comparator is strengthened B2, B3 is the matched
  same-model likelihood reference, and proposed/B3 equality is a correctness
  gate rather than a claimed advantage. A separate M7F role performs a no-fit
  four-cell preflight under a distinct seed and namespace.
- M7F is complete. Its accepted four-cell run passed every acquisition,
  native-trace, provenance, learner/evaluator-separation, and aggregate quality
  gate without fitting or scoring a model. The first run was correctly rejected
  because a parsed scope argument was not forwarded; it is retained and no row
  from it is reused. All three M7 workflow jobs now have a 360-minute safety
  timeout.
- M7 is complete as an executed live study. All 160 campaigns and the frozen
  analysis succeeded, but the primary proposed-minus-B2 contrast is incomplete
  at 117/160 campaigns because trace topology was ambiguous under communication
  faults. Its conditional Brier estimate is `+0.000233` (95% CI
  `[-0.001659, +0.002124]`, `p=0.685`), where positive is unfavorable to
  proposed. The published calculation does not establish a predictive advantage
  and exposes abstention and prediction--observation discrepancies. Their causes
  are not yet resolved well enough to call the overall approach successful or
  unsuccessful; M8 begins that separately labelled diagnosis.
- M8A preserved all 165 M7 artifacts for 90 days and independently reconstructed
  all 36,459 request-derived score rows, 117 summaries, and the primary
  equal-stratum contrast with zero mismatches. This rejects the tested
  identity, denominator, Brier-formula, and aggregation explanations.
- M8B aligned all 576,000 test requests, exactly replayed all 32 normalized or
  derived outputs from the four retained raw samples, and localized
  overprediction mainly to OpenTelemetry Demo and checkout. Mixed target support
  remains concentrated under communication faults, but no unique causal
  mechanism is established. The next step is a pinned Palladio reliability
  analyzer with hand-checkable semantic controls, not a post-hoc change to M7.
- M9A pinned the official Palladio Bench 5.2.2 archive, rebuilt the corresponding
  analyzer commit under an audited release-date dependency lock, and ran the
  official `ReliabilityTest` twice. Both solver calls returned `0.375`, conserved
  probability mass exactly, and matched an independently parsed recovery-tree
  oracle. This validates the integration boundary only.
- M9B generated seven independently audited PCM control groups and ran 15
  frozen semantic cases twice. Every solver value matched its external oracle,
  with zero repeat and probability-mass residuals. The source and model audits
  also expose two non-negotiable mapping limits: automatic allocation
  replication is unsupported, and one raw link probability is applied to both
  request and response transfer. M9C then audited the accepted M8B topology
  evidence and exact application sources, emitted the mandatory 16-row
  correspondence table, and instantiated each selected operation for colocated
  and split logical domains. All eight solver records matched the predeclared
  structural witness; this is not an accuracy result. M9D then completed the
  exploratory aligned-input comparison on preserved M7 material. It replayed
  160 learner-only fits, generated 184 admitted PCM models, and solved each
  twice. Palladio matched the direct B3/proposed probability within `3.34e-16`,
  validating the technical bridge only. Current admissible coverage was
  119/160 and transfer coverage 65/80; no common-support Brier comparison with
  B2 established predictive gain, while the positive prediction--observation
  discrepancy remained. Held-out outcomes entered only after the raw solver
  artifact existed. M7's published no-established-gain result and unresolved
  overall interpretation therefore remain unchanged. M9E completed a
  full-path feasibility gate for a byte-pinned, PCM-5.2-compatible Retriever
  release on both complete source trees. Retriever exited zero and emitted four
  PCM files per application, but they were empty shells; each application
  passed 5/15 frozen readiness gates. No model was scored. This establishes the
  cost of the tested Retriever branch, not a limitation of all Retriever
  versions or the Palladio ecosystem. A post-result correction restores the
  later headless OpenTelemetry PMX performability extension as the scientific
  priority for M9F. That route is audited before a partially manual PCM fallback
  is selected; any required completion remains explicitly measured rather than
  credited to automation. M9F has now completed that audit. The paper,
  historical source lineage, later embedded source snapshot, and binary were
  recovered, but four isolated standalone invocations all reached a 900-second
  watchdog after emitting only `osgi> gosh: stopping shell` and produced no PCM
  file. This is a launcher-route reproducibility and application-cost result,
  not evidence against PMX's scientific priority or the wider Palladio
  ecosystem. M9G completed its dual-track diagnostic. The public historical
  artifact contains five complete PCM models and the full PMX transformation
  sequence, while all four frozen guessed Gogo commands were unregistered and
  emitted no model. Crucially, embedded source declares the exact command as
  `main:main`; M9H tested that route prospectively rather than treating M9G as a
  negative test of PMX. The exact command reproduced the historical five-model
  semantic signature in its screen and both original confirmations and exited
  cleanly. Its two frozen one-error confirmations also completed, but remained
  identical to the original: the logs exposed no failure aggregate and the PCM
  contained no internal software failure. M9I then recovered all 25 relevant
  embedded sources and localized the distinction loss: error detection runs
  before the marked Spring child is merged into its Tomcat parent, while the
  internal error marker is not propagated or recomputed. M9J's matched carrier
  controls then closed the bounded PMX diagnostic. Carrier false reproduced the
  historical model, while both carrier-true runs created a repeat-exact 0.1
  failure in the generated `VisitResource.read` SEFF. The strict prospective
  gate remains failed because its unlabeled stdout aggregate was assigned to an
  underidentified slot; retained PCM reference resolution records the intended
  operation without rewriting that gate. Work now moves to M9K's frozen
  single-operation localization of the proposed model's largest checkout
  overprediction, not to open-ended tool repair.
  Separately, 0/160 qualified learner bundles retained raw
  spans. Four raw samples are learner-only schema-adaptable, but lack the direct
  Spring-WebMVC instrumentation semantics and OTel needs a format adapter. No
  accuracy outcome was read and the M7 interpretation remains unchanged.

The successful remote integration evidence and its limitations are recorded in
`docs/milestones/M6_LIVE_INGESTION_HARNESS.md`.

Completed M7P starts the two actual applications, sends 120 predeclared external
requests per application, and retains native raw telemetry plus failure
diagnostics. The accepted run retained 120/120 HTTP-successful attempts and 28
native traces for DeathStarBench, and 120/120 attempts and 159 traces for OTel
Demo, with every active container matching a digest lock. These are technical
feasibility counts, not effectiveness estimates; details and the superseded
diagnostic attempt are recorded in
`docs/milestones/M7P_RUNTIME_FEASIBILITY_PILOT.md`. The subsequent M7 design is
frozen separately.

Completed M7A exercised the acquisition path under N, NC, ND, and NCD
interventions for both applications. Its accepted run retained all 1,920
requests, linked every assigned trace id, verified and restored all 48
interventions, and passed all aggregate quality gates. The first run exposed and
retained an OTel Docker-log rotation failure; the accepted run used a lossless
mounted native collector sink without changing the workload or threshold.
Details are recorded in
`docs/milestones/M7A_FAULT_ACQUISITION_DIAGNOSTIC.md`. This remains a diagnostic
namespace: only the later frozen M7 campaign can support a live prediction or
transfer claim. Completed M7B then replaced a key service with two real
containers behind an explicit HAProxy in both applications. Its accepted
four-cell run showed traffic on both named backends, placement-dependent
intervention sets, semantic operation responses, complete request--trace
linkage, and clean recovery; its first failed semantic-contract attempt is
retained. Details are in
`docs/milestones/M7B_REPLICATED_PLACEMENT_PILOT.md`. M7C next freezes the
stochastic schedule and independent-repetition budget before M7 effectiveness
outcomes are inspected. M7C and its transparent resource recovery are complete:
900-second periods, a one-second transition guard, and 10 campaigns in each of
16 strata are frozen in
`docs/milestones/M7C_STOCHASTIC_FREEZE_PILOT.md`. M7D is also complete: all 64
pilot schemas passed the executable anti-leakage boundary documented in
`docs/milestones/M7D_LEARNER_EVIDENCE_BOUNDARY.md`. No main-analysis fit was
used for either decision. The separate M7F main-path preflight is documented in
`docs/milestones/M7F_NO_FIT_PREFLIGHT.md`; its accepted run also performed no
fit or score and remains excluded from M7 effectiveness evidence. The full M7
result is recorded in `docs/milestones/M7_FROZEN_LIVE_VALIDATION.md`: all
`N/ND` campaigns were topologically supported, whereas 43 of 80 `NC/NCD`
campaigns had at least one ambiguous operation. Proposed matched B3 wherever it
emitted, and the calculation established no advantage over strengthened B2;
this is an input to diagnosis rather than a terminal verdict on the approach.

## Generated tables

- runs.csv contains rank, conditioning, moment counts, and fit status per dataset.
- parameters.csv contains truth, identifiability, estimates, and errors per factor.
- targets.csv contains the corresponding result for availability targets.
- moments.csv preserves every empirical moment, its factor union, effective
  observation count, and generator truth for audit and independent re-analysis.
- summary.csv aggregates predeclared accuracy and failure metrics by family,
  observation mode, and sample size.
- manifest.json records provenance and row counts.

The M1 workflow additionally emits reference_fits.csv, reference_estimates.csv,
patterns.csv, reference_summary.csv, and paired_summary.csv. Its protocol is
frozen in docs/M1_LIKELIHOOD_PROTOCOL.md before the non-smoke run.

The M3 workflow emits fits, parameters, predictions, placement changes,
decisions, independent validation draws, structural classifications, ambiguity
witnesses, paired campaign contrasts, and their summaries. Its completed result
is recorded in docs/milestones/M3_NON_DIRECT_PLACEMENT_TRANSFER.md.

The M5 workflow emits per-campaign estimates, diagnostics, guarded and raw
decisions, execution status, paired stress-minus-control effects, and aggregate
coverage/width/diagnostic summaries. Its protocol deliberately permits the
unchanged method to fail under violated assumptions; empirical performance is
not a build gate.

The M7 workflow emits per-cell/mode diagnostics, current and transfer
predictions, held-out scores, method summaries, frozen paired contrasts, and an
analysis manifest. Its primary row is deliberately marked incomplete when any
campaign abstains; the workflow does not impute missing predictions to obtain a
favorable result.

Generated results are intentionally ignored by Git. GitHub workflow artifacts are
the source of experimental outputs until a reviewed result snapshot is explicitly
frozen for the paper.

## Scope not yet implemented

The current implementation does not claim support for arbitrary Boolean request
predicates, overlapping failure domains, general sparse elimination, or EM. M2
is one proved compiler rule, not a general factor-graph solver. M3 supports one
explicit two-domain placement transfer. M5's state-dependent loss and temporal
dependence are directed stress generators, not general estimators for those
mechanisms. M7 tests live current and transfer prediction only for the exact two
benchmark revisions and declared logical domains. Its incomplete primary result
does not establish effectiveness superiority, physical domain independence, or
unconditional trace-topology sufficiency.
