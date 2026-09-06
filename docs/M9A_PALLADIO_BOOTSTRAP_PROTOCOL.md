# M9A: Palladio reliability bootstrap protocol

## Purpose and boundary

M9A establishes a reproducible, commit-pinned execution boundary for the
official Palladio reliability analyzer. It is an integration and correctness
milestone, not an accuracy comparison and not evidence that either Palladio or
the telemetry-driven approach is successful.

The source is the official `Palladio-Analyzer-Reliability` release tag
`releases/5.2.2` at commit
`a694e570afb705dc9e0470dc321e77b7219dcea4`. The official `ReliabilityTest`
example is taken from `Palladio-Example-Models` commit
`4a8dc455216774435fefd42965b848851f7658ee`. Java is fixed to Temurin 17, as
required by the analyzer bundle. The corresponding versioned Linux
Palladio-Bench 5.2.2 archive is audited separately from the source build.

The first remote discovery attempt exposed one mutable transitive input in the
published source build. Palladio's Maven target
`palladio-target-platforms:0.1.0:palladio-2023-03` points to MDSD Ecore
Workflow `releases/latest`. At the Palladio 5.2.2 product cutoff that endpoint
resolved to MDSD 1.0.0, whose bundle requires JavaSE-17; by September 2026 it
resolved to 1.2.0, whose bundle requires JavaSE-21, so the historical Java-17
target no longer resolved. M9A therefore verifies the original target artifact
byte-for-byte, changes that single URL in an isolated Maven cache to the
versioned `releases/1.0.0` endpoint, and verifies the pinned repository metadata,
feature, and bundle hashes before building. The analyzer checkout itself remains
unchanged. This is a release-date dependency reconstruction, not an analyzer
source patch; both original and reconstructed hashes are retained.

M9A makes no PCM mapping for M7 and uses no M7 outcome. It cannot be used to
select a favorable Palladio configuration or to repair the M7 result.

## Three remote jobs

All three jobs run only in GitHub Actions and each has
`timeout-minutes: 360`.

1. `source_build` checks out the exact analyzer commit, applies the audited
   historical dependency lock outside that checkout, performs the Maven/Tycho
   build, and hashes the resulting reliability feature and solver bundle.
2. `product_audit` downloads the versioned official Palladio-Bench archive,
   checks its byte length and SHA-256, and inventories the included reliability
   feature and solver bundle. Eclipse products may package a feature either as a
   JAR or as an exploded directory; the exact 5.2.2 feature descriptor is
   required in either representation.
3. `official_example` overlays only a test harness onto the pinned analyzer
   test bundle, loads the five official PCM model files through Palladio's own
   model-loading jobs, executes `Pcm2MarkovStrategy` twice, and records success,
   failure, and physical-state probability mass.

The harness calls the public analyzer implementation; it does not reimplement
the DTMC computation in Python. The source build and the harness run are separate
jobs so a successful overlaid test cannot substitute for proving that the pinned
upstream analyzer code builds under the declared historical dependency lock.

## Discovery and acceptance

The upstream download directory publishes no SHA-256 alongside the product
archive, and the example repository does not publish an expected numeric result
for the launch file. Therefore the first successful workflow execution is a pin
discovery run only. It records, but does not accept, the archive SHA-256 and the
repeated example probability.

After that run, both values are added to the committed lock. M9A is accepted
only on a fresh execution where:

- source and example Git heads equal their full pinned commits;
- the analyzer checkout remains untouched, the one-URL historical target lock
  matches all committed before/after and repository hashes, and the build emits
  exactly version 5.2.2 of the required feature and solver bundle;
- the binary product has exactly 290,508,238 bytes and the newly committed
  SHA-256;
- the product contains the exact 5.2.2 reliability feature and solver bundle;
- two analyzer executions return finite probabilities in `[0,1]`, enumerate
  full physical-state mass, conserve success-plus-failure mass within `1e-12`,
  agree with each other within `1e-12`, and equal the newly committed example
  probability;
- manifests, build/test logs, and model-file hashes are retained as workflow
  artifacts.

A green discovery run is not milestone completion. Any analyzer-source
modification outside the recorded harness overlay, target-lock mismatch,
missing model, missing bundle,
non-deterministic probability, mass defect, or pin mismatch rejects the run.

## Next semantic milestone

M9B will construct independent hand-checkable PCM controls: one component, two
independent redundant paths, a shared resource disabling both replicas, a
communication failure, and conditional/fallback execution. Exact numerical
agreement will be required only where PCM and the comparison formula express
the same stochastic model. Unsupported mechanisms will be reported as limits
of comparability rather than silently dropped.
