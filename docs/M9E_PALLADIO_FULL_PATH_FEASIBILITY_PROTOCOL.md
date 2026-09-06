# M9E: Palladio full-path automation feasibility protocol

Status: frozen before the first remote extractor execution.

## Question and stopping rule

M9D established that Palladio executes the supplied M9C/B3 probability model
correctly. It did not construct that architecture or its reliability parameters
independently. M9E asks the narrower next question: can a publicly available
PCM extraction route produce a Palladio reliability-ready model for the two
fixed M7 operations without silently inheriting our topology and fitted
parameters?

This is a feasibility gate, not an accuracy comparison. It consumes no new live
outcome, computes no Brier score, and cannot change M7. A failed gate means only
that the tested extractor and rules do not provide that required element for
these pinned applications. It is neither a failure of Palladio nor a claim
about all PCM automation.

An application is `automatic_full_path_ready` only if every predeclared gate in
the JSON contract passes from the raw extractor output. Missing elements are
listed as manual or separately instrumented completion work. They are never
filled before the readiness decision. If either application is not ready, the
next comparator must be called `partially manual PCM`; no incomplete generated
model is sent to the reliability solver or scored.

## Candidate triage

Three automation families from the continuation plan are retained rather than
selecting only the easiest one.

PMX is not executed. Its official page describes extraction of architectural
performance models from Kieker logs and also states that the tool is no longer
maintained or supported. M7 has OpenTelemetry/native request and health
evidence, not Kieker OperationExecutionRecords. Converting those inputs or
evaluating a performance model as a reliability model would introduce a new
adapter and the wrong output semantics, so a failed run would be uninformative.

CIPM is not executed. The published implementation estimates performance-model
parameters such as resource demands, branches, loops, and parametric
dependencies, with technology-specific Java and tailored Lua transformations.
The paper does not specify an extractor for the MTTF/MTTR, communication
failure, shared-domain, semantic-success, and replication parameters required
by our reliability analyzer. Treating performance calibration as reliability
parameter extraction would overstate its scope.

Retriever is the most applicable executable structural candidate and is
therefore probed. It accepts heterogeneous project artifacts and has Docker and
ECMAScript rules. Version `v5.2.0.202408280745` is selected because it matches
the PCM 5.2 line used by the pinned reliability analyzer. The exact release
commit, Linux product asset, product checksum, rule registry, persistence path,
and default link-resource construction are locked in the JSON contract.

Sources:

- [official PMX page](https://se.informatik.uni-wuerzburg.de/en/tools/pmx/);
- [CIPM article](https://doi.org/10.1007/s10515-025-00521-9) and
  [replication record](https://doi.org/10.5281/zenodo.11236139);
- [official Retriever repository](https://github.com/PalladioSimulator/Palladio-ReverseEngineering-Retriever)
  and [compatible release](https://github.com/PalladioSimulator/Palladio-ReverseEngineering-Retriever/releases/tag/v5.2.0.202408280745).

## Fixed applications and rules

The applications, commits, operations, and source witnesses are inherited from
accepted M9C. They are not reselected after M9D.

| Application | Operation | Relevant implementation languages | Retriever rules |
|---|---|---|---|
| DeathStarBench Social Network | `read_user_timeline` | Lua entry, C++ target, Docker Compose | Docker |
| OpenTelemetry Demo | `browse_product` | TypeScript entry, Go target, Python driver, Docker Compose | Docker + ECMAScript |

Each complete application checkout is supplied to the extractor. Narrowing the
input to a favorable source fragment is forbidden. Operation-specific source
hashes are checked against M9C, and the extractor output is retained even when
the command exits nonzero or produces no model.

The probe uses one execution per application. This is enough for a deterministic
feasibility question; it is not a runtime benchmark. `/usr/bin/time -v` records
wall time and maximum RSS. Each application has an internal 5,400-second guard,
while every workflow job has `timeout-minutes: 360`.

## Full-path information boundary

The proposed route may use the frozen learner contract: semantic calibration
requests, sampled native traces, independent health observations, and declared
deployment/routing metadata. Evaluator requests and controller event times are
not learner inputs.

An independent PCM route may use the pinned upstream source and deployment
artifacts plus the same allowed calibration evidence. It may not copy our
fitted B3 vector, generated M9C/M9D XMI, or held-out outcome. A structural
extractor output remains independent only for the fields it actually produces.
Any human operation mapping, replica/fault-domain completion, semantic residual,
or reliability parameter must be explicitly logged with its source.

The eight mapping concerns remain request success, operation path, replication,
individual failure, communication failure, common domain, parameters, and
placement. M9E records in advance which evidence type each route would need; it
does not use absence from Retriever as permission to invent a value.

## Readiness gates

For each application, the audit checks all of the following in the raw output:

- successful extractor exit;
- repository, system, allocation, resource-environment, and usage models;
- a recognizable selected operation, both entry and target, and a SEFF external
  call path;
- two explicit target replicas and the two logical injected domains;
- reliability failure types and a semantic internal-failure residual;
- positive resource MTTF and MTTR values;
- a nonzero communication-link failure probability.

File presence is insufficient. A placeholder communication link with failure
probability zero does not count as a learned reliability parameter. Likewise,
a repository without a usage scenario cannot be loaded as our fixed operation
scenario merely by renaming it.

The downstream job hashes every generated model file, independently parses the
readiness evidence, and emits one row per gate. The raw extractor job does not
contain the gate decision logic.

## Planning guard after M9D

M9D may inform exploratory design but cannot size an independent full-path
contrast: `PCM-PAR/B3-parameters` equals B3 by construction and therefore has
zero between-method variance. No independent full-path prediction exists before
this gate. M9E consequently freezes neither a non-inferiority margin nor a
campaign count and authorizes no live collection.

If a partially manual PCM route is required, it must first be implemented and
debugged on preserved/development evidence with its information sources fixed.
Only then can its paired campaign-difference variance support a transparent
precision calculation. Any later confirming campaigns must remain independent
of M7/M9D/M9E development and preserve full raw traces and the direct probes
needed by both methods.

## Workflow and acceptance

The three remote jobs are:

1. audit the pinned M9C/M9D inputs, exact Retriever source/release metadata, and
   exact application sources;
2. verify the downloaded product checksum and execute Retriever for both full
   application checkouts, retaining logs, outputs, and resource use;
3. audit all output hashes and apply the frozen readiness gates.

All three jobs use `timeout-minutes: 360`. The accepted outcome may be ready,
partially ready, empty output, or a recorded extractor error. Acceptance means
the evidence chain and classification completed, not that automatic extraction
succeeded. Any source/hash mismatch, missing execution record, unclassified
gate, or use of accuracy outcomes fails the workflow.

The final manifest must keep these interpretation fields false:

- failed gate is an accuracy result;
- Retriever represents all PCM automation;
- M7 interpretation changed;
- new live collection authorized.
