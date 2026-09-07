# M9R: retained PMX serialization and inclusive-error composition control

Status: complete as a bounded technical census; composition remains unresolved
through this native-model bridge. No valid reliability probability was produced.
The run preserves all 16 planned records and makes zero new PMX invocations.

The accepted execution is [34131147623](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34131147623)
at `421273a1fd6a514bbe55e8da50906d92b1b5cfc4`, from
2026-09-07T14:06:49Z to 14:12:47Z. The exact-head
[CI 34131147704](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34131147704)
passed. The config SHA-256 is
`9883e51108d2c873416ad35ffe5e5a98cea18a453c80c6e8a744e664d5313a8d`.
The [prospective protocol](../M9R_PMX_COMPOSITION_PROTOCOL.md) contains the
eight fixed models, hypotheses, software oracles and stopping boundary.

## Inputs and disclosed variants

Both source models are the two retained extractions of M9Q's artificial
`nested_errors` fixture. All ten reference patterns and their original contract
were checked: two root errors, one child error contained in those two, and no
sibling errors. They are artificial patterns, not held-out benchmark requests.

Static source and file inspection before M9R established two dangling software
failure-type references in each repository. The PMX transformer creates the
referenced objects without adding them to the repository containment list.
The serialized five-file model retains their IDs but not the objects. M9Q's
operation/error checks did not verify this reference class and cannot establish
that such a repository is ready for Palladio reliability analysis.

For each of the two source repetitions, M9R preserves the original five files
byte-for-byte and creates three explicitly modified variants:

- contain the two missing software failure types, retaining IDs and reverse
  links, without changing probabilities;
- additionally replace the root's inclusive probability `0.2` by `1/9` under
  the declared conditional-local interpretation;
- alternatively replace both nonzero software probabilities by zero.

Only `extracted.repository` changes in these variants. Resource, system,
allocation and usage files remain unchanged. Every one of the 40 model-file
hashes matches the published preparation contract. All eight models pass
through the same accepted M9D loading/solving route, with the pinned analyzer
`a694e570afb705dc9e0470dc321e77b7219dcea4`, Java 17 and the M9A historical
target-platform lock. The Java harness contains no expected success values.

## Full result census

Two passes were attempted for every model. The harness retains exceptions per
case and also records when the analyzer returns an object containing unusable
numeric fields. A successful Actions job means the diagnostic completed.

| Variant | Records | Observed result | Valid software-oracle passes |
|---|---:|---|---:|
| Raw native repositories | 4 | `NullPointerException` because `SoftwareInducedFailureType` is null | 0 |
| Types contained, original inclusive probabilities | 4 | Returned success 0, failure sum 0, physical mass 0; evaluated 0 of 1 states | 0 |
| Conditional-local sensitivity | 4 | Same invalid zero-mass result | 0 |
| Zero-error control | 4 | Same invalid zero-mass result | 0 |

Raw failures occur in `MarkovSoftwareInducedFailureType.createInternalFailureType`
and the failure-type collection path. Containment completion removes that
specific outer failure, but does not qualify the complete model bridge.

The retained log localizes the later failure to distribution/context handling:
it contains 96 `StringNotPMFException` occurrences from
`ManagedPMFParser.createFromString` / `ContextWrapper.readComputedContextsToHashMaps`,
followed by 12 null-PMF exceptions in `MarkovBuilder.initLoopMarkovChain`.
The latter are caught inside the analyzer's transformation path, which returns
the zero-mass result. The record therefore does **not** establish zero system
availability. It also does not identify hardware defaults as the cause: the
observed later exception concerns loop probability-mass-function handling.

The zero-error control reaches the same failure boundary, so the invalid result
cannot be attributed to the proposed inclusive-versus-local error distinction.
No PMF or loop rewrite, resource modification, gate change or new solver run was
added after seeing this outcome. The limited bridge result is retained as
unresolved, as specified by the protocol.

## What remains analytic, rather than measured

