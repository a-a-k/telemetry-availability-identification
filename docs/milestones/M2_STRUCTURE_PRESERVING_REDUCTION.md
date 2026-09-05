# M2 report: structure-preserving likelihood reduction

## Status and evidence

Status: complete.

- Tested commit: `e3894b556cab813c84ce01bd3d5b0d4a05b72a82`.
- CI run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33959597099>.
- Diagnostic run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33959637133>.
- Full run: <https://github.com/a-a-k/telemetry-availability-identification/actions/runs/33959707497>.
- Aggregate artifact: `m2-aggregate-33959707497` (2,361,133 bytes; GitHub retention expiry: 2026-10-05).

The full manifest records a clean four-shard Linux run on the tested commit with
Python 3.13.15, NumPy 2.4.4, SciPy 1.17.1, and PyYAML 6.0.2.

## What was implemented

M2 adds the first proof-oriented observation compiler. For every observation
policy it assigns each primitive factor a membership signature across retained
observables. Factors with an identical nonzero signature are replaced by a named
product factor; factors with an all-zero signature are marked inactive and
removed from the likelihood.

The compiler also enumerates the complete supported moment matrix for the small
conjunctive models and returns one of three statuses for every original parameter
and target: `proved_identifiable`, `proved_ambiguous`, or `unresolved`. For every
proved-ambiguous quantity it emits two interior parameter vectors that retain all
supported observable moments but change that quantity.

The proposed reduced procedure uses the same exact conditional likelihood,
optimizer, starts, and stopping rules as B3. Product-factor bounds equal the
products of the original primitive bounds. Thus the experiment isolates the
compilation rule: a different likelihood objective or a weaker comparator cannot
explain the result.

## Preservation checks

Unit tests enumerate the full observable distributions of every original and
reduced family/mode pair and require equality to floating-point tolerance. The
workflow additionally compares optimized objectives campaign by campaign and
fails before artifact upload if the predeclared equivalence tolerance is
violated.

The full output contains:

| Table | Rows |
|---|---:|
| Compiler descriptions | 12 |
| Ambiguity witnesses | 26 |
| Method fits | 14,400 |
| Individual, combination, and target evaluations | 96,000 |
| Compressed input patterns | 52,943 |
| Paired fit comparisons | 7,200 |
| Paired summary cells | 36 |

Of 7,200 campaign prefixes, 6,600 contained supported observations for both
methods. Objective-equivalence rate was 100% in every summary cell and the
largest absolute B3/reduced NLL difference was `1.01e-11`. The remaining 600
prefixes are the expected health-only family under trace-only input, for which
neither method has an observation. No unsupported estimate was emitted.

All 26 ambiguity witnesses preserved observable moments with maximum discrepancy
`1.11e-16`. The smallest absolute change in the witnessed parameter or target was
0.0196, so the certificates are not merely round-off perturbations.

## Structural results

The compiler did not reduce any full or staggered-health model. This negative
control is required: those observation signatures distinguish the available
primitive columns even where a more general linear ambiguity remains.

Trace-only reductions were:

| Family | Parameters | Latent states | Explicit output |
|---|---:|---:|---|
| Mandatory fan-out | 6 to 3 | 64 to 8 | three identifiable products |
| Communication bottleneck | 5 to 1, one inactive | 32 to 2 | one identifiable path product |
| Two-domain path | 7 to 1, two inactive | 128 to 2 | one identifiable path product |
| Same-domain replicas | 3 to 0, three inactive | 8 to 0 | no supported quantity |

The unreduced B3 optimizer reported 1,797 non-unique multistart solutions. After
equivalent factor products were compiled explicitly, the proposed procedure
reported 596. These remaining cases are the genuine same-domain/no-joint-health
ambiguity, which signature grouping alone cannot remove and which the compiler
continues to certify rather than resolving arbitrarily.

## Statistical and runtime results

Individual, product, and target estimates agreed between B3 and the proposed
procedure to numerical precision. Across paired summary cells, mean MAE
differences were at most approximately `1e-9`. This equality is the expected
correctness result because both procedures optimize the same preserved
likelihood.

At sample size 2,000, trace-only identifiable-product MAE for the proposed
procedure was 0.00526 for mandatory fan-out, 0.00730 for the communication
bottleneck, and 0.00767 for the two-domain path. These are estimable combinations,
not recovered individual failure causes.

Median B3-to-proposed fit-time ratios in the trace-only cells ranged from 1.20 to
1.34 despite state-space reductions of 8x--64x. In unreduced cells the ratio was
approximately one. The modest speedup is unsurprising at 2--128 states, where
optimizer and Python overhead dominate. It does not establish large-graph
scalability.

## Interpretation

M2 supports a narrow T2-style claim: the implemented identical-signature rule
preserves the complete observable distribution and the optimized likelihood, and
it converts some non-identifiable primitive parameterizations into explicit
identifiable products. It does not increase statistical information and does not
improve estimates when no reduction applies.

This is useful method behavior rather than a headline accuracy result. A user can
receive the product that telemetry identifies, together with explicit evidence
that its constituent causes cannot be separated, instead of receiving an
arbitrary optimizer point.

The rule is not a general sparse factor-graph elimination algorithm, and the
input topology and observation semantics remain configured rather than extracted
from live telemetry. M3 must demonstrate why recovering such structure matters
for a target that is not simply an observed request-success frequency and must
compare against B0/B1/B2/B3/B4 under a placement change.
