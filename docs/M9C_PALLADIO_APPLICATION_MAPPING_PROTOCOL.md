# M9C: Palladio application-mapping protocol

Status: frozen before the first remote Palladio execution; completed with
accepted evidence recorded in `milestones/M9C_PALLADIO_APPLICATION_MAPPING.md`.

## Purpose and boundary

M9C constructs a source-grounded correspondence table and one minimal PCM
operation template for each live application. Each template is instantiated for
the two M7 logical placements. This is the required bridge between the
mechanism controls in M9B and the later debugging comparison on aligned M7
inputs.

M9C is not an accuracy comparison. It consumes no M7 predictions, scores, test
outcomes, or fitted parameters. Its nontrivial numeric inputs are synthetic
structural witnesses declared below. Passing M9C means that the recorded
operation abstractions have the intended PCM structure and solve to their
independently derived witness probabilities. It does not mean that Palladio
predicts either application accurately.

The M7 position remains unchanged: the published calculations establish no
predictive gain and disagree with observations, while the causes are not yet
diagnosed well enough for an overall success/failure verdict.

## Selection without result tuning

The selected operations are exactly the two routing probes frozen before M7B:

- DeathStarBench Social Network: `read_user_timeline`, targeting the replicated
  `user-timeline-service` on port 9090;
- OpenTelemetry Demo: `browse_product`, targeting the replicated
  `product-catalog` on port 3550.

They were selected because M7B used them to verify traffic through both named
backends, not because of any Palladio output or favorable M7 accuracy. Both
placements, `colocated` and `split`, are generated for both operations.

## Evidence boundary

The evidence job must byte-verify:

- accepted M8B run `34017401101`, artifact `9984348911`, including its artifact
  digest and the three topology tables used here;
- the M6/M7 operation, deployment, semantic-response, and HAProxy contracts;
- four pinned DeathStarBench source files at commit
  `6ecb09706140f8730b5385c08f1386c654c3c526`;
- six pinned OpenTelemetry Demo source files at commit
  `8c47d47c9ac27710d2b2a153bcd53e483bffe66d`;
- the accepted M9A and M9B configuration locks.

The source audit checks content markers as well as byte counts and SHA-256
digests. The generated correspondence table retains provenance classes for
observed evidence, frozen configuration, pinned source, manual equivalence,
synthetic witness values, unsupported mappings, and unidentified quantities.

M8B supplies two distinct facts that must not be conflated. Under N and ND,
all 40 full-view rows per selected operation are confirmed, every successful
trace contains the target, and both replicas have assignments. Under NC and
NCD, successful target-absent traces occur: 7,708 for DeathStarBench and 15,586
for OTel Demo across the retained branch table. Pinned source still shows a
mandatory synchronous target call for the fixed driver inputs. M9C therefore
uses the source-grounded mandatory call while preserving the target-absent
trace phenomenon as unresolved telemetry/operation evidence; it does not
reinterpret those traces as proof of an optional path.

## Mandatory correspondence table

| Element | DeathStarBench `read_user_timeline` | OTel Demo `browse_product` | PCM treatment and limitation |
|---|---|---|---|
| Success and timeout | HTTP 2xx plus the frozen timeline JSON shape; timeout or missing response fails | HTTP 2xx plus product id `OLJCESPC7Z`; timeout or missing response fails | Scenario success includes an operation-level residual calibrated to the same semantic predicate later; PCM does not inspect response bodies |
| Operation and path | nginx synchronously calls UserTimelineService; Redis/Mongo branch and PostStorage call occur inside target | frontend synchronously calls ProductCatalog.GetProduct; fixed default USD avoids the optional Currency call; flag and PostgreSQL work occur inside target | Required entry-to-target call is explicit; internal dependencies are collapsed into the semantic residual and are not presented as separately recovered components |
| Replication | Two TCP HAProxy backends | Two h2 HAProxy backends | Two explicit PCM assemblies/allocations and failure handling implement the stationary Boolean-OR success condition; this is not literal round-robin execution or a native PCM replication claim |
| Individual failure | Per-replica Docker pause with sampled container/backend state | Same | Required physical resource on each explicit path; only stationary availability is represented |
| Communication failure | Per-replica Docker-network disconnection over intervals | Same | Separate path links; `q_pcm = 1 - sqrt(c_path)` preserves one-call marginal success under the analyzer's two equal independent transfers; interval correlation is unsupported |
| Common domain | One pause factor gates both colocated replicas; split uses one factor per logical domain | Same | Colocated has one shared gating resource. For split, independent domain and replica availability are composed into each path resource |
| Parameters | No empirical parameter is used in M9C | No empirical parameter is used in M9C | Synthetic witness only. `MTTF=A`, `MTTR=1-A` are dimensionless ratio coordinates, not recovered durations |
| Placement | Logical injected failure-domain membership; containers still share a CI host and proxy is outside injected domains | Same | Dependence changes between one shared gate and two independent path factors; no physical-host isolation claim |

