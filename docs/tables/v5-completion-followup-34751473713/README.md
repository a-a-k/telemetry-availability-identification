# Matched E/R identification costs and retrospective forecast accuracy

All four configurations run on the same runner per application, with warm file cache, fresh processes and paired rounds. First-answer seconds include launch, reading, interpretation, construction, query and saving. Verification occurs after every timed run in a profile. Ratios are paired before taking the median; min/max and all 108 measurements remain in the CSV files. Input copies add no independent observations.

| Application | Attempts | Full → E, s | Full → R, s | Full → projection → R, s | Direct → R, s | E/direct R | Full R/direct R | Projected R/direct R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deathstarbench_social_network | 3600 | 1.956221 | 1.958712 | 1.957612 | 1.840151 | 1.062025 | 1.059159 | 1.058564 |
| deathstarbench_social_network | 7200 | 3.316800 | 3.317807 | 3.317959 | 3.103276 | 1.068840 | 1.069130 | 1.073840 |
| deathstarbench_social_network | 14400 | 6.185699 | 6.200366 | 6.195753 | 5.494842 | 1.125679 | 1.127534 | 1.128427 |
| opentelemetry_demo | 3600 | 4.376689 | 4.310787 | 4.321872 | 4.113264 | 1.064043 | 1.054483 | 1.049180 |
| opentelemetry_demo | 7200 | 7.832405 | 7.893404 | 7.871836 | 7.434372 | 1.053540 | 1.061745 | 1.063542 |
| opentelemetry_demo | 14400 | 15.592481 | 15.464324 | 15.573569 | 14.737559 | 1.061374 | 1.049314 | 1.054274 |
| spring_petclinic_microservices | 3600 | 2.034610 | 2.050751 | 2.028081 | 1.908090 | 1.063240 | 1.069133 | 1.065253 |
| spring_petclinic_microservices | 7200 | 3.366316 | 3.368091 | 3.356934 | 3.143351 | 1.067299 | 1.073910 | 1.064962 |
| spring_petclinic_microservices | 14400 | 6.179392 | 6.193156 | 6.216174 | 5.486056 | 1.124706 | 1.127491 | 1.132598 |

The E/direct R column compares different targets. Its interpretation requires the event/bounds and forecast checks. The other two ratios compare routes for exactly the same R. **No ratio here is multiplied by or presented as a new comparison with Palladio.**

