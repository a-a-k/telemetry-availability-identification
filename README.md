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

Milestone M6 adds the versioned `taid.live_bundle/v1` ingestion boundary. It
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

Generated results are intentionally ignored by Git. GitHub workflow artifacts are
the source of experimental outputs until a reviewed result snapshot is explicitly
frozen for the paper.

## Scope not yet implemented

The current implementation does not claim support for arbitrary Boolean request
predicates, overlapping failure domains, general sparse elimination, or EM. M2
is one proved compiler rule, not a general factor-graph solver. M3 supports one
explicit two-domain placement transfer. M5's state-dependent loss and temporal
dependence are directed stress generators, not general estimators for those
mechanisms. M6 provides ingestion and upstream-integration evidence only; live
effectiveness and live placement transfer remain untested until M7.
