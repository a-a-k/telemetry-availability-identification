# Corrected exact-backend comparison v2 — fixed before measurement

This bounded repeat addresses the baseline audit without modifying v1 evidence, the v1 tag, or any of the 356 scientific locks. The full protocol is `configs/v3_exact_comparison_v2.json`; its SHA-256 and source commit travel with every artifact. No final timing has been inspected when choosing these configurations.

## Census and answer contract

Use the same saved-model panel as the previous experiment: all original repetition=0 application cases (22 DS, 24 OTel, 32 Pet; two original structural absences), and all 27 prespecified synthetic positions. No new telemetry or campaigns. Three technical rounds, eight fixed methods, two representations, seven snapshots: 35,280 planned endpoint queries in 5,040 fresh streams. Technical repeats and artificial snapshots are not independent experimental units.

All methods return the same six variant and five contrast bound pairs, rational endpoint strings and statuses, without witnesses. `ours_direct` uses the frozen core's category-fiber candidates and scalar predicate evaluation, omitting certificate production; `ours_prepared` retains the existing control/aggregate-completion truth table. This is two algorithms for the same formal model, not two scientific models.

## Shared representation and preservation argument

Both arms begin with the same original loaded model. `original` passes it through. `completion_projected` explicitly transforms it into controls Z and K=AND(C). In a category, any known false completion forces K=false; all known true completions force K=true; otherwise either value is attainable. Every one of the eleven Boolean outputs depends on completions only through K, while missing or asynchronous mandatory bindings retain their original effect. The control coordinates, graph and demand semantics remain intact.

The projection of each original mask fiber is precisely the resulting control/K fiber. The admissible law on a fiber is arbitrary, so every distribution on its projected fiber has a lift. Identical projected fibers can be merged by adding their positive empirical weights: their weighted mixture still spans the whole simplex on that fiber. Thus the transformation preserves the complete admissible projected-law family, including dependencies, every reported endpoint and every contrast. It adds no independence assumption. Category merging and input copying are charged as common conversion work for every participant.

The prepared algorithm already exploits completion conjunction internally. The original arm measures that specialization alongside general representations. The common projected arm makes the same input reduction available to every competitor; its conversion cost is included in total and reported separately. Kernel-only times are supplementary, not a substitute for inclusive totals.

## Fixed methods and implementation choices

- CUDD 3.0.0 via dd 0.6.0: control-first order with no reordering, or one explicit sift per semantic construction; initial cache 16,384 entries, memory estimate 1 GiB. Reuse the same manager, replace predicate roots. Restrict each distinct output root by the observed mask. Primary: sift.
- aGrUM 3.1.1: deterministic Boolean support network with LazyPropagation. Conditioned mode observes the category and requests unique output posteriors. Joint mode requests each unique (category, output) joint posterior once per query. Both inspect support cells and aggregate original frequencies rationally. No unconditional mixture inference for verification. The positive category prior is uniform, used only to establish support; it does not replace the target joint observation law. Retain the BayesNet container, retain inference when only counts change, rebuild the inference engine on CPT/mask changes. Primary: conditioned.
- Storm 1.14.0: exact-rational sparse DTMC/MDP reachability. Compare the existing decision graph and a generic exact acyclic transition/terminal-label quotient with elimination of deterministic unlabelled stutters. Terminal labels preserve the whole eleven-bit output vector. Bottom-up identical transition choices imply identical reachability behaviour; deterministic stutters preserve unbounded reachability. Keep the initial weighted state separate and aggregate its category-to-target map, so arbitrary frequency updates remain valid. This is explicit preprocessing, not Storm's double-valued native bisimulation API. The Environment and parsed property cache survive semantic rebuilds. Identical target-state sets share native queries. Primary: compact.

All eight configurations appear separately. No per-case selection, minimum-over-variants headline, or tuning from final measured runtimes. BN native arithmetic is double with exact-inference scheduling; endpoints are support decisions plus rational aggregation, checked against the rational reference. Allocation failures and timeouts remain explicit.

## Timing and reuse

Each case/method/representation/round starts a fresh worker process. Import its selected native library before the timer. No oracle references are passed to workers. Separate native toy controls run in a process that exits before measurement. Source integrity checks occur in the parent and cannot warm native worker objects. Qualification of the measured answers happens in the parent after all streams of the profile have ended; raw BN cells are read from worker outputs, with no extra inference.

Seven sequential snapshots share one backend: initial; identical repeat; count changes; completion-mask hiding and category merging; metadata change; an added real synchronous graph relation; restore original. Count and mask changes are declared artificial operations, not additional sampled telemetry. Every snapshot charges conversion, exact semantic-key construction/comparison, required representation construction, data update and endpoint query. Structural changes retain available library infrastructure. The guard conservatively compares predicate-defining fields; proving logical equivalence of differently described graphs is outside its contract.

Construction plus first query, repeated query, observed-data changes and structure rebuild are reported separately. No cached final answers or category-extrema tables are carried between queries beyond each method's prepared representation. The additional structure edge can change reachability and the observed answer; it does not force every success bound to zero as the v1 missing-required-edge control did.

Wall and CPU cover the loaded-model-to-answer boundary. Transformation, key, build, update and query stages are explicit. Additional statistics are read after timers. Peak RSS and whole-process time include imports, seven snapshots, input load and diagnostic/record serialization; they are not per-query memory or full telemetry pipeline cost. Fixed limits: 60 seconds per stream, 3 GiB address space, aGrUM 1 GiB inference memory, one thread. A broken stream records subsequent snapshots as upstream failures; it does not silently recreate infrastructure.

## Automated outputs and interpretation

The measurement workflow uploads compact scalar evidence and full remote evidence separately. A completion-triggered reporting workflow verifies the full planned census and creates all measurement, stage, resource, exact-answer, representation, failure, paired-ratio and synthetic-scaling tables plus Markdown. Paired ratios use matching case, representation, phase and round, against each of our algorithms. Failed cases never receive zero times or disappear from coverage tables. Synthetic positions are displayed separately from applications.

This experiment measures computation on the same identified empirical models. Agreement between exact backends is semantic verification, not independent prediction validation. Original PMX pipeline and 761-model witness-output CUDD studies remain separate cohorts. The core scientific contribution remains formal semantics, telemetry identification, identifiability and attainable bounds.
