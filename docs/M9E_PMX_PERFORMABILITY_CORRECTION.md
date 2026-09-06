# M9E corrigendum: PMX performability route

Status: post-result correction recorded on 2026-09-06, after the accepted M9E
Retriever run and before M9F.

## Correction

The frozen M9E candidate triage was incomplete. It assessed the legacy PMX
distribution described by the old official tool page, but it did not separately
assess the later PMX performability work by Weber, Weber, and Henß. That work is
scientifically closer to the required full path because it reports a headless
PMX pipeline, OpenTelemetry trace input, a dependability transformation based
on erroneous spans, and downstream Palladio simulation.

Consequently, the following interpretation replaces the overly broad M9E
planning conclusion:

- lack of direct PMX support would increase application and integration cost;
  it would not remove PMX's scientific priority as the closest published
  comparator;
- `partially_manual_PCM_required` is the outcome of the tested Retriever
  branch, not a classification of every Palladio automation route;
- the selected Retriever release and rules are one executable structural
  probe. Their missing capabilities do not establish absence from other
  Retriever versions, extensions, or the Palladio ecosystem;
- a partially manual PCM baseline remains a possible fallback or cost-bearing
  variant, but it does not replace a separate PMX-performability audit.

The accepted M9E artifact, its 5/15 gate counts, and its no-scoring result are
unchanged. The frozen protocol and JSON contract remain untouched so their
pre-result identities continue to match the accepted workflow. This document
corrects only the scope inference and the order of subsequent work.

## Evidence newly brought into scope

The primary publication is [Integration of Performability-Model Extraction and
Performability Prediction in Continuous Integration / Continuous
Delivery](https://fb-swt.gi.de/fileadmin/FB/SWT/Softwaretechnik-Trends/Verzeichnis/Band_45_Heft_1/SSP24_26_camera-ready_8969.pdf).
The retrieved 244,692-byte PDF has SHA-256
`5d45195448d2a12c502a202721215c93d0623c1e02c7e6c9565338eff54c9a8f`.
It describes:

- refactoring PMX from an Eclipse UI into a headless OSGi pipeline with
  configurable reader, transformation, and writer stages;
- OpenTelemetry-format trace ingestion;
- propagation of error information from spans and estimation of functionality
  failure probabilities;
- a CI/CD chain from extraction to Palladio simulation and retained results.

The paper's own scope limits remain material. Its prototype check uses Spring
Petclinic, component detection is tailored to the available Spring Boot
instrumentation, the example is explicitly not representative, and accuracy
evaluation is future work. The publication therefore establishes a relevant
route and scientific priority, not readiness for the two M7 applications or
validity for the article's target probability.

Three public repositories/artifacts can be pinned:

1. The [OpenTracing PMX refactoring source](https://github.com/ptreyer/org.palladiosimulator.pmxupgrade)
   is available at commit
   `9ee8b8745c0c0bb3dfc1b529906fc001525a7ce5` under EPL-2.0. Its checked-in
   `FailureEstimationService` still contains a TODO and returns the system model
   unchanged, so this 2020 source tree alone is not evidence for the later
   dependability implementation.
2. The [PCM companion source](https://github.com/ptreyer/org.palladiosimulator.pmxupgrade-pcm)
   is available at commit
   `6ec1cb7387efc236c0e55f44ed5c79acb5fd9d33`. It supplies PCM construction
   code and failure-type resources, but its command-line class contains a
   developer-local hard-coded input/output path. This is an integration-cost
   observation, not a scientific exclusion.
3. The paper's [public CI/CD demonstration repository](https://se-gitlab-extern.fzi.de/SebastianWeberFZI/ableitung-von-leistungsmodellen-in-ci)
   is available at commit
   `9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2`. It contains four
   Jaeger/OpenTelemetry trace exports, an options file naming
   `TransformerSystemToPCMFailureDependencies`, and a 65,729,095-byte headless
   JAR with Git blob ID `cd46b43e3632b242bd670d898c597cd7772f5e2c`.
   The associated public pipeline 1120 completed successfully in 2024.

The last repository does not publish the corresponding plugin source or a
license file. Its pipeline refers to PMX, Palladio-runtime, and gnuplot images
through mutable `latest` tags. On 2026-09-06 the unauthenticated GitLab registry
API still listed the three repositories but returned no retained tags. Thus
the paper demonstrates an executed full chain, while exact present-day source
and container reproduction must be audited rather than presumed impossible or
presumed complete.

## Revised next milestone

M9F is a PMX-performability reproducibility and semantic-fit audit. Before any
accuracy scoring or new live collection it must:

1. pin and inventory the paper, both source repositories, the demonstration
   commit, binary JAR, sample traces, and any recoverable container identities;
2. execute the published headless extractor on its own public example in
   GitHub Actions and retain raw logs and generated files;
3. distinguish source-reproducible, binary-reproducible, and unavailable
   stages of the published chain;
4. map the produced PCM semantics separately to operation/control flow,
   software failure probability, host lifecycle, communication failure,
   replication, common failure domains, and the external-client success
   contract;
5. record every adapter, instrumentation requirement, and manual completion as
   application cost rather than treating it as a reason to demote the method;
6. leave M7 and all predictive-accuracy claims unchanged.

Only after this audit may the project decide whether M9F can extend the
published PMX route directly for the two applications or must expose a
partially manual continuation alongside it.