The complete per-application wording and provenance are frozen in
`configs/m9c_palladio_application_mapping.json` and emitted as a 16-row CSV.

## Stationary abstraction

For a stable request, let `r` be semantic residual success, `e_a,e_b`
individual replica availability, `c_a,c_b` communication-path call success,
and `g` domain availability. The predeclared route models are:

- colocated: `g * [e_a*c_a + (1-e_a*c_a)*e_b*c_b]`;
- split, with independent homogeneous domains: `g*e_a*c_a +
  (1-g*e_a*c_a)*g*e_b*c_b`;
- operation success: `r * route_success`.

HAProxy is configured with round robin, 500 ms checks, `fall 1`, and `rise 1`.
For stable binary backend states, its request-success condition is that at least
one complete target path is available. PCM's explicit primary/fallback action
is used only as an availability-equivalent encoding of that Boolean OR. The
model does not claim HAProxy retries a request after an arbitrary failure.
Detection/recovery transients, connection reuse, literal round-robin order, and
temporally correlated disconnects remain unsupported.

The analyzer applies a communication-link failure probability to both request
and response transfer. Consequently a desired path-call success `c` is encoded
as `q=1-sqrt(c)`. This preserves the one-request marginal under the equal,
independent two-transfer assumption; it does not reproduce the temporal process
that generated M7 network outages.

Palladio enumerates stationary physical states using MTTF/MTTR ratios. M9C uses
`MTTF=A`, `MTTR=1-A` solely as dimensionless coordinates giving availability
`A`. No duration estimate is claimed. A later aligned comparison may use this
ratio parameterization only because the pinned analyzer's result depends on the
ratio here; any claim about failure or repair times requires a separate
censoring-aware estimator.

## Structural witness and independent oracle

The same deliberately non-empirical witness is used for both applications so
that no application-specific fit can enter M9C:

- `r=0.97`, `g=0.90`, `e_a=0.80`, `e_b=0.70`;
- `c_a=0.90`, `c_b=0.85`;
- `q_a=1-sqrt(0.90)`, `q_b=1-sqrt(0.85)`.

The independent expected operation probabilities are:

- colocated: `0.7740018`, with eight physical states;
- split: `0.81140112`, with four physical states after composing each
  independent domain factor into its path resource.

There are four model instances and two technical repetitions, hence eight raw
solver records. The Java harness records no expected value.

## Acceptance rules

M9C passes only if:

1. the accepted M8B identity, topology files, study contracts, and pinned
   upstream sources all pass byte and marker audits;
2. the correspondence CSV contains all eight mandatory elements for both
   applications and retains every provenance/status field;
3. each generated PCM instance has one semantic residual action, two explicit
   target components, distinct assemblies, allocations and links, one
   hardware and one network failure type handled by the alternate path, and
   the correct shared/split resource ratios;
4. no unsupported automatic allocation replication is used;
5. all eight solver records match the predeclared probabilities within
   `1e-12`, conserve success/failure and physical-state mass, enumerate every
   physical state, and repeat exactly within tolerance;
6. the evidence, models, raw output, logs, resource measurements, and final
   acceptance manifest are retained as workflow artifacts.

A failure is first an integration, XMI, or semantic-mapping diagnostic. It is
not evidence that Palladio or the telemetry-driven method is generally wrong.
After a passed M9C, the next admissible step is the exploratory aligned-input
comparison on preserved M7 calibration material.

## Execution boundary

The official analyzer 5.2.2 commit, PCM 5.2.2 commit, release-date target lock,
Temurin Java 17, exact physical-state enumeration, and two-run harness are
inherited from accepted M9A/M9B. Full generation evidence and all Palladio
solving run in GitHub Actions. Local execution is limited to configuration,
unit, XML-generation, and structural-audit smokes. All three workflow jobs use
`timeout-minutes: 360`.
