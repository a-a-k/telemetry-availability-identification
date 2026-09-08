# V3: ordinary execution evidence for all ten operations

[Run 34241300741](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34241300741)
completed all three application audits at commit
`dc9256875b943df509469ffc50cb0fc8caf09b67`. Frozen configuration SHA256:
`4d791d650092c6a8267a5ab096382aed92d10c7fbd4ff74414f69aa533f26de6`.
All 4,080 ordinary calibration attempts have native traces and explained external
boundary parents. This establishes the census, not completeness of every native
call or adequacy of an estimator. Each consumer read exactly six ordinary files
with zero blocked access; no evaluator/controller files were supplied.

| Application / operation | Attempts | Failures / timeouts | External roots per attempt | Target SERVER spans |
| --- | --- | --- | --- | --- |
| DeathStar compose_post | 80 | 0 / 0 | 1 | Native kind is unlabelled; SERVER count is not call count |
| DeathStar read_home_timeline | 80 | 0 / 0 | 1 | Native kind is unlabelled; SERVER count is not call count |
| DeathStar read_user_timeline | 80 | 0 / 0 | 1 | Native kind is unlabelled; SERVER count is not call count |
| OTel browse_product | 80 | 0 / 0 | 1 | 1 per attempt |
| OTel add_to_cart | 80 | 0 / 0 | 2 | 1 per attempt |
| OTel checkout | 80 | 0 / 0 | 3 | 3 per attempt |
| Petclinic list_owners | 900 | 0 / 0 | 1 | No Visits call in observed graph |
| Petclinic owner_details_with_visits | 900 | 173 / 25 | 1 | 752 attempts with one, 148 without |
| Petclinic create_visit | 900 | 159 / 21 | 1 | 764 attempts with one, 136 without |
| Petclinic list_vets | 900 | 0 / 0 | 1 | No Visits call in observed graph |

Every one of the **46 Petclinic timeouts has native telemetry without an error
flag**, and has a span ending after the external 2-second deadline. All 286
other failures have a native error flag. A no-error interpretation would miss
these timeout outcomes. Timing uses aligned process clocks; the report does not
infer exact database commit time or a new causal mechanism. All target Visits
SERVER spans have no error flag, including late work; caller-level failures and
the external deadline therefore cannot be replaced by target span error counts.

OTel target SERVER spans lack `service.instance.id`, but retain observed
`study.replica` labels: browse a/b = 36/44, cart = 42/38, checkout = 122/118.
Missing standard instance ID is not missing all replica information. These are
call marginals: checkout's within-attempt joint routing law is not established
by them. Three catalog calls must not be collapsed to one call or treated as
independent merely because marginals are near one half.

DeathStar's 3,560 spans all have an empty native kind. Nevertheless, parent links
give one cross-service user-timeline entry per compose and per user-timeline
read. The home-timeline read has no such dependency in its observed graph.
Any use of these entries as execution calls requires an explicit source-grounded
adapter; assigning a fabricated native SERVER kind would misstate the input.

The existing full graph inventory remains visible, including background
dependencies, multiple OTel roots and DB CLIENT relations. Native absence is not
imputed to a healthy replica or successful dependency. Normal DeathStar/OTel
technical inputs cannot establish failed-route completeness or fault behavior.
Petclinic's late spans do not show which backend was selected for requests that
failed before reaching a SERVER span.

The normalized adapter records error Booleans, not the original distinction
between OTLP UNSET and explicit OK. This limits retrospective reconstruction.
The current official specification also distinguishes those statuses; HTTP
conventions can leave SERVER status unset for 4xx responses. These sources
describe the standards, not verified conformance of every historical library:
[Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/#set-status),
[HTTP span status](https://opentelemetry.io/docs/specs/semconv/http/http-spans/#status).

Three exact compact ZIPs total **18,507 bytes**; all 18 members, source/run/head
metadata and process cost records are retained in
[verified archives](../evidence/v3-execution-observation-audit-34241300741/verified-archives.json).
Full native/ordinary archives remain remote. No model fits, PMX invocations,
new independent observations or main campaigns occurred. The four artificial
controls and both Python versions' CI passed at the frozen source commit.

Consequence: a refinement must preserve joint call requirements, distinguish
deadline completion from error flags, and retain unresolved routing/call
observations. Its semantic and identification assumptions must be stated
before the main experiment; this census does not automatically choose G*.
