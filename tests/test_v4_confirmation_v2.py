import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from telemetry_availability.v4_retry_controls_v2 import inject_rules,RULES
from telemetry_availability.v4_confirmation_orchestration_v2 import validate_acquisition,SOURCE_RUN,SOURCE_HEAD


class RepairTests(unittest.TestCase):
    def test_real_declared_template_keeps_frontend_and_injects_only_backend(self):
        source=Path('src/telemetry_availability/petclinic_runtime_v3.py').read_text()
        templates=[n.args[0].value for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Attribute) and n.func.attr=='write_text' and n.args
            and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str)
            and 'default_backend study_replicas' in n.args[0].value]
        self.assertEqual(len(templates),1)
        original=templates[0];self.assertEqual(original.count('backend study_replicas\n'),2)
        actual=inject_rules(original)
        self.assertIn('  default_backend study_replicas\nfrontend stats',actual)
        self.assertIn('\nbackend study_replicas\n'+RULES+'  option httpchk',actual)
        self.assertEqual(actual.replace(RULES,''),original)
        with self.assertRaises(ValueError):inject_rules(original+'backend study_replicas\n')
        with self.assertRaises(ValueError):inject_rules('  default_backend study_replicas\n')

    def test_source_map_cannot_replace_a_retained_cohort_or_reuse_lost_petclinic(self):
        with patch.dict(os.environ,{'GITHUB_RUN_ID':'new-run','GITHUB_SHA':'new-head'}):
            identity=dict(application='opentelemetry_demo')
            receipt=dict(identity=identity,acquisition_run=SOURCE_RUN,acquisition_head=SOURCE_HEAD,
                test_binding_seal_sha256='t',primary_closed_seal_sha256='p')
            validate_acquisition(receipt,identity)
            with self.assertRaises(ValueError):validate_acquisition(dict(receipt,acquisition_run='new-run',acquisition_head='new-head'),identity)
            pet=dict(application='spring_petclinic_microservices')
            with self.assertRaises(ValueError):validate_acquisition(dict(receipt,identity=pet),pet)
            validate_acquisition(dict(receipt,identity=pet,acquisition_run='new-run',acquisition_head='new-head'),pet)
