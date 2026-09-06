# M9G: PMX launcher recovery and application-information delta

Status: complete. The accepted diagnostic run is
[34049195927](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34049195927)
at commit `a69881a3fb6ab48b3ee0980d9c1470d260de3e5b`.

## Result in one paragraph

M9G recovered and byte-audited the authors' historical successful PMX output,
but did not reproduce output through any of its four frozen guessed Gogo
commands. All four screens ended at their 120-second watchdog after reporting
`CommandNotFoundException` and wrote no model. The same binary's embedded
Declarative Services descriptor, recovered before interpretation, identifies
the actual registered scope/function pair as `main:main`; that exact
source-declared command was not one of the frozen M9G candidates and is
therefore the first M9H test, rather than a post-result addition to M9G. On the
separate application track, all 160 qualified learner bundles were audited:
none retains a raw trace stream, although every bundle retains derived trace,
topology, deployment, health/network, and external-success information. All
four raw schema samples can be filtered to learner periods without evaluator
data, but none exposes the Spring-WebMVC instrumentation marker assumed by the
audited PMX failure transformer; the OpenTelemetry Demo samples additionally
need an OTLP-to-reader adapter. These are measured reproducibility and
application costs, not evidence against PMX/Palladio and not an accuracy result.

## What was implemented

The frozen protocol is `docs/M9G_PMX_RECOVERY_AND_APPLICATION_DELTA_PROTOCOL.md`
and its machine-readable contract is `configs/m9g_pmx_recovery.json`. The
implementation in `telemetry_availability.pmx_recovery` provides five audited
operations:

1. validate fixed evidence identities, repository locks, scientific
   guardrails, candidate order, and runtime limits;
2. verify the historical ZIP and all fourteen members, summarize its five PCM
   models without random XMI identifiers, and extract launcher/source evidence
   from the byte-pinned JAR;
3. classify isolated Gogo screens and conditionally confirm the first eligible
   candidate on the authors' trace and the one-error-in-ten mechanism control;
4. inspect all 160 learner directories plus the four separately labelled raw
   schema samples without reading an evaluator file or request outcome; and
5. publish a joint diagnostic decision whose branches do not use accuracy.

The workflow has exactly three jobs and all three use `timeout-minutes: 360`.
Full downloads, four PMX invocations, and full evidence scans ran only in
GitHub Actions. Local work comprised configuration validation, unit/schema
smokes, and the full non-experimental test suite.

## Runs and correction history

| Run | Commit | Outcome | Role |
|---|---|---|---|
| [34049004382](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34049004382) | `f8de9d3a0162c018e0af7f035d81b072f8a124a7` | superseded | Launcher branch completed, but the application writer stopped after two Jaeger rows because the OTLP row had the additional `malformed_jsonl_records` field. Partial artifacts and the traceback remain public. |
| [34049195927](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34049195927) | `a69881a3fb6ab48b3ee0980d9c1470d260de3e5b` | accepted; all three jobs successful | The one-line schema normalization added a zero-valued field to Jaeger rows. Evidence identities, launcher candidates, decision rules, and scientific boundaries did not change. |

The accepted application job took 33 seconds, including an 11.07-second full
audit with peak resident memory 388,052 KiB. The launcher job took 8 minutes 33
seconds; 480 seconds were the four fixed internal watchdogs. The final decision
job took 24 seconds. The workflow elapsed 13 minutes 56 seconds including its
wait behind the superseded run.

## Accepted artifacts

| Artifact | ID | Stored bytes | GitHub SHA-256 digest |
|---|---:|---:|---|
| `m9g-pmx-recovery-34049195927` | `9994208636` | 239,138 | `4c593fc596173f0e4468adbfe730980eacf7039e028cfd783ecb3c6ee09f9ca8` |
| `m9g-application-delta-34049195927` | `9994097055` | 4,837 | `b6f5c299192d6e6d6534151cbd05b9cf55b2a20114e7b87be502d8cf9b3a1b5f` |
| `m9g-joint-decision-34049195927` | `9994214714` | 2,429 | `86ff94be118f8c92a61d694a8064f7d57096e244ab194c4c6a58113723df9c33` |

All three were retained for 90 days, through 5 December 2026. The recovery
artifact includes raw stdin, stdout, timing, resource use, and empty result
directories for every screen, in addition to the extracted static evidence.

## Track A: historical output and launcher

The public job-1984 ZIP matched its frozen size (13,676 bytes), SHA-256
`4ae91b639ceeb8ec7c1403bfeabb2b0b5af3a3bf8a6676d6dd94a3662ad8bdb0`,
fourteen-member inventory, and every member hash. Its five core PCM models are
XML-parseable, its full reader-to-writer log sequence is present, and its
identifier-insensitive semantic signature is
`4e2f00daefd89ce4ccde30074cbf09deb65a2d44736d6ccf0cacace8f004f695`.
The models contain five SEFFs, one external call, two allocation contexts, and
thirty entry-level system calls. The original trace produced no nonzero failure
probability, as expected; this historical artifact is not a failure-mechanism
control.

