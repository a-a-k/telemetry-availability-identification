# M9H: exact source-declared PMX entrypoint

Status: frozen before the first M9H remote invocation.

## Question

M9G recovered a complete historical PMX output and extracted two independent
declarations from the same byte-pinned public JAR:

- `OSGI-INF/org.palladiosimulator.pmx.core.Main.xml` declares
  `osgi.command.scope=main` and `osgi.command.function=main`;
- the embedded `Main.java` declares the same scope and function on the
  component whose public method is `main(String[] args)`.

M9H asks whether the exact resulting Gogo command
`main:main -of Options.txt` executes the authors' unchanged demonstration and,
if so, whether it reproduces the one-error-in-ten failure mechanism already
frozen in M9F. This is a prospective source-derived test, not a fifth candidate
added to M9G after seeing its screens.

The question is still technical and diagnostic. M9H performs no application
accuracy scoring, reads no M7 evidence or evaluator outcome, changes no
estimator, and authorizes no collection. Failure would characterize the public
JAR and tested headless environment, not PMX, Retriever, or Palladio generally.
Application-adapter cost remains the independent M9G result and does not reduce
PMX's scientific priority.

## Frozen evidence and command

The accepted anchors are:

- M9G run `34049195927` at
  `a69881a3fb6ab48b3ee0980d9c1470d260de3e5b` and all three artifact IDs,
  sizes, and GitHub SHA-256 digests;
- the M9G recovery, launcher, application, and decision manifest byte hashes;
- the public demonstration at commit
  `9b8d4c5707751eeabe31f7e7d6b7de0acf0c45a2`;
- `main.jar`, 65,729,095 bytes, SHA-256
  `befe481ab6f9db9d7b283a2ca810b9ec11a368e4ddc8cb6c669b73590d431013`;
- the authors' unchanged `Options.txt` and `jaegercustomers.json` input;
- the M9F one-error-in-ten trace transformation and expected probability 0.1;
- the historical output semantic signature
  `4e2f00daefd89ce4ccde30074cbf09deb65a2d44736d6ccf0cacace8f004f695`.

There is one execution command and no ordered search:

`main:main -of Options.txt`

The process starts through the JAR's embedded launcher on Temurin 11 with the
same Log4j context selector. Input is held for a fixed 20-second startup
stabilization before the source-declared command is written. The second and
final stdin line is the valid Gogo form `exit 0`, replacing M9G's invalid bare
`exit`. This line is only a bounded fallback: successful `Main.main` itself
calls `System.exit(0)` after the writer. Each process has an internal
180-second watchdog. No alternative scope, function, delay, or invocation can
be chosen from the result.

## Execution and acceptance

The exact command is screened once on the published trace. A screen is output
eligible only if all five core PCM file types are present and parseable, the
full reader/transformer/writer log sequence is present without a major error,
and the identifier-insensitive semantic signature equals the historical job.
Command registration, exit code, timeout, stdout, resource use, and result
inventory are reported separately.

Only an output-eligible screen unlocks four confirmation runs:

- unchanged published input, repeats 1 and 2;
- frozen single-error control, repeats 1 and 2.

Both original confirmations must remain output eligible and semantically
repeat-consistent. Both control confirmations must contain an internal software
failure occurrence and a nonzero repository failure probability equal to 0.1
within absolute tolerance `1e-12`. Exit zero is required for a clean launcher
classification but is not substituted for valid model output. The mechanism
control verifies one known transformation; it is not an accuracy test.

The decision states independent booleans for source-contract agreement,
command registration, original-output recovery, clean termination, repeat
consistency, and failure-mechanism reproduction. If the route and mechanism
pass, M9I may implement a learner-only adapter on the four nonrepresentative raw
samples before considering any new data. If output passes but the mechanism
does not, the failure mapping is diagnosed first. If the exact source command
is unavailable or produces no valid output, source/container reconstruction
continues and the existing manual PCM route remains a separately labelled
parallel contingency rather than being credited to PMX.

## Anti-straw-man and information boundaries

M9H is tied directly to executable evidence inside the tested JAR, not to a
generic baseline invented for comparison. It uses the authors' own trace,
options, plugins, Java major version, and historical semantic output as its
oracle. The startup delay and valid exit form remove two launcher artifacts
observed in M9G. The command is frozen before invocation and cannot be replaced
by a more favorable command after the run.

Conversely, even a successful M9H would establish only launcher and synthetic
failure-transformer reproducibility. It would not supply raw input for 160
historical campaigns, establish application instrumentation equivalence,
complete deployment/lifecycle/communication mapping, or demonstrate predictive
gain. Those remain separately measured questions.

## Workflow and reporting

The remote workflow has exactly three jobs:

1. audit the accepted M9G artifacts and source-to-command derivation;
2. run the exact entrypoint screen and conditional confirmations;
3. apply the frozen diagnostic decision.

All three jobs use `timeout-minutes: 360`. The 65 MB binary download and every
PMX invocation run only in GitHub Actions. Local activity is limited to config
validation, unit tests, and tiny synthetic output-classification smokes. A
milestone report must include every run, artifact identity, raw command outcome,
model/log checks, failure probability, resource use, limitation, and next
decision.

The M7 position remains unchanged: published calculations show no established
gain and discrepancies with observations; their causes are not sufficiently
resolved to declare the overall approach successful or failed.