For the uniform ten-pattern reference law, the inclusive root success is `0.8`.
Treating inclusive root and child errors as independent local-action errors
would give serial success `(1-0.2)(1-0.1)=0.72`. Under guaranteed child-error
propagation and independent local root failure, the local root probability
would instead be `(0.2-0.1)/(1-0.1)=1/9`, yielding `0.8`.

These are the frozen analytical oracles, **not observed Palladio answers in
M9R**. The counterfactual local root state when its child fails is not observed,
so the ten patterns do not establish the independence assumption behind the
conditional-local variant. A correct count of inclusive operation errors does
not by itself supply a justified independent local-error parameterization.
M9R tested this connection but did not reach valid solver probabilities.

## Technical failure retained before the accepted execution

The first run [34130882723](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34130882723)
at `044c1e905f3ddefe6fbf2f12d1da7880ca6cc7ab` verified both exact archives
and the artificial contract, then failed before writing its first model. Its
reader omitted the extraction archive's internal `probe/` level. The corrected
path and an archived-layout regression were committed before any solver run.
No model variant, probability or oracle changed. No artifact was uploaded by
that failed run; its failed-job log is preserved in the accepted contract as
`prior-preparation-failure.log`, 13,113 bytes, SHA-256
`f1a2c148f7faff6924734ff2d754628b7aaccb6e846a56500bfdc2bfb017c5a5`.

## Cost, provenance and retained artifacts

Preparation, solver and census jobs took 24, 306 and 19 seconds respectively.
The build command took 178.39 seconds and peaked at 1,640,576 KiB RSS. The
Maven test/solve command took 91.28 seconds and peaked at 1,454,252 KiB RSS.
The 16 measured loading/solve attempts total 10.079 seconds, including initial
initialization and failed paths. These timers do not measure a successful full
application forecast, monitoring overhead or engineering effort.

All three artifacts were unexpired at inspection and retain until
2026-12-06T14:06:50Z. They have source head
`421273a1fd6a514bbe55e8da50906d92b1b5cfc4` and run 34131147623.

| Artifact | ID | Compressed bytes | SHA-256 |
|---|---:|---:|---|
| m9r-pmx-composition-contract-34131147623 | 10022120861 | 41,406 | `b1e6c136a6c18a3321d07582f713d79b6fee56c908c2894e0897704ef8a80fc8` |
| m9r-pmx-composition-solver-34131147623 | 10022307725 | 120,135 | `29a2aa4bb3c3d346f5ecbe59d9c49a6d6626cb81df7394e8d5e320164327b780` |
| m9r-pmx-composition-census-34131147623 | 10022320207 | 1,224 | `93a564434cc6e7a8786e3520a3252c7c44c28ab28b1b878cfb28536ea5abfa40` |

| Principal file | Bytes | SHA-256 |
|---|---:|---|
| composition-contract.json | 18,538 | `1268ff09f4dbfaa2fd9e7bc17232495db7cdbb1488bf185bf4ed1977620ca0f5` |
| raw-result.json | 4,555 | `c17634ffb5dc57e3a1e2fe535333fc2b5a252b3d447177f4c27ed72fae9c7ce8` |
| composition-census.json | 11,709 | `102f38c36f5ecc94ea7ac18a24286863ddb2973f1bcb924b81ab96b03024d421` |
| runtime/solve.log | 1,170,291 | `3f4484158193e8f96e587f6d3b99c80dda7a7ea900984d1076c06caa89e06d22` |

Five local unit tests cover exact containment preservation, reference type/ID
validation, the no-local-preparation guard, nested archived staging, and retention
of missing/unphysical census rows. The only retained-file local check used the
two small artificial repositories; all actual model loading and solving ran on
GitHub Actions. No M7/M9P native stream or evaluator was read.

This narrows the next independent PMX comparison requirement to a demonstrated
solver-compatible representation and a justified error/request correspondence.
It is not a negative verdict on PMX/Palladio or evidence favoring the proposed
availability estimator. The current bounded control is complete; the independent
M9P confirmation proceeds under its unchanged protocol.
