from copy import deepcopy
import unittest
from test_v3_application_execution_v1 import fixture
from test_v3_comparison_pipeline_v1 import identity
from telemetry_availability.v4_execution_binding_v1 import fit_operation
from telemetry_availability.v4_missingness_v1 import experiment,missing_order,Bounds


class MissingnessTests(unittest.TestCase):
    def test_keeps_incompatible_primary_record_and_original_unknowns(self):
        data,spec,_,_,declaration=fixture();declaration['backend_success_check_statuses']=['L4OK']
        model,_,diagnostics=fit_operation(data,'toy',spec,identity())
        # Deliberately contradictory independent outcome. The experiment must
        # preserve it, not select the convenient E=Y subset.
        records=[dict(diagnostics[0],outcome=False,lower=1,upper=1)]
        value=experiment(model,records,[0,.5,1],['uniform_coordinates','failure_associated_coordinates','whole_native_attempt'],17)
        self.assertEqual(value['reference']['failure_excluded'],1)
        self.assertTrue(all(r['attempts']==1 for r in value['rows']))
        complete=[r for r in value['rows'] if r['information']=='all_native']
        self.assertTrue(all(r['failure_excluded']==1 for r in complete))
        self.assertTrue(all(r['fully_observed_states']==0 for r in complete))
        all_missing=[r for r in value['rows'] if r['missing_fraction_requested']==1 and r['information']=='none']
        self.assertTrue(all(r['width']==1 for r in all_missing))
        self.assertTrue(value['qualification']['exact_core_predicate_agreement'])

    def test_outcome_only_changes_failure_associated_mask_generator(self):
        rows=[dict(request_id=f'r{i}',outcome=i%2==0,observation={'native':True,'timely':True}) for i in range(20)]
        flipped=[dict(r,outcome=not r['outcome']) for r in rows]
        for kind in ('uniform_coordinates','whole_native_attempt'):
            self.assertEqual(missing_order(rows,['native','timely'],'timely',kind,19),missing_order(flipped,['native','timely'],'timely',kind,19))
        self.assertNotEqual(missing_order(rows,['native','timely'],'timely','failure_associated_coordinates',19),
                            missing_order(flipped,['native','timely'],'timely','failure_associated_coordinates',19))


if __name__=='__main__':unittest.main()
