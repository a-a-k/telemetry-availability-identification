"""Select the diagnosed semantic binding for newly acquired calibration data."""
from . import v3_comparison_candidates_v1 as orchestration
from .v4_execution_binding_v1 import fit_operation as diagnosed_fit
from .g0_aina_ordinary_v1 import identify_from_observed_graph as original_g0
from copy import deepcopy


def identify_g0(model):
    """Keep the competitor's historical-proxy parameter, on the shared graph.

    Giving G0 operation-window admission masks would silently change its frozen
    baseline semantics and deprive it of available probe observations.
    """
    source=deepcopy(model)
    replacements={'admitted_a':'probe_a','admitted_b':'probe_b'}
    source['replicas']={service:[[replacements.get(g,g) for g in gates] for gates in replicas]
        for service,replicas in source['replicas'].items()}
    ids=sorted({g for replicas in source['replicas'].values() for gates in replicas for g in gates})
    if not set(ids)<={'probe_a','probe_b'}: raise ValueError('G0 eligible replica scope changed')
    source['signal_ids']=ids
    source['observation_categories']=[dict(values=[row['historical_probe'][k] for k in ids],count=row['count'])
        for row in model['auxiliary_joint_categories']]
    result=original_g0(source)
    result['adaptation']['eligibility_binding']='original historical proxy observations, retained jointly by the revised builder'
    return result


def fit_operation(data, operation, spec, identity):
    model,report,_=diagnosed_fit(data,operation,spec,identity)
    for assumptions in (model['assumptions'],report['assumptions']):
        assumptions['historical_proxy_time_is_sampler_start_not_check_completion']=False
        assumptions['historical_proxy_snapshot_timestamp']='reading_completed; last HAProxy check can still be older'
    return model,report


def main():
    orchestration.VERSION='v4-confirmation-candidates-v1'
    orchestration.fit_operation=fit_operation
    orchestration.identify_from_observed_graph=identify_g0
    orchestration.main()


if __name__=='__main__': main()
