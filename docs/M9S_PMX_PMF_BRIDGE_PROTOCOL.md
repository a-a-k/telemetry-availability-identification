# M9S: complete the integer-loop representation bridge

Frozen before the new solver outputs. On 8 September 2026 the user explicitly
requested completing the independent PMX comparison. This authorizes the next
source-grounded repair and comparison stages. The bounded M9R protocol and its
failed results remain unchanged; its stopping boundary does not terminate this
new task. A qualified bridge is a prerequisite, not the final comparison.

## Source-grounded diagnosis

The retained PMX artificial repositories contain three LoopActions with integer
iteration expression `1`. The exact solver-core 5.2.2 source artifact is
`org.palladiosimulator.solver.core.source_5.2.2.jar`, obtained from the official
[release site](https://updatesite.palladio-simulator.com/palladio-analyzer-solver/releases/5.2.2/plugins/org.palladiosimulator.solver.core.source_5.2.2.jar),
64,279 bytes, SHA-256
`851367cc0534342acf6ff7a621c8724586bd2c491ebbf9a31904807bcd1e14f3`.
`LoopActionHandler` stores the solved expression; `ContextWrapper` later sends
the serialized loop expression to `ManagedPMFParser.createFromString`. That
parser requires a ProbabilityFunctionLiteral containing a ProbabilityMassFunction
and rejects an integer literal. The source matches the retained exception path.
The pinned reliability `MarkovBuilder.initLoopMarkovChain` then dereferences the
missing PMF and requires integer-valued samples. Resource demands have a separate
wrapper that already accepts numeric literals; they are not changed.

Source file SHA-256 values:

| Source | SHA-256 |
|---|---|
| ManagedPMFParser.java | `19dae201070ad74193b7ff3aec60e6b44eac58b3edd9b947ff47676f5d82a450` |
| ContextWrapper.java | `30f7a523fb1e7817e499868f2dd0acfb0e9715512c7b973fa9a72c56b88ed73d` |
| LoopActionHandler.java | `69e7296b056c4009e25b2ff138d7a6bfeaf263cf937278558558124124e26787` |
| MarkovBuilder.java at a694e570afb705dc9e0470dc321e77b7219dcea4 | `0508a0131400bdfd2172b9be7fab7a697672332ab50a143d8d3b715c43cea551` |

For nonnegative integer `k`, the point-mass expression `IntPMF[(k;1.0)]`
represents exactly the same deterministic iteration count. The bridge changes
only these loop-expression tokens and verifies the unchanged remainder of the
XML tree. No action, call, resource, workload, failure probability or solver
implementation is changed by that conversion. It is a disclosed compatibility
bridge, not unmodified native PMX output.

## Twelve-model control

Use both retained M9R source repetitions, verified against its original contract
and archive. For each repetition create the following six variants, in this order:

| Variant | Source | Additional change | Software success oracle |
|---|---|---|---:|
| Raw negative | M9R raw | None | Incomplete failure references must not qualify |
| Scalar-loop negative | M9R types contained | None | Prior PMF boundary must not yield a valid probability |
| Inclusive PMF | M9R types contained | Three `1` loop counts become point-mass PMFs | 0.72 |
| Conditional-local PMF | M9R conditional-local sensitivity | Same equivalent loop conversion | 0.8 |
| Zero-error PMF | M9R zero-error control | Same equivalent loop conversion | 1.0 |
| Random-loop positive control | M9R types contained | Leaf loops use point masses; root loop uses `IntPMF[(0;0.5)(2;0.5)]` | 0.724 |

The final variant is an explicitly different artificial law. It tests that the
solver respects the count distribution rather than substituting its mean:
root success is `0.8 * (0.5 + 0.5 * 0.9^2) = 0.724`, while replacing the random
count by its mean one gives 0.72. The root is resolved through the usage entry
and described-service reference, not selected by looking at a solver answer.

Run all 12 models twice in one fixed solver environment, preserving every
exception and returned numeric object. The harness contains no expected
probabilities; a separate census applies the frozen oracles with tolerance
`1e-12`. The positive gate requires all 16 positive records to have finite
probabilities in [0,1], success plus failure mass one, full physical-state mass
one, all physical states evaluated, and the correct software oracle. Both
negative controls must retain a failure or invalid probability in all eight
records. Missing, duplicate or unexpected identities block qualification.

The analyzer remains at `a694e570afb705dc9e0470dc321e77b7219dcea4`, with the
accepted M9A target-platform lock, Java 17 and M9R configuration. Do not add
hardware availability or reinterpret its defaults to make the oracle pass.
All preparation and solver execution occur on GitHub Actions; jobs have
360-minute limits and artifacts retain for 90 days. Local tests use artificial
XML and read-only retained artificial/source inspection. This stage performs
zero PMX extractions, zero live collection and zero evaluator reads.

## Continuation required after this gate

If qualified, apply the verified bridge to the request-level PMX mapping and
independent parameterization. Preserve raw extraction coverage, inclusive versus
local error assumptions, missing traces and requests, root identity, repeated
calls and target population. A valid solver result on artificial models is not
the requested independent accuracy comparison. Historical M7/M9P outputs used
for development cannot become untouched confirmation of a revised comparator;
freeze the final compared methods and analysis before fresh confirmation.
