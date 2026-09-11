# Exact model size and observation-mask scaling v1

Supplement to the author's complete performance-table request, fixed before its
timings. The unchanged `graph_execution_model_v1.py` core is measured remotely
on artificial chains. No native application data, new accuracy estimate or
additional independent campaign is involved.

Three finite axes are tested: (1)4/8/16/32/48 nodes at16 fully observed categories;
(2)the same node counts with all completion coordinates unknown and10 unknown
eligibility/deadline coordinates; (3)0/2/4/6/8/10 unknown controls at16 nodes with
all completion coordinates unknown. Nine eligibility signals gate entry; the
tenth control is timeliness. Every node is required. Completion has one entry
coordinate and one per synchronous chain edge. At48 nodes the total58 signals
remains inside the original64-coordinate cap and10-control cap.

Complete observations enumerate all16 configurations of the first four
completion coordinates, with all other coordinates true, giving exact success
1/16. Masked completion permits both0 and1. Every model's exact point/bounds and
evaluated-state count must match these independent analytic controls. Run one
untimed warmup and seven recorded solves per case; require exact complete-result
equality for every repeat. Retain every raw duration, median/min/max, actual
nodes/edges/categories/coordinates and full/reduced state counts.

The large full-fiber counts are exact combinatorial counts, not wall timings of
an executed brute-force solver. The completion reduction evaluates at most two
extremes per control assignment. Unknown controls still require exponential
enumeration. These finite measurements do not establish unrestricted linear
scalability, remove class caps or compare unlike synthetic PMX models.
