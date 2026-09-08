# Ordinary native identity and observed joint demands

[Run 34244994519](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34244994519)
completed all six jobs at commit `fca9e011a3722e8d39de3b4d7dd3506858a1f385`.
Protocol SHA256 `da925e50f35404fb8a1eabbea35b79fcafa40b5f213e141d500f50a3d1885a30`.
The original ordinary native projection is exactly reproduced from the pinned
DeathStar and OTel raw sources before restoring 3,560 `hostname` and 7,680
`host.name` attributes. Requests, probes and declarations remain byte-identical.
Petclinic's existing native data need no identity additions. Frozen v1 evidence
remains unchanged; standard instance-ID absence was never absence of all identity.

Every inspection runs in a separate job from raw preparation and reads exactly
six versioned ordinary files with zero blocked access. All 4,080 attempts and
ten operations are retained. No controller/evaluator input reaches inspection.

| Operation | Observed target entries | Exact known replica labels | Observed footprints |
| --- | --- | --- | --- |
| DeathStar compose_post | 80 | 80 through native hostname | a:32, b:48 |
| DeathStar read_user_timeline | 80 | 80 through native hostname | a:24, b:56 |
| DeathStar read_home_timeline | 0 | No target call expected | No observed user-timeline demand |
| OTel browse_product | 80 | 80 through study.replica | a:36, b:44 |
| OTel add_to_cart | 80 | 80 through study.replica | a:42, b:38 |
| OTel checkout | 240 over 80 attempts | 240 through study.replica | All 80 use both replicas; words a,b,a:42 and b,a,b:38 |
| Petclinic create_visit | 764 over 900 attempts | 764 through agreeing replica/instance IDs | 136 attempts lack an observed Visits entry |
| Petclinic owner_details_with_visits | 752 over 900 attempts | 752 through agreeing replica/instance IDs | 148 attempts lack an observed Visits entry |
| Petclinic list_owners / list_vets | 0 in each operation | No Visits call expected | No observed Visits demand |

The DeathStar adapter uses the two exact entry names created by the pinned
UserTimelineHandler source and a cross-service parent relation. It preserves
empty native kinds; no SERVER marker is fabricated. All observed target entry
labels resolve without conflict. A source-declared entry is an explicit adapter,
not a native field or a proof that all attempted calls reached an entry span.

OTel's normal-window checkout calls use both replicas in every retained attempt.
Replacing that joint footprint by independent draws from call marginals changes
the implied event under a single unavailable replica. These are development
observations, not proof of invariant round-robin routing under failures,
concurrency changes, retries or placement transfer. Timestamp word order is
descriptive, not established causal order.

Petclinic retains 284 failed attempts with no observed Visits entry. None is
assigned a guessed backend. All 46 timeouts have observed entries: create_visit
a/b = 10/11 and owner-details a/b = 13/12. Two additional create_visit failures
have observed target entries, one per replica. Thus, observed target completion
alone is not equivalent to the full external contract. Failure-specific
missingness and the complete outcome census remain available to the next model
binding; no successful-only footprint estimator is admitted here.

Six exact compact ZIPs total **12,257 bytes**, with 15 member hashes, source and
run metadata, full demand censuses and process cost records in
[verified archives](../evidence/v3-ordinary-identity-34244994519/verified-archives.json).
The three extended ordinary artifacts remain remote and have exact API digests
in the retained metadata. Two TLS metadata retrieval failures used the canonical
run-list record as a read-only fallback; no experiment was rerun or outcome
changed. Three bounded controls and CI on Python 3.11/3.13 passed.

This completes the identity extension and observed demand census. It does not
identify counterfactual capability of unselected replicas, imply independent
calls, estimate a main forecast or establish the graph predicate's equivalence
to business success. Main remains 0/240; next is the explicit model/observation
binding and its structural, semantic, missingness and independent controls.
