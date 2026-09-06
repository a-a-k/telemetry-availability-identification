# Implementation roadmap

## Phase 1: rank and moment vertical slice

Status: implemented.

Evidence: `milestones/M0_RANK_AND_MOMENTS.md`.

- typed primitive factors and conjunctive observables;
- known state-independent observation masks;
- structural versus empirical identifiability;
- identified log-moment baseline;
- four-family RQ1 workflow with nested samples and provenance.

## Phase 2: exact observed likelihood reference

Status: implemented as milestone M1.

Evidence: `milestones/M1_EXACT_LIKELIHOOD_REFERENCE.md`.

- compile an episode and its mask into a likelihood factor;
- enumerate latent states for small models independently of the simulator;
- add a standard constrained optimizer as the B3 correctness reference;
- verify that equal likelihood objectives converge to equal optima on oracle cases;
- retain boundary and convergence status instead of silently selecting one optimum.

## Phase 3: proposed identification procedure

Status: partially implemented across milestones M1--M2. M2 supplies one proved
signature-reduction rule, direct reduced-likelihood optimization, and three-way
diagnostic output. General heterogeneous adapters, broader elimination rules,
and B1 remain later work.

Evidence: `milestones/M2_STRUCTURE_PRESERVING_REDUCTION.md`.

- factor-graph compilation from heterogeneous records;
- domain-local elimination rules with preservation tests;
- EM or direct sparse optimization for the same observed likelihood;
- three-way diagnostics: proved identifiable, proved ambiguous, unresolved;
- B1 and B2 estimators under matched data eligibility rules.

## Phase 4: uncertainty

Status: implemented in M4, with directed assumption stress in M5.

Evidence: `milestones/M4_SIMULTANEOUS_UNCERTAINTY.md` and
`milestones/M5_DIRECTED_STRESS_TESTS.md`.

- independent-campaign calibration on synthetic data;
- simultaneous observable-probability constraints for small ambiguous models;
- extrema of target availability over compatible parameter sets;
- block bootstrap implementation and coverage study for dependent episodes;
- separate input uncertainty from simulation Monte Carlo error.

## Phase 5: live ingestion and frozen validation

Status: implemented in M6 and M7. M7 completed technically, while its
predeclared primary contrast is incomplete and supports no superiority claim.

Evidence: `milestones/M6_LIVE_INGESTION_HARNESS.md` and
`milestones/M7_FROZEN_LIVE_VALIDATION.md`.

- versioned adapters for traces, lifecycle/health, deployment, and mesh evidence;
- explicit operation specifications and external-client success audit;
- immutable calibration model followed by independent test periods;
- DeathStarBench and OpenTelemetry Demo campaigns;
- B0-B4 comparisons and predeclared ablations.

## Phase 6: placement transfer

Status: implemented synthetically in M3 and evaluated on the frozen live M7
matrix. The live transfer result is conditional on topology support and the
declared homogeneous-new-domain assumption.

Evidence: `milestones/M3_NON_DIRECT_PLACEMENT_TRANSFER.md` and
`milestones/M7_FROZEN_LIVE_VALIDATION.md`.

- replace known placement metadata without target-configuration calibration;
- preserve only audited transferable residual parameters;
- predict availability change, configuration choice, and regret;
- expose violations of transfer assumptions rather than refitting them away.

## Phase 7: post-M7 diagnosis and Palladio comparison

Status: M8A through M9H are complete. M9G recovered the historical PMX output,
bounded four unsuccessful guessed Gogo commands, and measured the application
information delta. M9H then executed the prospectively source-derived exact
`main:main` entrypoint and reproduced the historical PCM output, while its
frozen one-error control remained semantically unchanged. M9I recovered the
exact embedded source and localized that result to an error marker lost while
the Spring child is merged into its surviving Tomcat parent. M9J now tests the
source-implied carrier contract prospectively. M9C byte-audited accepted M8B and pinned application sources, emitted
all 16 required correspondence rows, and matched the external structural oracle
for both operation templates under both logical placements. M9D then completed
the aligned-input debugging comparison on preserved M7 evidence.

Evidence contract: `M8_M7_DIAGNOSTIC_PROTOCOL.md`.

- preserve all still-available M7 qualified, raw-sample, and analysis artifacts;
- independently verify identities, scores, denominators, and aggregation;
- diagnose bias, temporal behavior, semantic failures, and topology ambiguity;
- bootstrap and semantically validate a pinned Palladio reliability analyzer;
- compare fixed estimators and PCM/Palladio on aligned inputs before collecting
  any new live confirmation.

M8B found no test-health alignment mismatch and no normalized-output drift in
the four retained raw samples. It localized overprediction mainly to
OpenTelemetry Demo, especially checkout, and confirmed mixed target support
under communication faults without assigning a unique cause. These are
exploratory restrictions on the next comparison, not a revised M7 result.

