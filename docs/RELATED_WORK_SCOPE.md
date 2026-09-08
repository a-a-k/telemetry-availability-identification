# Focused related-work and attribution ledger

Status: a focused primary-source comparison for the current mathematical and
experimental claims, not an exhaustive literature review. Read on 2026-09-07.
Status updated 8 September: [M9P](milestones/M9P_INDEPENDENT_TEMPORAL_CONFIRMATION.md)
is complete, with conditional replication and marginal practical equivalence;
M9R's bounded composition census is complete without a valid probability.
This ledger does not select favorable comparators or turn
an implementation difficulty into evidence of scientific superiority.

## Identification and the observation contract

**Bu, Duffield, Lo Presti and Towsley (2002), _Network Tomography on General
Topologies_.** Sections 2–3 model independent link transmissions and derive a
linear system for log success probabilities. Theorems 1–2 cover identification
of all links and a specified subset. Section 4 develops matched estimation from
the same measurements. This is a direct predecessor for the combination of
path products, log-linear rank, partial parameter identification and statistical
inference. A claim that these ideas are new in the present study would be
incorrect. [Author-hosted paper](https://nickduffield.net/download/papers/Bu_tomography_02.pdf).

Our correspondence is to masked conjunction observations over declared
domain/instance/communication primitives and to a requested reliability target.
The new note's polynomial-target criterion requires an explicit proof and
careful novelty comparison; adding microservice names to an old inverse problem
does not itself establish a theoretical contribution. The live study also asks
whether that static observation/execution contract represents semantic request
success, which is separate from algebraic identifiability.

**Duffield (2006), _Network Tomography of Binary Network Performance
Characteristics_.** Sections 1.2–1.3 exhibit the multiplicative ambiguity of
separate path-success rates and explain the additional information in correlated
measurements. Later sections develop inference under binary performance
separability assumptions. The shared-path ambiguity example in our theorem note
must therefore be attributed as an explanation of an established phenomenon.
Its later binary-failure localization results are not a direct availability
estimator for the benchmark's repeated checkout calls. [Author-hosted paper](https://nickduffield.net/download/papers/D06-binary.pdf).

**Ma, He, Leung, Swami and Towsley (2013), _Identifiability of Link Metrics Based
on End-to-end Path Measurements_.** Sections 1–2 explain additive metrics,
log-transformed delivery ratios, rank and inseparable link combinations. The
paper's main contribution characterizes identification by topology and monitor
placement under controllable cycle-free paths. Our duplicate-membership product
reduction shares that elementary inseparability mechanism; it does not establish
a new minimum-monitor placement algorithm. [Author-hosted paper](https://www.commsp.ee.ic.ac.uk/~wiser/publications/Liang/NetworkTomography-IMC13.pdf).

**Nguyen and Thiran (2007), _Network Loss Inference with Second Order
Statistics of End-to-End Flows_.** Section 3.1 first collapses indistinguishable
consecutive links into virtual links and removes unobserved columns. Sections
3–5 then use covariances across flow snapshots to identify link-loss variances
under declared routing and sampling assumptions; the mean-loss inference also
uses the congestion/variance relation. This is a close precedent for explicit
alias reduction and obtaining information beyond marginal path means. Its
random snapshot log rates and covariance system differ from our Bernoulli
joint-success moments. We must not identify those two uses of “second order,”
or claim that link-alias reduction originated here.
[Conference paper, full text](https://conferences.sigcomm.org/imc/2007/papers/imc70.pdf).

**Geiger, Meek and Sturmfels (2006), _On the Toric Algebra of Graphical Models_.**
Section 2 connects monomial parameterizations with log-linear statistical models;
the paper studies factorization and algebraic conditions for graphical models.
This provides relevant mathematical background. Its normalized probability
parameterization and our supported moment vector are different objects, so
citing it cannot replace the proof of the masked-law equivalence or the exact
target statement used here. [Author-hosted paper](https://math.berkeley.edu/~bernd/AOS0092.pdf).

The present exact rational reference only implements the restricted statement in
[the theorem note](CONJUNCTIVE_OBSERVATION_TARGET_THEOREMS.md). It does not certify
an arbitrary Boolean observation map or automatically find a minimal dynamic
microservice model. The monomial row criterion, Boolean polynomial expansion,
and observational equivalence must each retain their hypotheses.

## Probability bounds and uncertainty

**Prékopa (1990), _Sharp Bounds on Probabilities Using Linear Programming_.**
The publisher's abstract describes LP bounds for unions and specified counts
of occurring events. Only the abstract was used here; no claim is made to have
read the full paper. [Publisher page](https://pubsonline.informs.org/doi/10.1287/opre.38.2.227).

**Boros and Lee, _Boole's Probability Bounding Problem, Linear Programming
Aggregations, and Nonnegative Quadratic Pseudo-Boolean Functions_, arXiv v4
(2025).** The introduction and original LP formulation describe the atom-based
probability-bounding problem, its historical basis and sharp attainable bounds.
The nine-atom two-path construction in this repository is a small specialization
of that established approach. Exponential atom count alone does not justify an
unqualified claim about the complexity of every associated optimization problem.
[Full text](https://arxiv.org/html/2110.10672).

Our [two-path note](B2_SHARP_OBSERVABLE_BOUNDS.md) supplies explicit attainable
envelopes under three declared dependence contracts. Its purpose is to expose
which assumptions turn an interval into the B2 point target. The elementary
union identities and LP construction are not a claimed new general method.
Likewise, projecting simultaneous confidence constraints through a feasible
parameter/law set is a standard coverage argument. M4's contribution to the
record is its implemented, frozen assessment under specified iid assumptions;
M5 prevents extending that result automatically to dependent or selectively
missing telemetry.

## Architecture extraction, validation and performability

**Weber, Weber and Henß, _Integration of Performability-Model Extraction and
Performability Prediction in Continuous Integration / Continuous Delivery_.**
The three-page report describes a PMX/PCM extraction and simulation pipeline
using traces and metrics, including per-function error counting. Its component
identification is tailored to Spring Boot's OpenTelemetry instrumentation, and
the Petclinic exercise assesses pipeline functionality. This is a scientifically
relevant full-path direction. A failed attempt with a separate Retriever route
does not test this method. [GI paper](https://fb-swt.gi.de/fileadmin/FB/SWT/Softwaretechnik-Trends/Verzeichnis/Band_45_Heft_1/SSP24_26_camera-ready_8969.pdf).

The cited report and the exact pinned binary/source used in M9F–R must be
distinguished. Source/output correspondence is required for claims about that
binary; a report's intended behavior is not proof that a particular saved file
implements it. Conversely, a defect or integration limit in that saved version
does not establish a limitation of the entire PMX/Palladio ecosystem. M9Q's
observed-operation adaptation and M9R's disclosed serialization/parameter
variants are additional study work whose assumptions and costs remain visible.

**Mazkatli, Monschein, Armbruster, Heinrich and Koziolek (2025), _Continuous
Integration of Architectural Performance Models with Parametric Dependencies –
the CIPM Approach_.** The paper combines model updates after software/runtime/
usage changes with adaptive monitoring, validation and recalibration of affected
performance parameters. Its evaluation covers accuracy, monitoring overhead and
scalability in six cases. Therefore automatic architectural calibration,
self-validation, and reducing instrumentation effort already have substantial
prior art. Our paper must not claim them as unqualified firsts. [Publisher full text](https://link.springer.com/article/10.1007/s10515-025-00521-9).

This comparison does not assert that CIPM has been tested on the current
functional-availability endpoint or that its published overhead numbers transfer
to our deployment. It identifies the existing research line against which any
automation or monitoring-cost claim must be framed. Our acquisition bytes and
runner/process timers do not measure an instrumented-versus-uninstrumented
monitoring effect.

**Friederich and Lazarova-Molnar (2022), _Data-Driven Reliability Modeling of
Smart Manufacturing Systems Using Process Mining_.** The full conference paper
specifies event and resource-state logs, extracts a Petri-net process, adds
resource fault models, and estimates activity/failure/repair distributions.
Sections 3.1.4 and 3.2 use timestamped resource-state changes for the fitted
durations. Section 4's data come from a simulated flow line; Section 5 places
further validation and timed-transition policy identification in future work.
This supplies a concrete extraction-and-parameterization predecessor, beyond
a general aspiration to automate modeling. Its observed resource histories
are a different input contract from our masked primitive/path inference; that
distinction must not become an unsupported claim about all later versions of
the authors' method. [WSC proceedings, full text](https://informs-sim.org/wsc22papers/254.pdf).

**Friederich and Lazarova-Molnar (2025), _Data-driven Reliability Assessment of
Manufacturing Systems Using Process Mining_.** The publisher's abstract
describes extraction, simulation, validation and decision support, demonstrated
with two flow-line cases. This already occupies the broad claim of a data-driven
reliability-model lifecycle, although it addresses manufacturing. Only the
abstract and publication metadata were accessible in this check; no comparison
of its detailed identifiability guarantees is inferred from their absence in
the abstract. The issue date is August 2025 and the online-first date is
30 December 2024. [Publisher page](https://journals.sagepub.com/doi/10.1177/00375497241302866),
[author-institution record](https://portal.findresearcher.sdu.dk/en/publications/data-driven-reliability-assessment-of-manufacturing-systems-using/).

The authors' earlier equipment-centric study explicitly describes using event
logs and resource-state logs to extract stochastic Petri nets, simulate them,
and validate a wafer-fabrication case. Thus combining interaction/event and
state evidence for reliability simulation also has direct precedents. This
statement uses the author institution's abstract, not an unverified claim about
its handling of partial observability or causal fault separation.
[Friederich, Cai, Gan and Lazarova-Molnar, SIGSIM-PADS 2023](https://portal.findresearcher.sdu.dk/en/publications/equipment-centric-data-driven-reliability-assessment-of-complex-m/).

## Target exposure and transport

**Sugiyama, Krauledat and Müller (2007), _Covariate Shift Adaptation by
Importance Weighted Cross Validation_.** Sections 1–2 distinguish changing
input distributions from a stable conditional response law; the theoretical
setup assumes known finite density ratios before considering empirical
estimation. Context reweighting therefore must be attributed to that established
research line. Our target-exposure identity and two-context illustration do
not establish a new adaptation method or justify invariance after a failure or
deployment intervention. [JMLR full text](https://jmlr.org/papers/volume8/sugiyama07a/sugiyama07a.pdf).

## Consequences for the current article argument

The reportable contribution must be narrower than discovery of log-linear
identification, likelihood estimation, union bounds, automatic model extraction
or model self-validation. The current record combines a declared observation
contract, explicit target certificates and ambiguity, an exact restricted
reduction, uncertainty under stated assumptions, and an audited examination of
live execution semantics and matched information inputs. The strength and
generality of that combination must be assessed from the completed evidence,
including unfavorable comparisons.

A claim of greater predictive accuracy, lower end-to-end cost, or an automatic
choice of the smallest adequate model still needs direct evidence. The article
should explain the qualified mathematical guarantees and the measured failure
boundaries without presenting the historical sequence of integration attempts
as the main contribution. M9P now bounds the temporal model's extra marginal
value within its registered equivalence region and passes its mean-bias criterion.
It establishes no accuracy superiority over the matched endpoint or PMX. The
independent PMX request-level mapping and comparison remain outstanding.
