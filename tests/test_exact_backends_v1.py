from fractions import Fraction
from functools import lru_cache
from itertools import product
import unittest
from test_graph_execution_bdd_v1 import tiny_model
from telemetry_availability.graph_execution_model_v1 import predicates,solve
from telemetry_availability.exact_backend_common_v1 import Circuit,FUNCTIONALS,semantic_key,updates,estimates_from_pairs
from telemetry_availability.prepared_exact_v1 import PreparedSpecialized
from telemetry_availability.storm_exact_v1 import decision_graph


class ExactBackendTests(unittest.TestCase):
    def test_circuit_exhaustive(self):
        model=tiny_model();circuit=Circuit(model)
        for values in product((False,True),repeat=len(model['signal_ids'])):
            state=dict(zip(model['signal_ids'],values));self.assertEqual(circuit.evaluate(state),predicates(model,state))

    def test_updates_reuse_and_exact_prepared(self):
        original=tiny_model();old=None;backend=None;rebuilds=[]
        for phase,model in updates(original):
            key=semantic_key(model)
            if key!=old:backend=PreparedSpecialized(model);old=key;rebuilds.append(phase)
            self.assertEqual(backend.query(model),solve(model)['estimates'])
        self.assertEqual(rebuilds,['initial','structure','restore'])

    def test_mdp_projection_against_frozen_extrema(self):
        for phase,model in updates(tiny_model()):
            actions,labels,_=decision_graph(model)
            @lru_cache(None)
            def visit(state,name,maximum):
                if state in labels:return Fraction(labels[state][FUNCTIONALS.index(name)])
                values=[sum(p*visit(target,name,maximum) for target,p in action.items()) for action in actions[state]]
                return (max if maximum else min)(values)
            pairs={n:(visit(0,n,False),visit(0,n,True)) for n in FUNCTIONALS}
            self.assertEqual(estimates_from_pairs(pairs),solve(model)['estimates'],phase)


if __name__=='__main__':unittest.main()
