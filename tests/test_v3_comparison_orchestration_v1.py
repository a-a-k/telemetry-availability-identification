from copy import deepcopy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from test_v3_comparison_pipeline_v1 import fitted, frozen_case, identity, test_evaluator
from telemetry_availability.v3_comparison_candidates_v1 import replay
from telemetry_availability.v3_comparison_roles_v1 import seal_role, load_role
from telemetry_availability.v3_comparison_orchestration_v1 import planned_cases, freeze_case, evaluate_case
from telemetry_availability.v3_primary_projection import write, sha


class PhysicalPipelineTests(unittest.TestCase):
    def test_matrix_has_all240_main_identities_and_distinct6_preflight(self):
        path = Path('configs/v3_comparison_design_v1.json')
        _, design, main = planned_cases(path, 'main')
        _, _, preflight = planned_cases(path, 'preflight')
        self.assertEqual(len(main), 240)
        self.assertEqual(sum(len(design['applications'][c['profile']]) for c in main), 800)
        self.assertEqual(len({c['key'] for c in main}), 240)
        self.assertEqual(len(preflight), 6)
        self.assertNotEqual(main[0]['identity']['namespace'], preflight[0]['identity']['namespace'])

    def test_physical_freeze_then_evaluate_reads_only_exact_roles(self):
        data, _, receipt, graph, pmx = frozen_case()
        _, _, (forecasts, models, _, costs) = fitted()
        with TemporaryDirectory() as directory, patch.dict(os.environ,
                GITHUB_SHA='artificial-head', GITHUB_RUN_ID='artificial-run', GITHUB_RUN_ATTEMPT='1'):
            base = Path(directory); source = base/'input'; out = base/'frozen-output'
            evaluator = test_evaluator(data); evaluator['manifest.json']['layer'] = 'L4'
            seal_role(base/'closed', 'evaluator', identity(), evaluator)
            receipt['evaluator_seal_sha256'] = sha(base/'closed/seal.json')
            write(source/'receipt/receipt.json', receipt)
            seal_role(source/'graph/candidates', 'graph_candidates', identity(),
                {'candidates.json': graph, 'models.json': models, 'costs.json': costs, 'read-audit.json': {}})
            write(source/'graph/replay.json', dict(result=replay(forecasts, models), read_audit=dict(blocked=[]),
                candidate_seal_sha256=sha(source/'graph/candidates/seal.json')))
            seal_role(source/'pmx', 'pmx_candidates', identity(),
                {'candidates.json': pmx, 'costs.json': {'stages': []}, 'read-audit.json': {}})
            # An unsealed sibling file is present but never available to the evaluator's read boundary.
            write(base/'forbidden-native.json', {'should_not_be_read': True})
            freeze_case(source, out, identity(), ['toy'])
            evaluate_case(out/'frozen', base/'closed', base/'report', identity(), ['toy'], 1)
            result = json.loads((base/'report/evaluation.json').read_bytes())
            self.assertEqual(result['read_audit']['blocked'], [])
            self.assertEqual(len(result['read_audit']['actual_data_reads']), 8)
            self.assertEqual(result['views']['all_sequence']['operations']['toy']['attempts'], 1)
            self.assertNotIn(str(base/'forbidden-native.json'), result['read_audit']['actual_data_reads'])
            # Replacing a closed role by another validly sealed value fails its frozen digest.
            changed = deepcopy(evaluator); changed['requests.json'][0]['semantic_success'] = False
            seal_role(base/'other-closed', 'evaluator', identity(), changed)
            with self.assertRaises(ValueError):
                evaluate_case(out/'frozen', base/'other-closed', base/'bad-report', identity(), ['toy'], 1)

    def test_missing_replay_removes_graph_points_before_freeze(self):
        _, _, receipt, graph, pmx = frozen_case()
        _, _, (_, models, _, costs) = fitted()
        with TemporaryDirectory() as directory, patch.dict(os.environ,
                GITHUB_SHA='artificial-head', GITHUB_RUN_ID='artificial-run', GITHUB_RUN_ATTEMPT='1'):
            root = Path(directory)
            write(root/'input/receipt.json', receipt)
            seal_role(root/'input/graph', 'graph_candidates', identity(),
                {'candidates.json': graph, 'models.json': models, 'costs.json': costs, 'read-audit.json': {}})
            freeze_case(root/'input', root/'output', identity(), ['toy'])
            documents, _ = load_role(root/'output/frozen', 'frozen_candidates', identity())
            forecasts = documents['candidates.json']['forecasts']['toy']
            self.assertEqual(forecasts['Gstar']['status'], 'missing')
            self.assertEqual(forecasts['PMX']['status'], 'missing')
            self.assertIsNone(forecasts['Gstar']['probability'])
