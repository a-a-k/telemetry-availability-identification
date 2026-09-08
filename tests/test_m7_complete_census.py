import unittest

from telemetry_availability.m7_complete_census import (
    census_rows, extract_observations, aggregate_operation, paired_rows, METHODS,
)


def prediction(method='proposed', value='0.8', placement='colocated', rep='0', operation='compose_post'):
    return dict(profile='deathstarbench_social_network', failure_law='N', repetition=rep,
                mode='full', scope='current' if placement=='colocated' else 'transfer',
                source_placement='colocated', target_placement=placement, method=method,
                operation=operation, prediction=value,
                status='estimated' if value else 'topology_ambiguous_target_fraction')


def observation_rows(placement='colocated', rep='0', operation='compose_post'):
    return [dict(profile='deathstarbench_social_network',target_placement=placement,
                 failure_law='N',repetition=rep,operation=operation,view=view,
                 test_requests='10',test_successes='6') for view in ('all_sequence','stable')]


class CompleteCensusTests(unittest.TestCase):
    def test_absent_forecast_retains_denominator_and_failure_reason(self):
        obs=extract_observations(observation_rows())
        values=census_rows([prediction(value='')],obs)
        self.assertEqual(len(values),2)
        for row in values:
            self.assertFalse(row['issued'])
            self.assertEqual(row['test_requests'],10)
            self.assertEqual(row['observed_availability'],.6)
            self.assertEqual(row['absolute_error_pp'],'')
            self.assertEqual(row['absence_reason'],'topology_ambiguous_target_fraction')

    def test_transfer_joins_target_and_rejects_conflicting_or_duplicate_data(self):
        source=observation_rows()
        source[0]['test_successes']='1'
        obs=extract_observations(source+observation_rows('split'))
        values=census_rows([prediction(placement='split')],obs)
        self.assertAlmostEqual(values[0]['signed_error_pp'],20)
        self.assertAlmostEqual(values[0]['brier_score'],.28)
        with self.assertRaisesRegex(ValueError,'contradictory'):
            extract_observations(source+observation_rows())
        with self.assertRaisesRegex(ValueError,'duplicate'):
            census_rows([prediction(),prediction()],obs)

    def test_coverage_and_condition_weighting_are_not_pooled_survivor_counts(self):
        obs=extract_observations(observation_rows()+observation_rows(rep='1')+observation_rows(rep='2'))
        values=census_rows([prediction(value='0.8'),prediction(value='0.8',rep='1'),prediction(value='0.6',rep='2')],obs)
        values=[r for r in values if r['view']=='all_sequence']
        values[2]['failure_law']='ND'
        summary=aggregate_operation(values,{'name':'artificial'},100,1)
        self.assertAlmostEqual(summary['absolute_error_pp'],10)
        values[1].update(issued=False,absence_reason='artificial_abstention')
        summary=aggregate_operation(values,{'name':'artificial'},100,1)
        self.assertEqual(summary['expected_campaigns'],3)
        self.assertEqual(summary['issued_campaigns'],2)
        self.assertEqual(summary['all_test_requests'],30)
        self.assertEqual(summary['issued_test_requests'],20)

    def test_partial_operation_pairs_remain_visible_without_complete_campaign(self):
        ops=('compose_post','read_home_timeline','read_user_timeline')
        obs=extract_observations([r for op in ops for r in observation_rows(operation=op)])
        preds=[prediction(method=method,operation=op,value='' if method=='proposed' and op=='compose_post' else '0.8') for method in METHODS for op in ops]
        common,summaries=paired_rows(census_rows(preds,obs),100,1)
        app=next(r for r in summaries if r['level']=='application_complete_campaigns' and r['view']=='all_sequence' and r['comparator']=='B2')
        self.assertEqual(app['common_operation_cells'],2)
        self.assertEqual(app['paired_campaigns'],0)
        self.assertEqual(app['absolute_error_pp_difference'],'')
        self.assertEqual(sum(r['common'] for r in common if r['comparator']=='B2'),4)


if __name__=='__main__':
    unittest.main()
