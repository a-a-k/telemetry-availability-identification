# M9B: Palladio semantic-control protocol

Status: frozen before the first remote Palladio execution.

## Purpose and scientific boundary

M9B tests whether explicit PCM 5.2 encodings exercise the reliability
mechanisms needed for a later aligned comparison. It is a correctness and
semantic-mapping milestone, not a comparison between Palladio and the
telemetry-driven estimators. It does not map M7 campaigns into PCM and cannot
change the M7 conclusion.

The current position remains: M7 establishes neither a predictive gain nor
agreement with the observations, while the causes of the discrepancies remain
insufficiently resolved to label the overall approach successful or failed.

The controls are deliberately small because their answers must be derivable
without Palladio. They are not presented as a competitive architecture or as a
surrogate for either live application. Richer application models are admitted
only after these mechanism-level encodings pass.

## Frozen software and execution boundary

- analyzer: official `Palladio-Analyzer-Reliability` 5.2.2 commit
  `a694e570afb705dc9e0470dc321e77b7219dcea4`;
- PCM metamodel: official `Palladio-Core-PCM` release 5.2.2 commit
  `5fbcc3409e02687881f88ab78b6242d8acd2677c`;
- Java: Temurin 17;
- historical target lock: the accepted M9A configuration with SHA-256
  `a7fd6e784612b4ba2df06f4ef2de4a4755a23a873540857f181831718825bc1d`;
- solver configuration: exact physical-state iteration, no state-count,
  decimal-place, or solving-time early stop; `POINTSOFFAILURE` evaluation;
- repetitions: two technical runs of every case;
- probability tolerance: `1e-12`;
- execution: full Palladio build and solving only in GitHub Actions;
- all three workflow jobs: `timeout-minutes: 360`.

The generated XMI, its independent structural audit, raw solver output, source
capability audit, logs, and final acceptance manifest are retained as separate
workflow artifacts.

## Predeclared cases and oracles

The exact parameters and expected values are machine-readable in
`configs/m9b_palladio_semantic_controls.json`. The following table is frozen
before solver output is available.

| Case | Mechanism and parameters | Independent success oracle |
|---|---|---:|
| `single_p0` | one action, software failure `p=0` | `1.0` |
| `single_p20` | one action, software failure `p=0.2` | `0.8` |
| `single_p100` | one action, software failure `p=1` | `0.0` |
| `fallback_perfect_alternative` | primary `p=0.2`, handled alternative `p=0` | `1.0` |
| `fallback_nominal` | primary `p=0.2`, handled alternative `p=0.3` | `0.94` |
| `fallback_failed_alternative` | primary `p=0.2`, handled alternative `p=1` | `0.8` |
| `conditional_b0` | failing action `p=0.4`, branch probability `b=0` | `1.0` |
| `conditional_b25` | failing action `p=0.4`, branch probability `b=0.25` | `0.9` |
| `conditional_b100` | failing action `p=0.4`, branch probability `b=1` | `0.6` |
| `network_q0` | cross-container call, link failure `q=0` | `1.0` |
| `network_q10_raw` | cross-container call, raw link failure `q=0.1` | `0.81` |
| `network_call_failure_10_mapped` | desired call success `0.9`, mapped `q=1-sqrt(0.9)` | `0.9` |
| `network_q100` | cross-container call, link failure `q=1` | `0.0` |
| `independent_redundant_paths` | explicit primary/fallback path availabilities `0.8`, `0.7`; common domain up | `0.94` |
| `shared_domain_redundant_paths` | same paths and common-domain availability `0.9` | `0.846` |

The formulas are:

- single action: `1-p`;
- typed fallback: `1-p_primary*p_alternative`;
- conditional call: `1-b*p`;
- implementation-level link control: `(1-q)^2`;
- explicit redundant paths: `A_1 + (1-A_1)*A_2`;
- common domain: `A_common * (A_1 + (1-A_1)*A_2)`.

The software and network controls have one physical state. The independent
path model has four states and the common-domain model has eight; acceptance
requires complete enumeration and total physical-state mass one.

## Communication-parameter semantic check

The pinned PCM metamodel describes `failureProbability` as the probability
that a service call over the link fails. The pinned analyzer source expands an
internal cross-container call into request transfer, remote execution, and
response transfer, applying the same link probability to each transfer.

M9B therefore freezes both interpretations rather than selecting one after
seeing output. With raw `q=0.1`, the source-level implementation oracle is
`(1-0.1)^2=0.81`, while the call-level reference from the metamodel wording is
`0.9`. A second case uses `q=1-sqrt(0.9)` and must return `0.9` under the equal,
independent two-transfer assumption. Direction-specific, correlated, or
interval-level communication data would require a different mapping; M9B does
not assume that this transformation already applies to M7 telemetry.

## Replication and common-domain encoding

The pinned analyzer source explicitly states that multiple allocation contexts
for one assembly context are not supported as replication: it selects one and
warns that results are inaccurate. M9B must not conceal that limitation by
duplicating allocation entries.

The redundancy controls instead encode a specified routing policy: a dispatcher
first calls path A and handles CPU-unavailability by calling a distinct path-B
component. The two components have distinct assembly, allocation, and resource
contexts. The shared-domain variant adds a `requiredByContainer=true` physical
resource to the dispatcher, so its unavailability gates both paths. This
validates explicit primary/fallback semantics only. It does not establish that
Palladio 5.2.2 natively represents an unspecified load balancer or Kubernetes
replica selection policy.

Physical availability is calculated by the analyzer as
`MTTF/(MTTF+MTTR)`. The chosen pairs are control inputs that realize the stated
ratios. They make no claim that a single telemetry availability identifies
MTTF and MTTR separately; that identification and censoring question remains a
later mapping requirement.

## Independent structural audit

Before solving, a Python audit parses the generated XMI and rejects a control
unless it verifies all of the following:

- usage scenarios bind the intended signatures and SEFFs;
- software controls contain exactly the specified action, typed handler, or
  probabilistic branches;
- the communication control contains one internal cross-container external
  call, two distinct allocations, a connecting link, and no software or
  hardware failure confound;
- redundancy uses two distinct required roles, components, assembly contexts,
  allocations, and resource containers;
- the fallback handles the CPU hardware failure type;
- the common resource gates the dispatcher and the link is perfect;
- every primitive parameter parsed from XMI agrees with the frozen JSON;
- all five PCM files for each model are hashed.

The model auditor also byte-verifies the pinned PCM metamodel and the M9A
bootstrap configuration. A separate source auditor byte-verifies
`MarkovSeffVisitor.java`, confirms the replication warning, and counts the two
message-transfer expansions.

## Acceptance and interpretation rules

The Java harness records scenario names and raw probabilities but contains no
expected success values. A downstream job accepts M9B only if all 30 records
(15 cases by two repetitions):

1. match the predeclared oracle within `1e-12`;
2. conserve success plus failure probability and physical-state mass;
3. enumerate every expected physical state;
4. repeat within tolerance;
5. satisfy the predeclared monotonic checks for failure, fallback quality,
   branch exposure, and link failure;
6. show lower success with the shared domain and exactly the expected `0.9`
   ratio to the otherwise identical independent-path control;
7. recover call success `0.9` in the explicitly mapped network case.

A failed control is first a model, integration, or semantic-mapping diagnostic.
It is not evidence that Palladio or the telemetry-driven approach is generally
successful or failed. A passed M9B establishes only that the recorded explicit
encodings match their hand-computed models. The next admissible step is a
mapping table and minimal operation model for each application, not a direct
headline comparison.