| Application | Attempts | Route | Read, s | Interpret, s | Represent, s | Frequencies, s | Reduce, s | Query, s | Save, s | Startup/dispatch, s | CPU, s | Peak RSS, MiB | Variables | Categories |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deathstarbench_social_network | 3600 | full_e | 0.228211 | 0.773905 | 0.173455 | 0.010477 | 0.000000 | 0.001583 | 0.000627 | 0.772274 | 2.530181 | 206.375000 | 29 | 10 |
| deathstarbench_social_network | 3600 | full_r | 0.228130 | 0.772431 | 0.175346 | 0.010277 | 0.000000 | 0.000147 | 0.000657 | 0.769793 | 2.531172 | 206.285156 | 29 | 10 |
| deathstarbench_social_network | 3600 | projected_r | 0.227290 | 0.778372 | 0.173452 | 0.010262 | 0.000135 | 0.000092 | 0.000363 | 0.767641 | 2.524981 | 206.417969 | 6 | 6 |
| deathstarbench_social_network | 3600 | direct_r | 0.226449 | 0.747978 | 0.094064 | 0.007573 | 0.000000 | 0.000099 | 0.000370 | 0.764788 | 2.411470 | 206.562500 | 6 | 6 |
| deathstarbench_social_network | 7200 | full_e | 0.463731 | 1.547326 | 0.503908 | 0.021325 | 0.000000 | 0.001627 | 0.000638 | 0.770937 | 3.888179 | 310.675781 | 29 | 10 |
| deathstarbench_social_network | 7200 | full_r | 0.462231 | 1.539226 | 0.510886 | 0.021654 | 0.000000 | 0.000163 | 0.000652 | 0.772487 | 3.890659 | 310.476562 | 29 | 10 |
| deathstarbench_social_network | 7200 | projected_r | 0.468165 | 1.542510 | 0.511109 | 0.021500 | 0.000150 | 0.000099 | 0.000364 | 0.773449 | 3.886466 | 310.734375 | 6 | 6 |
| deathstarbench_social_network | 7200 | direct_r | 0.466361 | 1.570778 | 0.279684 | 0.014599 | 0.000000 | 0.000110 | 0.000394 | 0.769040 | 3.673686 | 310.523438 | 6 | 6 |
| deathstarbench_social_network | 14400 | full_e | 0.940079 | 3.639136 | 0.781637 | 0.039561 | 0.000000 | 0.001638 | 0.000655 | 0.773597 | 6.759035 | 519.218750 | 29 | 10 |
| deathstarbench_social_network | 14400 | full_r | 0.943043 | 3.653930 | 0.780228 | 0.039773 | 0.000000 | 0.000177 | 0.000677 | 0.778325 | 6.773810 | 519.183594 | 29 | 10 |
| deathstarbench_social_network | 14400 | projected_r | 0.941754 | 3.648328 | 0.780253 | 0.039119 | 0.000401 | 0.000103 | 0.000364 | 0.777634 | 6.769122 | 519.074219 | 6 | 6 |
| deathstarbench_social_network | 14400 | direct_r | 0.931078 | 3.174036 | 0.591433 | 0.028894 | 0.000000 | 0.000113 | 0.000381 | 0.771860 | 6.068209 | 519.156250 | 6 | 6 |
| opentelemetry_demo | 3600 | full_e | 0.763543 | 2.353323 | 0.351541 | 0.017998 | 0.000000 | 0.003372 | 0.000796 | 0.862723 | 5.010503 | 446.425781 | 38 | 22 |
| opentelemetry_demo | 3600 | full_r | 0.759143 | 2.323709 | 0.353226 | 0.018822 | 0.000000 | 0.000169 | 0.000799 | 0.870261 | 4.916519 | 446.433594 | 38 | 22 |
| opentelemetry_demo | 3600 | projected_r | 0.759582 | 2.308075 | 0.350156 | 0.018107 | 0.000181 | 0.000091 | 0.000407 | 0.858737 | 4.954576 | 446.496094 | 6 | 7 |
| opentelemetry_demo | 3600 | direct_r | 0.757900 | 2.322975 | 0.157821 | 0.008535 | 0.000000 | 0.000099 | 0.000422 | 0.861464 | 4.748486 | 446.636719 | 6 | 7 |
| opentelemetry_demo | 7200 | full_e | 1.533815 | 4.647198 | 0.756673 | 0.026627 | 0.000000 | 0.003499 | 0.000858 | 0.871698 | 8.465115 | 789.226562 | 38 | 22 |
| opentelemetry_demo | 7200 | full_r | 1.550119 | 4.686972 | 0.759321 | 0.026277 | 0.000000 | 0.000219 | 0.000872 | 0.873437 | 8.526966 | 789.457031 | 38 | 22 |
| opentelemetry_demo | 7200 | projected_r | 1.560602 | 4.655575 | 0.761857 | 0.026302 | 0.000836 | 0.000110 | 0.000423 | 0.875346 | 8.515684 | 789.355469 | 6 | 7 |
| opentelemetry_demo | 7200 | direct_r | 1.520062 | 4.426079 | 0.585803 | 0.016648 | 0.000000 | 0.000105 | 0.000423 | 0.867673 | 8.061926 | 789.433594 | 6 | 7 |
| opentelemetry_demo | 14400 | full_e | 3.054313 | 10.052434 | 1.525074 | 0.052764 | 0.000000 | 0.003584 | 0.000861 | 0.892155 | 16.167159 | 1475.023438 | 38 | 22 |
| opentelemetry_demo | 14400 | full_r | 3.061842 | 9.954091 | 1.512840 | 0.053301 | 0.000000 | 0.000213 | 0.000834 | 0.891311 | 16.057964 | 1475.027344 | 38 | 22 |
| opentelemetry_demo | 14400 | projected_r | 3.063910 | 10.032066 | 1.514914 | 0.052785 | 0.000688 | 0.000112 | 0.000450 | 0.880873 | 16.206410 | 1474.910156 | 6 | 7 |
| opentelemetry_demo | 14400 | direct_r | 3.093024 | 9.565424 | 1.176838 | 0.032364 | 0.000000 | 0.000118 | 0.000443 | 0.869667 | 15.372361 | 1474.882812 | 6 | 7 |
| spring_petclinic_microservices | 3600 | full_e | 0.283826 | 0.749196 | 0.134607 | 0.009270 | 0.000000 | 0.001813 | 0.000766 | 0.852563 | 2.654111 | 238.527344 | 25 | 13 |
| spring_petclinic_microservices | 3600 | full_r | 0.284114 | 0.752232 | 0.137767 | 0.009319 | 0.000000 | 0.000157 | 0.000780 | 0.857400 | 2.677851 | 238.742188 | 25 | 13 |
| spring_petclinic_microservices | 3600 | projected_r | 0.285211 | 0.745452 | 0.138430 | 0.009215 | 0.000142 | 0.000108 | 0.000445 | 0.856511 | 2.658680 | 238.601562 | 8 | 8 |
| spring_petclinic_microservices | 3600 | direct_r | 0.281487 | 0.701571 | 0.065769 | 0.006324 | 0.000000 | 0.000110 | 0.000443 | 0.853421 | 2.541214 | 238.421875 | 8 | 8 |
| spring_petclinic_microservices | 7200 | full_e | 0.576304 | 1.603775 | 0.307292 | 0.017873 | 0.000000 | 0.001809 | 0.000761 | 0.860541 | 3.992918 | 373.449219 | 25 | 13 |
| spring_petclinic_microservices | 7200 | full_r | 0.577759 | 1.613526 | 0.299033 | 0.017839 | 0.000000 | 0.000169 | 0.000757 | 0.858147 | 3.989196 | 373.175781 | 25 | 13 |
| spring_petclinic_microservices | 7200 | projected_r | 0.576243 | 1.603865 | 0.300929 | 0.017847 | 0.000152 | 0.000113 | 0.000451 | 0.853249 | 3.984351 | 373.460938 | 8 | 8 |
| spring_petclinic_microservices | 7200 | direct_r | 0.579528 | 1.367989 | 0.333477 | 0.012553 | 0.000000 | 0.000114 | 0.000498 | 0.851934 | 3.769763 | 373.289062 | 8 | 8 |
| spring_petclinic_microservices | 14400 | full_e | 1.160166 | 3.461016 | 0.646258 | 0.035798 | 0.000000 | 0.001906 | 0.000807 | 0.866552 | 6.806516 | 643.031250 | 25 | 13 |
| spring_petclinic_microservices | 14400 | full_r | 1.159551 | 3.477973 | 0.643505 | 0.036014 | 0.000000 | 0.000195 | 0.000793 | 0.865872 | 6.790318 | 643.218750 | 25 | 13 |
| spring_petclinic_microservices | 14400 | projected_r | 1.164832 | 3.482585 | 0.643518 | 0.034775 | 0.000196 | 0.000125 | 0.000450 | 0.868065 | 6.844784 | 643.070312 | 8 | 8 |
| spring_petclinic_microservices | 14400 | direct_r | 1.165152 | 2.962596 | 0.467204 | 0.025138 | 0.000000 | 0.000128 | 0.000497 | 0.856730 | 6.089743 | 643.199219 | 8 | 8 |

