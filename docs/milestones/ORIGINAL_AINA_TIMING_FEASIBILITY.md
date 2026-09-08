# Original AINA timing feasibility: complete retrospective census

Run [34233092614](https://github.com/a-a-k/telemetry-availability-identification/actions/runs/34233092614), head63fff7ba58dea8901ed9ea3de5346a7b30733b94, success. Config SHA256317aa05621af000c67dd4b13c02b39fcc2f053721bd9db5eb360378369083106. Same byte-verified250 original archives,25000 windows,2500000 probes; frozen error classifier and thresholds before raw error inspection. No new source data or application run.

| p | Windows | Explicit6s read timeouts | Conditional lower bound>45s | Conditional lower bound>60s | Largest lower bound,s |
| --- | --- | --- | --- | --- | --- |
| 0.1 | 5000 | 29856 | 1595 | 796 | 240 |
| 0.3 | 5000 | 29295 | 1964 | 589 | 252 |
| 0.5 | 5000 | 33692 | 2280 | 686 | 240 |
| 0.7 | 5000 | 34644 | 2598 | 618 | 246 |
| 0.9 | 5000 | 35111 | 2616 | 794 | 222 |

All original failure records classify as HTTP5xx or explicit6s read timeouts; no residual category is omitted. There are162598 such timeout records. Under the recorded timer and sequential collector semantics,11053/25000 windows(44.212%) need more than the nominal45s remaining after the workflow's15s delay, and3483/25000(13.932%) need more than the controller's declared60s sleep. Bounds ignore all successful/fast-failing calls and other overhead, so they are conservative under those premises. Requests read-timeout semantics concern a period without received socket bytes, not a total request deadline: [official documentation](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts).

The original collector's --window40 argument never bounds its100-probe loop. Thus calling those results measurements of a fixed fault state throughout a single60s window is not justified by the source or retained annotations. This is a concrete measurement-alignment problem to investigate, distinct from async predicate invariance.

These are conditional lower bounds derived from logged timeout declarations, not measured timestamps. Controller preparation and stop/start costs are unknown; they shift and extend the actual physical fault interval. Counts above45s/60s do not determine which particular successes followed recovery, an exact bias correction, or the proportion of the original±error explained. No windows or outcomes are deleted/reclassified. Original global results, source, and full audit34231677146 remain unchanged. No second H is confirmed or refinement chosen here; a causal attribution needs a separately frozen intervention with actual timestamps and a negative control.

All original parsing ran remotely. The audit's inner elapsed time is8.289s; full process costs are retained separately. Exact compact artifact10058643986:255638bytes, sha256:767fdc04bb04900b73b151f6d6a42b260d712765f3a8e68bcbcb50f888b8d0db. [Summary](../evidence/original-aina-timing-34233092614/files/summary.json) and [complete window/error-type census ZIP](../evidence/original-aina-timing-34233092614/compact.zip) preserve all cases. Main0, new independent campaigns0.
