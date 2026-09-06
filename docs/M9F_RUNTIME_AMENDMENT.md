# M9F runtime amendment after the superseded launcher attempt

Status: frozen before the first recovery execution.

## Triggering observation

The first remote attempt, GitHub Actions run `34040388551` at commit
`e1600a63271e9b2c80b73779aa7714685a1c4c0d`, passed the complete provenance
job. In the headless job, the first direct invocation began at
`2026-09-06T14:50:11Z` and had not returned when the run was cancelled at
`2026-09-06T15:10:49Z`, 1,238 seconds later. Runner cleanup reported one live
`java` process below `timeout`; the loop therefore had not advanced beyond its
first invocation. No probe artifact or semantic-decision artifact was uploaded,
so no generated PCM result was inspected before this amendment.

For context only, the authors' historical containerized PMX job 1984 in public
pipeline 1120 reports a duration of 22.158142 seconds. That historical duration
does not prove how the standalone JAR should behave on GitHub, but makes a
multi-hour silent wait a poor diagnostic design.

Run `34040388551` is retained as a superseded runtime attempt. Its cancellation
is not classified as a scientific failure of PMX or Palladio.

## Frozen recovery

The recovery changes only launcher observability and bounded execution:

- every PMX invocation has a 900-second internal watchdog;
- a heartbeat is retained every 30 seconds with elapsed time, stdout bytes,
  result-file count, and result bytes;
- start, finish, elapsed time, and exit status are retained for every run;
- the JVM receives
  `-DLog4jContextSelector=org.apache.logging.log4j.core.selector.BasicContextSelector`,
  the logging selector specified by the `start` script embedded in the same
  byte-pinned JAR;
- all four predeclared runs continue even when one invocation times out;
- all three GitHub jobs retain `timeout-minutes: 360`.

The JAR, Java major version, author trace, one-error control, options, two
conditions, two repeats, required PCM files, semantic dimensions, failure
probability oracle, and decision rules are unchanged. The amendment performs no
accuracy scoring, reads no M7 evaluator outcome, and authorizes no new live
collection.

The first complete run under this amendment is the accepted M9F candidate. A
watchdog exit remains evidence about this pinned launcher route only; it cannot
be generalized to every PMX artifact or to the Palladio ecosystem, and it does
not demote PMX's scientific priority.
