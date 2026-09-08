# M9U: complete external-request PMX conformance

Run [34190274003](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34190274003)
completed successfully on its first attempt, 8 September 2026, 05:20:48–05:31:16 UTC,
at frozen commit `76fcc134bf689270771dbabd9aaf3e2503d8bb4b`. CI 34190273356 passed on Python 3.11 and
3.13; all 285 local tests passed before dispatch. Config SHA-256:
`f27f6c9963b472150db889137d895b731835cc3b27426ee54e2f6941dbb6ac21`. The [prospective protocol](../M9U_PMX_REQUEST_CONFORMANCE_PROTOCOL.md)
was committed before PMX execution. All four artifact ZIP byte counts/digests,
the input-contract file hashes and all 110 prepared PCM file hashes were verified.

All 12 PMX invocations pass the seven reference-resolved structure/error checks
and exact trace/span/operation/parent/time reconstruction. The 22 prepared models
produce 44 unique, complete, valid solver records; all 44 numerical oracles pass
within 1e-12. Physical mass is one and the single physical state is evaluated.
The unsupported conditional-local swallowed-child variant remains absent by
design, while its native-inclusive model is solved and retained.

| Control | Native-inclusive success | Conditional-local success |
|---|---:|---:|
| Propagated nested errors | .576 | .8 |
| Compound HTTP request | .81 | .9 |
| No native trace | .8 | .8 |
| Unmarked service boundaries | .576 | .8 |
| Repeated HTTP calls / colliding native names | .6561 | .729 |
| Swallowed child error | .9 | unsupported |

Each numeric entry is reproduced across two independent extractor invocations
and two solver passes. These are software/representation controls. In particular,
the repeated-call control has empirical external success .9: its different
independent-composition values demonstrate why correct solving does not establish
an application's independence assumptions or accurate end-to-end predictions.
The no-trace control receives only the disclosed external semantic outcome;
it does not establish native architecture discovery without a trace.

The external wrapper, structural enclosure time, service-boundary inference and
native HTTP path qualification are adapter additions with original provenance
retained. Neither native timestamps nor PMX's inclusive error estimates are
rewritten to match an availability oracle. Conditional-local estimates use only
the specified joint calibration counts, with propagation and positivity guards.
Palladio analyzer code and its M9S generic harness are unchanged.

The prepare job took 294 seconds, solver job 307 seconds, census job 18 seconds
(619 runner-seconds total). Twelve PMX invocations and preparation took 263.70
seconds at maximum RSS 337,888 KiB; the 20-second startup stabilization per
invocation is included. Analyzer build took 179.67 seconds at 1,663,112 KiB;
Maven solve invocation took 91.70 seconds at 1,348,660 KiB. These artificial costs
do not estimate application acquisition or fitting cost.

## Artifact evidence

Artifacts expire 7 December 2026, 05:20:49 UTC. Exact aggregate evidence is retained
in [the repository evidence directory](../evidence/m9u-34190274003/).

| Artifact | ID | ZIP bytes | SHA-256 |
|---|---:|---:|---|
| m9u-request-census-34190274003 | 10042166835 | 1605 | `dbb827fb5a9c66518e5869054d0efc09a35f0192c5f7d2056cb24677651f41cf` |
| m9u-request-solver-34190274003 | 10042158789 | 103059 | `cf2c17e5480c9d45401449ad7c1681c6dc534659693641b4cfc1994985291c85` |
| m9u-request-contract-34190274003 | 10042048832 | 361671 | `1d7f7af8c8bf8a239566e01fc883b67869e2a4382aab9feb5cb9feab8e4f1113` |
| m9u-request-input-34190274003 | 10041954761 | 47011 | `4f5eeb0a35c03dd8f462ac1fba2b24bdc113aa2c521fc50ae81596b4d68a3b3e` |

| Retained file | Bytes | SHA-256 |
|---|---:|---|
| request-contract.json | 51674 | `67a1db38dcf119ce770d29d2f181f8e62acef28bbdb0778d6fb76c9d5ff6bfe4` |
| input-contract.json | 5384 | `5f4404bcbe5b77302576f8a4e017128786901d3287f870a149f53fc9a0aac1f7` |
| raw-result.json | 13889 | `0dad15d1d4d3c3c5fe49e106e8efa437ae27c62a998dbc36938e03774a8df697` |
| request-conformance-census.json | 25821 | `2c67902b4f162ef46410d8de8d3fd5a5230c206353b38851f0fa77e2e3af1ecd` |
| extraction-resource-usage.txt | 913 | `3bbcbcc95a513b95c2db7ae744d120689ae12bb01e204ea5e8bcbc53203d6b9c` |
| build-resource-usage.txt | 886 | `0a1367bc3a74055179f13412e49457c297fa14953639a2da74735caab266310e` |
| solve-resource-usage.txt | 862 | `2f76fa28592f88f1fc537d9a4a0b3da003c0f76c13405014bb083ecbbdd0b435` |
| artifact-api.json | 3009 | `823308f725a95a19317fc408d90fb2f5822c0c647bbc6f4778a1ab8409cb84cf` |
| run-api.json | 8625 | `4eb1baee8ec53f644b4157c22d6b196cb0f0617472b21294504ab521fdc77f78` |

M9U closes the external-request software contract. Continue with M9V's historical
application development comparison and a separate prospective fresh confirmation;
independent application predictive validity is not established by these controls.
