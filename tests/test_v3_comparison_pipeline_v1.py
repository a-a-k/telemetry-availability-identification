from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_v3_application_execution_v1 import fixture
from telemetry_availability.v3_application_execution_v2 import fit_operation as technical_fit
from telemetry_availability.v3_comparison_candidates_v1 import (
    build, replay, combine, GRAPH_METHODS, PMX_METHODS, METHODS, absent)
from telemetry_availability.v3_comparison_roles_v1 import (
    campaign_id, digest, load_role, seal_role)
from telemetry_availability.v3_comparison_evaluation_v1 import (
    evaluate, stable_membership, missing_campaign, transfer_census, cost_analysis, complete_analysis)
from telemetry_availability.v3_primary_projection import sha


def identity(app='spring_petclinic_microservices', placement='colocated'):
    return dict(application=app, placement=placement, law='NCD', repetition=0,
        namespace='artificial-only', data_role='artificial_control', protocol_sha256='a'*64)


def fitted():
    data, spec, request, spans, declaration = fixture()
    declaration['backend_success_check_statuses'] = ['L4OK']
    result = build(data, {'toy': spec}, identity())
    return data, spec, result


def frozen_case():
    data, spec, (forecasts, models, reports, costs) = fitted()
    receipt = dict(identity=identity(), graph_input_seal_sha256='b'*64,
        pmx_input_seal_sha256='c'*64, evaluator_seal_sha256='d'*64)
    graph = dict(identity=identity(), input_seal_sha256='b'*64, forecasts=forecasts)
    pmx = dict(identity=identity(), input_seal_sha256='c'*64,
        forecasts={'toy': {'PMX': absent('unsupported', 'positivity'),
                          'PMX_inclusive': dict(status='ok', probability=.8, reason=None)}})
    return data, combine(identity(), ['toy'], graph, pmx, receipt), receipt, graph, pmx


def test_evaluator(data):
    request = dict(data['requests.json'][0], period='test')
    # Known identical probes bracket [start-1s,end+1s].
    probes = [dict(data['probes.json'][0], observed_at=f'2026-01-01T00:00:0{i}+00:00') for i in range(4)]
    return {'requests.json': [request], 'probes.json': probes,
        'manifest.json': dict(identity=identity(), test_quality=dict(qualified=True, reason=None))}


class ProspectiveModelTests(unittest.TestCase):
    def test_numeric_core_exactly_matches_qualified_v2(self):
        data, spec, (forecasts, models, reports, costs) = fitted()
        _, old = technical_fit(data, 'toy', spec)
        self.assertEqual(reports['toy']['result_sha256'], old['result_sha256'])
        self.assertEqual(models['execution']['toy']['identity']['data_role'], 'artificial_control')
        self.assertEqual(models['execution']['toy']['assumptions']['data_role'], 'artificial_control')
        self.assertEqual(replay(forecasts, models)['execution_models'], 1)
        self.assertEqual(set(forecasts['toy']), set(GRAPH_METHODS))
        self.assertTrue(all(r['seconds'] >= 0 for r in costs['stages']))

    def test_business_label_flip_changes_b0_only(self):
        data, spec, (before, _, _, _) = fitted()
        data['requests.json'][0]['semantic_success'] = False
        after, _, _, _ = build(data, {'toy': spec}, identity())
        for method in set(GRAPH_METHODS)-{'B0'}:
            self.assertEqual(before['toy'][method], after['toy'][method])
        self.assertEqual(after['toy']['B0']['probability'], 0)

    def test_deadline_violation_keeps_attempt_and_changes_execution_not_reachability(self):
        data, spec, _ = fitted()
        data['requests.json'][0].update(completed_at='2026-01-01T00:00:03.01+00:00', semantic_success=False, timed_out=True)
        forecasts, models, _, _ = build(data, {'toy': spec}, identity())
        self.assertEqual(forecasts['toy']['Gstar']['probability'], 0)
        self.assertEqual(forecasts['toy']['GID']['probability'], 1)
        self.assertEqual(forecasts['toy']['G_without_deadline']['probability'], 1)
        self.assertEqual(models['execution']['toy']['sample_count'], 1)

    def test_ambiguous_latent_states_are_not_filled(self):
        data, spec, _ = fitted(); data['probes.json'] = []
        forecasts, models, _, _ = build(data, {'toy': spec}, identity())
        self.assertEqual(forecasts['toy']['Gstar']['status'], 'unsupported')
        self.assertIsNone(forecasts['toy']['Gstar']['probability'])
        self.assertEqual((forecasts['toy']['Gstar']['identified_lower'], forecasts['toy']['Gstar']['identified_upper']), (0, 1))
        self.assertEqual(forecasts['toy']['B0']['status'], 'ok')
        replay(forecasts, models)

    def test_missing_graph_preserves_all_method_absences_and_b0(self):
        data, spec, _ = fitted(); data['native.json']['spans'] = {}
        forecasts, models, _, _ = build(data, {'toy': spec}, identity())
        self.assertEqual(forecasts['toy']['Gstar']['status'], 'unsupported')
        self.assertEqual(forecasts['toy']['B0']['probability'], 1)
        replay(forecasts, models)

    def test_tampered_saved_probability_fails_replay(self):
        _, _, (forecasts, models, _, _) = fitted()
        forecasts['toy']['G0']['probability'] = .4
        with self.assertRaises(ValueError):
            replay(forecasts, models)