M9A rebuilt Palladio reliability 5.2.2 under an audited historical target lock,
byte-pinned its official product, and reproduced the official example at
success probability 0.375 in two calls, exactly matching a hand-checkable XMI
oracle. M9B then matched all 15 frozen mechanism-level controls twice. It also
confirmed that automatic allocation replication is unsupported and that a raw
link failure parameter is applied to both request and response transfer. M9C
encodes those constraints explicitly: source-grounded mandatory target calls,
two explicit paths, logical common domains, a marginal two-transfer link
mapping, and a semantic residual. Its synthetic witness is a structural test,
not an M7 estimate or comparative-validity claim. All eight remote solver
records matched the frozen oracle. M9D introduced preserved M7 calibration
inputs without changing the historical estimators: the PCM solver received a
learner-only replay of the matched B3 parameter realization, B0/B2 remained
direct comparators, and evaluator outcomes were joined only downstream. The
first-attempt run generated 184 admitted PCM instances and 368 measured solver
records. Palladio matched the independent oracle and direct B3/proposed result
within `3.34e-16`, but no common-support Brier comparison with B2 established a
gain. Current coverage was 119/160 and transfer coverage 65/80, with every
missing prediction retained as topology ambiguity. This validates the aligned
technical bridge, not an independent architecture-extraction route or
predictive accuracy. The next phase must freeze the information boundary and
independent-confirmation design before any new live collection.

M9E is the first gate in that phase. It remotely probes the compatible
Retriever 5.2 product on both complete pinned application trees. Fifteen
predeclared gates distinguish a structural PCM extraction from a
reliability-ready full path. M9E performs no accuracy scoring, does not fill
missing model elements, and authorizes no new live collection. Its result is
limited to the tested Retriever release and rules.

M9E is complete. Retriever exited successfully and emitted repository, system,
allocation, and resource-environment files for both applications, but the files
were empty shells. Each application passed only the extractor and four
file-presence gates (5/15); usage, operation/call, replica/domain, and all four
reliability-semantic gates failed. A post-result correction records that the
initial triage omitted the later headless OpenTelemetry PMX performability
extension. M9F therefore gives that published route scientific priority and
audits its source, binary, pipeline reproducibility, generated semantics, and
application costs before deciding whether a partially manual PCM continuation
is necessary. Accuracy and new live confirmation remain deferred until an
independently parameterized comparator exists and supports a precision
calculation.

M9F separately audited the prioritized later PMX performability route. Its
accepted three-job run verified the paper, historical source lineage,
demonstration commit, embedded later source snapshot, and public binary. Under
the tested standalone launcher contract, however, all four predeclared
invocations emitted only `osgi> gosh: stopping shell`, became CPU-idle, reached
their 900-second watchdogs, and wrote no result file. The exact historical
container chain is also unavailable because its published references use
mutable `latest` tags without retained digests. This establishes neither an
absence of the claimed transformation nor a limitation of PMX/Palladio as a
whole. M9G therefore proceeds on two explicitly separate tracks: diagnose and
recover the public launcher/source/container route, and measure the adapter and
information work needed for the fixed M7 applications. A manual PCM route, if
used, remains separately labelled and cannot substitute for PMX evidence.

M9G completed both tracks. It byte-audited all fourteen files in the public
historical job artifact and recovered five complete PCM models plus their full
transformation log. Its four frozen guessed Gogo commands were all unregistered,
wrote no output, and reached 120-second watchdogs. The same static audit found
the exact embedded declaration `scope=main`, `function=main`; because
`main:main` was not among the frozen candidates, the M9G negative is not
generalized to it and M9H tests it prospectively. The application audit found
zero raw streams in 160 qualified learner bundles. Four separate raw samples
were learner-filterable and schema-adaptable, but none had the audited direct
Spring-WebMVC instrumentation marker; OTel additionally requires a format
adapter. No evaluator input, accuracy outcome, or new collection entered M9G.

M9H resolved the launcher question on its first remote attempt. The exact
`main:main -of Options.txt` command derived independently from the embedded DS
descriptor and Java source entered the transformation, exited zero, produced
all five core PCM files, completed all six log stages, and matched the
historical semantic signature in one screen and two confirmations. The same
chain ran twice on the frozen one-error-in-ten trace control, but both outputs
remained identical to the unchanged model: no internal software failure and no
nonzero probability appeared. Raw stdout reported the same success counts and
`Failure: null` values in both conditions. Therefore launcher recovery is no
longer an open explanation, but the error-to-internal-failure mapping is. M9I
uses embedded source and retained M9H evidence to localize that boundary before
freezing another mechanism test. This sequence does not score accuracy, revise
M7, authorize collection, or generalize one binary to PMX/Palladio as a whole.

M9I completed the source-level diagnosis without another PMX invocation. It
byte-audited all 25 Java sources across the exact reader, trace-to-internal,
internal-to-system, and failure-probability bundles and reverified all four M9H
confirmation boundaries. The retained string-valued `error="true"` tag matches
the reader and detector contract. The marked Spring child is detected before
merging, but its internal `SpanContainsError` marker is not copied when the
child's operation/tags are merged into the same-process Tomcat parent; error
detection is not rerun. The surviving parent is therefore counted as success,
and the downstream probability transformer receives no failure count. M9J
freezes a matched true/false control on that exact surviving carrier, with the
retained child-true result as a merge-loss witness. This diagnoses one tested
binary and adds an explicit preprocessing/application cost; it does not lower
PMX's scientific priority or describe the whole Palladio ecosystem.
