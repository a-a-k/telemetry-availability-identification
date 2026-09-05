# M6: versioned live-ingestion contract and benchmark harness

## Outcome

M6 is complete as an integration milestone. The repository now has a versioned
telemetry-bundle contract, strict Jaeger and OTLP JSON adapters, normalized audit
tables, and a remote harness that verifies two exact public benchmark revisions.
The final GitHub Actions run passed for both profiles and for the aggregate job.

This result is deliberately narrower than live validation. The records ingested
in M6 are small hand-authored contract fixtures. They demonstrate that required
evidence can be represented and that failures without exported traces survive
normalization; they do not measure either application and do not support an
availability-accuracy or placement claim.

## Frozen implementation and evidence

- implementation commit: `67471f5e1390d7c58e4c6f728cd4cc5015f76cd2`;
- platform-stable fixture-digest commit and tested revision:
  `8066de50c6f848d2c90acb4433d5c53896603766`;
- CI run: [33966163833](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33966163833), successful on Python 3.11 and 3.13;
- M6 run: [33966165064](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33966165064), successful, attempt 1;
- aggregate artifact: `m6-aggregate-33966165064`, artifact id
  `9969493325`, 1,384 compressed bytes, retained through 2026-10-05;
- profile artifacts: `m6-deathstarbench_social_network-33966165064`
  (id `9969487524`, 6,917 bytes) and
  `m6-opentelemetry_demo-33966165064` (id `9969488337`, 6,870 bytes).

The aggregate was produced on CPython 3.13.15 on the GitHub-hosted Linux runner
with NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2. Its manifest records a clean
worktree and the expected GitHub SHA.

## What was implemented

The `taid.live_bundle/v1` manifest requires digests and exactly two disjoint,
seed-separated periods. Its source tables keep the following evidence distinct:

- the external-client census, including timeouts and absent trace ids;
- Jaeger or OTLP spans with explicit parent graphs;
- versioned instance-to-service/domain deployment intervals;
- liveness, readiness, and restart signals without relabelling one as another;
- per-attempt mesh evidence with logical-call ids;
- intended, applied, verified, and confirmed fault-injection records;
- manual operation semantics, accepted outcomes, effects, and branch classes.

Ingestion rejects digest/path/identity errors, malformed trace identifiers,
cycles or missing parents, ambiguous deployment ownership, records outside their
periods, unknown mesh endpoints or injection scopes, and operation roots that do
not agree with the manual specification. Span identity is correctly scoped by
trace rather than assumed globally unique.

The benchmark harness adds an independent upstream check. It verifies repository
origin and exact `HEAD`, declared paths, Compose services, and operation-specific
endpoint/handler markers before running the corresponding adapter twice. It then
requires identical canonical fingerprints and emits normalized CSV tables plus a
machine-readable audit.

## Remote integration result

The remote jobs checked the following frozen evidence:

| Profile | Exact upstream commit | Adapter | Paths / services / operations |
|---|---|---|---|
| DeathStarBench Social Network | `6ecb09706140f8730b5385c08f1386c654c3c526` | Jaeger JSON v1 | 4 / 4 / 3 |
| OpenTelemetry Demo | `8c47d47c9ac27710d2b2a153bcd53e483bffe66d` | OTLP JSON v1 | 3 / 4 / 3 |

Both observed checkout commits and origins equalled the frozen profiles. All 11
aggregate quality counters were zero: there were no missing/duplicate profiles,
repository or commit mismatches, missing paths/services/operation markers,
contract failures, nondeterministic re-ingestions, or losses of the deliberately
untraced failures.

Each contract fixture produced 8 external requests, 6 traced requests, 12 spans,
4 deployments, 16 health records, 8 mesh attempts, and 2 confirmed injection
records. In each case, the other 2 requests were failed timeouts with no exported
trace. Thus root-trace coverage was intentionally 0.75, while both untraced
external failures remained in the normalized request census.

The fixtures also deliberately retain one unknown health observation and four
gaps beyond the 30-second freshness threshold per profile. The maximum gap is
3,590 seconds because calibration and test are separated by 50 minutes. These
are reported telemetry properties rather than silently imputed values or build
failures. The DeathStarBench specification contains 5 manual required effects;
the OTel Demo specification contains 4; both contain 6 branch rules.

## Interpretation

M6 removes an important validity gap: the statistical code is no longer fed by
an unspecified, trace-only preprocessing step. A missing server trace can now be
distinguished from an absent external request, health semantics remain explicit,
and deployment and injection provenance are auditable. Pinning two independently
maintained systems and checking their actual workload sources makes the harness
less benchmark-specific than a single synthetic adapter.

The strongest justified conclusion is only that the frozen interfaces and
integrity checks work end to end. The 0.75 trace coverage is constructed, not
observed. Marker presence is provenance evidence, not proof that a runtime
request exercised the intended path. Manually declared effects and branch
semantics remain analyst inputs. The adapters implement the frozen JSON shapes,
not every vendor extension or streaming collector protocol. Actual workload,
fault, transition, and placement behavior must therefore be measured in M7.

## Completion checks

- 55 local unit tests passed; only bounded fixture ingestion was run locally.
- Both trace formats normalized on their matching profiles.
- Re-ingestion fingerprints were stable for both profiles.
- External failures without spans were preserved and counted.
- Upstream repositories, commits, paths, services, and workload markers matched.
- Aggregate integrity and contract quality counters were all zero.
- No fixture statistic is labelled as live-system evidence.