class RoleAndFreezeTests(unittest.TestCase):
    def test_exact_role_seal_detects_tamper_extra_file_and_wrong_campaign(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)/'role'
            docs = {'native.json': {}, 'requests.json': [], 'manifest.json': {}}
            seal_role(root, 'pmx_calibration', identity(), docs)
            expected = sha(root/'seal.json')
            self.assertEqual(load_role(root, 'pmx_calibration', identity(), expected)[0], docs)
            with self.assertRaises(ValueError):
                load_role(root, 'pmx_calibration', identity(placement='split'), expected)
            (root/'requests.json').write_bytes(b'[1]')
            with self.assertRaises(ValueError):
                load_role(root, 'pmx_calibration', identity(), expected)
            (root/'test.json').write_bytes(b'[]')
            with self.assertRaises(ValueError):
                load_role(root, 'pmx_calibration', identity(), expected)

    def test_conditional_pmx_absence_is_never_replaced_by_inclusive(self):
        _, frozen, _, _, _ = frozen_case()
        self.assertEqual(frozen['forecasts']['toy']['PMX']['status'], 'unsupported')
        self.assertIsNone(frozen['forecasts']['toy']['PMX']['probability'])
        self.assertEqual(frozen['forecasts']['toy']['PMX_inclusive']['probability'], .8)
        self.assertEqual(set(frozen['forecasts']['toy']), set(METHODS))

    def test_cross_input_candidate_substitution_is_rejected(self):
        _, _, receipt, graph, pmx = frozen_case()
        graph['input_seal_sha256'] = 'e'*64
        with self.assertRaises(ValueError):
            combine(identity(), ['toy'], graph, pmx, receipt)

    def test_missing_job_remains_counted_with_explicit_reason(self):
        _, _, receipt, graph, _ = frozen_case()
        with self.assertRaises(ValueError):
            combine(identity(), ['toy'], graph, None, receipt)
        frozen = combine(identity(), ['toy'], graph, None, receipt, dict(pmx='solver job failed'))
        self.assertEqual(frozen['forecasts']['toy']['PMX']['status'], 'missing')
        self.assertEqual(frozen['forecasts']['toy']['PMX']['reason'], 'solver job failed')