The 65,729,095-byte JAR matched SHA-256
`befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`.
Its outer launcher is `aQute.launcher.pre.EmbeddedLauncher`; its embedded
`start` script invokes that class with the documented Log4j selector. The core
bundle contains 303 entries. Both `Main.java` and
`OSGI-INF/org.palladiosimulator.pmx.core.Main.xml` declare
`osgi.command.scope=main` and `osgi.command.function=main`. The method consumes
`-of/--options-file` and calls `System.exit(0)` after writing.

| Frozen screen | Exit | Seconds | Stdout bytes | Result/model files | Observed command result |
|---|---:|---:|---:|---:|---|
| `pmx -of Options.txt` | 124 | 120 | 165 | 0 / 0 | command `pmx` not found |
| `pmx:execute -of Options.txt` | 124 | 120 | 173 | 0 / 0 | command `pmx:execute` not found |
| `pmx:main -of Options.txt` | 124 | 120 | 170 | 0 / 0 | command `pmx:main` not found |
| `pmx:pmx -of Options.txt` | 124 | 120 | 169 | 0 / 0 | command `pmx:pmx` not found |

Each stdin then supplied bare `exit`; Gogo reported that its available exit
function requires an integer, printed `gosh: stopping shell`, and remained
alive until the watchdog. Thus the timing is not evidence that a transformation
started: all four logs have zero transformation markers. No candidate was
eligible, so the preregistered confirmations and mechanism control were
correctly not run.

This negative is narrower than the machine-readable status label
`pmx_launcher_recovery_not_reproduced`: it covers exactly four guessed commands.
It does not cover the now-observed source-declared `main:main` command. Adding
that command after seeing the static extraction would make it a different
test, so it is frozen prospectively as M9H. This separation prevents both
post-result fishing and a straw-man interpretation of M9G.

## Track B: application-information delta

The preserved M8A artifact identity, size, digest, and unexpired status all
matched. The audit found the complete expected matrix of 160 distinct learner
bundles (2 applications × 2 placements × 4 failure laws × 10 repetitions).

| Learner information | Bundles with field/support |
|---|---:|
| raw PMX-readable trace stream | 0 / 160 |
| derived trace ID, operation, service set, and span count | 160 / 160 |
| derived service topology | 160 / 160 |
| replica and domain declarations | 160 / 160 |
| lifecycle health and communication/network observations | 160 / 160 |
| external semantic-success observation | 160 / 160 |
| evaluator file opened | 0 / 160 |

The four raw samples were never treated as the accuracy population. Trace IDs
were selected solely from baseline and calibration rows in `trace-join.csv`;
the saved `request_success` column was not used. Each sample contained all
3,840 selected trace IDs and had zero selected test IDs or missing required
span fields.

| Application / placement | Native shape | Unique selected spans | Services | Direct `error=true` | OTLP error status | Spring-WebMVC marker |
|---|---|---:|---:|---:|---:|---:|
| DeathStarBench / colocated | Jaeger JSON | 54,142 | 12 | 190 | 0 | 0 |
| DeathStarBench / split | Jaeger JSON | 55,467 | 12 | 166 | 0 | 0 |
| OpenTelemetry Demo / colocated | OTLP JSONL | 106,346 | 11 | 1,334 | 110 | 0 |
| OpenTelemetry Demo / split | OTLP JSONL | 100,549 | 11 | 1,892 | 467 | 0 |

All four schemas are mechanically adaptable using learner-only trace IDs. The
two OTLP samples require an explicit envelope/field conversion. More
importantly, all four need a validated application-specific operation and error
mapping because a direct Spring-WebMVC marker is absent. Deployment,
replication, lifecycle/network observations, and external semantic success
remain separate learner inputs; span error is not silently equated with client
success.

## Decision and interpretation

The frozen joint status is
`historical_output_recovered_launcher_unresolved`. Its individual facts are:

- historical output recovered and semantically audited: true;
- output from the four M9G Gogo candidates recovered: false;
- clean launcher termination: false;
- one-error-in-ten failure mechanism reproduced: not tested because no
  candidate qualified;
- raw input directly present in all 160 learner bundles: false;
- four-sample learner-only schema adaptability: true;
- direct audited instrumentation semantics: false;
- additional deployment/lifecycle/communication mapping required: true.

M9H therefore tests the exact source-declared `main:main -of Options.txt` route
on the unchanged byte-pinned JAR, first on the authors' input and then on the
already frozen failure control if output qualifies. The manual PCM path remains
an explicitly labelled parallel contingency; it cannot be credited as PMX
automation. A future full-population collection may be proposed only under a
new preregistration because raw spans are absent from the historical 160
qualified bundles. M9G itself authorizes no collection and performs no
accuracy comparison.

The M7 position is unchanged: the published calculations establish no gain and
show prediction--observation discrepancies, while their causes remain too
incompletely resolved to declare the overall approach successful or failed.

## Verification

Before the accepted run, 164 local unit and bounded smoke tests passed. The
accepted workflow then validated the config independently in all three jobs.
To inspect the retained evidence, download the three artifact names above from
run 34049195927 and verify the GitHub-provided SHA-256 digests before reading
the manifests and CSV files.
