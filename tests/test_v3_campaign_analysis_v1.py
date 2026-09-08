from copy import deepcopy
import unittest
import numpy as np
from telemetry_availability.v3_campaign_analysis_v1 import analyze, paired_primary, cell_metrics, validate


METHODS=['Gstar','G0','PMX','B0']


def fixture():
    design={'applications':{'a':['x','y'],'b':['x','y'],'c':['x','y']},
            'placements':['colocated','split'],'laws':['N'],'repetitions':list(range(4))}
    rows=[]
    for app in design['applications']:
        for placement in design['placements']:
            for rep in design['repetitions']:
                ops={}
                for operation in design['applications'][app]:
                    # Correlated operation errors within a campaign, strong separation between clusters.
                    probs={'Gstar':.2+.1*rep,'G0':.1,'PMX':.15,'B0':0.0}
                    ops[operation]={'attempts':1 if operation=='x' else 1000,'successes':0,
                        'forecasts':{method:{'status':'ok','probability':prob} for method,prob in probs.items()}}
                rows.append({'campaign_id':f'{app}|{placement}|N|{rep}','application':app,'placement':placement,
                    'law':'N','repetition':rep,'view':'all_sequence','evaluator_status':'qualified','operations':ops})
    return design,rows


class V3CampaignAnalysisTests(unittest.TestCase):
    def test_six_contrasts_family_level_and_complete_census(self):
        design,rows=fixture();result=analyze(rows,design,METHODS)
        self.assertEqual(len(result['primary_contrasts']),6)
        self.assertEqual(result['method_slots'],24*2*4)
        contrast=result['primary_contrasts'][0]
        self.assertAlmostEqual(contrast['estimate_pp'],25)
        self.assertAlmostEqual(contrast['confidence_level'],.9916666666666667)
        self.assertEqual(contrast['bootstrap_draws'],10000)
        self.assertEqual(contrast['complete_common_campaigns'],8)
        self.assertFalse(contrast['finite_sample_family_coverage_guaranteed'])

    def test_bootstrap_draws_are_paired_whole_campaign_clusters(self):
        design,rows=fixture();rows=[r for r in rows if r['application']=='a']
        result=paired_primary(rows,['x','y'],'G0',[('colocated','N'),('split','N')],99)
        rng=np.random.Generator(np.random.PCG64(99));values=np.asarray([10.,20.,30.,40.])
        oracle=(values[rng.integers(0,4,size=(10000,4))].mean(axis=1)+
                values[rng.integers(0,4,size=(10000,4))].mean(axis=1))/2
        expected=np.quantile(oracle,[.05/12,1-.05/12],method='linear')
        np.testing.assert_allclose(result['interval_pp'],expected,atol=1e-12,rtol=0)
        self.assertAlmostEqual(result['bootstrap_sd_pp'],float(np.std(oracle,ddof=1)))
        reverse=paired_primary(list(reversed(rows)),['x','y'],'G0',[('colocated','N'),('split','N')],99)
        self.assertEqual(result,reverse)

    def test_equal_operation_weights_do_not_follow_attempt_counts(self):
        design,rows=fixture()
        for row in rows:
            row['operations']['x']['forecasts']['Gstar']['probability']=1.0
            row['operations']['y']['forecasts']['Gstar']['probability']=0.0
        result=analyze(rows,design,METHODS)
        self.assertAlmostEqual(result['applications']['a']['methods']['Gstar']['standardized_mean']['absolute_error_pp'],50.)
        self.assertAlmostEqual(result['primary_contrasts'][0]['estimate_pp'],40.)

    def test_absence_never_becomes_zero_and_partial_cells_remain_visible(self):
        design,rows=fixture()
        rows[0]['operations']['x']['forecasts']['PMX']={'status':'unsupported','probability':None,'reason':'no positive local support'}
        result=analyze(rows,design,METHODS);contrast=result['primary_contrasts'][1]
        self.assertEqual(contrast['common_cells'],15)
        self.assertEqual(contrast['complete_common_campaigns'],7)
        self.assertEqual(result['applications']['a']['methods']['PMX']['scored_cells'],15)
        self.assertEqual(result['applications']['a']['methods']['PMX']['absence_reasons'],{'no positive local support':1})
        absent=[r for r in result['attempted_census'] if r['forecast']['status']=='unsupported']
        self.assertEqual(len(absent),1);self.assertIsNone(absent[0]['metrics'])

    def test_empty_condition_and_empty_contrast_are_distinct(self):
        design,rows=fixture()
        for row in rows:
            if row['application']=='a' and row['placement']=='split':
                for op in row['operations'].values():
                    op['forecasts']['PMX']={'status':'missing','probability':None,'reason':'no candidate'}
        result=analyze(rows,design,METHODS);contrast=result['primary_contrasts'][1]
        self.assertEqual(contrast['retained_conditions'],1)
        self.assertEqual(contrast['planned_conditions'],2)
        self.assertEqual(contrast['support'][1]['complete_common_campaigns'],0)
        for row in rows:
            if row['application']=='a':
                for op in row['operations'].values():
                    op['forecasts']['PMX']={'status':'missing','probability':None,'reason':'no candidate'}
        result=analyze(rows,design,METHODS)
        contrast=result['primary_contrasts'][1]
        self.assertEqual(contrast['status'],'not_estimable_no_complete_common_campaign')
        self.assertIsNone(contrast['estimate_pp']);self.assertIsNone(contrast['interval_pp'])
        own=result['applications']['a']['methods']['PMX']
        self.assertEqual(len(own['own_support']),4)
        self.assertTrue(all(r['campaigns']==0 for r in own['own_support']))

    def test_one_common_campaign_does_not_produce_degenerate_confidence_claim(self):
        design,rows=fixture()
        for row in rows:
            if row['application']=='a' and row['placement']=='split' and row['repetition']!=0:
                row['evaluator_status']='unavailable';row['evaluator_reason']='archive absent'
        contrast=analyze(rows,design,METHODS)['primary_contrasts'][0]
        self.assertEqual(contrast['status'],'point_only_insufficient_independent_common_campaigns')
        self.assertIsNone(contrast['interval_pp'])

    def test_reject_duplicate_missing_nan_and_stable_substitution(self):
        design,rows=fixture()
        with self.assertRaises(AssertionError):validate(rows[:-1],design,METHODS)
        with self.assertRaises(AssertionError):validate(rows+[rows[0]],design,METHODS)
        bad=deepcopy(rows);bad[0]['operations']['x']['forecasts']['Gstar']['probability']=float('nan')
        with self.assertRaises(AssertionError):validate(bad,design,METHODS)
        bad=deepcopy(rows);bad[0]['view']='stable'
        with self.assertRaises(AssertionError):validate(bad,design,METHODS)
        bad_design=deepcopy(design);bad_design['repetitions'].append(0)
        with self.assertRaises(AssertionError):validate(rows,bad_design,METHODS)

    def test_brier_uses_all_outcomes_and_perfect_forecast_is_valid_zero(self):
        self.assertAlmostEqual(cell_metrics(.25,1,4)['brier'],.1875)
        self.assertEqual(cell_metrics(0,0,4)['absolute_error_pp'],0)


if __name__=='__main__':unittest.main()