class EvaluatorTests(unittest.TestCase):
    def test_test_outcomes_change_metrics_not_sealed_predictions(self):
        data, frozen, _, _, _ = frozen_case(); evaluator = test_evaluator(data)
        before = digest(frozen)
        result = evaluate(frozen, evaluator, identity(), ['toy'], 1, 'L4')
        self.assertEqual(result['views']['all_sequence']['operations']['toy']['successes'], 1)
        evaluator['requests.json'][0].update(semantic_success=False, timed_out=True)
        changed = evaluate(frozen, evaluator, identity(), ['toy'], 1, 'L4')
        self.assertEqual(changed['views']['all_sequence']['operations']['toy']['successes'], 0)
        self.assertEqual(before, digest(frozen))
        self.assertEqual(changed['views']['all_sequence']['operations']['toy']['attempts'], 1)

    def test_stable_subset_never_replaces_primary_denominator(self):
        data, frozen, _, _, _ = frozen_case(); evaluator = test_evaluator(data)
        evaluator['probes.json'][1]['replica_a_backend_status'] = 'DOWN'
        report = evaluate(frozen, evaluator, identity(), ['toy'], 1, 'L4')
        self.assertEqual(report['views']['all_sequence']['operations']['toy']['attempts'], 1)
        self.assertEqual(report['views']['stable']['operations']['toy']['attempts'], 0)
        self.assertEqual(report['stable']['retained_fraction'], 0)

    def test_stable_requires_brackets_known_states_and_bounded_gaps(self):
        data, _, _, _, _ = frozen_case(); evaluator = test_evaluator(data)
        requests, probes = evaluator['requests.json'], evaluator['probes.json']
        self.assertTrue(all(stable_membership(requests, probes, 'L4')[0].values()))
        for changed in (probes[1:], [probes[0], probes[-1]], [dict(p, replica_a_backend_check_status='unknown') for p in probes]):
            self.assertFalse(any(stable_membership(requests, changed, 'L4')[0].values()))

    def test_incomplete_or_duplicate_or_calibration_test_rows_fail(self):
        data, frozen, _, _, _ = frozen_case(); evaluator = test_evaluator(data)
        for rows in ([], evaluator['requests.json']*2, data['requests.json']):
            changed = deepcopy(evaluator); changed['requests.json'] = rows
            with self.assertRaises(ValueError):
                evaluate(frozen, changed, identity(), ['toy'], 1, 'L4')

    def test_transfer_does_not_impute_target_law_and_accounts_missing_campaigns(self):
        design = dict(applications={app: ['toy'] for app in ('a', 'b', 'c')},
            placements=['colocated', 'split'], laws=['NCD'], repetitions=[0])
        campaigns = [missing_campaign(identity(app, placement), ['toy']) for app in design['applications'] for placement in design['placements']]
        transfer = transfer_census(campaigns, design)
        self.assertEqual(transfer['planned_slots'], 6*len(METHODS))
        self.assertEqual(transfer['point_coverage'], 0)
        self.assertTrue(all(r['target_error_pp'] is None and r['observed_change'] is None for r in transfer['census']))
        analysis = complete_analysis(campaigns, [], design, [])
        self.assertEqual(len(analysis['primary_contrasts']), 6)
        self.assertEqual(analysis['stable']['applications']['a']['Gstar']['planned_cells'], 2)
        self.assertEqual(analysis['costs']['measured_campaigns'], 0)

    def test_unknown_cost_is_not_zero_and_shared_stage_is_not_multiplied(self):
        cid = campaign_id(identity())
        record = dict(campaign_id=cid, job_role='graph', attempt_id='1', stages=[
            dict(method='shared_graph_family', stage='extraction', seconds=2),
            dict(method='G0', stage='solve', seconds=.1)])
        result = cost_analysis([record], {cid})
        self.assertIsNone(result['cold_integration_labor_seconds'])
        self.assertEqual(next(r['sum_seconds'] for r in result['stage_summaries'] if r['stage']=='extraction'), 2)
        with self.assertRaises(ValueError):
            cost_analysis([record, record], {cid})
