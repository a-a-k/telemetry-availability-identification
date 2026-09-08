# M9S: qualified PMX integer-loop representation bridge

Status: complete and qualified. The first-attempt run
[34187887857](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34187887857)
at `fcafcd9375966817a675c76cec2e5b7c97c7d781` ran from
2026-09-08T04:41:35Z to 04:49:37Z. All three jobs succeeded; the corresponding
[CI](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34187868905)
passed 277 unit tests on Python 3.11 and 3.13. The frozen config SHA-256 is
`673de387d4d5911e56fa36d61e580a6ed8d09b181f5176e2dcc2f9db6ca6e1d0`.

## What changed and why

The [source-grounded protocol](../M9S_PMX_PMF_BRIDGE_PROTOCOL.md) isolates M9R's
loop failure. The solver-core 5.2.2 context reader requires an explicit PMF,
whereas the retained PMX models serialize deterministic counts as `1`.
Replacing each integer `k` by `IntPMF[(k;1.0)]` preserves the count law. Only
these expression tokens change; the bridge checks the unchanged XML tree,
failure references, probabilities and other four model files. The previously
disclosed failure-type containment completion remains necessary.

The two retained artificial source extractions produce six variants each,
attempted twice. The original raw and scalar-loop models remain negative
controls. No PMX extraction or live campaign is rerun. All loading and solving
use the original pinned analyzer and configuration on GitHub Actions.

| Variant | Records | Result in every record | Oracle passes |
|---|---:|---|---:|
| Raw negative | 4 | Missing software failure type; outer exception | Not eligible |
| Types contained, scalar loops | 4 | Zero success/failure/physical mass; zero evaluated states | Not eligible |
| Inclusive errors with PMF loops | 4 | Success 0.7200000000000001; failure 0.28 | 4/4 |
| Conditional-local sensitivity with PMF loops | 4 | Success 0.7999999999999999; failure 0.2 | 4/4 |
| Zero-error PMF control | 4 | Success 1.0; failure 0.0 | 4/4 |
| Random-loop control | 4 | Success 0.7240000000000001; failure 0.276 | 4/4 |

All 16 positive records have physical mass one and one of one physical states
evaluated. All frozen software oracles pass at tolerance `1e-12`. The full
24-record matrix has no missing, unexpected or duplicate identity. Both old
failure boundaries reproduce without changing their inputs.

The random-loop case is a separate artificial law, not an equivalent rewrite:
zero and two iterations each have probability one half. The root retains its
0.2 local-action error and its child 0.1, giving
`0.8 * (0.5 + 0.5 * 0.9^2) = 0.724`. The result demonstrates use of the count
distribution rather than substitution of its mean one, which would give 0.72.

## Interpretation

The previously analytic inclusive/local distinction is now also demonstrated
through the retained PMX structure and pinned solver. Counting parent and child
inclusive errors as independent local failures produces 0.72 for the declared
serial example; the explicitly assumed conditional-local interpretation gives
0.8. This does not prove that local errors are independent in an application,
or that every child error propagates. The original ten trace patterns do not
identify counterfactual root behavior when a child fails.

M9S resolves the demonstrated compatibility barrier with disclosed failure-type
containment and equivalent integer-loop encoding. It does not establish native
PMX interoperability for every PCM construct, or supply an application forecast.
The independent comparison continues with the request correspondence census
[M9T](M9T_PMX_REQUEST_CORRESPONDENCE.md) and the
[comparison execution plan](../PMX_INDEPENDENT_COMPARISON_EXECUTION.md).

## Provenance, retention and cost

All three downloaded ZIP lengths and SHA-256 digests were verified against the
Actions API, as were source run/head and unexpired status. All 60 prepared model
file hashes matched their contract. The retained summary and timing files are
in [the evidence directory](../evidence/m9s-34187887857/pmf-bridge-census.json).
The accepted gate is recorded separately in
`configs/m9s_pmf_bridge_acceptance.json`. No native application data was downloaded
locally in this stage.

All three artifacts expire at 2026-12-07T04:41:36Z. Names share prefix
`m9s-pmx-pmf-bridge-` and suffix `-34187887857`.

| Kind | ID | ZIP bytes | SHA-256 |
|---|---:|---:|---|
| contract | 10041146612 | 125,389 | `610a8a4f254407254cd4c594ecb82daaf19dfdacc7b64ca7cf134b81491b3d1c` |
| solver | 10041290625 | 110,378 | `3a2d84bdc7c0250a79be293964295565ed287649c3e8d876f6b572fdebba4857` |
| census | 10041298380 | 1,352 | `619f00dd9e3e6d5c29ff327ec4f0be0c1fd09cf27b67ecf522230e3b31d9b4ef` |

The contract is 21,256 bytes with SHA-256
`5dfeceaea31bc372d6ef7358ab9d1dfd0a29a0db48e30ed112100140b0252b94`;
raw solver output is 7,105 bytes with SHA-256
`ec2b8d36269f09f5bc21febd88458ca6f2217643324148e0f3e6fdc0973f3b76`;
the census is 12,941 bytes with SHA-256
`bb6135cbfb006843bc6067e107664b41cb99fbceab2465f108d5a3da40c7941b`.

Preparation, solver and census jobs took 21, 431 and 20 seconds. The analyzer
build took 287.53 seconds with peak RSS 1,866,028 KiB; the Maven solve command
took 98.58 seconds with peak RSS 1,309,672 KiB. The 24 case timers total
11.189235 seconds and include initialization and failed attempts. These are
technical control costs, not independent repetitions or an application cost
advantage. Six new unit tests cover exact expression-only conversion, rejection
of unsupported expressions, root selection, physical probability validity,
the remote execution boundary, and complete census accounting.
