"""Small, exhaustive semantic controls; no native libraries or saved models."""
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from itertools import product
import unittest
from test_graph_execution_bdd_v1 import tiny_model
from telemetry_availability.graph_execution_model_v1 import solve,validate
from telemetry_availability.exact_comparison_v2 import Direct,Prepared,project,snapshots,semantic_key
from telemetry_availability.exact_backend_common_v1 import FUNCTIONALS,estimates_from_pairs
from telemetry_availability.storm_exact_v1 import decision_graph
from telemetry_availability.storm_comparison_v2 import compact_graph


def graph_answer(actions,labels):
    @lru_cache(None)
    def visit(state,index,maximum):
        if state in labels:return Fraction(labels[state][index])
        values=[sum(p*visit(s,index,maximum) for s,p in a.items()) for a in actions[state]]
        return (max if maximum else min)(values)
    return estimates_from_pairs({n:(visit(0,i,False),visit(0,i,True)) for i,n in enumerate(FUNCTIONALS)})


class CorrectedComparisonTests(unittest.TestCase):
    def test_projection_all_completion_masks_and_missing_binding(self):
        for bits,missing in product(product((False,True,None),repeat=2),(False,True)):
            m=tiny_model()
            if missing:m['required_edge_completions'][0]['edge_id']='missing'
            for row in m['observation_categories']:
                for name,value in zip(m['completion_signals'],bits):row['values'][m['signal_ids'].index(name)]=value
            # Re-identical rows may emerge; use a single row to keep this control valid.
            m['observation_categories']=m['observation_categories'][:1];m['sample_count']=m['observation_categories'][0]['count']
            reduced=project(m,'completion_projected');validate(reduced)
            self.assertEqual(solve(m)['estimates'],solve(reduced)['estimates'])

    def test_both_ours_all_updates_and_representations(self):
        for cls,representation in product((Direct,Prepared),('original','completion_projected')):
            obj=cls();key=None;changes=[]
            for phase,raw in snapshots(tiny_model()):
                m=project(raw,representation);validate(m);new=semantic_key(m)
                if new!=key:obj.rebuild(m);key=new;changes.append(phase)
                self.assertEqual(obj.query(m),solve(raw)['estimates'],(cls,representation,phase))
            self.assertEqual(changes,['initial','structure','restore'])

    def test_storm_compaction_exact_and_count_update(self):
        for representation in ('original','completion_projected'):
            for phase,raw in snapshots(tiny_model()):
                m=project(raw,representation);actions,labels,columns=decision_graph(m)
                reduced,targets,groups=compact_graph(actions,labels,columns)
                self.assertLessEqual(len(reduced),len(actions))
                self.assertEqual(graph_answer(reduced,targets),solve(raw)['estimates'])
                changed=deepcopy(m)
                for i,row in enumerate(changed['observation_categories']):row['count']*=i+2
                changed['sample_count']=sum(r['count'] for r in changed['observation_categories'])
                reduced[0][0]={s:Fraction(sum(changed['observation_categories'][j]['count'] for j in js),changed['sample_count']) for s,js in groups.items()}
                self.assertEqual(graph_answer(reduced,targets),solve(changed)['estimates'])


if __name__=='__main__':unittest.main()
