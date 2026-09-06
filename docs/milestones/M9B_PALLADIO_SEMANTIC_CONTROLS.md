# M9B: Palladio semantic controls and mapping constraints

## Outcome

M9B is complete as a semantic-correctness milestone. The accepted GitHub
Actions run generated and independently audited seven PCM model groups, ran 15
hand-checkable cases twice through the pinned Palladio reliability 5.2.2
solver, and compared all 30 raw records with the oracles frozen before the
first execution.

Every case passed. The largest absolute oracle error was
`1.1102230246251565e-16`; the maximum success-plus-failure residual, physical
state mass residual, and between-repeat difference were all zero. The two
resource controls completely enumerated their four and eight physical states.
All seven predeclared monotonic and cross-control relationships also passed.

This establishes that the recorded explicit PCM encodings implement the small
mathematical models claimed for them. It is not an application-level accuracy
comparison, it does not validate an M7-to-PCM mapping, and it does not establish
native replica-selection support in Palladio 5.2.2.

The scientific position is unchanged: the published M7 calculations establish
no predictive gain and disagree with observations, while the causes remain
insufficiently resolved to declare the overall telemetry-driven approach
successful or failed.

## Frozen contract and implementation

The protocol and all expected probabilities were committed before the first
remote execution in commit
`71d7a82cfdc77036da62a17352f17e44e5a8100a`. The final accepted implementation
commit was `d35219472104ba41a179fc9e53ca5f54deca57e5`. The frozen configuration
SHA-256 was
`37fb11b921c547d3e5c0bbb8211a7bd7c65911ac828e25c7d96a0430628e7cef`.

The execution boundary was:

- official `Palladio-Analyzer-Reliability` 5.2.2 commit
  `a694e570afb705dc9e0470dc321e77b7219dcea4`;
- official PCM 5.2.2 metamodel commit
  `5fbcc3409e02687881f88ab78b6242d8acd2677c`;
- byte-verified `MarkovSeffVisitor.java`, 60,862 bytes, SHA-256
  `b95c1a89bc51857f7e51b56f7e03e7af22f960090429926962ee30e2d085040e`;
- byte-verified `pcm.ecore`, 312,718 bytes, SHA-256
  `04a1c8b753bdf4e957b7ba7d00440ab09a1774ceca758356210c886138efe5c8`;
- unchanged accepted M9A historical target lock, configuration SHA-256
  `a7fd6e784612b4ba2df06f4ef2de4a4755a23a873540857f181831718825bc1d`;
- Temurin 17.0.20.1 and Maven 3.9.16 on GitHub-hosted Ubuntu;
- exact physical-state iteration with no solver time, state-count, or decimal
  early stop;
- two technical repetitions per case and probability tolerance `1e-12`;
- all three workflow jobs with `timeout-minutes: 360`.

Python generated the XMI and performed a separate structural audit. The Java
harness loaded the resulting five-file PCM models through Palladio's standard
workflow, invoked `Pcm2MarkovStrategy`, checked probability mass and
repeatability, and wrote raw values without containing expected success
probabilities. A downstream Python job, isolated from the solver job, applied
the frozen oracles and relationship checks.

## Accepted execution

The accepted workflow was
[run 34024130716](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34024130716),
attempt 1 at the final implementation commit. All three jobs succeeded.

| Job | Result | GitHub wall time | Measured command wall time | Peak RSS |
|---|---|---:|---:|---:|
| Generate and structurally audit models | Passed | 21 s | 2.03 s | 109,216 KiB |
| Build and execute the solver suite | Passed | 3 min 40 s | 3 min 4.43 s | 1,703,832 KiB |
| Audit raw results against frozen oracles | Passed | 20 s | 1.09 s | 108,188 KiB |

The matching two-version repository CI was
[run 34024130892](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34024130892)
and also succeeded. Locally, all 127 unit tests passed; no Palladio build or
model execution was run locally.

## Solver results

| Case | Expected success | Repeat 1 | Repeat 2 | Absolute error per repeat | Physical states |
|---|---:|---:|---:|---:|---:|
| `single_p0` | 1.0 | 1.0 | 1.0 | 0 | 1 |
| `single_p20` | 0.8 | 0.8 | 0.8 | 0 | 1 |
| `single_p100` | 0.0 | 0.0 | 0.0 | 0 | 1 |
| `fallback_perfect_alternative` | 1.0 | 1.0 | 1.0 | 0 | 1 |
| `fallback_nominal` | 0.94 | 0.9400000000000001 | 0.9400000000000001 | `1.11e-16` | 1 |
| `fallback_failed_alternative` | 0.8 | 0.8 | 0.8 | 0 | 1 |
| `conditional_b0` | 1.0 | 1.0 | 1.0 | 0 | 1 |
| `conditional_b25` | 0.9 | 0.9 | 0.9 | 0 | 1 |
| `conditional_b100` | 0.6 | 0.6 | 0.6 | 0 | 1 |
| `network_q0` | 1.0 | 1.0 | 1.0 | 0 | 1 |
| `network_q10_raw` | 0.81 | 0.81 | 0.81 | 0 | 1 |
| `network_call_failure_10_mapped` | 0.9 | 0.8999999999999999 | 0.8999999999999999 | `1.11e-16` | 1 |
| `network_q100` | 0.0 | 0.0 | 0.0 | 0 | 1 |
| `independent_redundant_paths` | 0.94 | 0.94 | 0.94 | 0 | 4 |
| `shared_domain_redundant_paths` | 0.846 | 0.846 | 0.846 | 0 | 8 |

