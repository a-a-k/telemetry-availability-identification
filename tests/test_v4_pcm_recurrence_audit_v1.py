import unittest
from telemetry_availability.v4_pcm_recurrence_audit_v1 import audit


def repository():
    def body(prefix,called):
        return f'<bodyBehaviour_Loop><steps_Behaviour xsi:type="seff:StartAction" id="{prefix}s" successor_AbstractAction="{prefix}c"/><steps_Behaviour xsi:type="seff:ExternalCallAction" id="{prefix}c" calledService_ExternalService="{called}" successor_AbstractAction="{prefix}e"/><steps_Behaviour xsi:type="seff:StopAction" id="{prefix}e"/></bodyBehaviour_Loop>'
    loops=''.join(f'<steps_Behaviour xsi:type="seff:LoopAction" id="l{i}" successor_AbstractAction="'+('l2' if i==1 else 'e')+'">'+body(str(i),'leaf')+'<iterationCount_LoopAction specification="IntPMF[(0;0.5)(1;0.5)]"/></steps_Behaviour>' for i in (1,2))
    return '<Repository xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><signature id="root" entityName="root"/><signature id="leaf" entityName="leaf"/><serviceEffectSpecifications__BasicComponent describedService__SEFF="root"><steps_Behaviour xsi:type="seff:StartAction" id="s" successor_AbstractAction="i"/><steps_Behaviour xsi:type="seff:InternalAction" id="i" successor_AbstractAction="l1"/>'+loops+'<steps_Behaviour xsi:type="seff:StopAction" id="e"/></serviceEffectSpecifications__BasicComponent><serviceEffectSpecifications__BasicComponent describedService__SEFF="leaf"><steps_Behaviour xsi:type="seff:StartAction" id="ls" successor_AbstractAction="li"/><steps_Behaviour xsi:type="seff:InternalAction" id="li" successor_AbstractAction="le"><internalFailureOccurrenceDescriptions__InternalAction failureProbability="0.2"/></steps_Behaviour><steps_Behaviour xsi:type="seff:StopAction" id="le"/></serviceEffectSpecifications__BasicComponent></Repository>'


class RecurrenceTests(unittest.TestCase):
    def test_separate_marginal_loops_are_not_a_mutually_exclusive_joint_choice(self):
        usage='<Usage><operationSignature__EntryLevelSystemCall href="extracted.repository#root"/></Usage>'
        result=audit(repository(),usage)
        self.assertEqual(result['probability'],.81)
        # An exactly-one joint choice would yield .8. The saved PCM loop
        # representation is instead (0.5 + 0.5*0.8)^2.
        self.assertNotEqual(result['probability'],.8)
        self.assertEqual(result['serialized_probability_exact'],'81/100')

    def test_unhandled_branch_is_refused_instead_of_approximated(self):
        usage='<Usage><operationSignature__EntryLevelSystemCall href="extracted.repository#root"/></Usage>'
        with self.assertRaisesRegex(ValueError,'unhandled action'):
            audit(repository().replace('seff:LoopAction','seff:BranchAction'),usage)


if __name__=='__main__':unittest.main()
