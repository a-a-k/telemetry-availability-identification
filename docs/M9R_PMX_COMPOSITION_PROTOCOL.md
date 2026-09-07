# M9R: retained PMX failure references and inclusive-error composition

Status: frozen before any M9R solver output. This bounded control uses only the
two retained M9Q `nested_errors` artificial PCM models. It invokes PMX zero
times, acquires no live data, reads no evaluator and changes no M9P method.
All full model loading and solving occur in GitHub Actions with 360-minute jobs.

Before this freeze, static inspection of both retained repositories found
references to two software failure types whose objects are absent from the
serialized repository. The exact embedded `TransformerSystemToPCMFailureDependencies`
creates a new type and sets the reference without adding that type to the
repository's containment list. M9Q's resolved operation-frequency checks did
not check this reference class and do not establish loader validity. This is a
new, explicitly identified correspondence boundary, not a change to M9Q's gate.

## Fixed eight-model census

For each retained extraction repetition, preserve the original five core files
and create exactly four variants:

1. **Raw:** original files byte-for-byte, including dangling failure-type links.
   Attempt standard Palladio loading and record either a result or failure.
   A numeric answer cannot qualify the known incomplete failure references.
2. **Types contained:** add only the two missing software failure-type objects
   under the repository, retaining the exact referenced IDs and explicit reverse
   links. Add the required XML namespace. Keep operations, probabilities, calls,
   workload, resources, timings and allocation unchanged. This is a disclosed
   serialization bridge, not an unmodified native PMX output.
3. **Conditional-local sensitivity:** start from variant 2 and change only the
   root's inclusive error probability from `0.2` to `1/9`. This is the explicitly
   assumed conditional-local reinterpretation below, not a repair justified by
   seeing a solver answer or an estimator established for real applications.
4. **Zero-error control:** start from variant 2 and change the two nonzero
   software probabilities to zero. All call/workload/resource structure remains.

The raw graph contains one root entry, one call to a child, one call to a
successful sibling, and fixed one-iteration loops. Frozen expected software
successes for variants 2–4 are `0.72`, `0.8`, and `1.0`, respectively, conditional
on the generated resources being available. No hardware failure parameters are
added or adjusted: unsupported resource defaults or model validation prevent
qualification and must be reported. The existing audited analyzer configuration
is retained, including complete physical-state evaluation; it does not impose
the expected answers. No solver expected value is embedded in the Java harness.

Use the accepted Palladio analyzer commit
`a694e570afb705dc9e0470dc321e77b7219dcea4`, M9A release-date target lock,
Temurin 17, and the standard M9D loading/solving route. Attempt all eight models
in deterministic order in two passes, preserving per-case exceptions and any
partial output. There is no warmup or runtime-superiority claim. The downstream
audit retains missing models, invalid physical results and oracle mismatches;
the 16 expected records are a complete technical census, not independent
statistical replications. Probability tolerance is `1e-12`.

## Why these probabilities test a semantic boundary

Treat the ten fixed synthetic trace patterns as a uniform finite reference law.
The root is marked erroneous in two patterns, the child in one of those two,
and the sibling in none. Thus the reference root-error frequency is `0.2`,
the child-error frequency `0.1`, and the observed root success is `0.8`.
The completed native SEFF attaches both inclusive marginal frequencies as
internal failure probabilities along the same serial execution. Under ordinary
independent local-action composition, success is `0.8 × 0.9 = 0.72`.

If child failure always propagates and local root failure is independent of
child failure, the required local-root probability is
`(0.2-0.1)/(1-0.1)=1/9`, yielding `(1-1/9)×0.9=0.8`. The conditional-local
variant measures this correspondence only. The ten artificial patterns do not
observe the counterfactual local root state when its child fails and cannot
establish that independence assumption. The native operation flags can be
counted correctly while their independent composition answers a different
question. This distinction is the scientific purpose of the control.

No variant is a held-out availability forecast or a full benchmark application
mapping. Native span errors, request semantic outcomes, traffic denominators,
retries and omitted requests remain separate. A failure here triggers a scoped
report of the unresolved bridge; it does not authorize an open-ended sequence
of loader, metadata or model rewrites. The frozen M9P confirmation continues
independently to its final evaluation and retention audit.

## Pre-solver archive-path amendment

Run 34130882723 at `044c1e905f3ddefe6fbf2f12d1da7880ca6cc7ab` verified the
two complete archives and the artificial contract, then failed before writing
the first model because the extraction artifact itself contains a `probe/`
directory. The staging reader omitted that archive-internal level. No Palladio
build or solve ran and no probabilities were observed. The original run and
code remain preserved; the next contract retains its failed-job log. The
correction adds the one explicit path level and an artificial archived-layout
regression. The eight variants, edits, software oracles and solver configuration
are unchanged.
