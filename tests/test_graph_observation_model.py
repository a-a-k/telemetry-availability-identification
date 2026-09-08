from copy import deepcopy
import unittest
from telemetry_availability.graph_observation_model import identify,evaluate,probe_verdict


class ObservedGraphTests(unittest.TestCase):
    def model(self, observations):
        graph=dict(services=['entry','a','b','target'],edges=[
            dict(source=a,target=b,type='sync',factors=[]) for a,b in
            [('entry','a'),('a','target'),('entry','b'),('b','target')]])
        return identify(graph,dict(entry=[[]],a=[['a']],b=[['b']],target=[[]]),
            dict(entry='entry',required=['target'],semantics='immediate_sync_all_required'),
            ['a','b'],observations,assumptions=['small artificial model'])

    def test_joint_law_is_used_without_independence_assumption(self):
        model=self.model([dict(a=False,b=False)]*3+[dict(a=True,b=True)]*7)
        result=evaluate(model)
        self.assertEqual(result['prediction'],.7)
        # Independent marginals would give .91 and are deliberately not substituted.
        self.assertNotAlmostEqual(result['prediction'],1-(1-.7)**2)

    def test_informative_missingness_returns_sharp_bounds(self):
        model=self.model([dict(a=True,b=None),dict(a=False,b=None)])
        result=evaluate(model)
        self.assertIsNone(result['prediction']);self.assertEqual((result['lower'],result['upper']),(.5,1.))
        completions=[self.model([dict(a=True,b=False),dict(a=False,b=b)]) for b in (False,True)]
        self.assertEqual([evaluate(x)['prediction'] for x in completions],[.5,1.])

    def test_target_can_be_known_with_unknown_coordinate(self):
        result=evaluate(self.model([dict(a=True,b=None)]))
        self.assertEqual(result['prediction'],1.)
        self.assertFalse(result['physical_cause_parameters_identified'])

    def test_graph_mutation_and_equivalence(self):
        model=self.model([dict(a=True,b=False)]*8+[dict(a=False,b=True)]*2)
        changed=deepcopy(model)
        changed['graph']['edges']=[e for e in changed['graph']['edges'] if e['source']!='a']
        self.assertEqual(evaluate(model)['prediction'],1.)
        self.assertEqual(evaluate(changed)['prediction'],.2)
        reversed_model=deepcopy(model);reversed_model['graph']['edges'].reverse()
        self.assertEqual(evaluate(model),evaluate(reversed_model))

    def test_haproxy_previous_result_and_unknown_are_distinct(self):
        self.assertTrue(probe_verdict('UP','* L7OK')['value'])
        self.assertTrue(probe_verdict('UP','* L7OK')['check_in_progress'])
        self.assertFalse(probe_verdict('DOWN','* L7TOUT')['value'])
        self.assertIsNone(probe_verdict('UP','L4OK')['value'])
        self.assertIsNone(probe_verdict('','')['value'])
        self.assertTrue(probe_verdict('UP','* L4OK',layer='L4')['value'])


if __name__=='__main__':unittest.main()