Stage entries are separate medians and need not sum to the median total. Representation is the remainder of instrumented construction, including observation rows and bookkeeping. Ready-model queries are separate in [ready-query-summary.csv](ready-query-summary.csv). All native record counts and per-operation stages are retained.

| Application | Common points | Equal exact forecasts | E MAE, pp | R MAE, pp | E intervals/refusals | R intervals/refusals |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| deathstarbench_social_network | 18 | 18 | 0.944444444 | 0.944444444 | 0/0 | 0/0 |
| opentelemetry_demo | 12 | 12 | 2.000000000 | 2.000000000 | 5/1 | 5/1 |
| spring_petclinic_microservices | 24 | 24 | 0.925925926 | 0.925925926 | 0/0 | 0/0 |

R probabilities use calibration only; the existing independently checked test success counts are evaluation targets. The original equal-operation/condition aggregation and campaign-cluster contrast routine are unchanged. This is retrospective analysis of already opened test data. Exact equality of forecasts directly preserves their errors on that support; it does not establish equality of E and R on every admissible state or a population equivalence guarantee. Intervals and structural refusals are not replaced by midpoint forecasts.

Complete tables: [paired costs](paired-costs.csv), [cost summary](cost-summary.csv), [operation stages](operation-stages.csv), [ready queries](ready-queries.csv), [forecast pairs](forecast-pairs.csv), [accuracy](accuracy-summary.csv), [support](forecast-support.csv), [paired accuracy](paired-accuracy.csv), [provenance](provenance.json).