For every raw record, summed failure probability was exactly one minus success
at the written precision and accumulated physical-state probability was 1.0.
The accepted audit also verified:

- success decreased monotonically for software failure `p=0, 0.2, 1`;
- fallback success decreased as the alternative changed from perfect through
  `p=0.3` to always failing;
- conditional success decreased as branch exposure changed from 0 through
  0.25 to 1;
- communication success decreased for raw `q=0, 0.1, 1`;
- adding common-domain availability 0.9 reduced explicit redundant-path
  success from 0.94 to 0.846;
- the shared-to-independent ratio was exactly 0.9;
- the explicitly mapped link parameter recovered call success 0.9.

## Mapping results and capability boundaries

### Communication probability

The PCM metamodel describes link `failureProbability` as the probability that a
service call over the link fails. The pinned analyzer implementation applies
the same value separately to request and response transfer. Consequently, a
raw value `q=0.1` produced `(1-q)^2=0.81`, not the call-level reference 0.9.

The predeclared mapped case used
`q=1-sqrt(0.9)=0.05131670194948623` and produced
`0.8999999999999999`. This is a usable mapping only under the stated equal,
independent request/response assumption. Direction-specific, correlated, or
interval-level M7 observations cannot be inserted without another justified
mapping.

### Replication and common domains

The pinned source explicitly says that automatic replication through multiple
allocation contexts is unsupported and that one context is selected while the
others are ignored. M9B therefore did not encode a decorative duplicated
allocation. It used two distinct components and resource containers plus a
typed primary/fallback dispatcher.

The independent and shared-domain controls verify this explicit policy only.
They do not show that it matches the HAProxy routing behavior in M7, and they do
not turn Palladio 5.2.2 into a native model of arbitrary replicated service
selection. M9C must record this as a mapping decision or an unsupported case.

### Resource availability

The resource controls used MTTF/MTTR pairs solely to realize stationary
availabilities through `MTTF/(MTTF+MTTR)`. A single observed availability does
not identify those two quantities separately. M9B therefore makes no recovery
dynamics or telemetry-identification claim from the chosen pairs.

## Retained diagnostic history

Three remote attempts were rejected before acceptance. None contributes solver
values to the accepted result.

- [Run 34022996935](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34022996935)
  at the frozen protocol commit stopped at Java compilation: the harness used a
  non-API PCM name accessor. Commit
  `cf624768c8f4199f26cea2141756e8c5dd1ed857` replaced it with public EMF
  feature access without changing models or oracles.
- [Run 34023330264](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34023330264)
  compiled and entered the test runtime but lacked an explicit OSGi dependency
  on the PCM metamodel. Commit
  `1ffe9c0df774764b0c18c351de1915aef4368fa3` added the PCM and EMF runtime
  bundles.
- [Run 34023595218](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34023595218)
  loaded the models but exposed an incomplete bidirectional EMF serialization
  for software-failure occurrences. Commit
  `d35219472104ba41a179fc9e53ca5f54deca57e5` added the canonical reverse links,
  an independent structural gate, and model-progress logging. Parameters and
  expected probabilities remained unchanged.

Every rejected run retained the model-contract and solver-stage artifacts. The
sequence distinguishes integration and XMI-coding corrections from a changed
scientific hypothesis.

## Accepted artifacts

| Artifact | ID | Compressed bytes | Artifact digest | Retained through |
|---|---:|---:|---|---|
| `m9b-palladio-model-contract-34024130716` | 9986490948 | 85,562 | `sha256:8299ddbddc64f0d1fb84566e8efb0df45153965a50eca2628394fdd4cec98f23` | 2026-12-05 |
| `m9b-palladio-semantic-controls-34024130716` | 9986546794 | 82,769 | `sha256:41f89a3dd2044a3af1a9f63e363d45f8f5f473f64f6df5099d29a2bba15f9ffd` | 2026-12-05 |
| `m9b-palladio-acceptance-34024130716` | 9986561114 | 4,006 | `sha256:17563b8340e7b6e021b6cdf681e1ea23b37ac69a99c9ec6c7e0e1b5d1b1a744e` | 2026-12-05 |

The model artifact contains all 35 exact PCM files, the pinned metamodel, and
the independent structural manifest. The solver artifact contains the raw 30
records, capability-source audit, historical target lock, build/test logs,
versions, and test reports. The acceptance artifact contains the final manifest
and audit resource measurement.

## Interpretation and next milestone

M9B removes one integration uncertainty: on these explicit encodings, the
pinned analyzer reproduces the intended software-failure, fallback,
conditional, communication, redundant-path, and common-domain formulas across
their tested boundaries. These controls are intentionally small so that the
expected answers are external to the solver; they are not a reduced competitor
substituted for either live application.

The remaining mapping work is material. M9C must provide the mandatory
telemetry/operation-to-PCM correspondence table and one minimal operation model
for each application. It must preserve observed ambiguity, distinguish known
configuration from manual behavioral assumptions, map success and timeout
semantics explicitly, and mark unsupported replication or communication cases
rather than silently simplifying them. Only after that gate may an aligned
debugging comparison be constructed.
